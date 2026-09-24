package dev.chaosarbiter.handbookexporter;

import net.minecraft.resources.ResourceLocation;
import net.minecraft.server.MinecraftServer;

import java.util.function.Predicate;

final class CreateMechanicAdapter implements MechanicAdapter {
    @Override
    public String id() {
        return "create";
    }

    @Override
    public String requiredModId() {
        return "create";
    }

    @Override
    public Result collect(MinecraftServer server, Predicate<ResourceLocation> inScope) {
        CreateRuntimeIntrospection.IntrospectionResult result = new CreateRuntimeIntrospection(inScope).collect();
        return new Result(result.mechanics(), result.configs(), result.diagnostics());
    }
}
