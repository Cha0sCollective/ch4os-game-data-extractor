# Create 6.0.10 Runtime Exporter

This directory contains a read-only NeoForge 1.21.1 diagnostic mod for the
All of Create - Aeronautics handbook. It verifies facts that static source and
resource inspection cannot prove.

This is a developer proof of concept, not a mod to add to the real Bisect
server or normal client profile.

## Phase 2A scope and completed full run

The exporter supports both a ten-item sample and a full `create:*` namespace
run. The completed full run exported:

- loaded mod IDs, names, and versions;
- all 699 loaded `create:*` item registrations;
- all 643 corresponding Create block registrations and block-state properties;
- default item stack limits, durability, rarity, and component IDs;
- effective Create recipe headers after datapack loading;
- resolved item and block tag memberships;
- effective stress impact, stress capacity, and generated-RPM facts from
  Create's loaded runtime registries;
- effective values exposed by Create's loaded server and common configuration sections;
- provenance, output hashes, and full static/runtime reconciliation.

The sample mode remains available for exporter development. Its representative
entries are Shaft, Cogwheel, Mechanical Press, Mechanical Mixer, Basin,
Mechanical Pump, Fluid Tank, Steam Engine, Clipboard, and Potato Cannon.

The validated full run captured 1,888 effective recipes, 3,547 item/block tag
memberships, 1,309 mechanics facts, and 102 server/common settings. All 699
runtime item IDs reconciled without an unexplained entry. See
[`../../testing/create-runtime-exporter-0.2.2-full.md`](../../testing/create-runtime-exporter-0.2.2-full.md).

Creative tabs, localized client tooltips, baked models, textures, renderers,
inventories, and fluid capacities remain deferred. Model and texture metadata
is captured separately from pinned source without redistributing raw assets.

## Safety contract

The exporter:

- runs only in a dedicated-server process;
- is inert unless explicitly enabled;
- requires an exact disposable-instance confirmation token;
- requires Minecraft 1.21.1, NeoForge 21.1.233, Create 6.0.10, and declared
  pack version v2.1;
- refuses to run while any player is connected;
- requires an absolute output path outside the game directory;
- refuses to write into a non-empty output directory;
- creates files with `CREATE_NEW` and never overwrites them;
- can stop its disposable server after either success or refusal when the
  runner explicitly enables automatic shutdown;
- performs no network requests;
- registers no items, blocks, recipes, commands, mixins, access transformers,
  or coremods;
- exports no textures, models, jars, world data, player data, or credentials.

`verify_safety.py` enforces this boundary in CI.

## Development build

Use Java 21 and Gradle 8.14:

```shell
python verify_safety.py
gradle --no-daemon build
```

The build produces only the original exporter jar. It does not download,
package, or publish the All of Create modpack.

## Windows disposable runner

The GitHub Actions artifact contains the exporter jar, its SHA-256 checksum,
and the files in `runner/`. After extracting the artifact, choose:

- `Run-CreateHandbookExport.cmd` for the ten-item sample; or
- `Run-Full-CreateHandbookExport.cmd` for the full Create namespace.

The runner:

- downloads the official v2.1 CurseForge server pack and verifies its exact
  size and SHA-256 hash before extraction;
- requires no administrator/elevated privileges;
- recovers a complete verified server-pack `.partial` file left by an older
  failed run instead of downloading the roughly 300 MB archive again;
- works only under `%LOCALAPPDATA%\CreateHandbookExporter`;
- binds the disposable Minecraft server only to `127.0.0.1` on an ephemeral
  port, with query and RCON disabled;
- asks the user to review and explicitly accept the Minecraft EULA;
- supplies the export settings through process-scoped environment variables;
- creates a clean output ZIP under
  `%USERPROFILE%\Documents\Create-Handbook-Exports`;
- reports eight numbered, timestamped runner stages and explains every
  expected setup download before handing control to the stock server script;
- emits `[HANDBOOK EXPORT]` progress lines for each of ten runtime
  data-collection stages and reports record counts;
- retains a human-readable runner transcript and the Minecraft/NeoForge
  `latest.log` beside the clean result ZIP under
  `%USERPROFILE%\Documents\Create-Handbook-Exports`;
- never reads or changes the CurseForge client instance or Bisect server;
- removes only a successful disposable run bearing its safety marker;
- retains failed runs locally for diagnosis.

The same settings may be supplied as JVM properties for manual developer
runs:

```text
-Dhandbook.export.enabled=true
-Dhandbook.export.confirm=DISPOSABLE_INSTANCE
-Dhandbook.export.packVersion=v2.1
-Dhandbook.export.scope=sample
-Dhandbook.export.output=<absolute path outside the game directory>
-Dhandbook.export.autoStop=true
```

Full-namespace export additionally requires:

```text
-Dhandbook.export.scope=full
-Dhandbook.export.fullConfirm=EXPORT_ALL_CREATE_RUNTIME_FACTS
```

The default remains the ten-item sample. Full scope has an additional
interactive confirmation and exporter confirmation token.

## Runtime diagnostics and sample reconciliation

Version 0.2.2 preserves the PowerShell runner transcript and, when the stock
server produces it, the Minecraft/NeoForge `latest.log`. Neither log is placed
in the clean evidence ZIP because diagnostic output can contain local Windows
paths or the local account name.

Sample block reconciliation now expects block records only for requested items
that actually declare a corresponding block ID. This prevents an item-only
entry such as the Potato Cannon from being reported as a missing block while
still detecting a genuinely absent block record.

The 0.2.2 evidence ZIP also contains `mechanics.jsonl`,
`config-values.jsonl`, and `introspection-diagnostics.jsonl`. The mechanics
records come from Create's effective runtime stress registries; the
configuration records come from the loaded server config objects. Diagnostic
rows make a reflection mismatch visible without discarding the rest of a run.
Config getters are isolated field by field, so one incompatible option produces
a precise diagnostic while the exporter continues through the remaining
sections. Registry reflection is performed through Create's public
`SimpleRegistry` API. Interactive confirmation phrases ignore capitalization,
leading/trailing spaces, and repeated internal whitespace.

Config traversal identifies Catnip `ConfigBase` sections before looking for a
value getter. This is significant because nested sections also expose a
guarded `get()` method; invoking it treats a section as a scalar and raises an
assertion instead of visiting its options.

Catnip `ConfigGroup` objects are organizational markers rather than values or
nested objects. They are skipped without a diagnostic; the scalar fields they
group are still exported. Version 0.2.2 also reads Create's common config root,
which contains its world-generation switch, separately from the server root.
