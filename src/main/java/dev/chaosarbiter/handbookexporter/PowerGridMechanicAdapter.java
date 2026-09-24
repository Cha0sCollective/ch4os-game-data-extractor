package dev.chaosarbiter.handbookexporter;

import net.minecraft.core.Registry;
import net.minecraft.core.registries.BuiltInRegistries;
import net.minecraft.resources.ResourceLocation;
import net.minecraft.server.MinecraftServer;

import java.lang.reflect.Field;
import java.util.ArrayList;
import java.util.Comparator;
import java.util.List;
import java.util.Map;
import java.util.function.Predicate;

/** Captures registered wire ratings and effective equipment ranges without a Power Grid build dependency. */
final class PowerGridMechanicAdapter implements MechanicAdapter {
    private static final String CONFIG_CLASS = "org.patryk3211.powergrid.collections.ModdedConfigs";
    private static final String WIRE_ENTRY = "org.patryk3211.powergrid.electricity.wire.registry.WireItemEntry";
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
            return new Result(facts, List.of(), List.of());
        } catch (ReflectiveOperationException exception) {
            throw new IllegalStateException("Power Grid runtime API unavailable", exception);
        }
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
