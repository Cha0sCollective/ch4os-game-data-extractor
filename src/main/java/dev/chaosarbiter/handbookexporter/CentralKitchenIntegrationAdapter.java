package dev.chaosarbiter.handbookexporter;

import net.minecraft.core.registries.BuiltInRegistries;
import net.minecraft.resources.ResourceLocation;
import net.minecraft.server.MinecraftServer;
import net.minecraft.world.item.crafting.RecipeHolder;

import java.lang.reflect.Method;
import java.util.ArrayList;
import java.util.Comparator;
import java.util.List;
import java.util.Map;
import java.util.function.Predicate;

/** Effective Farmer's Delight cutting-board conversions performed by Central Kitchen at machine use. */
final class CentralKitchenIntegrationAdapter implements MechanicAdapter {
    private static final String CONFIG = "plus.dragons.createcentralkitchen.config.CCKConfig";
    private static final String CONVERTERS =
            "plus.dragons.createcentralkitchen.integration.farmersdelight.recipe.CuttingBoardRecipeConverters";
    private static final String CREATE_TYPES = "com.simibubi.create.AllRecipeTypes";
    private static final ResourceLocation CUTTING = ResourceLocation.parse("farmersdelight:cutting");

    @Override public String id() { return "create_central_kitchen"; }
    @Override public String requiredModId() { return id(); }
    @Override public List<String> requiredModIds() { return List.of(id(), "farmersdelight", "create"); }
    @Override public List<String> requiredClassNames() { return List.of(CONFIG, CONVERTERS, CREATE_TYPES); }

    @Override
    public Result collect(MinecraftServer server, Predicate<ResourceLocation> inScope) {
        List<Map<String, ?>> configs = new ArrayList<>();
        List<Map<String, ?>> definitions = new ArrayList<>();
        List<Map<String, ?>> relations = new ArrayList<>();
        List<Map<String, ?>> diagnostics = new ArrayList<>();
        try {
            Object settings = Class.forName(CONFIG).getMethod("recipes").invoke(null);
            boolean saw = enabled(settings, "convertCuttingBoardRecipesToSawingRecipes", configs);
            boolean deployer = enabled(settings, "convertCuttingBoardRecipesToDeployingRecipes", configs);
            @SuppressWarnings("unchecked")
            Predicate<RecipeHolder<?>> automatable = (Predicate<RecipeHolder<?>>)
                    Class.forName(CREATE_TYPES).getField("CAN_BE_AUTOMATED").get(null);
            Method canSaw = Class.forName(CONVERTERS).getMethod("canSaw", RecipeHolder.class);
            String sawId = id() + ":cutting_board_to_saw";
            String deployerId = id() + ":cutting_board_to_deployer";
            int sawCount = 0;
            int deployerCount = 0;
            for (RecipeHolder<?> recipe : server.getRecipeManager().getRecipes().stream()
                    .filter(holder -> inScope.test(holder.id()))
                    .filter(holder -> CUTTING.equals(BuiltInRegistries.RECIPE_TYPE.getKey(holder.value().getType())))
                    .sorted(Comparator.comparing(holder -> holder.id().toString())).toList()) {
                if (!automatable.test(recipe)) {
                    continue;
                }
                if (saw && Boolean.TRUE.equals(canSaw.invoke(null, recipe))) {
                    relations.add(relation(recipe.id().toString(), sawId, "create:cutting"));
                    sawCount++;
                }
                if (deployer) {
                    relations.add(relation(recipe.id().toString(), deployerId, "create:deploying"));
                    deployerCount++;
                }
            }
            if (saw) {
                definitions.add(definition(sawId, "create:cutting", sawCount,
                        "iron knife accepted by source recipe"));
            }
            if (deployer) {
                definitions.add(definition(deployerId, "create:deploying", deployerCount,
                        "source tool is held by the deployer and is not consumed"));
            }
        } catch (ReflectiveOperationException | RuntimeException | LinkageError exception) {
            diagnostics.add(Map.of("subsystem", "mechanic_adapter:" + id() + ":conversion",
                    "status", "partial", "error_class", exception.getClass().getName()));
        }
        return new Result(List.of(), configs, definitions, relations, diagnostics);
    }

    private boolean enabled(Object settings, String field, List<Map<String, ?>> configs)
            throws ReflectiveOperationException {
        Object configValue = settings.getClass().getField(field).get(settings);
        Object value = configValue.getClass().getMethod("get").invoke(configValue);
        if (!(value instanceof Boolean enabled)) {
            throw new IllegalStateException("Central Kitchen setting is not boolean: " + field);
        }
        configs.add(AdapterRows.config(id(), id(), "common", "recipes", field, enabled,
                null, CONFIG + ".recipes()." + field + ".get"));
        return enabled;
    }

    private Map<String, Object> definition(String id, String targetType, int count, String toolCondition) {
        return AdapterRows.definition(id(), "runtime_recipe_conversion", id,
                Map.of("source_recipe_type", CUTTING.toString(), "target_recipe_type", targetType,
                        "eligible_source_recipes", count),
                Map.of("meaning", "runtime machine conversion of accepted cutting-board recipes",
                        "tool", toolCondition), null, null, null, CONVERTERS);
    }

    private Map<String, Object> relation(String recipeId, String conversionId, String targetType) {
        return AdapterRows.relation(id(), "recipe", recipeId, "can_run_as",
                "runtime_recipe_conversion", conversionId, Map.of("target_recipe_type", targetType),
                Map.of("source", "accepted recipe and effective Central Kitchen setting"), CONVERTERS);
    }
}
