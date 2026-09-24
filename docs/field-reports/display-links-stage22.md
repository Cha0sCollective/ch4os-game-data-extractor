# Display Link registrations: full-pack validation

Validated against a disposable server copy of the Create: Ch4oS Packwiz
loadout. The handbook checkout was not modified. The evidence archive is
`E:\Extractor\captures\stage22-display-links.zip` (SHA-256
`ae2036a388d584b54bab017fde83208bc44dce34a586696aaab957ca739de08f`),
and the imported database is `E:\Extractor\captures\stage22-display-links.sqlite`.

| Area | Captured result |
| --- | ---: |
| Loaded mods | 279 |
| Items / effective recipes | 10,980 / 17,725 |
| Display source / target definitions | 78 / 13 |
| Item-to-source / item-to-target links | 165 / 78 |
| Display Link item to registered type links | 91 |
| Total gameplay definitions / relations | 516 / 2,346 |

The adapter reads Create's loaded Display Source and Display Target registries
and their block and block-entity lookup tables. It includes registrations made
by installed add-ons and tag providers. Item links require an item-backed
block, a registered source or target for that block or one of its valid block
entity types, and inclusion in the pack scope. Multiple block variants sharing
one item are combined into one item relationship.

For example, `powergrid:voltage_gauge` provides the registered
`powergrid:electric_gauge` source, `aeronautics:steam_vent` provides
`aeronautics:gas_display`, and `minecraft:acacia_sign` accepts the
`create:sign` target. `create:content_observer` offers item and fluid count and
list sources; `minecraft:chest` has no direct Display Link source registration
in this loadout. The Display Link item lists all registered source and target
types, and source/target definition pages link to the item-backed blocks that
provide them.

This is a registry-level compatibility map. Available options, line capacity,
and live displayed text can depend on the placed blocks and world state. The
capture does not claim that every source and target pair works in every setup.

The Display Link adapter diagnostic reported `ok`. The archive passed
manifest verification, the database passed SQLite `integrity_check`, and the
local viewer displayed the new item and definition links. The offline Java
build, Python tests, JavaScript syntax check, and runtime safety check passed.
