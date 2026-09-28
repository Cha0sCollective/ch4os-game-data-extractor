from contextlib import closing
from http.server import ThreadingHTTPServer
import json
from pathlib import Path
import sqlite3
from tempfile import TemporaryDirectory
import threading
import unittest
from urllib.error import HTTPError
from urllib.request import urlopen

from game_data_db import import_capture
from local_app import AppState, handler_for
from research_queue import prepare_jobs
from test_game_data_db import capture


class ReviewedSubjectTests(unittest.TestCase):
    def test_item_model_navigation_keeps_evidence_direction_and_current_snapshot(self):
        with TemporaryDirectory() as folder:
            root = Path(folder)
            capture(root / "capture.zip")
            first, later = root / "first.sqlite", root / "later.sqlite"
            import_capture(root / "capture.zip", first)
            import_capture(root / "capture.zip", later)
            with closing(sqlite3.connect(later)) as db, db:
                db.execute("UPDATE mods SET version='new' WHERE id='example'")
            state = AppState(root / "app", first)
            for database, value in [(first, 40), (later, 900)]:
                _, jobs = prepare_jobs(database, state.knowledge, "example")
                job = jobs[0]
                snapshot = job["snapshot_id"]
                base = {"format": "ch4os-research-finding-v1", "snapshot_id": snapshot,
                        "job_id": job["job_id"], "subject_kind": "system", "subject_id": "example:engines",
                        "evidence": {"kind": "installed_runtime", "locator": "capture/example/model"}}
                records = [
                    {**base, "finding_id": "example:capacity", "record_type": "claim",
                     "predicate": "capacity", "value": value, "unit": "J", "conditions": {"mode": "ordinary"}},
                    {**base, "finding_id": "example:membership", "record_type": "relation",
                     "subject_kind": "item", "subject_id": "example:ore", "predicate": "uses_behavior_model",
                     "object_kind": "system", "object_id": "example:engines", "conditions": {}},
                ]
                for record in records:
                    state.knowledge.submit_finding(record)
                    state.knowledge.review_finding(snapshot, record["finding_id"], "accept", database, "Reviewed")
            server = ThreadingHTTPServer(("127.0.0.1", 0), handler_for(state))
            thread = threading.Thread(target=server.serve_forever, daemon=True)
            thread.start()
            base_url = f"http://127.0.0.1:{server.server_port}"

            def get(path):
                with urlopen(base_url + path) as response:
                    return json.load(response)

            try:
                item = get("/api/items/example%3Aore")
                self.assertEqual(item["reviewed"]["claims"], [])
                self.assertEqual(item["reviewed"]["relations"][0]["direction"], "outgoing")
                model = get("/api/knowledge/subject?kind=system&id=example%3Aengines")
                fact = model["reviewed"]["claims"][0]
                self.assertEqual(fact["value"], 40)
                self.assertEqual(fact["conditions"], {"mode": "ordinary"})
                self.assertEqual(fact["evidence_status"], "runtime_confirmed")
                self.assertEqual(model["reviewed"]["relations"][0]["direction"], "incoming")
                for path in ["/api/knowledge/subject?kind=system&id=example%3Amissing",
                             "/api/knowledge/subject?kind=unsupported&id=example%3Aengines"]:
                    with self.assertRaises(HTTPError) as error:
                        get(path)
                    self.assertEqual(error.exception.code, 400)
            finally:
                server.shutdown()
                server.server_close()
                thread.join(timeout=5)


if __name__ == "__main__":
    unittest.main()
