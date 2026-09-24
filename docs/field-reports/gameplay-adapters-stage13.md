# Gameplay adapters: full-pack validation

Validated against a disposable server built from the Create: Ch4oS Packwiz
loadout. The source handbook repository was not modified. The evidence archive
is `E:\Extractor\captures\stage13-gameplay.zip` (SHA-256
`f8d9a39c4fdb4d7d2bff4ee3705f5f15b8e6411df2f08fd495e83256f4fdfa20`),
and the imported database is `E:\Extractor\captures\stage13-gameplay.sqlite`.

| Area | Captured result |
| --- | ---: |
| Loaded mods | 279 |
| Items / effective recipes | 10,980 / 17,725 |
| Existing mechanic property rows | 36,580 |
| Structured definitions / relations | 350 / 321 |
| Propulsion | 170 definitions, 188 relations, 31 settings |
| Electro Energetics | 107 definitions, 115 relations, 54 settings |
| Petrochem | 16 accepted custom recipes, 5 settings |
| Create Diesel Generators | 5 fuel types, 38 accepted custom recipes, 18 relations, 24 settings |
| CC peripheral integrations | 14 class APIs with Lua method annotations |

All eight bundled adapter diagnostics reported `ok`. The import passed SQLite
`integrity_check`. The generic item, recipe, and mechanic totals match the
pre-adapter capture. `verify_export` checked every file against the manifest,
and the Python tests, Java build, JavaScript syntax check, and runtime safety
check passed.

The specialized recipe adapter intersects effective JSON resources with IDs
accepted by the loaded recipe manager. Rejected recipe resources remain outside
these active definitions. Empty material result lists on
Petrochem engine-fuel recipes are recorded as fuel specifications. Electro's
insulation voltage is identified as an insulation rating. CC peripheral
signatures come from installed class annotations; attachment to a placed block
and a computer has not been simulated.

The local viewer now exposes structured definitions and their relationships in
the **Gameplay data** view, filterable by adapter. Older capture databases open
with an empty view. The underlying archive remains additive and importable by
the existing v1 database pipeline.
