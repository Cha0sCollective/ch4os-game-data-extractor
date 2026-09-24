# Local browser

Start the app with Python 3.11 or newer:

```text
python local_app.py
python local_app.py --database "C:\captures\game-data.sqlite"
python local_app.py --data-dir "D:\Ch4oS Data" --port 8765
```

It binds only to `127.0.0.1`, opens the browser, and uses the Python standard
library. `Ctrl+C` stops the local server. The default data directory is
`runs/local-app` in the extractor repository; capture ZIPs, imported databases,
and disposable server logs remain there. They are not committed.

The **Mods** view opens first, sorted by mod name. It starts with mods that
register loaded items; a checkbox also shows loaded mods with no items.
Select a mod to see its items, then use **View mod recipes** to inspect recipes
in the same namespace.
The all-items and all-recipes navigation remains available, including items
whose registry namespace has no matching loaded mod. The **Items** view
searches loaded item names and IDs and filters by mod. An
item page shows its basic facts, default component values, associated block,
state properties, block-entity types, item and block tags, mechanic properties,
and recipes that make or use it. A block's registered CC capability appears
on its item page; mapped Lua methods appear where the installed provider class
is known. Registration does not guarantee availability in every world state.
Items with registered Create Display Link roles show their available data-source
types or display-target types. The Display Link item lists all registered types
in the loaded pack; actual content and target capacity depend on the placed
blocks.
Uses include captured item-tag membership.
The **Recipes** view searches recipe IDs and known result items and filters by
namespace and recipe type. It shows normalized inputs, outputs, intermediate
steps, collection statuses, active resource pack, and expandable raw detail
JSON. Accepted cross-mod recipe links and eligible runtime conversions appear
on the source recipe page.
The **Gameplay data** view browses structured adapter definitions by adapter:
fuel tables, electrical ratings, specialized processes, and CC peripheral APIs.
Each detail shows relationships, evidence conditions, and source provenance.
Older captures without structured adapter files simply show an empty view.
**Analysis** shows conservative recipe conflict and ingredient findings
and compares the open database against an earlier capture ZIP or database.
See [recipe analysis](recipe-analysis.md) for supported contexts and limits.
**Coverage** groups unavailable, failed, and partial collection areas.
These statuses matter: an unexposed dynamic recipe input is not a known zero or
proof that an item has no uses.

The **Capture or import** dialog has three routes:

1. **Run a pack:** enter a Packwiz `pack.toml` HTTPS link or choose a local
   Packwiz/Prism ZIP, optionally give the Java 21 executable, accept the
   Minecraft EULA for the new disposable server, and start. The app calls the
   existing `ch4os_capture.py` runner and imports the resulting capture when
   it succeeds. Build the exporter JAR first with `./gradlew build` (or
   `gradlew.bat build` on Windows).
2. **Import capture:** choose an existing Ch4oS capture ZIP or enter its local
   path. The ZIP is verified and imported into a new SQLite file. The original
   capture is not changed.
3. **Open database:** enter the path of a database already built by this tool.
   Browsing connections are read only.

CSV and JSON buttons export the current filtered item or recipe list. These
are factual list exports; the complete recipe definition is available on each
recipe detail page and in the SQLite database. Generated documentation pages
are a separate later stage.

Only one capture or import job runs at a time. The dialog shows its progress
and any error; the retained server work directory is named in the capture
log. Local capture is limited to Minecraft 1.21.1 / NeoForge 21.1.x by the
current exporter build. Pack updates within that supported family use the
pack's declared versions.
