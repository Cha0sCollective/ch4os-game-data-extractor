# Create 6.0.10 Runtime Exporter

This directory contains a read-only NeoForge 1.21.1 diagnostic mod for the
All of Create - Aeronautics handbook. It verifies facts that static source and
resource inspection cannot prove.

This is a developer proof of concept, not a mod to add to the real Bisect
server or normal client profile.

## Phase 2A scope

The first pass exports:

- loaded mod IDs, names, and versions;
- ten representative `create:*` item registrations;
- corresponding block registrations and block-state properties;
- default item stack limits, durability, rarity, and component IDs;
- effective Create recipe headers after datapack loading;
- resolved item and block tag memberships;
- provenance, output hashes, and sample reconciliation.

The sample entries are Shaft, Cogwheel, Mechanical Press, Mechanical Mixer,
Basin, Mechanical Pump, Fluid Tank, Steam Engine, Clipboard, and Potato
Cannon.

Creative tabs, localized client tooltips, baked models, textures, renderers,
Create-specific stress values, inventories, and fluid capacities are
deliberately deferred until this server-side evidence is validated.

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
and the files in `runner/`. After extracting the artifact, double-click
`Run-CreateHandbookExport.cmd`.

The runner:

- downloads the official v2.1 CurseForge server pack and verifies its exact
  size and SHA-256 hash before extraction;
- works only under `%LOCALAPPDATA%\CreateHandbookExporter`;
- binds the disposable Minecraft server only to `127.0.0.1` on an ephemeral
  port, with query and RCON disabled;
- asks the user to review and explicitly accept the Minecraft EULA;
- supplies the export settings through process-scoped environment variables;
- creates a clean output ZIP under
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
