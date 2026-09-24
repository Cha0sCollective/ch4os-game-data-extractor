"""Conservative conflict analysis and effective-recipe snapshot comparison.

Only vanilla recipe contexts with known matching rules receive definite
input-collision findings. Other recipe types remain visible as inconclusive.
"""

from __future__ import annotations

import argparse
from collections import Counter, defaultdict
from contextlib import closing
import hashlib
from itertools import combinations
import json
from pathlib import Path
import sqlite3
from tempfile import TemporaryDirectory

from game_data_db import import_capture


COOKING = {"minecraft:smelting", "minecraft:blasting", "minecraft:smoking",
           "minecraft:campfire_cooking"}
SUPPORTED = COOKING | {"minecraft:crafting", "minecraft:stonecutting"}


def canonical(value: object) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def digest(value: object) -> str:
    return hashlib.sha256(canonical(value).encode("utf-8")).hexdigest()[:16]


def _source(detail: dict) -> dict | None:
    source = detail.get("source_json") or detail.get("codec_json")
    return source if isinstance(source, dict) else None


def _minecraft_id(identifier: str) -> str:
    return identifier if ":" in identifier else "minecraft:" + identifier


def _matching_key(recipe: dict) -> tuple[str, str] | None:
    """Return an exact definition key, never an inferred tag-overlap match."""
    detail = recipe["detail"]
    kind = recipe["type"]
    if not detail or kind not in SUPPORTED or detail.get("input_status") != "collected" \
            or detail.get("output_status") != "collected" \
            or detail.get("semantic_status") != "core_fields" or detail.get("dynamic_result"):
        return None
    source = _source(detail)
    if source is None:
        return None
    serializer = recipe["serializer"]
    if kind == "minecraft:crafting":
        if serializer == "minecraft:crafting_shaped":
            pattern, key = source.get("pattern"), source.get("key")
            if not isinstance(pattern, list) or not pattern or not isinstance(key, dict):
                return None
            if not all(isinstance(row, str) and len(row) == len(pattern[0]) for row in pattern):
                return None
            if any(symbol != " " and symbol not in key for row in pattern for symbol in row):
                return None
            grid = [[None if symbol == " " else key[symbol] for symbol in row] for row in pattern]
            mirrored = [list(reversed(row)) for row in grid]
            return kind, canonical(["shaped", min(canonical(grid), canonical(mirrored))])
        if serializer == "minecraft:crafting_shapeless":
            ingredients = source.get("ingredients")
            if not isinstance(ingredients, list) or not ingredients:
                return None
            return kind, canonical(["shapeless", sorted(canonical(term) for term in ingredients)])
        return None
    if serializer != kind:
        return None
    ingredient = source.get("ingredient")
    if ingredient is None:
        return None
    return kind, canonical(ingredient)


def _recipe_parts(recipe: dict) -> dict:
    detail = recipe["detail"] or {}
    return {
        "context": {"type": recipe["type"], "serializer": recipe["serializer"]},
        "inputs": {key: detail.get(key) for key in ("item_inputs", "fluid_inputs", "catalysts", "sequence", "layout")},
        "input_tags": sorted((term.get("kind"), term.get("id")) for key in ("item_inputs", "fluid_inputs")
                             for term in detail.get(key, []) if term.get("kind", "").endswith("_tag")),
        "outputs": {"item_outputs": detail.get("item_outputs"), "fluid_outputs": detail.get("fluid_outputs"),
                    "result_item_id": recipe["result_item_id"], "result_count": recipe["result_count"]},
        "process": {key: detail.get(key) for key in ("processing_parameters", "runtime_processing", "conditions",
                                                    "remaining_items_status", "dynamic_result")},
        "source_definition": _source(detail),
        "coverage": {key: recipe[key] for key in ("detail_status", "input_status", "output_status", "semantic_status")},
        "source_pack": recipe["source_pack_id"],
    }


def _read(path: Path) -> dict:
    uri = path.resolve().as_uri() + "?mode=ro"
    with closing(sqlite3.connect(uri, uri=True)) as db:
        capture = db.execute("SELECT generated_at_utc, minecraft_version, neoforge_version, "
                             "declared_pack_version, scope FROM capture WHERE id=1").fetchone()
        if capture is None:
            raise ValueError(f"not a Ch4oS database: {path}")
        names = {row[0] for row in db.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        required = {"recipes", "items", "item_tags"}
        if not required <= names:
            raise ValueError(f"not a Ch4oS database: {path}")
        recipes = {}
        columns = ("id", "type", "serializer", "result_item_id", "result_count", "source_pack_id",
                   "detail_status", "input_status", "output_status", "semantic_status", "detail_json")
        for row in db.execute(f"SELECT {', '.join(columns)} FROM recipes"):
            recipe = dict(zip(columns, row))
            recipe["detail"] = json.loads(recipe.pop("detail_json")) if recipe["detail_json"] else None
            recipes[recipe["id"]] = recipe
        overrides = []
        if "recipe_overrides" in names:
            overrides = [{"id": recipe_id, "effective_loaded": bool(loaded),
                          "effective_recipe_source_pack_id": recipes.get(recipe_id, {}).get("source_pack_id"),
                          "layers": json.loads(layers)}
                         for recipe_id, loaded, layers in db.execute(
                             "SELECT id, effective_loaded, layers_json FROM recipe_overrides ORDER BY id")]
        return {"capture": dict(zip(("generated_at_utc", "minecraft_version", "neoforge_version",
                                     "declared_pack_version", "scope"), capture)),
                "recipes": recipes,
                "items": {row[0] for row in db.execute("SELECT id FROM items")},
                "item_tags": {row[0] for row in db.execute("SELECT DISTINCT tag FROM item_tags")},
                "fluids": {row[0] for row in db.execute(
                    "SELECT entry_id FROM registry_entries WHERE registry_id='minecraft:fluid'")},
                "fluid_tags": {row[0] for row in db.execute(
                    "SELECT DISTINCT tag FROM registry_tags WHERE registry_id='minecraft:fluid'")},
                "overrides": overrides,
                "override_evidence": "recipe_overrides" in names and db.execute(
                    "SELECT 1 FROM capture_files WHERE name='recipe-overrides.jsonl'").fetchone() is not None}


def analyze_database(path: Path) -> dict:
    snapshot = _read(path)
    recipes = snapshot["recipes"]
    groups = defaultdict(list)
    inconclusive = Counter()
    missing = []
    for recipe in recipes.values():
        key = _matching_key(recipe)
        if key is None:
            inconclusive[recipe["type"] or "<unknown>"] += 1
        else:
            groups[key].append(recipe)
        detail = recipe["detail"] or {}
        if recipe["input_status"] != "collected":
            continue
        for field in ("item_inputs", "fluid_inputs", "catalysts"):
            for term in detail.get(field, []):
                kind, target = term.get("kind"), term.get("id")
                if kind == "item" and target and _minecraft_id(target) not in snapshot["items"]:
                    missing.append({"recipe_id": recipe["id"], "kind": "missing_item", "target": _minecraft_id(target),
                                    "path": term.get("path")})
                elif kind == "item_tag" and target and _minecraft_id(target) not in snapshot["item_tags"]:
                    missing.append({"recipe_id": recipe["id"], "kind": "empty_or_missing_item_tag",
                                    "target": _minecraft_id(target), "path": term.get("path")})
                elif kind == "fluid" and target and snapshot["fluids"] and _minecraft_id(target) not in snapshot["fluids"]:
                    missing.append({"recipe_id": recipe["id"], "kind": "missing_fluid",
                                    "target": _minecraft_id(target), "path": term.get("path")})
                elif kind == "fluid_tag" and target and snapshot["fluids"] and _minecraft_id(target) not in snapshot["fluid_tags"]:
                    missing.append({"recipe_id": recipe["id"], "kind": "empty_or_missing_fluid_tag",
                                    "target": _minecraft_id(target), "path": term.get("path")})
    findings = []
    for (context, key), members in groups.items():
        if len(members) < 2:
            continue
        signatures = {}
        for member in members:
            parts = _recipe_parts(member)
            signatures[member["id"]] = canonical({"outputs": parts["outputs"], "process": parts["process"]})
        for left, right in combinations(sorted(member["id"] for member in members), 2):
            same_result = signatures[left] == signatures[right]
            if context == "minecraft:stonecutting" and not same_result:
                # Stonecutter recipes present several choices for one input by design.
                continue
            kind = "equivalent_recipes" if same_result else "competing_inputs"
            findings.append({"id": digest([context, key, left, right]), "kind": kind,
                             "context": context, "recipes": [left, right],
                             "evidence": "exact input definitions within a supported recipe context"})
    return {"capture": snapshot["capture"],
            "counts": {"recipes": len(recipes), "analyzable": sum(len(group) for group in groups.values()),
                       "inconclusive": sum(inconclusive.values()), "findings": len(findings),
                       "missing_ingredients": len(missing), "overrides": len(snapshot["overrides"])},
            "findings": sorted(findings, key=lambda item: (item["kind"], item["context"], item["id"])),
            "missing_ingredients": sorted(missing, key=lambda item: (item["recipe_id"], item["kind"], item["target"])),
            "inconclusive_types": [{"type": key, "count": value} for key, value in inconclusive.most_common()],
            "overrides": snapshot["overrides"],
            "override_evidence": "captured" if snapshot["override_evidence"] else "unavailable_in_capture"}


def compare_databases(baseline: Path, current: Path) -> dict:
    old, new = _read(baseline), _read(current)
    old_ids, new_ids = set(old["recipes"]), set(new["recipes"])
    changed = []
    for recipe_id in sorted(old_ids & new_ids):
        before, after = _recipe_parts(old["recipes"][recipe_id]), _recipe_parts(new["recipes"][recipe_id])
        fields = [field for field in before if canonical(before[field]) != canonical(after[field])]
        if fields:
            changed.append({"id": recipe_id, "fields": fields,
                            "before": {field: before[field] for field in fields},
                            "after": {field: after[field] for field in fields}})
    old_analysis, new_analysis = analyze_database(baseline), analyze_database(current)
    prior = {finding["id"]: finding for finding in old_analysis["findings"]}
    now = {finding["id"]: finding for finding in new_analysis["findings"]}
    return {"baseline": old["capture"], "current": new["capture"],
            "counts": {"added": len(new_ids - old_ids), "removed": len(old_ids - new_ids),
                       "changed": len(changed), "new_conflicts": len(now.keys() - prior.keys()),
                       "resolved_conflicts": len(prior.keys() - now.keys())},
            "added_recipes": sorted(new_ids - old_ids), "removed_recipes": sorted(old_ids - new_ids),
            "changed_recipes": changed,
            "new_conflicts": [now[key] for key in sorted(now.keys() - prior.keys())],
            "resolved_conflicts": [prior[key] for key in sorted(prior.keys() - now.keys())],
            "baseline_coverage": old_analysis["counts"], "current_coverage": new_analysis["counts"]}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    analyze = sub.add_parser("analyze", help="Analyze one SQLite database or capture ZIP")
    analyze.add_argument("snapshot", type=Path)
    compare = sub.add_parser("compare", help="Compare baseline and current effective recipes")
    compare.add_argument("baseline", type=Path)
    compare.add_argument("current", type=Path)
    for command in (analyze, compare):
        command.add_argument("--output", type=Path, help="Write the JSON report to a new file")
    args = parser.parse_args(argv)
    with TemporaryDirectory(prefix="ch4os-analysis-") as folder:
        def database(source: Path, label: str) -> Path:
            if source.suffix.lower() != ".zip":
                return source
            destination = Path(folder) / f"{label}.sqlite"
            import_capture(source, destination)
            return destination
        if args.command == "analyze":
            report = analyze_database(database(args.snapshot, "snapshot"))
        else:
            report = compare_databases(database(args.baseline, "baseline"), database(args.current, "current"))
    rendered = json.dumps(report, ensure_ascii=False, indent=2) + "\n"
    if args.output:
        with args.output.open("x", encoding="utf-8") as target:
            target.write(rendered)
        print(f"Wrote {args.output}")
    else:
        print(rendered, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
