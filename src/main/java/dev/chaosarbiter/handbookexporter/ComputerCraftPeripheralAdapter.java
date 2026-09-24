package dev.chaosarbiter.handbookexporter;

import net.minecraft.core.registries.BuiltInRegistries;
import net.minecraft.resources.ResourceLocation;
import net.minecraft.server.MinecraftServer;
import net.minecraft.world.item.Item;
import net.minecraft.world.item.Items;
import net.minecraft.world.level.block.Block;
import net.neoforged.fml.ModList;
import net.neoforged.neoforge.capabilities.BlockCapability;
import net.neoforged.neoforge.capabilities.RegisterCapabilitiesEvent;

import java.lang.annotation.Annotation;
import java.lang.reflect.Method;
import java.util.ArrayList;
import java.util.Arrays;
import java.util.Comparator;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Locale;
import java.util.Map;
import java.util.function.Predicate;

/** Lua-visible methods declared by installed gameplay peripheral integrations. */
final class ComputerCraftPeripheralAdapter implements MechanicAdapter {
    private static volatile RegisterCapabilitiesEvent capabilityEvent;
    private static final String LUA_FUNCTION = "dan200.computercraft.api.lua.LuaFunction";
    private static final String PROPULSION = "dev.propulsionteam.propulsionsimulated.compat.computercraft.";
    private static final String ELECTRO = "com.george_vi.electroenergetics.compat.computercraft.peripherals.";
    private static final String DIESEL = "com.jesz.createdieselgenerators.compat.computercraft.peripherals.";
    private static final String PINOUT = "com.breakdown.pinout.content.pinout.";
    private static final String POWERGRID_CC = "org.patryk3211.powergrid.compat.cc.";
    private static final String ADDITION = "com.mrh0.createaddition.compat.computercraft.";
    private static final String NEW_AGE = "org.antarcticgardens.cna.compat.computercraft.peripherals.";
    private static final String NUMISMATICS =
            "dev.ithundxr.createnumismatics.compat.computercraft.implementation.peripherals.";
    private static final String BITS = "com.kipti.bnb.compat.computercraft.implementation.peripherals.";
    private static final String GADGETS = "com.rieno.gadgetsandgizmos.compat.computercraft.";
    private static final String AVIONICS = "ink.astrius.create_avionics.compat.";
    private static final String CREATE_CC = "com.simibubi.create.compat.computercraft.implementation.peripherals.";
    private static final Map<String, String> POWERGRID_ITEMS = Map.of(
            "BatteryPeripheral", "powergrid:battery",
            "GeneratorClutchPeripheral", "powergrid:generator_clutch",
            "CurrentGaugePeripheral", "powergrid:current_gauge",
            "EnergyMeterPeripheral", "powergrid:energy_meter",
            "PowerGaugePeripheral", "powergrid:power_gauge",
            "VoltageGaugePeripheral", "powergrid:voltage_gauge",
            "RedstoneConverterPeripheral", "powergrid:redstone_converter"
    );
    private static final List<Provider> PROVIDERS = List.of(
            new Provider("create", CREATE_CC, List.of("CreativeMotorPeripheral", "DisplayLinkPeripheral",
                    "FrogportPeripheral", "NixieTubePeripheral", "PackagerPeripheral", "PostboxPeripheral",
                    "RedstoneRequesterPeripheral", "RepackagerPeripheral", "SequencedGearshiftPeripheral",
                    "SignalPeripheral", "SpeedControllerPeripheral", "SpeedGaugePeripheral",
                    "StationPeripheral", "StickerPeripheral", "StockTickerPeripheral",
                    "StressGaugePeripheral", "TableClothShopPeripheral", "TrackObserverPeripheral")),
            new Provider("createpropulsion", PROPULSION, List.of("CoralGeneratorPeripheral",
                    "CreativeThrusterPeripheral", "CreativeVectorThrusterPeripheral", "IonThrusterPeripheral",
                    "LiquidVectorThrusterPeripheral", "RedstoneTransmissionPeripheral",
                    "SolidFuelThrusterPeripheral", "StirlingEnginePeripheral", "ThrusterPeripheral",
                    "TiltAdapterPeripheral", "VectorThrusterPeripheral")),
            new Provider("electroenergetics", ELECTRO, List.of("ElectricGaugePeripheral")),
            new Provider("createdieselgenerators", DIESEL, List.of("ChemicalTurretPeripheral")),
            new Provider("pinout", PINOUT, List.of("PinoutPeripheral")),
            new Provider("powergrid", POWERGRID_CC + "battery.", List.of("BatteryPeripheral")),
            new Provider("powergrid", POWERGRID_CC + "clutch.", List.of("GeneratorClutchPeripheral")),
            new Provider("powergrid", POWERGRID_CC + "gauges.", List.of("CurrentGaugePeripheral",
                    "EnergyMeterPeripheral", "PowerGaugePeripheral", "VoltageGaugePeripheral")),
            new Provider("powergrid", POWERGRID_CC + "redstone.", List.of("RedstoneConverterPeripheral")),
            new Provider("createaddition", ADDITION, List.of("DigitalAdapterPeripheral", "ElectricMotorPeripheral",
                    "ModularAccumulatorPeripheral", "PortableEnergyInterfacePeripheral", "RedstoneRelayPeripheral")),
            new Provider("create_new_age", NEW_AGE, List.of("CarbonBrushesBlockEntityPeripheral",
                    "EnergiserBlockEntityPeripheral", "MotorBlockEntityPeripheral")),
            new Provider("numismatics", NUMISMATICS, List.of("BankTerminalPeripheral",
                    "BrassDepositorPeripheral", "SalepointPeripheral", "VendorPeripheral")),
            new Provider("bits_n_bobs", BITS, List.of("HeadlampPeripheral")),
            new Provider("createthrusters", GADGETS, List.of("AdvancedContraptionControllerPeripheral",
                    "AileronBearingPeripheral", "AnalogueContraptionControllerPeripheral",
                    "AnalogueJoystickPeripheral", "BiDirectionalGearboxPeripheral", "ClawPeripheral",
                    "GyroscopeLinkPeripheral", "NavigationTablePeripheral", "ThrusterBearingPeripheral",
                    "ThrusterPeripheral", "VectorBearingPeripheral", "VirtualOrientationSourcePeripheral")),
            new Provider("create_avionics", AVIONICS + "simulated.peripherals.", List.of(
                    "AltitudeSensorPeripheral", "AnalogTransmissionPeripheral", "DirectionalGearshiftPeripheral",
                    "GimbalSensorPeripheral", "LaserPointerPeripheral", "LaserSensorPeripheral",
                    "LinkedTypewriterPeripheral", "NavTablePeripheral", "PhysicsAssemblerPeripheral",
                    "PortableEnginePeripheral", "RopeWinchPeripheral", "SteeringWheelPeripheral",
                    "SwivelBearingPeripheral", "ThrottleLeverPeripheral", "TorsionSpringPeripheral",
                    "VelocitySensorPeripheral")),
            new Provider("create_avionics", AVIONICS + "aeronautics.peripherals.", List.of(
                    "GasProviderPeripheral", "GyroscopicPropellerBearingPeripheral",
                    "MountedPotatoCannonPeripheral", "PropellerBearingPeripheral", "PropellerPeripheral")),
            new Provider("create_avionics", AVIONICS + "offroad.peripherals.", List.of("WheelMountPeripheral"))
    );

    @Override public String id() { return "computercraft_peripherals"; }
    @Override public String requiredModId() { return "computercraft"; }
    @Override public List<String> requiredClassNames() { return List.of(LUA_FUNCTION); }

    static void rememberCapabilities(RegisterCapabilitiesEvent event) {
        capabilityEvent = event;
    }

    @Override
    public Result collect(MinecraftServer server, Predicate<ResourceLocation> inScope) {
        List<Map<String, ?>> mechanics = new ArrayList<>();
        List<Map<String, ?>> definitions = new ArrayList<>();
        List<Map<String, ?>> relations = new ArrayList<>();
        List<Map<String, ?>> diagnostics = new ArrayList<>();
        Map<String, String> registeredItems = registeredPeripheralItems(inScope, mechanics, diagnostics);
        for (Provider provider : PROVIDERS) {
            if (!ModList.get().isLoaded(provider.modId())) {
                continue;
            }
            for (String simpleName : provider.classes()) {
                String name = provider.packageName() + simpleName;
                try {
                    Class<?> peripheral = Class.forName(name, false, getClass().getClassLoader());
                    List<Map<String, Object>> luaMethods = new ArrayList<>();
                    for (Method method : peripheral.getMethods()) {
                        if (method.isSynthetic() || method.isBridge()) {
                            continue;
                        }
                        for (Annotation annotation : method.getDeclaredAnnotations()) {
                            if (!LUA_FUNCTION.equals(annotation.annotationType().getName())) {
                                continue;
                            }
                            Map<String, Object> signature = new LinkedHashMap<>();
                            signature.put("java_name", method.getName());
                            String[] aliases = (String[]) annotation.annotationType()
                                    .getMethod("value").invoke(annotation);
                            signature.put("lua_names", aliases.length == 0 ? List.of(method.getName()) :
                                    Arrays.asList(aliases));
                            signature.put("parameters", Arrays.stream(method.getParameterTypes())
                                    .map(Class::getTypeName).toList());
                            signature.put("returns", method.getReturnType().getTypeName());
                            signature.put("main_thread", annotation.annotationType()
                                    .getMethod("mainThread").invoke(annotation));
                            luaMethods.add(signature);
                        }
                    }
                    luaMethods.sort(Comparator.comparing(row -> row.get("java_name").toString()));
                    List<String> linkedItems = itemIds(provider, simpleName).stream()
                            .filter(registeredItems::containsKey).toList();
                    if (linkedItems.isEmpty() || luaMethods.isEmpty()) {
                        continue;
                    }
                    String version = ModList.get().getModContainerById(provider.modId())
                            .map(container -> container.getModInfo().getVersion().toString()).orElse("unknown");
                    Map<String, Object> attrs = new LinkedHashMap<>();
                    attrs.put("provider_mod", provider.modId());
                    attrs.put("provider_version", version);
                    attrs.put("java_class", name);
                    attrs.put("lua_methods", luaMethods);
                    String definitionId = provider.modId() + ":" + simpleName;
                    definitions.add(AdapterRows.definition(id(), "cc_peripheral_api",
                            definitionId, attrs,
                            Map.of("meaning", "LuaFunction methods on a class mapped to a registered CC block",
                                    "attachment", "placed block and computer connection may be required"),
                            null, null, null, name + " method annotations"));
                    for (String item : linkedItems) {
                        Map<String, String> conditions = Map.of(
                                "basis", "loaded CC block capability registration and installed LuaFunction annotations",
                                "attachment", "requires a placed block and computer connection");
                        relations.add(AdapterRows.relation(id(), "item", item, "exposes_cc_peripheral",
                                "cc_peripheral_api", definitionId, Map.of("method_count", luaMethods.size()),
                                conditions, "RegisterCapabilitiesEvent.isBlockRegistered"));
                    }
                } catch (ReflectiveOperationException | RuntimeException | LinkageError exception) {
                    diagnostics.add(Map.of("subsystem", "mechanic_adapter:" + id() + ":" + name,
                            "status", "partial", "error_class", exception.getClass().getName()));
                }
            }
        }
        return new Result(mechanics, List.of(), definitions, relations, diagnostics);
    }

    private Map<String, String> registeredPeripheralItems(Predicate<ResourceLocation> inScope,
                                                           List<Map<String, ?>> mechanics,
                                                           List<Map<String, ?>> diagnostics) {
        RegisterCapabilitiesEvent event = capabilityEvent;
        if (event == null) {
            diagnostics.add(Map.of("subsystem", "mechanic_adapter:" + id() + ":registration",
                    "status", "partial", "reason", "capability registration event unavailable"));
            return Map.of();
        }
        try {
            Object value = Class.forName("dan200.computercraft.api.peripheral.PeripheralCapability",
                    false, getClass().getClassLoader()).getMethod("get").invoke(null);
            if (!(value instanceof BlockCapability<?, ?> capability)) {
                throw new IllegalStateException("CC peripheral capability has unexpected type");
            }
            Map<String, String> registered = new LinkedHashMap<>();
            for (Map.Entry<net.minecraft.resources.ResourceKey<Block>, Block> entry :
                    BuiltInRegistries.BLOCK.entrySet().stream()
                            .sorted(Map.Entry.comparingByKey(Comparator.comparing(key -> key.location().toString())))
                            .toList()) {
                ResourceLocation blockId = entry.getKey().location();
                if (!inScope.test(blockId) || !event.isBlockRegistered(capability, entry.getValue())) {
                    continue;
                }
                Item item = entry.getValue().asItem();
                if (item == Items.AIR) {
                    continue;
                }
                ResourceLocation itemId = BuiltInRegistries.ITEM.getKey(item);
                if (itemId == null || !inScope.test(itemId)) {
                    continue;
                }
                registered.put(itemId.toString(), blockId.toString());
                mechanics.add(MechanicRows.fact(id(), "item", itemId.toString(),
                        "integration.computercraft.peripheral_registered", true, null,
                        Map.of("meaning", "loaded server registered a CC peripheral capability for this block",
                                "block", blockId.toString(),
                                "availability", "may depend on block state, side, or world conditions"),
                        "RegisterCapabilitiesEvent.isBlockRegistered"));
            }
            return registered;
        } catch (ReflectiveOperationException | RuntimeException | LinkageError exception) {
            diagnostics.add(Map.of("subsystem", "mechanic_adapter:" + id() + ":registration",
                    "status", "partial", "error_class", exception.getClass().getName()));
            return Map.of();
        }
    }

    private List<String> itemIds(Provider provider, String simpleName) {
        if ("create".equals(provider.modId())) {
            if ("TableClothShopPeripheral".equals(simpleName)) {
                return List.of("andesite", "brass", "copper", "white", "orange", "magenta", "light_blue",
                        "yellow", "lime", "pink", "gray", "light_gray", "cyan", "purple", "blue",
                        "brown", "green", "red", "black").stream()
                        .map(color -> "create:" + color + "_table_cloth").toList();
            }
            String block = switch (simpleName) {
                case "FrogportPeripheral" -> "package_frogport";
                case "SignalPeripheral" -> "track_signal";
                case "SpeedControllerPeripheral" -> "rotation_speed_controller";
                case "SpeedGaugePeripheral" -> "speedometer";
                case "StationPeripheral" -> "track_station";
                case "StressGaugePeripheral" -> "stressometer";
                default -> null;
            };
            if (block != null) {
                return List.of("create:" + block);
            }
        }
        if ("powergrid".equals(provider.modId())) {
            String item = POWERGRID_ITEMS.get(simpleName);
            return item == null ? List.of() : List.of(item);
        }
        if ("electroenergetics".equals(provider.modId()) && "ElectricGaugePeripheral".equals(simpleName)) {
            return List.of("electroenergetics:ammeter", "electroenergetics:voltmeter");
        }
        if ("create_new_age".equals(provider.modId())) {
            return switch (simpleName) {
                case "CarbonBrushesBlockEntityPeripheral" -> List.of("create_new_age:carbon_brushes");
                case "EnergiserBlockEntityPeripheral" -> List.of("create_new_age:basic_energiser",
                        "create_new_age:advanced_energiser", "create_new_age:reinforced_energiser");
                case "MotorBlockEntityPeripheral" -> List.of("create_new_age:basic_motor",
                        "create_new_age:advanced_motor", "create_new_age:reinforced_motor");
                default -> List.of();
            };
        }
        if ("numismatics".equals(provider.modId()) && "VendorPeripheral".equals(simpleName)) {
            return List.of("numismatics:vendor", "numismatics:creative_vendor");
        }
        if ("createthrusters".equals(provider.modId())) {
            if ("NavigationTablePeripheral".equals(simpleName)) {
                return List.of("createthrusters:advanced_navigation_table");
            }
            if ("BiDirectionalGearboxPeripheral".equals(simpleName)) {
                return List.of("createthrusters:bidirectional_gearbox");
            }
        }
        if ("create_avionics".equals(provider.modId())) {
            if ("GasProviderPeripheral".equals(simpleName)) {
                return List.of("aeronautics:adjustable_burner", "aeronautics:steam_vent");
            }
            if ("PropellerPeripheral".equals(simpleName)) {
                return List.of("aeronautics:wooden_propeller", "aeronautics:andesite_propeller",
                        "aeronautics:smart_propeller");
            }
            if ("PortableEnginePeripheral".equals(simpleName)) {
                return List.of("white", "orange", "magenta", "light_blue", "yellow", "lime", "pink", "gray",
                        "light_gray", "cyan", "purple", "blue", "brown", "green", "red", "black")
                        .stream().map(color -> "simulated:" + color + "_portable_engine").toList();
            }
            String stem = simpleName.replaceFirst("Peripheral$", "");
            String path = stem.replaceAll("([a-z0-9])([A-Z])", "$1_$2").toLowerCase(Locale.ROOT);
            if ("NavTablePeripheral".equals(simpleName)) {
                path = "navigation_table";
            }
            if ("WheelMountPeripheral".equals(simpleName)) {
                return List.of("offroad:wheel_mount");
            }
            String namespace = List.of("GyroscopicPropellerBearingPeripheral", "MountedPotatoCannonPeripheral",
                    "PropellerBearingPeripheral").contains(simpleName) ? "aeronautics" : "simulated";
            return List.of(namespace + ":" + path);
        }
        String stem = simpleName.replaceFirst("Peripheral$", "");
        String path = stem.replaceAll("([a-z0-9])([A-Z])", "$1_$2").toLowerCase(Locale.ROOT);
        return List.of(provider.modId() + ":" + path);
    }

    private record Provider(String modId, String packageName, List<String> classes) {}
}
