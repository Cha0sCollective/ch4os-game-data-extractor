# Ch4oS Game Data Extractor

This repository is the standalone successor to the runtime exporter in the
[All of Create – Aeronautics handbook](https://github.com/Cha0sCollective/all-of-create-aeronautics-handbook).
The first stage preserves the existing NeoForge 1.21.1 exporter and its Windows
disposable-server runner. The game-data database and local application will be
built on this verified baseline.

## Current capabilities

The `pack` capture inventories loaded mods, items, blocks, effective recipe
headers, resolved tags, registry identities, and metadata about installed mod
artifacts. Create stress and configuration introspection remains available.
The current archive contract is `create-handbook-runtime-export-v1`; detailed
recipe ingredients and additional output semantics are future v2 work.

This stage retains the original mod ID, settings, runner names, and output
format so existing captures and handbook importers remain compatible. The
current Windows runner is pinned to the All of Create – Aeronautics v2.1 server
pack. See [legacy exporter instructions](docs/legacy-exporter.md) for its
guards, supported scopes, and usage.

## Build and verify

With Java 21 and Python 3:

```text
python verify_safety.py
./gradlew --no-daemon build
```

PowerShell can validate the Windows runner without starting Minecraft:

```powershell
./runner/Run-CreateHandbookExport.ps1 -ValidateOnly
```

The GitHub Actions workflow runs these checks and packages the original jar
with the Windows runner. Field reports from the source repository are in
`docs/field-reports/`; they document prior runs and do not claim a new run of
this standalone repository.

## Origin and attribution

The exporter history was filtered from `tools/create_runtime_exporter` at
handbook commit `deaf0dfae2daacfc759b80b2adab805f4bf83d35` (2026-08-29).
The handbook repository remains unchanged. The existing NeoForge mod metadata
declares MIT; the source repository does not include a repository-wide license
file, so no new license is asserted here.
