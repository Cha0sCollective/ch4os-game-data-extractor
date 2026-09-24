package dev.chaosarbiter.handbookexporter;

import java.lang.reflect.InvocationTargetException;
import java.lang.reflect.Method;
import java.util.LinkedHashMap;
import java.util.Map;

final class MechanicRows {
    private MechanicRows() {
    }

    static Map<String, Object> fact(String adapter, String entityKind, String entityId,
                                    String key, Object value, String unit,
                                    Map<String, ?> conditions, String source) {
        if (!(value instanceof Number || value instanceof Boolean || value instanceof String)) {
            throw new IllegalArgumentException("mechanic value must be a JSON scalar");
        }
        Map<String, Object> row = new LinkedHashMap<>();
        row.put("format", "ch4os-mechanic-v2");
        row.put("adapter_id", adapter);
        row.put("entity_kind", entityKind);
        row.put("entry_id", entityId);
        row.put("property_key", key);
        row.put("status", "captured_directly");
        row.put("value", value);
        // Keep the v1 fields so existing archive readers can still ingest these rows.
        int separator = key.indexOf('.');
        row.put("subsystem", separator < 0 ? adapter : key.substring(0, separator));
        row.put("fact_key", separator < 0 ? key : key.substring(separator + 1));
        row.put("value_number", value instanceof Number ? value : null);
        row.put("value_text", value instanceof Number ? null : String.valueOf(value));
        row.put("registered_value", true);
        row.put("evidence_status", "installed_runtime_confirmed");
        row.put("unit", unit);
        row.put("conditions", conditions);
        row.put("source_api", source);
        return row;
    }

    static Object call(Object target, String methodName) throws ReflectiveOperationException {
        Method method = target.getClass().getMethod(methodName);
        try {
            return method.invoke(target);
        } catch (InvocationTargetException exception) {
            throw new IllegalStateException(methodName + " failed", exception.getCause());
        }
    }
}
