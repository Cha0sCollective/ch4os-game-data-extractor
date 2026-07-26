package dev.chaosarbiter.handbookexporter;

import net.minecraft.SharedConstants;
import net.minecraft.core.Holder;
import net.minecraft.core.Registry;
import net.minecraft.core.component.TypedDataComponent;
import net.minecraft.core.registries.BuiltInRegistries;
import net.minecraft.resources.ResourceLocation;
import net.minecraft.server.MinecraftServer;
import net.minecraft.tags.TagKey;
import net.minecraft.world.item.BlockItem;
import net.minecraft.world.item.Item;
import net.minecraft.world.item.ItemStack;
import net.minecraft.world.item.crafting.RecipeHolder;
import net.minecraft.world.level.block.Block;
import net.minecraft.world.level.block.EntityBlock;
import net.minecraft.world.level.block.state.properties.Property;
import net.neoforged.fml.ModList;

import java.io.IOException;
import java.nio.file.Files;
import java.nio.file.Path;
import java.time.Instant;
import java.util.ArrayList;
import java.util.Comparator;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import java.util.Set;
import java.util.function.Predicate;

final class RuntimeSnapshotWriter {
    static final Set<String> SAMPLE_IDS = Set.of(
            "create:shaft",
            "create:cogwheel",
            "create:mechanical_press",
            "create:mechanical_mixer",
            "create:basin",
            "create:mechanical_pump",
            "create:fluid_tank",
            "create:steam_engine",
            "create:clipboard",
            "create:potato_cannon"
    );

    private final MinecraftServer server;
    private final ExporterSettings settings;
    private final Predicate<ResourceLocation> inScope;

    RuntimeSnapshotWriter(MinecraftServer server, ExporterSettings settings) {
        this.server = server;
        this.settings = settings;
        this.inScope = settings.scope().equals("full")
                ? id -> id.getNamespace().equals("create")
                : id -> SAMPLE_IDS.contains(id.toString());
    }

    Map<String, Object> write() throws IOException {
        Path output = settings.outputDirectory();
        Files.createDirectories(output);

        List<Map<String, ?>> mods = collectMods();
        List<Map<String, ?>> items = collectItems();
        List<Map<String, ?>> blocks = collectBlocks();
        List<Map<String, ?>> recipes = collectRecipes();
        List<Map<String, ?>> itemTags = collectTags(BuiltInRegistries.ITEM);
        List<Map<String, ?>> blockTags = collectTags(BuiltInRegistries.BLOCK);

        JsonFiles.writeJsonLines(output.resolve("mods.jsonl"), mods);
        JsonFiles.writeJsonLines(output.resolve("items.jsonl"), items);
        JsonFiles.writeJsonLines(output.resolve("blocks.jsonl"), blocks);
        JsonFiles.writeJsonLines(output.resolve("recipes.jsonl"), recipes);
        JsonFiles.writeJsonLines(output.resolve("item-tags.jsonl"), itemTags);
        JsonFiles.writeJsonLines(output.resolve("block-tags.jsonl"), blockTags);

        Map<String, Object> provenance = provenance(mods, items, blocks, recipes, itemTags, blockTags);
        JsonFiles.writeJson(output.resolve("provenance.json"), provenance);

        Map<String, Object> reconciliation = sampleReconciliation(items, blocks);
        JsonFiles.writeJson(output.resolve("sample-reconciliation.json"), reconciliation);

        List<Map<String, Object>> files = new ArrayList<>();
        try (var paths = Files.list(output)) {
            paths.filter(Files::isRegularFile)
                    .sorted()
                    .forEach(path -> {
                        try {
                            files.add(Map.of(
                                    "name", path.getFileName().toString(),
                                    "bytes", Files.size(path),
                                    "sha256", JsonFiles.sha256(path)
                            ));
                        } catch (IOException exception) {
                            throw new ExportFailure(exception);
                        }
                    });
        } catch (ExportFailure failure) {
            throw failure.ioException;
        }

        Map<String, Object> manifest = new LinkedHashMap<>();
        manifest.put("format", "create-handbook-runtime-export-v1");
        manifest.put("files", files);
        JsonFiles.writeJson(output.resolve("manifest.json"), manifest);
        return provenance;
    }

    private List<Map<String, ?>> collectMods() {
        List<Map<String, ?>> rows = new ArrayList<>();
        ModList.get().getMods().stream()
                .sorted(Comparator.comparing(info -> info.getModId()))
                .forEach(info -> {
                    Map<String, Object> row = new LinkedHashMap<>();
                    row.put("id", info.getModId());
                    row.put("name", info.getDisplayName());
                    row.put("version", info.getVersion().toString());
                    rows.add(row);
                });
        return rows;
    }

    private List<Map<String, ?>> collectItems() {
        List<Map<String, ?>> rows = new ArrayList<>();
        BuiltInRegistries.ITEM.entrySet().stream()
                .sorted(Map.Entry.comparingByKey(Comparator.comparing(key -> key.location().toString())))
                .forEach(entry -> {
                    ResourceLocation id = entry.getKey().location();
                    if (!inScope.test(id)) {
                        return;
                    }

                    Item item = entry.getValue();
                    ItemStack stack = item.getDefaultInstance();
                    Map<String, Object> row = new LinkedHashMap<>();
                    row.put("id", id.toString());
                    row.put("display_name", stack.getHoverName().getString());
                    row.put("description_id", item.getDescriptionId());
                    row.put("implementation_class", item.getClass().getName());
                    row.put("max_stack_size", stack.getMaxStackSize());
                    row.put("damageable", stack.isDamageableItem());
                    row.put("max_damage", stack.getMaxDamage());
                    row.put("rarity", stack.getRarity().name().toLowerCase());
                    row.put("default_component_ids", componentIds(stack));
                    if (item instanceof BlockItem blockItem) {
                        row.put("block_id", BuiltInRegistries.BLOCK.getKey(blockItem.getBlock()).toString());
                    } else {
                        row.put("block_id", null);
                    }
                    rows.add(row);
                });
        return rows;
    }

    private List<String> componentIds(ItemStack stack) {
        List<String> ids = new ArrayList<>();
        for (TypedDataComponent<?> component : stack.getComponents()) {
            ResourceLocation id = BuiltInRegistries.DATA_COMPONENT_TYPE.getKey(component.type());
            ids.add(id == null ? "<unregistered>" : id.toString());
        }
        ids.sort(String::compareTo);
        return ids;
    }

    private List<Map<String, ?>> collectBlocks() {
        List<Map<String, ?>> rows = new ArrayList<>();
        BuiltInRegistries.BLOCK.entrySet().stream()
                .sorted(Map.Entry.comparingByKey(Comparator.comparing(key -> key.location().toString())))
                .forEach(entry -> {
                    ResourceLocation id = entry.getKey().location();
                    if (!inScope.test(id)) {
                        return;
                    }

                    Block block = entry.getValue();
                    Map<String, Object> row = new LinkedHashMap<>();
                    row.put("id", id.toString());
                    row.put("description_id", block.getDescriptionId());
                    row.put("implementation_class", block.getClass().getName());
                    row.put("has_block_entity", block instanceof EntityBlock);
                    ResourceLocation itemId = BuiltInRegistries.ITEM.getKey(block.asItem());
                    row.put("item_id", itemId == null ? null : itemId.toString());
                    row.put("state_properties", stateProperties(block));
                    rows.add(row);
                });
        return rows;
    }

    private Map<String, List<String>> stateProperties(Block block) {
        Map<String, List<String>> values = new LinkedHashMap<>();
        block.getStateDefinition().getProperties().stream()
                .sorted(Comparator.comparing(Property::getName))
                .forEach(property -> values.put(
                        property.getName(),
                        property.getPossibleValues().stream()
                                .map(String::valueOf)
                                .sorted()
                                .toList()
                ));
        return values;
    }

    private List<Map<String, ?>> collectRecipes() {
        List<Map<String, ?>> rows = new ArrayList<>();
        server.getRecipeManager().getRecipes().stream()
                .sorted(Comparator.comparing(holder -> holder.id().toString()))
                .forEach(holder -> {
                    Map<String, Object> row = recipeRow(holder);
                    String id = (String) row.get("id");
                    String resultId = (String) row.get("result_item_id");
                    if (id.startsWith("create:") || (resultId != null && resultId.startsWith("create:"))) {
                        rows.add(row);
                    }
                });
        return rows;
    }

    private Map<String, Object> recipeRow(RecipeHolder<?> holder) {
        Map<String, Object> row = new LinkedHashMap<>();
        var recipe = holder.value();
        row.put("id", holder.id().toString());
        ResourceLocation type = BuiltInRegistries.RECIPE_TYPE.getKey(recipe.getType());
        ResourceLocation serializer = BuiltInRegistries.RECIPE_SERIALIZER.getKey(recipe.getSerializer());
        row.put("type", type == null ? null : type.toString());
        row.put("serializer", serializer == null ? null : serializer.toString());
        row.put("implementation_class", recipe.getClass().getName());
        try {
            ItemStack result = recipe.getResultItem(server.registryAccess());
            if (!result.isEmpty()) {
                row.put("result_item_id", BuiltInRegistries.ITEM.getKey(result.getItem()).toString());
                row.put("result_count", result.getCount());
            } else {
                row.put("result_item_id", null);
                row.put("result_count", null);
            }
        } catch (RuntimeException exception) {
            row.put("result_item_id", null);
            row.put("result_count", null);
            row.put("result_error", exception.getClass().getName());
        }
        return row;
    }

    private <T> List<Map<String, ?>> collectTags(Registry<T> registry) {
        List<Map<String, ?>> rows = new ArrayList<>();
        registry.getTagNames()
                .sorted(Comparator.comparing(tag -> tag.location().toString()))
                .forEach(tag -> registry.getTag(tag).ifPresent(named -> addTagRows(rows, tag, named)));
        return rows;
    }

    private <T> void addTagRows(
            List<Map<String, ?>> rows,
            TagKey<T> tag,
            Iterable<Holder<T>> holders
    ) {
        for (Holder<T> holder : holders) {
            holder.unwrapKey().ifPresent(key -> {
                ResourceLocation member = key.location();
                if (inScope.test(member)) {
                    rows.add(Map.of(
                            "tag", tag.location().toString(),
                            "member", member.toString()
                    ));
                }
            });
        }
    }

    private Map<String, Object> provenance(
            List<Map<String, ?>> mods,
            List<Map<String, ?>> items,
            List<Map<String, ?>> blocks,
            List<Map<String, ?>> recipes,
            List<Map<String, ?>> itemTags,
            List<Map<String, ?>> blockTags
    ) {
        Map<String, Object> row = new LinkedHashMap<>();
        row.put("format", "create-handbook-runtime-export-v1");
        row.put("generated_at_utc", Instant.now().toString());
        row.put("minecraft_version", SharedConstants.getCurrentVersion().getName());
        row.put("neoforge_version", modVersion("neoforge"));
        row.put("create_version", modVersion("create"));
        row.put("declared_pack_version", System.getProperty("handbook.export.packVersion"));
        row.put("scope", settings.scope());
        row.put("sample_ids", SAMPLE_IDS.stream().sorted().toList());
        row.put("dedicated_server", true);
        row.put("connected_players", server.getPlayerList().getPlayerCount());
        row.put("raw_assets_exported", false);
        row.put("network_requests_performed", false);
        row.put("counts", Map.of(
                "mods", mods.size(),
                "items", items.size(),
                "blocks", blocks.size(),
                "recipes", recipes.size(),
                "item_tag_memberships", itemTags.size(),
                "block_tag_memberships", blockTags.size()
        ));
        return row;
    }

    private String modVersion(String modId) {
        return ModList.get().getModContainerById(modId)
                .map(container -> container.getModInfo().getVersion().toString())
                .orElse("<missing>");
    }

    private Map<String, Object> sampleReconciliation(
            List<Map<String, ?>> items,
            List<Map<String, ?>> blocks
    ) {
        Set<String> itemIds = items.stream().map(row -> (String) row.get("id")).collect(java.util.stream.Collectors.toSet());
        Set<String> blockIds = blocks.stream().map(row -> (String) row.get("id")).collect(java.util.stream.Collectors.toSet());
        List<String> missingItems = SAMPLE_IDS.stream().filter(id -> !itemIds.contains(id)).sorted().toList();
        List<String> missingBlocks = SAMPLE_IDS.stream().filter(id -> !blockIds.contains(id)).sorted().toList();

        Map<String, Object> row = new LinkedHashMap<>();
        row.put("requested_ids", SAMPLE_IDS.stream().sorted().toList());
        row.put("found_item_ids", itemIds.stream().sorted().toList());
        row.put("found_block_ids", blockIds.stream().sorted().toList());
        row.put("missing_item_ids", missingItems);
        row.put("missing_block_ids", missingBlocks);
        return row;
    }

    private static final class ExportFailure extends RuntimeException {
        private final IOException ioException;

        private ExportFailure(IOException ioException) {
            super(ioException);
            this.ioException = ioException;
        }
    }
}
