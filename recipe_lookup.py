"""Find recipes that make or use an item in a Ch4oS capture ZIP."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys
import zipfile


def lookup(archive: zipfile.ZipFile, item_id: str) -> dict[str, list[dict]]:
    tags: set[str] = set()
    with archive.open("item-tags.jsonl") as stream:
        for line in stream:
            row = json.loads(line)
            if row["member"] == item_id:
                tags.add(row["tag"])

    matches: dict[str, list[dict]] = {"makes": [], "uses": []}
    with archive.open("recipe-details.jsonl") as stream:
        for line in stream:
            recipe = json.loads(line)
            output_matches = [entry for entry in recipe["item_outputs"]
                              if entry["kind"] == "item" and entry["id"] == item_id]
            if output_matches:
                matches["makes"].append({
                    "id": recipe["id"],
                    "type": recipe["type"],
                    "source_pack_id": recipe.get("source_pack_id"),
                    "matches": output_matches,
                    "output_status": recipe["output_status"],
                })

            inputs = list(recipe["item_inputs"])
            for step in recipe.get("sequence", []):
                inputs.extend(step.get("item_inputs", []))
            input_matches = [entry for entry in inputs if (
                (entry["kind"] == "item" and entry["id"] == item_id)
                or (entry["kind"] == "item_tag" and entry["id"] in tags)
            )]
            if input_matches:
                matches["uses"].append({
                    "id": recipe["id"],
                    "type": recipe["type"],
                    "source_pack_id": recipe.get("source_pack_id"),
                    "matches": input_matches,
                    "input_status": recipe["input_status"],
                })
    return matches


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("capture", type=Path, help="Capture ZIP from ch4os_capture.py")
    parser.add_argument("item_id", help="Item registry ID, for example create:brass_ingot")
    parser.add_argument("--direction", choices=("both", "makes", "uses"), default="both")
    parser.add_argument("--limit", type=int, default=30, help="Printed rows per direction")
    parser.add_argument("--json", action="store_true", help="Print all matches as JSON")
    args = parser.parse_args(argv)
    if args.limit < 1:
        parser.error("--limit must be positive")
    try:
        with zipfile.ZipFile(args.capture) as archive:
            matches = lookup(archive, args.item_id)
    except (OSError, zipfile.BadZipFile, KeyError, ValueError) as exc:
        print(f"Could not read recipe details: {exc}", file=sys.stderr)
        return 1
    if args.direction != "both":
        matches = {args.direction: matches[args.direction]}
    if args.json:
        print(json.dumps({"item_id": args.item_id, **matches}, indent=2))
    else:
        for direction, rows in matches.items():
            print(f"{direction.capitalize()} {args.item_id}: {len(rows)} recipe(s)")
            for row in rows[:args.limit]:
                via = ", ".join(f"{match['kind']} {match['id']}" for match in row["matches"])
                print(f"  {row['id']} [{row['type']}] via {via}")
            if len(rows) > args.limit:
                print(f"  ... {len(rows) - args.limit} more (use --json or a larger --limit)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
