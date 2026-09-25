from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from game_data_db import import_capture
from knowledge_store import KnowledgeStore
from research_queue import _subsystem, prepare_jobs, write_packets
from test_game_data_db import capture


class ResearchQueueTests(unittest.TestCase):
    def test_device_families_get_separate_jobs(self):
        self.assertEqual(_subsystem("org/patryk3211/powergrid/electricity/battery/BatterySpec.class", "powergrid"),
                         "electricity-battery")
        self.assertEqual(_subsystem("org/patryk3211/powergrid/compat/cc/BatteryPeripheral.class", "powergrid"),
                         "compat-cc")
        self.assertEqual(_subsystem("org/example/electricity/Battery.class", "example"), "electricity")

    def test_packets_are_bounded_and_reproducible(self):
        with TemporaryDirectory() as folder:
            root = Path(folder)
            source, database = root / "capture.zip", root / "capture.sqlite"
            capture(source, artifacts=True)
            import_capture(source, database)
            store = KnowledgeStore(root / "knowledge.sqlite")
            context, jobs = prepare_jobs(database, store, "example", "https://github.com/example/example")
            self.assertEqual(len(jobs), 1)
            self.assertEqual(jobs[0]["subsystem"], "electricity")
            self.assertEqual(jobs[0]["class_paths"], ["org/example/electricity/Battery.class"])
            self.assertEqual(jobs[0]["installed_artifacts"][0]["sha256"], "a" * 64)
            self.assertEqual(context["items"][0]["id"], "example:ingot")
            self.assertEqual(jobs[0]["job_id"], prepare_jobs(database, store, "example", "https://github.com/example/example")[1][0]["job_id"])
            changed_source = prepare_jobs(database, store, "example", "https://github.com/example/other")[1][0]
            self.assertNotEqual(jobs[0]["job_id"], changed_source["job_id"])
            result = write_packets(database, store, "example", root / "jobs", "https://github.com/example/example")
            self.assertEqual(result["job_count"], 1)
            self.assertTrue((root / "jobs" / "manifest.json").is_file())

    def test_source_finding_requires_installed_artifact_and_explicit_review(self):
        with TemporaryDirectory() as folder:
            root = Path(folder)
            source, database = root / "capture.zip", root / "capture.sqlite"
            capture(source, artifacts=True)
            import_capture(source, database)
            store = KnowledgeStore(root / "knowledge.sqlite")
            _, jobs = prepare_jobs(database, store, "example")
            job = jobs[0]
            finding = {"format": "ch4os-research-finding-v1", "snapshot_id": job["snapshot_id"],
                       "job_id": job["job_id"], "finding_id": "example:battery_capacity",
                       "record_type": "claim", "subject_kind": "item", "subject_id": "example:ore",
                       "predicate": "electrical.capacity", "value": 120, "unit": "Wh",
                       "conditions": {"state": "fully charged"},
                       "evidence": {"kind": "exact_source", "locator": "BatterySpec.java#L40",
                                    "artifact_sha256": "b" * 64, "source_revision": "abc123",
                                    "match_basis": "exact_installed_version"}}
            store.submit_finding(finding)
            self.assertEqual(store.read_subject(job["snapshot_id"], "item", "example:ore")["claims"], [])
            with self.assertRaisesRegex(ValueError, "not installed"):
                store.review_finding(job["snapshot_id"], finding["finding_id"], "accept", database)
            finding["evidence"]["artifact_sha256"] = "a" * 64
            finding["evidence"]["match_basis"] = "version_only"
            finding["finding_id"] = "example:battery_capacity_version_only"
            store.submit_finding(finding)
            with self.assertRaisesRegex(ValueError, "exact installed-version match"):
                store.review_finding(job["snapshot_id"], finding["finding_id"], "accept", database)
            finding["evidence"]["match_basis"] = "exact_installed_version"
            finding["finding_id"] = "example:battery_capacity_valid"
            store.submit_finding(finding)
            store.review_finding(job["snapshot_id"], finding["finding_id"], "accept", database)
            claim = store.read_subject(job["snapshot_id"], "item", "example:ore")["claims"][0]
            self.assertEqual(claim["evidence_status"], "source_derived")
            self.assertEqual(claim["conditions"], {"state": "fully charged"})

    def test_rejected_recipe_and_unknown_value_cannot_be_promoted(self):
        with TemporaryDirectory() as folder:
            root = Path(folder)
            source, database = root / "capture.zip", root / "capture.sqlite"
            capture(source, artifacts=True)
            import_capture(source, database)
            store = KnowledgeStore(root / "knowledge.sqlite")
            _, jobs = prepare_jobs(database, store, "example")
            base = {"format": "ch4os-research-finding-v1", "snapshot_id": jobs[0]["snapshot_id"],
                    "job_id": jobs[0]["job_id"], "subject_kind": "item", "subject_id": "example:ore",
                    "evidence": {"kind": "installed_runtime", "locator": "capture/recipes/example:smelt"}}
            missing_recipe = {**base, "finding_id": "example:missing_recipe", "record_type": "relation",
                              "predicate": "made_by", "object_kind": "recipe", "object_id": "example:rejected"}
            store.submit_finding(missing_recipe)
            with self.assertRaisesRegex(ValueError, "absent from this capture"):
                store.review_finding(jobs[0]["snapshot_id"], missing_recipe["finding_id"], "accept", database)
            unknown = {**base, "finding_id": "example:unknown_value", "record_type": "claim",
                       "predicate": "voltage", "value": None}
            store.submit_finding(unknown)
            with self.assertRaisesRegex(ValueError, "non-null value"):
                store.review_finding(jobs[0]["snapshot_id"], unknown["finding_id"], "accept", database)


if __name__ == "__main__":
    unittest.main()
