package dev.chaosarbiter.handbookexporter;

import com.google.gson.JsonArray;
import com.google.gson.JsonElement;
import com.google.gson.JsonObject;
import com.google.gson.JsonParser;

import java.io.IOException;
import java.io.InputStream;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.LinkOption;
import java.nio.file.Path;
import java.util.ArrayList;
import java.util.Comparator;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Locale;
import java.util.Map;
import java.util.Set;
import java.util.TreeSet;
import java.util.regex.Matcher;
import java.util.regex.Pattern;
import java.util.zip.ZipEntry;
import java.util.zip.ZipFile;

/**
 * Creates a metadata-only census of the exact top-level mod JARs in the
 * disposable server. No archive member is extracted or copied into the export.
 */
final class InstalledArtifactInventory {
    private static final int MAX_METADATA_BYTES = 2 * 1024 * 1024;
    private static final int MAX_MIXIN_CONFIG_BYTES = 4 * 1024 * 1024;
    private static final int MAX_SERVICE_BYTES = 1024 * 1024;
    private static final Pattern TOML_ARRAY_TABLE_PATTERN = Pattern.compile(
            "^\\s*\\[\\[\\s*([^]]+?)\\s*\\]\\]\\s*(?:#.*)?$"
    );
    private static final Pattern MOD_ID_PATTERN = Pattern.compile(
            "^\\s*modId\\s*=\\s*[\"']([a-z0-9_.-]+)[\"']\\s*(?:#.*)?$"
    );
    private static final Pattern JAVA_CLASS_PATTERN = Pattern.compile(
            "[A-Za-z_$][A-Za-z0-9_$]*(?:\\.[A-Za-z_$][A-Za-z0-9_$]*)+"
    );
    private static final Set<String> LOADER_METADATA_NAMES = Set.of(
            "META-INF/neoforge.mods.toml",
            "META-INF/mods.toml",
            "fabric.mod.json",
            "quilt.mod.json"
    );

    private InstalledArtifactInventory() {
    }

    static Result collect(Path gameDirectory) throws IOException {
        Path modsDirectory = gameDirectory.toAbsolutePath().normalize().resolve("mods");
        if (!Files.isDirectory(modsDirectory, LinkOption.NOFOLLOW_LINKS)) {
            throw new IOException("disposable server mods directory is missing");
        }

        List<Path> jars;
        try (var paths = Files.list(modsDirectory)) {
            jars = paths
                    .filter(path -> Files.isRegularFile(path, LinkOption.NOFOLLOW_LINKS))
                    .filter(path -> path.getFileName().toString()
                            .toLowerCase(Locale.ROOT)
                            .endsWith(".jar"))
                    .sorted(Comparator.comparing(path -> path.getFileName().toString()))
                    .toList();
        }

        List<Map<String, ?>> artifacts = new ArrayList<>();
        List<Map<String, ?>> entries = new ArrayList<>();
        List<Map<String, ?>> mixinConfigs = new ArrayList<>();
        List<Map<String, ?>> services = new ArrayList<>();
        List<Map<String, ?>> diagnostics = new ArrayList<>();

        for (Path jar : jars) {
            collectJar(jar, artifacts, entries, mixinConfigs, services, diagnostics);
        }
        return new Result(artifacts, entries, mixinConfigs, services, diagnostics);
    }

    private static void collectJar(
            Path jar,
            List<Map<String, ?>> artifacts,
            List<Map<String, ?>> locations,
            List<Map<String, ?>> mixinConfigs,
            List<Map<String, ?>> services,
            List<Map<String, ?>> diagnostics
    ) throws IOException {
        String fileName = jar.getFileName().toString();
        String sha256 = JsonFiles.sha256(jar);
        String artifactId = "jar:" + fileName + "#sha256:" + sha256;
        long byteSize = Files.size(jar);

        try (ZipFile zip = new ZipFile(jar.toFile())) {
            List<? extends ZipEntry> entries = zip.stream()
                    .filter(entry -> !entry.isDirectory())
                    .sorted(Comparator.comparing(ZipEntry::getName))
                    .toList();
            TreeSet<String> declaredModIds = new TreeSet<>();
            List<String> loaderMetadataPaths = new ArrayList<>();
            int classCount = 0;
            int assetCount = 0;
            int dataCount = 0;
            int signatureCount = 0;

            for (ZipEntry entry : entries) {
                String entryPath = entry.getName();
                if (!isSafeArchivePath(entryPath)) {
                    diagnostics.add(diagnostic(
                            artifactId,
                            fileName,
                            entryPath,
                            "unsafe_archive_entry_path_skipped",
                            new IOException("archive entry path is not safe to index")
                    ));
                    continue;
                }
                String kind = classify(entryPath);
                if (kind.equals("class")) {
                    classCount++;
                }
                if (entryPath.startsWith("assets/")) {
                    assetCount++;
                }
                if (entryPath.startsWith("data/")) {
                    dataCount++;
                }
                if (isSignature(entryPath)) {
                    signatureCount++;
                }
                if (LOADER_METADATA_NAMES.contains(entryPath)) {
                    loaderMetadataPaths.add(entryPath);
                    try {
                        declaredModIds.addAll(readDeclaredModIds(zip, entry));
                    } catch (IOException | RuntimeException exception) {
                        diagnostics.add(diagnostic(
                                artifactId,
                                fileName,
                                entryPath,
                                "loader_metadata_read_failed",
                                exception
                        ));
                    }
                }

                locations.add(entryLocation(artifactId, entry, kind));

                if (isMixinConfig(entryPath)) {
                    try {
                        mixinConfigs.add(readMixinConfig(artifactId, zip, entry));
                    } catch (IOException | RuntimeException exception) {
                        diagnostics.add(diagnostic(
                                artifactId,
                                fileName,
                                entryPath,
                                "mixin_config_read_failed",
                                exception
                        ));
                    }
                }
                if (entryPath.startsWith("META-INF/services/")) {
                    try {
                        services.add(readService(artifactId, zip, entry));
                    } catch (IOException | RuntimeException exception) {
                        diagnostics.add(diagnostic(
                                artifactId,
                                fileName,
                                entryPath,
                                "service_descriptor_read_failed",
                                exception
                        ));
                    }
                }
            }

            Map<String, Object> artifact = new LinkedHashMap<>();
            artifact.put("artifact_id", artifactId);
            artifact.put("file_name", fileName);
            artifact.put("byte_size", byteSize);
            artifact.put("sha256", sha256);
            artifact.put("declared_mod_ids", declaredModIds);
            artifact.put("loader_metadata_paths", loaderMetadataPaths);
            artifact.put("entry_count", entries.size());
            artifact.put("class_entry_count", classCount);
            artifact.put("asset_entry_count", assetCount);
            artifact.put("data_entry_count", dataCount);
            artifact.put("signature_entry_count", signatureCount);
            artifact.put("inventory_status", "complete");
            artifact.put("raw_jar_exported", false);
            artifact.put("raw_entry_content_exported", false);
            artifacts.add(artifact);
        } catch (IOException | RuntimeException exception) {
            diagnostics.add(diagnostic(
                    artifactId,
                    fileName,
                    null,
                    "jar_inventory_failed",
                    exception
            ));
            Map<String, Object> artifact = new LinkedHashMap<>();
            artifact.put("artifact_id", artifactId);
            artifact.put("file_name", fileName);
            artifact.put("byte_size", byteSize);
            artifact.put("sha256", sha256);
            artifact.put("inventory_status", "failed");
            artifact.put("raw_jar_exported", false);
            artifact.put("raw_entry_content_exported", false);
            artifacts.add(artifact);
        }
    }

    private static Map<String, Object> entryLocation(
            String artifactId,
            ZipEntry entry,
            String kind
    ) {
        String entryPath = entry.getName();
        Map<String, Object> row = new LinkedHashMap<>();
        row.put("artifact_id", artifactId);
        row.put("entry_path", entryPath);
        row.put("entry_kind", kind);
        row.put("namespace", namespace(entryPath));
        row.put("logical_id", logicalId(entryPath, kind));
        row.put("class_name", kind.equals("class")
                ? entryPath.substring(0, entryPath.length() - ".class".length())
                        .replace('/', '.')
                : null);
        row.put("byte_size", entry.getSize());
        row.put("compressed_size", entry.getCompressedSize());
        row.put("crc32", entry.getCrc() < 0
                ? null
                : String.format(Locale.ROOT, "%08x", entry.getCrc()));
        row.put("raw_content_exported", false);
        return row;
    }

    private static Set<String> readDeclaredModIds(ZipFile zip, ZipEntry entry)
            throws IOException {
        String text = readText(zip, entry, MAX_METADATA_BYTES);
        TreeSet<String> ids = new TreeSet<>();
        if (entry.getName().endsWith(".toml")) {
            boolean inModsTable = false;
            for (String line : text.split("\\R")) {
                Matcher table = TOML_ARRAY_TABLE_PATTERN.matcher(line);
                if (table.matches()) {
                    inModsTable = table.group(1).trim().equals("mods");
                    continue;
                }
                if (inModsTable) {
                    Matcher modId = MOD_ID_PATTERN.matcher(line);
                    if (modId.matches()) {
                        ids.add(modId.group(1));
                    }
                }
            }
        } else if (entry.getName().equals("fabric.mod.json")) {
            JsonElement root = JsonParser.parseString(text);
            if (root.isJsonObject()) {
                JsonElement id = root.getAsJsonObject().get("id");
                if (id != null && id.isJsonPrimitive()) {
                    ids.add(id.getAsString());
                }
            }
        } else if (entry.getName().equals("quilt.mod.json")) {
            JsonElement root = JsonParser.parseString(text);
            if (root.isJsonObject()) {
                JsonObject loader = object(root.getAsJsonObject(), "quilt_loader");
                if (loader != null) {
                    JsonElement id = loader.get("id");
                    if (id != null && id.isJsonPrimitive()) {
                        ids.add(id.getAsString());
                    }
                }
            }
        }
        return ids;
    }

    private static Map<String, Object> readMixinConfig(
            String artifactId,
            ZipFile zip,
            ZipEntry entry
    ) throws IOException {
        JsonElement root = JsonParser.parseString(
                readText(zip, entry, MAX_MIXIN_CONFIG_BYTES)
        );
        if (!root.isJsonObject()) {
            throw new IOException("mixin configuration root is not an object");
        }
        JsonObject object = root.getAsJsonObject();
        String packageName = string(object, "package");
        List<Map<String, String>> declaredMixins = new ArrayList<>();
        addMixins(declaredMixins, object, "mixins", "common", packageName);
        addMixins(declaredMixins, object, "client", "client", packageName);
        addMixins(declaredMixins, object, "server", "server", packageName);

        Map<String, Object> row = new LinkedHashMap<>();
        row.put("artifact_id", artifactId);
        row.put("config_path", entry.getName());
        row.put("package", packageName);
        row.put("required", bool(object, "required"));
        row.put("plugin", string(object, "plugin"));
        row.put("refmap", string(object, "refmap"));
        row.put("declared_mixins", declaredMixins);
        row.put("raw_config_exported", false);
        return row;
    }

    private static void addMixins(
            List<Map<String, String>> rows,
            JsonObject object,
            String member,
            String side,
            String packageName
    ) {
        JsonElement value = object.get(member);
        if (value == null || !value.isJsonArray()) {
            return;
        }
        JsonArray array = value.getAsJsonArray();
        for (JsonElement element : array) {
            if (!element.isJsonPrimitive()) {
                continue;
            }
            String declared = element.getAsString();
            String className = packageName == null || packageName.isBlank()
                    ? declared
                    : packageName + "." + declared;
            rows.add(Map.of(
                    "side", side,
                    "declared_name", declared,
                    "class_name", className
            ));
        }
    }

    private static Map<String, Object> readService(
            String artifactId,
            ZipFile zip,
            ZipEntry entry
    ) throws IOException {
        String text = readText(zip, entry, MAX_SERVICE_BYTES);
        TreeSet<String> providers = new TreeSet<>();
        for (String rawLine : text.split("\\R")) {
            String line = rawLine.split("#", 2)[0].trim();
            if (!line.isEmpty() && JAVA_CLASS_PATTERN.matcher(line).matches()) {
                providers.add(line);
            }
        }
        Map<String, Object> row = new LinkedHashMap<>();
        row.put("artifact_id", artifactId);
        row.put("descriptor_path", entry.getName());
        row.put(
                "service_interface",
                entry.getName().substring("META-INF/services/".length())
        );
        row.put("provider_classes", providers);
        row.put("raw_descriptor_exported", false);
        return row;
    }

    private static String readText(ZipFile zip, ZipEntry entry, int limit)
            throws IOException {
        if (entry.getSize() > limit) {
            throw new IOException("archive metadata entry exceeds safety limit");
        }
        try (InputStream input = zip.getInputStream(entry)) {
            byte[] bytes = input.readNBytes(limit + 1);
            if (bytes.length > limit) {
                throw new IOException("archive metadata entry exceeds safety limit");
            }
            return new String(bytes, StandardCharsets.UTF_8);
        }
    }

    private static Map<String, Object> diagnostic(
            String artifactId,
            String fileName,
            String entryPath,
            String reason,
            Exception exception
    ) {
        Map<String, Object> row = new LinkedHashMap<>();
        row.put("artifact_id", artifactId);
        row.put("file_name", fileName);
        row.put("entry_path", entryPath);
        row.put("reason", reason);
        row.put("error_class", exception.getClass().getName());
        row.put("local_path_exported", false);
        return row;
    }

    private static boolean isMixinConfig(String path) {
        int separator = path.lastIndexOf('/');
        String name = path.substring(separator + 1).toLowerCase(Locale.ROOT);
        return name.endsWith(".mixins.json")
                || name.endsWith(".mixin.json")
                || name.startsWith("mixins.")
                || name.startsWith("mixin.");
    }

    private static boolean isSafeArchivePath(String path) {
        if (path.isBlank()
                || path.startsWith("/")
                || path.startsWith("\\")
                || path.contains("\\")
                || path.indexOf('\0') >= 0) {
            return false;
        }
        for (String part : path.split("/", -1)) {
            if (part.isEmpty() || part.equals(".") || part.equals("..")) {
                return false;
            }
        }
        return true;
    }

    private static boolean isSignature(String path) {
        String upper = path.toUpperCase(Locale.ROOT);
        return upper.startsWith("META-INF/")
                && (upper.endsWith(".SF")
                || upper.endsWith(".RSA")
                || upper.endsWith(".DSA")
                || upper.endsWith(".EC"));
    }

    private static String classify(String path) {
        String lower = path.toLowerCase(Locale.ROOT);
        if (lower.endsWith(".class")) {
            return "class";
        }
        if (LOADER_METADATA_NAMES.contains(path)) {
            return "loader_metadata";
        }
        if (isMixinConfig(path)) {
            return "mixin_config";
        }
        if (path.startsWith("META-INF/services/")) {
            return "service_descriptor";
        }
        if (lower.matches("assets/[^/]+/lang/.+\\.json")) {
            return "language";
        }
        if (lower.matches("assets/[^/]+/models/item/.+\\.json")) {
            return "item_model";
        }
        if (lower.matches("assets/[^/]+/models/block/.+\\.json")) {
            return "block_model";
        }
        if (lower.matches("assets/[^/]+/blockstates/.+\\.json")) {
            return "blockstate";
        }
        if (lower.matches("assets/[^/]+/textures/.+")) {
            return "texture";
        }
        if (lower.matches("data/[^/]+/recipes?/.+\\.json")) {
            return "recipe";
        }
        if (lower.matches("data/[^/]+/tags/.+\\.json")) {
            return "tag";
        }
        if (lower.matches("data/[^/]+/loot_tables?/.+\\.json")) {
            return "loot_table";
        }
        if (lower.matches("data/[^/]+/advancements?/.+\\.json")) {
            return "advancement";
        }
        if (lower.matches("data/[^/]+/worldgen/.+\\.json")) {
            return "worldgen";
        }
        if (path.startsWith("assets/")) {
            return "asset_resource";
        }
        if (path.startsWith("data/")) {
            return "data_resource";
        }
        return "archive_resource";
    }

    private static String namespace(String path) {
        String[] parts = path.split("/", 3);
        if (parts.length >= 3
                && (parts[0].equals("assets") || parts[0].equals("data"))) {
            return parts[1];
        }
        return null;
    }

    private static String logicalId(String path, String kind) {
        String[] parts = path.split("/");
        if (parts.length < 4
                || !(parts[0].equals("assets") || parts[0].equals("data"))) {
            return null;
        }
        int start = switch (kind) {
            case "item_model", "block_model" -> 4;
            case "blockstate", "language", "texture", "recipe",
                    "loot_table", "advancement", "worldgen" -> 3;
            case "tag" -> 4;
            default -> -1;
        };
        if (start < 0 || start >= parts.length) {
            return null;
        }
        StringBuilder pathPart = new StringBuilder();
        for (int index = start; index < parts.length; index++) {
            if (pathPart.length() > 0) {
                pathPart.append('/');
            }
            pathPart.append(parts[index]);
        }
        String value = pathPart.toString()
                .replaceFirst("\\.(json|png|mcmeta|ogg)$", "");
        return parts[1] + ":" + value;
    }

    private static JsonObject object(JsonObject root, String member) {
        JsonElement value = root.get(member);
        return value != null && value.isJsonObject() ? value.getAsJsonObject() : null;
    }

    private static String string(JsonObject root, String member) {
        JsonElement value = root.get(member);
        return value != null && value.isJsonPrimitive() ? value.getAsString() : null;
    }

    private static Boolean bool(JsonObject root, String member) {
        JsonElement value = root.get(member);
        return value != null && value.isJsonPrimitive() ? value.getAsBoolean() : null;
    }

    record Result(
            List<Map<String, ?>> artifacts,
            List<Map<String, ?>> entries,
            List<Map<String, ?>> mixinConfigs,
            List<Map<String, ?>> services,
            List<Map<String, ?>> diagnostics
    ) {
        static Result empty() {
            return new Result(List.of(), List.of(), List.of(), List.of(), List.of());
        }
    }
}
