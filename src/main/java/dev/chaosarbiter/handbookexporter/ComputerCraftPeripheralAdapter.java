package dev.chaosarbiter.handbookexporter;

import net.minecraft.core.registries.BuiltInRegistries;
import net.minecraft.resources.ResourceLocation;
import net.minecraft.server.MinecraftServer;
import net.neoforged.fml.ModList;

import java.lang.annotation.Annotation;
import java.lang.reflect.Method;
import java.util.ArrayList;
import java.util.Arrays;
import java.util.Comparator;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import java.util.function.Predicate;

/** Lua-visible methods declared by installed gameplay peripheral integrations. */
final class ComputerCraftPeripheralAdapter implements MechanicAdapter {
    private static final String LUA_FUNCTION = "dan200.computercraft.api.lua.LuaFunction";
    private static final String PROPULSION = "dev.propulsionteam.propulsionsimulated.compat.computercraft.";
    private static final String ELECTRO = "com.george_vi.electroenergetics.compat.computercraft.peripherals.";
    private static final String DIESEL = "com.jesz.createdieselgenerators.compat.computercraft.peripherals.";
    private static final String PINOUT = "com.breakdown.pinout.content.pinout.";
    private static final String POWERGRID_CC = "org.patryk3211.powergrid.compat.cc.";
    private static final String POWERGRID_BRIDGE = POWERGRID_CC + "CCBridge";
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
            new Provider("powergrid", POWERGRID_CC + "redstone.", List.of("RedstoneConverterPeripheral"))
    );

    @Override public String id() { return "computercraft_peripherals"; }
    @Override public String requiredModId() { return "computercraft"; }
    @Override public List<String> requiredClassNames() { return List.of(LUA_FUNCTION); }

    @Override
    public Result collect(MinecraftServer server, Predicate<ResourceLocation> inScope) {
        List<Map<String, ?>> mechanics = new ArrayList<>();
        List<Map<String, ?>> definitions = new ArrayList<>();
        List<Map<String, ?>> relations = new ArrayList<>();
        List<Map<String, ?>> diagnostics = new ArrayList<>();
        boolean powerGridBridge = powerGridBridgePresent();
        for (Provider provider : PROVIDERS) {
            if (!ModList.get().isLoaded(provider.modId()) ||
                    !inScope.test(ResourceLocation.fromNamespaceAndPath(provider.modId(), "cc_peripheral_api"))) {
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
                            Map.of("meaning", "installed class has LuaFunction methods",
                                    "attachment", "not verified without a placed block and computer"),
                            null, null, null, name + " method annotations"));
                    String item = POWERGRID_ITEMS.get(simpleName);
                    if ("powergrid".equals(provider.modId()) && powerGridBridge && item != null) {
                        ResourceLocation itemId = ResourceLocation.parse(item);
                        if (BuiltInRegistries.ITEM.containsKey(itemId) && BuiltInRegistries.BLOCK.containsKey(itemId)) {
                            Map<String, String> conditions = Map.of("basis", "Power Grid CC capability registration",
                                    "attachment", "requires a placed block and computer connection");
                            relations.add(AdapterRows.relation(id(), "item", item, "exposes_cc_peripheral",
                                    "cc_peripheral_api", definitionId, Map.of("method_count", luaMethods.size()),
                                    conditions, POWERGRID_BRIDGE + ".registerCapabilities"));
                            mechanics.add(MechanicRows.fact(id(), "item", item,
                                    "integration.computercraft.peripheral_available", true, null,
                                    conditions, POWERGRID_BRIDGE + ".registerCapabilities"));
                        }
                    }
                } catch (ReflectiveOperationException | RuntimeException | LinkageError exception) {
                    diagnostics.add(Map.of("subsystem", "mechanic_adapter:" + id() + ":" + name,
                            "status", "partial", "error_class", exception.getClass().getName()));
                }
            }
        }
        return new Result(mechanics, List.of(), definitions, relations, diagnostics);
    }

    private boolean powerGridBridgePresent() {
        if (!ModList.get().isLoaded("powergrid")) {
            return false;
        }
        try {
            return Arrays.stream(Class.forName(POWERGRID_BRIDGE, false, getClass().getClassLoader()).getMethods())
                    .anyMatch(method -> "registerCapabilities".equals(method.getName()));
        } catch (ClassNotFoundException | LinkageError exception) {
            return false;
        }
    }

    private record Provider(String modId, String packageName, List<String> classes) {}
}
