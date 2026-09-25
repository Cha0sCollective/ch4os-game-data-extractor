# Power Grid 0.6.1 GDE pilot — current Create: Ch4oS capture

This is the reviewed stage-3 dataset for the **current** Create: Ch4oS server, not the handbook stock-v2.1 Power Grid 0.5.5.1 snapshot. The handbook repository has not been changed.

- Capture: `E:\Extractor\captures\stage28-powergrid.zip`; imported DB: `E:\Extractor\captures\stage28-powergrid.sqlite`.
- Knowledge store: `E:\Extractor\captures\gde-knowledge.sqlite`; snapshot `3bf12728f3ed364b769a520d506fe3b4d0be7835adc8109a03aa5a4757181b23`.
- Installed artifact: `powergrid-mc1.21.1-0.6.1.jar`, SHA-256 `b2835c36af6794a963737c617b5f9dd6b41aba5078d418c88847193fbcf702e5`.
- Inventory: **116 items, 77 blocks, 112 accepted recipes**. All 116 item identities have reviewed registry coverage. Eight gameplay-system areas are explicitly unresolved; this is not yet a complete mod guide.
- Research queue: 78 bounded, device-family packets in `E:\Extractor\captures\research\powergrid-stage28`; 132 accepted findings are preserved in `research/powergrid-stage28-findings.jsonl` (116 registry coverage, 8 unresolved system coverage, 8 artifact-backed behavior/relationship records).

## Confirmed ratings and relationships

| Entry | Current snapshot fact | Scope and meaning |
| --- | --- | --- |
| Ordinary battery | 120 Wh; 90% initial charge; 11.5 V empty / 12.7 V full open-circuit output; 0.10002488 Ω full-charge internal resistance | Per placed block, from effective loaded server specification. Assembled ordinary multiblock capacity scales with block count. These voltage values are outputs at charge states, **not safe-input ratings**. |
| Potato battery | 0.00006 Wh; starts full; 0.5 V empty / 0.9 V full; 452.8996 Ω full-charge resistance | Per placed block. No multiblock claim accepted. |
| Portable battery | 20,000 internal charge units base + 20,000 per Create Capacity enchantment level | No Wh conversion or voltage rating claimed. Placed form and capacity rule are linked. |
| Wires | Captured registered current, length, resistance, insulation and thermal mass by wire type | Thermal mass is a simulation parameter without a verified physical unit; failure thresholds remain unresolved. |
| Portable drill / saw / baton / zapper | Base configured action costs of 25 / 100 / 250 / 500 internal charge units | Effective server config; exact artifact review confirms a worn portable battery supplies charge for their relevant actions. Boosted action costs remain to be reviewed. |
| LV button | 10-game-tick pressed timeout | Installed-artifact-derived behavior, not a runtime setting. |
| Fuse holder | Current-based trip condition and distinct reset/removal states | Installed-artifact-derived qualitative behavior. Trip setting unit/range remains unresolved. |

The captured item relationships also expose CC:Tweaked peripherals and Create Display Link registrations. The voltage gauge's CC peripheral appears in this snapshot. A registered capability still depends on its placed-block and connection conditions.

## Source-version boundary

The public upstream `v0.6.1` tag targets Minecraft 1.20.1/Forge. The current 1.21.1 development branch is 0.6.2. Neither checkout is treated as the exact source of the installed NeoForge 1.21.1/0.6.1 JAR. Accepted source-derived findings instead cite methods in the installed artifact and its SHA-256; all other source hypotheses remain unverified. A future exact source match or focused test can upgrade those areas without changing prior snapshots.

## Coverage still unresolved

| System area | Missing guide-grade evidence |
| --- | --- |
| Storage | Charging limits, portable output semantics, and battery safety behavior. |
| Generation | Generator assembly and speed/output formulas; solar-panel operating conditions. |
| Wiring | Overheat thresholds, cooling behavior, and consequences by wire type. |
| Measurement | Meter calibration, units, and redstone reporting behavior. |
| Control and protection | Breaker, switch, relay and fuse ratings and fault conditions. |
| Circuit design | Board workflow and component interaction/rating graph. |
| Portable equipment | Boosted action costs and low-charge output effects. |
| Integrations | Exact usage semantics for all registered CC/Create interfaces; other installed cross-mod links only when pack evidence supports them. |

These statuses appear in the Research view's mod-level coverage. No handbook prose should treat them as settled. TFMG compatibility code is present in the JAR, but TFMG is not loaded in this capture, so it is not a current-pack integration. Petrochem and Create Propulsion are loaded, but no direct Power Grid-specific integration was verified merely from co-installation.

## Verification

The disposable NeoForge 21.1.248 server completed the stage28 export with the Power Grid adapter `ok` (54 mechanics, 9 effective configs, 3 definitions, 5 adapter relations). Manifest hashes verified; import produced 10,980 items and 17,725 accepted recipes. The viewer was checked at `http://127.0.0.1:8766/`: the ordinary battery displays its conditional ratings, artifact-backed multiblock formula, CC/display links, and evidence labels; the portable battery displays its four source-derived tool links. The rejected-recipe resources remain excluded from the accepted recipe table.

## Item inventory

This is the complete loaded Power Grid item registry for the pilot snapshot. Identity coverage does not imply complete gameplay analysis.

| Item ID | Display name |
| --- | --- |
| `powergrid:acid_bucket` | Blazing Acid Bucket |
| `powergrid:alarm_bell` | Alarm Bell |
| `powergrid:barretter_tube` | Barretter Tube |
| `powergrid:basin_heater` | Basin Heater |
| `powergrid:battery` | Battery |
| `powergrid:bjt_npn` | NPN BJT |
| `powergrid:bjt_pnp` | PNP BJT |
| `powergrid:capacitor` | Capacitor |
| `powergrid:carbon_pile_coil` | Carbon Pile Coil |
| `powergrid:ceiling_tile` | Ceiling Tile |
| `powergrid:circuit_board` | Circuit Board |
| `powergrid:circuit_design_table` | Circuit Design Table |
| `powergrid:circuit_schematic` | Circuit Schematic |
| `powergrid:conductive_casing` | Conductive Casing |
| `powergrid:constant_speed_motor` | Constant Speed Motor |
| `powergrid:contactor` | Contactor |
| `powergrid:copper_coil` | Copper Coil |
| `powergrid:copper_cord` | Copper Cord |
| `powergrid:copper_plating` | Copper Plating |
| `powergrid:copper_plating_slab` | Copper Plating Slab |
| `powergrid:copper_plating_stairs` | Copper Plating Stairs |
| `powergrid:cord_junction` | Cord Junction |
| `powergrid:creative_current_source` | Creative Current Source |
| `powergrid:creative_resistor` | Creative Resistor |
| `powergrid:creative_voltage_source` | Creative Voltage Source |
| `powergrid:crt` | Cathode Ray Tube |
| `powergrid:current_gauge` | Current Gauge |
| `powergrid:debug` | Debug |
| `powergrid:device_connector` | Device Connector |
| `powergrid:diode` | Diode |
| `powergrid:display_module` | Display Module |
| `powergrid:electric_fan` | Electric Fan |
| `powergrid:electric_motor` | Electric Motor |
| `powergrid:electric_pump` | Electric Pump |
| `powergrid:electrical_gizmo` | Electrical Gizmo |
| `powergrid:electrobaton` | Electro-Baton |
| `powergrid:electromagnet` | Electromagnet |
| `powergrid:electrozapper` | Electro-Zapper |
| `powergrid:empty_circuit` | Empty Circuit |
| `powergrid:energy_meter` | Energy Meter |
| `powergrid:factory_light` | Factory Light |
| `powergrid:fe_inverter` | FE Inverter |
| `powergrid:fuse_holder` | Fuse Holder |
| `powergrid:generator_clutch` | Generator Clutch |
| `powergrid:generator_commutator` | Generator Commutator |
| `powergrid:generator_housing` | Generator Housing |
| `powergrid:generator_induction_rotor` | Generator Induction Rotor |
| `powergrid:generator_large_induction_rotor` | Generator Large Induction Rotor |
| `powergrid:generator_vertical_commutator` | Vertical Generator Commutator |
| `powergrid:golden_wire` | Golden Wire |
| `powergrid:grounding_rod` | Grounding Rod |
| `powergrid:growth_lamp` | Growth Lamp |
| `powergrid:heating_coil` | Heating Coil |
| `powergrid:heavy_wire_connector` | Heavy Wire Connector |
| `powergrid:hv_breaker` | HV Breaker |
| `powergrid:hv_switch` | HV Switch |
| `powergrid:incomplete_battery` | Incomplete Battery |
| `powergrid:incomplete_bjt_npn` | Incomplete NPN BJT |
| `powergrid:incomplete_bjt_pnp` | Incomplete PNP BJT |
| `powergrid:incomplete_circuit` | Incomplete Circuit |
| `powergrid:incomplete_electrical_gizmo` | Incomplete Electrical Gizmo |
| `powergrid:incomplete_punch_card` | Incomplete Punch Card |
| `powergrid:incomplete_solar_panel` | Incomplete Solar Panel |
| `powergrid:incomplete_transformer_core` | Incomplete Transformer Core |
| `powergrid:incomplete_unetched_circuit` | Incomplete Unetched Circuit |
| `powergrid:insulated_copper_wire` | Insulated Copper Wire |
| `powergrid:integrated_circuit` | Integrated Circuit |
| `powergrid:iron_wire` | Iron Wire |
| `powergrid:light_bulb` | Light Bulb |
| `powergrid:light_fixture` | Light Fixture |
| `powergrid:lv_button` | LV Button |
| `powergrid:lv_light_bulb` | LV Light Bulb |
| `powergrid:lv_switch` | LV Switch |
| `powergrid:magnet` | Magnet |
| `powergrid:modular_display` | Modular Display |
| `powergrid:multimeter` | Multimeter |
| `powergrid:mv_switch` | MV Switch |
| `powergrid:neon_bulb` | Neon Bulb |
| `powergrid:pins` | Pins |
| `powergrid:plotter` | Plotter |
| `powergrid:portable_battery` | Portable Battery |
| `powergrid:portable_battery_placeable` | Portable Battery Placeable |
| `powergrid:portable_drill` | Portable Drill |
| `powergrid:portable_saw` | Portable Saw |
| `powergrid:potato_battery` | Potato Battery |
| `powergrid:potentiometer` | Potentiometer |
| `powergrid:power_gauge` | Power Gauge |
| `powergrid:power_resistor` | Power Resistor |
| `powergrid:punch_card` | Punch Card |
| `powergrid:punch_card_reader` | Punch Card Reader |
| `powergrid:redstone_converter` | Redstone Converter |
| `powergrid:redstone_relay` | Redstone Relay |
| `powergrid:regulator_tube` | Regulator Tube |
| `powergrid:relay` | Relay |
| `powergrid:relay_dpdt` | Double Pole Relay |
| `powergrid:resistive_coil` | Resistive Coil |
| `powergrid:resistor` | Resistor |
| `powergrid:rheostat` | Rheostat |
| `powergrid:servo` | Servo |
| `powergrid:socket` | Socket |
| `powergrid:solar_panel` | Solar Panel |
| `powergrid:solar_panel_bearing` | Solar Panel Bearing |
| `powergrid:spark_gap` | Spark Gap |
| `powergrid:string_light_cord` | String Light Cord |
| `powergrid:thermometer` | Thermometer |
| `powergrid:transformer_core` | Transformer Core |
| `powergrid:unetched_circuit` | Unetched Circuit |
| `powergrid:variac` | Variac |
| `powergrid:varistor` | Varistor |
| `powergrid:vertical_generator_housing` | Vertical Generator Housing |
| `powergrid:vfet` | Static Induction Transistor |
| `powergrid:voltage_gauge` | Voltage Gauge |
| `powergrid:wire` | Copper Wire |
| `powergrid:wire_connector` | Wire Connector |
| `powergrid:wire_cutter` | Wire Cutters |
| `powergrid:zinc_sheet` | Zinc Sheet |
