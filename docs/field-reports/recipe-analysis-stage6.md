# Recipe analysis stage validation

The stage 6 exporter was built with Java 21 and run on another copy of the
public Packwiz server. Its new resource-stack file was added to the existing
v1 capture format without changing the effective recipe or mechanic rows.
The source handbook repository remained clean at
`deaf0dfae2daacfc759b80b2adab805f4bf83d35`.

The capture is `E:\Extractor\captures\stage6-public-overrides.zip`
(SHA-256 `19bd8cde31b79426de70b565e33fce4eae3ae5e325b4c0600421715cf764570f`).
Its database is `E:\Extractor\captures\stage6-public-overrides.sqlite`.
The complete current analysis is
`E:\Extractor\captures\stage6-public-analysis-final.json`.

| Measure | Count |
| --- | ---: |
| Effective loaded recipes | 17,725 |
| Recipes with supported exact-input comparison | 12,785 |
| Inconclusive recipe matching | 4,940 |
| Competing-input recipe pairs | 32 |
| Equivalent recipe pairs | 10 |
| Missing item or empty-tag ingredient findings | 15 |
| Recipe IDs with multiple resource-pack definitions | 248 |

Of the 248 resource overrides, 242 have an effective loaded recipe and 6 do
not. These are active resource stacks, not 248 duplicate effective recipes.
The 15 ingredient findings include 2 missing item IDs, 10 empty or missing
item tags, and 3 empty or missing fluid tags. They need recipe-level review;
optional compat definitions can legitimately reference currently empty tags.

Comparing the previous stage 5 database to this stage 6 database found zero
added, removed, or changed effective recipes and zero new or resolved
conflicts. This is expected because both runs use the same pack. Small
fixture tests exercise changed outputs, additions/removals, conflict
resolution, mirrored crafting, stonecutter choices, and resource overrides.
The SQLite database passed integrity and foreign-key checks. The unchanged
handbook runtime importer accepted the new capture, importing all 17,725
recipes and 36,580 mechanic rows. The local viewer was checked with this
database and shows the 248 resource overrides in its Analysis view.
