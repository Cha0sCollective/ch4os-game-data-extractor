package dev.chaosarbiter.handbookexporter;

import net.minecraft.core.Registry;
import net.minecraft.core.registries.BuiltInRegistries;
import net.minecraft.resources.ResourceLocation;
import net.minecraft.server.MinecraftServer;
import net.minecraft.world.level.block.Block;

import java.lang.reflect.Field;
import java.util.ArrayList;
import java.util.Comparator;
import java.util.List;
import java.util.Map;
import java.util.function.Predicate;

/** Captures loaded Power Grid specifications without a Power Grid build dependency. */
final class PowerGridMechanicAdapter implements MechanicAdapter {
    private static final String CONFIG_CLASS = "org.patryk3211.powergrid.collections.ModdedConfigs";
    private static final String WIRE_ENTRY = "org.patryk3211.powergrid.electricity.wire.registry.WireItemEntry";
    private static final String BATTERY_BLOCK = "org.patryk3211.powergrid.electricity.battery.AbstractBatteryBlock";
    private static final String BATTERY_SPEC = "org.patryk3211.powergrid.electricity.battery.BatterySpec";
    private static final String PORTABLE_BATTERY_BLOCK = "org.patryk3211.powergrid.equipment.portablebattery.PortableBatteryBlock";
    private static final String BATTERY_UTILS = "org.patryk3211.powergrid.equipment.portablebattery.BatteryUtils";
    private static final ResourceLocation WIRE_REGISTRY = ResourceLocation.parse("powergrid:wire_types");

    @Override
    public String id() {
        return "powergrid";
    }

    @Override
    public String requiredModId() {
        return "powergrid";
    }

    @Override
    public Result collect(MinecraftServer server, Predicate<ResourceLocation> inScope) {
        try {
            Registry<?> wires = server.registryAccess().registries()
                    .filter(entry -> entry.key().location().equals(WIRE_REGISTRY))
                    .map(entry -> entry.value()).findFirst()
                    .orElseThrow(() -> new IllegalStateException("Power Grid wire registry not found"));
            List<Map<String, ?>> facts = new ArrayList<>();
            List<Map<String, ?>> configsOut = new ArrayList<>();
            List<Map<String, ?>> definitions = new ArrayList<>();
            List<Map<String, ?>> relations = new ArrayList<>();
            List<Map<String, ?>> diagnostics = new ArrayList<>();
            wires.entrySet().stream()
                    .sorted(Map.Entry.comparingByKey(Comparator.comparing(key -> key.location().toString())))
                    .forEach(entry -> {
                        ResourceLocation itemId = entry.getKey().location();
                        if (!inScope.test(itemId) || !BuiltInRegistries.ITEM.containsKey(itemId)) {
                            return;
                        }
                        Object wire = entry.getValue();
                        try {
                            addWire(facts, itemId, wire, "maximumCurrent", "maximum_current", "A");
                            addWire(facts, itemId, wire, "resistancePerItem", "resistance_per_item", "ohm/item");
                            addWire(facts, itemId, wire, "maximumLength", "maximum_length", "blocks");
                            addWire(facts, itemId, wire, "itemsPerMeter", "items_per_meter", "items/block");
                            addWire(facts, itemId, wire, "thermalMass", "thermal_mass", null);
                            addWire(facts, itemId, wire, "insulated", "insulated", null);
                        } catch (ReflectiveOperationException exception) {
                            throw new IllegalStateException("Power Grid wire lookup failed for " + itemId, exception);
                        }
                    });

            ResourceLocation multimeter = ResourceLocation.parse("powergrid:multimeter");
            if (inScope.test(multimeter) && BuiltInRegistries.ITEM.containsKey(multimeter)) {
                Class<?> configs = Class.forName(CONFIG_CLASS);
                Object root = configs.getMethod("server").invoke(null);
                Object equipment = field(root, "equipment");
                addEquipment(facts, multimeter, equipment, "multimeterVoltage", "maximum_voltage", "V");
                addEquipment(facts, multimeter, equipment, "multimeterCurrent", "maximum_current", "A");
            }
            try {
                addBatteries(facts, configsOut, definitions, relations, inScope);
            } catch (ReflectiveOperationException | LinkageError | RuntimeException exception) {
                diagnostics.add(Map.of("subsystem", "mechanic_adapter:powergrid:batteries",
                        "status", "partial", "error_class", exception.getClass().getName(),
                        "error_message", String.valueOf(exception.getMessage()),
                        "row_count", 0));
            }
            try {
                addPortableToolUses(facts, configsOut, inScope);
            } catch (ReflectiveOperationException | LinkageError | RuntimeException exception) {
                diagnostics.add(Map.of("subsystem", "mechanic_adapter:powergrid:portable_tools",
                        "status", "partial", "error_class", exception.getClass().getName(),
                        "error_message", String.valueOf(exception.getMessage()),
                        "row_count", 0));
            }
            return new Result(facts, configsOut, definitions, relations, diagnostics);
        } catch (ReflectiveOperationException exception) {
            throw new IllegalStateException("Power Grid runtime API unavailable", exception);
        }
    }

    private void addBatteries(List<Map<String, ?>> facts, List<Map<String, ?>> configsOut,
                              List<Map<String, ?>> definitions, List<Map<String, ?>> relations,
                              Predicate<ResourceLocation> inScope) throws ReflectiveOperationException {
        Class<?> batteryClass = Class.forName(BATTERY_BLOCK);
        Class<?> specClass = Class.forName(BATTERY_SPEC);
        for (String name : List.of("battery", "potato_battery")) {
            ResourceLocation id = ResourceLocation.parse("powergrid:" + name);
            if (!inScope.test(id) || !BuiltInRegistries.ITEM.containsKey(id)
                    || !BuiltInRegistries.BLOCK.containsKey(id)) {
                continue;
            }
            Block block = BuiltInRegistries.BLOCK.get(id);
            if (!batteryClass.isInstance(block)) {
                continue;
            }
            Object spec = block.getClass().getMethod("getSpec").invoke(block);
            if (!specClass.isInstance(spec)) {
                throw new IllegalStateException("Power Grid battery has an unknown specification type: " + id);
            }
            double capacityInternal = decimal((Number) specClass.getMethod("getMaxCharge").invoke(spec));
            double initialInternal = decimal((Number) specClass.getMethod("getInitialCharge").invoke(spec));
            double emptyVoltage = decimal((Number) specClass.getMethod("calculateVoltage", float.class).invoke(spec, 0f));
            double fullVoltage = decimal((Number) specClass.getMethod("calculateVoltage", float.class).invoke(spec, 1f));
            double fullResistance = decimal((Number) specClass.getMethod("calculateResistance", float.class).invoke(spec, 1f));
            if (capacityInternal <= 0 || !Double.isFinite(initialInternal) || !Double.isFinite(fullVoltage)
                    || !Double.isFinite(emptyVoltage) || !Double.isFinite(fullResistance)) {
                throw new IllegalStateException("Power Grid battery specification is not finite: " + id);
            }
            String source = BATTERY_BLOCK + ".getSpec/" + BATTERY_SPEC;
            Map<String, Object> singleBlock = name.equals("battery")
                    ? Map.of("basis", "one placed battery block", "state", "effective loaded server configuration",
                            "multiblock", "assembled capacity scales with battery count; this is not an assembly rating")
                    : Map.of("basis", "one placed potato battery block", "state", "loaded specification");
            facts.add(derivedFact(id, "electrical.battery.single_block_capacity", capacityInternal / 3600d,
                    "Wh", singleBlock, source + ".getMaxCharge / 3600"));
            facts.add(derivedFact(id, "electrical.battery.initial_charge_fraction", initialInternal / capacityInternal,
                    "fraction", Map.of("basis", "new block default"), source + ".getInitialCharge/getMaxCharge"));
            facts.add(MechanicRows.fact(id(), "item", id.toString(), "electrical.battery.output_voltage_full_charge",
                    fullVoltage, "V", Map.of("state_of_charge", 1,
                            "meaning", "open-circuit output at full charge, not a maximum safe input voltage"),
                    source + ".calculateVoltage(1)"));
            facts.add(MechanicRows.fact(id(), "item", id.toString(), "electrical.battery.output_voltage_empty_charge",
                    emptyVoltage, "V", Map.of("state_of_charge", 0,
                            "meaning", "open-circuit output at empty charge"), source + ".calculateVoltage(0)"));
            facts.add(MechanicRows.fact(id(), "item", id.toString(), "electrical.battery.internal_resistance_full_charge",
                    fullResistance, "ohm", Map.of("state_of_charge", 1),
                    source + ".calculateResistance(1)"));
            String definitionId = "powergrid:" + name + "_spec";
            definitions.add(AdapterRows.definition(id(), "battery_spec", definitionId,
                    Map.of("single_block_capacity_wh", capacityInternal / 3600d,
                            "initial_charge_fraction", initialInternal / capacityInternal,
                            "output_voltage_at_empty_charge_v", emptyVoltage,
                            "output_voltage_at_full_charge_v", fullVoltage,
                            "internal_resistance_at_full_charge_ohm", fullResistance),
                    singleBlock, null, null, null, source));
            relations.add(AdapterRows.relation(id(), "item", id.toString(), "has_battery_spec",
                    "battery_spec", definitionId, Map.of(), singleBlock, source));
        }
        addPortableBattery(facts, configsOut, definitions, relations, inScope);
        ResourceLocation acid = ResourceLocation.parse("powergrid:battery");
        if (inScope.test(acid) && BuiltInRegistries.ITEM.containsKey(acid)) {
            Object electricity = field(Class.forName(CONFIG_CLASS).getMethod("server").invoke(null), "electricity");
            addConfig(configsOut, "electricity", electricity, "acidBatteryCapacity", "Wh");
            addConfig(configsOut, "electricity", electricity, "acidBatteryInitialCharge", "fraction");
            addConfig(configsOut, "electricity", electricity, "acidBatteryFullChargeInternalResistance", "ohm");
        }
    }

    private void addPortableBattery(List<Map<String, ?>> facts, List<Map<String, ?>> configsOut,
                                    List<Map<String, ?>> definitions, List<Map<String, ?>> relations,
                                    Predicate<ResourceLocation> inScope) throws ReflectiveOperationException {
        ResourceLocation blockId = ResourceLocation.parse("powergrid:portable_battery");
        ResourceLocation itemId = ResourceLocation.parse("powergrid:portable_battery");
        if (!inScope.test(itemId) || !BuiltInRegistries.ITEM.containsKey(itemId)
                || !BuiltInRegistries.BLOCK.containsKey(blockId)) {
            return;
        }
        Block block = BuiltInRegistries.BLOCK.get(blockId);
        if (!Class.forName(PORTABLE_BATTERY_BLOCK).isInstance(block)) {
            return;
        }
        Object root = Class.forName(CONFIG_CLASS).getMethod("server").invoke(null);
        Object equipment = field(root, "equipment");
        int base = ((Number) MechanicRows.call(field(equipment, "portableBatteryBaseCapacity"), "get")).intValue();
        int perLevel = ((Number) MechanicRows.call(field(equipment, "portableBatteryEnchantCapacity"), "get")).intValue();
        int blockBase = ((Number) MechanicRows.call(block, "capacity")).intValue();
        int utilityBase = ((Number) Class.forName(BATTERY_UTILS).getMethod("getMaxCharge", int.class).invoke(null, 0)).intValue();
        if (base != blockBase || base != utilityBase) {
            throw new IllegalStateException("Portable Battery capacity APIs disagree");
        }
        addConfig(configsOut, "equipment", equipment, "portableBatteryBaseCapacity", "internal charge units");
        addConfig(configsOut, "equipment", equipment, "portableBatteryEnchantCapacity", "internal charge units/level");
        Map<String, Object> baseConditions = Map.of("capacity_enchantment_level", 0,
                "meaning", "base internal charge capacity; enchanted stacks and placed blocks can hold more");
        facts.add(MechanicRows.fact(id(), "item", itemId.toString(), "electrical.portable_battery.base_capacity",
                base, "internal charge units", baseConditions, PORTABLE_BATTERY_BLOCK + ".capacity"));
        facts.add(MechanicRows.fact(id(), "item", itemId.toString(), "electrical.portable_battery.capacity_per_enchantment_level",
                perLevel, "internal charge units/level", Map.of("enchantment", "create:capacity"),
                BATTERY_UTILS + ".getMaxCharge(int)"));
        String definitionId = "powergrid:portable_battery_capacity";
        definitions.add(AdapterRows.definition(id(), "battery_capacity_rule", definitionId,
                Map.of("base", base, "per_capacity_enchantment_level", perLevel,
                        "expression", "base + per_capacity_enchantment_level * level",
                        "unit", "internal charge units"),
                Map.of("enchantment", "create:capacity", "state", "effective server configuration"),
                null, null, null, BATTERY_UTILS + ".getMaxCharge(int)"));
        relations.add(AdapterRows.relation(id(), "item", itemId.toString(), "uses_capacity_rule",
                "battery_capacity_rule", definitionId, Map.of(), Map.of(), BATTERY_UTILS + ".getMaxCharge(int)"));
        relations.add(AdapterRows.relation(id(), "item", itemId.toString(), "places_as",
                "block", blockId.toString(), Map.of(), Map.of("usage", "placed portable battery"),
                "PortableBatteryItem.getBlock"));
        ResourceLocation placeable = ResourceLocation.parse("powergrid:portable_battery_placeable");
        if (BuiltInRegistries.ITEM.containsKey(placeable) && inScope.test(placeable)) {
            relations.add(AdapterRows.relation(id(), "item", placeable.toString(), "places_as",
                    "block", blockId.toString(), Map.of(), Map.of(), "PortableBatteryBlock"));
        }
    }

    private void addPortableToolUses(List<Map<String, ?>> facts, List<Map<String, ?>> configsOut,
                                     Predicate<ResourceLocation> inScope)
            throws ReflectiveOperationException {
        ResourceLocation battery = ResourceLocation.parse("powergrid:portable_battery");
        if (!inScope.test(battery) || !BuiltInRegistries.ITEM.containsKey(battery)) {
            return;
        }
        Object equipment = field(Class.forName(CONFIG_CLASS).getMethod("server").invoke(null), "equipment");
        String[][] tools = {
                {"portable_drill", "drillEnergyPerUse", "mining"},
                {"portable_saw", "sawEnergyPerUse", "mining"},
                {"electrobaton", "electroBatonEnergyPerUse", "hit"},
                {"electrozapper", "electroZapperEnergyPerShot", "shot"}
        };
        for (String[] tool : tools) {
            ResourceLocation toolId = ResourceLocation.parse("powergrid:" + tool[0]);
            if (!inScope.test(toolId) || !BuiltInRegistries.ITEM.containsKey(toolId)) {
                continue;
            }
            int configuredCost = ((Number) MechanicRows.call(field(equipment, tool[1]), "get")).intValue();
            if (configuredCost < 0) {
                throw new IllegalStateException("Portable tool charge cost is negative: " + toolId);
            }
            addConfig(configsOut, "equipment", equipment, tool[1], "internal charge units/action");
            Map<String, Object> conditions = Map.of("action", tool[2],
                    "value", "configured base cost; power-source relationship requires artifact review");
            facts.add(MechanicRows.fact(id(), "item", toolId.toString(), "electrical.portable_tool.base_charge_cost",
                    configuredCost, "internal charge units/action", conditions,
                    CONFIG_CLASS + ".server().equipment." + tool[1] + ".get"));
        }
    }

    private void addConfig(List<Map<String, ?>> configs, String section, Object group,
                           String fieldName, String unit) throws ReflectiveOperationException {
        Object setting = field(group, fieldName);
        configs.add(AdapterRows.config(id(), "powergrid", "server", "powergrid.server." + section,
                fieldName, MechanicRows.call(setting, "get"), unit,
                CONFIG_CLASS + ".server()." + section + "." + fieldName + ".get"));
    }

    private Map<String, Object> derivedFact(ResourceLocation itemId, String key, double value, String unit,
                                            Map<String, ?> conditions, String source) {
        Map<String, Object> fact = MechanicRows.fact(id(), "item", itemId.toString(), key,
                value, unit, conditions, source);
        fact.put("status", "derived");
        fact.put("evidence_status", "installed_runtime_derived");
        return fact;
    }

    private double decimal(Number value) {
        return Double.parseDouble(Float.toString(value.floatValue()));
    }

    private void addWire(List<Map<String, ?>> facts, ResourceLocation itemId, Object wire,
                         String method, String key, String unit) throws ReflectiveOperationException {
        facts.add(MechanicRows.fact(id(), "item", itemId.toString(), "electrical.wire." + key,
                MechanicRows.call(wire, method), unit,
                Map.of("basis", "registered wire type"), WIRE_ENTRY + "." + method));
    }

    private void addEquipment(List<Map<String, ?>> facts, ResourceLocation itemId, Object equipment,
                              String fieldName, String key, String unit) throws ReflectiveOperationException {
        Object setting = field(equipment, fieldName);
        facts.add(MechanicRows.fact(id(), "item", itemId.toString(), "electrical.meter." + key,
                MechanicRows.call(setting, "get"), unit,
                Map.of("meaning", "measurement range", "configuration", "effective server setting"),
                CONFIG_CLASS + ".server().equipment." + fieldName + ".get"));
    }

    private Object field(Object target, String name) throws ReflectiveOperationException {
        Field field = target.getClass().getField(name);
        return field.get(target);
    }
}
