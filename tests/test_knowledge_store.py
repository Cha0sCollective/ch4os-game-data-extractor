import json
from contextlib import closing
from pathlib import Path
import sqlite3
from tempfile import TemporaryDirectory
import unittest

from catalog import Catalog
from game_data_db import import_capture
from knowledge_store import KnowledgeStore
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


if __name__ == "__main__":
    unittest.main()
