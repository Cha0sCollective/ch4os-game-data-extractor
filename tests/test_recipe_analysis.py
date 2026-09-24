import json
from contextlib import closing
from pathlib import Path
import shutil
import sqlite3
from tempfile import TemporaryDirectory
import unittest

from game_data_db import import_capture
from recipe_analysis import analyze_database, compare_databases
from test_game_data_db import capture


def add_recipe(db, recipe_id, recipe_type, serializer, source, output, *, semantic="core_fields"):
    detail = {"id": recipe_id, "type": recipe_type, "serializer": serializer,
              "input_status": "collected", "output_status": "collected", "semantic_status": semantic,
              "source_json": source,
              "item_inputs": [{"kind": "item", "id": "example:ore", "path": "ingredient"}],
              "item_outputs": [{"kind": "item", "id": output, "quantity": 1, "path": "result"}]}
    db.execute("INSERT INTO recipes VALUES (?, ?, ?, ?, NULL, ?, 1, NULL, NULL, NULL, "
               "'collected', 'collected', 'collected', ?, ?)",
               (recipe_id, recipe_id.partition(":")[0], recipe_type, serializer, output,
                semantic, json.dumps(detail)))


class RecipeAnalysisTests(unittest.TestCase):
    def test_override_evidence_is_imported_when_present(self):
        with TemporaryDirectory() as folder:
            root = Path(folder)
            source, database = root / "source.zip", root / "data.sqlite"
            capture(source, overrides=True)
            import_capture(source, database)
            report = analyze_database(database)
            self.assertEqual(report["override_evidence"], "captured")
            self.assertEqual(report["overrides"][0]["layers"][1]["pack_id"], "file/override")

    def test_exact_cooking_collision_and_stonecutter_choice(self):
        with TemporaryDirectory() as folder:
            root = Path(folder)
            source, database = root / "source.zip", root / "data.sqlite"
            capture(source)
            import_capture(source, database)
            with closing(sqlite3.connect(database)) as db, db:
                ingredient = {"item": "example:ore"}
                add_recipe(db, "example:cook_a", "minecraft:smelting", "minecraft:smelting",
                           {"ingredient": ingredient, "result": {"id": "example:ingot"}}, "example:ingot")
                add_recipe(db, "example:cook_b", "minecraft:smelting", "minecraft:smelting",
                           {"ingredient": ingredient, "result": {"id": "example:ore"}}, "example:ore")
                add_recipe(db, "example:stone_a", "minecraft:stonecutting", "minecraft:stonecutting",
                           {"ingredient": ingredient, "result": {"id": "example:ingot"}}, "example:ingot")
                add_recipe(db, "example:stone_b", "minecraft:stonecutting", "minecraft:stonecutting",
                           {"ingredient": ingredient, "result": {"id": "example:ore"}}, "example:ore")
                add_recipe(db, "example:custom", "example:machine", "example:machine",
                           {"ingredient": ingredient}, "example:ore", semantic="partial_or_dynamic")
            report = analyze_database(database)
            self.assertEqual([(f["kind"], f["recipes"]) for f in report["findings"]],
                             [("competing_inputs", ["example:cook_a", "example:cook_b"])])
            self.assertGreater(report["counts"]["inconclusive"], 0)

    def test_mirrored_shaped_equivalence_and_missing_ingredient(self):
        with TemporaryDirectory() as folder:
            root = Path(folder)
            source, database = root / "source.zip", root / "data.sqlite"
            capture(source)
            import_capture(source, database)
            with closing(sqlite3.connect(database)) as db, db:
                left = {"pattern": ["AB"], "key": {"A": {"item": "example:ore"},
                                                       "B": {"item": "example:ingot"}}}
                right = {"pattern": ["BA"], "key": left["key"]}
                add_recipe(db, "example:left", "minecraft:crafting", "minecraft:crafting_shaped",
                           left, "example:ingot")
                add_recipe(db, "example:right", "minecraft:crafting", "minecraft:crafting_shaped",
                           right, "example:ingot")
                detail = json.loads(db.execute("SELECT detail_json FROM recipes WHERE id='example:left'").fetchone()[0])
                detail["item_inputs"].append({"kind": "item", "id": "example:absent", "path": "key.C"})
                detail["item_inputs"].append({"kind": "item_tag", "id": "c:absent", "path": "key.D"})
                db.execute("UPDATE recipes SET detail_json=? WHERE id='example:left'", (json.dumps(detail),))
            report = analyze_database(database)
            self.assertEqual(report["findings"][0]["kind"], "equivalent_recipes")
            self.assertEqual({issue["kind"] for issue in report["missing_ingredients"]},
                             {"missing_item", "empty_or_missing_item_tag"})

    def test_snapshot_changes_and_conflict_lifecycle(self):
        with TemporaryDirectory() as folder:
            root = Path(folder)
            source, baseline, current = root / "source.zip", root / "old.sqlite", root / "new.sqlite"
            capture(source)
            import_capture(source, baseline)
            with closing(sqlite3.connect(baseline)) as db, db:
                ingredient = {"item": "example:ore"}
                for suffix, output in (("a", "example:ore"), ("b", "example:ingot")):
                    add_recipe(db, f"example:{suffix}", "minecraft:smelting", "minecraft:smelting",
                               {"ingredient": ingredient, "result": {"id": output}}, output)
            shutil.copyfile(baseline, current)
            with closing(sqlite3.connect(current)) as db, db:
                db.execute("DELETE FROM recipes WHERE id='example:b'")
                detail = json.loads(db.execute("SELECT detail_json FROM recipes WHERE id='example:a'").fetchone()[0])
                detail["source_json"]["ingredient"] = {"tag": "c:new_ore"}
                detail["item_inputs"] = [{"kind": "item_tag", "id": "c:new_ore", "path": "ingredient"}]
                detail["item_outputs"][0]["quantity"] = 2
                db.execute("UPDATE recipes SET result_count=2, detail_json=? WHERE id='example:a'",
                           (json.dumps(detail),))
                add_recipe(db, "example:added", "minecraft:stonecutting", "minecraft:stonecutting",
                           {"ingredient": ingredient, "result": {"id": "example:ore"}}, "example:ore")
            report = compare_databases(baseline, current)
            self.assertEqual(report["counts"], {"added": 1, "removed": 1, "changed": 1,
                                                 "new_conflicts": 0, "resolved_conflicts": 1})
            self.assertIn("outputs", report["changed_recipes"][0]["fields"])
            self.assertIn("input_tags", report["changed_recipes"][0]["fields"])
            self.assertEqual(report["removed_recipes"], ["example:b"])


if __name__ == "__main__":
    unittest.main()
