from contextlib import closing
from pathlib import Path
import sqlite3
from tempfile import TemporaryDirectory
import unittest

from game_data_db import import_capture
from knowledge_store import KnowledgeStore
from research_queue import prepare_jobs
from research.validate_gde_guide import validate
from test_game_data_db import capture


class GuideReferenceTests(unittest.TestCase):
    def fixture(self, root):
        source, database = root / "capture.zip", root / "capture.sqlite"
        capture(source, artifacts=True)
        import_capture(source, database)
        store = KnowledgeStore(root / "knowledge.sqlite")
        _, jobs = prepare_jobs(database, store, "example")
        job = jobs[0]
        finding = {"format": "ch4os-research-finding-v1", "snapshot_id": job["snapshot_id"],
                   "job_id": job["job_id"], "finding_id": "example:battery_capacity",
                   "record_type": "claim", "subject_kind": "item", "subject_id": "example:ore",
                   "predicate": "capacity", "value": 12, "unit": "Wh", "conditions": {},
                   "evidence": {"kind": "exact_source", "locator": "Battery.java#capacity",
                                "artifact_sha256": "a" * 64, "source_revision": "b" * 40,
                                "match_basis": "exact_installed_version"}}
        store.submit_finding(finding)
        guide = root / "guide.md"
        guide.write_text(f"<!-- gde-snapshot: {job['snapshot_id']} -->\n12 Wh.\n"
                         "<!-- gde-ref: example:battery_capacity -->\n")
        return database, store, finding, guide

    def test_generic_reference_rejects_pending_and_records_accepted(self):
        with TemporaryDirectory() as folder:
            database, store, finding, guide = self.fixture(Path(folder))
            with self.assertRaisesRegex(ValueError, "not accepted"):
                validate(database, store.path, guide)
            store.review_finding(finding["snapshot_id"], finding["finding_id"], "accept", database)
            result = validate(database, store.path, guide, record_refs=True)
            self.assertEqual(result["references"], 1)
            with store.connect() as db:
                self.assertEqual(db.execute("SELECT record_id FROM guide_refs").fetchone()[0], finding["finding_id"])

    def test_wrong_artifact_is_rejected_even_with_source_revision(self):
        with TemporaryDirectory() as folder:
            database, store, finding, guide = self.fixture(Path(folder))
            store.review_finding(finding["snapshot_id"], finding["finding_id"], "accept", database)
            with store.connect() as db:
                db.execute("UPDATE evidence SET artifact_sha256=?", ("c" * 64,))
            with self.assertRaisesRegex(ValueError, "not tied to this pack"):
                validate(database, store.path, guide)

    def test_missing_reference_and_snapshot_separation(self):
        with TemporaryDirectory() as folder:
            database, store, finding, guide = self.fixture(Path(folder))
            store.review_finding(finding["snapshot_id"], finding["finding_id"], "accept", database)
            guide.write_text("<!-- gde-ref: example:battery_capacity -->")
            with self.assertRaisesRegex(ValueError, "require a gde-snapshot"):
                validate(database, store.path, guide)
            guide.write_text(f"<!-- gde-snapshot: {finding['snapshot_id']} -->\n<!-- gde-ref: example:missing -->")
            with self.assertRaisesRegex(ValueError, "not accepted"):
                validate(database, store.path, guide)
            with closing(sqlite3.connect(database)) as db, db:
                db.execute("UPDATE mods SET version='3.0'")
            with self.assertRaisesRegex(ValueError, "snapshot differs"):
                validate(database, store.path, guide)


if __name__ == "__main__":
    unittest.main()
