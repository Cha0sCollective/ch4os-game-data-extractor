package dev.chaosarbiter.handbookexporter;

import java.util.LinkedHashMap;
import java.util.Map;

/** Structured adapter output for facts that cannot be represented by one scalar property. */
public final class AdapterRows {
    private AdapterRows() {
    }

    public static Map<String, Object> config(String adapter, String modId, String scope,
                                      String path, String field, Object effectiveValue,
                                      String unit, String sourceApi) {
        if (effectiveValue == null) {
            throw new IllegalArgumentException("effective config value cannot be null");
        }
        Map<String, Object> row = new LinkedHashMap<>();
        row.put("adapter_id", adapter);
        row.put("mod_id", modId);
        row.put("config_scope", scope);
        row.put("config_path", path);
        row.put("field_name", field);
        row.put("effective_value", effectiveValue);
        row.put("unit_hint", unit);
        row.put("evidence_status", "installed_runtime_confirmed");
        row.put("source_api", sourceApi);
        return row;
    }

    public static Map<String, Object> definition(String adapter, String kind, String id,
                                          Object attributes, Map<String, ?> conditions,
                                          String sourceResourceId, String sourcePackId,
                                          String sourceSha256, String sourceApi) {
        Map<String, Object> row = new LinkedHashMap<>();
        row.put("format", "ch4os-adapter-definition-v1");
        row.put("adapter_id", adapter);
        row.put("kind", kind);
        row.put("id", id);
        row.put("status", "captured_directly");
        row.put("attributes", attributes);
        row.put("conditions", conditions);
        row.put("source_resource_id", sourceResourceId);
        row.put("source_pack_id", sourcePackId);
        row.put("source_sha256", sourceSha256);
        row.put("source_api", sourceApi);
        return row;
    }

    public static Map<String, Object> relation(String adapter, String subjectKind, String subjectId,
                                        String predicate, String objectKind, String objectId,
                                        Map<String, ?> attributes, Map<String, ?> conditions,
                                        String sourceApi) {
        Map<String, Object> row = new LinkedHashMap<>();
        row.put("format", "ch4os-adapter-relation-v1");
        row.put("adapter_id", adapter);
        row.put("subject_kind", subjectKind);
        row.put("subject_id", subjectId);
        row.put("predicate", predicate);
        row.put("object_kind", objectKind);
        row.put("object_id", objectId);
        row.put("status", "captured_directly");
        row.put("attributes", attributes);
        row.put("conditions", conditions);
        row.put("source_api", sourceApi);
        return row;
    }
}
