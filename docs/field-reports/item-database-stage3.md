# Item database stage validation

The public Create: Ch4oS server was run again with the additive item-detail
collector. It shut down with exit code 0 and produced a 22-file manifest. The
capture ZIP SHA-256 is
`4d744b86b0c8e1a3123a1abe8e95cc4adc0d63e16e93dd4cf88222d38d1cb3ce`;
the manifest SHA-256 is
`e1d265d2805a1c61210b7982cb12c3ed47eb026b8e2ab1d61625f212e8f256b4`.
The pack and handbook repositories were not modified.

| Database measure | Count |
| --- | ---: |
| Loaded items | 10,980 |
| Loaded recipes | 17,725 |
| Default item components | 67,981 |
| Component values captured | 67,979 |
| Component values whose codecs failed | 2 |
| Block items with collected block-entity type IDs | 2,685 |
| Block items with unavailable block-entity type IDs | 11 |
| Recipe terms | 52,327 |
| Runtime mechanic facts | 18,314 |
| Registry entries | 32,934 |
| Unloaded recipe resources | 3,531 |

The two component codec failures were `minecraft:max_damage` on
`create:cardboard_sword` and `quark:backpack`; each is marked `failed` with no
fabricated value. The 11 unresolved block-entity types belong to Handcrafted
fancy beds and are marked `unavailable`. Three `destroy:badge/*` items have no
matching loaded mod ID for their namespace, so their `mod_id` is null rather
than guessed. Of the 18,314 Create runtime mechanic rows, 1,086 have a
registered numeric value; 17,228 unregistered values are stored as
`unavailable` with null values, even though the original evidence rows contain
zero placeholders.

The SQLite import passed `PRAGMA integrity_check` and foreign-key checks. Its
item query found 16 final recipes making `minecraft:iron_ingot` and 225 using
it, matching the recipe-detail ZIP lookup. The original handbook archive
validator accepted the new 22-file capture and its unchanged 17,725 recipe
headers. A minimal Minecraft/NeoForge-only server also produced a 22-file
capture with 1,333 item details and 8,314 component values; all component
values encoded there. Both new captures imported, as did an earlier 21-file
capture without item details and an older capture without recipe details.
