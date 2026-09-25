# Power Grid 0.6.1: completed source-analysis passes

The eight remaining Power Grid gameplay passes for snapshot
`036e71e3ba239fed30e59fabc3fa5df12485021aac98e1e0fa22e448c1e8802d`
are complete in GDE. This review used the exact installed
`powergrid-mc1.21.1-0.6.1.jar` (SHA-256
`b2835c36af6794a963737c617b5f9dd6b41aba5078d418c88847193fbcf702e5`)
and the effective stage-33 capture. It used no live probes or placed-device
testing. The stock-v2.1 Power Grid 0.5.5.1 research remains a separate
historical version.

The final pass added 45 accepted findings: 31 claims, five typed
relationships, and nine coverage decisions. The eight previously unresolved
`full_gameplay_analysis` systems—storage, generation, wiring, measurement,
control and protection, circuit design, portable equipment, and integrations—
are now verified for source-led explanation in this snapshot. The inventory
audit added a ninth verified device-family scope for loads and actuators. All
116 registered Power Grid items retain identity coverage, all 26 captured
circuit-component mappings are present, and no Power Grid finding is pending.
Both older open Power Grid adapter tasks are resolved with stage-33 evidence:
component mappings are captured as typed records; effective generator,
rotor, winding, and transformer config values are captured, while
assembly-dependent outputs remain conditional source-derived facts.

The [current-pack guide](../guides/power-grid-0.6.1-current-pack.md) now covers
battery charge and thermal behavior, generation and transformer assemblies,
wire contact and cutting, measurement and displays, protective controls,
board execution, portable supply, installed ComputerCraft methods, and the
major powered device families. Those device families include Create-facing
heaters, fan, pump, and electromagnet, plus light fixtures, CRT, carbon pile,
alarm bell, rheostat, variac, servo, punch-card reader, and spark gap. The
viewer exposes their evidence on the corresponding item pages. No
source-derived number is presented as a universal input-voltage rating where
the code instead computes behavior from charge, temperature, assembly, or
load.

One proposed portable-battery wording was rejected during exact-bytecode
review: an insufficient-charge draw removes the charge component and returns
zero, rather than preserving the residual charge. The corrected finding is
accepted and cited by the guide. The rejected record remains in the review
history, with its claim and evidence removed.

Validation: the guide resolves 84 accepted GDE claims or relationships with
snapshot-matched evidence; the finding builder reproduced byte-for-byte
output; 32 Python tests and the runtime safety check pass. The live viewer on
port 8766 returned the updated Power Grid battery claims and verified
coverage. The handbook repository remains unchanged for the pilot review
gate.
