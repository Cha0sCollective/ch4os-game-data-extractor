# Recipe detail export

`recipes.jsonl` remains the original v1 header file. Pack captures now add
`recipe-details.jsonl` with one `ch4os-recipe-detail-v1` row for each effective
loaded recipe. The runtime export manifest authenticates both files. Existing
v1 readers can continue using the original header file.

Each detail row includes the recipe ID, type, serializer, implementation
class, recipe namespace, source resource ID and pack ID, and the source JSON
where the resource is available. It also records the recipe codec's encoded
representation when the serializer can produce one. Runtime item ingredients
include their encoded ingredient definitions, expanded item choices, and a
status if a large choice list was truncated. The collector derives item and
fluid inputs and outputs, amounts, chances, catalysts, sequenced processing
steps, shaped layout, conditions, and common time/heat/energy fields where the
definition exposes them. Public runtime output methods are used as a fallback
for generated processing recipes whose serializer cannot encode them again.

`input_status`, `output_status`, `semantic_status`, `source_status`, and
`codec_status` distinguish collected facts from incomplete or unsupported
semantics. Missing quantities are omitted; they must not be interpreted as
zero. Custom recipe JSON is preserved even when the generic collector cannot
interpret every field. Some special recipes choose results dynamically from
the crafting input; their output status is explicitly incomplete.

The source JSON is recipe data read from the active resource manager. The
separate installed-artifact inventory still contains only archive metadata;
it does not export JARs, classes, models, or textures.

`unloaded-recipe-resources.jsonl` inventories JSON resources absent from the
effective recipe manager, with their active resource-pack ID and source JSON.
This includes recipes skipped by conditions as well as parse failures; a row
alone does not prove an error. Use the server log's `Parsing error loading
recipe` lines to identify rejected definitions. The
[public-pack rejection report](field-reports/public-pack-rejected-recipes.md)
traces the 39 errors in the tested public Packwiz snapshot.

For an immediate item lookup without SQLite, run:

```text
python recipe_lookup.py capture.zip create:brass_ingot
python recipe_lookup.py capture.zip minecraft:iron_ingot --direction uses --json
```

The lookup resolves item-tag inputs using the capture's `item-tags.jsonl` and
includes nested sequenced-assembly inputs. It reports only the facts exposed
by the detail rows; dynamic recipes with unexposed inputs or outputs may not
appear in the corresponding result list.
