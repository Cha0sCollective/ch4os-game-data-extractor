package dev.chaosarbiter.handbookexporter;

import com.mojang.logging.LogUtils;
import net.minecraft.server.MinecraftServer;
import net.neoforged.api.distmarker.Dist;
import net.neoforged.bus.api.IEventBus;
import net.neoforged.fml.ModContainer;
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
            LOGGER.info("[HANDBOOK EXPORT] Starting guarded runtime export.");
            LOGGER.info("[HANDBOOK EXPORT] Verifying dedicated-server state and exact runtime versions.");
            CompatibilityProfile profile = verifyEnvironment(server);
            LOGGER.info(
                    "[HANDBOOK EXPORT] Environment verified for profile {}: Minecraft {}, NeoForge {}.",
                    profile.id(), profile.minecraftVersion(), profile.neoForgeVersion()
            );
            ExporterSettings settings = ExporterSettings.load(FMLPaths.GAMEDIR.get());
            LOGGER.info(
                    "[HANDBOOK EXPORT] Scope is '{}'; output safety checks passed.",
                    settings.scope()
            );
            Map<String, Object> provenance = new RuntimeSnapshotWriter(server, settings).write();
            LOGGER.info(
                    "[HANDBOOK EXPORT] Completed successfully at {} with counts {}",
                    settings.outputDirectory(),
                    provenance.get("counts")
            );
        } catch (Exception exception) {
            LOGGER.error(
                    "[HANDBOOK EXPORT] Refused or failed. No existing output files were overwritten.",
                    exception
            );
        } finally {
            if (ExporterSettings.autoStop(FMLPaths.GAMEDIR.get())) {
                LOGGER.info("[HANDBOOK EXPORT] Requesting clean disposable-server shutdown.");
                server.halt(false);
            }
        }
    }

    private CompatibilityProfile verifyEnvironment(MinecraftServer server) {
        if (FMLEnvironment.dist != Dist.DEDICATED_SERVER) {
            throw new IllegalStateException("exporter only runs in a disposable dedicated-server process");
        }
        if (server.getPlayerList().getPlayerCount() != 0) {
            throw new IllegalStateException("exporter refuses to run while any player is connected");
        }

        CompatibilityProfile profile = CompatibilityProfile.selected();
        profile.verify();
        return profile;
    }
}
