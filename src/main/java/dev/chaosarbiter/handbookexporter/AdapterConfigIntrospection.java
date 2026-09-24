package dev.chaosarbiter.handbookexporter;

import java.lang.reflect.Field;
import java.lang.reflect.Method;
import java.lang.reflect.Modifier;
import java.util.ArrayList;
import java.util.Comparator;
import java.util.IdentityHashMap;
import java.util.List;
import java.util.Map;

/** Reads loaded ConfigBase-style values without treating an on-disk TOML file as effective state. */
final class AdapterConfigIntrospection {
    private AdapterConfigIntrospection() {
    }

    static void collect(String adapter, String modId, String scope, Object root,
                        String nestedPackagePrefix, List<Map<String, ?>> values,
                        List<Map<String, ?>> diagnostics) {
        walk(adapter, modId, scope, root, scope, nestedPackagePrefix, values, diagnostics,
                new IdentityHashMap<>(), 0);
    }

    private static void walk(String adapter, String modId, String scope, Object root, String path,
                             String nestedPackagePrefix, List<Map<String, ?>> values,
                             List<Map<String, ?>> diagnostics, IdentityHashMap<Object, Boolean> visited,
                             int depth) {
        if (root == null || depth > 5 || visited.put(root, true) != null) {
            return;
        }
        List<Field> fields = new ArrayList<>(List.of(root.getClass().getFields()));
        fields.sort(Comparator.comparing(Field::getName));
        for (Field field : fields) {
            if (Modifier.isStatic(field.getModifiers())) {
                continue;
            }
            try {
                Object child = field.get(root);
                if (child == null) {
                    continue;
                }
                Method getter;
                try {
                    getter = child.getClass().getMethod("get");
                } catch (NoSuchMethodException ignored) {
                    getter = null;
                }
                if (getter != null && getter.getParameterCount() == 0) {
                    Object effective = getter.invoke(child);
                    if (effective instanceof Number || effective instanceof Boolean || effective instanceof String) {
                        values.add(AdapterRows.config(adapter, modId, scope, path, field.getName(), effective,
                                null, root.getClass().getName() + "." + field.getName() + ".get"));
                    }
                } else if (child.getClass().getName().startsWith(nestedPackagePrefix)) {
                    walk(adapter, modId, scope, child, path + "." + field.getName(), nestedPackagePrefix,
                            values, diagnostics, visited, depth + 1);
                }
            } catch (ReflectiveOperationException | RuntimeException exception) {
                diagnostics.add(Map.of("subsystem", "mechanic_adapter:" + adapter + ":config:" + path
                                + "." + field.getName(),
                        "status", "partial", "error_class", exception.getClass().getName()));
            }
        }
    }
}
