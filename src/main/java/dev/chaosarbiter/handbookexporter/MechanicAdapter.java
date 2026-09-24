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

    Result collect(MinecraftServer server, Predicate<ResourceLocation> inScope);

    record Result(
            List<Map<String, ?>> mechanics,
            List<Map<String, ?>> configs,
            List<Map<String, ?>> diagnostics
    ) {
        public static Result empty() {
            return new Result(List.of(), List.of(), List.of());
        }
    }
}
