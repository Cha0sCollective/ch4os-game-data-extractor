package dev.chaosarbiter.handbookexporter;

import com.google.gson.JsonParser;
import net.minecraft.resources.ResourceLocation;
import net.minecraft.server.MinecraftServer;

import java.io.IOException;
import java.nio.charset.StandardCharsets;
import java.security.MessageDigest;
import java.security.NoSuchAlgorithmException;
import java.util.ArrayList;
import java.util.Comparator;
import java.util.HexFormat;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;

/** Resource-level evidence for definitions absent from the effective recipe manager. */
final class UnloadedRecipeResources {
    private static final int MAX_BYTES = 2 * 1024 * 1024;

    private UnloadedRecipeResources() {
    }

    static List<Map<String, ?>> collect(MinecraftServer server) {
        List<Map<String, ?>> rows = new ArrayList<>();
        server.getResourceManager().listResources("recipe", id -> id.getPath().endsWith(".json"))
                .entrySet().stream()
                .sorted(Map.Entry.comparingByKey(Comparator.comparing(ResourceLocation::toString)))
                .forEach(entry -> {
                    ResourceLocation resourceId = entry.getKey();
                    String path = resourceId.getPath();
                    if (!path.startsWith("recipe/") || !path.endsWith(".json")) {
                        return;
                    }
                    String recipePath = path.substring("recipe/".length(), path.length() - ".json".length());
                    ResourceLocation recipeId = ResourceLocation.fromNamespaceAndPath(
                            resourceId.getNamespace(), recipePath
                    );
                    if (server.getRecipeManager().byKey(recipeId).isPresent()) {
                        return;
                    }
                    Map<String, Object> row = new LinkedHashMap<>();
                    row.put("id", recipeId.toString());
                    row.put("resource_id", resourceId.toString());
                    row.put("source_pack_id", entry.getValue().sourcePackId());
                    row.put("load_status", "not_loaded");
                    row.put("reason_status", "unknown_may_be_condition_or_parse_failure");
                    try (var stream = entry.getValue().open()) {
                        byte[] bytes = stream.readNBytes(MAX_BYTES + 1);
                        if (bytes.length > MAX_BYTES) {
                            row.put("source_status", "too_large");
                        } else {
                            row.put("source_sha256", sha256(bytes));
                            row.put("source_json", JsonParser.parseString(new String(bytes, StandardCharsets.UTF_8)));
                            row.put("source_status", "captured");
                        }
                    } catch (IOException | RuntimeException exception) {
                        row.put("source_status", "failed");
                        row.put("source_error", exception.getClass().getSimpleName());
                    }
                    rows.add(row);
                });
        return rows;
    }

    private static String sha256(byte[] bytes) {
        try {
            return HexFormat.of().formatHex(MessageDigest.getInstance("SHA-256").digest(bytes));
        } catch (NoSuchAlgorithmException exception) {
            throw new IllegalStateException("SHA-256 unavailable", exception);
        }
    }
}
