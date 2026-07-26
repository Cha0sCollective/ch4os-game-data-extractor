#!/usr/bin/env python3
"""Fail closed when the runtime-exporter safety boundary is weakened."""

from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parent
JAVA = ROOT / "src/main/java/dev/chaosarbiter/handbookexporter"
RESOURCES = ROOT / "src/main/resources"


def main() -> int:
    failures: list[str] = []
    java_text = "\n".join(
        path.read_text(encoding="utf-8") for path in sorted(JAVA.glob("*.java"))
    )
    mod_toml = (RESOURCES / "META-INF/neoforge.mods.toml").read_text(encoding="utf-8")
    properties = (ROOT / "gradle.properties").read_text(encoding="utf-8")

    required = {
        "explicit enable flag": 'handbook.export.enabled',
        "disposable confirmation": "DISPOSABLE_INSTANCE",
        "dedicated-server guard": "Dist.DEDICATED_SERVER",
        "zero-player guard": "getPlayerCount() != 0",
        "absolute output requirement": "must be absolute",
        "outside-game-directory guard": "output directory must be outside",
        "create version lock": 'EXPECTED_CREATE = "6.0.10"',
        "pack version lock": 'EXPECTED_PACK = "v2.1"',
        "non-overwriting writes": "StandardOpenOption.CREATE_NEW",
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

    if failures:
        print("\n".join(f"ERROR: {failure}" for failure in failures), file=sys.stderr)
        return 1

    print("Runtime exporter safety contract verified.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
