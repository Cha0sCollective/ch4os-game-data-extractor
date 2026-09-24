# SQLite item and recipe database

`game_data_db.py` imports a capture ZIP without changing it. Python 3.11+ and
SQLite from the Python standard library are enough. The destination must be a
new file. The importer verifies the manifest's sizes and SHA-256 digests before
creating the database and removes an incomplete database if import fails.

```text
python game_data_db.py import capture.zip --output game-data.sqlite
python game_data_db.py item game-data.sqlite minecraft:iron_ingot
```

The database holds loaded mods, every captured item and block, item components,
block state properties, block-entity type IDs, item and block tags, registry
identities and tags, loaded recipes, normalized recipe inputs and outputs,
effective configuration values, and runtime mechanic facts. Recipe inputs
retain item-tag references; item lookups resolve them through captured tag
membership. The recipe detail JSON remains available for custom definitions
whose semantics cannot be normalized fully. Unloaded recipe resources are
stored separately and must not be treated as loaded recipes or parse errors.
Outputs of individual sequenced-assembly steps are marked as intermediate;
only final recipe outputs count as ways to make an item.

`item-details.jsonl` is an additive `ch4os-item-detail-v1` file with one row
per captured item. Its component values describe the *default registered item
stack*, not every possible stack obtained during play. A component reports
`captured`, `unsupported_non_persistent`, or `failed` individually. The file
also records block-entity type IDs valid for an associated block, with
`collected`, `not_applicable`, or `unavailable` status. Original `items.jsonl`
and the v1 manifest format remain unchanged. Existing capture ZIPs without
item or recipe detail files still import; their missing fields are marked
`unavailable_legacy_capture` or `unavailable` rather than assigned zero.

An item's namespace links to a loaded mod of the same ID when one exists.
Namespace alone cannot prove which mod supplied an item, so unmatched
namespaces retain a null `mod_id`. Global configuration values stay in
`config_values`; the importer does not claim that a particular setting affects
an item without that relationship being evidenced. `properties` can attach
arbitrary named facts, units, conditions, status, and source to items, blocks,
or registry entries. Current Create runtime stress records are imported there.
An unregistered stress value is `unavailable` with a null value even if the
legacy evidence row contains a numeric zero.

The `item` command reports recipes that make an item and recipes using it
directly or through a loaded item tag. It also includes block properties
attached to the item's associated block. Recipe rows retain statuses for
incomplete inputs, outputs, or custom semantics. A missing use in a legacy
capture or a dynamic recipe is not proof that no such recipe exists.
