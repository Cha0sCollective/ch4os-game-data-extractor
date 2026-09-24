# Adapter infrastructure stage validation

The exporter was built with Java 21 and run on a fresh copy of the public
Create: Ch4oS disposable server. The source handbook checkout and the previous
captures were not modified. The new capture is
`E:\Extractor\captures\stage7-infrastructure.zip` (SHA-256
`8a7bad8970a533d600b524516f68bd4e3a2d55d37303edea261bb4a1c73c9409`)
and the standalone database is
`E:\Extractor\captures\stage7-infrastructure.sqlite`.

| Measure | Count |
| --- | ---: |
| Loaded mods | 279 |
| Items | 10,980 |
| Effective recipes | 17,725 |
| Existing mechanic facts | 36,580 |
| Effective config values | 103 |
| New adapter definitions | 0 |
| New adapter relations | 0 |

The new files are empty until a mod-specific adapter emits structured facts.
The manifest authenticated all 25 evidence files, and the capture completed
all 12 collection stages. Create, Deep Seas, and Power Grid adapter diagnostics
remained `ok` and now include their installed mod versions. The standalone
database passed `PRAGMA integrity_check` and `PRAGMA foreign_key_check`.

The standalone importer also accepted the previous stage 6 ZIP with zero
definitions and relations. The unchanged handbook runtime importer accepted
the new stage 7 ZIP, verifying archive hashes and provenance counts and
importing 10,980 items, 17,725 recipes, and 36,580 mechanics. This checks the
additive archive contract before the new adapters populate these files.

Python's 17 unit tests, the safety check, and the offline Gradle build passed.
The importer fixture tests structured definitions, relations, and explicit
unknown values. The effective JSON resource reader and optional feature probes
compile; their live data paths will be exercised by the upcoming mod adapters.
