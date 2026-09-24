# Mechanic adapter stage validation

The standalone exporter was built with Java 21 and run on a **copy** of the
previous public Create: Ch4oS disposable server. The capture completed all 12
data stages and shut down with exit code 0. The original handbook checkout and
the earlier server capture ZIP were not modified.

The new capture is `E:\Extractor\captures\stage5-public-adapters.zip`
(SHA-256 `792c7554fd0d021c7e91d5d439f351c363ec29c217b0a13145865f281eb14d7a`).
The imported database is `E:\Extractor\captures\stage5-public-adapters.sqlite`.

| Measure | Count |
| --- | ---: |
| Loaded items | 10,980 |
| Loaded recipes | 17,725 |
| Total mechanic property rows | 36,580 |
| Existing Create mechanic rows | 18,314 |
| Create Deep Seas hull rows | 18,234 |
| Power Grid rows | 32 |

All three adapter diagnostics reported `ok`. The SQLite database passed
`PRAGMA integrity_check` and `PRAGMA foreign_key_check`. The source handbook's
existing runtime importer also accepted the new capture using its unchanged
schema; it imported all 36,580 mechanic rows. This confirms the additive rows
retain the older fields required by existing archive readers.

Representative installed-pack values:

| Item | Property | Effective value | Context |
| --- | --- | ---: | --- |
| `create_submarine:ballast_tank` | Hull max water depth | 230 blocks | Default block state when used as a hull block; whole-submarine limit depends on weakest hull block |
| `create_submarine:ballast_tank` | Implosion chance | 0.04 | Implosion enabled in this capture |
| `powergrid:wire` | Wire maximum current | 80 A | Registered wire type |
| `powergrid:multimeter` | Maximum voltage | 500 V | Configured measurement range, not a device safety rating |

The local viewer was restarted on this database and visually checked on the
ballast tank detail page. It shows the hull values, their conditions, and their
runtime API source. The existing item and recipe inventories have the same
counts as the prior capture. The previous capture ZIP and database remain
available for comparison in the later diff stage.
