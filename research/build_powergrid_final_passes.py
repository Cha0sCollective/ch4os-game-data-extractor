"""Build the eight source-led Power Grid gameplay pass findings for stage 33.

Every claim is tied to the exact installed artifact. This script reads no live
server state and does not modify the capture or knowledge database.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
ARTIFACT = Path(r"E:\Extractor\captures\stage22-display-links-runtime\server\mods\powergrid-mc1.21.1-0.6.1.jar")
JOBS = Path(r"E:\Extractor\captures\research\powergrid-stage33")
OUTPUT = ROOT / "research" / "powergrid-final-pass-findings.jsonl"
SHA256 = "b2835c36af6794a963737c617b5f9dd6b41aba5078d418c88847193fbcf702e5"

if hashlib.sha256(ARTIFACT.read_bytes()).hexdigest() != SHA256:
    raise ValueError("installed Power Grid artifact changed")

manifest = json.loads((JOBS / "manifest.json").read_text(encoding="utf-8"))
packets = [json.loads((JOBS / entry["file"]).read_text(encoding="utf-8"))
           for entry in manifest["jobs"]]
jobs = {packet["subsystem"]: packet for packet in packets}
snapshot = packets[0]["snapshot_id"]
findings: list[dict] = []


def add(subsystem: str, suffix: str, record_type: str, subject_kind: str,
        subject_id: str, **fields: object) -> None:
    findings.append({
        "format": "ch4os-research-finding-v1",
        "snapshot_id": snapshot,
        "job_id": jobs[subsystem]["job_id"],
        "finding_id": "powergrid:source_completion:" + suffix,
        "record_type": record_type,
        "subject_kind": subject_kind,
        "subject_id": subject_id,
        **fields,
    })


def evidence(locator: str) -> dict:
    return {"kind": "installed_artifact", "artifact_sha256": SHA256,
            "locator": locator}


def claim(subsystem: str, suffix: str, item: str, predicate: str, value: str,
          locator: str, **conditions: object) -> None:
    add(subsystem, suffix, "claim", "item", item, predicate=predicate, value=value,
        unit=None, conditions=conditions, evidence=evidence(locator))


claim("electricity-battery", "battery_charge_and_heat", "powergrid:battery",
      "electrical.battery.charge_and_heat",
      "The controller computes source voltage and resistance from stored-energy fraction. Converged circuit current changes energy by power × 0.05 per electrical tick, clamped to zero and effective assembled capacity. Internal I²R loss heats the battery; depletion sets source voltage to zero. Thermal failure is conditional on the thermal behavior, not a fixed safe-input voltage.",
      "org.patryk3211.powergrid.electricity.battery.BatteryBlockEntity#updateParameters,#calculatePower,#electricalTick,#specifyThermalBehaviour")

claim("kinetics-generator", "generator_assembly_output", "powergrid:generator_housing",
      "electrical.generator.assembly_output",
      "Generated EMF depends on rotor speed, field strength, and winding-coil constant. The winding collector counts connected coils and parallel paths to set electrical parameters, so winding layout and load alter terminal output; rotor and clutch configuration also govern mechanical operation.",
      "org.patryk3211.powergrid.kinetics.base.GeneratorBlockEntity#emfVoltage,#tick;org.patryk3211.powergrid.kinetics.generator.winding.WindingBlockEntity#collectWindingParts,#calculateElectricalParameters,#buildCircuit",
      output_type="conditional modeled EMF and loaded terminal voltage")

claim("electricity-transformer", "transformer_coil_circuit", "powergrid:transformer_core",
      "electrical.transformer.coil_circuit",
      "The formed transformer has separately configured primary and secondary coils. Its circuit is built from coil turns, resistance, inductance, and core coupling; turn ratio alone does not fix the loaded output voltage.",
      "org.patryk3211.powergrid.electricity.transformer.TransformerBlockEntity#makePrimary,#makeSecondary,#buildCircuit,#getPrimary,#getSecondary",
      applies_to="formed small or medium transformer")

claim("electricity-wire", "wire_cutting", "powergrid:wire_cutter",
      "electrical.wire.cutting",
      "A good cutter removes a wire without the bad-cutter item-loss penalty. Cutting a live wire at or above the effective damage-current threshold harms the player; bad cutters halve that threshold and return only 75% of the wire item count. The current is absolute, so reversing direction does not remove the risk.",
      "org.patryk3211.powergrid.electricity.wire.BaseWireEntity#interact,#cut",
      good_cutter_tag="powergrid:wire_cutters", bad_cutter_tag="powergrid:bad_wire_cutters")

claim("electricity-wire", "wire_entity_contact", "powergrid:wire",
      "electrical.wire.entity_contact",
      "When entity-wire interaction is enabled, uninsulated wire segments touching a living entity add that entity to the circuit. A modeled current at or above the effective entity-damage threshold causes electrocution damage proportional to current divided by the threshold. Spectators are excluded; creative players participate only if that config switch is enabled.",
      "org.patryk3211.powergrid.electricity.wire.WireEntity#tick,#isConnectedTo;org.patryk3211.powergrid.electricity.wire.EntityWireInteraction#wireTouching,#postTick",
      applies_to="uninsulated wires with entity interaction enabled")

claim("electricity-wire", "wire_endpoint_topology", "powergrid:wire",
      "electrical.wire.endpoint_topology",
      "A wire item connects two compatible endpoints and can merge adjacent wire segments. Placed wire entities can split or extend around junction and block endpoints, so the circuit graph follows the resulting segments rather than treating all nearby wires as one conductor.",
      "org.patryk3211.powergrid.electricity.wire.WireItem#connect,#mergeWires,#useOn;org.patryk3211.powergrid.electricity.wire.BlockWireEntity#split,#extend")

claim("kinetics-plotter", "plotter_scale_and_sampling", "powergrid:plotter",
      "electrical.plotter.scale_and_sampling",
      "The plotter offers voltage scales of 2, 20, 200, and 2,000. Its buffer duration changes inversely with absolute kinetic speed, and samples are normalized by the selected scale and clamped to the visible range. It normally records only a converged electrical network; a configuration switch can allow nonconverged samples.",
      "org.patryk3211.powergrid.kinetics.plotter.PlotterBlockEntity#onSpeedChanged,#tick,#resample,<clinit>",
      requires_speed="kinetic speed requirement fulfilled")

claim("electricity-modulardisplay", "display_module_modes", "powergrid:modular_display",
      "electrical.modular_display.module_modes",
      "The display has six module character modes: 0–9, 9–0, 1–0, hexadecimal, symbols, and alphabet. Modules select and color slots; an overheated thermal slot can blank its page.",
      "org.patryk3211.powergrid.electricity.modulardisplay.DisplayModuleType;ModularDisplayBlockEntity#interact,#setColor,#setIndex;DisplaySlotThermal")

claim("electricity-electricswitch", "hv_switch_arcing", "powergrid:hv_switch",
      "electrical.switch.arc_conditions",
      "The high-voltage switch moves a rod using kinetic input. Its spark-extinguishing speed depends on switched-wire current and a configured factor, while spark potential depends on rod position and another factor. With insufficient speed, the switch may arc according to potential difference; it has no one fixed safe switching voltage.",
      "org.patryk3211.powergrid.electricity.electricswitch.HvSwitchBlockEntity#extinguishRPM,#sparkPotential,#tick,#getResistance,#buildCircuit")

claim("circuits-components", "relay_contact_model", "powergrid:relay",
      "circuit.relay.contact_model",
      "A relay component derives its voltage and current thresholds from the schematic and uses the configured holding-current percentage. Its coil drives two switched contacts; the double relay variant drives four contacts. Contact state is synchronized after circuit ticks.",
      "org.patryk3211.powergrid.circuits.components.RelayComponent#bake,#tick;DoubleRelayComponent#bake",
      applies_to="schematic relay components")

claim("circuits-components", "redstone_relay_logic", "powergrid:redstone_relay",
      "circuit.redstone_relay.logic",
      "The redstone relay component makes a switched electrical path. Any received redstone signal above zero powers it; zero unpowers it, and the switched-wire state follows that input.",
      "org.patryk3211.powergrid.circuits.components.RedstoneRelayComponent#bake,#receiveRedstone",
      applies_to="schematic redstone relay component")

claim("circuits-circuitboard", "board_runtime_and_cooling", "powergrid:circuit_board",
      "circuit.board.runtime_and_cooling",
      "The board bakes schematic pads, nodes, wires, and components into an electrical circuit. Its server tick advances thermal units and ticked components; board cooling multipliers affect thermal behavior. Neighbor processing and edge connections allow configured adjacent-board links.",
      "org.patryk3211.powergrid.circuits.circuitboard.BakedCircuit#from,#tick;CircuitBoardBlockEntity#bakeCircuit,#edgeConnect,#processNeighbor,#addCoolingMultiplier,#removeCoolingMultiplier")

claim("equipment-portablebattery", "portable_chest_supply_corrected", "powergrid:portable_battery",
      "electrical.portable_battery.chest_supply",
      "Portable-tool energy draw looks for a portable battery in the chest equipment slot. If stored charge is less than the action cost, the call removes the charge component and returns zero; otherwise it deducts the full cost. Available-power factor is one above half charge, then falls with remaining charge to a floor of 0.25. Creative instabuild bypasses charge draw.",
      "org.patryk3211.powergrid.equipment.portablebattery.BatteryUtils#drawEnergy,#tryDrawEnergy",
      applies_to="player-held tools using BatteryUtils")

claim("compat-cc", "cc_battery_methods", "powergrid:battery",
      "integration.computercraft.battery_methods",
      "The ComputerCraft battery peripheral exposes capacity, energy, chargePercentage, and powerDraw. It binds to the battery controller, so a formed multiblock reports controller values rather than an isolated block's single-block capacity.",
      "org.patryk3211.powergrid.compat.cc.battery.BatteryPeripheral#capacity,#energy,#chargePercentage,#powerDraw;MultiBlockBatteryEntity#getControllerBE")

claim("compat-cc", "cc_gauge_methods", "powergrid:voltage_gauge",
      "integration.computercraft.gauge_methods",
      "ComputerCraft gauge peripherals expose measured quantities as voltage, current, or power methods on the corresponding gauge. The voltage gauge provides voltage; the other registered gauge types provide current and power respectively.",
      "org.patryk3211.powergrid.compat.cc.gauges.VoltageGaugePeripheral#voltage;CurrentGaugePeripheral#current;PowerGaugePeripheral#power")

claim("compat-cc", "cc_clutch_methods", "powergrid:generator_clutch",
      "integration.computercraft.clutch_methods",
      "The ComputerCraft generator-clutch peripheral exposes mode, load, and rpm. It reports zero rpm when no rotor behavior is attached.",
      "org.patryk3211.powergrid.compat.cc.clutch.GeneratorClutchPeripheral#mode,#load,#rpm")

claim("compat-cc", "cc_converter_override", "powergrid:redstone_converter",
      "integration.computercraft.converter_override",
      "The ComputerCraft converter peripheral offers setValue and clearValue. setValue installs a signal override; clearValue removes it, allowing the converter's ordinary redstone input path to resume.",
      "org.patryk3211.powergrid.compat.cc.redstone.RedstoneConverterPeripheral#setValue,#clearValue;org.patryk3211.powergrid.electricity.redstoneconverter.RedstoneConverterBlockEntity#electricalTick")

claim("electricity-basinheater", "basin_heater_heat_levels", "powergrid:basin_heater",
      "electrical.heater.create_heat_levels",
      "Electrical loss heats the basin heater. Its source maps temperature below 300°C to no Create heat, 300–599°C to fading, 600–1199°C to kindled, and 1200°C or above to seething. These are operating-state thresholds, not an input-voltage rating.",
      "org.patryk3211.powergrid.electricity.basinheater.BasinHeaterBlockEntity#electricalTick,#setState,#boilerHeater")

claim("electricity-heater", "heating_coil_states", "powergrid:heating_coil",
      "electrical.heater.temperature_states",
      "The heating coil applies electrical power as heat. Below 200°C it is cold; from 200°C to below 400°C it smokes; at 400°C or above it blasts. Its state follows modeled temperature, not a fixed voltage threshold.",
      "org.patryk3211.powergrid.electricity.heater.HeaterBlockEntity#electricalTick,#tick,#specifyThermalBehaviour")

claim("electricity-fan", "electric_fan_current_speed", "powergrid:electric_fan",
      "electrical.fan.current_speed",
      "The electric fan uses Create airflow. Its modeled speed is wire current × 64, limited to ±256; magnitude below one produces zero speed. Current sign reverses the airflow direction, and a speed change rebuilds its air-current behavior.",
      "org.patryk3211.powergrid.electricity.fan.ElectricFanBlockEntity#getSpeed,#getAirFlowDirection,#tick,#onSpeedChanged")

claim("electricity-pump", "electric_pump_power_speed", "powergrid:electric_pump",
      "electrical.pump.power_speed",
      "The electric pump derives its speed from simulated pump-element power multiplied by the effective pump-power factor, capped by the effective maximum-speed setting. A speed change updates pressure in connected Create fluid pipes; the pump range is separately configured.",
      "org.patryk3211.powergrid.electricity.pump.ElectricPumpBlockEntity#getSpeed,#getRange,#tick,#updatePressureChange")

claim("electricity-electromagnet", "electromagnet_processing", "powergrid:electromagnet",
      "electrical.electromagnet.processing",
      "The electromagnet uses a powered coil and a magnetizing behavior. When that behavior runs, the simulated coil resistance is halved. It looks up magnetizing recipes for items and can process items on a Create belt or as world item entities.",
      "org.patryk3211.powergrid.electricity.electromagnet.ElectromagnetBlockEntity#tick,#getRecipe,#tryProcessOnBelt,#tryProcessInWorld,#onMagnetizationComplete")

claim("electricity-bell", "alarm_bell_current_audio", "powergrid:alarm_bell",
      "electrical.alarm_bell.current_audio",
      "The bell's audio responds to absolute circuit current. Below 0.25 A its volume is zero; above that, volume equals twice the current magnitude. Its pitch also varies with current and is capped by its source calculation.",
      "org.patryk3211.powergrid.electricity.bell.AlarmBellBlockEntity#getVolume,#getPitch,#electricalTick")

claim("electricity-crt", "crt_electrical_display", "powergrid:crt",
      "electrical.crt.display_inputs",
      "The CRT has separate X and Y deflection sampling paths, heater current, grid-to-cathode potential, and anode-to-cathode potential. Its trace depends on those electrical inputs; a heater current below 0.8 A suppresses its modeled brightness factor.",
      "org.patryk3211.powergrid.electricity.crt.CRTBlockEntity#buildCircuit,#electricalTick,#tick")

claim("electricity-sparkgap", "spark_gap_switching", "powergrid:spark_gap",
      "electrical.spark_gap.switching",
      "The open plasma channel closes when absolute potential difference exceeds its configured voltage setting. Once closed, it opens when absolute current falls below the corresponding current setting. The two settings create a voltage ignition and current-extinction behavior.",
      "org.patryk3211.powergrid.electricity.sparkgap.SparkGapBlockEntity#electricalTick,#buildCircuit")

claim("kinetics-rheostat", "rheostat_resistance_split", "powergrid:rheostat",
      "electrical.rheostat.resistance_split",
      "The three-terminal rheostat divides its selected total resistance into two complementary paths according to its arm ratio. The source bounds that ratio between 0.01 and 0.99, avoiding a zero-resistance end segment.",
      "org.patryk3211.powergrid.kinetics.rheostat.RheostatBlockEntity#getRatio,#buildCircuit,#refreshParameters")

claim("kinetics-variac", "variac_adjustable_coupling", "powergrid:variac",
      "electrical.variac.adjustable_coupling",
      "The variac is a three-terminal variable transformer. Its arm ratio changes the effective turns and coupled electrical parameters; the source keeps the ratio above zero. Output remains dependent on circuit loading and core coupling.",
      "org.patryk3211.powergrid.kinetics.variac.VariacBlockEntity#getRatio,#buildCircuit,#refreshParameters,#tick")

claim("kinetics-servo", "servo_power_and_target", "powergrid:servo",
      "electrical.servo.power_and_target",
      "The servo uses coil power and torque to determine available movement speed. A separate control-wire potential maps to a target angle and is clamped to ±360 degrees; the target and generated speed are dynamic circuit results.",
      "org.patryk3211.powergrid.kinetics.servo.ServoBlockEntity#torque,#tick,#applyNewSpeed")

claim("kinetics-punchcard", "punch_card_reader_outputs", "powergrid:punch_card_reader",
      "electrical.punch_card_reader.outputs",
      "The reader advances the inserted punch card with kinetic motion. It builds eight switched electrical paths, changes their states as card position changes, and also exposes a redstone output derived from the current card position.",
      "org.patryk3211.powergrid.kinetics.punchcard.PunchCardReaderBlockEntity#currentItem,#electricalTick,#tick,#getRedstoneOutput,#buildCircuit")

claim("electricity-light", "bulb_fixture_failure", "powergrid:light_fixture",
      "electrical.light.bulb_fixture",
      "A light fixture uses its installed bulb's resistance and burned state for the switched filament path. Removing the bulb or burning it out opens that path; the bulb's state also determines light level and special effects. Factory lights use a shared filament across connected parts.",
      "org.patryk3211.powergrid.electricity.light.fixture.AbstractLightFixtureBlockEntity#lightBulbChanged,#electricalTick;org.patryk3211.powergrid.electricity.light.bulb.LightBulbState#tick,#getPowerLevel;org.patryk3211.powergrid.electricity.light.factorylight.FactoryLightBlockEntity#tick,#buildCircuit")

claim("electricity-carbonpile", "carbon_pile_variable_resistance", "powergrid:carbon_pile_coil",
      "electrical.carbon_pile.variable_resistance",
      "A carbon-pile coil takes its base resistance from the pile arrangement above it, then multiplies by trim and a coil-pull-dependent gain. The path opens when the resulting resistance is nonpositive. Dissipated pile-wire power heats the pile blocks.",
      "org.patryk3211.powergrid.electricity.carbonpile.CarbonPileCoilBlockEntity#pileChanged,#refreshResistance,#gain;CarbonPileBlockEntity#tick")

for subsystem, suffix, subject, predicate, target, locator in [
    ("electricity-basinheater", "basin_heater_create_heat", "powergrid:basin_heater", "provides_heat_to", "create:blaze_burner_heat", "org.patryk3211.powergrid.electricity.basinheater.BasinHeaterBlockEntity#setState,#boilerHeater"),
    ("electricity-fan", "electric_fan_create_airflow", "powergrid:electric_fan", "drives", "create:air_current", "org.patryk3211.powergrid.electricity.fan.ElectricFanBlockEntity#getAirCurrent,#getSpeed,#tick"),
    ("electricity-pump", "electric_pump_create_fluid", "powergrid:electric_pump", "pressurizes", "create:fluid_transport", "org.patryk3211.powergrid.electricity.pump.ElectricPumpBlockEntity#updatePressureChange,#updatePipeNetwork"),
    ("electricity-electromagnet", "electromagnet_create_belt", "powergrid:electromagnet", "processes_on", "create:belt_transport", "org.patryk3211.powergrid.electricity.electromagnet.ElectromagnetBlockEntity#tryProcessOnBelt"),
]:
    add(subsystem, suffix, "relation", "item", subject, predicate=predicate,
        object_kind="interface", object_id=target, conditions={}, evidence=evidence(locator))

add("kinetics-punchcard", "reader_reads_punch_card", "relation", "item",
    "powergrid:punch_card_reader", predicate="reads", object_kind="item",
    object_id="powergrid:punch_card", conditions={},
    evidence=evidence("org.patryk3211.powergrid.kinetics.punchcard.PunchCardReaderBlockEntity#insertCard,#currentItem,#electricalTick"))

# A completed pass means the installed-version source path and captured effective
# settings needed for a player-facing explanation have been reviewed. It does
# not imply every possible player-built circuit has one fixed output value.
for system, subsystem, explanation in [
    ("storage", "electricity-battery", "Ordinary, potato, and portable battery capacities and charge behavior are captured; ordinary multiblock geometry, resistance, charge update, heat, and failure paths are source reviewed. Outputs remain conditional on charge and circuit load."),
    ("generation", "kinetics-generator", "Generator EMF and winding assembly, motor load, solar operating curve, transformer coil coupling and core formation, FE conversion, and major powered Create devices are source reviewed with effective pack settings. Loaded output remains conditional on assembly and load."),
    ("wiring", "electricity-wire", "All captured wire types have effective ratings; endpoint topology, cutting, uninsulated entity contact, grounding, thermal response, and conditional failure paths are source reviewed."),
    ("measurement", "kinetics-plotter", "Gauge ranges and redstone scaling, energy meter, multimeter, thermometer, plotter speed/convergence/scale, CRT electrical inputs, and modular display modes are source reviewed."),
    ("control_protection", "electricity-electricswitch", "LV/MV switch thresholds, contactor, fuse and breaker state transitions, high-voltage switch arcing, relay contacts, redstone relay, spark gap, rheostat, variac, servo, punch-card reader, carbon pile, and converter control paths are source reviewed."),
    ("circuit_design", "circuits-circuitboard", "The design-table schematic, all 26 loaded component mappings, board assembly, baked-circuit ticking, edge connections, and thermal cooling are source reviewed."),
    ("portable_equipment", "equipment-portablebattery", "Portable battery chest-slot supply, low-charge factor, action costs, all four tool boost paths, and zapper projectile behavior are source reviewed."),
    ("integrations", "compat-cc", "Only installed ComputerCraft, Create, Simulated, and Sable bridges are included. Registered peripherals and per-device methods, plus bridge behavior, are source reviewed."),
    ("loads_and_actuators", "electricity", "The installed basin heater, heating coil, fan, pump, electromagnet, alarm bell, light fixtures, CRT, carbon pile, rheostat, variac, servo, punch-card reader, and spark gap have source-backed operating summaries and item-page evidence."),
]:
    add(subsystem, system + "_full_pass", "coverage", "system", "powergrid:" + system,
        area="full_gameplay_analysis", status="verified", explanation=explanation)

findings.sort(key=lambda finding: finding["finding_id"])
OUTPUT.write_text("".join(json.dumps(finding, sort_keys=True, separators=(",", ":")) + "\n"
                          for finding in findings), encoding="utf-8")
print({"snapshot_id": snapshot, "findings": len(findings), "output": str(OUTPUT)})
