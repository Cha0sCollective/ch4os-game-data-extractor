from contextlib import closing
import json
from pathlib import Path
import sqlite3
from tempfile import TemporaryDirectory
import unittest

from game_data_db import import_capture
from knowledge_store import KnowledgeStore
from research_queue import prepare_jobs
from test_game_data_db import capture


class GapResolutionTests(unittest.TestCase):
    def test_resolution_keeps_proposal_and_requires_snapshot_scoped_accepted_evidence(self):
        with TemporaryDirectory() as folder:
            root = Path(folder)
            capture(root / "capture.zip")
            database = root / "capture.sqlite"
            import_capture(root / "capture.zip", database)
            store = KnowledgeStore(root / "knowledge.sqlite")
            snapshot = store.register_capture(database)
            _, jobs = prepare_jobs(database, store, "example")
            job = jobs[0]
            base = {"format": "ch4os-research-finding-v1", "snapshot_id": snapshot, "job_id": job["job_id"],
                    "subject_kind": "item", "subject_id": "example:ore"}
            gap = {**base, "finding_id": "example:gap", "record_type": "gap", "description": "Capacity unknown"}
            fact = {**base, "finding_id": "example:capacity", "record_type": "claim", "predicate": "capacity",
                    "value": 12, "evidence": {"kind": "installed_runtime", "locator": "capture/capacity/example"}}
            for record in (gap, fact):
                store.submit_finding(record)
            store.review_finding(snapshot, gap["finding_id"], "accept", database, "Question retained")
            with self.assertRaisesRegex(ValueError, "accepted fact"):
                store.resolve_gap(snapshot, gap["finding_id"], [fact["finding_id"]], "Answered")
            store.review_finding(snapshot, fact["finding_id"], "accept", database, "Captured")
            store.resolve_gap(snapshot, gap["finding_id"], [fact["finding_id"]], "Answered")
            store.resolve_gap(snapshot, gap["finding_id"], [fact["finding_id"]], "Answered")
            row = next(r for r in store.list_findings(snapshot, status="all") if r["id"] == gap["finding_id"])
            self.assertEqual(row["finding"], gap)
            self.assertEqual(row["status"], "accepted")
            self.assertEqual(row["review_note"], "Question retained")
            self.assertEqual(row["resolution"]["record_ids"], [fact["finding_id"]])
            with self.assertRaisesRegex(ValueError, "immutable"):
                store.resolve_gap(snapshot, gap["finding_id"], [fact["finding_id"]], "Different answer")
            with closing(sqlite3.connect(database)) as db, db:
                db.execute("UPDATE mods SET version='different' WHERE id='example'")
            other_snapshot = store.register_capture(database)
            with self.assertRaisesRegex(ValueError, "accepted gap not found"):
                store.resolve_gap(other_snapshot, gap["finding_id"], [fact["finding_id"]], "Answered")


if __name__ == "__main__":
    unittest.main()
