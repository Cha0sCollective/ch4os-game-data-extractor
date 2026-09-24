package dev.chaosarbiter.handbookexporter;

import net.minecraft.core.Registry;
import net.minecraft.core.registries.BuiltInRegistries;
import net.minecraft.resources.ResourceLocation;
import net.minecraft.server.MinecraftServer;
import net.minecraft.world.item.Item;
import net.minecraft.world.item.Items;
import net.minecraft.world.level.block.Block;
import net.minecraft.world.level.block.entity.BlockEntityType;

import java.lang.reflect.Method;
import java.util.ArrayList;
import java.util.Comparator;
import java.util.LinkedHashMap;
import java.util.LinkedHashSet;
import java.util.List;
import java.util.Map;
import java.util.Set;
import java.util.function.Predicate;

/** Create's loaded Display Link sources and targets, mapped to item-backed blocks. */
final class DisplayLinkAdapter implements MechanicAdapter {
    private static final String BUILT_IN = "com.simibubi.create.api.registry.CreateBuiltInRegistries";
    private static final String SOURCE = "com.simibubi.create.api.behaviour.display.DisplaySource";
    private static final String TARGET = "com.simibubi.create.api.behaviour.display.DisplayTarget";
    private static final String SIMPLE = "com.simibubi.create.api.registry.SimpleRegistry";
    private static final String SIGN = "com.simibubi.create.AllDisplayTargets";

    @Override public String id() { return "create_display_links"; }
    @Override public String requiredModId() { return "create"; }
    @Override public List<String> requiredClassNames() { return List.of(BUILT_IN, SOURCE, TARGET, SIMPLE); }

    @Override
    public Result collect(MinecraftServer server, Predicate<ResourceLocation> inScope) {
        List<Map<String, ?>> definitions = new ArrayList<>();
        List<Map<String, ?>> relations = new ArrayList<>();
        List<Map<String, ?>> diagnostics = new ArrayList<>();
        Map<RoleKey, RoleEvidence> itemRoles = new LinkedHashMap<>();
        try {
            ClassLoader loader = getClass().getClassLoader();
            Class<?> registries = Class.forName(BUILT_IN, false, loader);
            Class<?> sourceClass = Class.forName(SOURCE, false, loader);
            Class<?> targetClass = Class.forName(TARGET, false, loader);
            Class<?> simpleClass = Class.forName(SIMPLE, false, loader);
            Class<?> multiClass = Class.forName(SIMPLE + "$Multi", false, loader);
            Registry<?> sources = (Registry<?>) registries.getField("DISPLAY_SOURCE").get(null);
            Registry<?> targets = (Registry<?>) registries.getField("DISPLAY_TARGET").get(null);
            Method sourceGet = multiClass.getMethod("get", Object.class);
            Method targetGet = simpleClass.getMethod("get", Object.class);
            Object sourcesByBlock = sourceClass.getField("BY_BLOCK").get(null);
            Object sourcesByEntity = sourceClass.getField("BY_BLOCK_ENTITY").get(null);
            Object targetsByBlock = targetClass.getField("BY_BLOCK").get(null);
            Object targetsByEntity = targetClass.getField("BY_BLOCK_ENTITY").get(null);
            Object signTarget = signTarget(loader);

            addDefinitions(sources, "display_source", inScope, definitions);
            addDefinitions(targets, "display_target", inScope, definitions);
            ResourceLocation linkItem = ResourceLocation.parse("create:display_link");
            if (inScope.test(linkItem) && BuiltInRegistries.ITEM.containsKey(linkItem)) {
                for (Map<String, ?> definition : definitions) {
                    String kind = definition.get("kind").toString();
                    String definitionId = definition.get("id").toString();
                    relations.add(AdapterRows.relation(id(), "item", linkItem.toString(),
                            "display_source".equals(kind) ? "supports_display_source" : "supports_display_target",
                            kind, definitionId, Map.of(),
                            Map.of("meaning", "registered type in the loaded Create Display Link registry",
                                    "availability", "requires a suitable placed source or target block"),
                            BUILT_IN));
                }
            }
            List<BlockEntityType<?>> entityTypes = new ArrayList<>();
            for (BlockEntityType<?> type : BuiltInRegistries.BLOCK_ENTITY_TYPE) {
                entityTypes.add(type);
            }
            entityTypes.sort(Comparator.comparing(type -> BuiltInRegistries.BLOCK_ENTITY_TYPE.getKey(type).toString()));

            for (Block block : BuiltInRegistries.BLOCK.entrySet().stream()
                    .sorted(Map.Entry.comparingByKey(Comparator.comparing(key -> key.location().toString())))
                    .map(Map.Entry::getValue).toList()) {
                ResourceLocation blockId = BuiltInRegistries.BLOCK.getKey(block);
                Item item = block.asItem();
                if (item == Items.AIR || !inScope.test(blockId)) {
                    continue;
                }
                ResourceLocation itemId = BuiltInRegistries.ITEM.getKey(item);
                if (itemId == null || !inScope.test(itemId)) {
                    continue;
                }
                Map<String, Set<String>> sourceIds = new LinkedHashMap<>();
                Map<String, Set<String>> targetIds = new LinkedHashMap<>();
                addSources(sourceGet.invoke(sourcesByBlock, block), sources, sourceIds, "block registration");
                Object blockTarget = targetGet.invoke(targetsByBlock, block);
                addTarget(blockTarget, targets, targetIds, "block registration");
                for (BlockEntityType<?> type : entityTypes) {
                    if (!type.isValid(block.defaultBlockState())) {
                        continue;
                    }
                    String typeId = BuiltInRegistries.BLOCK_ENTITY_TYPE.getKey(type).toString();
                    addSources(sourceGet.invoke(sourcesByEntity, type), sources, sourceIds,
                            "block entity type " + typeId);
                    if (blockTarget == null) {
                        Object entityTarget = targetGet.invoke(targetsByEntity, type);
                        addTarget(entityTarget, targets, targetIds, "block entity type " + typeId);
                        if (entityTarget == null && ("minecraft:sign".equals(typeId)
                                || "minecraft:hanging_sign".equals(typeId))) {
                            addTarget(signTarget, targets, targetIds, "SignBlockEntity fallback");
                        }
                    }
                }
                addRoles(itemId, blockId, "provides_display_source", "display_source", sourceIds,
                        inScope, itemRoles);
                addRoles(itemId, blockId, "accepts_display_output", "display_target", targetIds,
                        inScope, itemRoles);
            }
            itemRoles.entrySet().stream().sorted(Comparator.comparing(entry -> entry.getKey().toString()))
                    .forEach(entry -> {
                        RoleKey role = entry.getKey();
                        RoleEvidence evidence = entry.getValue();
                        relations.add(AdapterRows.relation(id(), "item", role.item(), role.predicate(),
                                role.kind(), role.definition(),
                                Map.of("block_ids", List.copyOf(evidence.blocks),
                                        "registration_basis", List.copyOf(evidence.bases)),
                                Map.of("meaning", "registered Create Display Link role for an item-backed block",
                                        "availability", "actual connection depends on a placed block and world state"),
                                SOURCE + ".BY_BLOCK/BY_BLOCK_ENTITY; " + TARGET + ".BY_BLOCK/BY_BLOCK_ENTITY"));
                    });
        } catch (ReflectiveOperationException | RuntimeException | LinkageError exception) {
            diagnostics.add(Map.of("subsystem", "mechanic_adapter:" + id() + ":registry",
                    "status", "partial", "error_class", exception.getClass().getName()));
        }
        return new Result(List.of(), List.of(), definitions, relations, diagnostics);
    }

    private void addDefinitions(Registry<?> registry, String kind, Predicate<ResourceLocation> inScope,
                                List<Map<String, ?>> definitions) {
        List<Object> values = new ArrayList<>();
        for (Object value : registry) {
            values.add(value);
        }
        values.sort(Comparator.comparing(value -> {
            ResourceLocation key = registryId(registry, value);
            return key == null ? "" : key.toString();
        }));
        for (Object value : values) {
            ResourceLocation key = registryId(registry, value);
            if (key == null || !inScope.test(key)) {
                continue;
            }
            definitions.add(AdapterRows.definition(id(), kind, key.toString(),
                    Map.of("implementation_class", value.getClass().getName()),
                    Map.of("meaning", "registered Create Display Link " + kind.replace('_', ' '),
                            "availability", "placement and world state can affect the offered option"),
                    null, null, null, BUILT_IN + "." + ("display_source".equals(kind)
                            ? "DISPLAY_SOURCE" : "DISPLAY_TARGET")));
        }
    }

    private Object signTarget(ClassLoader loader) {
        try {
            Object entry = Class.forName(SIGN, false, loader).getField("SIGN").get(null);
            return entry.getClass().getMethod("get").invoke(entry);
        } catch (ReflectiveOperationException | LinkageError exception) {
            return null;
        }
    }

    private void addSources(Object values, Registry<?> registry, Map<String, Set<String>> found, String basis) {
        if (!(values instanceof List<?> list)) {
            return;
        }
        for (Object value : list) {
            addId(value, registry, found, basis);
        }
    }

    private void addTarget(Object value, Registry<?> registry, Map<String, Set<String>> found, String basis) {
        if (value != null) {
            addId(value, registry, found, basis);
        }
    }

    private void addId(Object value, Registry<?> registry, Map<String, Set<String>> found, String basis) {
        ResourceLocation id = registryId(registry, value);
        if (id != null) {
            found.computeIfAbsent(id.toString(), ignored -> new LinkedHashSet<>()).add(basis);
        }
    }

    private void addRoles(ResourceLocation item, ResourceLocation block, String predicate, String kind,
                          Map<String, Set<String>> found, Predicate<ResourceLocation> inScope,
                          Map<RoleKey, RoleEvidence> roles) {
        found.entrySet().stream().sorted(Map.Entry.comparingByKey()).forEach(entry -> {
            if (!inScope.test(ResourceLocation.parse(entry.getKey()))) {
                return;
            }
            RoleEvidence evidence = roles.computeIfAbsent(
                    new RoleKey(item.toString(), predicate, kind, entry.getKey()), ignored -> new RoleEvidence());
            evidence.blocks.add(block.toString());
            evidence.bases.addAll(entry.getValue());
        });
    }

    private record RoleKey(String item, String predicate, String kind, String definition) {}

    private static final class RoleEvidence {
        private final Set<String> blocks = new LinkedHashSet<>();
        private final Set<String> bases = new LinkedHashSet<>();
    }

    @SuppressWarnings({"rawtypes", "unchecked"})
    private ResourceLocation registryId(Registry<?> registry, Object value) {
        return ((Registry) registry).getKey(value);
    }
}
