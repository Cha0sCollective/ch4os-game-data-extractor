package dev.chaosarbiter.handbookexporter;

import java.io.IOException;
import java.nio.file.Files;
import java.nio.file.Path;
import java.util.Locale;

final class ExporterSettings {
    static final String CONFIRMATION = "DISPOSABLE_INSTANCE";
    static final String FULL_CONFIRMATION = "EXPORT_ALL_CREATE_RUNTIME_FACTS";

    private final Path outputDirectory;
    private final String scope;

    private ExporterSettings(Path outputDirectory, String scope) {
        this.outputDirectory = outputDirectory;
        this.scope = scope;
    }

    static ExporterSettings load(Path gameDirectory) throws IOException {
        if (!Boolean.getBoolean("handbook.export.enabled")) {
            throw new IllegalStateException("handbook.export.enabled is not true");
        }
        if (!CONFIRMATION.equals(System.getProperty("handbook.export.confirm"))) {
            throw new IllegalStateException("disposable-instance confirmation is missing");
        }

        String outputValue = System.getProperty("handbook.export.output", "").trim();
        if (outputValue.isEmpty()) {
            throw new IllegalStateException("handbook.export.output must be an absolute path");
        }

        Path output = Path.of(outputValue).toAbsolutePath().normalize();
        if (!Path.of(outputValue).isAbsolute()) {
            throw new IllegalStateException("handbook.export.output must be absolute");
        }
        if (output.startsWith(gameDirectory.toAbsolutePath().normalize())) {
            throw new IllegalStateException("output directory must be outside the Minecraft game directory");
        }
        if (Files.exists(output)) {
            try (var files = Files.list(output)) {
                if (files.findAny().isPresent()) {
                    throw new IllegalStateException("output directory must not already contain files");
                }
            }
        }

        String scope = System.getProperty("handbook.export.scope", "sample")
                .trim().toLowerCase(Locale.ROOT);
        if (!scope.equals("sample") && !scope.equals("full")) {
            throw new IllegalStateException("handbook.export.scope must be sample or full");
        }
        if (scope.equals("full")
                && !FULL_CONFIRMATION.equals(System.getProperty("handbook.export.fullConfirm"))) {
            throw new IllegalStateException("full-export confirmation is missing");
        }

        return new ExporterSettings(output, scope);
    }

    Path outputDirectory() {
        return outputDirectory;
    }

    String scope() {
        return scope;
    }
}
