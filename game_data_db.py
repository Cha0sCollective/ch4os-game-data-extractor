"""Import a Ch4oS runtime capture ZIP into a local SQLite item/recipe database."""

from __future__ import annotations

import argparse
from contextlib import closing
import hashlib
import json
import os
from pathlib import Path
import sqlite3
import sys
import zipfile


SCHEMA = Path(__file__).with_name("schema.sql")
REQUIRED = {"provenance.json", "mods.jsonl", "items.jsonl", "blocks.jsonl", "recipes.jsonl"}
PROPERTY_STATUSES = {"captured_directly", "derived", "unavailable", "unsupported",
                     "not_applicable", "failed_to_collect"}


def compact(value: object) -> str:
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"))


def nullable_json(value: object) -> str | None:
    return None if value is None else compact(value)


def namespace(identifier: str) -> str:
    return identifier.partition(":")[0]


def rows(archive: zipfile.ZipFile, name: str):
    if name not in archive.namelist():
        return
    with archive.open(name) as source:
        for number, line in enumerate(source, 1):
            if line.strip():
                try:
                    yield json.loads(line)
                except (UnicodeDecodeError, json.JSONDecodeError) as exc:
                    raise ValueError(f"{name}:{number}: invalid JSON: {exc}") from exc


def verify_capture(archive: zipfile.ZipFile) -> tuple[dict, dict]:
    names = archive.namelist()
    if len(names) != len(set(names)):
        raise ValueError("capture ZIP contains duplicate entry names")
    if "manifest.json" not in names:
        raise ValueError("capture ZIP has no manifest.json")
    manifest = json.loads(archive.read("manifest.json"))
    if manifest.get("format") != "create-handbook-runtime-export-v1":
        raise ValueError("unsupported capture format")
    listed = {entry["name"]: entry for entry in manifest["files"]}
    if len(listed) != len(manifest["files"]):
        raise ValueError("manifest lists a file more than once")
    missing = REQUIRED - listed.keys()
    if missing:
        raise ValueError(f"capture missing required evidence: {', '.join(sorted(missing))}")
    if set(names) != set(listed) | {"manifest.json"}:
        raise ValueError("ZIP entries differ from manifest file list")
    for name, entry in listed.items():
        if "/" in name or "\\" in name or name.startswith("."):
            raise ValueError(f"unsafe evidence name: {name}")
        digest = hashlib.sha256()
        size = 0
        with archive.open(name) as source:
            for chunk in iter(lambda: source.read(1024 * 1024), b""):
                size += len(chunk)
                digest.update(chunk)
        if size != entry["bytes"] or digest.hexdigest() != entry["sha256"]:
            raise ValueError(f"manifest size or SHA-256 mismatch: {name}")
    provenance = json.loads(archive.read("provenance.json"))
    if provenance.get("format") != manifest["format"]:
        raise ValueError("provenance format differs from manifest")
    return manifest, provenance


def import_capture(capture: Path, output: Path) -> dict[str, int]:
    """Create a new database atomically. Never modify the input ZIP or an existing DB."""
    if output.exists():
        raise FileExistsError(f"database already exists: {output}")
    output.parent.mkdir(parents=True, exist_ok=True)
    temporary = output.with_name(output.name + f".building-{os.getpid()}")
    if temporary.exists():
        raise FileExistsError(f"temporary database already exists: {temporary}")
    try:
        with zipfile.ZipFile(capture) as archive:
            manifest, provenance = verify_capture(archive)
            with closing(sqlite3.connect(temporary)) as db:
                db.executescript(SCHEMA.read_text(encoding="utf-8"))
                populate(db, archive, manifest, provenance)
                problems = db.execute("PRAGMA foreign_key_check").fetchall()
                if problems:
                    raise ValueError(f"database foreign-key problems: {problems[:3]}")
                db.commit()
                summary = {name: db.execute(f"SELECT COUNT(*) FROM {name}").fetchone()[0]
                           for name in ("items", "recipes", "item_components", "recipe_terms", "properties")}
        os.replace(temporary, output)
        return summary
    except BaseException:
        temporary.unlink(missing_ok=True)
        raise


def populate(db: sqlite3.Connection, archive: zipfile.ZipFile, manifest: dict, provenance: dict) -> None:
    db.execute(
        "INSERT INTO capture VALUES (1, ?, ?, ?, ?, ?, ?, ?)",
        (provenance["format"], provenance.get("generated_at_utc"),
         provenance.get("minecraft_version"), provenance.get("neoforge_version"),
         provenance.get("declared_pack_version"), provenance.get("scope"), compact(provenance)),
    )
    db.executemany("INSERT INTO capture_files VALUES (?, ?, ?)",
                   ((f["name"], f["bytes"], f["sha256"]) for f in manifest["files"]))

    db.executemany("INSERT INTO mods VALUES (?, ?, ?)",
                   ((r["id"], r["name"], r.get("version")) for r in rows(archive, "mods.jsonl")))
    mod_ids = {r[0] for r in db.execute("SELECT id FROM mods")}
    def mod_id(identifier: str) -> str | None:
        candidate = namespace(identifier)
        return candidate if candidate in mod_ids else None

    for block in rows(archive, "blocks.jsonl"):
        block_id = block["id"]
        db.execute("INSERT INTO blocks VALUES (?, ?, ?, ?, ?, ?, ?)",
                   (block_id, namespace(block_id), mod_id(block_id), block.get("item_id"),
                    block.get("description_id"), block.get("implementation_class"),
                    int(block.get("has_block_entity", False))))
        db.executemany("INSERT INTO block_properties VALUES (?, ?, ?)",
                       ((block_id, name, compact(values))
                        for name, values in block.get("state_properties", {}).items()))

    has_item_details = "item-details.jsonl" in archive.namelist()
    details = {r["id"]: r for r in rows(archive, "item-details.jsonl")}
    item_count = 0
    for item in rows(archive, "items.jsonl"):
        item_count += 1
        item_id = item["id"]
        detail = details.pop(item_id, None)
        if has_item_details and detail is None:
            raise ValueError(f"item detail missing for {item_id}")
        db.execute("INSERT INTO items VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                   (item_id, namespace(item_id), mod_id(item_id), item.get("display_name"),
                    item.get("description_id"), item.get("implementation_class"),
                    item.get("max_stack_size"), bool_integer(item.get("damageable")),
                    item.get("max_damage"), item.get("rarity"), item.get("block_id"),
                    "collected" if detail is not None else "unavailable_legacy_capture",
                    detail.get("component_status", "unavailable") if detail else "unavailable",
                    detail.get("block_entity_type_status", "unavailable") if detail else "unavailable"))
        if detail is None:
            db.executemany("INSERT INTO item_components VALUES (?, ?, ?, NULL, NULL)",
                           ((item_id, component_id, "unavailable_legacy_capture")
                            for component_id in item.get("default_component_ids", [])))
        else:
            db.executemany("INSERT INTO item_components VALUES (?, ?, ?, ?, ?)",
                           ((item_id, c["id"], c["status"], nullable_json(c.get("value")), c.get("error"))
                            for c in detail.get("default_components", [])))
            if item.get("block_id"):
                db.executemany("INSERT OR IGNORE INTO block_entity_types VALUES (?, ?)",
                               ((item["block_id"], type_id)
                                for type_id in detail.get("block_entity_type_ids", [])))
    if details:
        raise ValueError(f"item details have no matching item: {next(iter(details))}")
    if item_count != provenance.get("counts", {}).get("items", item_count):
        raise ValueError("item count differs from provenance")

    db.executemany("INSERT INTO item_tags VALUES (?, ?)",
                   ((r["tag"], r["member"]) for r in rows(archive, "item-tags.jsonl")))
    db.executemany("INSERT INTO block_tags VALUES (?, ?)",
                   ((r["tag"], r["member"]) for r in rows(archive, "block-tags.jsonl")))
    db.executemany("INSERT INTO registry_entries VALUES (?, ?, ?, ?, ?)",
                   ((r["registry_id"], r["entry_id"], r.get("namespace"),
                     r.get("implementation_class"), nullable_json(r.get("access_sources")))
                    for r in rows(archive, "registry-entries.jsonl")))
    db.executemany("INSERT INTO registry_tags VALUES (?, ?, ?)",
                   ((r["registry_id"], r["tag"], r["member"])
                    for r in rows(archive, "registry-tags.jsonl")))

    has_recipe_details = "recipe-details.jsonl" in archive.namelist()
    recipe_details = {r["id"]: r for r in rows(archive, "recipe-details.jsonl")}
    recipe_count = 0
    for header in rows(archive, "recipes.jsonl"):
        recipe_count += 1
        recipe_id = header["id"]
        detail = recipe_details.pop(recipe_id, None)
        if has_recipe_details and detail is None:
            raise ValueError(f"recipe detail missing for {recipe_id}")
        db.execute("INSERT INTO recipes VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                   (recipe_id, namespace(recipe_id), header.get("type"), header.get("serializer"),
                    header.get("implementation_class"), header.get("result_item_id"),
                    header.get("result_count"), detail.get("source_pack_id") if detail else None,
                    detail.get("source_resource_id") if detail else None,
                    detail.get("source_sha256") if detail else None,
                    "collected" if detail else "unavailable_legacy_capture",
                    detail.get("input_status", "unavailable") if detail else "unavailable",
                    detail.get("output_status", "unavailable") if detail else "partial_header_only",
                    detail.get("semantic_status", "unavailable") if detail else "unavailable",
                    nullable_json(detail)))
        if detail is None:
            if header.get("result_item_id"):
                insert_term(db, recipe_id, "output", None,
                            {"path": "header_result", "kind": "item", "id": header["result_item_id"],
                             "quantity": header.get("result_count"), "origin": "legacy_header"})
        else:
            for field, role in (("item_inputs", "input"), ("fluid_inputs", "input"),
                                ("item_outputs", "output"), ("fluid_outputs", "output"),
                                ("catalysts", "catalyst")):
                for term in detail.get(field, []):
                    insert_term(db, recipe_id, role, None, term)
            for step in detail.get("sequence", []):
                for field, role in (("item_inputs", "input"), ("fluid_inputs", "input"),
                                    ("item_outputs", "intermediate_output"),
                                    ("fluid_outputs", "intermediate_output")):
                    for term in step.get(field, []):
                        insert_term(db, recipe_id, role, step.get("index"), term)
    if recipe_details:
        raise ValueError(f"recipe details have no matching header: {next(iter(recipe_details))}")
    if recipe_count != provenance.get("counts", {}).get("recipes", recipe_count):
        raise ValueError("recipe count differs from provenance")

    for mechanic in rows(archive, "mechanics.jsonl"):
        entry_id = mechanic["entry_id"]
        kind = mechanic.get("entity_kind")
        if kind is None:
            kind = "block" if db.execute("SELECT 1 FROM blocks WHERE id=?", (entry_id,)).fetchone() else "item"
            if kind == "item" and not db.execute("SELECT 1 FROM items WHERE id=?", (entry_id,)).fetchone():
                kind = "registry_entry"
        if kind not in {"item", "block", "registry_entry"}:
            raise ValueError(f"invalid mechanic entity kind for {entry_id}: {kind}")
        if kind in {"item", "block"} and not db.execute(
                f"SELECT 1 FROM {'items' if kind == 'item' else 'blocks'} WHERE id=?", (entry_id,)).fetchone():
            raise ValueError(f"mechanic references missing {kind}: {entry_id}")
        if "status" in mechanic:
            status = mechanic["status"]
            value = mechanic.get("value")
            key = mechanic["property_key"]
        else:
            registered = mechanic.get("registered_value")
            status = "captured_directly" if registered is not False and mechanic.get("value_number") is not None else "unavailable"
            value = mechanic.get("value_number") if status == "captured_directly" else None
            key = f"{mechanic.get('subsystem', 'unknown')}.{mechanic['fact_key']}"
        if status not in PROPERTY_STATUSES:
            raise ValueError(f"invalid mechanic status for {entry_id}: {status}")
        if status not in {"captured_directly", "derived"}:
            value = None
        elif value is None or not isinstance(value, (str, int, float, bool)):
            raise ValueError(f"captured mechanic has no scalar value: {entry_id} {key}")
        db.execute("INSERT INTO properties (entity_kind, entity_id, property_key, status, value_json, unit, conditions_json, source, source_record_json) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                   (kind, entry_id, key,
                    status, nullable_json(value), mechanic.get("unit"), nullable_json(mechanic.get("conditions")),
                    mechanic.get("source_api"), compact(mechanic)))
    db.executemany("INSERT INTO config_values (mod_id, config_scope, config_path, field_name, effective_value_json, unit_hint, evidence_status, source_api) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                   ((r.get("mod_id"), r.get("config_scope"), r.get("config_path"),
                     r.get("field_name"), nullable_json(r.get("effective_value")),
                     r.get("unit_hint"), r.get("evidence_status"), r.get("source_api"))
                    for r in rows(archive, "config-values.jsonl")))
    db.executemany("INSERT INTO unloaded_recipe_resources VALUES (?, ?, ?, ?, ?)",
                   ((r["id"], r.get("source_pack_id"), r.get("source_sha256"),
                     r.get("reason_status"), nullable_json(r.get("source_json")))
                    for r in rows(archive, "unloaded-recipe-resources.jsonl")))


def bool_integer(value: object) -> int | None:
    return None if value is None else int(bool(value))


def insert_term(db: sqlite3.Connection, recipe_id: str, role: str,
                step: int | None, term: dict) -> None:
    db.execute("INSERT INTO recipe_terms (recipe_id, role, sequence_step, path, kind, target_id, quantity, chance, definition_json, origin) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
               (recipe_id, role, step, term.get("path"), term["kind"], term.get("id"),
                term.get("quantity"), term.get("chance"), nullable_json(term.get("definition")),
                term.get("origin")))


def item_report(db: sqlite3.Connection, item_id: str) -> dict:
    db.row_factory = sqlite3.Row
    item = db.execute("SELECT items.*, mods.name AS mod_name, mods.version AS mod_version "
                      "FROM items LEFT JOIN mods ON mods.id=items.mod_id WHERE items.id=?", (item_id,)).fetchone()
    if item is None:
        raise ValueError(f"item not found: {item_id}")
    result = dict(item)
    result["components"] = [dict(r) for r in db.execute(
        "SELECT component_id, status, value_json FROM item_components WHERE item_id=? ORDER BY component_id", (item_id,))]
    result["item_tags"] = [r[0] for r in db.execute(
        "SELECT tag FROM item_tags WHERE item_id=? ORDER BY tag", (item_id,))]
    result["block_tags"] = [r[0] for r in db.execute(
        "SELECT tag FROM block_tags WHERE block_id=? ORDER BY tag", (item["block_id"],))]
    result["block_entity_types"] = [r[0] for r in db.execute(
        "SELECT type_id FROM block_entity_types WHERE block_id=? ORDER BY type_id", (item["block_id"],))]
    result["properties"] = [dict(r) for r in db.execute(
        "SELECT entity_kind, property_key, status, value_json, unit, conditions_json, source, source_record_json "
        "FROM properties "
        "WHERE (entity_kind='item' AND entity_id=?) OR (entity_kind='block' AND entity_id=?) "
        "ORDER BY property_key", (item_id, item["block_id"]))]
    result["makes"] = [r[0] for r in db.execute(
        "SELECT DISTINCT recipe_id FROM recipe_terms WHERE role='output' AND kind='item' "
        "AND target_id=? ORDER BY recipe_id", (item_id,))]
    result["uses"] = [r[0] for r in db.execute(
        "SELECT DISTINCT t.recipe_id FROM recipe_terms t "
        "LEFT JOIN item_tags tags ON t.kind='item_tag' AND t.target_id=tags.tag "
        "WHERE t.role IN ('input','catalyst') AND "
        "((t.kind='item' AND t.target_id=?) OR tags.item_id=?) ORDER BY t.recipe_id", (item_id, item_id))]
    return result


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    importer = commands.add_parser("import", help="Create a new SQLite database from a capture ZIP")
    importer.add_argument("capture", type=Path)
    importer.add_argument("--output", required=True, type=Path)
    item = commands.add_parser("item", help="Show an item's known facts and recipe IDs")
    item.add_argument("database", type=Path)
    item.add_argument("item_id")
    args = parser.parse_args(argv)
    try:
        if args.command == "import":
            print(json.dumps(import_capture(args.capture, args.output), indent=2))
        else:
            if not args.database.is_file():
                raise FileNotFoundError(f"database does not exist: {args.database}")
            with closing(sqlite3.connect(args.database)) as db:
                print(json.dumps(item_report(db, args.item_id), indent=2, ensure_ascii=False))
        return 0
    except (OSError, ValueError, KeyError, sqlite3.Error, zipfile.BadZipFile) as exc:
        print(f"Game data database error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
