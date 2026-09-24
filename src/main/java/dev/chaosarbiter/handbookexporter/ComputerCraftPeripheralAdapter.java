package dev.chaosarbiter.handbookexporter;

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
    private static final List<Provider> PROVIDERS = List.of(
            new Provider("createpropulsion", PROPULSION, List.of("CoralGeneratorPeripheral",
                    "CreativeThrusterPeripheral", "CreativeVectorThrusterPeripheral", "IonThrusterPeripheral",
                    "LiquidVectorThrusterPeripheral", "RedstoneTransmissionPeripheral",
                    "SolidFuelThrusterPeripheral", "StirlingEnginePeripheral", "ThrusterPeripheral",
                    "TiltAdapterPeripheral", "VectorThrusterPeripheral")),
            new Provider("electroenergetics", ELECTRO, List.of("ElectricGaugePeripheral")),
            new Provider("createdieselgenerators", DIESEL, List.of("ChemicalTurretPeripheral")),
            new Provider("pinout", PINOUT, List.of("PinoutPeripheral"))
    );

    @Override public String id() { return "computercraft_peripherals"; }
    @Override public String requiredModId() { return "computercraft"; }
    @Override public List<String> requiredClassNames() { return List.of(LUA_FUNCTION); }

    @Override
    public Result collect(MinecraftServer server, Predicate<ResourceLocation> inScope) {
        if (!inScope.test(ResourceLocation.parse("computercraft:computer_normal"))) {
            return Result.empty();
        }
        List<Map<String, ?>> definitions = new ArrayList<>();
        List<Map<String, ?>> diagnostics = new ArrayList<>();
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
                    String version = ModList.get().getModContainerById(provider.modId())
                            .map(container -> container.getModInfo().getVersion().toString()).orElse("unknown");
                    Map<String, Object> attrs = new LinkedHashMap<>();
                    attrs.put("provider_mod", provider.modId());
                    attrs.put("provider_version", version);
                    attrs.put("java_class", name);
                    attrs.put("lua_methods", luaMethods);
                    definitions.add(AdapterRows.definition(id(), "cc_peripheral_api",
                            provider.modId() + ":" + simpleName, attrs,
                            Map.of("meaning", "installed class has LuaFunction methods",
                                    "attachment", "not verified without a placed block and computer"),
                            null, null, null, name + " method annotations"));
                } catch (ReflectiveOperationException | RuntimeException | LinkageError exception) {
                    diagnostics.add(Map.of("subsystem", "mechanic_adapter:" + id() + ":" + name,
                            "status", "partial", "error_class", exception.getClass().getName()));
                }
            }
        }
        return new Result(List.of(), List.of(), definitions, List.of(), diagnostics);
    }

    private record Provider(String modId, String packageName, List<String> classes) {}
}
