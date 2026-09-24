# Recipe detail stage validation

The public Create: Ch4oS Packwiz ZIP was captured again on Minecraft 1.21.1 /
NeoForge 21.1.248 with the additive recipe-detail exporter. The disposable
server completed its export and shut down. All 21 manifest-listed evidence
files passed byte-count and SHA-256 checks. The local capture ZIP SHA-256 is
`3260e55d8f605e8a21f787f341dce5b870b91a7af0ceac5a66beb0218ec5a563`;
its manifest SHA-256 is
`4d627c6a716b20562123168119a6b915972adee8e9e807dff631f5f60e67dff5`.

| Recipe measure | Count |
| --- | ---: |
| Effective loaded recipes | 17,725 |
| Detail rows | 17,725 |
| Active source JSON captured | 17,094 |
| Serializer representations encoded | 17,660 |
| Recipes with normalized item/fluid inputs | 17,658 |
| Recipes with normalized item/fluid outputs | 17,576 |
| Generated recipes without a source JSON resource | 631 |
| Generated Slice & Dice recipes not re-encodable by their serializer | 65 |
| Unloaded recipe resources, including conditional skips | 3,531 |
| Parse failures in the server log | 39 |

All 65 recipes without source JSON and codec output retained runtime item
inputs and outputs through fallback methods, including multiple outputs and
chances. The 67 rows with no exposed item/fluid inputs and 149 with no exposed
item/fluid outputs are marked `not_exposed_or_not_applicable`; the exporter
does not turn unknowns into zero. Source JSON or serializer output remains
available for most of those special recipes. A vanilla smithing recipe
captured all three item inputs, and a shaped recipe counted repeated symbols
in its layout. The lookup command found 16 recipes making
`minecraft:iron_ingot` and 225 using it, including item-tag matches.

Every one of the 39 server-log parse failures matched an active resource in
`unloaded-recipe-resources.jsonl`. Its source-pack IDs confirmed the two Paxi
ZIPs that override six recipes with empty JSON. See the
[rejected recipe report](public-pack-rejected-recipes.md) for the source and
cause breakdown. The other 3,492 unloaded resources must not be called parse
failures without a matching log error; many are conditional skips.

A separate minimal Packwiz ZIP without Create also completed a 21-file
capture with 1,290 recipe-detail rows. The pack-specific captures and server
logs are local test artifacts and are not committed to this repository.
The handbook's existing `mod_catalog` archive validator accepted the new
capture and its original 17,725-row `recipes.jsonl` file without modification.
