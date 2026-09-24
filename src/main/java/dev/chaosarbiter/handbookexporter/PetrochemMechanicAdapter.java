package dev.chaosarbiter.handbookexporter;

import net.minecraft.resources.ResourceLocation;
import net.minecraft.server.MinecraftServer;

import java.lang.reflect.Field;
import java.util.ArrayList;
import java.util.List;
import java.util.Map;
import java.util.function.Predicate;

/** Active Petrochem processes and effective loaded settings. */
final class PetrochemMechanicAdapter implements MechanicAdapter {
    private static final String CONFIG = "io.github.hadron13.petrochem.config.PetrochemConfig";

    @Override public String id() { return "petrochem"; }
    @Override public String requiredModId() { return "petrochem"; }
    @Override public List<String> requiredClassNames() { return List.of(CONFIG); }

    @Override
    public Result collect(MinecraftServer server, Predicate<ResourceLocation> inScope) {
        if (!inScope.test(ResourceLocation.parse("petrochem:pumpjack"))) {
            return Result.empty();
        }
        List<Map<String, ?>> definitions = new ArrayList<>();
        List<Map<String, ?>> configs = new ArrayList<>();
        List<Map<String, ?>> diagnostics = new ArrayList<>();
        AcceptedRecipeDefinitions.collect(id(), server, inScope, definitions, diagnostics);
        try {
            Class<?> owner = Class.forName(CONFIG);
            for (String scope : List.of("common", "server")) {
                Object root = owner.getMethod(scope).invoke(null);
                AdapterConfigIntrospection.collect(id(), id(), scope, root,
                        "io.github.hadron13.petrochem.config.", configs, diagnostics);
                if ("server".equals(scope)) {
                    collectStress(root, configs);
                }
            }
        } catch (ReflectiveOperationException | RuntimeException | LinkageError exception) {
            diagnostics.add(Map.of("subsystem", "mechanic_adapter:" + id() + ":config",
                    "status", "partial", "error_class", exception.getClass().getName()));
        }
        return new Result(List.of(), configs, definitions, List.of(), diagnostics);
    }

    private void collectStress(Object serverConfig, List<Map<String, ?>> configs)
            throws ReflectiveOperationException {
        Object kinetics = serverConfig.getClass().getField("kinetics").get(serverConfig);
        Object stress = kinetics.getClass().getField("stressValues").get(kinetics);
        for (String property : List.of("impacts", "capacities")) {
            Field field = stress.getClass().getDeclaredField(property);
            field.setAccessible(true);
            @SuppressWarnings("unchecked")
            Map<ResourceLocation, ?> registered = (Map<ResourceLocation, ?>) field.get(stress);
            for (var entry : registered.entrySet().stream()
                    .sorted(Map.Entry.comparingByKey()).toList()) {
                Object value = MechanicRows.call(entry.getValue(), "get");
                if (value instanceof Number) {
                    configs.add(AdapterRows.config(id(), id(), "server", "stressValues." + property,
                            entry.getKey().toString(), value, "SU/rpm",
                            stress.getClass().getName() + "." + property + ".get"));
                }
            }
        }
    }
}
