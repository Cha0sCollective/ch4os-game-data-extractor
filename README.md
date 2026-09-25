# Ch4oS Game Data Extractor

This repository is the standalone successor to the runtime exporter in the
[All of Create – Aeronautics handbook](https://github.com/Cha0sCollective/all-of-create-aeronautics-handbook).
The exporter preserves the existing NeoForge 1.21.1 runtime capture and its
Windows disposable-server runner. Captures can be imported into a local SQLite
item and recipe database and explored in a loopback-only browser.

## Current capabilities

The `pack` capture inventories loaded mods, items, blocks, effective recipes,
resolved tags, registry identities, and metadata about installed mod
artifacts. Optional [mechanic adapters](docs/mechanic-adapters.md) capture
Create stress, Create Deep Seas hull ratings, Power Grid limits, Propulsion
fuels, Electro Energetics ratings, Petrochem and Diesel Generators processes,
and installed CC peripheral APIs. Runtime sources and conditions accompany
these facts. The adapters use feature probes rather than pinned mod versions;
older captures remain importable.
The archive keeps the `create-handbook-runtime-export-v1` manifest and original
recipe headers. Additive `recipe-details.jsonl` rows include item and fluid
inputs and outputs, layouts, process facts, source JSON, and explicit coverage
statuses. See [recipe detail format](docs/recipe-details.md).
`recipe_lookup.py` answers which captured recipes make or use an item.
The additive `item-details.jsonl` records default item component values and
associated block-entity types where available. `game_data_db.py` builds a
normalized SQLite database from either current or earlier v1 capture ZIPs;
see [database format and limitations](docs/item-database.md).
`local_app.py` provides a mod-first directory, item, recipe, and gameplay-data browsing, coverage views, filtered
CSV/JSON exports, and capture/import controls. See [local browser guide](docs/local-browser.md).
The Research view prepares bounded source-analysis packets and reviews proposed
facts into a persistent, snapshot-scoped GDE knowledge database. Item pages
show all captured relationships and accepted source-derived claims with their
evidence labels. See [reviewed research workflow](docs/research-workflow.md).
The current Power Grid 0.6.1 pilot and its remaining guide-readiness tests are
recorded in [the stage-33 field report](docs/field-reports/powergrid-pilot-stage33.md).
Its Analysis view and `recipe_analysis.py` provide conservative recipe conflict
findings and baseline-to-current snapshot comparison; see [recipe analysis](docs/recipe-analysis.md).

This stage retains the original mod ID, settings, runner names, and output
format so existing captures and handbook importers remain compatible. The
current Windows runner selects the pinned All of Create – Aeronautics v2.1
profile. Direct exporter runs default to the general Minecraft 1.21.1 / NeoForge
21.1.x profile; mods and pack version are not pinned there. The exporter still
requires a disposable dedicated server, zero players, and explicit capture
confirmation. See [legacy exporter instructions](docs/legacy-exporter.md) for
the original runner and archive contract.

## Capture a Packwiz pack

The new capture command accepts a hosted Packwiz `pack.toml` link (including a
normal GitHub file link), a local or HTTPS ZIP
containing Packwiz files, or a Prism import ZIP that points to a Packwiz pack.
Both forms install only the server side into a new disposable NeoForge server.
It reads the pack's Minecraft and NeoForge versions, so routine mod and
NeoForge patch updates do not require a new hard-coded pack profile. This
exporter build supports Minecraft 1.21.1 / NeoForge 21.1.x; other game or
loader families need a compatible exporter build.

Build the exporter JAR with Java 21, then use Python 3.11 or newer:

```text
python ch4os_capture.py "https://example.org/pack/pack.toml" --inspect
python ch4os_capture.py "C:\path\to\pack.zip" --inspect
python ch4os_capture.py "C:\path\to\pack.zip" --accept-minecraft-eula --output "C:\path\to\capture.zip"
```

The full capture downloads the official NeoForge server installer and a
versioned Packwiz installer, installs the pack's server files, starts a local
loopback-only server, and writes a verified export ZIP. The disposable work
directory and logs are printed and retained for diagnosis. The EULA flag
records acceptance only in that disposable server; review the
[Minecraft EULA](https://www.minecraft.net/eula) before using it. For a Java
21 installation that is not on `PATH`, pass `--java` with its executable path.
The ZIP's prelaunch command is read only to find the Packwiz link; executable
files inside a supplied ZIP are never launched.

## Build a local database

With Python 3.11 or newer, import a capture to a new SQLite file and inspect
an item:

```text
python game_data_db.py import "C:\path\to\capture.zip" --output "C:\path\to\game-data.sqlite"
python game_data_db.py item "C:\path\to\game-data.sqlite" minecraft:iron_ingot
```

## Browse locally

```text
python local_app.py
python local_app.py --database "C:\path\to\game-data.sqlite"
```

The app opens at `http://127.0.0.1:8765/`. It can import a capture ZIP from a
file picker or local path, open an existing database, or start a new Packwiz
server-side capture from a link or ZIP. New captures require a built exporter
JAR, Java 21, and acceptance of the Minecraft EULA in the app.

## Build and verify

With Java 21 and Python 3:

```text
python verify_safety.py
python -m unittest discover -s tests
./gradlew --no-daemon build
```

PowerShell can validate the Windows runner without starting Minecraft:

```powershell
./runner/Run-CreateHandbookExport.ps1 -ValidateOnly
```

The GitHub Actions workflow runs these checks and packages the original jar
with the Windows runner. Field reports from the source repository are in
`docs/field-reports/`; they document prior runs and do not claim a new run of
this standalone repository. The
[Packwiz capture report](docs/field-reports/create-ch4os-public-packwiz.md)
documents a new end-to-end run of this command.

The Prism ZIP contains installer metadata rather than the gameplay JARs.

## Origin and attribution

The exporter history was filtered from `tools/create_runtime_exporter` at
handbook commit `deaf0dfae2daacfc759b80b2adab805f4bf83d35` (2026-08-29).
The handbook repository remains unchanged. The existing NeoForge mod metadata
declares MIT; the source repository does not include a repository-wide license
file, so no new license is asserted here.
