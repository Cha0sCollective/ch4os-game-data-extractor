# Power Grid 0.6.1 source-led follow-up

Snapshot `036e71e3ba239fed30e59fabc3fa5df12485021aac98e1e0fa22e448c1e8802d`
uses the installed `powergrid-mc1.21.1-0.6.1.jar` (SHA-256
`b2835c36af6794a963737c617b5f9dd6b41aba5078d418c88847193fbcf702e5`).
The effective capture is `E:\Extractor\captures\stage33-powergrid.sqlite`;
reviewed findings are in `E:\Extractor\captures\gde-knowledge.sqlite`.

The previous optional placed-device probe was removed before release. Its 21
test-backed findings were retracted from the knowledge database, and the
disposable server's exporter JAR was rebuilt without the probe. No live probe
is needed to explain the installed code. The old stage-33 wording that made
in-world tests a guide gate is superseded by eight accepted source-analysis
coverage updates. The obsolete assembly-instrumentation task is resolved.

The source follow-up accepted 14 findings: ordinary-battery assembly shape and
thermal failure behavior, two transformer-core relationships, zapper projectile
behavior, a verified projectile-model slice, and eight updated full-analysis
coverage records. The installed code specifies battery assembly as square
horizontal layers up to three wide and five high, with capacity proportional
to width × width × height. The zapper code specifies projectile power, speed,
default weapon range, direct-hit scaling and nearby arcs. These findings are
source-derived and keep their artifact hash and method locators in GDE.

The [Power Grid guide draft](../guides/power-grid-0.6.1-current-pack.md)
combines those findings with the effective capture. Its 48 GDE references were
validated as accepted, snapshot-matched records with evidence, then recorded in
`guide_refs`. The guide is in this GDE repository for pilot review. The
handbook repository remains unchanged.

The later [final source-pass report](powergrid-final-source-passes.md)
supersedes this checkpoint's unresolved coverage statuses and 48-reference
guide count.
