package dev.chaosarbiter.handbookexporter;

import net.minecraft.core.Registry;
import net.minecraft.core.registries.BuiltInRegistries;
import net.minecraft.resources.ResourceLocation;
import net.minecraft.server.MinecraftServer;
import net.minecraft.world.item.Item;
import net.minecraft.world.level.block.Block;

import java.lang.reflect.Method;
import java.util.ArrayList;
import java.util.Comparator;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import java.util.function.Predicate;

/** Loaded wire ratings, simulated-device mappings, and effective electrical settings. */
final class ElectroEnergeticsMechanicAdapter implements MechanicAdapter {
    private static final String MOD = "electroenergetics";
    private static final String WIRE = "com.george_vi.electroenergetics.simulation.WireType";
    private static final String DEVICE = "com.george_vi.electroenergetics.devices.device.SimulatedDeviceType";
    private static final String CONFIG = "com.george_vi.electroenergetics.config.CEEConfigs";

    @Override
    public String id() {
        return MOD;
    }

    @Override
    public String requiredModId() {
        return MOD;
    }

    @Override
    public List<String> requiredClassNames() {
        return List.of(WIRE, DEVICE, CONFIG);
    }

    @Override
    public Result collect(MinecraftServer server, Predicate<ResourceLocation> inScope) {
        if (!inScope.test(ResourceLocation.parse(MOD + ":wire_type"))) {
            return Result.empty();
        }
        List<Map<String, ?>> definitions = new ArrayList<>();
        List<Map<String, ?>> relations = new ArrayList<>();
        List<Map<String, ?>> configs = new ArrayList<>();
        List<Map<String, ?>> diagnostics = new ArrayList<>();
        collectPart("wire_types", diagnostics, () -> collectWires(definitions, relations, diagnostics));
        collectPart("devices", diagnostics, () -> collectDevices(definitions, relations, diagnostics));
        collectPart("config", diagnostics, () -> {
            Object effective = Class.forName(CONFIG).getMethod("server").invoke(null);
            AdapterConfigIntrospection.collect(id(), MOD, "server", effective,
                    "com.george_vi.electroenergetics.config.", configs, diagnostics);
        });
        return new Result(List.of(), configs, definitions, relations, diagnostics);
    }

    private void collectWires(List<Map<String, ?>> definitions, List<Map<String, ?>> relations,
                              List<Map<String, ?>> diagnostics) throws ReflectiveOperationException {
        ResourceLocation key = ResourceLocation.parse(MOD + ":wire_type");
        Registry<?> registry = BuiltInRegistries.REGISTRY.get(key);
        if (registry == null) {
            throw new IllegalStateException("missing registry " + key);
        }
        for (ResourceLocation entryId : registry.keySet().stream()
                .sorted(Comparator.comparing(ResourceLocation::toString)).toList()) {
            String wireId = entryId.toString();
            try {
                Object wire = registry.get(entryId);
                Map<String, Object> attrs = new LinkedHashMap<>();
                for (String method : List.of("getResistance", "insulationResistance", "maxInsulationVoltage",
                        "getMaxTemperature", "getMaxLength", "getSag", "getThickness", "insulated",
                        "isInvulnerable", "isDecorative")) {
                    attrs.put(method, MechanicRows.call(wire, method));
                }
                definitions.add(AdapterRows.definition(id(), "electro_wire_type", wireId, attrs,
                        Map.of("meaning", "loaded wire registry and effective supplier values",
                                "maxInsulationVoltage", "insulation breakdown rating, not a universal grid voltage limit"),
                        null, null, null, WIRE));
                linkItem(relations, wireId, wire, "getDrops", "drops_item");
                linkItem(relations, wireId, wire, "getSpooledItem", "spooled_as");
            } catch (ReflectiveOperationException | RuntimeException exception) {
                diagnostics.add(partial("wire:" + wireId, exception));
            }
        }
    }

    private void linkItem(List<Map<String, ?>> relations, String wireId, Object wire,
                          String getter, String predicate) throws ReflectiveOperationException {
        Object item = MechanicRows.call(wire, getter);
        if (item instanceof Item material && material != net.minecraft.world.item.Items.AIR) {
            relations.add(AdapterRows.relation(id(), "electro_wire_type", wireId, predicate,
                    "item", BuiltInRegistries.ITEM.getKey(material).toString(), Map.of(), Map.of(),
                    WIRE + "." + getter));
        }
    }

    private void collectDevices(List<Map<String, ?>> definitions, List<Map<String, ?>> relations,
                                List<Map<String, ?>> diagnostics) throws ReflectiveOperationException {
        ResourceLocation key = ResourceLocation.parse(MOD + ":simulated_device_type");
        Registry<?> registry = BuiltInRegistries.REGISTRY.get(key);
        if (registry == null) {
            throw new IllegalStateException("missing registry " + key);
        }
        Method validBlocks = Class.forName(DEVICE).getMethod("validBlocks");
        for (ResourceLocation entryId : registry.keySet().stream()
                .sorted(Comparator.comparing(ResourceLocation::toString)).toList()) {
            String deviceId = entryId.toString();
            try {
                @SuppressWarnings("unchecked")
                java.util.Collection<Block> blocks = (java.util.Collection<Block>) validBlocks.invoke(registry.get(entryId));
                definitions.add(AdapterRows.definition(id(), "electro_device_type", deviceId,
                        Map.of("valid_block_count", blocks.size()),
                        Map.of("meaning", "registered simulated device type"), null, null, null, DEVICE));
                for (Block block : blocks) {
                    relations.add(AdapterRows.relation(id(), "electro_device_type", deviceId,
                            "simulates_block", "block", BuiltInRegistries.BLOCK.getKey(block).toString(),
                            Map.of(), Map.of(), DEVICE + ".validBlocks"));
                }
            } catch (ReflectiveOperationException | RuntimeException exception) {
                diagnostics.add(partial("device:" + deviceId, exception));
            }
        }
    }

    private Map<String, ?> partial(String part, Exception exception) {
        return Map.of("subsystem", "mechanic_adapter:" + id() + ":" + part,
                "status", "partial", "error_class", exception.getClass().getName());
    }

    private void collectPart(String part, List<Map<String, ?>> diagnostics, Collector collector) {
        try {
            collector.run();
        } catch (ReflectiveOperationException | RuntimeException | LinkageError exception) {
            diagnostics.add(Map.of("subsystem", "mechanic_adapter:" + id() + ":" + part,
                    "status", "partial", "error_class", exception.getClass().getName()));
        }
    }

    @FunctionalInterface
    private interface Collector {
        void run() throws ReflectiveOperationException;
    }
}
