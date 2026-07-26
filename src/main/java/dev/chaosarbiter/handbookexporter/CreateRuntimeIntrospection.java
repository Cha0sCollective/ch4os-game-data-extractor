package dev.chaosarbiter.handbookexporter;

import net.minecraft.core.registries.BuiltInRegistries;
import net.minecraft.resources.ResourceLocation;
import net.minecraft.world.level.block.Block;

import java.lang.reflect.Field;
import java.lang.reflect.InvocationTargetException;
import java.lang.reflect.Method;
import java.lang.reflect.Modifier;
import java.util.ArrayList;
import java.util.Arrays;
import java.util.Comparator;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import java.util.function.DoubleSupplier;
import java.util.function.Function;
import java.util.function.Predicate;
import java.util.function.Supplier;

/**
 * Reads Create's public runtime registries without adding Create as a compile-time
 * dependency. The exporter remains a small NeoForge-only diagnostic mod while the
 * exact Create version is still enforced before this class is called.
 */
final class CreateRuntimeIntrospection {
    private static final String STRESS_CLASS =
            "com.simibubi.create.api.stress.BlockStressValues";
    private static final String CONFIG_CLASS =
            "com.simibubi.create.infrastructure.config.AllConfigs";

    private final Predicate<ResourceLocation> inScope;

    CreateRuntimeIntrospection(Predicate<ResourceLocation> inScope) {
        this.inScope = inScope;
    }

    IntrospectionResult collect() {
        List<Map<String, ?>> mechanics = new ArrayList<>();
        List<Map<String, ?>> configs = new ArrayList<>();
        List<Map<String, ?>> diagnostics = new ArrayList<>();
        collectStress(mechanics, diagnostics);
        collectConfigs(configs, diagnostics);
        return new IntrospectionResult(mechanics, configs, diagnostics);
    }

    private void collectStress(
            List<Map<String, ?>> rows,
            List<Map<String, ?>> diagnostics
    ) {
        try {
            Class<?> stressClass = Class.forName(STRESS_CLASS);
            Method impactMethod = stressClass.getMethod("getImpact", Block.class);
            Method capacityMethod = stressClass.getMethod("getCapacity", Block.class);
            Object impactRegistry = stressClass.getField("IMPACTS").get(null);
            Object capacityRegistry = stressClass.getField("CAPACITIES").get(null);
            Object rpmRegistry = stressClass.getField("RPM").get(null);

            BuiltInRegistries.BLOCK.entrySet().stream()
                    .sorted(Map.Entry.comparingByKey(
                            Comparator.comparing(key -> key.location().toString())
                    ))
                    .forEach(entry -> {
                        ResourceLocation id = entry.getKey().location();
                        if (!inScope.test(id)) {
                            return;
                        }
                        Block block = entry.getValue();
                        rows.add(stressRow(
                                id,
                                "stress_impact",
                                invokeNumber(impactMethod, null, block),
                                "SU/RPM",
                                lookup(impactRegistry, block)
                        ));
                        rows.add(stressRow(
                                id,
                                "stress_capacity",
                                invokeNumber(capacityMethod, null, block),
                                "SU/RPM",
                                lookup(capacityRegistry, block)
                        ));

                        Object rpm = lookup(rpmRegistry, block);
                        if (rpm != null) {
                            Map<String, Object> row = baseMechanicRow(id, "generated_rpm", "RPM");
                            row.put("value_number", recordNumber(rpm, "value"));
                            row.put("may_generate_less", recordBoolean(rpm, "mayGenerateLess"));
                            row.put("provider_class", rpm.getClass().getName());
                            row.put("registered_value", true);
                            rows.add(row);
                        }
                    });
            diagnostics.add(status("stress_registries", "ok", rows.size(), null));
        } catch (ReflectiveOperationException | RuntimeException exception) {
            diagnostics.add(status("stress_registries", "error", rows.size(), exception));
        }
    }

    private Map<String, Object> stressRow(
            ResourceLocation id,
            String factKey,
            double value,
            String unit,
            Object provider
    ) {
        Map<String, Object> row = baseMechanicRow(id, factKey, unit);
        row.put("value_number", value);
        row.put("registered_value", provider != null);
        row.put("provider_class", provider == null ? null : provider.getClass().getName());
        return row;
    }

    private Map<String, Object> baseMechanicRow(
            ResourceLocation id,
            String factKey,
            String unit
    ) {
        Map<String, Object> row = new LinkedHashMap<>();
        row.put("entry_id", id.toString());
        row.put("subsystem", "kinetics");
        row.put("fact_key", factKey);
        row.put("unit", unit);
        row.put("evidence_status", "installed_runtime_confirmed");
        row.put("source_api", STRESS_CLASS);
        return row;
    }

    private void collectConfigs(
            List<Map<String, ?>> rows,
            List<Map<String, ?>> diagnostics
    ) {
        try {
            Class<?> configsClass = Class.forName(CONFIG_CLASS);
            Object serverConfig = configsClass.getMethod("server").invoke(null);
            for (Field sectionField : sortedPublicFields(serverConfig.getClass())) {
                Object section = sectionField.get(serverConfig);
                if (section == null) {
                    continue;
                }
                for (Field optionField : sortedPublicFields(section.getClass())) {
                    Object configValue = optionField.get(section);
                    Method getter = zeroArgumentMethod(configValue, "get");
                    if (getter == null) {
                        continue;
                    }
                    Object effective = getter.invoke(configValue);
                    Map<String, Object> row = new LinkedHashMap<>();
                    row.put("mod_id", "create");
                    row.put("config_scope", "server");
                    row.put("config_path", "server." + sectionField.getName());
                    row.put("config_class", section.getClass().getSimpleName());
                    row.put("field_name", optionField.getName());
                    row.put("effective_value", jsonScalar(effective));
                    row.put("runtime_value_class", effective == null
                            ? null
                            : effective.getClass().getName());
                    row.put("unit_hint", unitHint(optionField.getName()));
                    row.put("evidence_status", "installed_runtime_confirmed");
                    row.put("source_api", CONFIG_CLASS + ".server()");
                    rows.add(row);
                }
            }
            diagnostics.add(status("server_config", "ok", rows.size(), null));
        } catch (ReflectiveOperationException | RuntimeException exception) {
            diagnostics.add(status("server_config", "error", rows.size(), exception));
        }
    }

    private List<Field> sortedPublicFields(Class<?> type) {
        return Arrays.stream(type.getFields())
                .filter(field -> Modifier.isPublic(field.getModifiers()))
                .sorted(Comparator.comparing(Field::getName))
                .toList();
    }

    private Method zeroArgumentMethod(Object target, String name) {
        if (target == null) {
            return null;
        }
        return Arrays.stream(target.getClass().getMethods())
                .filter(method -> method.getName().equals(name))
                .filter(method -> method.getParameterCount() == 0)
                .findFirst()
                .orElse(null);
    }

    private Object lookup(Object registry, Block block) {
        if (registry == null) {
            return null;
        }
        if (registry instanceof Map<?, ?> map) {
            return map.get(block);
        }
        Method getter = Arrays.stream(registry.getClass().getMethods())
                .filter(method -> method.getName().equals("get"))
                .filter(method -> method.getParameterCount() == 1)
                .filter(method -> method.getParameterTypes()[0].isAssignableFrom(block.getClass())
                        || method.getParameterTypes()[0].isAssignableFrom(Block.class))
                .findFirst()
                .orElse(null);
        if (getter == null) {
            return null;
        }
        try {
            Object value = getter.invoke(registry, block);
            return unwrapProvider(value, block);
        } catch (IllegalAccessException | InvocationTargetException exception) {
            throw new IllegalStateException("Create registry lookup failed", exception);
        }
    }

    private Object unwrapProvider(Object value, Block block) {
        if (value instanceof DoubleSupplier supplier) {
            return supplier;
        }
        if (value instanceof Supplier<?> supplier) {
            return supplier.get();
        }
        if (value instanceof Function<?, ?> function) {
            @SuppressWarnings("unchecked")
            Function<Block, ?> blockFunction = (Function<Block, ?>) function;
            return blockFunction.apply(block);
        }
        return value;
    }

    private double invokeNumber(Method method, Object target, Object argument) {
        try {
            Object value = method.invoke(target, argument);
            if (value instanceof Number number) {
                return number.doubleValue();
            }
            throw new IllegalStateException("Create API returned a non-numeric stress value");
        } catch (IllegalAccessException | InvocationTargetException exception) {
            throw new IllegalStateException("Create stress lookup failed", exception);
        }
    }

    private Number recordNumber(Object value, String methodName) {
        try {
            Object result = value.getClass().getMethod(methodName).invoke(value);
            return result instanceof Number number ? number : null;
        } catch (ReflectiveOperationException exception) {
            return null;
        }
    }

    private Boolean recordBoolean(Object value, String methodName) {
        try {
            Object result = value.getClass().getMethod(methodName).invoke(value);
            return result instanceof Boolean bool ? bool : null;
        } catch (ReflectiveOperationException exception) {
            return null;
        }
    }

    private Object jsonScalar(Object value) {
        if (value == null || value instanceof Number || value instanceof Boolean
                || value instanceof String) {
            return value;
        }
        if (value instanceof Enum<?> enumValue) {
            return enumValue.name();
        }
        return String.valueOf(value);
    }

    private String unitHint(String fieldName) {
        String lower = fieldName.toLowerCase();
        if (lower.contains("speed") || lower.endsWith("rpm")) {
            return "RPM_or_blocks_per_second_review_required";
        }
        if (lower.contains("time") || lower.contains("timer") || lower.contains("timeout")) {
            return "ticks_or_seconds_review_required";
        }
        if (lower.contains("range") || lower.contains("distance") || lower.contains("length")
                || lower.contains("height") || lower.contains("depth")) {
            return "blocks";
        }
        if (lower.contains("capacity")) {
            return "mod_specific_capacity_review_required";
        }
        return null;
    }

    private Map<String, Object> status(
            String subsystem,
            String status,
            int rowCount,
            Exception exception
    ) {
        Map<String, Object> row = new LinkedHashMap<>();
        row.put("subsystem", subsystem);
        row.put("status", status);
        row.put("row_count", rowCount);
        row.put("error_class", exception == null ? null : exception.getClass().getName());
        row.put("error_message", exception == null ? null : safeMessage(exception));
        return row;
    }

    private String safeMessage(Exception exception) {
        String message = exception.getMessage();
        if (message == null || message.isBlank()) {
            return "No diagnostic message was provided.";
        }
        return message.replace('\\', '/').replaceAll("[A-Za-z]:/[^\\s]+", "<local-path>");
    }

    record IntrospectionResult(
            List<Map<String, ?>> mechanics,
            List<Map<String, ?>> configs,
            List<Map<String, ?>> diagnostics
    ) {
    }
}
