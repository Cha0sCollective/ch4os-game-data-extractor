#!/usr/bin/env python3
"""Fail closed when the runtime-exporter safety boundary is weakened."""

from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parent
JAVA = ROOT / "src/main/java/dev/chaosarbiter/handbookexporter"
RESOURCES = ROOT / "src/main/resources"
RUNNER = ROOT / "runner/Run-CreateHandbookExport.ps1"


def main() -> int:
    failures: list[str] = []
    java_text = "\n".join(
        path.read_text(encoding="utf-8") for path in sorted(JAVA.glob("*.java"))
    )
    mod_toml = (RESOURCES / "META-INF/neoforge.mods.toml").read_text(encoding="utf-8")
    properties = (ROOT / "gradle.properties").read_text(encoding="utf-8")
    runner_text = RUNNER.read_text(encoding="utf-8")

    required = {
        "explicit enable flag": 'handbook.export.enabled',
        "environment enable flag": "HANDBOOK_EXPORT_ENABLED",
        "disposable confirmation": "DISPOSABLE_INSTANCE",
        "dedicated-server guard": "Dist.DEDICATED_SERVER",
        "zero-player guard": "getPlayerCount() != 0",
        "absolute output requirement": "must be absolute",
        "outside-game-directory guard": "output directory must be outside",
        "create version lock": 'EXPECTED_CREATE = "6.0.10"',
        "pack version lock": 'EXPECTED_PACK = "v2.1"',
        "non-overwriting writes": "StandardOpenOption.CREATE_NEW",
        "automatic disposable shutdown": "server.halt(false)",
        "exporter progress prefix": "[HANDBOOK EXPORT]",
        "exporter data stages": "Data stage {}/8",
    }
    for label, needle in required.items():
        if needle not in java_text:
            failures.append(f"missing {label}: {needle}")

    forbidden = {
        "network API": ("java.net.", "java.net.http", "Socket(", "URL("),
        "destructive file API": ("Files.delete", "deleteIfExists", "REPLACE_EXISTING"),
        "process execution": ("ProcessBuilder", "Runtime.getRuntime().exec"),
        "mixin declaration": ("[[mixins]]", "coremods.json", "accessTransformers"),
    }
    combined = java_text + "\n" + mod_toml
    for label, needles in forbidden.items():
        for needle in needles:
            if needle in combined:
                failures.append(f"forbidden {label}: {needle}")

    if (RESOURCES / "assets").exists():
        failures.append("raw assets directory must not exist")

    for lock in (
        "minecraft_version=1.21.1",
        "neo_version=21.1.233",
        "mod_license=MIT",
    ):
        if lock not in properties:
            failures.append(f"missing build lock: {lock}")

    runner_required = {
        "official server-pack project/file": "mods/1518930/files/8478465/download",
        "official server-pack hash": "4b835f2362dd97b62d03c6322febebcd3490f2c00b4114f4b972b46e818a5c8b",
        "official server-pack byte size": "314214774",
        "exporter jar hash verification": "create_runtime_exporter-0.1.2.sha256",
        "separate local working root": "CreateHandbookExporter",
        "disposable marker": ".handbook-disposable-instance",
        "loopback-only server": '"server-ip" -Value "127.0.0.1"',
        "ephemeral server port": '"server-port" -Value "0"',
        "disabled query": '"enable-query" -Value "false"',
        "disabled RCON": '"enable-rcon" -Value "false"',
        "Minecraft EULA confirmation": "I ACCEPT",
        "sample default": '[string]$Scope = "sample"',
        "clean export archive": "Compress-Archive",
        "timestamped stages": "Stage $Number/$TotalStages",
        "human-readable transcript": "Start-Transcript",
        "download explanation": "It may perform up to three additional setup downloads",
        "completion summary": "EXPORT COMPLETE",
        "failure summary": "EXPORT FAILED during",
        "primitive size comparison": "$actualBytes -ne $ExpectedBytes",
        "size-path regression test": "-ExpectedBytes $validationBytes",
        "partial-download recovery": "Recovered the complete verified download from the previous run",
    }
    for label, needle in runner_required.items():
        if needle not in runner_text:
            failures.append(f"missing runner {label}: {needle}")

    runner_forbidden = {
        "CurseForge client mutation": (
            "CurseForge\\Minecraft\\Instances",
            "curseforge\\minecraft\\instances",
        ),
        "Bisect access": ("bisecthosting", "ssh ", "sftp"),
        "credential collection": ("Get-Credential", "ConvertTo-SecureString"),
        "unverified execution download": ("Invoke-Expression", "iex "),
    }
    for label, needles in runner_forbidden.items():
        for needle in needles:
            if needle in runner_text:
                failures.append(f"forbidden runner {label}: {needle}")

    if failures:
        print("\n".join(f"ERROR: {failure}" for failure in failures), file=sys.stderr)
        return 1

    print("Runtime exporter safety contract verified.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
