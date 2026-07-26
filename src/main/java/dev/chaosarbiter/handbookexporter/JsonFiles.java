package dev.chaosarbiter.handbookexporter;

import com.google.gson.Gson;
import com.google.gson.GsonBuilder;

import java.io.BufferedWriter;
import java.io.IOException;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.Path;
import java.nio.file.StandardOpenOption;
import java.security.MessageDigest;
import java.security.NoSuchAlgorithmException;
import java.util.HexFormat;
import java.util.List;
import java.util.Map;

final class JsonFiles {
    private static final Gson GSON = new GsonBuilder()
            .disableHtmlEscaping()
            .setPrettyPrinting()
            .create();
    private static final Gson COMPACT_GSON = new GsonBuilder()
            .disableHtmlEscaping()
            .create();

    private JsonFiles() {
    }

    static void writeJson(Path path, Object value) throws IOException {
        try (BufferedWriter writer = newFile(path)) {
            GSON.toJson(value, writer);
            writer.newLine();
        }
    }

    static void writeJsonLines(Path path, List<? extends Map<String, ?>> rows) throws IOException {
        try (BufferedWriter writer = newFile(path)) {
            for (Map<String, ?> row : rows) {
                COMPACT_GSON.toJson(row, writer);
                writer.newLine();
            }
        }
    }

    static String sha256(Path path) throws IOException {
        try {
            MessageDigest digest = MessageDigest.getInstance("SHA-256");
            try (var input = Files.newInputStream(path)) {
                byte[] buffer = new byte[8192];
                int read;
                while ((read = input.read(buffer)) >= 0) {
                    digest.update(buffer, 0, read);
                }
            }
            return HexFormat.of().formatHex(digest.digest());
        } catch (NoSuchAlgorithmException exception) {
            throw new IllegalStateException("SHA-256 unavailable", exception);
        }
    }

    private static BufferedWriter newFile(Path path) throws IOException {
        Files.createDirectories(path.getParent());
        return Files.newBufferedWriter(
                path,
                StandardCharsets.UTF_8,
                StandardOpenOption.CREATE_NEW,
                StandardOpenOption.WRITE
        );
    }
}
