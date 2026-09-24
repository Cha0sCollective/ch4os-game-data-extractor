package dev.chaosarbiter.handbookexporter;

import com.google.gson.JsonObject;
import net.minecraft.core.registries.BuiltInRegistries;
import net.minecraft.resources.ResourceLocation;
import net.minecraft.server.MinecraftServer;
import net.minecraft.world.item.crafting.RecipeHolder;

import java.util.ArrayList;
import java.util.Comparator;
import java.util.HashSet;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import java.util.Set;
import java.util.function.Predicate;

/** Promotes active custom recipe definitions, excluding resources rejected by the recipe manager. */
final class AcceptedRecipeDefinitions {
    private AcceptedRecipeDefinitions() {
    }

    static void collect(String adapter, MinecraftServer server, Predicate<ResourceLocation> inScope,
                        List<Map<String, ?>> definitions, List<Map<String, ?>> diagnostics) {
        List<RecipeHolder<?>> accepted = server.getRecipeManager().getRecipes().stream()
                .filter(holder -> inScope.test(holder.id()))
                .filter(holder -> {
                    ResourceLocation type = BuiltInRegistries.RECIPE_TYPE.getKey(holder.value().getType());
                    return type != null && adapter.equals(type.getNamespace());
                })
                .sorted(Comparator.comparing(holder -> holder.id().toString())).toList();
        Set<ResourceLocation> resourceIds = new HashSet<>();
        for (RecipeHolder<?> holder : accepted) {
            resourceIds.add(ResourceLocation.fromNamespaceAndPath(holder.id().getNamespace(),
                    "recipe/" + holder.id().getPath() + ".json"));
        }
        Map<ResourceLocation, EffectiveDataResources.LoadedJson> sources = new LinkedHashMap<>();
        for (EffectiveDataResources.LoadedJson loaded : EffectiveDataResources.collect(server, "recipe",
                resourceIds::contains)) {
            sources.put(loaded.resourceId(), loaded);
        }
        for (RecipeHolder<?> holder : accepted) {
            ResourceLocation resourceId = ResourceLocation.fromNamespaceAndPath(holder.id().getNamespace(),
                    "recipe/" + holder.id().getPath() + ".json");
            EffectiveDataResources.LoadedJson loaded = sources.get(resourceId);
            if (loaded == null || !"captured".equals(loaded.status()) || !loaded.json().isJsonObject()) {
                diagnostics.add(Map.of("subsystem", "mechanic_adapter:" + adapter + ":recipe:" + holder.id(),
                        "status", "partial", "reason", loaded == null ? "source_unavailable" : loaded.status()));
                continue;
            }
            JsonObject source = loaded.json().getAsJsonObject();
            Map<String, Object> attributes = new LinkedHashMap<>();
            attributes.put("recipe_type", BuiltInRegistries.RECIPE_TYPE.getKey(holder.value().getType()).toString());
            for (String field : List.of("ingredients", "results", "mode", "biome", "processing_time",
                    "heat_requirement", "mold", "energy", "stress")) {
                if (source.has(field)) {
                    attributes.put(field, source.get(field));
                }
            }
            if (attributes.get("results") instanceof com.google.gson.JsonArray results && results.isEmpty()
                    && attributes.get("recipe_type").toString().endsWith("_fuel")) {
                attributes.put("output_semantics", "fuel specification; no material result in source recipe");
            }
            Map<String, Object> conditions = new LinkedHashMap<>();
            conditions.put("meaning", "accepted by loaded recipe manager");
            if (source.has("neoforge:conditions")) {
                conditions.put("source_conditions", source.get("neoforge:conditions"));
            }
            definitions.add(AdapterRows.definition(adapter, "specialized_recipe", holder.id().toString(),
                    attributes, conditions, resourceId.toString(), loaded.sourcePackId(),
                    loaded.sourceSha256(), "MinecraftServer.getRecipeManager + effective data resource"));
        }
    }
}
