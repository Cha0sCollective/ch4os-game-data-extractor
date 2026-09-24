#!/usr/bin/env python3
"""Fail closed when the runtime-exporter safety boundary is weakened."""

from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parent
JAVA = ROOT / "src/main/java/dev/chaosarbiter/handbookexporter"
RESOURCES = ROOT / "src/main/resources"
RUNNER = ROOT / "runner/Run-CreateHandbookExport.ps1"
SAMPLE_LAUNCHER = ROOT / "runner/Run-CreateHandbookExport.cmd"
FULL_LAUNCHER = ROOT / "runner/Run-Full-CreateHandbookExport.cmd"
PACK_LAUNCHER = ROOT / "runner/Run-Pack-HandbookExport.cmd"


def main() -> int:
    failures: list[str] = []
    java_text = "\n".join(
        path.read_text(encoding="utf-8") for path in sorted(JAVA.glob("*.java"))
    )
    mod_toml = (RESOURCES / "META-INF/neoforge.mods.toml").read_text(encoding="utf-8")
    properties = (ROOT / "gradle.properties").read_text(encoding="utf-8")
    runner_text = RUNNER.read_text(encoding="utf-8")
    sample_launcher_text = SAMPLE_LAUNCHER.read_text(encoding="utf-8")
    full_launcher_text = FULL_LAUNCHER.read_text(encoding="utf-8")
    pack_launcher_text = PACK_LAUNCHER.read_text(encoding="utf-8")

    required = {
        "explicit enable flag": 'handbook.export.enabled',
        "environment enable flag": "HANDBOOK_EXPORT_ENABLED",
        "disposable confirmation": "DISPOSABLE_INSTANCE",
        "pack export confirmation": "EXPORT_ALL_PACK_RUNTIME_FACTS",
        "dedicated-server guard": "Dist.DEDICATED_SERVER",
        "zero-player guard": "getPlayerCount() != 0",
        "absolute output requirement": "must be absolute",
        "outside-game-directory guard": "output directory must be outside",
        "legacy Create version lock": '"6.0.10", "v2.1"',
        "legacy NeoForge version lock": '"21.1.233"',
        "generic compatibility profile": '"21.1.*"',
        "profile selection": 'handbook.export.profile',
        "non-overwriting writes": "StandardOpenOption.CREATE_NEW",
        "automatic disposable shutdown": "server.halt(false)",
        "exporter progress prefix": "[HANDBOOK EXPORT]",
        "exporter data stages": "Data stage {}/12",
        "expected block reconciliation": '"expected_block_ids"',
        "effective mechanics output": '"mechanics.jsonl"',
        "effective config output": '"config-values.jsonl"',
        "introspection diagnostics": '"introspection-diagnostics.jsonl"',
        "installed artifact inventory": '"installed-artifacts.jsonl"',
        "archive entry locations": '"artifact-entries.jsonl"',
        "mixin declarations": '"mixin-configs.jsonl"',
        "service providers": '"service-providers.jsonl"',
        "artifact diagnostics": '"artifact-diagnostics.jsonl"',
        "generic registry summaries": '"registry-summaries.jsonl"',
        "generic registry identities": '"registry-entries.jsonl"',
        "generic registry tags": '"registry-tags.jsonl"',
        "raw jar exclusion marker": '"raw_jar_exported"',
        "raw archive content exclusion marker": '"raw_content_exported"',
        "bounded archive metadata reads": "readNBytes",
        "common config root": 'collectConfigRoot(configsClass, "common"',
        "config-group marker handling": "CONFIG_GROUP_SIMPLE_NAME",
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
        "exporter jar hash verification": "create_runtime_exporter-0.5.0.sha256",
        "separate local working root": "CreateHandbookExporter",
        "disposable marker": ".handbook-disposable-instance",
        "loopback-only server": '"server-ip" -Value "127.0.0.1"',
        "ephemeral server port": '"server-port" -Value "0"',
        "disabled query": '"enable-query" -Value "false"',
        "disabled RCON": '"enable-rcon" -Value "false"',
        "Minecraft EULA confirmation": "I ACCEPT",
        "noninteractive owner scope approval": "AcceptExportScope",
        "legacy runner compatibility profile": '"HANDBOOK_EXPORT_PROFILE" = "aoca-v2.1"',
        "headless completion option": "NoOpenExplorer",
        "authenticated evidence verification": "Every manifest-listed evidence file passed byte-count and SHA-256 verification.",
        "whitespace-tolerant confirmations": '.Trim() -replace "\\s+", " "',
        "case-insensitive confirmations": '-ine "I ACCEPT"',
        "sample default": '[string]$Scope = "sample"',
        "pack scope accepted": '[ValidateSet("sample", "full", "pack")]',
        "clean export archive": "Compress-Archive",
        "timestamped stages": "Stage $Number/$TotalStages",
        "human-readable transcript": "Start-Transcript",
        "preserved Minecraft log": "create-export-$runId-minecraft.log",
        "download explanation": "It may perform up to three additional setup downloads",
        "completion summary": "EXPORT COMPLETE",
        "failure summary": "EXPORT FAILED during",
        "primitive size comparison": "$actualBytes -ne $ExpectedBytes",
        "size-path regression test": "-ExpectedBytes $validationBytes",
        "partial-download recovery": "Recovered the complete verified download from the previous run",
        "logs beside export": 'Join-Path $OutputRoot "create-export-$runId.log"',
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

    launcher_required = {
        "sample execution-policy bypass": (
            sample_launcher_text,
            "-ExecutionPolicy Bypass",
        ),
        "full execution-policy bypass": (
            full_launcher_text,
            "-ExecutionPolicy Bypass",
        ),
        "explicit full scope": (
            full_launcher_text,
            "-Scope full",
        ),
        "pack execution-policy bypass": (
            pack_launcher_text,
            "-ExecutionPolicy Bypass",
        ),
        "explicit pack scope": (
            pack_launcher_text,
            "-Scope pack",
        ),
    }
    for label, (launcher_text, needle) in launcher_required.items():
        if needle not in launcher_text:
            failures.append(f"missing launcher {label}: {needle}")

    if failures:
        print("\n".join(f"ERROR: {failure}" for failure in failures), file=sys.stderr)
        return 1

    print("Runtime exporter safety contract verified.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
