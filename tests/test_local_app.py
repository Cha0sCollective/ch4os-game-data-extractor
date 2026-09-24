import json
from contextlib import closing
from io import StringIO
from pathlib import Path
import shutil
import sqlite3
from tempfile import TemporaryDirectory
from threading import Thread
import time
import unittest
from urllib.error import HTTPError
from urllib.request import Request, urlopen
from http.server import ThreadingHTTPServer
from unittest.mock import patch

from game_data_db import import_capture
from local_app import AppState, handler_for
from test_game_data_db import capture


class LocalAppTests(unittest.TestCase):
    def test_capture_job_passes_pack_source_to_existing_runner_and_imports_result(self):
        with TemporaryDirectory() as folder:
            root = Path(folder)
            source = root / "pack.zip"
            capture(source)
            state = AppState(root / "app-data")
            commands = []

            class FakeProcess:
                def __init__(self, command, **kwargs):
                    commands.append(command)
                    output = Path(command[command.index("--output") + 1])
                    shutil.copyfile(source, output)
                    self.stdout = StringIO("Capture complete\n")

                def wait(self):
                    return 0

            with patch("local_app.subprocess.Popen", FakeProcess):
                job_id = state.capture_job(str(source), java="C:/Java21/java.exe", memory="4G", eula=True)
                for _ in range(100):
                    job = state.job(job_id)
                    if job["status"] != "running":
                        break
                    time.sleep(0.02)
            self.assertEqual(job["status"], "completed", job["error"])
            self.assertEqual(state.current_catalog().overview()["counts"]["items"], 2)
            self.assertIn("--accept-minecraft-eula", commands[0])
            self.assertIn("C:/Java21/java.exe", commands[0])

    def test_browse_export_and_import_through_loopback_api(self):
        with TemporaryDirectory() as folder:
            root = Path(folder)
            source, database = root / "capture.zip", root / "source.sqlite"
            capture(source)
            import_capture(source, database)
            state = AppState(root / "app-data", database)
            server = ThreadingHTTPServer(("127.0.0.1", 0), handler_for(state))
            thread = Thread(target=server.serve_forever, daemon=True)
            thread.start()
            base = f"http://127.0.0.1:{server.server_port}"

            def get(path):
                with urlopen(base + path) as response:
                    return json.load(response)

            def post(path, payload):
                request = Request(base + path, data=json.dumps(payload).encode(), method="POST",
                                  headers={"Content-Type": "application/json"})
                with urlopen(request) as response:
                    return json.load(response)

            try:
                self.assertEqual(get("/api/status")["capture"]["counts"]["items"], 2)
                self.assertEqual(get("/api/mods")["mods"][0]["name"], "Example")
                self.assertEqual(get("/api/mods?q=example")["mods"][0]["item_count"], 2)
                self.assertEqual(get("/api/mods?q=example")["mods"][0]["recipe_count"], 1)
                self.assertEqual(get("/api/filters")["mods"][0]["version"], "2.0")
                self.assertEqual(get("/api/items?q=ore")["items"][0]["id"], "example:ore")
                self.assertEqual(get("/api/items/example%3Aore")["uses"], ["example:smelt"])
                self.assertEqual(get("/api/items/example%3Aore")["makes"], [])
                voltage = next(prop for prop in get("/api/items/example%3Aore")["properties"]
                               if prop["property_key"] == "electrical.meter.maximum_voltage")
                self.assertEqual(voltage["value"], 500.0)
                self.assertEqual(voltage["conditions"], {"meaning": "measurement range"})
                self.assertEqual(get("/api/recipes?type=minecraft%3Asmelting")["total"], 1)
                self.assertEqual(get("/api/recipes/example%3Asmelt")["terms"][0]["kind"], "item_tag")
                self.assertEqual(get("/api/coverage")["item_components"][0]["status"], "captured")
                with urlopen(base + "/api/export?kind=items&format=csv&q=ore") as response:
                    self.assertIn(b"example:ore", response.read())

                with self.assertRaises(HTTPError) as error:
                    post("/api/capture", {"source": str(source), "eula": False})
                self.assertEqual(error.exception.code, 400)

                job_id = post("/api/import-path", {"path": str(source)})["job_id"]
                for _ in range(100):
                    job = get(f"/api/jobs/{job_id}")
                    if job["status"] != "running":
                        break
                    time.sleep(0.02)
                self.assertEqual(job["status"], "completed", job["error"])
                self.assertEqual(get("/api/status")["capture"]["counts"]["recipes"], 1)
                with closing(sqlite3.connect(job["result"]["database"])) as db:
                    self.assertEqual(db.execute("PRAGMA integrity_check").fetchone()[0], "ok")
            finally:
                server.shutdown()
                server.server_close()
                thread.join(timeout=5)


if __name__ == "__main__":
    unittest.main()
