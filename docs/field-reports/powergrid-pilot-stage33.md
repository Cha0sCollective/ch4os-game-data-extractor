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

| Area | New reviewed evidence | Remaining guide-readiness test |
| --- | --- | --- |
| Storage | Charge-dependent battery voltage and resistance, energy updates, multiblock capacity conditions | Measure a representative charging circuit and thermal behavior; no universal safe charging voltage/current was found. |
| Generation and conversion | Generator EMF and winding model, motor load, transformer coupling, FE inverter control; effective rotor, field and core settings | Observe assembled generator/transformer parameters and loaded output in placed systems. |
| Wiring | Type-specific cooling factors; heating formula, 175°C default overheat state and visual consequences | Test wire cutting, entity contact and connector topology in world. The inspected overheat path itself does not remove the wire. |
| Measurement | 5-block multimeter probe setting, voltage/current probe modes, thermometer, plotter and modular-display paths | Check display scaling and plotter timing on placed devices. |
| Control and protection | Contactor switching added to earlier fuse, breaker and LV/MV switch evidence | Exercise relay, redstone and HV-switch combinations in circuits. |
| Circuit design | All 26 loaded component mappings; design-table schematic writing and board assembly paths | Build and run a representative custom circuit end to end. |
| Portable equipment | Effective tool speed settings and all four boostable action paths | Test projectile effect and low-charge supply in world. |
| Integrations | Installed CC, Create, Simulated and Sable bridge paths distinguished from optional absent mods | Exercise per-device API and Sable/Simulated use cases on the loaded server. |

The knowledge database contains 185 accepted stage-33 findings: 38 claims,
10 relationships, 4 formulas, 132 coverage decisions and one adapter task.
All 116 Power Grid item identities are covered. The eight focused areas above
now have verified, artifact-backed review slices. Their broader
`full_gameplay_analysis` statuses remain **unresolved** until the named
placed-device tests pass; the viewer shows those specific reasons. The one
open task concerns live assembly parameters unavailable to a registry-only
startup capture. Stage-32 adapter tasks were closed with stage-33 evidence.

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

The next substage is a disposable-server placed-device fixture for the eight
remaining full-analysis areas. It should record live state and interaction
results as test evidence, then close only the coverage areas its assertions
actually establish. Handbook work remains behind the Power Grid GDE review
gate.
