package dev.chaosarbiter.handbookexporter;

import net.minecraft.SharedConstants;
import net.neoforged.fml.ModList;

/** Version expectations for one tested runtime, separate from the safety guards. */
record CompatibilityProfile(
        String id,
        String minecraftVersion,
        String neoForgeVersion,
        String createVersion,
        String declaredPackVersion
) {
    static final String LEGACY_ID = "aoca-v2.1";
    static final String GENERIC_ID = "neoforge-1.21.1";

    static CompatibilityProfile selected() {
        return switch (ExporterSettings.profileId()) {
            case LEGACY_ID -> new CompatibilityProfile(
                    LEGACY_ID, "1.21.1", "21.1.233", "6.0.10", "v2.1"
            );
            case GENERIC_ID -> new CompatibilityProfile(
                    GENERIC_ID, "1.21.1", "21.1.*", null, null
            );
            default -> throw new IllegalStateException(
                    "unsupported compatibility profile: " + ExporterSettings.profileId()
            );
        };
    }

    void verify() {
        requireVersion("Minecraft", SharedConstants.getCurrentVersion().getName(), minecraftVersion);
        String actualNeoForge = modVersion("neoforge");
        if (neoForgeVersion.endsWith(".*")) {
            String family = neoForgeVersion.substring(0, neoForgeVersion.length() - 1);
            if (!actualNeoForge.startsWith(family)) {
                throw new IllegalStateException(
                        "NeoForge version mismatch: expected " + neoForgeVersion
                                + ", found " + actualNeoForge
                );
            }
        } else {
            requireVersion("NeoForge", actualNeoForge, neoForgeVersion);
        }
        if (createVersion != null) {
            requireVersion("Create", modVersion("create"), createVersion);
        }
        if (declaredPackVersion != null) {
            requireVersion(
                    "pack declaration",
                    ExporterSettings.declaredPackVersion(),
                    declaredPackVersion
            );
        }
    }

    private static String modVersion(String modId) {
        return ModList.get().getModContainerById(modId)
                .map(container -> container.getModInfo().getVersion().toString())
                .orElse("<missing>");
    }

    private static void requireVersion(String component, String actual, String expected) {
        if (!expected.equals(actual)) {
            throw new IllegalStateException(
                    component + " version mismatch: expected " + expected + ", found " + actual
            );
        }
    }
}
