import json
from contextlib import closing
from pathlib import Path
import sqlite3
from tempfile import TemporaryDirectory
import unittest

from catalog import Catalog
from game_data_db import import_capture
from knowledge_store import KnowledgeStore
from research_queue import prepare_jobs
from test_game_data_db import capture


class KnowledgeStoreTests(unittest.TestCase):
    def test_reimport_same_capture_reuses_snapshot_and_preserves_reviewed_claim(self):
        with TemporaryDirectory() as folder:
            root = Path(folder)
            source = root / "capture.zip"
            capture(source)
            first, second = root / "first.sqlite", root / "second.sqlite"
            import_capture(source, first)
            import_capture(source, second)
            store = KnowledgeStore(root / "knowledge.sqlite")
            snapshot_id = store.register_capture(first)
            with store.connect() as db:
                db.execute("INSERT INTO evidence VALUES (?, ?, ?, ?, ?, ?, ?)",
                           (snapshot_id, "runtime:test", "installed_runtime", "capture/mechanics/example", None, None, None))
                db.execute("INSERT INTO claims VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                           (snapshot_id, "claim:test", "item", "example:ore", "capacity", "100", "J", "{}",
                            "runtime_confirmed", "runtime:test"))
                db.commit()
            self.assertEqual(snapshot_id, store.register_capture(second))
            self.assertEqual(store.read_subject(snapshot_id, "item", "example:ore")["claims"][0]["value"], 100)

    def test_distinct_capture_never_inherits_claims(self):
        with TemporaryDirectory() as folder:
            root = Path(folder)
            source = root / "capture.zip"
            capture(source)
            first, second = root / "first.sqlite", root / "second.sqlite"
            import_capture(source, first)
            import_capture(source, second)
            with closing(sqlite3.connect(second)) as db, db:
                provenance = json.loads(db.execute("SELECT provenance_json FROM capture").fetchone()[0])
                provenance["generated_at_utc"] = "2027-01-01T00:00:00Z"
                db.execute("UPDATE capture SET provenance_json=?, generated_at_utc=? WHERE id=1",
                           (json.dumps(provenance), provenance["generated_at_utc"]))
            store = KnowledgeStore(root / "knowledge.sqlite")
            self.assertNotEqual(store.register_capture(first), store.register_capture(second))

    def test_revalidation_skips_intervening_unreviewed_captures(self):
        with TemporaryDirectory() as folder:
            root = Path(folder)
            source = root / "capture.zip"
            capture(source)
            databases = [root / f"capture-{index}.sqlite" for index in range(3)]
            for index, database in enumerate(databases):
                import_capture(source, database)
                with closing(sqlite3.connect(database)) as db, db:
                    provenance = json.loads(db.execute("SELECT provenance_json FROM capture").fetchone()[0])
                    provenance["generated_at_utc"] = f"2027-01-0{index + 1}T00:00:00Z"
                    db.execute("UPDATE capture SET provenance_json=?,generated_at_utc=? WHERE id=1",
                               (json.dumps(provenance), provenance["generated_at_utc"]))
            store = KnowledgeStore(root / "knowledge.sqlite")
            first = store.register_capture(databases[0])
            with store.connect() as db:
                db.execute("INSERT INTO coverage VALUES (?,?,?,?,?,?)",
                           (first, "system", "example:power", "behavior", "verified", "Reviewed"))
            store.register_capture(databases[1])
            latest = store.register_capture(databases[2])
            report = store.mod_coverage(latest, "example", databases[2])
            self.assertEqual(report["revalidation"][0]["prior_snapshot_id"], first)
            self.assertEqual(report["revalidation"][0]["status"], "pending")
            self.assertEqual(store.mod_coverage(first, "example", databases[0])["revalidation"], [])

    def test_revalidation_requires_reviewed_findings_and_records_evidence(self):
        with TemporaryDirectory() as folder:
            root = Path(folder)
            source = root / "capture.zip"
            capture(source, artifacts=True)
            first_db, second_db = root / "first.sqlite", root / "second.sqlite"
            import_capture(source, first_db)
            import_capture(source, second_db)
            with closing(sqlite3.connect(second_db)) as db, db:
                provenance = json.loads(db.execute("SELECT provenance_json FROM capture").fetchone()[0])
                provenance["generated_at_utc"] = "2027-02-01T00:00:00Z"
                db.execute("UPDATE capture SET provenance_json=?,generated_at_utc=? WHERE id=1",
                           (json.dumps(provenance), provenance["generated_at_utc"]))
            store = KnowledgeStore(root / "knowledge.sqlite")
            first = store.register_capture(first_db)
            with store.connect() as db:
                db.execute("INSERT INTO coverage VALUES (?,?,?,?,?,?)",
                           (first, "item", "example:ore", "registry_identity", "verified", "Reviewed"))
            second = store.register_capture(second_db)
            _, jobs = prepare_jobs(second_db, store, "example")
            with self.assertRaises(ValueError):
                store.review_revalidation(second, "example", " ")
            with self.assertRaises(ValueError):
                store.review_revalidation(second, "example", "Compared captures")
            finding = {"format": "ch4os-research-finding-v1", "snapshot_id": second,
                       "job_id": jobs[0]["job_id"], "finding_id": "example:rechecked",
                       "record_type": "coverage", "subject_kind": "item",
                       "subject_id": "example:ore", "area": "registry_identity",
                       "status": "verified", "explanation": "Checked new capture"}
            store.submit_finding(finding)
            with self.assertRaises(ValueError):
                store.review_revalidation(second, "example", "Compared captures")
            store.review_finding(second, finding["finding_id"], "accept", second_db)
            store.review_revalidation(second, "example", "Unchanged artifact and registry verified")
            reviewed = store.mod_coverage(second, "example", second_db)["revalidation"][0]
            self.assertEqual(reviewed["status"], "reviewed")
            self.assertEqual(reviewed["review_note"], "Unchanged artifact and registry verified")
            self.assertIsNotNone(reviewed["reviewed_at_utc"])

    def test_generic_item_relationships_include_incoming_edges(self):
        with TemporaryDirectory() as folder:
            root = Path(folder)
            source, database = root / "capture.zip", root / "capture.sqlite"
            capture(source, adapter_rows=True)
            import_capture(source, database)
            with closing(sqlite3.connect(database)) as db, db:
                db.execute("INSERT INTO adapter_relations (adapter_id,subject_kind,subject_id,predicate,object_kind,object_id,status,source_record_json) VALUES (?,?,?,?,?,?,?,?)",
                           ("test", "item", "example:tool", "charges", "item", "example:ore", "captured_directly", "{}"))
            relation = next(link for link in Catalog(database).item("example:ore")["relations"] if link["predicate"] == "charges")
            self.assertEqual(relation["direction"], "incoming")
            self.assertEqual(relation["subject_id"], "example:tool")

    def test_mod_coverage_reports_unresolved_systems_separately_from_item_identity(self):
        with TemporaryDirectory() as folder:
            root = Path(folder)
            source, database = root / "capture.zip", root / "capture.sqlite"
            capture(source)
            import_capture(source, database)
            store = KnowledgeStore(root / "knowledge.sqlite")
            snapshot = store.register_capture(database)
            with store.connect() as db:
                db.execute("INSERT INTO coverage VALUES (?,?,?,?,?,?)",
                           (snapshot, "item", "example:ore", "registry_identity", "verified", "Loaded registry"))
                db.execute("INSERT INTO coverage VALUES (?,?,?,?,?,?)",
                           (snapshot, "system", "example:power", "full_gameplay_analysis", "unresolved", "Needs review"))
            report = store.mod_coverage(snapshot, "example", database)
            self.assertEqual(report["items_with_coverage"], 1)
            self.assertEqual(report["system_areas"][0]["status"], "unresolved")

    def test_reviewed_coverage_can_close_a_gap_with_history(self):
        with TemporaryDirectory() as folder:
            root = Path(folder)
            source, database = root / "capture.zip", root / "capture.sqlite"
            capture(source, artifacts=True)
            import_capture(source, database)
            store = KnowledgeStore(root / "knowledge.sqlite")
            _, jobs = prepare_jobs(database, store, "example")
            job = jobs[0]
            for finding_id, status in (("example:gap", "unresolved"), ("example:resolved", "verified")):
                finding = {"format": "ch4os-research-finding-v1", "snapshot_id": job["snapshot_id"],
                           "job_id": job["job_id"], "finding_id": finding_id,
                           "record_type": "coverage", "subject_kind": "system",
                           "subject_id": "example:power", "area": "operation", "status": status,
                           "explanation": f"Reviewed {status}"}
                store.submit_finding(finding)
                store.review_finding(job["snapshot_id"], finding_id, "accept", database)
            subject = store.read_subject(job["snapshot_id"], "system", "example:power")
            self.assertEqual(subject["coverage"][0]["status"], "verified")
            self.assertEqual([row["previous_status"] for row in subject["coverage_history"]],
                             [None, "unresolved"])

    def test_reviewed_adapter_request_becomes_traceable_task(self):
        with TemporaryDirectory() as folder:
            root = Path(folder)
            source, database = root / "capture.zip", root / "capture.sqlite"
            capture(source, artifacts=True)
            import_capture(source, database)
            store = KnowledgeStore(root / "knowledge.sqlite")
            _, jobs = prepare_jobs(database, store, "example")
            job = jobs[0]
            finding = {"format": "ch4os-research-finding-v1", "snapshot_id": job["snapshot_id"],
                       "job_id": job["job_id"], "finding_id": "example:adapter_request",
                       "record_type": "adapter_request", "subject_kind": "item",
                       "subject_id": "example:ore", "description": "Capture effective ore behavior"}
            store.submit_finding(finding)
            store.review_finding(job["snapshot_id"], finding["finding_id"], "accept", database)
            tasks = store.list_adapter_tasks(job["snapshot_id"], "example")
            self.assertEqual(len(tasks), 1)
            self.assertEqual(tasks[0]["status"], "open")
            with self.assertRaises(ValueError):
                store.resolve_adapter_task(job["snapshot_id"], finding["finding_id"], " ")
            store.resolve_adapter_task(job["snapshot_id"], finding["finding_id"],
                                       "capture/example-fresh.zip: verified effective behavior")
            self.assertEqual(store.list_adapter_tasks(job["snapshot_id"], "example")[0]["status"], "resolved")


if __name__ == "__main__":
    unittest.main()
