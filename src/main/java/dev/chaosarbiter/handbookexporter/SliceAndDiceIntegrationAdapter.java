package dev.chaosarbiter.handbookexporter;

import net.minecraft.core.registries.BuiltInRegistries;
import net.minecraft.resources.ResourceLocation;
import net.minecraft.server.MinecraftServer;
import net.minecraft.world.item.crafting.RecipeHolder;

import java.util.ArrayList;
import java.util.Comparator;
import java.util.HashMap;
import java.util.List;
import java.util.Map;
import java.util.function.Predicate;
import java.util.regex.Matcher;
import java.util.regex.Pattern;

/** Links accepted Slice & Dice recipes to their accepted Farmer's Delight source recipes. */
final class SliceAndDiceIntegrationAdapter implements MechanicAdapter {
    private static final Pattern COOKING_SUFFIX = Pattern.compile("^(.*)_([0-9]+)$");

    @Override public String id() { return "sliceanddice"; }
    @Override public String requiredModId() { return id(); }
    @Override public List<String> requiredModIds() { return List.of(id(), "farmersdelight"); }

    @Override
    public Result collect(MinecraftServer server, Predicate<ResourceLocation> inScope) {
        Map<ResourceLocation, RecipeHolder<?>> accepted = new HashMap<>();
        for (RecipeHolder<?> recipe : server.getRecipeManager().getRecipes()) {
            accepted.put(recipe.id(), recipe);
        }
        List<Map<String, ?>> definitions = new ArrayList<>();
        List<Map<String, ?>> relations = new ArrayList<>();
        for (String conversion : List.of("cutting", "cooking")) {
            ResourceLocation sourceType = ResourceLocation.parse("farmersdelight:" + conversion);
            ResourceLocation targetType = ResourceLocation.parse(
                    "cutting".equals(conversion) ? "sliceanddice:cutting" : "create:mixing");
            String definitionId = id() + ":" + conversion + "_conversion";
            int count = 0;
            for (RecipeHolder<?> target : accepted.values().stream()
                    .sorted(Comparator.comparing(recipe -> recipe.id().toString())).toList()) {
                ResourceLocation targetId = target.id();
                if (!"sliceanddice".equals(targetId.getNamespace())
                        || !targetId.getPath().startsWith(conversion + "/")
                        || !targetType.equals(BuiltInRegistries.RECIPE_TYPE.getKey(target.value().getType()))
                        || !inScope.test(targetId)) {
                    continue;
                }
                String sourcePath = targetId.getPath().substring(conversion.length() + 1);
                int slash = sourcePath.indexOf('/');
                if (slash <= 0) {
                    continue;
                }
                String sourceNamespace = sourcePath.substring(0, slash);
                String originalPath = sourcePath.substring(slash + 1);
                if ("cooking".equals(conversion)) {
                    Matcher suffix = COOKING_SUFFIX.matcher(originalPath);
                    if (!suffix.matches()) {
                        continue;
                    }
                    originalPath = suffix.group(1);
                }
                ResourceLocation sourceId = ResourceLocation.tryBuild(sourceNamespace, originalPath);
                RecipeHolder<?> source = sourceId == null ? null : accepted.get(sourceId);
                if (source == null || !sourceType.equals(BuiltInRegistries.RECIPE_TYPE.getKey(source.value().getType()))
                        || !inScope.test(sourceId)) {
                    continue;
                }
                Map<String, String> conditions = Map.of("basis", "both source and generated recipes accepted by loaded recipe manager");
                relations.add(AdapterRows.relation(id(), "recipe", sourceId.toString(), "converted_to",
                        "recipe", targetId.toString(), Map.of("target_recipe_type", targetType.toString()),
                        conditions, "MinecraftServer.getRecipeManager"));
                relations.add(AdapterRows.relation(id(), "recipe", targetId.toString(), "generated_by",
                        "loaded_recipe_conversion", definitionId,
                        Map.of("source_recipe_id", sourceId.toString()), conditions,
                        "MinecraftServer.getRecipeManager"));
                count++;
            }
            if (count > 0) {
                definitions.add(AdapterRows.definition(id(), "loaded_recipe_conversion", definitionId,
                        Map.of("source_recipe_type", sourceType.toString(),
                                "target_recipe_type", targetType.toString(), "accepted_recipe_pairs", count),
                        Map.of("meaning", "accepted generated recipes linked to their accepted source recipes"),
                        null, null, null, "MinecraftServer.getRecipeManager"));
            }
        }
        return new Result(List.of(), List.of(), definitions, relations, List.of());
    }
}
