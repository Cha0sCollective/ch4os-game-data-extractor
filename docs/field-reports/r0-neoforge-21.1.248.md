# Standalone R0 server capture

An owner-provided server archive was used as a fixture for a fresh disposable
capture on Minecraft 1.21.1 / NeoForge 21.1.248 with Create 6.0.10. The source
archive SHA-256 was `c228034ab4418cec9521ea7d92aa2fba70d4ea6e954720cb5ddaf7ed3c7abea0`.

Only the server mods, libraries, configuration, datapacks, and server config
defaults were copied into the disposable instance. World state, player lists,
account caches, and prior logs were excluded. The copied instance bound to
`127.0.0.1` on an ephemeral port with query and RCON disabled.

The generic `neoforge-1.21.1` profile completed a pack-wide export. All 19
manifest-listed files passed byte-count and SHA-256 checks. The capture reports:

Manifest SHA-256: `99a6f363feef8169fa04c29554017cdd1a06577582f1cd390755ca518a0667c`.
Local export ZIP SHA-256: `01dc77876d4ba1a4798596175d2f612a0752b874acbf4ec259f8bd53d7273e46`.

| Record | Count |
| --- | ---: |
| Loaded mods | 268 |
| Items | 10,363 |
| Blocks | 8,649 |
| Effective recipe headers | 15,741 |
| Registry identities | 29,783 |
| Installed artifacts | 229 |
| Artifact diagnostics | 0 |

Create stress and server/common configuration introspection reported `ok`.
The server completed its capture and exited successfully; a mod's background
thread triggered a warning during shutdown. These counts describe this R0
snapshot, not the older handbook v2.1 baseline. The source archive and raw
capture stay local and are not committed.
