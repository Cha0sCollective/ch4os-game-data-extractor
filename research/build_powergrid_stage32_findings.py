"""Curate explicit Power Grid 0.6.1 review proposals for the stage-32 capture.

This one-off pilot checks the new capture before proposing previously reviewed
findings again. It does not write to the knowledge store or accept findings.
"""

from __future__ import annotations

from copy import deepcopy
import json
import math
from pathlib import Path
import sqlite3


ROOT = Path(r"E:\Extractor\captures")
REPO = Path(__file__).resolve().parent.parent
OLD = ROOT / "stage28-powergrid.sqlite"
NEW = ROOT / "stage32-powergrid.sqlite"
OLD_JOBS = ROOT / "research" / "powergrid-stage28"
NEW_JOBS = ROOT / "research" / "powergrid-stage32"
OLD_FINDINGS = REPO / "research" / "powergrid-stage28-findings.jsonl"
OUTPUT = REPO / "research" / "powergrid-stage32-findings.jsonl"
ARTIFACT_SHA = "b2835c36af6794a963737c617b5f9dd6b41aba5078d418c88847193fbcf702e5"


def packets(folder: Path) -> dict[str, dict]:
    manifest = json.loads((folder / "manifest.json").read_text(encoding="utf-8"))
    return {packet["job_id"]: packet for entry in manifest["jobs"]
            for packet in [json.loads((folder / entry["file"]).read_text(encoding="utf-8"))]}


def normalized_properties(db: sqlite3.Connection) -> dict[tuple[str, str], tuple]:
    rows = db.execute("SELECT entity_id,property_key,value_json,unit,conditions_json FROM properties "
                      "WHERE entity_id LIKE 'powergrid:%'")
    return {(entry, key): (json.loads(value) if value is not None else None, unit,
                            json.loads(conditions) if conditions is not None else None)
            for entry, key, value, unit, conditions in rows}


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
        raise ValueError("Power Grid item inventory changed; findings need fresh individual review")
    for db in (old, new):
        artifacts = {row[0] for row in db.execute(
            "SELECT sha256 FROM installed_artifacts WHERE declared_mod_ids_json LIKE '%powergrid%'")}
        if ARTIFACT_SHA not in artifacts:
            raise ValueError("installed Power Grid artifact changed")
    old_properties, new_properties = normalized_properties(old), normalized_properties(new)
    if not all(key in new_properties and equivalent(value, new_properties[key])
               for key, value in old_properties.items()):
        raise ValueError("previous Power Grid runtime properties changed")

old_packets = packets(OLD_JOBS)
new_packets = packets(NEW_JOBS)
new_by_subsystem = {packet["subsystem"]: packet for packet in new_packets.values()}
snapshot_id = next(iter(new_packets.values()))["snapshot_id"]
findings: list[dict] = []

for line in OLD_FINDINGS.read_text(encoding="utf-8").splitlines():
    finding = json.loads(line)
    if finding["subject_kind"] == "system" and finding["record_type"] == "coverage":
        continue
    previous_subsystem = old_packets[finding["job_id"]]["subsystem"]
    if previous_subsystem not in new_by_subsystem:
        raise ValueError(f"research subsystem disappeared: {previous_subsystem}")
    proposal = deepcopy(finding)
    proposal["snapshot_id"] = snapshot_id
    proposal["job_id"] = new_by_subsystem[previous_subsystem]["job_id"]
    proposal["finding_id"] = finding["finding_id"].replace("stage28", "stage32_revalidated")
    findings.append(proposal)


def add(subsystem: str, suffix: str, record_type: str, subject_kind: str,
        subject_id: str, **fields) -> None:
    findings.append({"format": "ch4os-research-finding-v1", "snapshot_id": snapshot_id,
                     "job_id": new_by_subsystem[subsystem]["job_id"],
                     "finding_id": f"powergrid:stage32:{suffix}", "record_type": record_type,
                     "subject_kind": subject_kind, "subject_id": subject_id, **fields})


def artifact(locator: str) -> dict:
    return {"kind": "installed_artifact", "artifact_sha256": ARTIFACT_SHA, "locator": locator}


def claim(subsystem: str, suffix: str, subject: str, predicate: str, value,
          locator: str, conditions: dict | None = None, unit: str | None = None) -> None:
    add(subsystem, suffix, "claim", "item", subject, predicate=predicate, value=value,
        unit=unit, conditions=conditions or {}, evidence=artifact(locator))


claim("electricity-solarpanel", "solar_operating_conditions", "powergrid:solar_panel",
      "electrical.solar.output_conditions",
      "Panel output follows an irradiance- and temperature-dependent I/V model; shade, orientation, weather, array size and load change the operating point.",
      "org.patryk3211.powergrid.electricity.solarpanel.SolarPanelBlockEntity#getIrradiance,#electricalTick;SolarHelper#IVCurve",
      {"reference_values": "see effective solarPanelVoc/Isc/Vmp/Imp capture fields",
       "do_not_interpret_as": "fixed output or guaranteed power"})
claim("kinetics-generator", "generator_dynamic_emf", "powergrid:generator_housing",
      "electrical.generator.output_conditions",
      "Generated voltage depends on kinetic speed, field strength, winding properties and assembled generator state.",
      "org.patryk3211.powergrid.kinetics.base.GeneratorBlockEntity#emfVoltage;org.patryk3211.powergrid.kinetics.generator.winding.WindingBlockEntity#calculateElectricalParameters",
      {"value": "dynamic; no fixed voltage rating inferred"})
claim("electricity-grounding", "grounding_path_condition", "powergrid:grounding_rod",
      "electrical.grounding.path_condition",
      "A ground path is enabled only after enough connected conductive blocks are counted; its resistance varies with the count and configured endpoints.",
      "org.patryk3211.powergrid.electricity.grounding.GroundingRodBlockEntity#minBlocks,#lazyTick",
      {"configuration": "see captured groundingMinimumBlocks/MaximumBlocks/HighestResistance/LowestResistance"})
claim("electricity-grounding", "grounding_damage_condition", "powergrid:grounding_rod",
      "electrical.grounding.damage_condition",
      "The rod checks approximately every 10 game ticks; a modeled rod potential magnitude at or above 48 V can damage nearby entities.",
      "org.patryk3211.powergrid.electricity.grounding.GroundingRodBlockEntity#tick,DANGER_POTENTIAL",
      {"meaning": "hazard trigger in this implementation, not a promise of safety below 48 V"})
claim("electricity-electricswitch", "breaker_trip_condition", "powergrid:hv_breaker",
      "electrical.breaker.trip_condition",
      "When enabled and the simulation has converged, absolute current above the configured scroll setting opens the switched wire; a zero setting disables this trip.",
      "org.patryk3211.powergrid.electricity.electricswitch.HvBreakerBlockEntity#tick",
      {"setting": "in-world scroll setting", "setting_unit": "not independently verified"})

for name, subsystem, predicate, value, locator, conditions, unit in [
    ("voltage_gauge", "electricity-gauge", "electrical.gauge.measures", "Difference between two node potentials", "VoltageGaugeBlockEntity#getValue,#buildCircuit", {"polarity": "signed; dial uses magnitude"}, "V"),
    ("current_gauge", "electricity-gauge", "electrical.gauge.measures", "Current through the gauge's series wire", "CurrentGaugeBlockEntity#getValue,#buildCircuit", {"polarity": "signed; dial uses magnitude"}, "A"),
    ("power_gauge", "electricity-gauge", "electrical.gauge.measures", "Series current multiplied by shunt potential difference", "PowerGaugeBlockEntity#getValue,#buildCircuit", {"polarity": "signed; dial uses magnitude"}, "W"),
]:
    claim(subsystem, name + "_measurement", "powergrid:" + name, predicate, value,
          "org.patryk3211.powergrid.electricity.gauge." + locator, conditions, unit)

claim("electricity-gauge", "gauge_redstone_output", "powergrid:voltage_gauge",
      "electrical.gauge.redstone_output",
      "Gauge redstone output is the floored, clamped dial fraction times 15; output saturates at signal 15 even when the visual dial overranges.",
      "org.patryk3211.powergrid.electricity.gauge.GaugeBlockEntity#tick",
      {"applies_to": ["voltage_gauge", "current_gauge", "power_gauge"],
       "visual_dial": "can reach 1.125 of selected full scale"})
claim("electricity-gauge", "energy_meter_accumulation", "powergrid:energy_meter",
      "electrical.energy_meter.accumulation",
      "Per game tick, adds measured current × shunt potential difference × 0.05 divided by 3600 in Wh mode or 3,600,000 in kWh mode; stored display wraps at 100,000 in either direction.",
      "org.patryk3211.powergrid.electricity.gauge.EnergyMeterBlockEntity#tick",
      {"units": "Wh or kWh according to precision mode", "sign": "signed energy can decrease"})
claim("electricity-gauge", "energy_meter_redstone_pulse", "powergrid:energy_meter",
      "electrical.energy_meter.redstone_reporting",
      "On two-tick electrical updates, the meter emits a clamped 0–15 comparator pulse for whole-unit increases and resets the pulse on the next interval.",
      "org.patryk3211.powergrid.electricity.gauge.EnergyMeterBlockEntity#electricalTick",
      {"mode": "comparator pulse; not a continuous 0–15 energy level"})
claim("electricity-redstoneconverter", "redstone_converter_input", "powergrid:redstone_converter",
      "electrical.redstone_converter.input_behavior",
      "The converter normalizes a facing signal to 0–1, clamps invalid values, and combines it with direct redstone unless a peripheral override is active.",
      "org.patryk3211.powergrid.electricity.redstoneconverter.RedstoneConverterBlockEntity#electricalTick",
      {"override": "ComputerCraft setValue/clearValue when the peripheral is available"})
claim("equipment-portablebattery", "portable_low_charge_output", "powergrid:portable_battery",
      "electrical.portable_battery.low_charge_output",
      "Below half charge, available tool power scales as charge fraction divided by 0.5, floored at 0.25; an action without enough charge yields zero power.",
      "org.patryk3211.powergrid.equipment.portablebattery.BatteryUtils#drawEnergy,#tryDrawEnergy",
      {"basis": "worn battery charge fraction", "not_a_voltage_rating": True})
claim("circuits-schematic", "schematic_storage", "powergrid:circuit_schematic",
      "circuit.schematic.storage",
      "The circuit design table serializes a custom schematic into item custom data under the Schematic key.",
      "org.patryk3211.powergrid.circuits.schematic.CircuitSchematic#deserializeNbt;org.patryk3211.powergrid.circuits.editor.CircuitDesignTableBlockEntity#writeToItem",
      {"workflow": "in-world designed circuit, not an ordinary recipe"})
claim("compat-cc", "cc_energy_meter_methods", "powergrid:energy_meter",
      "integration.computercraft.energy_meter_methods",
      ["energy", "getValue", "maxRange"],
      "org.patryk3211.powergrid.compat.cc.gauges.EnergyMeterPeripheral#energy,#getValue,#maxRange",
      {"availability": "registered capability; placed block and connection conditions still apply"})

for subject, subsystem, area, explanation in [
    ("powergrid:storage", "electricity-battery", "battery_ratings", "Ordinary/potato battery specifications and portable capacity rule are in the fresh capture; multiblock capacity was rechecked against the unchanged installed artifact."),
    ("powergrid:generation", "electricity-solarpanel", "solar_reference_settings", "Fresh capture provides reference PV values and maximum assembled panel count with explicit operating conditions."),
    ("powergrid:wiring", "electricity-wire", "wire_registry_ratings", "Fresh capture provides registered wire current, resistance, length, insulation and thermal mass by wire type."),
    ("powergrid:measurement", "electricity-gauge", "core_meter_behavior", "Gauge selectable ranges are runtime captured and core gauge/energy-meter behavior was checked in the installed artifact."),
    ("powergrid:control_protection", "electricity-electricswitch", "switch_fault_thresholds", "LV/MV switch overvoltage thresholds are captured as fault triggers; breaker and fuse conditions were checked in the installed artifact."),
    ("powergrid:circuit_design", "circuits-schematic", "schematic_persistence", "Installed artifact confirms custom schematic serialization in the design-table workflow."),
    ("powergrid:portable_equipment", "equipment-portablebattery", "portable_charge_source", "Configured base tool costs and battery capacity are captured; exact artifact confirms chest-slot source and low-charge behavior."),
    ("powergrid:integrations", "compat-cc", "loaded_cc_display_registration", "The capture records loaded CC peripheral and Create Display Link registrations, including the voltage gauge."),
]:
    add(subsystem, f"{area}_coverage", "coverage", "system", subject,
        area=area, status="verified", explanation=explanation)

for subject, subsystem, explanation in [
    ("powergrid:storage", "electricity-battery", "Charging limits and complete in-world battery safety behavior need targeted verification."),
    ("powergrid:generation", "kinetics-generator", "Generator assembly/rating equations, motor loads and full FE conversion need targeted review; solar reference values are captured."),
    ("powergrid:wiring", "electricity-wire", "Wire overheat, cooling and failure consequences need a complete verified path; effective safety toggles are captured."),
    ("powergrid:measurement", "electricity-gauge", "Core gauge and energy meter semantics are checked; multimeter, thermometer, plotter and display behavior need complete review."),
    ("powergrid:control_protection", "electricity-electricswitch", "LV/MV switch and HV breaker fault triggers are checked; relays and the full protection family still need review."),
    ("powergrid:circuit_design", "circuits-schematic", "Schematic storage is checked; component-to-item mapping and circuit board assembly workflow remain to be captured."),
    ("powergrid:portable_equipment", "equipment-portablebattery", "Base costs and low-charge effect are checked; each boosted tool action path still needs complete review."),
    ("powergrid:integrations", "compat-cc", "Loaded CC/Create registrations are captured, but all per-device usage semantics and other installed cross-mod interactions need review."),
]:
    add(subsystem, f"{subject.split(':')[1]}_remaining", "coverage", "system", subject,
        area="full_gameplay_analysis", status="unresolved", explanation=explanation)

add("circuits-components", "component_mapping_adapter", "adapter_request", "system",
    "powergrid:circuit_design", description="Capture Power Grid component registry IDs and their item/tag mappings as typed relationships; retain conditions and loaded-version provenance.")
add("kinetics-generator", "generator_parameters_adapter", "adapter_request", "system",
    "powergrid:generation", description="Capture effective assembled generator/winding and transformer parameters where the loaded server exposes them; keep dynamic output conditions separate from static ratings.")

findings.sort(key=lambda row: row["finding_id"])
if len({row["finding_id"] for row in findings}) != len(findings):
    raise ValueError("duplicate finding IDs")
OUTPUT.write_text("".join(json.dumps(row, sort_keys=True, separators=(",", ":")) + "\n"
                          for row in findings), encoding="utf-8")
print({"snapshot_id": snapshot_id, "findings": len(findings), "output": str(OUTPUT)})
