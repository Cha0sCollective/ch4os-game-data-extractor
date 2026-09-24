package dev.chaosarbiter.handbookexporter;

import com.mojang.logging.LogUtils;
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
import net.neoforged.fml.loading.FMLPaths;
import org.slf4j.Logger;

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
import java.util.TreeMap;
import java.util.TreeSet;
import java.util.function.Predicate;

final class RuntimeSnapshotWriter {
    private static final Logger LOGGER = LogUtils.getLogger();

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
        this.inScope = switch (settings.scope()) {
            case "pack" -> id -> true;
            case "full" -> id -> id.getNamespace().equals("create");
            default -> id -> SAMPLE_IDS.contains(id.toString());
        };
    }

    Map<String, Object> write() throws IOException {
        Path output = settings.outputDirectory();
        Files.createDirectories(output);

        progress(1, "Collecting loaded mod identities.");
        List<Map<String, ?>> mods = collectMods();
        progressCount("loaded mods", mods.size());

        progress(2, "Collecting in-scope item registrations and default stack facts.");
        List<Map<String, ?>> items = collectItems();
        progressCount("items", items.size());
        List<Map<String, ?>> itemDetails = new ItemDetailCollector(server, inScope).collect();
        if (itemDetails.size() != items.size()) {
            throw new IllegalStateException("item detail count differs from item count");
        }
        progressCount("item detail rows", itemDetails.size());

        progress(3, "Collecting corresponding block registrations and state properties.");
        List<Map<String, ?>> blocks = collectBlocks();
        progressCount("blocks", blocks.size());

        progress(4, "Collecting effective recipe headers and detailed definitions after datapack loading.");
        List<Map<String, ?>> recipes = collectRecipes();
        progressCount("recipes", recipes.size());
        List<Map<String, ?>> recipeDetails = collectRecipeDetails(recipes);
        progressCount("recipe detail rows", recipeDetails.size());
        List<Map<String, ?>> unloadedRecipeResources = settings.scope().equals("pack")
                ? UnloadedRecipeResources.collect(server)
                : List.of();
        progressCount("unloaded recipe resources (including conditional skips)", unloadedRecipeResources.size());

        progress(5, "Resolving loaded item and block tag memberships.");
        List<Map<String, ?>> itemTags = collectTags(BuiltInRegistries.ITEM);
        List<Map<String, ?>> blockTags = collectTags(BuiltInRegistries.BLOCK);
        LOGGER.info(
                "[HANDBOOK EXPORT] Collected {} item-tag and {} block-tag memberships.",
                itemTags.size(),
                blockTags.size()
        );

        progress(6, "Enumerating built-in and datapack-backed registry identities and tags.");
        RegistryInventory registryInventory = collectRegistryInventory();
        progressCount("registry summaries", registryInventory.summaries().size());
        progressCount("registry entries", registryInventory.entries().size());
        progressCount("registry tag memberships", registryInventory.tags().size());

        progress(7, "Reading effective mechanic facts through installed-mod adapters.");
        MechanicAdapter.Result introspection = MechanicAdapters.collect(server, inScope);
        progressCount("effective mechanics facts", introspection.mechanics().size());
        progressCount("effective server/common configuration values", introspection.configs().size());

        progress(8, "Inventorying exact installed mod artifacts without extracting archive content.");
        InstalledArtifactInventory.Result artifactInventory = settings.scope().equals("pack")
                ? InstalledArtifactInventory.collect(FMLPaths.GAMEDIR.get())
                : InstalledArtifactInventory.Result.empty();
        progressCount("installed mod artifacts", artifactInventory.artifacts().size());
        progressCount("safe archive entry locations", artifactInventory.entries().size());
        progressCount("mixin configurations", artifactInventory.mixinConfigs().size());
        progressCount("Java service descriptors", artifactInventory.services().size());
        if (!artifactInventory.diagnostics().isEmpty()) {
            LOGGER.warn(
                    "[HANDBOOK EXPORT] Artifact inventory preserved {} diagnostic row(s) for review.",
                    artifactInventory.diagnostics().size()
            );
        }

        progress(9, "Writing JSONL evidence files with non-overwriting writes.");
        JsonFiles.writeJsonLines(output.resolve("mods.jsonl"), mods);
        JsonFiles.writeJsonLines(output.resolve("items.jsonl"), items);
        JsonFiles.writeJsonLines(output.resolve("item-details.jsonl"), itemDetails);
        JsonFiles.writeJsonLines(output.resolve("blocks.jsonl"), blocks);
        JsonFiles.writeJsonLines(output.resolve("recipes.jsonl"), recipes);
        JsonFiles.writeJsonLines(output.resolve("recipe-details.jsonl"), recipeDetails);
        JsonFiles.writeJsonLines(output.resolve("unloaded-recipe-resources.jsonl"), unloadedRecipeResources);
        JsonFiles.writeJsonLines(output.resolve("item-tags.jsonl"), itemTags);
        JsonFiles.writeJsonLines(output.resolve("block-tags.jsonl"), blockTags);
        JsonFiles.writeJsonLines(output.resolve("registry-summaries.jsonl"), registryInventory.summaries());
        JsonFiles.writeJsonLines(output.resolve("registry-entries.jsonl"), registryInventory.entries());
        JsonFiles.writeJsonLines(output.resolve("registry-tags.jsonl"), registryInventory.tags());
        JsonFiles.writeJsonLines(output.resolve("mechanics.jsonl"), introspection.mechanics());
        JsonFiles.writeJsonLines(output.resolve("config-values.jsonl"), introspection.configs());
        JsonFiles.writeJsonLines(
                output.resolve("introspection-diagnostics.jsonl"),
                introspection.diagnostics()
        );
        JsonFiles.writeJsonLines(
                output.resolve("installed-artifacts.jsonl"),
                artifactInventory.artifacts()
        );
        JsonFiles.writeJsonLines(
                output.resolve("artifact-entries.jsonl"),
                artifactInventory.entries()
        );
        JsonFiles.writeJsonLines(
                output.resolve("mixin-configs.jsonl"),
                artifactInventory.mixinConfigs()
        );
        JsonFiles.writeJsonLines(
                output.resolve("service-providers.jsonl"),
                artifactInventory.services()
        );
        JsonFiles.writeJsonLines(
                output.resolve("artifact-diagnostics.jsonl"),
                artifactInventory.diagnostics()
        );

        progress(10, "Writing provenance and sample reconciliation.");
        Map<String, Object> provenance = provenance(
                mods,
                items,
                blocks,
                recipes,
                recipeDetails,
                unloadedRecipeResources,
                itemTags,
                blockTags,
                registryInventory,
                introspection.mechanics(),
                introspection.configs(),
                artifactInventory
        );
        JsonFiles.writeJson(output.resolve("provenance.json"), provenance);

        Map<String, Object> reconciliation = sampleReconciliation(items, blocks);
        JsonFiles.writeJson(output.resolve("sample-reconciliation.json"), reconciliation);

        progress(11, "Hashing the completed evidence files.");
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
        progress(12, "Writing the final manifest.");
        JsonFiles.writeJson(output.resolve("manifest.json"), manifest);
        LOGGER.info("[HANDBOOK EXPORT] All 12 collection stages completed.");
        return provenance;
    }

    private void progress(int stage, String message) {
        LOGGER.info("[HANDBOOK EXPORT] Data stage {}/12 - {}", stage, message);
    }

    private void progressCount(String label, int count) {
        LOGGER.info("[HANDBOOK EXPORT] Collected {} {}.", count, label);
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
                    if (settings.scope().equals("pack")
                            || id.startsWith("create:")
                            || (resultId != null && resultId.startsWith("create:"))) {
                        rows.add(row);
                    }
                });
        return rows;
    }

    private List<Map<String, ?>> collectRecipeDetails(List<Map<String, ?>> recipes) {
        RecipeDetailCollector collector = new RecipeDetailCollector(server);
        List<Map<String, ?>> rows = new ArrayList<>();
        for (Map<String, ?> header : recipes) {
            ResourceLocation id = ResourceLocation.parse((String) header.get("id"));
            server.getRecipeManager().byKey(id).ifPresent(holder -> rows.add(collector.collect(holder, header)));
        }
        if (rows.size() != recipes.size()) {
            throw new IllegalStateException("effective recipe detail count differs from header count");
        }
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

    private RegistryInventory collectRegistryInventory() {
        Map<String, RegistryDescriptor> registries = new TreeMap<>();
        BuiltInRegistries.REGISTRY.entrySet().forEach(entry -> addRegistry(
                registries,
                entry.getKey().location(),
                entry.getValue(),
                "built_in"
        ));
        server.registryAccess().registries().forEach(entry -> addRegistry(
                registries,
                entry.key().location(),
                entry.value(),
                "server_registry_access"
        ));

        List<Map<String, ?>> summaries = new ArrayList<>();
        List<Map<String, ?>> entries = new ArrayList<>();
        List<Map<String, ?>> tags = new ArrayList<>();
        registries.forEach((registryId, descriptor) -> collectRegistry(
                registryId,
                descriptor.registry,
                descriptor.accessSources,
                summaries,
                entries,
                tags
        ));
        return new RegistryInventory(summaries, entries, tags);
    }

    private void addRegistry(
            Map<String, RegistryDescriptor> registries,
            ResourceLocation registryId,
            Registry<?> registry,
            String accessSource
    ) {
        RegistryDescriptor descriptor = registries.computeIfAbsent(
                registryId.toString(),
                ignored -> new RegistryDescriptor(registry)
        );
        descriptor.accessSources.add(accessSource);
    }

    private <T> void collectRegistry(
            String registryId,
            Registry<T> registry,
            Set<String> accessSources,
            List<Map<String, ?>> summaries,
            List<Map<String, ?>> entries,
            List<Map<String, ?>> tags
    ) {
        int entryStart = entries.size();
        int tagStart = tags.size();

        registry.entrySet().stream()
                .sorted(Map.Entry.comparingByKey(Comparator.comparing(key -> key.location().toString())))
                .forEach(entry -> {
                    ResourceLocation entryId = entry.getKey().location();
                    if (!inScope.test(entryId)) {
                        return;
                    }
                    Map<String, Object> row = new LinkedHashMap<>();
                    row.put("registry_id", registryId);
                    row.put("entry_id", entryId.toString());
                    row.put("namespace", entryId.getNamespace());
                    row.put("implementation_class", entry.getValue().getClass().getName());
                    row.put("access_sources", List.copyOf(accessSources));
                    entries.add(row);
                });

        registry.getTagNames()
                .sorted(Comparator.comparing(tag -> tag.location().toString()))
                .forEach(tag -> registry.getTag(tag).ifPresent(named -> {
                    List<String> members = new ArrayList<>();
                    for (Holder<T> holder : named) {
                        holder.unwrapKey().ifPresent(key -> {
                            if (inScope.test(key.location())) {
                                members.add(key.location().toString());
                            }
                        });
                    }
                    members.stream().sorted().forEach(member -> {
                        Map<String, Object> row = new LinkedHashMap<>();
                        row.put("registry_id", registryId);
                        row.put("tag", tag.location().toString());
                        row.put("member", member);
                        tags.add(row);
                    });
                }));

        Map<String, Object> summary = new LinkedHashMap<>();
        summary.put("registry_id", registryId);
        summary.put("access_sources", List.copyOf(accessSources));
        summary.put("entry_count", entries.size() - entryStart);
        summary.put("tag_membership_count", tags.size() - tagStart);
        summaries.add(summary);
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
            List<Map<String, ?>> recipeDetails,
            List<Map<String, ?>> unloadedRecipeResources,
            List<Map<String, ?>> itemTags,
            List<Map<String, ?>> blockTags,
            RegistryInventory registryInventory,
            List<Map<String, ?>> mechanics,
            List<Map<String, ?>> configs,
            InstalledArtifactInventory.Result artifactInventory
    ) {
        Map<String, Object> row = new LinkedHashMap<>();
        row.put("format", "create-handbook-runtime-export-v1");
        row.put("compatibility_profile", CompatibilityProfile.selected().id());
        row.put("generated_at_utc", Instant.now().toString());
        row.put("minecraft_version", SharedConstants.getCurrentVersion().getName());
        row.put("neoforge_version", modVersion("neoforge"));
        row.put("create_version", modVersion("create"));
        row.put("declared_pack_version", settings.declaredPackVersionValue());
        row.put("scope", settings.scope());
        row.put("pack_wide_registry_capture", settings.scope().equals("pack"));
        row.put("generic_registry_identity_capture", true);
        row.put("recipe_detail_format", "ch4os-recipe-detail-v1");
        row.put("item_detail_format", "ch4os-item-detail-v1");
        row.put("recipe_resource_json_exported", true);
        row.put("sample_ids", SAMPLE_IDS.stream().sorted().toList());
        row.put("dedicated_server", true);
        row.put("connected_players", server.getPlayerList().getPlayerCount());
        row.put("raw_assets_exported", false);
        row.put("installed_artifact_metadata_capture", settings.scope().equals("pack"));
        row.put("raw_jars_exported", false);
        row.put("raw_archive_content_exported", false);
        row.put("network_requests_performed", false);
        Map<String, Integer> counts = new LinkedHashMap<>();
        counts.put("mods", mods.size());
        counts.put("items", items.size());
        counts.put("blocks", blocks.size());
        counts.put("recipes", recipes.size());
        counts.put("recipe_details", recipeDetails.size());
        counts.put("unloaded_recipe_resources", unloadedRecipeResources.size());
        counts.put("item_tag_memberships", itemTags.size());
        counts.put("block_tag_memberships", blockTags.size());
        counts.put("registry_summaries", registryInventory.summaries().size());
        counts.put("registry_entries", registryInventory.entries().size());
        counts.put("registry_tag_memberships", registryInventory.tags().size());
        counts.put("mechanics", mechanics.size());
        counts.put("effective_config_values", configs.size());
        counts.put("installed_artifacts", artifactInventory.artifacts().size());
        counts.put("artifact_entries", artifactInventory.entries().size());
        counts.put("mixin_configs", artifactInventory.mixinConfigs().size());
        counts.put("service_descriptors", artifactInventory.services().size());
        counts.put("artifact_diagnostics", artifactInventory.diagnostics().size());
        row.put("counts", counts);
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
        Set<String> expectedBlockIds = items.stream()
                .map(row -> (String) row.get("block_id"))
                .filter(id -> id != null)
                .collect(java.util.stream.Collectors.toSet());
        List<String> missingItems = SAMPLE_IDS.stream().filter(id -> !itemIds.contains(id)).sorted().toList();
        List<String> missingBlocks = expectedBlockIds.stream().filter(id -> !blockIds.contains(id)).sorted().toList();

        Map<String, Object> row = new LinkedHashMap<>();
        row.put("requested_ids", SAMPLE_IDS.stream().sorted().toList());
        row.put("expected_block_ids", expectedBlockIds.stream().sorted().toList());
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

    private record RegistryInventory(
            List<Map<String, ?>> summaries,
            List<Map<String, ?>> entries,
            List<Map<String, ?>> tags
    ) {
    }

    private static final class RegistryDescriptor {
        private final Registry<?> registry;
        private final Set<String> accessSources = new TreeSet<>();

        private RegistryDescriptor(Registry<?> registry) {
            this.registry = registry;
        }
    }
}
