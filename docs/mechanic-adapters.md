# Mechanic and property adapters

The generic capture always inventories loaded mods, items, blocks, components,
registries, and recipes. Adapters only add mechanic facts; their absence or
failure cannot remove an item or recipe. The current bundled adapters are:

| Adapter | Runtime source | Item-view facts |
| --- | --- | --- |
| Create | `BlockStressValues` and effective config API | Stress impact, capacity, generated RPM on associated blocks |
| Create Deep Seas (`create_submarine`) | `HullStrengthConfig.getFor(defaultBlockState)` | Effective hull max water depth and implosion chance on associated blocks |
| Power Grid | `powergrid:wire_types` registry and effective server equipment config | Wire current, resistance, length, density and insulation; multimeter voltage/current measurement ranges |
| Create: Propulsion | Loaded thruster and Coral fuel managers; effective common config | Fluid/solid fuels, thrust and consumption multipliers, burn times, Coral FE per mB, fuel-to-block links |
| Electro Energetics | Loaded wire and simulated-device registries; effective server config | Wire resistance and insulation ratings, device-to-block links, electrical settings |
| Petrochem | Accepted loaded custom recipes and effective config | Pumpjack, distilling, electrolyzing, engine fuel and turbine fuel specifications; configured stress values |
| Create Diesel Generators | Loaded fuel-type registry, accepted custom recipes, effective config | Engine fuel performance by size, accepted fluids, distillation and other processes |
| CC peripherals | `LuaFunction` annotations in installed integration classes | Lua-visible method names and Java signatures for Propulsion, Electro, Diesel Generators, Pinout, and Power Grid; Power Grid's declared block capability links to its item entries |

Deep Seas' hull values are ratings **when a block is used as a submarine hull**.
Its API applies the installed pack's runtime multipliers. A submarine's actual
limit depends on its weakest hull block; the item's rating is not a promise
that a whole submarine can reach that depth. Implosion may also be disabled in
configuration, which is recorded as a condition. The Power Grid multimeter's
maximum voltage is its *measurement range*, not a maximum safe voltage for
every Power Grid device. Wire types expose a maximum current, but this adapter
does not infer a wire voltage rating that the registry does not provide.

New facts use additive `ch4os-mechanic-v2` rows in `mechanics.jsonl`:

```json
{"format":"ch4os-mechanic-v2","adapter_id":"powergrid","entity_kind":"item","entry_id":"powergrid:multimeter","property_key":"electrical.meter.maximum_voltage","status":"captured_directly","value":500.0,"unit":"V","conditions":{"meaning":"measurement range","configuration":"effective server setting"},"source_api":"org.patryk3211.powergrid.collections.ModdedConfigs.server().equipment.multimeterVoltage.get","subsystem":"electrical","fact_key":"meter.maximum_voltage","value_number":500.0,"registered_value":true,"evidence_status":"installed_runtime_confirmed"}
```

The additive rows retain the older `subsystem`, `fact_key`, `value_number` or
`value_text`, and `evidence_status` fields for existing archive importers.
The SQLite importer accepts both these rows and the earlier Create mechanic
rows. Valid property statuses are `captured_directly`, `derived`, `unavailable`,
`unsupported`, `not_applicable`, and `failed_to_collect`. Unknown values remain
`NULL`, never zero. The viewer shows conditions and source beside each property.
Older capture ZIPs still import, but naturally do not gain facts that were not
captured at runtime. Recapture a pack to populate new adapters.

To add an adapter, implement the public `MechanicAdapter` interface and list
its class in `META-INF/services/dev.chaosarbiter.handbookexporter.MechanicAdapter`
on the runtime classpath. A bundled adapter can also be registered in
`MechanicAdapters`. Return facts and optional effective config rows; report
unsupported or missing data explicitly. The runner records an adapter
diagnostic and continues generic capture when one adapter fails. Keep adapters
read-only: use loaded runtime registries and configuration APIs, and do not
read or modify world state to guess a static item property.

## Structured adapter output

The adapter result also accepts `definitions` and `relations`. The original
three-list constructor remains available. New captures add optional
`adapter-definitions.jsonl` and `adapter-relations.jsonl` files to the v1 archive
manifest; older archives still import with empty corresponding SQLite tables.
`AdapterRows` builds these rows, and `EffectiveDataResources.collect` reads the
effective JSON layer in a named server data directory after datapacks load. It
records the source pack and content hash and reports oversized or unreadable
resources without guessing their contents.

A definition has a stable namespaced `id`, `kind`, structured `attributes`,
conditions, status, and source resource/API information. A relation has typed
subject and object IDs, a predicate, structured attributes, conditions, and a
source. For example, a fuel definition can retain its multipliers, while a
`fuel_for` relation links the fuel to a particular machine with its operating
conditions. Unknown values use an explicit unavailable status; they are never
entered as zero. The importer stores these records in `adapter_definitions` and
`adapter_relations` without pretending every definition is an item property.

The local viewer's **Gameplay data** section browses these definitions by
adapter, with values, conditions, relationships, and provenance. Specialized
recipe definitions are included only when the server recipe manager accepted
their IDs; a rejected JSON resource cannot appear as an active process.

Electro Energetics' `maxInsulationVoltage` is an insulation breakdown rating,
not a universal grid limit. Empty material results on a Petrochem fuel recipe
describe a fuel specification, not a missing item output. The CC catalog reads
installed Lua method annotations but does not place blocks or computers, so it
does not claim that each peripheral can attach in every world state.
For Power Grid, its installed `CCBridge.registerCapabilities` maps seven block
entities to CC peripherals when CC is loaded. These item records gain a
`integration.computercraft.peripheral_available` fact and a relation to the
peripheral API. The Voltage Gauge's Lua methods include `voltage()`,
`getValue()`, `maxRange()`, and `rangePercentage()`.

Adapters may declare several required mod IDs and optional class probes. The
runner skips an absent integration cleanly, records the installed versions of
its required mods with each structured row and diagnostic, and isolates a
failing adapter from the generic inventory. These probes are feature checks,
not hard-coded pack or mod version gates. Config facts should come from loaded
runtime settings via `AdapterRows.config`; a TOML file by itself is not proof
of the value currently in use.
