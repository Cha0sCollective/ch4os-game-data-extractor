# Create runtime exporter 0.5.0 pack run

## Result

The 2026-08-25 owner-approved stock-v2.1 disposable dedicated-server run
completed successfully.

- Run ID: `20260825-104010-47565904`
- Manifest SHA-256:
  `eddf0f32634a5e4c628985dd60507b6bcbda59fa97ba3f5cf0eaf2c79a5d1dc7`
- ZIP SHA-256:
  `21cd4d7b2e0550f2e3599e45f6fde19f5539cf8089115023b7b8f0e32366b960`
- `registry-summaries.jsonl` SHA-256:
  `c2af3a807c933f4e746b3e1af5d6202d892bb29f10b551608c5bc1230dd14e9c`
- `registry-entries.jsonl` SHA-256:
  `3edd2b22b61bf8de7afa31fd980f32708e4002e7f0691abf488ec747a8b65981`
- `registry-tags.jsonl` SHA-256:
  `1a886ef328b0eb041c9736ea4c2305b1a19da00c1d0955f39487406359acf002`

## Runtime checks

- Minecraft 1.21.1, NeoForge 21.1.233, Create 6.0.10, declared pack v2.1.
- Dedicated-server guard passed with zero connected players.
- Official server-pack size and SHA-256 lock passed.
- All 12 data stages completed.
- 167 registries, 27,102 entries, and 49,960 generic tag memberships captured.
- Prior 239-mod, 9,433-item, 7,862-block, and 14,953-recipe counts remained
  stable.
- Create introspection completed with no non-ok subsystem result.
- Installed-artifact inventory completed with zero diagnostics.
- All requested sample item/block IDs reconciled.
- Every manifest-listed file passed byte-count and SHA-256 verification.
- Server exited 0 and the marker-guarded disposable instance was removed.

The stock bootstrap emitted its ordinary pack compatibility, client-class-on-
server mixin, missing optional item, and version-check timeout warnings. None
prevented server startup, datapack completion, export, manifest authentication,
or clean shutdown. These logs remain local because they contain machine paths.

## Handoff checks

The per-mod handoff builder re-authenticated the same manifest and produced 97
packets, 97 prompts, and 97 source-reference rows. All runtime gameplay artifact
hashes matched the committed baseline. The source ledger contains 84 public
repository references and 13 explicit no-public-source/official-distribution
routes. Published prompt text contains no local user, AppData, or export-root
paths.

The transferable local handoff ZIP is 4,914,867 bytes with SHA-256
`f8b65defffd5015eea07c6079fb9709519a8d8622b83858fcd9f5a320153ad15`.

The candidate also passes the exporter build/safety/PowerShell checks, full
Knowledge and version gates, independent Draft 2020-12 validation of all
35,260 active-snapshot records, and the unchanged 185-test repository
baseline.
