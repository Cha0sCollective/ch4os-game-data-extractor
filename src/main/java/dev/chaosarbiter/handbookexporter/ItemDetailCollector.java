package dev.chaosarbiter.handbookexporter;

import com.google.gson.JsonElement;
import com.mojang.serialization.Codec;
import com.mojang.serialization.JsonOps;
import net.minecraft.core.component.TypedDataComponent;
import net.minecraft.core.registries.BuiltInRegistries;
import net.minecraft.resources.ResourceLocation;
import net.minecraft.server.MinecraftServer;
import net.minecraft.world.item.BlockItem;
import net.minecraft.world.item.Item;
import net.minecraft.world.item.ItemStack;
import net.minecraft.world.level.block.EntityBlock;
import net.minecraft.world.level.block.state.BlockState;

import java.util.ArrayList;
import java.util.Comparator;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import java.util.function.Predicate;

/** Optional facts about a default registered item; the v1 items file is unchanged. */
final class ItemDetailCollector {
    private final MinecraftServer server;
    private final Predicate<ResourceLocation> inScope;

    ItemDetailCollector(MinecraftServer server, Predicate<ResourceLocation> inScope) {
        this.server = server;
        this.inScope = inScope;
    }

    List<Map<String, ?>> collect() {
        List<Map<String, ?>> rows = new ArrayList<>();
        BuiltInRegistries.ITEM.entrySet().stream()
                .sorted(Map.Entry.comparingByKey(Comparator.comparing(key -> key.location().toString())))
                .forEach(entry -> {
                    ResourceLocation id = entry.getKey().location();
                    if (inScope.test(id)) {
                        rows.add(itemRow(id, entry.getValue()));
                    }
                });
        return rows;
    }

    private Map<String, Object> itemRow(ResourceLocation id, Item item) {
        Map<String, Object> row = new LinkedHashMap<>();
        row.put("format", "ch4os-item-detail-v1");
        row.put("id", id.toString());
        List<Map<String, Object>> components = new ArrayList<>();
        for (TypedDataComponent<?> component : item.getDefaultInstance().getComponents()) {
            components.add(componentRow(component));
        }
        components.sort(Comparator.comparing(component -> (String) component.get("id")));
        row.put("default_components", components);
        row.put("component_status", components.stream().allMatch(component -> "captured".equals(component.get("status")))
                ? "collected" : "partial");

        if (item instanceof BlockItem blockItem) {
            BlockState state = blockItem.getBlock().defaultBlockState();
            List<String> types = BuiltInRegistries.BLOCK_ENTITY_TYPE.entrySet().stream()
                    .filter(entry -> entry.getValue().isValid(state))
                    .map(entry -> entry.getKey().location().toString())
                    .sorted()
                    .toList();
            row.put("block_entity_type_ids", types);
            row.put("block_entity_type_status", !types.isEmpty() ? "collected"
                    : blockItem.getBlock() instanceof EntityBlock ? "unavailable" : "not_applicable");
        } else {
            row.put("block_entity_type_ids", List.of());
            row.put("block_entity_type_status", "not_applicable");
        }
        return row;
    }

    private <T> Map<String, Object> componentRow(TypedDataComponent<T> component) {
        Map<String, Object> row = new LinkedHashMap<>();
        ResourceLocation id = BuiltInRegistries.DATA_COMPONENT_TYPE.getKey(component.type());
        row.put("id", id == null ? "<unregistered>" : id.toString());
        Codec<T> codec = component.type().codec();
        if (codec == null) {
            row.put("status", "unsupported_non_persistent");
            return row;
        }
        try {
            JsonElement value = codec.encodeStart(
                    server.registryAccess().createSerializationContext(JsonOps.INSTANCE), component.value()
            ).getOrThrow(IllegalStateException::new);
            row.put("value", value);
            row.put("status", "captured");
        } catch (RuntimeException exception) {
            row.put("status", "failed");
            row.put("error", exception.getClass().getSimpleName());
        }
        return row;
    }
}
