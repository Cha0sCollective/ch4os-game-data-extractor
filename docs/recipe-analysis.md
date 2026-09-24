# Recipe analysis and snapshot comparison

Open **Analysis** in the local viewer to inspect the current database. To
compare pack versions, give it an earlier Ch4oS capture ZIP or SQLite database
as the baseline. The currently open database is the new snapshot. Both inputs
are read without modifying their contents. The viewer shows counts and the
first 100 records in each category. The command line writes the complete JSON
report:

```text
python recipe_analysis.py analyze current-capture.zip --output analysis.json
python recipe_analysis.py compare old-capture.zip new-capture.zip --output changes.json
```

SQLite database paths work in place of ZIP paths. The comparison reports
added, removed, and changed effective recipe IDs, plus new and resolved
conflict groups. A changed recipe lists the fields that differ, with old and
new values. It compares normalized captured definitions and processing facts,
not ZIP byte order or timestamps.

An input collision requires **the same processing context and exact captured
ingredient definitions**. The analyzer currently understands vanilla shaped
and shapeless crafting, smelting, blasting, smoking, campfire cooking, and
stonecutting. Shaped crafting accounts for horizontal mirroring. It reports
different outputs for the same crafting/cooking input as competing recipes,
and identical input/output/process definitions as equivalent recipe pairs.
Different stonecutter outputs from the same input are normal choices, so they are not
called conflicts. Recipes sharing only an output item are never grouped.

The analyzer does not infer tag overlap, shaped-versus-shapeless overlap, or
custom machine matching rules. Recipes without complete supported semantics
are counted by type as **inconclusive**; they still participate in ID-based
snapshot comparisons. Missing item and fluid IDs, and tags with no loaded
members, are listed separately where registry evidence exists. An empty tag
may be intentional in an optional compatibility recipe, so it is a review
finding rather than proof of a broken pack.

New pack captures include `recipe-overrides.jsonl`, a small, additive file
listing recipe resource IDs provided by more than one active resource pack,
their pack stack, and whether the effective recipe loaded. For loaded recipes,
the analysis also shows the effective recipe's source pack. This is source
override evidence, not a second effective recipe. Older captures have no
resource-stack evidence; the analysis explicitly marks override detection
unavailable for them. The capture archive format and existing handbook reader
remain compatible.
