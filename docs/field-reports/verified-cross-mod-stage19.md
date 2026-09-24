# Verified cross-mod capture: full-pack validation

Validated against a disposable server matching the Create: Ch4oS Packwiz
loadout. The handbook checkout was not modified. The evidence archive is
`E:\Extractor\captures\stage19-verified-cross-mod.zip` (SHA-256
`87e1cc8d1f5000c2e58bf859217c4cd0d0db6f19365ec9862ddb8ad590a10db2`),
and the imported database is
`E:\Extractor\captures\stage19-verified-cross-mod.sqlite`.

| Area | Captured result |
| --- | ---: |
| Loaded mods | 279 |
| Items / effective recipes | 10,980 / 17,725 |
| Mechanic property rows | 36,788 |
| Structured definitions / relations | 425 / 2,012 |
| CC item-backed registered blocks | 208 |
| Mapped CC method APIs / item links | 85 / 127 |
| Central Kitchen eligible deployer / saw conversions | 305 / 233 |
| Slice & Dice accepted source/result recipe pairs | 513 |

The CC registration fact comes from NeoForge's loaded block-capability
registration event. It applies to an item only when its associated block has a
registered CC provider. Lua methods are linked where an installed provider
class with `LuaFunction` annotations maps to that registered block. A provider
may still return no peripheral for a particular state, side, or world context;
the capture does not claim an in-world computer connection.

Central Kitchen's saw and deployer conversions are runtime machine behavior.
The capture records effective settings and links only accepted Farmer's Delight
cutting recipes that satisfy the installed automation predicate and, for saws,
the installed saw eligibility check. Slice & Dice links accepted generated
recipes to accepted source recipes; it does not duplicate them. World-specific
shop prices and controller networks are outside this static server capture.

The CC, Central Kitchen, and Slice & Dice adapter diagnostics reported `ok`.
The archive passed manifest verification, the imported database passed SQLite
`integrity_check`, and the viewer displayed a mapped CC item and navigable
source-to-generated recipe links. The offline Java build, Python tests,
JavaScript syntax check, and runtime safety check passed.
