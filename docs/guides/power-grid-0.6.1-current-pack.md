# Power Grid 0.6.1 in the current Create: Ch4oS pack

This guide describes the **installed Power Grid 0.6.1** artifact in the current
Create: Ch4oS capture. The stock-v2.1 handbook researched Power Grid 0.5.5.1;
its values and behavior are a separate historical snapshot. The numbers below
come from the effective server capture, while behavior explanations come from
the exact installed JAR. The GDE viewer holds the item pages, recipes, and
evidence for this snapshot.

## Start with the electrical model

Power Grid simulates a connected circuit. A source has an open-circuit output
voltage and internal resistance; a wire adds resistance and heat; a load changes
the current and therefore the voltage measured at its terminals. **A battery's
full-charge output voltage is not a maximum safe input-voltage rating.** The
ordinary battery's voltage and internal resistance change with its stored
charge, and circuit current changes that charge each tick. For a quick
diagnosis, use the voltage gauge across two nodes, the current gauge in series,
and the power gauge for series current times shunt potential difference. A
multimeter probes terminals for voltage or a wire for current, with a captured
five-block probe distance setting and separate 500 V and 50 A warning limits.

Evidence: `powergrid:stage33:battery_soc_model`,
`powergrid:stage33_revalidated:voltage_gauge_measurement`,
`powergrid:stage33_revalidated:current_gauge_measurement`,
`powergrid:stage33_revalidated:power_gauge_measurement`,
`powergrid:stage33:multimeter_probe_modes`.

## Batteries and portable charge

| Device | Effective capacity | Output at empty → full charge | Other effective setting |
| --- | ---: | ---: | --- |
| Ordinary battery, one block | 120 Wh | 11.5 → 12.7 V, open circuit | 90% initial charge; 0.10002488 Ω internal resistance at full charge |
| Potato battery, one block | 0.00006 Wh | 0.5 → 0.9 V, open circuit | Starts full; 452.8996 Ω internal resistance at full charge |
| Portable battery | 20,000 internal charge units | Not a circuit voltage source | +20,000 units per capacity-enchantment level |

Ordinary battery blocks can connect into a multiblock. The source code sets
vertical as the main connection axis, a maximum width of three blocks, and a
maximum height of five. Its controller counts **width × width × height** blocks
and multiplies the single-block capacity by that count. For example, a formed
2 × 2 × 3 battery has 12 blocks and 1,440 Wh of capacity at this pack's
effective 120 Wh per block. This formula says nothing about raising the
open-circuit voltage. The controller also divides its electrical resistance by
the assembly size. An overheat callback can remove attached wires and explode
at a block within the assembly; that conditional failure path does not define
a universal safe charging voltage.

The potato battery has its own tiny capacity and high resistance; do not apply
the ordinary battery's multiblock formula to it. Portable batteries supply the
drill, saw, electro-baton, and electro-zapper. Below half charge, available tool
power scales with charge fraction, floored at 0.25; an action with insufficient
charge yields zero power.

Evidence: `powergrid:source_followup:battery_assembly_shape`,
`powergrid:stage33_revalidated:multiblock_capacity_formula`,
`powergrid:source_followup:battery_overheat_path`,
`powergrid:stage33:potato_soc_model`,
`powergrid:stage33_revalidated:portable_low_charge_output`,
`powergrid:stage33_revalidated:portable_battery_powers_portable_drill`,
`powergrid:stage33_revalidated:portable_battery_powers_portable_saw`,
`powergrid:stage33_revalidated:portable_battery_powers_electrobaton`,
`powergrid:stage33_revalidated:portable_battery_powers_electrozapper`.

## Wires, heat, and grounding

| Conductor | Effective current setting | Maximum span | Resistance per item | Insulated |
| --- | ---: | ---: | ---: | --- |
| Copper wire | 80 A | 24 blocks | 0.0015 Ω | No |
| Insulated copper wire | 70 A | 16 blocks | 0.0015 Ω | Yes |
| Iron wire | 160 A | 64 blocks | 0.005 Ω | No |
| Golden wire | 160 A | 12 blocks | 0.003 Ω | No |
| Copper cord and string-light cord | 60 A | 16 blocks | 0.0015 Ω | Yes |

These are effective per-type settings, not a guarantee that every built
circuit will operate at the listed current. Wire temperature rises with
current squared times resistance, loses heat according to its cooling factor
and temperature above ambient, and changes according to thermal mass. With
wire overheating enabled, two consecutive heating ticks above the default
175°C threshold set the overheated state and visual effects. That inspected
path does not itself delete the wire. Grounding rods establish a ground path
only after enough conductive blocks are counted: this pack uses a minimum of
10 and counts at most 64. The resistance endpoints are 1 Ω and 5,000 Ω.
The rod's separate damage path checks about every ten game ticks and can hurt
nearby entities at modeled rod potential magnitude of at least 48 V.

Evidence: `powergrid:stage33:wire_heat_model`,
`powergrid:stage33:wire_overheat_consequence`,
`powergrid:stage33_revalidated:grounding_path_condition`,
`powergrid:stage33_revalidated:grounding_damage_condition`.

## Generation, conversion, and motion

A generator is an assembly, so its voltage is not a single item rating. The
installed model multiplies rotor speed, field strength, and the effective
winding-coil constant (5.0), with a sign convention. Winding resistance depends
on coil count and parallel winding paths, and its simulated inductance depends
on that resistance. This pack sets the maximum rotor assembly size to eight
blocks and the maximum rotor speed setting to 272 rpm. A large induction rotor
has 128 SU/RPM stress impact; a regular induction rotor and generator clutch
have 32 SU/RPM each. Loaded output still depends on the assembly and load.

The electric motor converts electrical input into Create rotation. Input power
and Create stress determine speed and torque; the dynamic-resistance setting
changes the electrical load model. The solar panel uses an irradiance- and
temperature-dependent I/V curve. Its captured reference open-circuit voltage
is 26.4 V, reference maximum-power voltage 21.12 V and current 3.036 A, with
up to 25 connected panels. Shade, orientation, weather, array size, and load
move the operating point. Those reference values are not a guaranteed
constant output.

A transformer core forms a small transformer when wrenched alone or a medium
transformer from a matching 2 × 2 core arrangement. The resulting circuit uses
primary and secondary turns, core inductance, and coupling. Turn ratio is
useful for design, but does not by itself promise a loaded terminal voltage.
The FE inverter holds up to 20,000 FE; its voltage model depends on stored FE,
the pack's FE-per-volt setting, and a smoothed control throttle derived from
its control capacitor. Read the facing-side FE port and control condition on
its GDE item page before connecting another energy system.

Evidence: `powergrid:stage33:generator_emf_formula`,
`powergrid:stage33:winding_count_resistance`,
`powergrid:stage33:motor_load_model`,
`powergrid:stage33_revalidated:solar_operating_conditions`,
`powergrid:source_followup:core_forms_small_transformer`,
`powergrid:source_followup:core_forms_medium_transformer`,
`powergrid:stage33:transformer_coupling`,
`powergrid:stage33:fe_inverter_output_model`.

## Read a circuit before controlling it

The voltage gauge offers 2, 20, 200, and 2,000 V full-scale ranges. The
current gauge offers 0.02, 0.2, 2, and 20 A; the power gauge offers 20, 200,
2,000, and 20,000 W. Choose a range that keeps the dial useful. The voltage
gauge's redstone signal is the floored, clamped dial fraction times 15, so
signal 15 does not prove the reading is within range. The energy meter
accumulates measured current times its shunt potential difference over game
ticks and can pulse a comparator on whole-unit increases. The thermometer
reports current and peak observed temperature; tooltip warning colors change
at 125, 150, and 175°C. The plotter samples connected wires into a buffer,
with kinetic speed changing sampling. The modular display uses modules to
select and color measurement slots; thermal slots can blank when overheated.

Evidence: `powergrid:stage33_revalidated:gauge_redstone_output`,
`powergrid:stage33_revalidated:energy_meter_accumulation`,
`powergrid:stage33_revalidated:energy_meter_redstone_pulse`,
`powergrid:stage33:thermometer_state`,
`powergrid:stage33:plotter_sampling`,
`powergrid:stage33:modular_display_slots`.

## Switching and protection

Use switches and contactors to separate a control decision from the power
path. The LV and MV switches have effective overvoltage thresholds of 320 V
and 640 V. A contactor builds two switched wire paths; its state can drive a
0/15 comparator signal, and stacked contactors are supported. The fuse holder
blows when a converged simulation has a closed fuse and absolute current
above its scroll setting. `resetFuse` closes an open or blown fuse, while
`removeBlown` changes only blown to open. An enabled HV breaker opens its
switched wire when absolute current exceeds its scroll setting after
simulation convergence; a zero setting disables this trip. The redstone
converter normalizes its facing signal to 0–1 and combines it with direct
redstone unless a peripheral override is active.

Evidence: `powergrid:stage33:contactor_switching`,
`powergrid:stage33_revalidated:fuse_trip_condition`,
`powergrid:stage33_revalidated:fuse_reset_behavior`,
`powergrid:stage33_revalidated:breaker_trip_condition`,
`powergrid:stage33_revalidated:redstone_converter_input`.

## Custom circuits and portable equipment

The circuit design table edits a schematic and writes it to a circuit
schematic item. A circuit board reads that design, determines its required
component items, and builds the described circuit. This pack exposes 26
loaded circuit-component definitions, all mapped to an item or tag in GDE.
The design is item data, so a circuit board is not explained by its ordinary
crafting recipe alone. Begin with the schematic, then use the design table's
component list to gather parts such as resistors, capacitors, diodes,
transistors, relays, and tubes.

Portable tools consume internal charge from the portable battery: 25 units
per drill action, 100 per saw action, 250 per baton action, and 500 per zapper
shot at the effective base settings. An integrated circuit boosts these four
tools. Boosted drill and saw mining doubles charge draw; the saw also doubles
destroy speed. The baton retains its base charge cost but raises its effect
cap and slow duration. The zapper retains its base shot cost, doubles the
projectile power parameter, and launches with a movement vector scaled to four
blocks per tick. On a direct
hit, damage begins at 8 × projectile power and is divided across up to three
targets; power above 0.6 can arc to at most two nearby entities. The weapon
reports a default projectile range of 15 blocks, which is not a hard lifetime
limit. Water destroys the projectile.

Evidence: `powergrid:stage33:design_table_workflow`,
`powergrid:stage33:board_schematic_build`,
`powergrid:stage33:portable_drill_boost_behavior`,
`powergrid:stage33:portable_saw_boost_behavior`,
`powergrid:stage33:electrobaton_boost_behavior`,
`powergrid:stage33:electrozapper_boost_behavior`,
`powergrid:source_followup:zapper_projectile_effect`.

## Installed integrations

The loaded ComputerCraft bridge registers peripherals for the battery,
energy meter, generator clutch, redstone converter, and current, power, and
voltage gauges. The energy meter exposes `energy`, `getValue`, and `maxRange`.
The loaded Simulated bridge registers five sensor sources with the redstone
converter. The loaded Sable bridge substitutes an electric-fan block entity
and tracks ship sublevel transitions. These are installed pack integrations;
optional absent mods are not part of this guide.

Evidence: `powergrid:stage33:cc_registered_devices`,
`powergrid:stage33_revalidated:cc_energy_meter_methods`,
`powergrid:stage33:simulated_sensor_bridge`,
`powergrid:stage33:sable_fan_bridge`.

## Troubleshooting by symptom

| Symptom | First things to inspect |
| --- | --- |
| Battery seems to have less voltage under load | Compare open-circuit and loaded terminal readings; check state of charge, internal resistance, and wire resistance. |
| Larger battery has no higher voltage | Assembly size multiplies capacity and changes controller resistance; it is not a series-voltage rule. |
| Wire is hot or marked overheated | Compare current, length/resistance, cooling factor, and thermal mass; check whether overheating is enabled. |
| Generator reading changes unexpectedly | Check rotor speed, field, winding count, parallel paths, and the connected load. |
| Gauge redstone stays at 15 | Change the gauge range; the redstone output saturates even if the visual dial overranges. |
| Fuse or breaker opens | Compare measured absolute current with its scroll setting and check the device's state/reset path. |
| Portable tool is weak or stops | Check battery charge, available-power reduction below half charge, action cost, and boost state. |

The GDE item pages hold the exact effective configuration, recipes, typed
relationships, and source locators behind these explanations. This guide is a
review artifact for the current snapshot; the handbook repository remains
unchanged pending the Power Grid GDE review gate.
