package dev.chaosarbiter.handbookexporter;

import net.minecraft.core.registries.BuiltInRegistries;
import net.minecraft.resources.ResourceLocation;
import net.minecraft.server.MinecraftServer;
import net.minecraft.world.item.Item;
import net.minecraft.world.item.ItemStack;
import net.minecraft.world.level.material.FlowingFluid;
import net.minecraft.world.level.material.Fluid;

import java.lang.reflect.Field;
import java.lang.reflect.Method;
import java.util.ArrayList;
import java.util.Comparator;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import java.util.Optional;
import java.util.function.Predicate;

/** Effective Propulsion fuel tables and selected loaded gameplay settings. */
final class PropulsionMechanicAdapter implements MechanicAdapter {
    private static final String BASE = "dev.propulsionteam.propulsionsimulated.";
    private static final String FLUID_MANAGER = BASE + "content.thruster.ThrusterFuelManager";
    private static final String SOLID_MANAGER = BASE + "content.thruster.SolidThrusterFuelManager";
    private static final String CORAL_MANAGER = BASE + "content.platinum.CoralGeneratorFuelManager";
    private static final String CONFIG = BASE + "PropulsionConfig";
    private static final List<String> CONFIG_FIELDS = List.of(
            "BASE_THRUST", "OBSTRUCTION_SCAN_LENGTH", "OBSTRUCTION_IGNORE_OTHER_SUBLEVELS",
            "FUEL_TANK_CAPACITY_MB", "FUEL_MB_PER_TICK_AT_FULL_THROTTLE",
            "ION_THRUSTER_ENERGY_CAPACITY_FE", "ION_THRUSTER_FE_PER_TICK_AT_FULL_THROTTLE",
            "ION_THRUSTER_BASE_THRUST", "ION_MULTIBLOCK_2X_THRUST_MULTIPLIER",
            "ION_MULTIBLOCK_3X_THRUST_MULTIPLIER", "VECTOR_THRUSTER_BASE_THRUST",
            "LIQUID_VECTOR_THRUSTER_BASE_THRUST", "LIQUID_VECTOR_THRUSTER_FUEL_TANK_CAPACITY_MB",
            "LIQUID_VECTOR_THRUSTER_FUEL_MB_PER_TICK_AT_FULL_THROTTLE",
            "SOLID_FUEL_THRUSTER_BASE_THRUST", "MULTIBLOCK_2X_THRUST_MULTIPLIER",
            "MULTIBLOCK_3X_THRUST_MULTIPLIER", "MULTIBLOCK_2X_FUEL_EFFICIENCY",
            "MULTIBLOCK_3X_FUEL_EFFICIENCY", "MULTIBLOCK_2X_OXIDIZER_EFFICIENCY",
            "MULTIBLOCK_3X_OXIDIZER_EFFICIENCY", "USE_ATMOSPHERIC_PRESSURE",
            "ATMOSPHERIC_PRESSURE_AMOUNT", "THRUST_UNITS_PER_KN", "CABLE_ENERGY_TRANSFER",
            "STIRLING_GENERATED_SU", "BURNERS_POWER_HEATED_MIXERS",
            "BURNERS_HEAT_STEAM_ENGINES", "BURNERS_SUPERHEAT_STEAM_ENGINES",
            "BLAZE_BURNERS_HEAT_STIRLING_ENGINES", "SOLID_BURNER_FUEL_CONSUMPTION_MULTIPLIER"
    );

    @Override
    public String id() {
        return "createpropulsion";
    }

    @Override
    public String requiredModId() {
        return "createpropulsion";
    }

    @Override
    public List<String> requiredClassNames() {
        return List.of(FLUID_MANAGER, SOLID_MANAGER, CORAL_MANAGER, CONFIG);
    }

    @Override
    public Result collect(MinecraftServer server, Predicate<ResourceLocation> inScope) {
        if (!inScope.test(ResourceLocation.parse("createpropulsion:thruster"))) {
            return Result.empty();
        }
        List<Map<String, ?>> definitions = new ArrayList<>();
        List<Map<String, ?>> relations = new ArrayList<>();
        List<Map<String, ?>> configs = new ArrayList<>();
        List<Map<String, ?>> diagnostics = new ArrayList<>();
        collectPart("fluid_fuels", diagnostics, () -> collectFluidFuels(definitions, relations));
        collectPart("solid_fuels", diagnostics, () -> collectSolidFuels(definitions, relations));
        collectPart("coral_fuels", diagnostics, () -> collectCoralFuels(definitions, relations));
        collectPart("config", diagnostics, () -> collectConfigs(configs, diagnostics));
        return new Result(List.of(), configs, definitions, relations, diagnostics);
    }

    private void collectFluidFuels(List<Map<String, ?>> definitions, List<Map<String, ?>> relations)
            throws ReflectiveOperationException {
        Class<?> manager = Class.forName(FLUID_MANAGER);
        Map<?, ?> fuels = (Map<?, ?>) manager.getMethod("getFuelPropertiesMap").invoke(null);
        List<Map.Entry<?, ?>> entries = new ArrayList<>(fuels.entrySet());
        entries.sort(Comparator.comparing(entry -> fluidId((Fluid) entry.getKey()).toString()));
        for (Map.Entry<?, ?> entry : entries) {
            ResourceLocation fuelId = fluidId((Fluid) entry.getKey());
            Object properties = entry.getValue();
            Map<String, Object> attributes = new LinkedHashMap<>();
            attributes.put("thrust_multiplier", MechanicRows.call(properties, "thrustMultiplier"));
            attributes.put("consumption_multiplier", MechanicRows.call(properties, "consumptionMultiplier"));
            attributes.put("particle_type", String.valueOf(MechanicRows.call(properties, "particleType")));
            definitions.add(AdapterRows.definition(id(), "thruster_fluid_fuel", fuelId.toString(), attributes,
                    Map.of("meaning", "loaded effective fluid fuel"), null, null, null,
                    FLUID_MANAGER + ".getFuelPropertiesMap"));
            for (String block : List.of("thruster", "liquid_vector_thruster", "liquid_burner")) {
                addFuelRelation(relations, "fluid", fuelId.toString(), block, "fluid fuel table",
                        FLUID_MANAGER + ".getFuelPropertiesMap");
            }
        }
    }

    private void collectSolidFuels(List<Map<String, ?>> definitions, List<Map<String, ?>> relations)
            throws ReflectiveOperationException {
        Class<?> manager = Class.forName(SOLID_MANAGER);
        Method find = manager.getMethod("findDefinitionForStack", ItemStack.class);
        Method propertiesFor = manager.getMethod("getProperties", ItemStack.class);
        Method burnTicks = manager.getMethod("resolveBurnTicks", ItemStack.class);
        for (Map.Entry<net.minecraft.resources.ResourceKey<Item>, Item> entry : BuiltInRegistries.ITEM.entrySet().stream()
                .sorted(Map.Entry.comparingByKey(Comparator.comparing(key -> key.location().toString()))).toList()) {
            ItemStack stack = entry.getValue().getDefaultInstance();
            Object definition = find.invoke(null, stack);
            if (definition == null) {
                continue;
            }
            Object properties = propertiesFor.invoke(null, stack);
            ResourceLocation fuelId = entry.getKey().location();
            Map<String, Object> attributes = new LinkedHashMap<>();
            attributes.put("thrust_multiplier", MechanicRows.call(properties, "thrustMultiplier"));
            attributes.put("consumption_multiplier", MechanicRows.call(properties, "consumptionMultiplier"));
            attributes.put("burn_ticks", burnTicks.invoke(null, stack));
            attributes.put("particle_type", String.valueOf(MechanicRows.call(properties, "particleType")));
            Optional<?> sourceTag = (Optional<?>) MechanicRows.call(definition, "itemTagId");
            sourceTag.ifPresent(tag -> attributes.put("matched_item_tag", tag.toString()));
            definitions.add(AdapterRows.definition(id(), "thruster_solid_fuel", fuelId.toString(), attributes,
                    Map.of("meaning", "loaded effective item fuel", "stack", "default item stack"),
                    null, null, null, SOLID_MANAGER + ".findDefinitionForStack/getProperties/resolveBurnTicks"));
            addFuelRelation(relations, "item", fuelId.toString(), "solid_fuel_thruster", "item fuel table",
                    SOLID_MANAGER + ".findDefinitionForStack");
        }
    }

    private void collectCoralFuels(List<Map<String, ?>> definitions, List<Map<String, ?>> relations)
            throws ReflectiveOperationException {
        Class<?> manager = Class.forName(CORAL_MANAGER);
        Method getProperties = manager.getMethod("getProperties", Fluid.class);
        for (Map.Entry<net.minecraft.resources.ResourceKey<Fluid>, Fluid> entry : BuiltInRegistries.FLUID.entrySet().stream()
                .sorted(Map.Entry.comparingByKey(Comparator.comparing(key -> key.location().toString()))).toList()) {
            Fluid fluid = entry.getValue();
            if (fluid instanceof FlowingFluid flowing && flowing.getSource() != fluid) {
                continue;
            }
            Object properties = getProperties.invoke(null, fluid);
            if (properties == null) {
                continue;
            }
            String fuelId = entry.getKey().location().toString();
            Object fePerMb = MechanicRows.call(properties, "fePerMb");
            definitions.add(AdapterRows.definition(id(), "coral_generator_fuel", fuelId,
                    Map.of("fe_per_mb", fePerMb), Map.of("meaning", "loaded effective coral fuel"),
                    null, null, null, CORAL_MANAGER + ".getProperties"));
            addFuelRelation(relations, "fluid", fuelId, "coral_generator", "generator fuel table",
                    CORAL_MANAGER + ".getProperties");
        }
    }

    private void collectConfigs(List<Map<String, ?>> configs, List<Map<String, ?>> diagnostics)
            throws ReflectiveOperationException {
        Class<?> owner = Class.forName(CONFIG);
        for (String fieldName : CONFIG_FIELDS) {
            try {
                Field field = owner.getField(fieldName);
                Object effective = MechanicRows.call(field.get(null), "get");
                configs.add(AdapterRows.config(id(), requiredModId(), "common", "PropulsionConfig",
                        fieldName, effective, null, CONFIG + "." + fieldName + ".get"));
            } catch (ReflectiveOperationException | RuntimeException exception) {
                diagnostics.add(Map.of("subsystem", "mechanic_adapter:" + id() + ":config:" + fieldName,
                        "status", "partial", "error_class", exception.getClass().getName()));
            }
        }
    }

    private void addFuelRelation(List<Map<String, ?>> relations, String kind, String fuelId,
                                 String blockPath, String basis, String sourceApi) {
        ResourceLocation blockId = ResourceLocation.fromNamespaceAndPath("createpropulsion", blockPath);
        if (BuiltInRegistries.BLOCK.containsKey(blockId)) {
            relations.add(AdapterRows.relation(id(), kind, fuelId, "fuel_for", "block",
                    blockId.toString(), Map.of(), Map.of("basis", basis), sourceApi));
        }
    }

    private ResourceLocation fluidId(Fluid fluid) {
        return BuiltInRegistries.FLUID.getKey(fluid);
    }

    private void collectPart(String part, List<Map<String, ?>> diagnostics, Collector collector) {
        try {
            collector.run();
        } catch (ReflectiveOperationException | RuntimeException | LinkageError exception) {
            diagnostics.add(Map.of("subsystem", "mechanic_adapter:" + id() + ":" + part,
                    "status", "partial", "error_class", exception.getClass().getName()));
        }
    }

    @FunctionalInterface
    private interface Collector {
        void run() throws ReflectiveOperationException;
    }
}
