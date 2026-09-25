"""Prepare read-only per-mod source-analysis packets and review agent findings.

Packets contain installed-pack identities and source routes, never copied source
bodies or JAR contents. Agent findings are proposals until explicitly reviewed.
"""

from __future__ import annotations

import argparse
from collections import defaultdict
from contextlib import closing
import hashlib
import json
from pathlib import Path
import sqlite3

from knowledge_store import KnowledgeStore, _canonical


MAX_CLASS_PATHS = 160


def _subsystem(path: str, mod_id: str) -> str:
    parts = path.removesuffix(".class").split("/")
    lowered = [part.lower() for part in parts]
    for token in (mod_id.lower(), mod_id.lower().replace("_", "")):
        if token in lowered:
            index = lowered.index(token)
            if index + 1 < len(parts) - 1:
                family = parts[index + 1].lower()
                # Device families are small enough to research independently.
                # A single "electricity" packet buried batteries among the
                # network simulation and unrelated machines.
                if family in {"electricity", "kinetics", "circuits", "equipment", "compat"} \
                        and index + 2 < len(parts) - 1:
                    return f"{family}-{parts[index + 2].lower()}"
                return family
    return "other"


def prepare_jobs(capture_db: Path, store: KnowledgeStore, mod_id: str,
                 source_url: str = "") -> tuple[dict, list[dict]]:
    snapshot_id = store.register_capture(capture_db)
    with closing(sqlite3.connect(f"file:{capture_db.resolve().as_posix()}?mode=ro", uri=True)) as db:
        db.row_factory = sqlite3.Row
        mod = db.execute("SELECT id,name,version FROM mods WHERE id=?", (mod_id,)).fetchone()
        if mod is None:
            raise ValueError(f"mod is absent from this capture: {mod_id}")
        items = [dict(row) for row in db.execute(
            "SELECT id,display_name,block_id,implementation_class FROM items WHERE mod_id=? ORDER BY id", (mod_id,))]
        blocks = [dict(row) for row in db.execute(
            "SELECT id,implementation_class,has_block_entity FROM blocks WHERE mod_id=? ORDER BY id", (mod_id,))]
        recipes = [row[0] for row in db.execute("SELECT id FROM recipes WHERE namespace=? ORDER BY id", (mod_id,))]
        facts = [dict(row) for row in db.execute(
            "SELECT entity_kind,entity_id,property_key,status,value_json,unit,conditions_json FROM properties "
            "WHERE entity_id LIKE ? ORDER BY entity_id,property_key", (mod_id + ":%",))]
        relations = [dict(row) for row in db.execute(
            "SELECT subject_kind,subject_id,predicate,object_kind,object_id,conditions_json FROM adapter_relations "
            "WHERE subject_id LIKE ? OR object_id LIKE ? ORDER BY adapter_id,predicate,subject_id,object_id",
            (mod_id + ":%", mod_id + ":%"))] if _has_table(db, "adapter_relations") else []
        artifacts = []
        paths: dict[str, list[str]] = defaultdict(list)
        if _has_table(db, "installed_artifacts"):
            for row in db.execute("SELECT artifact_id,file_name,sha256,byte_size,declared_mod_ids_json "
                                  "FROM installed_artifacts ORDER BY file_name"):
                if mod_id not in json.loads(row[4]):
                    continue
                artifacts.append({"artifact_id": row[0], "file_name": row[1], "sha256": row[2], "byte_size": row[3]})
            if _has_table(db, "artifact_entries"):
                for artifact in artifacts:
                    for row in db.execute("SELECT entry_path FROM artifact_entries WHERE artifact_id=? "
                                          "AND entry_kind='class' ORDER BY entry_path", (artifact["artifact_id"],)):
                        paths[_subsystem(row[0], mod_id)].append(row[0])
        configs = [dict(row) for row in db.execute(
            "SELECT config_scope,config_path,field_name,effective_value_json,unit_hint FROM config_values "
            "WHERE mod_id=? ORDER BY config_path,field_name", (mod_id,))]
    context = {"format": "ch4os-research-context-v1", "snapshot_id": snapshot_id,
               "mod_id": mod_id, "mod_name": mod["name"], "installed_version": mod["version"],
               "installed_artifacts": artifacts, "source_candidate_url": source_url or None,
               "source_match_status": "unverified", "items": items, "blocks": blocks,
               "recipe_ids": recipes, "captured_properties": facts,
               "captured_relations": relations, "effective_config": configs}
    context_sha256 = hashlib.sha256((_canonical(context) + "\n").encode("utf-8")).hexdigest()
    packets = []
    if not paths:
        paths["artifact_inventory_unavailable"] = []
    for subsystem, class_paths in sorted(paths.items()):
        chunks = [class_paths[i:i + MAX_CLASS_PATHS] for i in range(0, len(class_paths), MAX_CLASS_PATHS)] or [[]]
        for index, chunk in enumerate(chunks, 1):
            task_name = f"{subsystem}-{index:02d}"
            # Packets are immutable review inputs. A changed source candidate
            # or context creates a new job instead of colliding with an old one.
            job_id = hashlib.sha256(f"{snapshot_id}:{mod_id}:{task_name}:{context_sha256}:"
                                    f"{','.join(chunk)}".encode()).hexdigest()[:20]
            packet = {"format": "ch4os-research-job-v1", "snapshot_id": snapshot_id,
                      "mod_id": mod_id, "installed_version": mod["version"],
                      "installed_artifacts": artifacts, "source_candidate_url": source_url or None,
                      "source_match_status": "unverified", "mod_context_file": "context.json",
                      "mod_context_sha256": context_sha256,
                      "item_ids": [item["id"] for item in items],
                      "subsystem": subsystem, "chunk": index, "chunks_in_subsystem": len(chunks),
                      "job_id": job_id, "class_paths": chunk,
                      "instructions": [
                          "Inspect installed-version source or the exact installed artifact for every gameplay-relevant path in this packet.",
                          "Trace registrations, capacities, rates, formulas, controls, conditions, and cross-mod interfaces to player-facing entries.",
                          "Return ch4os-research-finding-v1 records; name exact evidence locations and distinguish facts from hypotheses.",
                          "Do not edit repositories or databases; unresolved behavior remains a gap, not an inferred value.",
                      ]}
            store.add_job(packet)
            packets.append(packet)
    return context, packets


def _has_table(db: sqlite3.Connection, name: str) -> bool:
    return db.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name=?", (name,)).fetchone() is not None


def write_packets(capture_db: Path, store: KnowledgeStore, mod_id: str,
                  output: Path, source_url: str = "") -> dict:
    context, packets = prepare_jobs(capture_db, store, mod_id, source_url)
    output.mkdir(parents=True, exist_ok=True)
    context_data = (_canonical(context) + "\n").encode("utf-8")
    context_file = output / "context.json"
    if context_file.exists() and context_file.read_bytes() != context_data:
        raise ValueError(f"context file already differs: {context_file}")
    context_file.write_bytes(context_data)
    manifest = {"format": "ch4os-research-queue-v1", "snapshot_id": context["snapshot_id"],
                "mod_id": mod_id, "context_sha256": hashlib.sha256(context_data).hexdigest(), "jobs": []}
    for packet in packets:
        file_name = f"{packet['subsystem']}-{packet['chunk']:02d}-{packet['job_id']}.json"
        data = (_canonical(packet) + "\n").encode("utf-8")
        destination = output / file_name
        if destination.exists() and destination.read_bytes() != data:
            raise ValueError(f"packet file already differs: {destination}")
        destination.write_bytes(data)
        manifest["jobs"].append({"job_id": packet["job_id"], "file": file_name,
                                 "sha256": hashlib.sha256(data).hexdigest(),
                                 "class_paths": len(packet["class_paths"])})
    manifest_file = output / "manifest.json"
    manifest_file.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    return {"snapshot_id": context["snapshot_id"], "mod_id": mod_id,
            "job_count": len(packets), "output": str(output)}


def submit_file(store: KnowledgeStore, path: Path) -> int:
    if path.suffix.lower() not in {".json", ".jsonl"} or not path.is_file():
        raise ValueError("select a JSON or JSONL finding file")
    if path.stat().st_size > 10 * 1024 * 1024:
        raise ValueError("finding file exceeds 10 MiB")
    raw = path.read_text(encoding="utf-8")
    findings = [json.loads(line) for line in raw.splitlines() if line.strip()] if path.suffix.lower() == ".jsonl" else json.loads(raw)
    if isinstance(findings, dict):
        findings = [findings]
    if not isinstance(findings, list):
        raise ValueError("finding file must contain a record or list of records")
    for finding in findings:
        store.submit_finding(finding)
    return len(findings)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--database", type=Path, required=True, help="Imported capture database")
    parser.add_argument("--knowledge", type=Path, required=True, help="Persistent GDE knowledge database")
    commands = parser.add_subparsers(dest="command", required=True)
    prepare = commands.add_parser("prepare", help="Prepare bounded read-only packets for one mod")
    prepare.add_argument("--mod", required=True)
    prepare.add_argument("--source-url", default="")
    prepare.add_argument("--output", type=Path, required=True)
    submit = commands.add_parser("submit", help="Submit an agent's JSON or JSONL findings for review")
    submit.add_argument("input", type=Path)
    review = commands.add_parser("review", help="Accept or reject one pending finding")
    review.add_argument("finding_id")
    review.add_argument("--decision", choices=("accept", "reject"), required=True)
    review.add_argument("--note", default="")
    listing = commands.add_parser("list", help="List jobs and findings")
    listing.add_argument("--mod", default="")
    listing.add_argument("--status", choices=("pending", "accepted", "rejected", "all"), default="pending")
    tasks = commands.add_parser("tasks", help="List reviewed adapter tasks")
    tasks.add_argument("--mod", default="")
    resolve = commands.add_parser("resolve-task", help="Record how a reviewed adapter task was addressed")
    resolve.add_argument("finding_id")
    resolve.add_argument("--resolution", required=True, help="Capture or test evidence for the completed change")
    args = parser.parse_args(argv)
    store = KnowledgeStore(args.knowledge)
    snapshot_id = store.register_capture(args.database)
    if args.command == "prepare":
        print(json.dumps(write_packets(args.database, store, args.mod, args.output, args.source_url), indent=2))
    elif args.command == "submit":
        print(json.dumps({"submitted": submit_file(store, args.input)}))
    elif args.command == "review":
        print(json.dumps(store.review_finding(snapshot_id, args.finding_id, args.decision, args.database, args.note)))
    elif args.command == "tasks":
        print(json.dumps({"adapter_tasks": store.list_adapter_tasks(snapshot_id, args.mod)}, indent=2))
    elif args.command == "resolve-task":
        store.resolve_adapter_task(snapshot_id, args.finding_id, args.resolution)
        print(json.dumps({"finding_id": args.finding_id, "status": "resolved"}))
    else:
        print(json.dumps({"jobs": store.list_jobs(snapshot_id, args.mod),
                          "findings": store.list_findings(snapshot_id, args.mod, args.status)}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
