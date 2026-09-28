"""Offline artifact lineage for reviewed knowledge; never alters raw captures.

Nested artifacts must descend from a captured outer SHA-256. Minecraft server
bundles provide a reviewed platform-version association, distinct from a binary
hash recorded during capture. Source matching is still a separate review.
"""

from __future__ import annotations

import argparse
from contextlib import closing
import hashlib
from io import BytesIO
import json
from pathlib import Path
import sqlite3
import tomllib
from zipfile import ZipFile

from knowledge_store import KnowledgeStore, capture_identity


def inspect_nested(capture: Path, path: Path) -> list[dict]:
    data = path.read_bytes()
    root_sha = hashlib.sha256(data).hexdigest()
    with closing(sqlite3.connect(capture.resolve().as_uri() + "?mode=ro", uri=True)) as db:
        if db.execute("SELECT 1 FROM installed_artifacts WHERE sha256=?", (root_sha,)).fetchone() is None:
            raise ValueError("outer artifact SHA-256 is not in this capture")
        installed = dict(db.execute("SELECT id,version FROM mods"))
    links = []

    def walk(payload: bytes, parent_sha: str, chain: str, depth: int) -> None:
        if depth > 8:
            raise ValueError("nested artifact depth exceeds 8")
        with ZipFile(BytesIO(payload)) as archive:
            if "META-INF/jarjar/metadata.json" not in archive.namelist():
                return
            metadata = json.loads(archive.read("META-INF/jarjar/metadata.json"))
            for entry in sorted(metadata.get("jars", []), key=lambda row: row["path"]):
                entry_path = entry["path"]
                child = archive.read(entry_path)
                child_sha = hashlib.sha256(child).hexdigest()
                full_entry = chain + "!/" + entry_path
                with ZipFile(BytesIO(child)) as child_archive:
                    names = child_archive.namelist()
                    descriptor = next((name for name in ("META-INF/neoforge.mods.toml", "META-INF/mods.toml")
                                       if name in names), None)
                    if descriptor:
                        manifest = child_archive.read("META-INF/MANIFEST.MF").decode("utf-8") if "META-INF/MANIFEST.MF" in names else ""
                        jar_version = next((line.partition(": ")[2].strip() for line in manifest.splitlines()
                                            if line.startswith("Implementation-Version: ")), None)
                        for mod in tomllib.loads(child_archive.read(descriptor).decode("utf-8")).get("mods", []):
                            version = mod.get("version")
                            if version == "${file.jarVersion}":
                                version = jar_version
                            mod_id = mod.get("modId")
                            if mod_id in installed:
                                if version != installed[mod_id]:
                                    raise ValueError(f"nested version differs from installed {mod_id}")
                                links.append({"kind": "nested", "mod_id": mod_id, "version": version,
                                              "artifact_sha256": child_sha, "file_name": entry_path.rsplit("/", 1)[-1],
                                              "root_sha256": root_sha, "parent_sha256": parent_sha,
                                              "entry_path": full_entry, "descriptor": descriptor})
                walk(child, child_sha, full_entry, depth + 1)

    walk(data, root_sha, path.name, 0)
    return sorted(links, key=lambda row: (row["mod_id"], row["entry_path"]))


def inspect_platform(capture: Path, path: Path) -> list[dict]:
    _, provenance, installed = capture_identity(capture)
    data = path.read_bytes()
    with ZipFile(BytesIO(data)) as archive:
        version = json.loads(archive.read("version.json"))["id"]
        if version != dict(installed).get("minecraft") or version != provenance.get("minecraft_version"):
            raise ValueError("platform artifact version differs from captured Minecraft")
        # Read the bundle's actual server member, not an arbitrary ZIP with a
        # version.json. Preserve the original bundle and server hash separately.
        entries = [line.split("\t") for line in archive.read("META-INF/versions.list").decode().splitlines() if line]
        selected = [row for row in entries if len(row) == 3 and row[1] == version]
        if len(selected) != 1:
            raise ValueError("platform bundle needs one matching server member")
        expected, _, member = selected[0]
        server_sha = hashlib.sha256(archive.read("META-INF/versions/" + member)).hexdigest()
        if server_sha != expected:
            raise ValueError("platform server member hash differs from bundle metadata")
    return [{"kind": "platform_version", "mod_id": "minecraft", "version": version,
             "artifact_sha256": hashlib.sha256(data).hexdigest(), "file_name": path.name,
             "metadata_version": version, "server_sha256": server_sha, "server_entry": member,
             "basis": "offline server bundle version matched to captured platform; binary hash was not captured"}]


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--database", type=Path, required=True)
    parser.add_argument("--knowledge", type=Path, required=True)
    parser.add_argument("--artifact", type=Path, required=True)
    parser.add_argument("--kind", choices=("nested", "platform"), required=True)
    parser.add_argument("--note", required=True)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    links = (inspect_nested if args.kind == "nested" else inspect_platform)(args.database, args.artifact)
    store = KnowledgeStore(args.knowledge)
    store.register_capture(args.database)
    store.review_artifact_links(args.database, links, args.note)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(links, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"associations": len(links), "kind": args.kind}))


if __name__ == "__main__":
    main()
