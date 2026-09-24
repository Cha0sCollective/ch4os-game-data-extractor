package dev.chaosarbiter.handbookexporter;

import java.io.IOException;
import java.nio.file.Files;
import java.nio.file.LinkOption;
import java.nio.file.Path;
import java.util.Locale;

final class ExporterSettings {
    static final String CONFIRMATION = "DISPOSABLE_INSTANCE";
    static final String FULL_CONFIRMATION = "EXPORT_ALL_CREATE_RUNTIME_FACTS";
    static final String PACK_CONFIRMATION = "EXPORT_ALL_PACK_RUNTIME_FACTS";

    private final Path outputDirectory;
    private final String scope;
    private final String declaredPackVersion;

    private ExporterSettings(Path outputDirectory, String scope, String declaredPackVersion) {
        this.outputDirectory = outputDirectory;
        this.scope = scope;
        this.declaredPackVersion = declaredPackVersion;
    }

    static ExporterSettings load(Path gameDirectory) throws IOException {
        if (!enabled()) {
            throw new IllegalStateException("handbook.export.enabled is not true");
        }
        if (!CONFIRMATION.equals(value(
                "handbook.export.confirm",
                "HANDBOOK_EXPORT_CONFIRM",
                ""
        ))) {
            throw new IllegalStateException("disposable-instance confirmation is missing");
        }

        String outputValue = value(
                "handbook.export.output",
                "HANDBOOK_EXPORT_OUTPUT",
                ""
        ).trim();
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

        String scope = value(
                "handbook.export.scope",
                "HANDBOOK_EXPORT_SCOPE",
                "sample"
        )
                .trim().toLowerCase(Locale.ROOT);
        if (!scope.equals("sample")
                && !scope.equals("full")
                && !scope.equals("pack")) {
            throw new IllegalStateException(
                    "handbook.export.scope must be sample, full, or pack"
            );
        }
        if (scope.equals("full")
                && !FULL_CONFIRMATION.equals(value(
                        "handbook.export.fullConfirm",
                        "HANDBOOK_EXPORT_FULL_CONFIRM",
                        ""
                ))) {
            throw new IllegalStateException("full-export confirmation is missing");
        }
        if (scope.equals("pack")
                && !PACK_CONFIRMATION.equals(value(
                        "handbook.export.packConfirm",
                        "HANDBOOK_EXPORT_PACK_CONFIRM",
                        ""
                ))) {
            throw new IllegalStateException("pack-export confirmation is missing");
        }

        return new ExporterSettings(output, scope, declaredPackVersion());
    }

    static boolean enabled() {
        return Boolean.parseBoolean(value(
                "handbook.export.enabled",
                "HANDBOOK_EXPORT_ENABLED",
                "false"
        ));
    }

    static boolean autoStop(Path gameDirectory) {
        boolean requested = Boolean.parseBoolean(value(
                "handbook.export.autoStop",
                "HANDBOOK_EXPORT_AUTOSTOP",
                "false"
        ));
        return requested && (
                Files.isRegularFile(
                        gameDirectory.resolve(".handbook-disposable-instance"),
                        LinkOption.NOFOLLOW_LINKS
                ) || Files.isRegularFile(
                        gameDirectory.resolve(".ch4os-disposable-instance"),
                        LinkOption.NOFOLLOW_LINKS
                )
        );
    }

    static String declaredPackVersion() {
        return value(
                "handbook.export.packVersion",
                "HANDBOOK_EXPORT_PACK_VERSION",
                ""
        );
    }

    static String profileId() {
        return value(
                "handbook.export.profile",
                "HANDBOOK_EXPORT_PROFILE",
                CompatibilityProfile.GENERIC_ID
        ).trim();
    }

    private static String value(String propertyName, String environmentName, String defaultValue) {
        String propertyValue = System.getProperty(propertyName);
        if (propertyValue != null) {
            return propertyValue;
        }
        String environmentValue = System.getenv(environmentName);
        return environmentValue == null ? defaultValue : environmentValue;
    }

    Path outputDirectory() {
        return outputDirectory;
    }

    String scope() {
        return scope;
    }

    String declaredPackVersionValue() {
        return declaredPackVersion;
    }
}
