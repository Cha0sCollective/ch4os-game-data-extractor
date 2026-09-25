"""Propose source-backed Power Grid 0.6.1 findings after the stage-33 review.

This follow-up reads the installed-artifact identity and existing job packets.
It does not start a server or perform placed-device probes.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path


REPO = Path(__file__).resolve().parent.parent
ARTIFACT = Path(r"E:\Extractor\captures\stage22-display-links-runtime\server\mods\powergrid-mc1.21.1-0.6.1.jar")
JOBS = Path(r"E:\Extractor\captures\research\powergrid-stage33")
OUTPUT = REPO / "research" / "powergrid-source-followup-findings.jsonl"
EXPECTED_SHA256 = "b2835c36af6794a963737c617b5f9dd6b41aba5078d418c88847193fbcf702e5"

if hashlib.sha256(ARTIFACT.read_bytes()).hexdigest() != EXPECTED_SHA256:
    raise ValueError("installed Power Grid artifact changed")

manifest = json.loads((JOBS / "manifest.json").read_text(encoding="utf-8"))
packets = [json.loads((JOBS / entry["file"]).read_text(encoding="utf-8"))
           for entry in manifest["jobs"]]
by_subsystem = {packet["subsystem"]: packet for packet in packets}
snapshot_id = packets[0]["snapshot_id"]
findings: list[dict] = []


def add(subsystem: str, suffix: str, record_type: str, subject_kind: str,
        subject_id: str, **fields) -> None:
    findings.append({
        "format": "ch4os-research-finding-v1",
        "snapshot_id": snapshot_id,
        "job_id": by_subsystem[subsystem]["job_id"],
        "finding_id": "powergrid:source_followup:" + suffix,
        "record_type": record_type,
        "subject_kind": subject_kind,
        "subject_id": subject_id,
        **fields,
    })


def evidence(locator: str) -> dict:
    return {"kind": "installed_artifact", "artifact_sha256": EXPECTED_SHA256,
            "locator": locator}


add("electricity-battery", "battery_assembly_shape", "claim", "item", "powergrid:battery",
    predicate="electrical.battery.assembly_shape",
    value="Ordinary batteries connect into square horizontal layers, up to 3 blocks wide and 5 blocks high. The controller counts width × width × height blocks; capacity equals the effective single-block capacity multiplied by that count.",
    unit=None,
    conditions={"applies_to": "ordinary multiblock battery", "width_blocks": "1..3",
                "height_blocks": "1..5", "single_block_capacity_property": "electrical.battery.single_block_capacity"},
    evidence=evidence("org.patryk3211.powergrid.electricity.battery.MultiBlockBatteryEntity#getMainConnectionAxis,#getMaxLength,#getMaxWidth,#getSize,#setCapacitySize,#updateConnectivity;CustomConnectivityHandler#formMulti"))

add("electricity-battery", "battery_overheat_path", "claim", "item", "powergrid:battery",
    predicate="electrical.battery.overheat_consequence",
    value="The controller's thermal behavior invokes an overheat callback. That callback removes connected wires and causes an explosion at a random block in the assembled battery; explosion strength scales with assembled block count. This is a conditional failure path, not a fixed safe input-voltage rating.",
    unit=None,
    conditions={"trigger": "thermal behavior invokes overheat callback", "assembly": "ordinary multiblock controller"},
    evidence=evidence("org.patryk3211.powergrid.electricity.battery.MultiBlockBatteryEntity#addBehaviours,#overheated;org.patryk3211.powergrid.electricity.base.ThermalBehaviour#overheatCallback"))

add("equipment-zapper", "zapper_projectile_effect", "claim", "item", "powergrid:electrozapper",
    predicate="electrical.portable_tool.projectile_effect",
    value="A shot starts with a movement vector scaled to four blocks per tick and reports a default projectile range of 15 blocks. Direct-hit damage starts at 8 × projectile power, then is divided by up to three targets. When projectile power exceeds 0.6, the hit can arc to as many as two nearby entities within an inflated two-block box. A powered Wither boss is ignored and water destroys the projectile.",
    unit=None,
    conditions={"projectile_power": "max(0.5, portable-battery drawEnergy result) × (2 if boosted else 1)",
                "range_note": "default weapon range, not a hard projectile lifetime limit",
                "nearby_target_count": "up to two additional entities"},
    evidence=evidence("org.patryk3211.powergrid.equipment.zapper.ElectroZapperItem#getDefaultProjectileRange,#use;org.patryk3211.powergrid.equipment.zapper.ZapProjectileEntity#create,#tick,#onHitEntity"))

add("equipment-zapper", "zapper_projectile_scope", "coverage", "system", "powergrid:portable_equipment",
    area="zapper_projectile_model", status="verified",
    explanation="The installed artifact defines projectile speed, default weapon range, charge/boost power, direct-hit scaling, nearby arcs and water behavior.")

for suffix, object_id, condition, locator in [
    ("small_transformer", "powergrid:transformer_small", "no matching 2×2 core arrangement",
     "org.patryk3211.powergrid.electricity.transformer.TransformerCoreBlock#onWrenched"),
    ("medium_transformer", "powergrid:transformer_medium", "matching 2×2 core arrangement",
     "org.patryk3211.powergrid.electricity.transformer.TransformerCoreBlock#onWrenched,#locate2x2"),
]:
    add("electricity-transformer", "core_forms_" + suffix, "relation", "item",
        "powergrid:transformer_core", predicate="forms_when_wrenched_as",
        object_kind="block", object_id=object_id, conditions={"arrangement": condition},
        evidence=evidence(locator))

# These replace stage-33 wording that treated in-world tests as a gate. A
# complete guide needs traceable source facts and effective pack settings.
for subject, subsystem, explanation in [
    ("powergrid:storage", "electricity-battery", "Source review covers battery charge, resistance, assembly shape and overheat path. Finish the charging and thermal-control branches in the installed artifact, then document conditional behavior and effective values."),
    ("powergrid:generation", "kinetics-generator", "Trace remaining generator, rotor, winding and transformer assembly controls in the installed artifact. Explain output as a function of assembly and load rather than a single fixed rating."),
    ("powergrid:wiring", "electricity-wire", "Trace wire cutting, entity-contact effects and connector topology from the installed artifact; relate each path to captured wire specifications."),
    ("powergrid:measurement", "equipment-multimeter", "Trace display scaling, plotter sampling and per-device readouts from the installed artifact, then record the precise modes and units."),
    ("powergrid:control_protection", "electricity-contactor", "Trace relay, redstone, fuse, breaker and high-voltage switch control paths from the installed artifact; document trigger and reset conditions."),
    ("powergrid:circuit_design", "circuits-circuitboard", "Trace board baking, component consumption, circuit execution and cooling from the installed artifact; connect each step to the loaded component mappings."),
    ("powergrid:portable_equipment", "equipment-zapper", "Trace zapper projectile damage and range, low-charge behavior and portable-battery supply from the installed artifact; document charge and boost conditions."),
    ("powergrid:integrations", "compat-cc", "Trace installed per-device ComputerCraft methods and the Create, Simulated and Sable bridges; record only interfaces present in this pack."),
]:
    add(subsystem, subject.split(":", 1)[1] + "_source_scope", "coverage", "system",
        subject, area="full_gameplay_analysis", status="unresolved",
        explanation=explanation)

findings.sort(key=lambda finding: finding["finding_id"])
OUTPUT.write_text("".join(json.dumps(finding, sort_keys=True, separators=(",", ":")) + "\n"
                          for finding in findings), encoding="utf-8")
print({"snapshot_id": snapshot_id, "findings": len(findings), "output": str(OUTPUT)})
