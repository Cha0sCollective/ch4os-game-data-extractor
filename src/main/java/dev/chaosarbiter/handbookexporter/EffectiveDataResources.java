package dev.chaosarbiter.handbookexporter;

import com.google.gson.JsonElement;
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
import java.util.List;
import java.util.Map;
import java.util.function.Predicate;

/** Reads the effective layer of a named data directory after datapacks have loaded. */
public final class EffectiveDataResources {
    private static final int MAX_BYTES = 2 * 1024 * 1024;

    private EffectiveDataResources() {
    }

    public static List<LoadedJson> collect(MinecraftServer server, String directory,
                                    Predicate<ResourceLocation> inScope) {
        if (directory.isBlank() || directory.startsWith("/") || directory.contains("..")) {
            throw new IllegalArgumentException("invalid data directory");
        }
        List<LoadedJson> rows = new ArrayList<>();
        server.getResourceManager().listResources(directory, id -> id.getPath().endsWith(".json"))
                .entrySet().stream()
                .sorted(Map.Entry.comparingByKey(Comparator.comparing(ResourceLocation::toString)))
                .forEach(entry -> {
                    ResourceLocation id = entry.getKey();
                    if (!inScope.test(id)) {
                        return;
                    }
                    String pack = entry.getValue().sourcePackId();
                    try (var stream = entry.getValue().open()) {
                        byte[] bytes = stream.readNBytes(MAX_BYTES + 1);
                        if (bytes.length > MAX_BYTES) {
                            rows.add(new LoadedJson(id, pack, null, null, "too_large", null));
                            return;
                        }
                        String sha256 = sha256(bytes);
                        JsonElement json = JsonParser.parseString(new String(bytes, StandardCharsets.UTF_8));
                        rows.add(new LoadedJson(id, pack, sha256, json, "captured", null));
                    } catch (IOException | RuntimeException exception) {
                        rows.add(new LoadedJson(id, pack, null, null, "failed",
                                exception.getClass().getName()));
                    }
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

    public record LoadedJson(ResourceLocation resourceId, String sourcePackId, String sourceSha256,
                      JsonElement json, String status, String errorClass) {
    }
}
