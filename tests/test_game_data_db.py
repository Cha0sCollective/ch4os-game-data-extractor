import hashlib
from contextlib import closing
import json
from pathlib import Path
import sqlite3
from tempfile import TemporaryDirectory
import unittest
import zipfile

from game_data_db import import_capture, item_report


def jsonl(records):
    return "".join(json.dumps(row) + "\n" for row in records).encode()


def capture(path, *, details=True, corrupt=False, overrides=False, adapter_rows=False):
    files = {
        "provenance.json": json.dumps({"format": "create-handbook-runtime-export-v1",
                                       "scope": "pack", "counts": {"items": 2, "recipes": 1}}).encode(),
        "mods.jsonl": jsonl([{"id": "example", "name": "Example", "version": "2.0"}]),
        "items.jsonl": jsonl([
            {"id": "example:ore", "display_name": "Ore", "default_component_ids": ["minecraft:max_stack_size"]},
            {"id": "example:ingot", "display_name": "Ingot", "block_id": "example:ingot_block",
             "default_component_ids": ["minecraft:max_stack_size"]},
        ]),
        "blocks.jsonl": jsonl([{"id": "example:ingot_block", "item_id": "example:ingot",
                                "has_block_entity": True, "state_properties": {"facing": ["north", "south"]}}]),
        "recipes.jsonl": jsonl([{"id": "example:smelt", "type": "minecraft:smelting",
                                 "serializer": "minecraft:smelting", "result_item_id": "example:ingot",
                                 "result_count": 1}]),
        "item-tags.jsonl": jsonl([{"tag": "c:ores", "member": "example:ore"}]),
        "block-tags.jsonl": jsonl([{"tag": "c:storage_blocks", "member": "example:ingot_block"}]),
        "mechanics.jsonl": jsonl([
            {"entry_id": "example:ingot_block", "subsystem": "kinetics", "fact_key": "stress_impact",
             "value_number": 0, "registered_value": False, "source_api": "example.api"},
            {"entry_id": "example:ingot_block", "subsystem": "kinetics", "fact_key": "generated_rpm",
             "value_number": 32, "registered_value": True, "source_api": "example.api"},
            {"format": "ch4os-mechanic-v2", "adapter_id": "deep_seas", "entity_kind": "block",
             "entry_id": "example:ingot_block", "property_key": "hull.max_water_depth",
             "status": "captured_directly", "value": 180, "unit": "blocks",
             "conditions": {"usage": "submarine hull block"}, "source_api": "HullStrengthConfig.getFor"},
            {"format": "ch4os-mechanic-v2", "adapter_id": "powergrid", "entity_kind": "item",
             "entry_id": "example:ore", "property_key": "electrical.meter.maximum_voltage",
             "status": "captured_directly", "value": 500.0, "unit": "V",
             "conditions": {"meaning": "measurement range"}, "source_api": "Equipment.get"},
        ]),
    }
    if details:
        files["item-details.jsonl"] = jsonl([
            {"id": "example:ore", "component_status": "collected",
             "block_entity_type_status": "not_applicable", "block_entity_type_ids": [],
             "default_components": [{"id": "minecraft:max_stack_size", "status": "captured", "value": 64}]},
            {"id": "example:ingot", "component_status": "partial",
             "block_entity_type_status": "collected", "block_entity_type_ids": ["example:storage"],
             "default_components": [{"id": "minecraft:max_stack_size", "status": "failed", "error": "CodecError"}]},
        ])
        files["recipe-details.jsonl"] = jsonl([{
            "id": "example:smelt", "source_pack_id": "mod/example", "input_status": "collected",
            "output_status": "collected", "semantic_status": "core_fields",
            "item_inputs": [{"kind": "item_tag", "id": "c:ores", "path": "ingredient"}],
            "item_outputs": [{"kind": "item", "id": "example:ingot", "quantity": 1, "path": "result"}],
            "sequence": [{"index": 0, "item_outputs": [
                {"kind": "item", "id": "example:ore", "path": "results[0]"}]}],
        }])
    if overrides:
        files["recipe-overrides.jsonl"] = jsonl([{
            "id": "example:smelt", "resource_id": "example:recipe/smelt.json",
            "effective_loaded": True,
            "layers": [{"pack_id": "mod/example"}, {"pack_id": "file/override"}],
        }])
    if adapter_rows:
        provenance = json.loads(files["provenance.json"])
        provenance["counts"].update({"adapter_definitions": 2, "adapter_relations": 1})
        files["provenance.json"] = json.dumps(provenance).encode()
        files["adapter-definitions.jsonl"] = jsonl([
            {"format": "ch4os-adapter-definition-v1", "adapter_id": "example",
             "kind": "fuel", "id": "example:ingot_fuel", "status": "captured_directly",
             "attributes": {"burn_ticks": 800}, "conditions": {"engine": "example:burner"},
             "source_resource_id": "example:fuel/ingot.json", "source_pack_id": "mod/example",
             "source_sha256": "abc"},
            {"format": "ch4os-adapter-definition-v1", "adapter_id": "example",
             "kind": "fuel", "id": "example:unknown_fuel", "status": "unavailable",
             "attributes": None, "source_api": "example.api"},
        ])
        files["adapter-relations.jsonl"] = jsonl([
            {"format": "ch4os-adapter-relation-v1", "adapter_id": "example",
             "subject_kind": "item", "subject_id": "example:ingot", "predicate": "fuel_for",
             "object_kind": "block", "object_id": "example:ingot_block",
             "status": "captured_directly", "attributes": {"burn_ticks": 800},
             "conditions": {"state": "lit"}, "source_api": "example.api"},
        ])
    manifest = {"format": "create-handbook-runtime-export-v1", "files": [
        {"name": name, "bytes": len(body), "sha256": hashlib.sha256(body).hexdigest()}
        for name, body in files.items()
    ]}
    with zipfile.ZipFile(path, "w") as archive:
        for name, body in files.items():
            archive.writestr(name, body + b"broken" if corrupt and name == "items.jsonl" else body)
        archive.writestr("manifest.json", json.dumps(manifest))


class GameDataDbTests(unittest.TestCase):
    def test_item_relations_and_missing_value_status(self):
        with TemporaryDirectory() as folder:
            source, database = Path(folder) / "capture.zip", Path(folder) / "items.sqlite"
            capture(source)
            self.assertEqual(import_capture(source, database)["items"], 2)
            with closing(sqlite3.connect(database)) as db:
                ore = item_report(db, "example:ore")
                ingot = item_report(db, "example:ingot")
                self.assertEqual(ore["uses"], ["example:smelt"])
                self.assertEqual(ore["makes"], [])
                self.assertEqual(ingot["makes"], ["example:smelt"])
                self.assertEqual(ingot["mod_version"], "2.0")
                self.assertEqual(ingot["block_entity_types"], ["example:storage"])
                self.assertEqual(ingot["block_tags"], ["c:storage_blocks"])
                self.assertEqual(ore["components"][0]["value_json"], "64")
                self.assertIsNone(ingot["components"][0]["value_json"])
                properties = {row["property_key"]: row for row in ingot["properties"]}
                self.assertEqual(properties["kinetics.stress_impact"]["status"], "unavailable")
                self.assertIsNone(properties["kinetics.stress_impact"]["value_json"])
                self.assertEqual(properties["kinetics.generated_rpm"]["value_json"], "32")
                self.assertEqual(properties["hull.max_water_depth"]["value_json"], "180")
                self.assertEqual(json.loads(properties["hull.max_water_depth"]["conditions_json"]),
                                 {"usage": "submarine hull block"})
                ore_properties = {row["property_key"]: row for row in ore["properties"]}
                self.assertEqual(ore_properties["electrical.meter.maximum_voltage"]["value_json"], "500.0")
                self.assertEqual(ore_properties["electrical.meter.maximum_voltage"]["source"], "Equipment.get")

    def test_legacy_capture_keeps_unknown_detail_explicit(self):
        with TemporaryDirectory() as folder:
            source, database = Path(folder) / "capture.zip", Path(folder) / "items.sqlite"
            capture(source, details=False)
            import_capture(source, database)
            with closing(sqlite3.connect(database)) as db:
                ore = item_report(db, "example:ore")
                ingot = item_report(db, "example:ingot")
                self.assertEqual(ore["detail_status"], "unavailable_legacy_capture")
                self.assertEqual(ore["components"][0]["status"], "unavailable_legacy_capture")
                self.assertEqual(ingot["makes"], ["example:smelt"])
                self.assertEqual(ore["uses"], [])

    def test_corrupt_evidence_does_not_create_database(self):
        with TemporaryDirectory() as folder:
            source, database = Path(folder) / "capture.zip", Path(folder) / "items.sqlite"
            capture(source, corrupt=True)
            with self.assertRaisesRegex(ValueError, "mismatch"):
                import_capture(source, database)
            self.assertFalse(database.exists())

    def test_structured_adapter_rows_and_legacy_compatibility(self):
        with TemporaryDirectory() as folder:
            source, database = Path(folder) / "capture.zip", Path(folder) / "items.sqlite"
            capture(source, adapter_rows=True)
            summary = import_capture(source, database)
            self.assertEqual(summary["adapter_definitions"], 2)
            self.assertEqual(summary["adapter_relations"], 1)
            with closing(sqlite3.connect(database)) as db:
                attributes, pack = db.execute(
                    "SELECT attributes_json, source_pack_id FROM adapter_definitions WHERE id=?",
                    ("example:ingot_fuel",)).fetchone()
                self.assertEqual(json.loads(attributes), {"burn_ticks": 800})
                self.assertEqual(pack, "mod/example")
                self.assertIsNone(db.execute(
                    "SELECT attributes_json FROM adapter_definitions WHERE id=?",
                    ("example:unknown_fuel",)).fetchone()[0])
                self.assertEqual(db.execute(
                    "SELECT predicate FROM adapter_relations WHERE subject_id=?",
                    ("example:ingot",)).fetchone()[0], "fuel_for")


if __name__ == "__main__":
    unittest.main()
