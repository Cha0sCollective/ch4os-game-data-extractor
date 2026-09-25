"""Loopback-only web browser for Ch4oS capture and SQLite game data."""

from __future__ import annotations

import argparse
from collections import deque
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
from pathlib import Path
import re
import sqlite3
import subprocess
import sys
import threading
from urllib.parse import parse_qs, unquote, urlsplit
import uuid
import webbrowser

from catalog import Catalog
from game_data_db import import_capture
from knowledge_store import KnowledgeStore
from recipe_analysis import analyze_database, compare_databases
from research_queue import submit_file, write_packets


ROOT = Path(__file__).resolve().parent
WEB = ROOT / "web"
MAX_UPLOAD_BYTES = 512 * 1024 * 1024


class AppState:
    def __init__(self, data_dir: Path, database: Path | None = None,
                 knowledge: Path | None = None):
        self.data_dir = data_dir.resolve()
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.knowledge = KnowledgeStore(knowledge or self.data_dir / "knowledge.sqlite")
        self.catalog = Catalog(database, self.knowledge) if database else None
        self.lock = threading.Lock()
        self.jobs: dict[str, dict] = {}
        self.running_job: str | None = None

    def current_catalog(self) -> Catalog | None:
        with self.lock:
            return self.catalog

    def select_database(self, path: Path) -> dict:
        catalog = Catalog(path, self.knowledge)
        overview = catalog.overview()
        with self.lock:
            self.catalog = catalog
        return overview

    def compare(self, source: Path) -> dict:
        current = self.current_catalog()
        if current is None:
            raise ValueError("open a current database first")
        if not source.is_file():
            raise ValueError(f"baseline file not found: {source}")
        if source.suffix.lower() == ".zip":
            database = self.data_dir / "databases" / f"baseline-{uuid.uuid4().hex[:12]}.sqlite"
            import_capture(source, database)
        elif source.suffix.lower() in {".sqlite", ".db"}:
            database = source
        else:
            raise ValueError("baseline must be a Ch4oS capture ZIP or SQLite database")
        return compare_databases(database, current.path)

    def prepare_research(self, mod_id: str, source_url: str = "") -> dict:
        current = self.current_catalog()
        if current is None:
            raise ValueError("open a capture database first")
        if not re.fullmatch(r"[a-z0-9_.-]+", mod_id):
            raise ValueError("select a valid mod ID")
        output = self.data_dir / "research" / current.snapshot_id[:12] / mod_id
        return write_packets(current.path, self.knowledge, mod_id, output, source_url)

    def start_job(self, kind: str, worker) -> str:
        with self.lock:
            if self.running_job is not None:
                raise ValueError("another capture or import is still running")
            job_id = uuid.uuid4().hex[:12]
            self.jobs[job_id] = {"id": job_id, "kind": kind, "status": "running",
                                 "log": deque(maxlen=120), "result": None, "error": None}
            self.running_job = job_id

        def run():
            try:
                result = worker(lambda message: self.add_log(job_id, message))
                with self.lock:
                    self.jobs[job_id]["result"] = result
                    self.jobs[job_id]["status"] = "completed"
            except Exception as exc:
                with self.lock:
                    self.jobs[job_id]["error"] = str(exc)
                    self.jobs[job_id]["status"] = "failed"
            finally:
                with self.lock:
                    self.running_job = None

        threading.Thread(target=run, name=f"ch4os-{kind}-{job_id}", daemon=True).start()
        return job_id

    def add_log(self, job_id: str, message: str) -> None:
        with self.lock:
            self.jobs[job_id]["log"].append(message.rstrip())

    def job(self, job_id: str) -> dict:
        with self.lock:
            if job_id not in self.jobs:
                raise ValueError("job not found")
            job = self.jobs[job_id]
            return {**job, "log": list(job["log"])}

    def import_job(self, source: Path) -> str:
        if not source.is_file() or source.suffix.lower() != ".zip":
            raise ValueError("select an existing capture ZIP")

        def worker(log):
            output = self.data_dir / "databases" / f"capture-{uuid.uuid4().hex[:12]}.sqlite"
            log(f"Importing {source}")
            summary = import_capture(source, output)
            overview = self.select_database(output)
            log(f"Database ready: {output}")
            return {"database": str(output), "summary": summary, "capture": overview}

        return self.start_job("import", worker)

    def capture_job(self, source: str, *, java: str = "", memory: str = "8G", eula: bool = False) -> str:
        if not eula:
            raise ValueError("accept the Minecraft EULA for this disposable server first")
        if not re.fullmatch(r"\d+[MG]", memory, re.IGNORECASE):
            raise ValueError("memory must look like 8G or 4096M")
        if not (source.startswith("https://") or
                (Path(source).is_file() and Path(source).suffix.lower() == ".zip")):
            raise ValueError("enter a Packwiz HTTPS link or an existing local pack ZIP")

        def worker(log):
            output = self.data_dir / "captures" / f"capture-{uuid.uuid4().hex[:12]}.zip"
            output.parent.mkdir(parents=True, exist_ok=True)
            command = [sys.executable, str(ROOT / "ch4os_capture.py"), source,
                       "--accept-minecraft-eula", "--output", str(output),
                       "--work-root", str(self.data_dir / "server-runs"), "--memory", memory]
            if java:
                command.extend(("--java", java))
            log(f"Capturing {source}")
            process = subprocess.Popen(
                command, cwd=ROOT, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                text=True, encoding="utf-8", errors="replace", bufsize=1,
                creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
            )
            assert process.stdout is not None
            for line in process.stdout:
                log(line)
            if process.wait() != 0:
                raise ValueError("capture failed; inspect the job log and retained server work directory")
            log(f"Capture saved: {output}")
            database = self.data_dir / "databases" / f"capture-{uuid.uuid4().hex[:12]}.sqlite"
            summary = import_capture(output, database)
            overview = self.select_database(database)
            log(f"Database ready: {database}")
            return {"capture_zip": str(output), "database": str(database),
                    "summary": summary, "capture": overview}

        return self.start_job("capture", worker)


def handler_for(state: AppState):
    class Handler(BaseHTTPRequestHandler):
        server_version = "Ch4oSLocal/1.0"

        def _send(self, status: int, content_type: str, body: bytes, extra: dict | None = None):
            self.send_response(status)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "no-store")
            self.send_header("X-Content-Type-Options", "nosniff")
            self.send_header("Content-Security-Policy", "default-src 'self'; style-src 'self'; script-src 'self'; img-src 'self' data:; connect-src 'self'; base-uri 'none'; form-action 'self'")
            if extra:
                for key, value in extra.items():
                    self.send_header(key, value)
            self.end_headers()
            self.wfile.write(body)

        def _json(self, status: int, value: object):
            self._send(status, "application/json; charset=utf-8",
                       json.dumps(value, ensure_ascii=False).encode("utf-8"))

        def _error(self, status: int, message: str):
            self._json(status, {"error": message})

        def _catalog(self) -> Catalog:
            catalog = state.current_catalog()
            if catalog is None:
                raise RuntimeError("import a capture or open a database first")
            return catalog

        def _query(self, query: str) -> dict[str, str]:
            return {key: values[0] for key, values in parse_qs(query, keep_blank_values=True).items()}

        def _number(self, value: str, default: int) -> int:
            try:
                return int(value)
            except ValueError:
                return default

        def _origin_ok(self) -> bool:
            host = self.headers.get("Host", "")
            port = self.server.server_port
            if host not in (f"127.0.0.1:{port}", f"localhost:{port}"):
                return False
            origin = self.headers.get("Origin")
            return origin is None or origin in (f"http://127.0.0.1:{port}", f"http://localhost:{port}")

        def do_GET(self):
            if not self._origin_ok():
                return self._error(403, "local app host only")
            try:
                parsed = urlsplit(self.path)
                path, args = parsed.path, self._query(parsed.query)
                if path in ("/", "/app.css", "/app.js"):
                    filename = "index.html" if path == "/" else path[1:]
                    content_type = {"index.html": "text/html", "app.css": "text/css",
                                    "app.js": "text/javascript"}[filename]
                    return self._send(200, content_type + "; charset=utf-8", (WEB / filename).read_bytes())
                if path == "/api/status":
                    catalog = state.current_catalog()
                    return self._json(200, {"database": str(catalog.path) if catalog else None,
                                            "capture": catalog.overview() if catalog else None,
                                            "data_directory": str(state.data_dir),
                                            "running_job": state.running_job})
                if path.startswith("/api/jobs/"):
                    return self._json(200, state.job(path.removeprefix("/api/jobs/")))
                catalog = self._catalog()
                if path == "/api/filters":
                    return self._json(200, catalog.filters())
                if path == "/api/adapter-definitions":
                    return self._json(200, catalog.adapter_definitions(args.get("q", ""), args.get("adapter", ""),
                                                                      int(args.get("limit", "50")), int(args.get("offset", "0"))))
                if path == "/api/adapter-definitions/detail":
                    return self._json(200, catalog.adapter_definition(args.get("adapter", ""),
                                                                       args.get("kind", ""), args.get("id", "")))
                if path == "/api/mods":
                    return self._json(200, catalog.mods(args.get("q", ""), args.get("all", "0") == "1",
                                                        self._number(args.get("limit", "50"), 50),
                                                        self._number(args.get("offset", "0"), 0)))
                if path == "/api/items":
                    return self._json(200, catalog.items(args.get("q", ""), args.get("mod", ""),
                                                         args.get("coverage", "all"),
                                                         self._number(args.get("limit", "50"), 50),
                                                         self._number(args.get("offset", "0"), 0)))
                if path.startswith("/api/items/"):
                    return self._json(200, catalog.item(unquote(path.removeprefix("/api/items/"))))
                if path == "/api/recipes":
                    return self._json(200, catalog.recipes(args.get("q", ""), args.get("type", ""),
                                                           args.get("mod", ""), args.get("coverage", "all"),
                                                           self._number(args.get("limit", "50"), 50),
                                                           self._number(args.get("offset", "0"), 0)))
                if path.startswith("/api/recipes/"):
                    return self._json(200, catalog.recipe(unquote(path.removeprefix("/api/recipes/"))))
                if path == "/api/coverage":
                    return self._json(200, catalog.coverage())
                if path == "/api/knowledge/mod-coverage":
                    mod_id = args.get("mod", "")
                    if not mod_id:
                        raise ValueError("mod is required")
                    return self._json(200, state.knowledge.mod_coverage(catalog.snapshot_id, mod_id, catalog.path))
                if path == "/api/research":
                    mod_id = args.get("mod", "")
                    return self._json(200, {"snapshot_id": catalog.snapshot_id,
                                            "jobs": state.knowledge.list_jobs(catalog.snapshot_id, mod_id),
                                            "findings": state.knowledge.list_findings(catalog.snapshot_id, mod_id,
                                                                                       args.get("status", "pending")),
                                            "coverage": state.knowledge.mod_coverage(catalog.snapshot_id, mod_id, catalog.path)
                                            if mod_id else None})
                if path.startswith("/api/research/jobs/"):
                    return self._json(200, state.knowledge.job(catalog.snapshot_id,
                                                                unquote(path.removeprefix("/api/research/jobs/"))))
                if path == "/api/analysis":
                    report = analyze_database(catalog.path)
                    report["findings"] = report["findings"][:100]
                    report["missing_ingredients"] = report["missing_ingredients"][:100]
                    report["overrides"] = report["overrides"][:100]
                    return self._json(200, report)
                if path == "/api/export":
                    kind, fmt = args.get("kind", ""), args.get("format", "")
                    content_type, body = catalog.export(kind, fmt, args.get("q", ""), args.get("mod", ""),
                                                        args.get("type", ""), args.get("coverage", "all"))
                    return self._send(200, content_type, body,
                                      {"Content-Disposition": f'attachment; filename="ch4os-{kind}.{fmt}"'})
                return self._error(404, "not found")
            except ValueError as exc:
                return self._error(404 if "not found" in str(exc) else 400, str(exc))
            except RuntimeError as exc:
                return self._error(409, str(exc))
            except (OSError, sqlite3.Error, KeyError, json.JSONDecodeError) as exc:
                return self._error(500, str(exc))

        def _read_json(self) -> dict:
            if self.headers.get("Content-Type", "").split(";", 1)[0] != "application/json":
                raise ValueError("expected application/json")
            size = self._number(self.headers.get("Content-Length", "0"), 0)
            if size < 1 or size > 1024 * 1024:
                raise ValueError("invalid JSON request size")
            value = json.loads(self.rfile.read(size))
            if not isinstance(value, dict):
                raise ValueError("expected JSON object")
            return value

        def _upload(self, folder: str) -> Path:
            if self.headers.get("Content-Type", "").split(";", 1)[0] != "application/zip":
                raise ValueError("expected a ZIP file upload")
            size = self._number(self.headers.get("Content-Length", "0"), 0)
            if size < 1 or size > MAX_UPLOAD_BYTES:
                raise ValueError("ZIP upload must be between 1 byte and 512 MB")
            destination = state.data_dir / folder / f"upload-{uuid.uuid4().hex[:12]}.zip"
            destination.parent.mkdir(parents=True, exist_ok=True)
            remaining = size
            try:
                with destination.open("xb") as output:
                    while remaining:
                        chunk = self.rfile.read(min(1024 * 1024, remaining))
                        if not chunk:
                            raise ValueError("incomplete ZIP upload")
                        output.write(chunk)
                        remaining -= len(chunk)
            except Exception:
                destination.unlink(missing_ok=True)
                raise
            return destination

        def do_POST(self):
            if not self._origin_ok():
                return self._error(403, "local app host only")
            try:
                path = urlsplit(self.path).path
                if path == "/api/upload-pack":
                    return self._json(200, {"path": str(self._upload("pack-sources"))})
                if path == "/api/upload-baseline":
                    return self._json(200, {"path": str(self._upload("baselines"))})
                if path == "/api/import":
                    return self._json(202, {"job_id": state.import_job(self._upload("uploads"))})
                data = self._read_json()
                if path == "/api/import-path":
                    return self._json(202, {"job_id": state.import_job(Path(str(data.get("path", ""))))})
                if path == "/api/open-database":
                    return self._json(200, state.select_database(Path(str(data.get("path", "")))))
                if path == "/api/capture":
                    return self._json(202, {"job_id": state.capture_job(
                        str(data.get("source", "")), java=str(data.get("java", "")),
                        memory=str(data.get("memory", "8G")), eula=data.get("eula") is True)})
                if path == "/api/compare":
                    report = state.compare(Path(str(data.get("baseline", ""))))
                    for key in ("added_recipes", "removed_recipes", "changed_recipes",
                                "new_conflicts", "resolved_conflicts"):
                        report[key] = report[key][:100]
                    return self._json(200, report)
                if path == "/api/research/prepare":
                    return self._json(200, state.prepare_research(str(data.get("mod_id", "")),
                                                                  str(data.get("source_url", ""))))
                if path == "/api/research/submit":
                    return self._json(200, {"submitted": submit_file(state.knowledge,
                                                                      Path(str(data.get("path", ""))))})
                if path == "/api/research/review":
                    catalog = self._catalog()
                    return self._json(200, state.knowledge.review_finding(
                        catalog.snapshot_id, str(data.get("finding_id", "")),
                        str(data.get("decision", "")), catalog.path, str(data.get("note", ""))))
                return self._error(404, "not found")
            except (ValueError, OSError, json.JSONDecodeError) as exc:
                return self._error(400, str(exc))

        def log_message(self, format, *args):
            if not self.path.startswith("/api/jobs/"):
                super().log_message(format, *args)

    return Handler


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--database", type=Path, help="Open an existing Ch4oS SQLite database")
    parser.add_argument("--knowledge", type=Path, help="Use an existing reviewed knowledge database")
    parser.add_argument("--data-dir", type=Path, default=ROOT / "runs" / "local-app")
    parser.add_argument("--port", type=int, default=8765)
    parser.add_argument("--no-browser", action="store_true")
    args = parser.parse_args(argv)
    if not 1 <= args.port <= 65535:
        parser.error("port must be between 1 and 65535")
    try:
        state = AppState(args.data_dir, args.database, args.knowledge)
        server = ThreadingHTTPServer(("127.0.0.1", args.port), handler_for(state))
        url = f"http://127.0.0.1:{server.server_port}/"
        print(f"Ch4oS local browser: {url}", flush=True)
        print(f"App data: {state.data_dir}", flush=True)
        if not args.no_browser:
            webbrowser.open(url)
        try:
            server.serve_forever()
        except KeyboardInterrupt:
            pass
        finally:
            server.server_close()
        return 0
    except (OSError, ValueError, sqlite3.Error) as exc:
        print(f"Local browser error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
