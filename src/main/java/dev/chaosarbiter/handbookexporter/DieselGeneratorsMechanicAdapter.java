package dev.chaosarbiter.handbookexporter;

import net.minecraft.core.Holder;
import net.minecraft.core.HolderSet;
import net.minecraft.core.Registry;
import net.minecraft.core.registries.BuiltInRegistries;
import net.minecraft.resources.ResourceLocation;
import net.minecraft.server.MinecraftServer;
import net.minecraft.world.level.material.Fluid;

import java.lang.reflect.Field;
import java.lang.reflect.Modifier;
import java.util.ArrayList;
import java.util.Comparator;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import java.util.function.Predicate;

/** Data-driven engine fuel types, active processes, and effective settings. */
final class DieselGeneratorsMechanicAdapter implements MechanicAdapter {
    private static final String MOD = "createdieselgenerators";
    private static final String FUEL = "com.jesz.createdieselgenerators.fuel_type.FuelType";
    private static final String CONFIG = "com.jesz.createdieselgenerators.CDGConfig";

    @Override public String id() { return MOD; }
    @Override public String requiredModId() { return MOD; }
    @Override public List<String> requiredClassNames() { return List.of(FUEL, CONFIG); }

    @Override
    public Result collect(MinecraftServer server, Predicate<ResourceLocation> inScope) {
        if (!inScope.test(ResourceLocation.parse(MOD + ":fuel_type"))) {
            return Result.empty();
        }
        List<Map<String, ?>> definitions = new ArrayList<>();
        List<Map<String, ?>> relations = new ArrayList<>();
        List<Map<String, ?>> configs = new ArrayList<>();
        List<Map<String, ?>> diagnostics = new ArrayList<>();
        try {
            collectFuelTypes(server, definitions, relations, diagnostics);
        } catch (ReflectiveOperationException | RuntimeException | LinkageError exception) {
            diagnostics.add(partial("fuel_types", exception));
        }
        AcceptedRecipeDefinitions.collect(id(), server, inScope, definitions, diagnostics);
        collectConfigs(configs, diagnostics);
        return new Result(List.of(), configs, definitions, relations, diagnostics);
    }

    private void collectFuelTypes(MinecraftServer server, List<Map<String, ?>> definitions,
                                  List<Map<String, ?>> relations, List<Map<String, ?>> diagnostics)
            throws ReflectiveOperationException {
        ResourceLocation key = ResourceLocation.parse(MOD + ":fuel_type");
        Registry<?> registry = server.registryAccess().registries()
                .filter(entry -> entry.key().location().equals(key))
                .map(entry -> entry.value()).findFirst().orElse(null);
        if (registry == null) {
            throw new IllegalStateException("missing registry " + key);
        }
        for (ResourceLocation entryId : registry.keySet().stream()
                .sorted(Comparator.comparing(ResourceLocation::toString)).toList()) {
            try {
                Object fuel = registry.get(entryId);
                Map<String, Object> attrs = new LinkedHashMap<>();
                attrs.put("sound_pitch", MechanicRows.call(fuel, "soundPitch"));
                attrs.put("burner_strength", MechanicRows.call(fuel, "burnerStrength"));
                for (String engine : List.of("normal", "modular", "huge")) {
                    Object properties = MechanicRows.call(fuel, engine);
                    attrs.put(engine, Map.of("speed", MechanicRows.call(properties, "speed"),
                            "strength", MechanicRows.call(properties, "strength"),
                            "burn", MechanicRows.call(properties, "burn")));
                }
                HolderSet<?> fluids = (HolderSet<?>) MechanicRows.call(fuel, "fluid");
                definitions.add(AdapterRows.definition(id(), "diesel_engine_fuel_type", entryId.toString(),
                        attrs, Map.of("meaning", "loaded data-driven engine fuel type"),
                        null, null, null, FUEL));
                for (Holder<?> holder : fluids) {
                    if (holder.value() instanceof Fluid fluid) {
                        relations.add(AdapterRows.relation(id(), "diesel_engine_fuel_type", entryId.toString(),
                                "accepts_fluid", "fluid", BuiltInRegistries.FLUID.getKey(fluid).toString(),
                                Map.of(), Map.of(), FUEL + ".fluid"));
                    }
                }
            } catch (ReflectiveOperationException | RuntimeException exception) {
                diagnostics.add(partial("fuel_type:" + entryId, exception));
            }
        }
    }

    private void collectConfigs(List<Map<String, ?>> configs, List<Map<String, ?>> diagnostics) {
        try {
            Class<?> owner = Class.forName(CONFIG);
            for (Field field : owner.getFields()) {
                if (!Modifier.isStatic(field.getModifiers()) ||
                        !field.getType().getName().contains("ModConfigSpec$ConfigValue") ||
                        List.of("ENGINES_EMIT_SOUND_ON_TRAINS", "FUEL_TOOLTIPS", "DIESEL_ENGINE_IN_JEI")
                                .contains(field.getName())) {
                    continue;
                }
                try {
                    Object value = MechanicRows.call(field.get(null), "get");
                    if (value instanceof Number || value instanceof Boolean || value instanceof String) {
                        configs.add(AdapterRows.config(id(), MOD, "runtime", "CDGConfig",
                                field.getName(), value, null, CONFIG + "." + field.getName() + ".get"));
                    }
                } catch (ReflectiveOperationException | RuntimeException exception) {
                    diagnostics.add(partial("config:" + field.getName(), exception));
                }
            }
        } catch (ClassNotFoundException | LinkageError exception) {
            diagnostics.add(partial("config", exception));
        }
    }

    private Map<String, ?> partial(String part, Throwable exception) {
        return Map.of("subsystem", "mechanic_adapter:" + id() + ":" + part,
                "status", "partial", "error_class", exception.getClass().getName());
    }
}
