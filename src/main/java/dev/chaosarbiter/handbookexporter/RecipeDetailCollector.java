package dev.chaosarbiter.handbookexporter;

import com.google.gson.JsonArray;
import com.google.gson.JsonElement;
import com.google.gson.JsonObject;
import com.google.gson.JsonParser;
import com.mojang.serialization.JsonOps;
import net.minecraft.core.registries.BuiltInRegistries;
import net.minecraft.resources.ResourceLocation;
import net.minecraft.server.MinecraftServer;
import net.minecraft.server.packs.resources.Resource;
import net.minecraft.world.item.ItemStack;
import net.minecraft.world.item.crafting.Ingredient;
import net.minecraft.world.item.crafting.Recipe;
import net.minecraft.world.item.crafting.RecipeHolder;
import net.minecraft.world.item.crafting.ShapedRecipe;

import java.io.IOException;
import java.lang.reflect.InvocationTargetException;
import java.lang.reflect.Method;
import java.nio.charset.StandardCharsets;
import java.security.MessageDigest;
import java.security.NoSuchAlgorithmException;
import java.util.ArrayList;
import java.util.HexFormat;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import java.util.Optional;

/** Additive detail rows; the original recipes.jsonl header contract stays unchanged. */
final class RecipeDetailCollector {
    private static final int MAX_SOURCE_BYTES = 2 * 1024 * 1024;
    private static final int MAX_INGREDIENT_OPTIONS = 256;
    private final MinecraftServer server;

    RecipeDetailCollector(MinecraftServer server) {
        this.server = server;
    }

    Map<String, Object> collect(RecipeHolder<?> holder, Map<String, ?> header) {
        Recipe<?> recipe = holder.value();
        Map<String, Object> row = new LinkedHashMap<>();
        row.put("format", "ch4os-recipe-detail-v1");
        row.putAll(header);
        row.put("recipe_namespace", holder.id().getNamespace());
        row.put("group", recipe.getGroup());
        row.put("special", recipe.isSpecial());
        row.put("show_notification", recipe.showNotification());

        JsonElement source = sourceJson(holder.id(), row);
        JsonElement encoded = encodedRecipe(recipe, row);
        JsonObject definition = source != null && source.isJsonObject()
                ? source.getAsJsonObject()
                : encoded != null && encoded.isJsonObject() ? encoded.getAsJsonObject() : null;
        row.put("source_json", source);
        row.put("codec_json", encoded);
        List<Map<String, Object>> runtimeIngredients = runtimeIngredients(recipe, row);
        row.put("runtime_ingredients", runtimeIngredients);

        List<Map<String, Object>> itemInputs = new ArrayList<>();
        List<Map<String, Object>> fluidInputs = new ArrayList<>();
        List<Map<String, Object>> itemOutputs = new ArrayList<>();
        List<Map<String, Object>> fluidOutputs = new ArrayList<>();
        List<Map<String, Object>> catalysts = new ArrayList<>();
        if (definition != null) {
            collectSpecs(definition, "ingredient", itemInputs, fluidInputs, false);
            collectSpecs(definition, "ingredients", itemInputs, fluidInputs, false);
            collectSpecs(definition, "key", itemInputs, fluidInputs, false);
            collectSpecs(definition, "inputs", itemInputs, fluidInputs, false);
            collectSpecs(definition, "input", itemInputs, fluidInputs, false);
            collectSpecs(definition, "template", itemInputs, fluidInputs, false);
            collectSpecs(definition, "base", itemInputs, fluidInputs, false);
            collectSpecs(definition, "addition", itemInputs, fluidInputs, false);
            collectSpecs(definition, "result", itemOutputs, fluidOutputs, true);
            collectSpecs(definition, "results", itemOutputs, fluidOutputs, true);
            collectSpecs(definition, "catalyst", catalysts, fluidInputs, false);
            collectSpecs(definition, "catalysts", catalysts, fluidInputs, false);
            applyPatternQuantities(definition, itemInputs);
        }
        if (itemInputs.isEmpty()) {
            for (Map<String, Object> ingredient : runtimeIngredients) {
                Object encodedIngredient = ingredient.get("definition");
                if (encodedIngredient instanceof JsonElement json) {
                    collectSpec(json, "runtime_ingredients[" + ingredient.get("index") + "]",
                            itemInputs, fluidInputs, false);
                }
            }
        }
        List<Map<String, Object>> runtimeItemOutputs = runtimeItemOutputs(recipe, row);
        row.put("runtime_item_outputs", runtimeItemOutputs);
        if (itemOutputs.isEmpty()) {
            itemOutputs.addAll(runtimeItemOutputs);
        }
        if (itemOutputs.isEmpty() && header.get("result_item_id") instanceof String resultId) {
            Map<String, Object> result = new LinkedHashMap<>();
            result.put("path", "runtime_result");
            result.put("kind", "item");
            result.put("id", resultId);
            result.put("quantity", header.get("result_count"));
            result.put("origin", "getResultItem");
            itemOutputs.add(result);
        }
        List<Map<String, Object>> runtimeFluidOutputs = runtimeFluidOutputs(recipe, row);
        row.put("runtime_fluid_outputs", runtimeFluidOutputs);
        if (fluidOutputs.isEmpty()) {
            fluidOutputs.addAll(runtimeFluidOutputs);
        }
        row.put("item_inputs", itemInputs);
        row.put("fluid_inputs", fluidInputs);
        row.put("item_outputs", itemOutputs);
        row.put("fluid_outputs", fluidOutputs);
        row.put("catalysts", catalysts);
        row.put("sequence", collectSequence(definition));
        row.put("processing_parameters", processingParameters(definition));
        row.put("runtime_processing", runtimeProcessing(recipe));
        row.put("conditions", definition == null ? null : firstPresent(definition, "neoforge:conditions", "conditions"));
        row.put("layout", layout(recipe, definition));
        row.put("dynamic_result", header.get("result_item_id") == null);
        boolean hasInputs = !itemInputs.isEmpty() || !fluidInputs.isEmpty();
        boolean hasOutputs = !itemOutputs.isEmpty() || !fluidOutputs.isEmpty();
        row.put("input_status", hasInputs ? "collected" : "not_exposed_or_not_applicable");
        row.put("output_status", hasOutputs ? "collected" : "not_exposed_or_not_applicable");
        row.put("semantic_status", knownVanillaRecipe(header) && hasInputs && hasOutputs
                ? "core_fields" : "partial_or_dynamic");
        row.put("remaining_items_status", "not_collected_without_recipe_input");
        return row;
    }

    private JsonElement sourceJson(ResourceLocation id, Map<String, Object> row) {
        ResourceLocation resourceId = ResourceLocation.fromNamespaceAndPath(
                id.getNamespace(), "recipe/" + id.getPath() + ".json"
        );
        row.put("source_resource_id", resourceId.toString());
        Optional<Resource> found = server.getResourceManager().getResource(resourceId);
        if (found.isEmpty()) {
            row.put("source_status", "unavailable");
            row.put("source_pack_id", null);
            return null;
        }
        Resource resource = found.get();
        row.put("source_pack_id", resource.sourcePackId());
        try (var stream = resource.open()) {
            byte[] bytes = stream.readNBytes(MAX_SOURCE_BYTES + 1);
            if (bytes.length > MAX_SOURCE_BYTES) {
                row.put("source_status", "too_large");
                return null;
            }
            row.put("source_sha256", sha256(bytes));
            JsonElement json = JsonParser.parseString(new String(bytes, StandardCharsets.UTF_8));
            row.put("source_status", "captured");
            return json;
        } catch (IOException | RuntimeException exception) {
            row.put("source_status", "failed");
            row.put("source_error", exception.getClass().getSimpleName());
            return null;
        }
    }

    private JsonElement encodedRecipe(Recipe<?> recipe, Map<String, Object> row) {
        try {
            JsonElement encoded = Recipe.CODEC.encodeStart(
                    server.registryAccess().createSerializationContext(JsonOps.INSTANCE), recipe
            ).getOrThrow(IllegalStateException::new);
            row.put("codec_status", "encoded");
            return encoded;
        } catch (RuntimeException exception) {
            row.put("codec_status", "unsupported");
            row.put("codec_error", exception.getClass().getSimpleName() + ": " + exception.getMessage());
            return null;
        }
    }

    private List<Map<String, Object>> runtimeIngredients(Recipe<?> recipe, Map<String, Object> row) {
        List<Map<String, Object>> ingredients = new ArrayList<>();
        try {
            int index = 0;
            for (Ingredient ingredient : recipe.getIngredients()) {
                Map<String, Object> entry = new LinkedHashMap<>();
                entry.put("index", index++);
                entry.put("custom", ingredient.isCustom());
                entry.put("empty", ingredient.isEmpty());
                try {
                    entry.put("definition", Ingredient.CODEC.encodeStart(
                            server.registryAccess().createSerializationContext(JsonOps.INSTANCE), ingredient
                    ).getOrThrow(IllegalStateException::new));
                    entry.put("definition_status", "encoded");
                } catch (RuntimeException exception) {
                    entry.put("definition_status", "unsupported");
                    entry.put("definition_error", exception.getClass().getSimpleName());
                }
                try {
                    ItemStack[] options = ingredient.getItems();
                    List<Map<String, Object>> choices = new ArrayList<>();
                    for (int choice = 0; choice < Math.min(options.length, MAX_INGREDIENT_OPTIONS); choice++) {
                        ItemStack stack = options[choice];
                        if (!stack.isEmpty()) {
                            choices.add(Map.of(
                                    "item_id", BuiltInRegistries.ITEM.getKey(stack.getItem()).toString(),
                                    "count", stack.getCount()
                            ));
                        }
                    }
                    entry.put("item_options", choices);
                    entry.put("option_count", options.length);
                    entry.put("options_status", options.length > MAX_INGREDIENT_OPTIONS ? "truncated" : "complete");
                } catch (RuntimeException exception) {
                    entry.put("options_status", "unsupported");
                    entry.put("options_error", exception.getClass().getSimpleName());
                }
                ingredients.add(entry);
            }
            row.put("runtime_ingredients_status", "collected");
        } catch (RuntimeException exception) {
            row.put("runtime_ingredients_status", "unsupported");
            row.put("runtime_ingredients_error", exception.getClass().getSimpleName());
        }
        return ingredients;
    }

    private List<Map<String, Object>> runtimeItemOutputs(Recipe<?> recipe, Map<String, Object> row) {
        List<Map<String, Object>> outputs = new ArrayList<>();
        Object value = invokeOptional(recipe, "getRollableResults", row);
        if (!(value instanceof List<?> results)) {
            return outputs;
        }
        int index = 0;
        for (Object result : results) {
            try {
                Object stackValue = result.getClass().getMethod("getStack").invoke(result);
                Object chanceValue = result.getClass().getMethod("getChance").invoke(result);
                if (stackValue instanceof ItemStack stack && !stack.isEmpty()) {
                    Map<String, Object> entry = new LinkedHashMap<>();
                    entry.put("path", "runtime_item_outputs[" + index + "]");
                    entry.put("kind", "item");
                    entry.put("id", BuiltInRegistries.ITEM.getKey(stack.getItem()).toString());
                    entry.put("quantity", stack.getCount());
                    entry.put("chance", chanceValue);
                    entry.put("origin", "getRollableResults");
                    outputs.add(entry);
                }
            } catch (ReflectiveOperationException | RuntimeException exception) {
                row.put("runtime_item_outputs_error", exception.getClass().getSimpleName());
            }
            index++;
        }
        return outputs;
    }

    private List<Map<String, Object>> runtimeFluidOutputs(Recipe<?> recipe, Map<String, Object> row) {
        List<Map<String, Object>> outputs = new ArrayList<>();
        Object value = invokeOptional(recipe, "getFluidResults", row);
        if (!(value instanceof List<?> results)) {
            return outputs;
        }
        int index = 0;
        for (Object result : results) {
            if (result instanceof net.neoforged.neoforge.fluids.FluidStack stack && !stack.isEmpty()) {
                Map<String, Object> entry = new LinkedHashMap<>();
                entry.put("path", "runtime_fluid_outputs[" + index + "]");
                entry.put("kind", "fluid");
                entry.put("id", BuiltInRegistries.FLUID.getKey(stack.getFluid()).toString());
                entry.put("quantity", stack.getAmount());
                entry.put("origin", "getFluidResults");
                outputs.add(entry);
            }
            index++;
        }
        return outputs;
    }

    private Map<String, Object> runtimeProcessing(Recipe<?> recipe) {
        Map<String, Object> facts = new LinkedHashMap<>();
        Object duration = invokeOptional(recipe, "getProcessingDuration", facts);
        if (duration instanceof Number) {
            facts.put("duration", duration);
            if (inheritsFrom(recipe.getClass(), "com.simibubi.create.content.processing.recipe.ProcessingRecipe")) {
                facts.put("duration_unit", "ticks");
            }
        }
        Object heat = invokeOptional(recipe, "getRequiredHeat", facts);
        if (heat != null) {
            facts.put("required_heat", heat.toString());
        }
        return facts;
    }

    private boolean inheritsFrom(Class<?> type, String className) {
        for (Class<?> current = type; current != null; current = current.getSuperclass()) {
            if (current.getName().equals(className)) {
                return true;
            }
        }
        return false;
    }

    private Object invokeOptional(Recipe<?> recipe, String methodName, Map<String, Object> diagnostics) {
        try {
            Method method = recipe.getClass().getMethod(methodName);
            return method.invoke(recipe);
        } catch (NoSuchMethodException exception) {
            return null;
        } catch (IllegalAccessException | InvocationTargetException | RuntimeException exception) {
            diagnostics.put(methodName + "_error", exception.getClass().getSimpleName());
            return null;
        }
    }

    private void collectSpecs(JsonObject definition, String field, List<Map<String, Object>> items,
                              List<Map<String, Object>> fluids, boolean output) {
        if (definition.has(field)) {
            collectSpec(definition.get(field), field, items, fluids, output);
        }
    }

    private void collectSpec(JsonElement value, String path, List<Map<String, Object>> items,
                             List<Map<String, Object>> fluids, boolean output) {
        if (value == null || value.isJsonNull()) {
            return;
        }
        if (value.isJsonArray()) {
            JsonArray array = value.getAsJsonArray();
            for (int index = 0; index < array.size(); index++) {
                collectSpec(array.get(index), path + "[" + index + "]", items, fluids, output);
            }
            return;
        }
        if (!value.isJsonObject()) {
            return;
        }
        JsonObject object = value.getAsJsonObject();
        String type = string(object, "type");
        String fluid = string(object, "fluid");
        String fluidTag = string(object, "fluid_tag");
        String tag = string(object, "tag");
        String item = string(object, "item");
        String id = string(object, "id");
        ResourceLocation outputId = id == null ? null : ResourceLocation.tryParse(id);
        boolean fluidKind = fluid != null || fluidTag != null
                || type != null && (type.equals("neoforge:tag") || type.equals("neoforge:single"))
                || output && hasNumber(object, "amount") && outputId != null
                && BuiltInRegistries.FLUID.containsKey(outputId);

        String identity = fluid != null ? fluid : fluidTag != null ? fluidTag
                : item != null ? item : id != null ? id : tag;
        if (identity != null) {
            Map<String, Object> entry = new LinkedHashMap<>();
            entry.put("path", path);
            entry.put("kind", fluidKind ? (fluidTag != null || tag != null ? "fluid_tag" : "fluid")
                    : tag != null ? ("neoforge:block_tag".equals(type) ? "block_tag" : "item_tag") : "item");
            entry.put("id", identity);
            entry.put("quantity", number(object, fluidKind ? "amount" : "count"));
            entry.put("chance", number(object, "chance"));
            entry.put("definition", object);
            (fluidKind ? fluids : items).add(entry);
            return;
        }
        for (var member : object.entrySet()) {
            if (member.getValue().isJsonArray() || member.getValue().isJsonObject()) {
                collectSpec(member.getValue(), path + "." + member.getKey(), items, fluids, output);
            }
        }
    }

    private List<Map<String, Object>> collectSequence(JsonObject definition) {
        List<Map<String, Object>> steps = new ArrayList<>();
        if (definition == null || !definition.has("sequence") || !definition.get("sequence").isJsonArray()) {
            return steps;
        }
        JsonArray sequence = definition.getAsJsonArray("sequence");
        for (int index = 0; index < sequence.size(); index++) {
            if (!sequence.get(index).isJsonObject()) {
                continue;
            }
            JsonObject step = sequence.get(index).getAsJsonObject();
            Map<String, Object> entry = new LinkedHashMap<>();
            entry.put("index", index);
            entry.put("type", string(step, "type"));
            List<Map<String, Object>> itemsIn = new ArrayList<>();
            List<Map<String, Object>> fluidsIn = new ArrayList<>();
            List<Map<String, Object>> itemsOut = new ArrayList<>();
            List<Map<String, Object>> fluidsOut = new ArrayList<>();
            collectSpecs(step, "ingredient", itemsIn, fluidsIn, false);
            collectSpecs(step, "ingredients", itemsIn, fluidsIn, false);
            collectSpecs(step, "result", itemsOut, fluidsOut, true);
            collectSpecs(step, "results", itemsOut, fluidsOut, true);
            entry.put("item_inputs", itemsIn);
            entry.put("fluid_inputs", fluidsIn);
            entry.put("item_outputs", itemsOut);
            entry.put("fluid_outputs", fluidsOut);
            entry.put("definition", step);
            steps.add(entry);
        }
        return steps;
    }

    private void applyPatternQuantities(JsonObject definition, List<Map<String, Object>> itemInputs) {
        if (!definition.has("pattern") || !definition.get("pattern").isJsonArray()) {
            return;
        }
        Map<String, Integer> counts = new LinkedHashMap<>();
        for (JsonElement line : definition.getAsJsonArray("pattern")) {
            if (line.isJsonPrimitive() && line.getAsJsonPrimitive().isString()) {
                for (char symbol : line.getAsString().toCharArray()) {
                    if (symbol != ' ') {
                        counts.merge(String.valueOf(symbol), 1, Integer::sum);
                    }
                }
            }
        }
        for (Map<String, Object> input : itemInputs) {
            String path = (String) input.get("path");
            if (path != null && path.startsWith("key.") && path.length() >= 5) {
                Integer quantity = counts.get(path.substring(4, 5));
                if (quantity != null) {
                    input.put("quantity", quantity);
                }
            }
        }
    }

    private Map<String, JsonElement> processingParameters(JsonObject definition) {
        Map<String, JsonElement> parameters = new LinkedHashMap<>();
        if (definition == null) {
            return parameters;
        }
        for (String field : List.of("processing_time", "processingTime", "cookingtime", "cookingTime",
                "heat_requirement", "heatRequirement", "energy", "stress", "experience", "loops")) {
            if (definition.has(field)) {
                parameters.put(field, definition.get(field));
            }
        }
        return parameters;
    }

    private Map<String, Object> layout(Recipe<?> recipe, JsonObject definition) {
        Map<String, Object> layout = new LinkedHashMap<>();
        if (recipe instanceof ShapedRecipe shaped) {
            layout.put("width", shaped.getWidth());
            layout.put("height", shaped.getHeight());
        }
        if (definition != null) {
            if (definition.has("pattern")) {
                layout.put("pattern", definition.get("pattern"));
            }
            if (definition.has("key")) {
                layout.put("key", definition.get("key"));
            }
        }
        return layout;
    }

    private boolean knownVanillaRecipe(Map<String, ?> header) {
        Object serializer = header.get("serializer");
        return serializer instanceof String id && id.startsWith("minecraft:");
    }

    private static JsonElement firstPresent(JsonObject object, String... fields) {
        for (String field : fields) {
            if (object.has(field)) {
                return object.get(field);
            }
        }
        return null;
    }

    private static String string(JsonObject object, String field) {
        JsonElement value = object.get(field);
        return value != null && value.isJsonPrimitive() && value.getAsJsonPrimitive().isString()
                ? value.getAsString() : null;
    }

    private static boolean hasNumber(JsonObject object, String field) {
        JsonElement value = object.get(field);
        return value != null && value.isJsonPrimitive() && value.getAsJsonPrimitive().isNumber();
    }

    private static Number number(JsonObject object, String field) {
        return hasNumber(object, field) ? object.get(field).getAsNumber() : null;
    }

    private static String sha256(byte[] bytes) {
        try {
            return HexFormat.of().formatHex(MessageDigest.getInstance("SHA-256").digest(bytes));
        } catch (NoSuchAlgorithmException exception) {
            throw new IllegalStateException("SHA-256 unavailable", exception);
        }
    }
}
