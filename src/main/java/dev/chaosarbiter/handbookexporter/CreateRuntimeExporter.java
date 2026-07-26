package dev.chaosarbiter.handbookexporter;

import com.mojang.logging.LogUtils;
import net.minecraft.SharedConstants;
import net.minecraft.server.MinecraftServer;
import net.neoforged.api.distmarker.Dist;
import net.neoforged.bus.api.IEventBus;
import net.neoforged.fml.ModContainer;
import net.neoforged.fml.ModList;
import net.neoforged.fml.common.Mod;
import net.neoforged.fml.loading.FMLEnvironment;
import net.neoforged.fml.loading.FMLPaths;
import net.neoforged.neoforge.common.NeoForge;
import net.neoforged.neoforge.event.server.ServerStartedEvent;
import org.slf4j.Logger;

import java.util.Map;

@Mod(CreateRuntimeExporter.MOD_ID)
public final class CreateRuntimeExporter {
    static final String MOD_ID = "create_runtime_exporter";
    private static final String EXPECTED_MINECRAFT = "1.21.1";
    private static final String EXPECTED_NEOFORGE = "21.1.233";
    private static final String EXPECTED_CREATE = "6.0.10";
    private static final String EXPECTED_PACK = "v2.1";
    private static final Logger LOGGER = LogUtils.getLogger();

    public CreateRuntimeExporter(IEventBus modEventBus, ModContainer modContainer) {
        NeoForge.EVENT_BUS.addListener(this::onServerStarted);
    }

    private void onServerStarted(ServerStartedEvent event) {
        if (!ExporterSettings.enabled()) {
            LOGGER.info("Create handbook runtime exporter is installed but disabled.");
            return;
        }

        MinecraftServer server = event.getServer();
        try {
            verifyEnvironment(server);
            ExporterSettings settings = ExporterSettings.load(FMLPaths.GAMEDIR.get());
            Map<String, Object> provenance = new RuntimeSnapshotWriter(server, settings).write();
            LOGGER.info(
                    "Create handbook runtime export completed at {} with counts {}",
                    settings.outputDirectory(),
                    provenance.get("counts")
            );
        } catch (Exception exception) {
            LOGGER.error(
                    "Create handbook runtime export refused or failed. No existing output files were overwritten.",
                    exception
            );
        } finally {
            if (ExporterSettings.autoStop()) {
                LOGGER.info("Create handbook runtime exporter requested a clean disposable-server shutdown.");
                server.halt(false);
            }
        }
    }

    private void verifyEnvironment(MinecraftServer server) {
        if (FMLEnvironment.dist != Dist.DEDICATED_SERVER) {
            throw new IllegalStateException("exporter only runs in a disposable dedicated-server process");
        }
        if (server.getPlayerList().getPlayerCount() != 0) {
            throw new IllegalStateException("exporter refuses to run while any player is connected");
        }

        requireVersion("Minecraft", SharedConstants.getCurrentVersion().getName(), EXPECTED_MINECRAFT);
        requireVersion("NeoForge", modVersion("neoforge"), EXPECTED_NEOFORGE);
        requireVersion("Create", modVersion("create"), EXPECTED_CREATE);
        requireVersion(
                "pack declaration",
                ExporterSettings.declaredPackVersion(),
                EXPECTED_PACK
        );
    }

    private String modVersion(String modId) {
        return ModList.get().getModContainerById(modId)
                .map(container -> container.getModInfo().getVersion().toString())
                .orElse("<missing>");
    }

    private void requireVersion(String component, String actual, String expected) {
        if (!expected.equals(actual)) {
            throw new IllegalStateException(
                    component + " version mismatch: expected " + expected + ", found " + actual
            );
        }
    }
}
