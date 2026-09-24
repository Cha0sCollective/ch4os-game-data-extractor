package dev.chaosarbiter.handbookexporter;

import net.minecraft.resources.ResourceLocation;
import net.minecraft.server.MinecraftServer;
import net.neoforged.fml.ModList;

import java.util.ArrayList;
import java.util.Comparator;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import java.util.ServiceConfigurationError;
import java.util.ServiceLoader;
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
        List<Map<String, ?>> diagnostics = new ArrayList<>();
        try {
            ServiceLoader.load(MechanicAdapter.class).forEach(adapters::add);
        } catch (ServiceConfigurationError exception) {
            diagnostics.add(diagnostic("service_loader", "error", 0, exception));
        }
        adapters.sort(Comparator.comparing(MechanicAdapter::id));
        for (MechanicAdapter adapter : adapters) {
            if (!ModList.get().isLoaded(adapter.requiredModId())) {
                diagnostics.add(diagnostic(adapter.id(), "not_applicable", 0, null));
                continue;
            }
            try {
                MechanicAdapter.Result result = adapter.collect(server, inScope);
                mechanics.addAll(result.mechanics());
                configs.addAll(result.configs());
                diagnostics.addAll(result.diagnostics());
                boolean partial = result.diagnostics().stream()
                        .anyMatch(row -> "error".equals(row.get("status")) || "partial".equals(row.get("status")));
                diagnostics.add(diagnostic(adapter.id(), partial ? "partial" : "ok",
                        result.mechanics().size(), null));
            } catch (RuntimeException | LinkageError exception) {
                diagnostics.add(diagnostic(adapter.id(), "error", 0, exception));
            }
        }
        return new MechanicAdapter.Result(mechanics, configs, diagnostics);
    }

    private static Map<String, Object> diagnostic(String adapter, String status, int count, Throwable failure) {
        Map<String, Object> row = new LinkedHashMap<>();
        row.put("subsystem", "mechanic_adapter:" + adapter);
        row.put("status", status);
        row.put("row_count", count);
        row.put("error_class", failure == null ? null : failure.getClass().getName());
        return row;
    }
}
