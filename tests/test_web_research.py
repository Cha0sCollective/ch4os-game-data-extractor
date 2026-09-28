import hashlib
from contextlib import closing
import json
from pathlib import Path
import sqlite3
from tempfile import TemporaryDirectory
import unittest

from game_data_db import import_capture
from knowledge_store import KnowledgeStore
from research_queue import submit_file
from test_game_data_db import capture
from web_research import build_handoff, snapshot_inventory, write_handoff


def task():
    return {"format": "ch4os-web-research-task-v1", "mod_id": "example", "subsystem": "battery",
            "title": "Battery gameplay", "item_ids": ["example:ingot", "example:ore"],
            "questions": ["Explain capacity, conditions, and controls."], "definition_kinds": ["fuel"],
            "source": {"repository": "https://github.com/example/mod", "revision": "b" * 40,
                       "declared_version": "2.0", "match_status": "release_candidate",
                       "match_note": "Version declared at this upstream revision matches installed version.",
                       "routes": [{"path": "src/Battery.java", "purpose": "Battery behavior"}]}}


class WebResearchTests(unittest.TestCase):
    def setup_capture(self, root, **options):
        source, database = root / "capture.zip", root / "capture.sqlite"
        capture(source, **options)
        import_capture(source, database)
        return database, KnowledgeStore(root / "knowledge.sqlite")

    def test_handoff_roundtrip_is_deterministic_and_excludes_unloaded_recipes(self):
        with TemporaryDirectory() as folder:
            root = Path(folder)
            database, store = self.setup_capture(root, artifacts=True, adapter_rows=True)
            before = hashlib.sha256(database.read_bytes()).hexdigest()
            output = root / "handoff"
            result = write_handoff(database, store, task(), output)
            first = {p.name: p.read_bytes() for p in output.iterdir()}
            self.assertEqual(result, write_handoff(database, store, task(), output))
            self.assertEqual(first, {p.name: p.read_bytes() for p in output.iterdir()})
            context = json.loads(first["context.json"])
            self.assertEqual([r["id"] for r in context["recipes"]], ["example:smelt"])
            self.assertEqual(context["adapter_definitions"][0]["attributes"], {"burn_ticks": 800})
            unknown = next(p for item in context["items"] for p in item["properties"] if p["value"] is None)
            self.assertIsNone(unknown["value"])
            self.assertIn("release_candidate", first["prompt.md"].decode())
            self.assertIn("src/Battery.java", first["handoff.md"].decode())
            self.assertFalse(any(p.suffix in {".jar", ".sqlite", ".class", ".java"} for p in output.iterdir()))
            self.assertEqual(before, hashlib.sha256(database.read_bytes()).hexdigest())
            proposal = {"format": "ch4os-research-finding-v1", "snapshot_id": result["snapshot_id"],
                        "job_id": result["job_id"], "finding_id": "example:web_battery:capacity",
                        "record_type": "claim", "subject_kind": "item", "subject_id": "example:ore",
                        "predicate": "capacity", "value": 12, "unit": "Wh", "conditions": {},
                        "evidence": {"kind": "exact_source", "locator": "https://github.com/example/mod/blob/" + "b" * 40 + "/src/Battery.java#L2",
                                     "artifact_sha256": "a" * 64, "source_revision": "b" * 40,
                                     "match_basis": "release_candidate"}}
            response = root / "findings.json"
            response.write_text(json.dumps([proposal]))
            self.assertEqual(submit_file(store, response), 1)
            with self.assertRaisesRegex(ValueError, "exact installed-version match"):
                store.review_finding(result["snapshot_id"], proposal["finding_id"], "accept", database)
            self.assertEqual(store.read_subject(result["snapshot_id"], "item", "example:ore")["claims"], [])

    def test_snapshot_separation_and_reviewed_knowledge_export(self):
        with TemporaryDirectory() as folder:
            root = Path(folder)
            database, store = self.setup_capture(root, artifacts=True)
            _, packet = build_handoff(database, store, task())
            store.add_job(packet)
            finding = {"format": "ch4os-research-finding-v1", "snapshot_id": packet["snapshot_id"],
                       "job_id": packet["job_id"], "finding_id": "example:reviewed_capacity",
                       "record_type": "claim", "subject_kind": "item", "subject_id": "example:ore",
                       "predicate": "capacity", "value": 12, "unit": "Wh", "conditions": {"upgrade": False},
                       "evidence": {"kind": "installed_artifact", "locator": "Battery.class#capacity",
                                    "artifact_sha256": "a" * 64}}
            store.submit_finding(finding)
            store.review_finding(packet["snapshot_id"], finding["finding_id"], "accept", database)
            context, changed_packet = build_handoff(database, store, task())
            self.assertEqual(context["reviewed"]["claims"][0]["conditions"], {"upgrade": False})
            self.assertNotEqual(packet["job_id"], changed_packet["job_id"])
            with closing(sqlite3.connect(database)) as db, db:
                db.execute("UPDATE mods SET version='3.0' WHERE id='example'")
            next_task = task()
            next_task["source"]["declared_version"] = "3.0"
            next_context, next_packet = build_handoff(database, store, next_task)
            self.assertNotEqual(packet["snapshot_id"], next_packet["snapshot_id"])
            self.assertEqual(next_context["reviewed"]["claims"], [])

    def test_older_capture_and_invalid_source_or_entry(self):
        with TemporaryDirectory() as folder:
            database, store = self.setup_capture(Path(folder), details=False, artifacts=False)
            context, _ = build_handoff(database, store, task())
            self.assertEqual(context["installed_artifacts"], [])
            self.assertEqual(context["recipes"][0]["id"], "example:smelt")
            self.assertEqual(snapshot_inventory(database, store)["mods"][0]["item_count"], 2)
            bad = task()
            bad["source"]["declared_version"] = "3.0"
            with self.assertRaisesRegex(ValueError, "differs"):
                build_handoff(database, store, bad)
            bad = task()
            bad["item_ids"] = ["example:missing"]
            with self.assertRaisesRegex(ValueError, "item not found"):
                build_handoff(database, store, bad)


if __name__ == "__main__":
    unittest.main()
