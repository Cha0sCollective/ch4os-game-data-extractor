"""Build a disposable NeoForge server from a Packwiz URL or ZIP and capture it."""

from __future__ import annotations

import argparse
import contextlib
import functools
import hashlib
import http.server
import json
import os
from pathlib import Path, PurePosixPath
import re
import shutil
import subprocess
import sys
import tempfile
import threading
import tomllib
from urllib.parse import urlsplit
from urllib.request import urlopen
import uuid
import zipfile


PACKWIZ_INSTALLER_URL = (
    "https://github.com/packwiz/packwiz-installer/releases/download/v0.5.14/"
    "packwiz-installer.jar"
)
PACKWIZ_INSTALLER_SHA256 = "c9f646908d340d84773948a9a7d98bc1dae250d35e1016dc6e2b8459760b5598"
PACKWIZ_BOOTSTRAP_URL = (
    "https://github.com/packwiz/packwiz-installer-bootstrap/releases/download/v0.0.3/"
    "packwiz-installer-bootstrap.jar"
)
PACKWIZ_BOOTSTRAP_SHA256 = "a8fbb24dc604278e97f4688e82d3d91a318b98efc08d5dbfcbcbcab6443d116c"
PACK_URL_RE = re.compile(r"https://[^\s\"']+?/pack\.toml(?:\?[^\s\"']*)?")
VERSION_RE = re.compile(r"^[0-9A-Za-z.+-]+$")


class CaptureError(RuntimeError):
    pass


def download(url: str, target: Path, limit: int) -> None:
    target.parent.mkdir(parents=True, exist_ok=True)
    with urlopen(url, timeout=60) as response, target.open("wb") as output:
        if urlsplit(response.url).scheme != "https":
            raise CaptureError(f"Download redirected away from HTTPS: {url}")
        size = 0
        while chunk := response.read(1024 * 1024):
            size += len(chunk)
            if size > limit:
                raise CaptureError(f"Download exceeds size limit: {url}")
            output.write(chunk)


def normalize_pack_url(url: str) -> str:
    """Accept a normal GitHub file link as well as its raw Packwiz URL."""
    parsed = urlsplit(url)
    if parsed.netloc.lower() == "github.com":
        pieces = parsed.path.strip("/").split("/")
        if len(pieces) >= 5 and pieces[2] == "blob" and pieces[-1] == "pack.toml":
            return "https://raw.githubusercontent.com/" + "/".join(
                [pieces[0], pieces[1], *pieces[3:]]
            )
    return url


def read_pack_url(url: str) -> bytes:
    parsed = urlsplit(url)
    if parsed.scheme != "https" or not parsed.netloc or not parsed.path.endswith("/pack.toml"):
        raise CaptureError("Packwiz source must be an HTTPS pack.toml URL")
    with urlopen(url, timeout=60) as response:
        if urlsplit(response.url).scheme != "https":
            raise CaptureError("Packwiz URL redirected away from HTTPS")
        data = response.read(1024 * 1024 + 1)
    if len(data) > 1024 * 1024:
        raise CaptureError("pack.toml exceeds 1 MiB")
    return data


def parse_pack(data: bytes) -> dict[str, str]:
    try:
        pack = tomllib.loads(data.decode("utf-8-sig"))
        versions = pack["versions"]
        minecraft = versions["minecraft"]
        neoforge = versions["neoforge"]
    except (UnicodeError, ValueError, KeyError, TypeError) as exc:
        raise CaptureError("pack.toml needs [versions] minecraft and neoforge values") from exc
    if not isinstance(minecraft, str) or not isinstance(neoforge, str):
        raise CaptureError("Packwiz Minecraft and NeoForge versions must be strings")
    if not VERSION_RE.fullmatch(minecraft) or not VERSION_RE.fullmatch(neoforge):
        raise CaptureError("Packwiz version contains unsupported characters")
    if minecraft != "1.21.1" or not neoforge.startswith("21.1."):
        raise CaptureError(
            f"This exporter build supports Minecraft 1.21.1 / NeoForge 21.1.x; "
            f"pack requests {minecraft} / {neoforge}"
        )
    return {"name": str(pack.get("name", "Packwiz pack")), "minecraft": minecraft, "neoforge": neoforge}


def safe_zip_path(name: str) -> PurePosixPath:
    path = PurePosixPath(name)
    if (path.is_absolute() or not path.parts or ".." in path.parts
            or "\\" in name or ":" in name or any(part in ("", ".") for part in path.parts)):
        raise CaptureError(f"Unsafe ZIP entry: {name}")
    return path


def extract_embedded_pack(archive: zipfile.ZipFile, pack_entry: str, destination: Path) -> None:
    root = PurePosixPath(pack_entry).parent
    total = 0
    for entry in archive.infolist():
        path = safe_zip_path(entry.filename)
        if entry.is_dir():
            continue
        try:
            relative = path.relative_to(root)
        except ValueError:
            continue
        if not relative.parts:
            continue
        # Ignore symlinks and keep the extraction rooted in our disposable directory.
        if ((entry.external_attr >> 16) & 0o170000) == 0o120000:
            raise CaptureError(f"ZIP contains a symbolic link: {entry.filename}")
        total += entry.file_size
        if total > 2 * 1024**3:
            raise CaptureError("Bundled Packwiz files exceed 2 GiB")
        target = destination.joinpath(*relative.parts)
        target.parent.mkdir(parents=True, exist_ok=True)
        with archive.open(entry) as source, target.open("wb") as output:
            shutil.copyfileobj(source, output)


def resolve_source(source: str, scratch: Path) -> tuple[dict[str, str], str | None, Path | None]:
    """Return parsed pack, remote URL, and local served directory if bundled."""
    if source.startswith("https://") and urlsplit(source).path.endswith("/pack.toml"):
        url = normalize_pack_url(source)
        return parse_pack(read_pack_url(url)), url, None

    if source.startswith("https://") and urlsplit(source).path.lower().endswith(".zip"):
        archive_path = scratch / "pack-source.zip"
        download(source, archive_path, 1024**3)
    else:
        archive_path = Path(source).expanduser().resolve()
        if not archive_path.is_file() or archive_path.suffix.lower() != ".zip":
            raise CaptureError("Source must be a Packwiz pack.toml URL or a local/HTTPS ZIP")

    with zipfile.ZipFile(archive_path) as archive:
        entries = {entry.filename: entry for entry in archive.infolist() if not entry.is_dir()}
        if len(entries) != sum(not entry.is_dir() for entry in archive.infolist()):
            raise CaptureError("ZIP contains duplicate file names")
        names = list(entries)
        for name in names:
            safe_zip_path(name)
        embedded = [name for name in names if PurePosixPath(name).name == "pack.toml"]
        if len(embedded) > 1:
            raise CaptureError("ZIP contains more than one pack.toml")
        if embedded:
            if entries[embedded[0]].file_size > 1024 * 1024:
                raise CaptureError("pack.toml exceeds 1 MiB")
            data = archive.read(embedded[0])
            if len(data) > 1024 * 1024:
                raise CaptureError("pack.toml exceeds 1 MiB")
            info = parse_pack(data)
            destination = scratch / "pack-source"
            extract_embedded_pack(archive, embedded[0], destination)
            return info, None, destination

        configs = [name for name in names if PurePosixPath(name).name == "instance.cfg"]
        if len(configs) != 1:
            raise CaptureError("ZIP needs one bundled pack.toml or one Prism instance.cfg")
        if entries[configs[0]].file_size > 1024 * 1024:
            raise CaptureError("instance.cfg exceeds 1 MiB")
        config = archive.read(configs[0]).decode("utf-8-sig")
        prelaunch = next((line for line in config.splitlines() if line.startswith("PreLaunchCommand=")), "")
        links = PACK_URL_RE.findall(prelaunch)
        if len(links) != 1:
            raise CaptureError("Prism ZIP needs exactly one Packwiz pack.toml URL")
        url = normalize_pack_url(links[0])
        return parse_pack(read_pack_url(url)), url, None


@contextlib.contextmanager
def serve_pack(directory: Path):
    class QuietHandler(http.server.SimpleHTTPRequestHandler):
        def log_message(self, format: str, *args: object) -> None:
            pass

    handler = functools.partial(QuietHandler, directory=str(directory))
    server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield f"http://127.0.0.1:{server.server_port}/pack.toml"
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def run(command: list[str], cwd: Path, log: Path, *, env: dict[str, str] | None = None,
        timeout: int | None = None) -> None:
    print(f"Running: {command[0]} {command[1] if len(command) > 1 else ''} (log: {log})", flush=True)
    with log.open("w", encoding="utf-8", errors="replace") as output:
        try:
            result = subprocess.run(command, cwd=cwd, env=env, stdout=output,
                                    stderr=subprocess.STDOUT, timeout=timeout)
        except subprocess.TimeoutExpired as exc:
            raise CaptureError(f"Command timed out; inspect {log}") from exc
    if result.returncode:
        raise CaptureError(f"Command failed ({result.returncode}); inspect {log}")


def update_properties(path: Path) -> None:
    values = {
        "server-ip": "127.0.0.1",
        "server-port": "0",
        "enable-query": "false",
        "enable-rcon": "false",
        "online-mode": "true",
        "max-players": "1",
        "motd": "Ch4oS disposable data capture",
    }
    existing = path.read_text(encoding="utf-8") if path.exists() else ""
    lines = [line for line in existing.splitlines() if line.split("=", 1)[0].strip() not in values]
    lines.extend(f"{key}={value}" for key, value in values.items())
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def verify_export(directory: Path) -> dict:
    manifest_path = directory / "manifest.json"
    if not manifest_path.is_file():
        raise CaptureError("No export manifest was produced; inspect the server log")
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    if manifest.get("format") != "create-handbook-runtime-export-v1":
        raise CaptureError("Unsupported export manifest format")
    for entry in manifest.get("files", []):
        name = entry["name"]
        if PurePosixPath(name).name != name:
            raise CaptureError(f"Unsafe manifest entry: {name}")
        path = directory / name
        if not path.is_file() or path.stat().st_size != entry["bytes"] or sha256(path) != entry["sha256"]:
            raise CaptureError(f"Manifest check failed: {name}")
    return manifest


def capture(args: argparse.Namespace, info: dict[str, str], url: str | None, local_root: Path | None,
            scratch: Path) -> Path:
    if not args.accept_minecraft_eula:
        raise CaptureError("Capture requires --accept-minecraft-eula (https://www.minecraft.net/eula)")
    java = args.java or shutil.which("java")
    if not java:
        raise CaptureError("Java 21 was not found; pass --java with its executable path")
    check = subprocess.run([java, "-version"], capture_output=True, text=True)
    if check.returncode or not re.search(r'\bversion "21(?:\.|\")', check.stderr + check.stdout):
        raise CaptureError("This NeoForge exporter requires Java 21")

    exporter = (args.exporter_jar or Path(__file__).parent / "build/libs/create_runtime_exporter-0.5.0.jar")
    exporter = Path(exporter).expanduser().resolve()
    if not exporter.is_file():
        raise CaptureError(f"Build the exporter first or pass --exporter-jar: {exporter}")

    server = scratch / "server"
    server.mkdir()
    (server / ".ch4os-disposable-instance").write_text("ch4os-disposable-v1\n", encoding="utf-8")
    output = Path(args.output).expanduser().resolve()
    if output.exists():
        raise CaptureError(f"Output already exists: {output}")
    if output == scratch or scratch in output.parents or output in scratch.parents:
        raise CaptureError("Output must be outside the disposable work directory")

    installer = scratch / "neoforge-installer.jar"
    version = info["neoforge"]
    neo_url = (f"https://maven.neoforged.net/releases/net/neoforged/neoforge/{version}/"
               f"neoforge-{version}-installer.jar")
    print(f"Installing Minecraft {info['minecraft']} / NeoForge {version}", flush=True)
    download(neo_url, installer, 200 * 1024**2)
    run([java, "-jar", str(installer), "--installServer"], server,
        scratch / "neoforge-install.log", timeout=30 * 60)

    packwiz = server / "packwiz-installer.jar"
    download(PACKWIZ_INSTALLER_URL, packwiz, 30 * 1024**2)
    if sha256(packwiz) != PACKWIZ_INSTALLER_SHA256:
        raise CaptureError("Packwiz installer download did not match the expected release")
    bootstrap = server / "packwiz-installer-bootstrap.jar"
    download(PACKWIZ_BOOTSTRAP_URL, bootstrap, 30 * 1024**2)
    if sha256(bootstrap) != PACKWIZ_BOOTSTRAP_SHA256:
        raise CaptureError("Packwiz bootstrap download did not match the expected release")
    with (serve_pack(local_root) if local_root else contextlib.nullcontext(url)) as pack_url:
        print(f"Installing server-side Packwiz files from {pack_url}", flush=True)
        run([java, "-jar", str(bootstrap), "--bootstrap-no-update", "-g", "-s", "server", pack_url],
            server, scratch / "packwiz-install.log", timeout=30 * 60)

    (server / "mods").mkdir(exist_ok=True)
    shutil.copy2(exporter, server / "mods" / exporter.name)
    update_properties(server / "server.properties")
    (server / "eula.txt").write_text("eula=true\n", encoding="utf-8")
    evidence = scratch / "evidence"
    launcher = server / "libraries/net/neoforged/neoforge" / version
    args_file = launcher / ("win_args.txt" if os.name == "nt" else "unix_args.txt")
    if not args_file.is_file():
        raise CaptureError(f"NeoForge installation did not create {args_file}")
    environment = os.environ.copy()
    environment.update({
        "HANDBOOK_EXPORT_ENABLED": "true",
        "HANDBOOK_EXPORT_PROFILE": "neoforge-1.21.1",
        "HANDBOOK_EXPORT_CONFIRM": "DISPOSABLE_INSTANCE",
        "HANDBOOK_EXPORT_SCOPE": "pack",
        "HANDBOOK_EXPORT_PACK_CONFIRM": "EXPORT_ALL_PACK_RUNTIME_FACTS",
        "HANDBOOK_EXPORT_OUTPUT": str(evidence),
        "HANDBOOK_EXPORT_AUTOSTOP": "true",
    })
    print("Starting disposable loopback-only server and collecting pack data", flush=True)
    run([java, f"-Xmx{args.memory}", f"@{args_file.relative_to(server).as_posix()}", "nogui"],
        server, scratch / "server.log", env=environment, timeout=args.server_timeout_minutes * 60)
    manifest = verify_export(evidence)
    output.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(output, "x", compression=zipfile.ZIP_DEFLATED, compresslevel=6) as archive:
        for path in sorted(evidence.iterdir()):
            if path.is_file():
                archive.write(path, path.name)
    print(f"Capture complete: {output} ({len(manifest['files'])} verified evidence files)", flush=True)
    return output


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source", help="Packwiz pack.toml HTTPS URL or Packwiz/Prism ZIP")
    parser.add_argument("--inspect", action="store_true", help="Show pack versions without installing")
    parser.add_argument("--accept-minecraft-eula", action="store_true", help="Accept the Minecraft EULA for this disposable server")
    parser.add_argument("--output", type=Path, help="New capture ZIP path")
    parser.add_argument("--work-root", type=Path, default=Path(__file__).parent / "runs")
    parser.add_argument("--exporter-jar", type=Path)
    parser.add_argument("--java", help="Java 21 executable")
    parser.add_argument("--memory", default="8G", help="Server maximum heap, e.g. 8G")
    parser.add_argument("--server-timeout-minutes", type=int, default=60)
    args = parser.parse_args(argv)
    if not re.fullmatch(r"\d+[MG]", args.memory, re.IGNORECASE):
        parser.error("--memory must look like 8G or 4096M")
    if args.server_timeout_minutes < 1:
        parser.error("--server-timeout-minutes must be positive")
    try:
        if args.inspect:
            with tempfile.TemporaryDirectory(prefix="ch4os-inspect-") as temporary:
                info, url, root = resolve_source(args.source, Path(temporary))
                print(json.dumps({**info, "packwiz_url": url, "bundled_pack": root is not None}, indent=2))
        else:
            if args.output is None:
                parser.error("--output is required for capture")
            work_root = args.work_root.expanduser().resolve()
            work_root.mkdir(parents=True, exist_ok=True)
            scratch = work_root / f"capture-{uuid.uuid4().hex[:12]}"
            scratch.mkdir()
            print(f"Disposable work directory: {scratch}", flush=True)
            info, url, root = resolve_source(args.source, scratch)
            print(json.dumps(info, indent=2), flush=True)
            capture(args, info, url, root, scratch)
        return 0
    except (CaptureError, OSError, zipfile.BadZipFile) as exc:
        print(f"Capture error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
