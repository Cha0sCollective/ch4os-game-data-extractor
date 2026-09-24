package dev.chaosarbiter.handbookexporter;

import net.minecraft.resources.ResourceLocation;
import net.minecraft.server.MinecraftServer;

import java.util.List;
import java.util.Map;
import java.util.function.Predicate;

/** Optional runtime facts. An adapter never controls the generic item or recipe inventory. */
public interface MechanicAdapter {
    String id();

    String requiredModId();

    /** Additional required mods are checked at runtime, never against a pinned pack version. */
    default List<String> requiredModIds() {
        return List.of(requiredModId());
    }

    /** Optional API probes let an integration skip cleanly when a mod changes its surface. */
    default List<String> requiredClassNames() {
        return List.of();
    }

    Result collect(MinecraftServer server, Predicate<ResourceLocation> inScope);

    record Result(
            List<Map<String, ?>> mechanics,
            List<Map<String, ?>> configs,
            List<Map<String, ?>> definitions,
            List<Map<String, ?>> relations,
            List<Map<String, ?>> diagnostics
    ) {
        public Result(List<Map<String, ?>> mechanics, List<Map<String, ?>> configs,
                      List<Map<String, ?>> diagnostics) {
            this(mechanics, configs, List.of(), List.of(), diagnostics);
        }

        public static Result empty() {
            return new Result(List.of(), List.of(), List.of(), List.of(), List.of());
        }
    }
}
