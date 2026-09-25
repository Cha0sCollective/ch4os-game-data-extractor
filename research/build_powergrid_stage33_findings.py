"""Build review proposals for the exact installed Power Grid 0.6.1 artifact.

Previous findings are re-proposed only after inventory, artifact, and runtime
property equality checks. This writes proposals, never reviewed knowledge.
"""

from __future__ import annotations

from copy import deepcopy
import json
import math
from pathlib import Path
import sqlite3


ROOT = Path(r"E:\Extractor\captures")
REPO = Path(__file__).resolve().parent.parent
OLD = ROOT / "stage32-powergrid.sqlite"
NEW = ROOT / "stage33-powergrid.sqlite"
OLD_JOBS = ROOT / "research" / "powergrid-stage32"
NEW_JOBS = ROOT / "research" / "powergrid-stage33"
OLD_FINDINGS = REPO / "research" / "powergrid-stage32-findings.jsonl"
OUTPUT = REPO / "research" / "powergrid-stage33-findings.jsonl"
ARTIFACT_SHA = "b2835c36af6794a963737c617b5f9dd6b41aba5078d418c88847193fbcf702e5"


def packets(folder: Path) -> dict[str, dict]:
    manifest = json.loads((folder / "manifest.json").read_text(encoding="utf-8"))
    return {packet["job_id"]: packet for entry in manifest["jobs"]
            for packet in [json.loads((folder / entry["file"]).read_text(encoding="utf-8"))]}


def properties(db: sqlite3.Connection) -> dict[tuple[str, str], tuple]:
    rows = db.execute("SELECT entity_id,property_key,value_json,unit,conditions_json FROM properties "
                      "WHERE entity_id LIKE 'powergrid:%'")
    return {(item, key): (json.loads(value) if value is not None else None, unit,
                          json.loads(conditions) if conditions is not None else None)
            for item, key, value, unit, conditions in rows}


def equivalent(first, second) -> bool:
    if type(first) in (int, float) and type(second) in (int, float):
        return math.isclose(first, second, rel_tol=1e-6, abs_tol=1e-9)
    if isinstance(first, dict) and isinstance(second, dict):
        return first.keys() == second.keys() and all(equivalent(first[key], second[key]) for key in first)
    if isinstance(first, (list, tuple)) and isinstance(second, type(first)):
        return len(first) == len(second) and all(equivalent(a, b) for a, b in zip(first, second))
    return first == second


with sqlite3.connect(OLD) as old, sqlite3.connect(NEW) as new:
    old_items = {row[0] for row in old.execute("SELECT id FROM items WHERE mod_id='powergrid'")}
    new_items = {row[0] for row in new.execute("SELECT id FROM items WHERE mod_id='powergrid'")}
    if len(old_items) != 116 or old_items != new_items:
        raise ValueError("Power Grid item inventory changed; findings need individual review")
    for db in (old, new):
        hashes = {row[0] for row in db.execute(
            "SELECT sha256 FROM installed_artifacts WHERE declared_mod_ids_json LIKE '%powergrid%'")}
        if ARTIFACT_SHA not in hashes:
            raise ValueError("installed Power Grid artifact changed")
    old_properties, new_properties = properties(old), properties(new)
    if not all(key in new_properties and equivalent(value, new_properties[key])
               for key, value in old_properties.items()):
        raise ValueError("previous Power Grid runtime properties changed")
    component_count = new.execute("SELECT COUNT(*) FROM adapter_definitions WHERE adapter_id='powergrid' "
                                  "AND kind='circuit_component' AND status='captured_directly'").fetchone()[0]
    mapping_count = new.execute("SELECT COUNT(*) FROM adapter_relations WHERE adapter_id='powergrid' "
                                "AND predicate='provides_circuit_component'").fetchone()[0]
    if component_count != 26 or mapping_count < component_count:
        raise ValueError("loaded circuit component mappings are incomplete")
diagnostics = [json.loads(line) for line in
               (ROOT / "stage33-powergrid-evidence" / "introspection-diagnostics.jsonl")
               .read_text(encoding="utf-8").splitlines()]
powergrid_diagnostics = [row for row in diagnostics
                         if row.get("subsystem", "").startswith("mechanic_adapter:powergrid")]
if len(powergrid_diagnostics) != 1 or powergrid_diagnostics[0]["status"] != "ok":
    raise ValueError("Power Grid adapter reported a partial subsystem")

old_packets = packets(OLD_JOBS)
new_packets = packets(NEW_JOBS)
by_subsystem = {packet["subsystem"]: packet for packet in new_packets.values()}
snapshot_id = next(iter(new_packets.values()))["snapshot_id"]
findings: list[dict] = []

for line in OLD_FINDINGS.read_text(encoding="utf-8").splitlines():
    finding = json.loads(line)
    if finding["record_type"] == "adapter_request":
        continue
    if finding["record_type"] == "coverage" and finding["subject_kind"] == "system":
        continue
    subsystem = old_packets[finding["job_id"]]["subsystem"]
    proposal = deepcopy(finding)
    proposal["snapshot_id"] = snapshot_id
    proposal["job_id"] = by_subsystem[subsystem]["job_id"]
    proposal["finding_id"] = "powergrid:stage33_revalidated:" + finding["finding_id"].split(":", 2)[-1]
    findings.append(proposal)


def add(subsystem: str, suffix: str, record_type: str, subject_kind: str,
        subject_id: str, **fields) -> None:
    findings.append({"format": "ch4os-research-finding-v1", "snapshot_id": snapshot_id,
                     "job_id": by_subsystem[subsystem]["job_id"],
                     "finding_id": "powergrid:stage33:" + suffix, "record_type": record_type,
                     "subject_kind": subject_kind, "subject_id": subject_id, **fields})


def artifact(locator: str) -> dict:
    return {"kind": "installed_artifact", "artifact_sha256": ARTIFACT_SHA, "locator": locator}


def claim(subsystem: str, suffix: str, subject: str, predicate: str, value,
          locator: str, conditions: dict | None = None, unit: str | None = None) -> None:
    add(subsystem, suffix, "claim", "item", subject, predicate=predicate, value=value,
        unit=unit, conditions=conditions or {}, evidence=artifact(locator))


def relation(subsystem: str, suffix: str, subject: str, predicate: str,
             object_kind: str, object_id: str, locator: str, conditions: dict | None = None) -> None:
    add(subsystem, suffix, "relation", "item", subject, predicate=predicate,
        object_kind=object_kind, object_id=object_id, conditions=conditions or {},
        evidence=artifact(locator))


def formula(subsystem: str, suffix: str, subject: str, result: str,
            expression: dict, unit: str, locator: str, conditions: dict | None = None) -> None:
    add(subsystem, suffix, "formula", "item", subject, result_predicate=result,
        expression=expression, unit=unit, conditions=conditions or {}, evidence=artifact(locator))


# Storage: distinguish chemical charge, open-circuit output, internal resistance,
# and the circuit's actual terminal voltage and current.
claim("electricity-battery", "battery_soc_model", "powergrid:battery",
      "electrical.battery.operating_model",
      "State of charge determines source voltage and internal resistance. Circuit current changes stored energy each tick; the value is clamped between empty and assembled capacity.",
      "org.patryk3211.powergrid.electricity.battery.BatteryBlockEntity#updateParameters,#calculatePower,#electricalTick,#setEnergy",
      {"assembly": "ordinary batteries can form a capacity-scaled multiblock", "not_a_rating": "no fixed safe charging voltage or current inferred"})
claim("electricity-battery", "potato_soc_model", "powergrid:potato_battery",
      "electrical.battery.operating_model",
      "Source voltage and resistance follow state of charge; terminal behavior also depends on connected load.",
      "org.patryk3211.powergrid.electricity.battery.PotatoBatteryBlockEntity;BatteryBlockEntity#updateParameters")

# Generation and conversion: all assembled/live values are conditional.
formula("kinetics-generator", "generator_emf_formula", "powergrid:generator_housing",
        "electrical.generator.generated_emf",
        {"operation": "multiply", "sign_convention": "negative", "operands": [
            {"variable": "rotor_speed"}, {"variable": "field_strength"},
            {"capture_property": "electrical.generator.winding_coil_constant"}]}, "V",
        "org.patryk3211.powergrid.kinetics.base.GeneratorBlockEntity#emfVoltage",
        {"assembly": "connected rotor and windings", "meaning": "EMF, not guaranteed loaded terminal voltage"})
claim("kinetics-generator", "winding_count_resistance", "powergrid:generator_housing",
      "electrical.generator.winding_model",
      "Winding resistance depends on the count of connected coils and parallel winding paths; the simulated winding also has inductance proportional to resistance.",
      "org.patryk3211.powergrid.kinetics.generator.winding.WindingBlockEntity#getCoilCount,#calculateElectricalParameters",
      {"assembly": "actual placed windings; no universal fixed output"})
claim("kinetics-motor", "motor_load_model", "powergrid:electric_motor",
      "electrical.motor.operating_model",
      "Electrical input power and Create stress determine rotational speed and torque; the dynamic-resistance setting changes the electrical load model.",
      "org.patryk3211.powergrid.kinetics.motor.ElectricMotorBlockEntity#torque,#calculateSpeed,#tick",
      {"configuration": "powergrid.server.electricity.motorDynamicResistance and powergrid.server.kinetics.torqueForStress"})
claim("electricity-transformer", "transformer_coupling", "powergrid:transformer_core",
      "electrical.transformer.operating_model",
      "Configured primary and secondary turns, core inductance and coupling create a coupled-inductor circuit. Turn ratio alone does not guarantee a fixed loaded output voltage.",
      "org.patryk3211.powergrid.electricity.transformer.TransformerBlockEntity#buildCircuit",
      {"assembly": "both winding configurations and terminal pairs must be present"})
formula("electricity-febridge", "fe_inverter_output_model", "powergrid:fe_inverter",
        "electrical.fe_inverter.output_voltage",
        {"operation": "multiply", "operands": [
            {"operation": "divide", "operands": [{"variable": "stored_FE"},
                {"config": "powergrid.server.electricity.forgeEnergyPerVolt"}]},
            {"operation": "subtract", "operands": [1, {"variable": "smoothed_control_throttle"}]}]}, "V",
        "org.patryk3211.powergrid.electricity.febridge.FEInverterBlockEntity#updateParameters,#electricalTick",
        {"control": "throttle derives from control-capacitor voltage and configured control voltage",
         "energy_port": "FE capability is exposed on the facing side"})

# Wiring, measurement, and control.
formula("electricity-wire", "wire_heat_model", "powergrid:wire",
        "electrical.wire.temperature_change_per_tick",
        {"operation": "divide", "operands": [
            {"operation": "subtract", "operands": [
                {"operation": "divide", "operands": [
                    {"operation": "multiply", "operands": [
                        {"variable": "current_squared"}, {"variable": "resistance"}]}, 20]},
                {"operation": "divide", "operands": [
                    {"operation": "multiply", "operands": [
                        {"capture_property": "electrical.wire.dissipation_factor"},
                        {"variable": "temperature_minus_ambient"}]}, 20]}]},
            {"capture_property": "electrical.wire.thermal_mass"}]}, "deg C/tick",
        "org.patryk3211.powergrid.electricity.wire.BaseWireEntity#temperatureUpdate",
        {"enabled_if": "powergrid.server.electricity.wireOverheating", "scope": "wire type and placed geometry determine resistance"})
claim("electricity-wire", "wire_overheat_consequence", "powergrid:wire",
      "electrical.wire.overheat_consequence",
      "The wire has a 175°C default overheat threshold. Two consecutive heating ticks above it set an overheated state and client visual effects; the inspected path does not automatically remove or damage the wire.",
      "org.patryk3211.powergrid.electricity.wire.BaseWireEntity#<init>,#testForOverheat,#setSharedFlagOnFire;BlockWireEntity#tick;HangingWireEntity#tick",
      {"enabled_if": "wireOverheating", "separate_behavior": "wire cutting and entity shock are separate interactions"})
claim("equipment-multimeter", "multimeter_probe_modes", "powergrid:multimeter",
      "electrical.meter.probe_modes",
      "Terminal probing measures voltage; probing a wire measures current. Main-hand shift interaction clears the probe connection; voltage and current warnings use separate effective limits.",
      "org.patryk3211.powergrid.equipment.multimeter.MultimeterItem#useOn,#useOnWire,#onTerminal,#inventoryTick,#getMode,#setMode",
      {"probe_distance": "see effective electrical.meter.maximum_probe_distance"})
claim("equipment-thermometer", "thermometer_state", "powergrid:thermometer",
      "electrical.thermometer.reporting",
      "Reports current and maximum observed temperature through its dial, redstone output and goggle tooltip; tooltip warning colors change at 125, 150 and 175°C.",
      "org.patryk3211.powergrid.equipment.thermometer.ThermometerBlockEntity#temperature,#tick,#resetMax,#addToGoggleTooltip",
      {"meaning": "display warning bands, not material failure ratings"})
claim("kinetics-plotter", "plotter_sampling", "powergrid:plotter",
      "electrical.plotter.sampling",
      "Connected sampling wires feed a recorded buffer; kinetic speed changes sampling, and the plotter supports per-trace color and maximum-value controls.",
      "org.patryk3211.powergrid.kinetics.plotter.PlotterBlockEntity#buildCircuit,#tick,#resample,#onSpeedChanged,#setColor")
claim("electricity-modulardisplay", "modular_display_slots", "powergrid:modular_display",
      "electrical.modular_display.reporting",
      "Display modules select and color measurement slots; display state is electrically updated and thermal slots can blank on overheating.",
      "org.patryk3211.powergrid.electricity.modulardisplay.ModularDisplayBlockEntity#interact,#setColor,#setIndex,#electricalTick;DisplaySlotThermal",
      {"state": "placed, configured display"})
claim("electricity-contactor", "contactor_switching", "powergrid:contactor",
      "electrical.contactor.switching",
      "A controllable contactor builds two switched wire paths; its state can drive a 0/15 comparator signal and stacked contactors are supported.",
      "org.patryk3211.powergrid.electricity.contactor.ContactorBlockEntity#buildCircuit,#electricalTick,#setState,#getSignal",
      {"state": "placed circuit and control input"})

# Designed circuits are not reducible to ordinary recipe outputs.
claim("circuits-editor", "design_table_workflow", "powergrid:circuit_design_table",
      "circuit.design_table.workflow",
      "The design table edits a schematic and writes or reads it on a schematic item; the custom design is serialized in item data.",
      "org.patryk3211.powergrid.circuits.editor.CircuitDesignTableBlockEntity#createMenu,#setSchematic,#writeToItem,#readFromItem",
      {"input": "player-designed layout", "not_an_ordinary_recipe": True})
claim("circuits-circuitboard", "board_schematic_build", "powergrid:circuit_board",
      "circuit.board.assembly",
      "A placed board reads the schematic, derives its required component items, and builds a circuit from the design.",
      "org.patryk3211.powergrid.circuits.circuitboard.CircuitBoardBlockEntity#setSchematic,#getRequiredItems,#buildCircuit",
      {"components": "26 loaded component mappings captured in adapter definitions and relationships"})
relation("circuits-editor", "design_table_schematic", "powergrid:circuit_design_table",
         "writes_design_to", "item", "powergrid:circuit_schematic",
         "org.patryk3211.powergrid.circuits.editor.CircuitDesignTableBlockEntity#writeToItem")
relation("circuits-circuitboard", "board_schematic", "powergrid:circuit_board",
         "loads_design_from", "item", "powergrid:circuit_schematic",
         "org.patryk3211.powergrid.circuits.circuitboard.CircuitBoardBlockEntity#setSchematic")

# Portable equipment and verified loaded integrations.
for tool, subsystem, behavior, locator in [
    ("portable_drill", "equipment-drill", "Boosted mining doubles charge draw; the drill's speed settings are captured separately.", "org.patryk3211.powergrid.equipment.drill.DrillItem#energyPerUse,#getDestroySpeed"),
    ("portable_saw", "equipment-saw", "Boosted mining doubles charge draw and destroy speed; crouching can invoke Create tree cutting.", "org.patryk3211.powergrid.equipment.saw.SawItem#energyPerUse,#getDestroySpeed;com.simibubi.create.content.kinetics.saw.TreeCutter"),
    ("electrobaton", "equipment-baton", "Boosting keeps the configured base charge cost, but raises the effect cap from 30 to 60 and slow duration from 60 to 120 ticks.", "org.patryk3211.powergrid.equipment.baton.ElectroBatonItem#energyPerUse,#hurtEnemy"),
    ("electrozapper", "equipment-zapper", "Boosting keeps the configured base shot cost and doubles a projectile parameter; precise damage and range are not inferred.", "org.patryk3211.powergrid.equipment.zapper.ElectroZapperItem#energyPerUse,#use;ZapProjectileEntity#create"),
]:
    claim(subsystem, tool + "_boost_behavior", "powergrid:" + tool,
          "electrical.portable_tool.boost_behavior", behavior, locator,
          {"boost_item": "powergrid:integrated_circuit", "requires": "boost component on tool"})
    relation(subsystem, tool + "_boost_item", "powergrid:integrated_circuit",
             "boosts", "item", "powergrid:" + tool,
             "org.patryk3211.powergrid.equipment.BoostRecipe#matches;ItemBoostUtils#isBoosted",
             {"recipe": "loaded Create deployer boost recipe", "already_boosted": "recipe does not match"})
claim("compat-cc", "cc_registered_devices", "powergrid:redstone_converter",
      "integration.computercraft.registration",
      "The installed CC bridge registers peripheral capabilities for redstone converter, battery, energy meter, generator clutch, and gauge devices.",
      "org.patryk3211.powergrid.compat.cc.CCBridge#registerCapabilities",
      {"installed_dependency": "computercraft 1.120.2", "methods": "see captured peripheral adapter and device-specific claims"})
claim("compat-simulated", "simulated_sensor_bridge", "powergrid:redstone_converter",
      "integration.simulated.sensor_bridge",
      "The installed Simulated bridge registers five sensor sources with Power Grid's redstone converter registry.",
      "org.patryk3211.powergrid.compat.simulated.SimulatedBridge#setup",
      {"installed_dependency": "simulated 1.3.1", "device": "redstone converter"})
claim("compat-sable", "sable_fan_bridge", "powergrid:electric_fan",
      "integration.sable.electric_fan_bridge",
      "The installed Sable bridge substitutes an electric-fan block entity and tracks ship sublevel transitions for entities.",
      "org.patryk3211.powergrid.compat.sable.SableProxyImpl#init,#setSubLevelTracking",
      {"installed_dependency": "sable 2.0.5", "state": "bridge registration; no fixed thrust rating inferred"})

for subject, subsystem, area, explanation in [
    ("powergrid:storage", "electricity-battery", "storage_operating_model", "Battery charge-dependent voltage, resistance, energy update and multiblock capacity were reviewed against the exact artifact; effective values are captured."),
    ("powergrid:generation", "kinetics-generator", "dynamic_conversion_model", "Generator winding/EMF, motor load, transformer coupling and FE inverter controls were reviewed; assembly-dependent outputs remain conditional."),
    ("powergrid:wiring", "electricity-wire", "wire_thermal_model", "Wire resistance, thermal mass and cooling factors are runtime captured; overheat threshold and visual consequences were reviewed in the artifact."),
    ("powergrid:measurement", "equipment-multimeter", "measurement_device_behavior", "Gauge, energy meter, multimeter, thermometer, plotter and modular-display behavior has artifact-backed findings."),
    ("powergrid:control_protection", "electricity-contactor", "contactor_switching", "Contactor switching is reviewed in addition to prior fuse, breaker and LV/MV switch findings."),
    ("powergrid:circuit_design", "circuits-circuitboard", "component_and_board_workflow", "All 26 loaded circuit components have captured mappings; table and board schematic flow is source reviewed."),
    ("powergrid:portable_equipment", "equipment-drill", "boosted_tool_paths", "All four boostable tools have reviewed action-path behavior with effective base charge costs separately captured."),
    ("powergrid:integrations", "compat-cc", "installed_bridges", "Installed CC, Create, Simulated and Sable bridges are distinguished from optional absent integrations."),
]:
    add(subsystem, area + "_coverage", "coverage", "system", subject,
        area=area, status="verified", explanation=explanation)

for subject, subsystem, explanation in [
    ("powergrid:storage", "electricity-battery", "Exact in-world charge acceptance and thermal safety under representative circuits still need focused testing; no universal safe-input limit was found."),
    ("powergrid:generation", "kinetics-generator", "Assembly-specific generator/transformer outputs and remaining kinetic devices need placed-system tests before a complete design guide."),
    ("powergrid:wiring", "electricity-wire", "Thermal behavior is reviewed; wire cutting, entity shock and connector topology need focused interaction tests."),
    ("powergrid:measurement", "equipment-multimeter", "Device paths are reviewed, but display scaling and plotter timing need placed-device verification."),
    ("powergrid:control_protection", "electricity-contactor", "Contactor, fuse and breaker paths are reviewed; relay, redstone and high-voltage switch interactions need full circuit tests."),
    ("powergrid:circuit_design", "circuits-circuitboard", "Component mappings and schematic-to-board flow are reviewed; a representative custom circuit still needs an end-to-end in-world build test."),
    ("powergrid:portable_equipment", "equipment-drill", "Boosted action paths are reviewed; zapper projectile effect and battery supply behavior need focused in-world tests."),
    ("powergrid:integrations", "compat-cc", "Loaded bridge registration is reviewed; per-device API behavior and Sable/Simulated usage need focused loaded-server tests."),
]:
    add(subsystem, subject.split(":")[1] + "_remaining", "coverage", "system", subject,
        area="full_gameplay_analysis", status="unresolved", explanation=explanation)

add("kinetics-generator", "assembly_parameters_adapter", "adapter_request", "system",
    "powergrid:generation", description="Record placed generator winding, rotor, motor and transformer assembly parameters with circuit state when an instrumented test can expose them; do not treat configured limits as actual output.")

findings.sort(key=lambda row: row["finding_id"])
if len({row["finding_id"] for row in findings}) != len(findings):
    raise ValueError("duplicate finding IDs")
OUTPUT.write_text("".join(json.dumps(row, sort_keys=True, separators=(",", ":")) + "\n"
                          for row in findings), encoding="utf-8")
print({"snapshot_id": snapshot_id, "findings": len(findings), "output": str(OUTPUT)})
