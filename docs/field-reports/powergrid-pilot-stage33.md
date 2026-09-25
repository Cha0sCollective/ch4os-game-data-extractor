# Power Grid 0.6.1 gap review — current Create: Ch4oS pack

This report covers the current pack's installed Power Grid 0.6.1 JAR. The
handbook stock-v2.1/Power Grid 0.5.5.1 material remains a separate historical
snapshot. The handbook repository was not changed.

- Disposable-server capture: `E:\Extractor\captures\stage33-powergrid.zip`;
  imported database: `E:\Extractor\captures\stage33-powergrid.sqlite`.
- Reviewed knowledge: `E:\Extractor\captures\gde-knowledge.sqlite`; snapshot
  `036e71e3ba239fed30e59fabc3fa5df12485021aac98e1e0fa22e448c1e8802d`.
- Installed artifact: `powergrid-mc1.21.1-0.6.1.jar`, SHA-256
  `b2835c36af6794a963737c617b5f9dd6b41aba5078d418c88847193fbcf702e5`.
- Power Grid adapter status: `ok`, with 99 mechanics, 52 effective configs,
  29 definitions and 58 relations. The 26 runtime circuit-component entries
  all have item or tag mappings; 27 `provides_circuit_component` links include
  one entry with both forms. Circuit Design Table pages expose the 26
  `supports_circuit_component` links through the generic relationship view.

## Gaps investigated

| Area | New reviewed evidence | Next source-analysis work |
| --- | --- | --- |
| Storage | Charge-dependent battery voltage and resistance, energy updates, multiblock capacity conditions | Trace charging and thermal-control branches; no universal safe charging voltage/current was found. |
| Generation and conversion | Generator EMF and winding model, motor load, transformer coupling, FE inverter control; effective rotor, field and core settings | Trace the remaining assembly controls and express loaded output as conditional. |
| Wiring | Type-specific cooling factors; heating formula, 175°C default overheat state and visual consequences | Trace cutting, entity contact and connector topology. The inspected overheat path itself does not remove the wire. |
| Measurement | 5-block multimeter probe setting, voltage/current probe modes, thermometer, plotter and modular-display paths | Trace display scaling and plotter timing. |
| Control and protection | Contactor switching added to earlier fuse, breaker and LV/MV switch evidence | Trace relay, redstone and HV-switch control paths. |
| Circuit design | All 26 loaded component mappings; design-table schematic writing and board assembly paths | Trace board baking, execution and cooling. |
| Portable equipment | Effective tool speed settings and all four boostable action paths | Trace zapper projectile and low-charge supply behavior. |
| Integrations | Installed CC, Create, Simulated and Sable bridge paths distinguished from optional absent mods | Trace per-device APIs and loaded bridge behavior. |

At the stage-33 checkpoint, the knowledge database contained 185 accepted findings: 38 claims,
10 relationships, 4 formulas, 132 coverage decisions and one adapter task.
All 116 Power Grid item identities are covered. The eight focused areas above
now have verified, artifact-backed review slices. Their broader
`full_gameplay_analysis` statuses remain **unresolved** while the named code
paths are analyzed. Source-follow-up findings supersede the older coverage
wording in the live viewer. The assembly-instrumentation task has been closed
as unnecessary for this source-led workflow. Stage-32 adapter tasks were
closed with stage-33 evidence.

The stage-32 → stage-33 revalidation is explicitly marked reviewed. The
revalidation note records the unchanged installed artifact, matching 116-item
inventory, equivalent prior Power Grid runtime properties and accepted new
findings. Revalidation now has a review action in the CLI and local viewer;
accepting a subset of findings alone does not clear its pending status.

## Verification

The capture ZIP authenticated on import. The stage-33 database passed
`integrity_check` and contains 10,980 items and 17,725 accepted recipes;
none of the 3,531 unloaded/rejected recipe resource IDs entered the accepted
recipe table. The viewer at `http://127.0.0.1:8766/` serves this snapshot and
shows reviewed revalidation and item relationships. Python tests (32),
JavaScript syntax check, safety verification and offline Gradle build pass.

The next substage reads the eight remaining code paths from the exact installed
artifact and turns reviewed facts into a Power Grid guide. No live probe is
part of this workflow. The handbook repository remains behind the Power Grid
GDE review gate.
