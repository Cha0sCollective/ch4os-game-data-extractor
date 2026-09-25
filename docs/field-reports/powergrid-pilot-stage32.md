# Power Grid 0.6.1 pilot follow-up — current Create: Ch4oS pack

This is the follow-up GDE pilot on the current pack. It does not replace the
handbook's historical stock-v2.1/Power Grid 0.5.5.1 research. The handbook
repository was not changed.

- Capture: `E:\Extractor\captures\stage32-powergrid.zip`; imported database:
  `E:\Extractor\captures\stage32-powergrid.sqlite`; reviewed knowledge:
  `E:\Extractor\captures\gde-knowledge.sqlite`.
- Snapshot: `de691a61c001e6096318dd19037f2a36282093bfd122c7e24ad731355bae2451`.
- Installed Power Grid JAR: `powergrid-mc1.21.1-0.6.1.jar`, SHA-256
  `b2835c36af6794a963737c617b5f9dd6b41aba5078d418c88847193fbcf702e5`.
- Inventory: 116 Power Grid items, 77 blocks and 112 accepted recipes. The
  exporter ran on disposable NeoForge 21.1.248 and reported the Power Grid
  adapter `ok`: 83 mechanics, 34 effective configs, 3 definitions, 5 relations.

## Captured values and their limits

| Device | Effective stage-32 data | Boundary |
| --- | --- | --- |
| Ordinary battery | 120 Wh per block; starts at 90%; open-circuit output is 11.5 V empty and 12.7 V full; full-charge resistance 0.10002488 Ω | Multiblock capacity scales with assembled block count. These are charge-dependent outputs, not safe-input ratings. |
| Potato battery | 0.00006 Wh per block; 0.5–0.9 V open-circuit output; full-charge resistance 452.8996 Ω | No ordinary-battery multiblock behavior was inferred for this type. |
| Portable battery | 20,000 internal charge units base, plus 20,000 per Create Capacity level | Internal charge units have no reviewed Wh or voltage conversion. |
| Solar panel | Reference Voc 26.4 V, Isc 3.3 A, Vmp 21.12 V, Imp 3.036 A; 48 cells; NOCT 45°C; assembled array limit 25 panels | The installed implementation varies output with irradiance, weather, temperature, orientation and load. Reference values are not guaranteed circuit output. |
| LV / MV switch | 320 / 640 V overvoltage fault triggers | A fault trigger is not a universal safe operating rating; the HV switch uses a different implementation and has no value inferred from these. |
| Grounding rod | 10 conductive blocks minimum; 64 counted maximum; resistance-model endpoints 5,000 and 1 Ω | Actual resistance depends on the connected ground path. The artifact's 48 V damage trigger does not establish safety below that level. |
| FE inverter | 20 V control configuration; 20,000 FE internal buffer | Neither is a universal FE-to-electrical conversion ratio. |
| Voltage/current/power gauges | Selectable full-scale ranges 2/20/200/2000 V, 0.02/0.2/2/20 A, and 20/200/2000/20000 W | Measurement ranges are not safe-input ratings. |

The exact installed JAR also supports reviewed claims on dynamic generator
output, HV breaker trip conditions, fuse reset and trip behavior, gauge and
energy-meter measurement and redstone reporting, redstone-converter input,
portable-battery low-charge output, schematic storage, and selected CC
peripheral methods. The accepted findings are in
`research/powergrid-stage32-findings.jsonl`; their locators and artifact hash
appear on item pages separately from runtime-confirmed values.

## Review state

There are 157 accepted findings for this snapshot: 18 claims, 4 relations,
1 formula, 132 coverage decisions, and 2 adapter requests. Every item has
reviewed registry-identity coverage. Eight narrower system slices are verified:
battery ratings, solar reference settings, wire registry ratings, core meter
behavior, switch fault thresholds, schematic persistence, portable charge
source, and loaded CC/Create registration. Eight wider `full_gameplay_analysis`
areas remain **unresolved**: storage, generation, wiring, measurement, control
and protection, circuit design, portable equipment, and integrations. These
statuses are deliberate and visible in the viewer; a beginner-to-expert guide
must not treat them as completed coverage.

Two open adapter tasks request a typed circuit-component-to-item mapping and
effective generator/winding/transformer parameters where the server exposes
them. Further artifact analysis or focused tests are needed for charging
limits; generator assembly and output formulas; wire cooling and failure;
the remaining measurement and protection devices; circuit design workflow;
boosted tool paths; and each installed integration's usage conditions.

The public upstream `v0.6.1` tag is for Minecraft 1.20.1/Forge, so it was not
accepted as exact source for the installed 1.21.1/NeoForge artifact. Reviewed
source-derived claims cite the installed JAR and its hash. A later capture
receives a separate snapshot and revalidation queue; the older claims are not
silently carried over. The stage-32 proposals rechecked the unchanged JAR,
116-item inventory, and prior runtime facts before being explicitly reviewed.

## Verification

The stage-32 export manifest authenticated all 25 payload files; the imported
SQLite database passed `integrity_check`. The full pack import contains 10,980
items and 17,725 accepted recipes. None of the 3,531 unloaded/rejected recipe
resource IDs appears in the accepted recipe table. The local viewer at
`http://127.0.0.1:8766/` serves the stage-32 capture and knowledge store:
its Research API shows 116/116 Power Grid items with coverage, eight verified
system slices, eight unresolved wider areas, two open adapter tasks, and one
pending revalidation link. Python tests (31), JavaScript syntax check, and the
offline Gradle build pass.
