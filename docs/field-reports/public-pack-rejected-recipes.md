# Public Packwiz pack: 39 rejected recipe definitions

The Minecraft 1.21.1 / NeoForge 21.1.248 server log from the public Create:
Ch4oS Packwiz capture contains 39 `Parsing error loading recipe` entries. These
definitions never entered the effective recipe manager, so they are separate
from the 17,725 loaded recipes. The errors come from these active resources:

| Effective source | Count | Cause shown by the log and resource |
| --- | ---: | --- |
| `petrochem-neoforge-1.21.1-1.3.2.jar` (`data/gearbox/recipe/…`) | 16 | Fifteen refer to unregistered `gearbox:*` serializers; one sequenced assembly also uses invalid/stale fields. No `gearbox` mod was loaded. |
| `create_things_and_misc-4.1.1-neoforge-1.21.1.jar` | 6 | Four sail recipes refer to items from absent optional mods; two refer to `create_things_and_misc:deleted_mod_element`. |
| Paxi `no_dnd_diamond_1.21.zip` | 4 | Four DnDesires recipes are overridden with `{}`, which has no recipe `type`. The original JAR definitions are populated; the Paxi ZIP is the active source. |
| `createcafe-1.4.3.jar` | 4 | Two Blood Magic altar and one Botania infusion serializers are absent; one mixing ingredient names `c:foods/blood_orange` as an item that does not exist. |
| `cmpackagecouriers-neoforge-2.3.0.jar` | 3 | Two recipes refer to its missing `portable_stock_ticker` item; one uses a missing Create Factory Logistics item. |
| Paxi `Create_Easy_Stone_Generators_ No_Obsidian_Gen.zip` | 2 | Two Create Generators recipes are overridden with `{}` and lack a recipe `type`. |
| `createdeco-2.1.3.jar` | 1 | The placard recipe uses `{"id":"minecraft:white_dye"}` as an ingredient, where the ingredient codec expects `item` or `tag`. |
| `justenoughbreeding-neoforge-1.21.1-3.2.1.jar` | 1 | The Quark shiba breeding recipe has `{"meat":"true"}` in its ingredient list, which the codec does not accept. |
| `mechanical_botany-1.1.3+1.21.1-neoforged.jar` | 1 | Its Create Cafe integration refers to the absent `createcafe:coffee_seeds` item. |
| `create_fantasizing-1.21.1-1.2.0-b3.jar` | 1 | It refers to the unregistered `create:mystery_conversion` serializer. |

The two Paxi ZIP names suggest that their empty overrides were intended to
remove recipes. On this runtime, an empty JSON object is still passed to the
recipe parser and logged as an error. This is an inference from the ZIP names
and contents; the pack authors' intent was not independently confirmed.

Recipe IDs were matched to `data/<namespace>/recipe/<path>.json` entries in
the installed mod JARs and Paxi datapack ZIPs. The six overridden IDs exist in
both a mod JAR and a Paxi ZIP; the `{}` parse error confirms the Paxi version
was active. The new `unloaded-recipe-resources.jsonl` evidence independently
reports those Paxi ZIP names as the active `source_pack_id` and records source
JSON for all 39 rejected IDs. It also contains conditionally skipped recipes;
only IDs paired with server-log parse errors are counted here. This field
report describes this snapshot only. Changes to the pack or mod versions could
change the list.
