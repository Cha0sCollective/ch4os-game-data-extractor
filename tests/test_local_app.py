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
from catalog import Catalog
from local_app import AppState, handler_for
from test_game_data_db import capture


class LocalAppTests(unittest.TestCase):
    def test_item_exposes_registered_display_link_roles(self):
        with TemporaryDirectory() as folder:
            root = Path(folder)
            source, database = root / "capture.zip", root / "source.sqlite"
            capture(source, adapter_rows=True)
            import_capture(source, database)
            with closing(sqlite3.connect(database)) as db:
                db.execute(
                    "INSERT INTO adapter_definitions (adapter_id, kind, id, status, attributes_json, source_record_json) "
                    "VALUES (?, ?, ?, ?, ?, ?)",
                    ("create_display_links", "display_source", "create:item_count", "captured_directly",
                     json.dumps({"implementation_class": "example.ItemCountSource"}), "{}"))
                db.execute(
                    "INSERT INTO adapter_relations (adapter_id, subject_kind, subject_id, predicate, "
                    "object_kind, object_id, status, attributes_json, source_record_json) "
                    "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                    ("create_display_links", "item", "example:ore", "provides_display_source",
                     "display_source", "create:item_count", "captured_directly",
                     json.dumps({"registration_basis": ["block entity type example:ore"]}), "{}"))
                db.commit()
            role = Catalog(database).item("example:ore")["display_link_roles"][0]
            self.assertEqual(role["id"], "create:item_count")
            self.assertEqual(role["predicate"], "provides_display_source")
            self.assertEqual(role["link_attributes"]["registration_basis"], ["block entity type example:ore"])

    def test_recipe_exposes_verified_cross_mod_relation(self):
        with TemporaryDirectory() as folder:
            root = Path(folder)
            source, database = root / "capture.zip", root / "source.sqlite"
            capture(source, adapter_rows=True)
            import_capture(source, database)
            with closing(sqlite3.connect(database)) as db:
                db.execute(
                    "INSERT INTO adapter_relations (adapter_id, subject_kind, subject_id, predicate, "
                    "object_kind, object_id, status, attributes_json, source_record_json) "
                    "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                    ("sliceanddice", "recipe", "example:smelt", "converted_to", "recipe",
                     "sliceanddice:cutting/example/smelt", "captured_directly",
                     json.dumps({"target_recipe_type": "sliceanddice:cutting"}), "{}"))
                db.commit()
            relation = Catalog(database).recipe("example:smelt")["cross_mod_relations"][0]
            self.assertEqual(relation["object_id"], "sliceanddice:cutting/example/smelt")
            self.assertEqual(relation["attributes"]["target_recipe_type"], "sliceanddice:cutting")

    def test_item_exposes_linked_cc_peripheral_methods(self):
        with TemporaryDirectory() as folder:
            root = Path(folder)
            source, database = root / "capture.zip", root / "source.sqlite"
            capture(source, adapter_rows=True)
            import_capture(source, database)
            with closing(sqlite3.connect(database)) as db:
                db.execute(
                    "INSERT INTO adapter_definitions (adapter_id, kind, id, status, attributes_json, source_record_json) "
                    "VALUES (?, ?, ?, ?, ?, ?)",
                    ("computercraft_peripherals", "cc_peripheral_api", "example:OrePeripheral",
                     "captured_directly", json.dumps({"provider_mod": "example", "provider_version": "2.0",
                                                      "lua_methods": [{"java_name": "voltage", "lua_names": ["voltage"]}]}), "{}"))
                db.execute(
                    "INSERT INTO adapter_relations (adapter_id, subject_kind, subject_id, predicate, "
                    "object_kind, object_id, status, conditions_json, source_record_json) "
                    "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                    ("computercraft_peripherals", "item", "example:ore", "exposes_cc_peripheral",
                     "cc_peripheral_api", "example:OrePeripheral", "captured_directly",
                     json.dumps({"attachment": "placed block"}), "{}"))
                db.commit()
            peripheral = Catalog(database).item("example:ore")["cc_peripherals"][0]
            self.assertEqual(peripheral["attributes"]["lua_methods"][0]["lua_names"], ["voltage"])
            self.assertEqual(peripheral["link_conditions"]["attachment"], "placed block")

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
            capture(source, adapter_rows=True)
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
                self.assertEqual(get("/api/filters")["adapters"][0]["definition_count"], 2)
                self.assertEqual(get("/api/adapter-definitions?adapter=example")["total"], 2)
                definition = get("/api/adapter-definitions/detail?adapter=example&kind=fuel&id=example%3Aingot_fuel")
                self.assertEqual(definition["attributes"], {"burn_ticks": 800})
                self.assertEqual(definition["source_pack_id"], "mod/example")
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
                prepared = post("/api/research/prepare", {"mod_id": "example"})
                self.assertEqual(prepared["job_count"], 1)
                research = get("/api/research?mod=example")
                self.assertEqual(research["coverage"]["item_count"], 2)
                self.assertEqual(len(research["jobs"]), 1)
                finding = {"format": "ch4os-research-finding-v1", "snapshot_id": research["snapshot_id"],
                           "job_id": research["jobs"][0]["id"], "finding_id": "example:missing_behavior",
                           "record_type": "gap", "subject_kind": "item", "subject_id": "example:ore",
                           "description": "Unknown ore behavior"}
                findings_path = root / "findings.jsonl"
                findings_path.write_text(json.dumps(finding) + "\n", encoding="utf-8")
                self.assertEqual(post("/api/research/submit", {"path": str(findings_path)})["submitted"], 1)
                self.assertEqual(len(get("/api/research?mod=example")["findings"]), 1)
                post("/api/research/review", {"finding_id": finding["finding_id"], "decision": "accept"})
                self.assertEqual(get("/api/research?mod=example")["findings"], [])
                adapter_request = {**finding, "finding_id": "example:adapter_request",
                                   "record_type": "adapter_request", "description": "Capture effective ore behavior"}
                findings_path.write_text(json.dumps(adapter_request) + "\n", encoding="utf-8")
                post("/api/research/submit", {"path": str(findings_path)})
                self.assertEqual(get("/api/research?mod=example")["jobs"][0]["status"], "submitted")
                post("/api/research/review", {"finding_id": adapter_request["finding_id"],
                                              "decision": "accept"})
                self.assertEqual(get("/api/research?mod=example")["adapter_tasks"][0]["status"], "open")
                post("/api/research/resolve-task", {"finding_id": adapter_request["finding_id"],
                                                     "resolution": "capture/example.zip: verified"})
                self.assertEqual(get("/api/research?mod=example")["adapter_tasks"][0]["status"], "resolved")
                self.assertEqual(get("/api/analysis")["counts"]["recipes"], 1)
                self.assertEqual(post("/api/compare", {"baseline": str(database)})["counts"]["changed"], 0)
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
