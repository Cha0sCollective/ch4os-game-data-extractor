package dev.chaosarbiter.handbookexporter;

import net.minecraft.resources.ResourceLocation;
import net.minecraft.server.MinecraftServer;
import net.neoforged.fml.ModList;

import java.util.ArrayList;
import java.util.Comparator;
import java.util.HashSet;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import java.util.ServiceConfigurationError;
import java.util.ServiceLoader;
import java.util.Set;
import java.util.function.Predicate;

/** Runs bundled and service-provided adapters independently after generic collection. */
final class MechanicAdapters {
    private MechanicAdapters() {
    }

    static MechanicAdapter.Result collect(MinecraftServer server, Predicate<ResourceLocation> inScope) {
        List<MechanicAdapter> adapters = new ArrayList<>(List.of(
                new CreateMechanicAdapter(),
                new DeepSeasMechanicAdapter(),
                new PowerGridMechanicAdapter()
        ));
        List<Map<String, ?>> mechanics = new ArrayList<>();
        List<Map<String, ?>> configs = new ArrayList<>();
        List<Map<String, ?>> definitions = new ArrayList<>();
        List<Map<String, ?>> relations = new ArrayList<>();
        List<Map<String, ?>> diagnostics = new ArrayList<>();
        try {
            ServiceLoader.load(MechanicAdapter.class).forEach(adapters::add);
        } catch (ServiceConfigurationError exception) {
            diagnostics.add(Map.of("subsystem", "mechanic_adapter:service_loader",
                    "status", "error", "row_count", 0,
                    "error_class", exception.getClass().getName()));
        }
        adapters.sort(Comparator.comparing(MechanicAdapter::id));
        Set<String> seenIds = new HashSet<>();
        for (MechanicAdapter adapter : adapters) {
            try {
                if (!seenIds.add(adapter.id())) {
                    diagnostics.add(diagnostic(adapter, "duplicate_adapter", 0, null, Map.of()));
                    continue;
                }
                List<String> missingMods = adapter.requiredModIds().stream()
                        .filter(modId -> !ModList.get().isLoaded(modId)).toList();
                if (!missingMods.isEmpty()) {
                    diagnostics.add(diagnostic(adapter, "not_applicable", 0, null,
                            Map.of("missing_mods", missingMods)));
                    continue;
                }
                List<String> missingClasses = adapter.requiredClassNames().stream()
                        .filter(className -> !classAvailable(adapter, className)).toList();
                if (!missingClasses.isEmpty()) {
                    diagnostics.add(diagnostic(adapter, "unsupported", 0, null,
                            Map.of("missing_classes", missingClasses)));
                    continue;
                }
                MechanicAdapter.Result result = adapter.collect(server, inScope);
                Map<String, String> versions = requiredModVersions(adapter);
                List<Map<String, ?>> stampedDefinitions = withVersions(result.definitions(), versions);
                List<Map<String, ?>> stampedRelations = withVersions(result.relations(), versions);
                mechanics.addAll(result.mechanics());
                configs.addAll(result.configs());
                definitions.addAll(stampedDefinitions);
                relations.addAll(stampedRelations);
                diagnostics.addAll(result.diagnostics());
                boolean partial = result.diagnostics().stream()
                        .anyMatch(row -> "error".equals(row.get("status")) || "partial".equals(row.get("status")));
                diagnostics.add(diagnostic(adapter, partial ? "partial" : "ok",
                        result.mechanics().size() + result.definitions().size() + result.relations().size(),
                        null, Map.of("mechanics", result.mechanics().size(),
                                "definitions", result.definitions().size(),
                                "relations", result.relations().size(),
                                "configs", result.configs().size())));
            } catch (RuntimeException | LinkageError exception) {
                diagnostics.add(diagnostic(adapter, "error", 0, exception, Map.of()));
            }
        }
        return new MechanicAdapter.Result(mechanics, configs, definitions, relations, diagnostics);
    }

    private static List<Map<String, ?>> withVersions(List<Map<String, ?>> rows, Map<String, String> versions) {
        List<Map<String, ?>> stamped = new ArrayList<>();
        for (Map<String, ?> row : rows) {
            Map<String, Object> copy = new LinkedHashMap<>(row);
            copy.putIfAbsent("required_mod_versions", versions);
            stamped.add(copy);
        }
        return stamped;
    }

    private static Map<String, String> requiredModVersions(MechanicAdapter adapter) {
        Map<String, String> versions = new LinkedHashMap<>();
        adapter.requiredModIds().forEach(modId -> ModList.get().getModContainerById(modId)
                .ifPresent(container -> versions.put(modId, container.getModInfo().getVersion().toString())));
        return versions;
    }

    private static boolean classAvailable(MechanicAdapter adapter, String className) {
        try {
            Class.forName(className, false, adapter.getClass().getClassLoader());
            return true;
        } catch (ClassNotFoundException | LinkageError exception) {
            return false;
        }
    }

    private static Map<String, Object> diagnostic(MechanicAdapter adapter, String status, int count,
                                                   Throwable failure, Map<String, ?> detail) {
        Map<String, Object> row = new LinkedHashMap<>();
        row.put("subsystem", "mechanic_adapter:" + adapter.id());
        row.put("status", status);
        row.put("row_count", count);
        row.put("error_class", failure == null ? null : failure.getClass().getName());
        try {
            row.put("required_mod_versions", requiredModVersions(adapter));
        } catch (RuntimeException exception) {
            row.put("required_mod_versions", Map.of());
        }
        row.putAll(detail);
        return row;
    }
}
