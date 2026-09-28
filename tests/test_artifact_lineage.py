from contextlib import closing
import hashlib
from io import BytesIO
import json
from pathlib import Path
import sqlite3
from tempfile import TemporaryDirectory
import unittest
from zipfile import ZipFile

from artifact_lineage import inspect_nested, inspect_platform, inspect_loader
from game_data_db import import_capture
from knowledge_store import KnowledgeStore, artifact_hashes
from research.validate_gde_guide import validate
from test_game_data_db import capture


def jar(entries):
    data = BytesIO()
    with ZipFile(data, "w") as archive:
        for name, value in entries.items():
            archive.writestr(name, value)
    return data.getvalue()


class ArtifactLineageTests(unittest.TestCase):
    def fixture(self, root, child_version="2.0"):
        child = jar({"META-INF/neoforge.mods.toml":
                     f'[[mods]]\nmodId="child"\nversion="{child_version}"\n'})
        outer = jar({"META-INF/jarjar/metadata.json": json.dumps({"jars": [{"path": "META-INF/jarjar/child.jar"}]}),
                     "META-INF/jarjar/child.jar": child})
        artifact = root / "outer.jar"
        artifact.write_bytes(outer)
        source, database = root / "capture.zip", root / "capture.sqlite"
        capture(source, artifacts=True)
        import_capture(source, database)
        with closing(sqlite3.connect(database)) as db, db:
            db.execute("INSERT INTO mods(id,name,version) VALUES ('child','Child','2.0')")
            db.execute("INSERT INTO mods(id,name,version) VALUES ('minecraft','Minecraft','1.21.1')")
            provenance = json.loads(db.execute("SELECT provenance_json FROM capture").fetchone()[0])
            provenance["minecraft_version"] = "1.21.1"
            db.execute("UPDATE capture SET provenance_json=?", (json.dumps(provenance),))
            db.execute("UPDATE installed_artifacts SET sha256=?", (hashlib.sha256(outer).hexdigest(),))
        store = KnowledgeStore(root / "knowledge.sqlite")
        snapshot = store.register_capture(database)
        job = {"snapshot_id": snapshot, "job_id": "job", "mod_id": "example", "subsystem": "cross-mod"}
        store.add_job(job)
        return database, store, snapshot, artifact

    def test_nested_owner_acceptance_and_guide_snapshot_separation(self):
        with TemporaryDirectory() as folder:
            root = Path(folder)
            database, store, snapshot, artifact = self.fixture(root)
            links = inspect_nested(database, artifact)
            self.assertEqual(links[0]["mod_id"], "child")
            store.review_artifact_links(database, links, "Read nested descriptor and captured outer hash")
            finding = {"format": "ch4os-research-finding-v1", "snapshot_id": snapshot, "job_id": "job",
                       "finding_id": "example:cross_mod", "record_type": "claim", "subject_kind": "item",
                       "subject_id": "example:ore", "predicate": "behavior", "value": "child implementation",
                       "evidence": {"kind": "exact_source", "mod_id": "child", "locator": "Child.java#behavior",
                                    "artifact_sha256": links[0]["artifact_sha256"], "source_revision": "a" * 40,
                                    "match_basis": "exact_installed_version"}}
            store.submit_finding(finding)
            store.review_finding(snapshot, finding["finding_id"], "accept", database)
            guide = root / "guide.md"
            guide.write_text(f"<!-- gde-snapshot: {snapshot} -->\n<!-- gde-ref: example:cross_mod -->")
            self.assertEqual(validate(database, store.path, guide)["references"], 1)
            finding = {**finding, "finding_id": "example:wrong_owner", "evidence": {**finding["evidence"], "mod_id": "example"}}
            store.submit_finding(finding)
            with self.assertRaisesRegex(ValueError, "not installed"):
                store.review_finding(snapshot, finding["finding_id"], "accept", database)
            with closing(sqlite3.connect(database)) as db, db:
                db.execute("UPDATE mods SET version='3.0' WHERE id='child'")
            newer = store.register_capture(database)
            with store.connect() as db:
                self.assertNotIn(links[0]["artifact_sha256"], artifact_hashes(db, newer, "child"))

    def test_nested_root_and_version_mismatch(self):
        with TemporaryDirectory() as folder:
            root = Path(folder)
            database, store, snapshot, artifact = self.fixture(root, "3.0")
            with self.assertRaisesRegex(ValueError, "version differs"):
                inspect_nested(database, artifact)
            artifact.write_bytes(jar({"META-INF/jarjar/metadata.json": '{"jars":[]}'}))
            with self.assertRaisesRegex(ValueError, "not in this capture"):
                inspect_nested(database, artifact)
            with self.assertRaisesRegex(ValueError, "root is not installed"):
                store.review_artifact_links(database, [{"kind": "nested", "mod_id": "child", "version": "2.0",
                    "artifact_sha256": "c" * 64, "root_sha256": "b" * 64, "parent_sha256": "b" * 64,
                    "entry_path": "other.jar!/child.jar"}], "review")

    def test_platform_version_is_reviewed_separately_and_immutable(self):
        with TemporaryDirectory() as folder:
            root = Path(folder)
            database, store, snapshot, _ = self.fixture(root)
            server = jar({"net/minecraft/server/Main.class": "fixture"})
            sha = hashlib.sha256(server).hexdigest()
            platform = root / "server.jar"
            def write(version):
                platform.write_bytes(jar({"version.json": json.dumps({"id": version}),
                    "META-INF/versions.list": f"{sha}\t{version}\t{version}/server.jar\n",
                    f"META-INF/versions/{version}/server.jar": server}))
            write("1.21.1")
            links = inspect_platform(database, platform)
            store.review_artifact_links(database, links, "Version and server member inspected offline")
            store.review_artifact_links(database, links, "Version and server member inspected offline")
            with store.connect() as db:
                self.assertEqual(db.execute("SELECT COUNT(*) FROM snapshot_artifacts WHERE mod_id='minecraft'").fetchone()[0], 0)
                self.assertIn(links[0]["artifact_sha256"], artifact_hashes(db, snapshot, "minecraft"))
            with self.assertRaisesRegex(ValueError, "immutable"):
                store.review_artifact_links(database, links, "changed review")
            write("1.21.2")
            with self.assertRaisesRegex(ValueError, "version differs"):
                inspect_platform(database, platform)

    def test_loader_source_evidence_requires_review_and_stays_snapshot_scoped(self):
        with TemporaryDirectory() as folder:
            root = Path(folder)
            database, _, _, _ = self.fixture(root)
            with closing(sqlite3.connect(database)) as db, db:
                db.execute("INSERT INTO mods(id,name,version) VALUES ('neoforge','NeoForge','21.1.248')")
                provenance = json.loads(db.execute("SELECT provenance_json FROM capture").fetchone()[0])
                provenance["neoforge_version"] = "21.1.248"
                db.execute("UPDATE capture SET provenance_json=?", (json.dumps(provenance),))
            store = KnowledgeStore(root / "loader-knowledge.sqlite")
            snapshot = store.register_capture(database)
            store.add_job({"snapshot_id": snapshot, "job_id": "loader", "mod_id": "example", "subsystem": "fluids"})
            library = root / "loader.jar"

            def write(version, system="neoforge", entrypoint=True):
                entries = {"META-INF/neoforge.mods.toml": f'[[mods]]\nmodId="neoforge"\nversion="{version}"\n',
                           "META-INF/MANIFEST.MF": f"Manifest-Version: 1.0\r\nFML-System-Mods: {system}\r\n\r\n"
                           f"Name: net/neoforged/neoforge/internal/versions/neoforge/\r\nImplementation-Version: {version}\r\n"}
                if entrypoint:
                    entries["net/neoforged/neoforge/internal/versions/neoforge/NeoForgeVersion.class"] = "fixture"
                library.write_bytes(jar(entries))

            write("21.1.248")
            links = inspect_loader(database, library)
            finding = {"format": "ch4os-research-finding-v1", "snapshot_id": snapshot, "job_id": "loader",
                       "finding_id": "example:loader_fluid", "record_type": "claim", "subject_kind": "item",
                       "subject_id": "example:ore", "predicate": "fluid_wrapper", "value": "source rule",
                       "evidence": {"kind": "installed_artifact", "mod_id": "neoforge", "locator": "FluidTank.class",
                                    "artifact_sha256": links[0]["artifact_sha256"]}}
            store.submit_finding(finding)
            with self.assertRaisesRegex(ValueError, "does not match"):
                store.review_finding(snapshot, finding["finding_id"], "accept", database)
            store.review_artifact_links(database, links, "Offline system-module association; hash not captured")
            store.review_finding(snapshot, finding["finding_id"], "accept", database)
            reviewed = store.read_subject(snapshot, "item", "example:ore")
            self.assertEqual(reviewed["claims"][0]["evidence_status"], "source_derived")
            with store.connect() as db:
                self.assertEqual(db.execute("SELECT COUNT(*) FROM snapshot_artifacts WHERE mod_id='neoforge'").fetchone()[0], 0)
            write("21.1.249")
            with self.assertRaisesRegex(ValueError, "version differs"):
                inspect_loader(database, library)
            write("21.1.248", system="unrelated")
            with self.assertRaisesRegex(ValueError, "system-module"):
                inspect_loader(database, library)
            write("21.1.248", entrypoint=False)
            with self.assertRaisesRegex(ValueError, "system-module"):
                inspect_loader(database, library)
            with closing(sqlite3.connect(database)) as db, db:
                db.execute("UPDATE mods SET version='21.1.249' WHERE id='neoforge'")
                provenance["neoforge_version"] = "21.1.249"
                db.execute("UPDATE capture SET provenance_json=?", (json.dumps(provenance),))
            newer = store.register_capture(database)
            with store.connect() as db:
                self.assertNotIn(links[0]["artifact_sha256"], artifact_hashes(db, newer, "neoforge"))


if __name__ == "__main__":
    unittest.main()
