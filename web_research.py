"""Export small GitHub-first research handoffs from a captured GDE snapshot.

Only packet metadata is registered in the knowledge store. Captures are read
only; neither SQLite files, upstream source bodies, nor JAR bytes are exported.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import re

from catalog import Catalog
from knowledge_store import KnowledgeStore, _canonical


def _decode(row: dict) -> dict:
    return {key.removesuffix("_json") if key.endswith("_json") else key:
            json.loads(value) if key.endswith("_json") and value is not None else value
            for key, value in row.items()}


def _reviewed(store: KnowledgeStore, snapshot: str, mod: str) -> dict:
    result = {}
    with store.connect() as db:
        for table in ("claims", "relations", "formulas"):
            query = (f"SELECT r.*,e.kind AS evidence_kind,e.locator AS evidence_locator,"
                     "e.artifact_sha256,e.source_revision,e.notes AS evidence_notes "
                     f"FROM {table} r JOIN evidence e ON e.snapshot_id=r.snapshot_id AND e.id=r.evidence_id "
                     "WHERE r.snapshot_id=? AND (substr(r.subject_id,1,instr(r.subject_id,':')-1)=?")
            params = [snapshot, mod]
            if table == "relations":
                query += " OR substr(r.object_id,1,instr(r.object_id,':')-1)=?"
                params.append(mod)
            result[table] = [_decode(dict(row)) for row in db.execute(query + ") ORDER BY r.id", params)]
        result["coverage"] = [dict(row) for row in db.execute(
            "SELECT subject_kind,subject_id,area,status,explanation FROM coverage "
            "WHERE snapshot_id=? AND substr(subject_id,1,instr(subject_id,':')-1)=? ORDER BY subject_kind,subject_id,area",
            (snapshot, mod))]
    return result


def snapshot_inventory(capture: Path, store: KnowledgeStore) -> dict:
    catalog = Catalog(capture, store)
    with catalog.connect() as db:
        mods = [dict(row) for row in db.execute(
            "SELECT m.id,m.name,m.version,"
            "COALESCE(i.amount,0) AS item_count,COALESCE(b.amount,0) AS block_count,"
            "COALESCE(r.amount,0) AS recipe_count FROM mods m "
            "LEFT JOIN (SELECT mod_id,COUNT(*) AS amount FROM items GROUP BY mod_id) i ON i.mod_id=m.id "
            "LEFT JOIN (SELECT mod_id,COUNT(*) AS amount FROM blocks GROUP BY mod_id) b ON b.mod_id=m.id "
            "LEFT JOIN (SELECT namespace,COUNT(*) AS amount FROM recipes GROUP BY namespace) r ON r.namespace=m.id "
            "ORDER BY m.id")]
    overview = catalog.overview()
    return {"format": "ch4os-handbook-snapshot-v1", "snapshot_id": catalog.snapshot_id,
            "minecraft_version": overview["minecraft_version"],
            "neoforge_version": overview["neoforge_version"], "mods": mods,
            "recipe_scope": "effective loaded recipes only; counts use recipe namespace"}


def reviewed_export(capture: Path, store: KnowledgeStore, mod_id: str) -> dict:
    catalog = Catalog(capture, store)
    with catalog.connect() as db:
        mod = db.execute("SELECT id,name,version FROM mods WHERE id=?", (mod_id,)).fetchone()
        if mod is None:
            raise ValueError(f"mod is absent from this capture: {mod_id}")
    return {"format": "ch4os-handbook-knowledge-v1", "snapshot_id": catalog.snapshot_id,
            "mod": dict(mod), "reviewed": _reviewed(store, catalog.snapshot_id, mod_id)}


def _compact_item(item: dict) -> dict:
    result = {key: item[key] for key in ("id", "display_name", "block_id", "implementation_class",
                                        "item_tags", "block_tags", "block_entity_types", "block_state_properties",
                                        "cc_peripherals", "display_link_roles", "component_status",
                                        "block_entity_type_status", "max_stack_size", "max_damage", "components")}
    result["properties"] = [{key: value for key, value in prop.items() if key != "source_record"}
                            for prop in item["properties"]]
    result["block"] = {key: item["block"][key] for key in ("id", "implementation_class", "has_block_entity")} if item["block"] else None
    return result


def _compact_recipe(recipe: dict) -> dict:
    result = {key: recipe[key] for key in ("id", "type", "serializer", "source_pack_id", "source_resource_id",
                                          "source_sha256", "input_status", "output_status", "semantic_status",
                                          "result_item_id", "result_count")}
    result["terms"] = [{key: value for key, value in term.items() if key != "definition"}
                       for term in recipe["terms"]]
    detail = recipe["detail"] or {}
    # Keep the effective resource and process parameters; omit duplicate codec
    # representations and expanded runtime ingredient lists. They can dwarf a
    # useful task without adding a new item/quantity or gameplay condition.
    result["effective_detail"] = {key: detail[key] for key in (
        "source_json", "processing_parameters", "runtime_processing", "layout", "sequence",
        "conditions", "dynamic_result") if key in detail}
    result["cross_mod_relations"] = recipe["cross_mod_relations"]
    return result


def build_handoff(capture: Path, store: KnowledgeStore, task: dict) -> tuple[dict, dict]:
    if task.get("format") != "ch4os-web-research-task-v1":
        raise ValueError("unsupported web research task format")
    for field in ("mod_id", "subsystem", "title"):
        if not isinstance(task.get(field), str) or not task[field].strip():
            raise ValueError(f"task needs {field}")
    if not re.fullmatch(r"[a-z0-9_-]+", task["subsystem"]):
        raise ValueError("subsystem must be a lowercase task name")
    if not task.get("questions") or not all(isinstance(q, str) and q.strip() for q in task["questions"]):
        raise ValueError("task needs focused research questions")
    source = task.get("source", {})
    if not re.fullmatch(r"https://github\.com/[^/]+/[^/]+", source.get("repository", "")):
        raise ValueError("task needs a GitHub source repository URL")
    if not re.fullmatch(r"[0-9a-f]{40}", source.get("revision", "")):
        raise ValueError("pin source to a full Git commit SHA")
    if source.get("match_status") not in {"release_candidate", "exact_installed_version"}:
        raise ValueError("source match status must be explicit")
    if not source.get("match_note"):
        raise ValueError("source needs the reason for choosing this revision")
    catalog = Catalog(capture, store)
    mod_id = task["mod_id"]
    with catalog.connect() as db:
        mod = db.execute("SELECT * FROM mods WHERE id=?", (mod_id,)).fetchone()
        if mod is None:
            raise ValueError(f"mod is absent from this capture: {mod_id}")
        if source.get("declared_version") != mod["version"]:
            raise ValueError("source declared version differs from installed mod version")
        inventory = [dict(row) for row in db.execute(
            "SELECT id,display_name,block_id FROM items WHERE mod_id=? ORDER BY id", (mod_id,))]
        non_item_blocks = [dict(row) for row in db.execute(
            "SELECT id,implementation_class,has_block_entity FROM blocks "
            "WHERE mod_id=? AND (item_id IS NULL OR item_id='minecraft:air') ORDER BY id", (mod_id,))]
        item_ids = sorted(set(task.get("item_ids", [])))
        if not item_ids or len(item_ids) > 80:
            raise ValueError("select 1 to 80 item IDs for a bounded assignment")
        artifacts = []
        if catalog._has_table(db, "installed_artifacts"):
            artifacts = [dict(row) for row in db.execute(
                "SELECT file_name,sha256,declared_mod_ids_json FROM installed_artifacts ORDER BY file_name")
                if mod_id in json.loads(row["declared_mod_ids_json"])]
            for artifact in artifacts:
                artifact.pop("declared_mod_ids_json")
        configs = [_decode(dict(row)) for row in db.execute(
            "SELECT config_scope,config_path,field_name,effective_value_json,unit_hint,evidence_status,source_api "
            "FROM config_values WHERE mod_id=? ORDER BY config_scope,config_path,field_name", (mod_id,))]
        if task.get("config_fields"):
            wanted = set(task["config_fields"])
            configs = [row for row in configs if row["field_name"] in wanted]
            missing = wanted - {row["field_name"] for row in configs}
            if missing:
                raise ValueError(f"selected config fields are absent: {sorted(missing)}")
        definitions = []
        if catalog._has_table(db, "adapter_definitions"):
            for row in db.execute("SELECT adapter_id,kind,id,status,attributes_json,conditions_json,"
                                  "source_resource_id,source_pack_id,source_sha256,source_api "
                                  "FROM adapter_definitions ORDER BY adapter_id,kind,id"):
                if row["adapter_id"] == mod_id and row["kind"] in task.get("definition_kinds", []):
                    definitions.append(_decode(dict(row)))
        definition_ids = {row["id"] for row in definitions}
        relations = []
        selected = set(item_ids) | set(task.get("fluid_ids", [])) | definition_ids
        if catalog._has_table(db, "adapter_relations"):
            for row in db.execute("SELECT adapter_id,subject_kind,subject_id,predicate,object_kind,object_id,status,"
                                  "attributes_json,conditions_json,source_api FROM adapter_relations "
                                  "ORDER BY adapter_id,subject_kind,subject_id,predicate,object_kind,object_id"):
                if row["subject_id"] in selected or row["object_id"] in selected:
                    relations.append(_decode(dict(row)))
        fluid_ids = sorted(set(task.get("fluid_ids", [])) | {
            row[key + "_id"] for row in relations for key in ("subject", "object")
            if row[key + "_kind"] == "fluid"})
        # Registry tags distinguish actual loaded fluid memberships from names
        # that merely resemble another mod's fuel.
        fluid_tags = [dict(row) for row in db.execute(
            "SELECT registry_id,tag,member FROM registry_tags WHERE registry_id='minecraft:fluid' ORDER BY tag,member")
            if row["member"] in fluid_ids]
        fluid_tag_ids = {row["tag"] for row in fluid_tags}
        recipe_ids = set(task.get("recipe_ids", []))
        for row in db.execute("SELECT id,result_item_id FROM recipes ORDER BY id"):
            if row["result_item_id"] in item_ids:
                recipe_ids.add(row["id"])
        for row in db.execute("SELECT recipe_id,kind,target_id FROM recipe_terms ORDER BY recipe_id"):
            if (row["kind"] == "fluid" and row["target_id"] in fluid_ids) or (
                    row["kind"] == "fluid_tag" and row["target_id"] in fluid_tag_ids):
                recipe_ids.add(row["recipe_id"])
        installed_mods = [dict(row) for row in db.execute("SELECT id,name,version FROM mods ORDER BY id")]
    items = [catalog.item(item_id) for item_id in item_ids]
    for item in items:
        recipe_ids.update(item["makes"])
        recipe_ids.update(item["uses"])
    recipes = [_compact_recipe(catalog.recipe(recipe_id)) for recipe_id in sorted(recipe_ids)]
    context = {"format": "ch4os-web-research-context-v1", "snapshot_id": catalog.snapshot_id,
               "mod": dict(mod), "source": source, "installed_artifacts": artifacts,
               "installed_mods": installed_mods, "mod_item_inventory": inventory,
               "non_item_blocks": non_item_blocks,
               "items": [_compact_item(item) for item in items], "effective_config": configs, "adapter_definitions": definitions,
               "captured_relations": relations, "fluid_tags": fluid_tags, "recipes": recipes,
               "reviewed": _reviewed(store, catalog.snapshot_id, mod_id),
               "pending_findings": store.list_findings(catalog.snapshot_id, mod_id),
               "adapter_tasks": store.list_adapter_tasks(catalog.snapshot_id, mod_id),
               "recipe_scope": "effective loaded recipes involving selected entries, fluids or explicit recipe IDs"}
    context_hash = hashlib.sha256((_canonical(context) + "\n").encode()).hexdigest()
    job_id = hashlib.sha256((_canonical(task) + ":" + context_hash).encode()).hexdigest()[:20]
    packet = {"format": "ch4os-research-job-v1", "snapshot_id": catalog.snapshot_id,
              "job_id": job_id, "mod_id": mod_id, "installed_version": mod["version"],
              "subsystem": task["subsystem"], "task": task, "item_ids": item_ids,
              "source_candidate_url": source["repository"], "source_match_status": source["match_status"],
              "installed_artifacts": artifacts, "mod_context_file": "context.json",
              "mod_context_sha256": context_hash, "instructions": [
                  "Read pinned GitHub source, explain player-facing behavior, and return report plus proposed findings.",
                  "Do not modify repositories or databases. Do not run live probes or propose in-game testing."]}
    return context, packet


def render_context(context: dict) -> str:
    mod = context["mod"]
    lines = [f"# Captured context: {mod['name']} {mod['version']}", "",
             f"Snapshot: `{context['snapshot_id']}`. This export contains data and evidence routes, not mod source.", "",
             "Captured settings and loaded data take precedence over upstream defaults. Unknown values remain unknown.", ""]
    sections = [("Selected items", "items"), ("Effective configuration", "effective_config"),
                ("Loaded gameplay definitions", "adapter_definitions"), ("Captured relationships", "captured_relations"),
                ("Loaded fluid tag memberships", "fluid_tags"), ("Effective recipes", "recipes"),
                ("Reviewed knowledge for this snapshot", "reviewed"), ("Pending findings", "pending_findings"),
                ("Adapter tasks", "adapter_tasks"), ("Full mod item inventory (scope reference)", "mod_item_inventory"),
                ("Blocks without inventory items", "non_item_blocks"),
                ("Installed mod identities (integration scope)", "installed_mods")]
    for title, key in sections:
        value = context[key]
        if key in {"installed_mods", "mod_item_inventory"}:
            lines.extend([f"## {title}", "", "| ID | Version or item name |", "| --- | --- |"])
            lines.extend(f"| `{row['id']}` | {row.get('version', row.get('display_name', ''))} |" for row in value)
            lines.append("")
        else:
            data = "\n".join(_canonical(row) for row in value) if isinstance(value, list) else _canonical(value)
            lines.extend([f"## {title}", "", "One JSON record per line; empty sections contain no captured records.", "",
                          "```jsonl" if isinstance(value, list) else "```json", data, "```", ""])
    return "\n".join(lines)


def render_prompt(context: dict, packet: dict) -> str:
    task, source = packet["task"], context["source"]
    base = source["repository"] + "/blob/" + source["revision"] + "/"
    raw_base = source["repository"].replace("https://github.com/", "https://raw.githubusercontent.com/") + "/" + source["revision"] + "/"
    lines = [f"# {task['title']}", "",
             "Read the linked GitHub implementation and produce a thorough, practical gameplay report for a modpack handbook.",
             "This is an external research assignment in ordinary Chat with web access. Return your work in this chat.", "",
             f"Target: **{context['mod']['name']} {context['mod']['version']}**.",
             f"Snapshot: `{packet['snapshot_id']}`. Job: `{packet['job_id']}`.",
             f"Source revision: `{source['revision']}`. Match status: `{source['match_status']}`.",
             source["match_note"], "",
             "Use this pinned revision for all source links. Follow helpers and registrations as needed. Read method bodies; search snippets are insufficient.",
             "The companion context contains the installed items, effective settings, loaded recipes, fuel memberships, and existing GDE facts.",
             "Use those pack values when they override upstream defaults. Do not substitute the latest branch or another Minecraft/loader version.", "",
             "## Questions to answer", ""]
    lines.extend(f"{index}. {question}" for index, question in enumerate(task["questions"], 1))
    lines.extend(["", "## Starting source routes", ""])
    for route in source.get("routes", []):
        lines.append(f"- [{route.get('purpose', route['path'])}]({base + route['path']}) ([raw source]({raw_base + route['path']}))")
    lines.extend(["", "## Scope and working rules", "",
                  "- Explain setup, operation, controls, units, limits, scaling, item interactions, and common failure causes from the code.",
                  "- Trace each consequential number or behavior to a pinned file and method, with line links when accessible. Show formulas and conditions separately from example values.",
                  "- Cover every selected item. Distinguish static item ratings from fuel-dependent, multiblock, configured, or upgraded values.",
                  "- Cross-mod conclusions must follow code registrations, loaded tags, effective recipes, or captured interfaces in this pack. Names alone do not establish compatibility.",
                  "- Read source directly. Do not launch Minecraft, run live probes, or turn missing information into an in-game testing assignment.",
                  "- If a source file cannot be accessed, identify the file and missing answer plainly. Do not invent its behavior or cite a file you did not read.",
                  "- Propose reusable extractor fields and typed relationships for gaps. Give the source accessor or calculation where you find it.",
                  "- Do not edit repositories or databases. Your findings are proposals for local review.", "",
                  "## Return two parts", "",
                  "First, a readable Markdown report: overview; device comparison; setup and controls; formulas with worked examples; item interactions and integrations; troubleshooting; GDE gaps; and files actually read.",
                  "End with a selected-item checklist: covered / decorative-or-component / unanswered, with one short reason per item.", "",
                  "Second, a JSON array of `ch4os-research-finding-v1` records. Use these exact metadata values on every record:", "",
                  "```json", json.dumps({"format": "ch4os-research-finding-v1", "snapshot_id": packet["snapshot_id"],
                                          "job_id": packet["job_id"]}, indent=2), "```", "",
                  f"Give each record a unique `finding_id` beginning `{packet['mod_id']}:web_{task['subsystem'].replace('-', '_')}:`.",
                  "Every record needs `record_type`, `subject_kind`, and `subject_id`. Use captured item/block/recipe IDs exactly; system/interface IDs must be namespaced.", "",
                  "- `claim`: `predicate`, non-null `value`, optional `unit`, and `conditions` object.",
                  "- `relation`: `predicate`, `object_kind`, `object_id`, and `conditions` object.",
                  "- `formula`: `result_predicate`, structured `expression` object, `unit`, and `conditions` object.",
                  "- `coverage`: `area`, `status` (`verified`, `not_applicable`, or `unresolved`), and `explanation`.",
                  "- `gap` or `adapter_request`: `description`; include code locations and proposed accessors in the description.", "",
                  "Claims, relations, and formulas also need `evidence`. For this job use:", "",
                  "```json", json.dumps({"kind": "exact_source", "locator": base + "FILE_PATH#LSTART-LEND (also name the method)",
                                          "source_revision": source["revision"],
                                          "artifact_sha256": context["installed_artifacts"][0]["sha256"] if context["installed_artifacts"] else None,
                                          "match_basis": source["match_status"],
                                          "notes": "Explain the code path and any effective config or loaded-data substitution."}, indent=2), "```", "",
                  "Preserve the supplied match_basis; the local reviewer handles source-version acceptance. Do not claim runtime confirmation from reading source.",
                  "Do not return placeholder records. Unknown values belong in gap records, not zero-valued claims.", ""])
    if task.get("outside_scope"):
        lines.extend(["## Assigned separately", "", *[f"- {entry}" for entry in task["outside_scope"]], ""])
    return "\n".join(lines)


def write_handoff(capture: Path, store: KnowledgeStore, task: dict, output: Path) -> dict:
    context, packet = build_handoff(capture, store, task)
    prompt, readable = render_prompt(context, packet), render_context(context)
    files = {"context.json": _canonical(context) + "\n",
             "job.json": json.dumps(packet, ensure_ascii=False, indent=2) + "\n",
             "prompt.md": prompt, "context.md": readable, "handoff.md": prompt + "\n---\n\n" + readable}
    manifest = {"format": "ch4os-web-research-handoff-v1", "snapshot_id": packet["snapshot_id"],
                "job_id": packet["job_id"], "files": {name: hashlib.sha256(body.encode()).hexdigest()
                                                         for name, body in sorted(files.items())}}
    files["manifest.json"] = json.dumps(manifest, indent=2) + "\n"
    # Check all destinations before registering or writing anything.
    for name, body in files.items():
        path = output / name
        if path.exists() and path.read_bytes() != body.encode():
            raise ValueError(f"handoff already differs; choose a new directory: {path}")
    store.add_job(packet)
    output.mkdir(parents=True, exist_ok=True)
    for name, body in files.items():
        (output / name).write_bytes(body.encode())
    return {"snapshot_id": packet["snapshot_id"], "job_id": packet["job_id"],
            "items": len(context["items"]), "recipes": len(context["recipes"]), "output": str(output)}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--database", type=Path, required=True)
    parser.add_argument("--knowledge", type=Path, required=True)
    commands = parser.add_subparsers(dest="command", required=True)
    prepare = commands.add_parser("prepare")
    prepare.add_argument("--task", type=Path, required=True)
    prepare.add_argument("--output", type=Path, required=True)
    inventory = commands.add_parser("inventory")
    inventory.add_argument("--output", type=Path, required=True)
    reviewed = commands.add_parser("reviewed")
    reviewed.add_argument("--mod", required=True)
    reviewed.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(argv)
    store = KnowledgeStore(args.knowledge)
    if args.command == "prepare":
        result = write_handoff(args.database, store, json.loads(args.task.read_text(encoding="utf-8")), args.output)
    else:
        result = snapshot_inventory(args.database, store) if args.command == "inventory" else reviewed_export(args.database, store, args.mod)
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_bytes((json.dumps(result, ensure_ascii=False, indent=2) + "\n").encode())
        result = {"snapshot_id": result["snapshot_id"], "output": str(args.output)}
    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
