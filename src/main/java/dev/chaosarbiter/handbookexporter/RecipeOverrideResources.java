package dev.chaosarbiter.handbookexporter;

import net.minecraft.resources.ResourceLocation;
import net.minecraft.server.MinecraftServer;

import java.util.ArrayList;
import java.util.Comparator;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;

/** Resource-stack evidence for duplicate recipe IDs across active packs. */
final class RecipeOverrideResources {
    private RecipeOverrideResources() {
    }

    static List<Map<String, ?>> collect(MinecraftServer server) {
        List<Map<String, ?>> rows = new ArrayList<>();
        server.getResourceManager().listResourceStacks("recipe", id -> id.getPath().endsWith(".json"))
                .entrySet().stream()
                .sorted(Map.Entry.comparingByKey(Comparator.comparing(ResourceLocation::toString)))
                .forEach(entry -> {
                    if (entry.getValue().size() < 2) {
                        return;
                    }
                    ResourceLocation resourceId = entry.getKey();
                    String path = resourceId.getPath();
                    if (!path.startsWith("recipe/") || !path.endsWith(".json")) {
                        return;
                    }
                    String recipePath = path.substring("recipe/".length(), path.length() - ".json".length());
                    ResourceLocation recipeId = ResourceLocation.fromNamespaceAndPath(
                            resourceId.getNamespace(), recipePath);
                    Map<String, Object> row = new LinkedHashMap<>();
                    row.put("id", recipeId.toString());
                    row.put("resource_id", resourceId.toString());
                    row.put("effective_loaded", server.getRecipeManager().byKey(recipeId).isPresent());
                    row.put("layers", entry.getValue().stream()
                            .map(resource -> Map.of("pack_id", resource.sourcePackId()))
                            .toList());
                    rows.add(row);
                });
        return rows;
    }
}
