# Exporter 0.4.0 pack-scope field validation

**Run:** `20260729-124738-013a2efe`  
**Status:** passed  
**Environment:** stock All of Create – Aeronautics v2.1, Minecraft 1.21.1,
NeoForge 21.1.233, Create 6.0.10

This is the first field validation of exporter 0.4.0 in explicit `pack` scope.
It ran a disposable, loopback-only dedicated server with zero connected
players and exited successfully.

## Evidence identity

| Local evidence | SHA-256 | Repository treatment |
|---|---|---|
| `create-6.0.10-pack-20260729-124738-013a2efe.zip` | `e7e12d0e498834cbb9287118b1ad2dbffe387c892c17b796d49ca52157c098d7` | Retained outside Git; factual summaries committed |
| `create-export-20260729-124738-013a2efe.log` | `8d41ec0ca2975d02eeb5796ef69c3bb973f829146f0b69981aef14f0a0e54fef` | Not committed; contains local machine details |
| `create-export-20260729-124738-013a2efe-minecraft.log` | `e650d28b872a2a5b5d9cfece8b270da59b7dbc5fbffff503a2240e052374c040` | Not committed; diagnostic evidence only |

The uploaded duplicate copies were byte-for-byte identical to these three
files.

## Captured result

| Evidence family | Rows |
|---|---:|
| Loaded mods | 239 |
| Items | 9,433 |
| Blocks | 7,862 |
| Effective recipes | 14,953 |
| Item-tag memberships | 14,831 |
| Block-tag memberships | 30,585 |
| Effective mechanics facts | 15,781 |
| Effective server/common settings | 102 |
| Installed artifacts | 180 |
| Safe archive-entry locations | 148,966 |
| Mixin configurations | 257 |
| Java service descriptors | 130 |
| Artifact-inventory diagnostics | 0 |

Create stress-registry, server-config, and common-config introspection all
completed successfully. Every requested sample item and block ID reconciled.

## Authentication and safety checks

- The ZIP passed archive-integrity testing.
- Its manifest listed exactly the 16 payload files present; there were no
  missing or unlisted payloads.
- Every payload byte count and SHA-256 matched the manifest.
- Every JSON and JSONL file parsed, and every JSONL row count matched
  provenance.
- Provenance locked the run to Minecraft 1.21.1, NeoForge 21.1.233, Create
  6.0.10, pack v2.1, dedicated-server mode, and explicit `pack` scope.
- The evidence records `raw_assets_exported=false`,
  `raw_jars_exported=false`, `raw_archive_content_exported=false`, and
  `network_requests_performed=false`.
- All artifact references resolved, all recorded archive paths were safe, and
  no raw-content marker was present.
- The runner reused and reverified the cached official server pack.

## Pack-catalog import

The current PR #9 receiver imported the authenticated run successfully:

- snapshot `all-of-create-aeronautics-v2.1-a2824435d31a`;
- 261 merged client/server runtime components;
- 177 client-and-server, 22 client-only, and 62 server-only observations;
- 1,727 indexed pack files and 4,748 effective TOML options;
- 180 exact installed artifacts, 179 mod declarations, 148,966 safe entry
  locations, 257 mixin configs, and 130 service descriptors;
- 45 reviewed interaction records backed by 175 participants and 174 evidence
  rows;
- zero artifact-inventory diagnostics, TOML parse errors, or client/server
  version conflicts; and
- `PRAGMA quick_check = ok`, with overall validation passed.

All 97 gameplay targets matched an exact installed artifact filename and the
expected declared mod ID. There were no gameplay filename/declaration
mismatches.

## Diagnostic boundary

The catalog's two existing `client_artifact_without_mod_id` diagnostics are
not exporter failures. They correspond to the aggregate/wrapper artifacts
`connector-2.0.0-beta.15+1.21.1-full.jar` and
`kotlinforforge-5.12.0-all.jar`; the artifact inventory itself reported zero
diagnostics.

The Minecraft/NeoForge log also contains normal stock-pack startup warnings
and compatibility noise. Because the server exited with code 0, the exporter
completed every requested collector, and all evidence authentication passed,
those unrelated messages are not investigated in this validation.

## Conclusion

Exporter 0.4.0 has passed its pack-scope field gate. Its installed-artifact
metadata may now be treated as **installed-environment confirmed routing
evidence**. It identifies where a future question should be investigated; it
does not, by itself, prove what an unreviewed class or resource does.

No additional owner run is currently required. The next work is to route the
97 gameplay targets through these exact installed locations, prioritize the 13
without public source, and promote only reviewed findings into subsystem
evidence packets.
