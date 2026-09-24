# Create runtime exporter 0.2.2 full run

## Evidence identity

- Run ID: `20260726-085142-fcd81d3e`
- Clean archive SHA-256:
  `8ef3b90525a344f49a43f392c67e8d3c3bb4a3ec34a4d9477d4cb4dbfe783db3`
- Runner-log SHA-256:
  `28733b14185b578107d4fdd94d617e5111a1c63d8b2c5a83e1a899a7a6e3ad9d`
- Minecraft-log SHA-256:
  `556f5a4e4001210d86ee283458aadca5f4e51536135705165e3a0710e29db15e`
- Minecraft: 1.21.1
- NeoForge: 21.1.233
- Create: 6.0.10
- Declared pack: All of Create - Aeronautics v2.1
- Export scope: full
- Loaded mods: 239
- Connected players: 0
- Raw assets exported: false
- Network requests performed by exporter: false

Both uploaded copies of the ZIP and logs were byte-identical. Every file named
by `manifest.json` matched both its recorded byte size and SHA-256 digest.
Every JSON and JSONL record parsed successfully, and every provenance count
matched the corresponding file's actual row count.

## Full results

| Evidence | Rows |
|---|---:|
| Create items | 699 |
| Create blocks | 643 |
| Create-related effective recipe headers | 1,888 |
| Item-tag memberships | 800 |
| Block-tag memberships | 2,747 |
| Effective mechanics facts | 1,309 |
| Effective server/common settings | 102 |

Item, block, and mod IDs were unique within their respective files. All
requested reconciliation IDs were present, with zero missing items and zero
missing blocks.

The three runtime-introspection subsystems completed without partial results:

| Subsystem | Status | Rows | Field errors |
|---|---|---:|---:|
| Stress registries | `ok` | 1,309 | — |
| Server config | `ok` | 101 | 0 |
| Common config | `ok` | 1 | 0 |

This confirms the 0.2.2 `ConfigGroup` correction and the separate common-config
root. Runtime coverage now agrees with the corrected static inventory:
27 client settings, 101 server settings, and one common/world-generation
setting. The dedicated-server exporter intentionally captures the 102 loaded
server/common values and not the 27 client-only values.

## Static-catalog reconciliation

The static catalog contains 687 candidate player-facing item forms. Runtime
contains 699 registered `create:*` items:

- 685 IDs appear in both layers.
- Static-only `create:package` and `create:rare_package` are generic
  resource/model candidates rather than live registry IDs.
- Runtime adds four registered cardboard-package dimensions and ten registered
  rare-package variants.

The runtime-only registrations are:

- `create:cardboard_package_10x8`
- `create:cardboard_package_10x12`
- `create:cardboard_package_12x10`
- `create:cardboard_package_12x12`
- `create:rare_creeper_package`
- `create:rare_darcy_package`
- `create:rare_evan_package`
- `create:rare_jinx_package`
- `create:rare_kryppers_package`
- `create:rare_simi_package`
- `create:rare_starlotte_package`
- `create:rare_thunder_package`
- `create:rare_up_package`
- `create:rare_vector_package`

This is the expected purpose of runtime reconciliation: it replaces two
ambiguous resource candidates with the 14 concrete item registrations actually
loaded by Create 6.0.10.

Recipe totals are not expected to match the source-only catalog one-for-one.
The full runtime set reflects effective datapack loading, installed-mod
conditions, and runtime-generated compatibility recipes. The static set also
retains source-declared conditional recipes whose optional dependencies may not
be installed. The runtime file is therefore authoritative for recipes present
in stock pack v2.1, while static records remain useful for source locations,
ingredients, and conditional intent.

## Operational result

The runner completed all eight stages, preserved both logs, created the clean
JSON/JSONL evidence ZIP, removed the disposable server directory, and retained
the verified server-pack cache. No runner error token or exporter-component
warning/error was present.

The submitted full run satisfies the final field-validation gate for the
runtime exporter proof of concept.
