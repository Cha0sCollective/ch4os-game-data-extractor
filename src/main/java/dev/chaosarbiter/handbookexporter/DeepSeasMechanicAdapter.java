package dev.chaosarbiter.handbookexporter;

import net.minecraft.core.registries.BuiltInRegistries;
import net.minecraft.resources.ResourceLocation;
import net.minecraft.server.MinecraftServer;
import net.minecraft.world.level.block.state.BlockState;

import java.lang.reflect.Field;
import java.lang.reflect.Method;
import java.util.ArrayList;
import java.util.Comparator;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import java.util.Optional;
import java.util.function.Predicate;

/** Reads Deep Seas' effective hull rating after its per-block config and multipliers. */
final class DeepSeasMechanicAdapter implements MechanicAdapter {
    private static final String HULL_CONFIG =
            "com.maxenonyme.createsubmarine.submarine.config.HullStrengthConfig";
    private static final String SERVER_CONFIG =
            "com.maxenonyme.createsubmarine.submarine.config.SubmarineConfig";

    @Override
    public String id() {
        return "create_deep_seas";
    }

    @Override
    public String requiredModId() {
        return "create_submarine";
    }

    @Override
    public Result collect(MinecraftServer server, Predicate<ResourceLocation> inScope) {
        try {
            Method getFor = Class.forName(HULL_CONFIG).getMethod("getFor", BlockState.class);
            Class<?> settings = Class.forName(SERVER_CONFIG);
            Object disabled = configValue(settings, "DISABLE_IMPLOSION");
            List<Map<String, ?>> facts = new ArrayList<>();
            Map<String, Object> conditions = new LinkedHashMap<>();
            conditions.put("usage", "submarine hull block");
            conditions.put("block_state", "default");
            conditions.put("submarine_limit", "weakest hull block");
            conditions.put("implosion_disabled", disabled);
            BuiltInRegistries.BLOCK.entrySet().stream()
                    .sorted(Map.Entry.comparingByKey(Comparator.comparing(key -> key.location().toString())))
                    .forEach(entry -> {
                        ResourceLocation id = entry.getKey().location();
                        if (!inScope.test(id)) {
                            return;
                        }
                        try {
                            @SuppressWarnings("unchecked")
                            Optional<Object> rating = (Optional<Object>) getFor.invoke(null,
                                    entry.getValue().defaultBlockState());
                            if (rating.isEmpty()) {
                                return;
                            }
                            Object value = rating.get();
                            facts.add(MechanicRows.fact(id(), "block", id.toString(),
                                    "hull.max_water_depth", MechanicRows.call(value, "maxWaterDepth"),
                                    "blocks", conditions, HULL_CONFIG + ".getFor"));
                            facts.add(MechanicRows.fact(id(), "block", id.toString(),
                                    "hull.implosion_chance", MechanicRows.call(value, "implosionChance"),
                                    "probability", conditions, HULL_CONFIG + ".getFor"));
                        } catch (ReflectiveOperationException exception) {
                            throw new IllegalStateException("Deep Seas hull lookup failed for " + id, exception);
                        }
                    });
            Map<String, Object> config = new LinkedHashMap<>();
            config.put("mod_id", requiredModId());
            config.put("config_scope", "common");
            config.put("config_path", "hullStrength");
            config.put("field_name", "disableImplosion");
            config.put("effective_value", disabled);
            config.put("unit_hint", null);
            config.put("evidence_status", "installed_runtime_confirmed");
            config.put("source_api", SERVER_CONFIG + ".DISABLE_IMPLOSION");
            return new Result(facts, List.of(config), List.of());
        } catch (ReflectiveOperationException exception) {
            throw new IllegalStateException("Deep Seas runtime API unavailable", exception);
        }
    }

    private Object configValue(Class<?> owner, String fieldName) throws ReflectiveOperationException {
        Field field = owner.getField(fieldName);
        return MechanicRows.call(field.get(null), "get");
    }
}
