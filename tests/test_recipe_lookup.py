import json
import unittest
import zipfile
from io import BytesIO

from recipe_lookup import lookup


class RecipeLookupTests(unittest.TestCase):
    def test_make_and_use_with_tag_and_sequence(self):
        capture = BytesIO()
        with zipfile.ZipFile(capture, "w") as archive:
            archive.writestr("item-tags.jsonl", json.dumps({"member": "example:ore", "tag": "c:ores"}) + "\n")
            rows = [
                {
                    "id": "example:smelt", "type": "minecraft:smelting", "source_pack_id": "mod/example",
                    "item_inputs": [{"kind": "item_tag", "id": "c:ores"}],
                    "item_outputs": [{"kind": "item", "id": "example:ingot"}],
                    "sequence": [], "input_status": "collected", "output_status": "collected",
                },
                {
                    "id": "example:assembly", "type": "example:assembly", "source_pack_id": "mod/example",
                    "item_inputs": [], "item_outputs": [{"kind": "item", "id": "example:ore"}],
                    "sequence": [{"item_inputs": [{"kind": "item", "id": "example:ore"}]}],
                    "input_status": "collected", "output_status": "collected",
                },
            ]
            archive.writestr("recipe-details.jsonl", "".join(json.dumps(row) + "\n" for row in rows))
        capture.seek(0)
        with zipfile.ZipFile(capture) as archive:
            matches = lookup(archive, "example:ore")
        self.assertEqual([row["id"] for row in matches["makes"]], ["example:assembly"])
        self.assertEqual([row["id"] for row in matches["uses"]], ["example:smelt", "example:assembly"])


if __name__ == "__main__":
    unittest.main()
