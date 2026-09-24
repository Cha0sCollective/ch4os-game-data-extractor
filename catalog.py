"""Read-only queries for the local game-data browser."""

from __future__ import annotations

from contextlib import contextmanager
import json
from pathlib import Path
import sqlite3

from game_data_db import item_report


def _like(value: str) -> str:
    return "%" + value.lower().replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_") + "%"


class Catalog:
    def __init__(self, path: Path):
        self.path = path.resolve()
        if not self.path.is_file():
            raise FileNotFoundError(self.path)
        with self.connect() as db:
            if not db.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='capture'").fetchone():
                raise ValueError(f"not a Ch4oS database: {self.path}")

    @contextmanager
    def connect(self):
        db = sqlite3.connect(self.path.as_uri() + "?mode=ro", uri=True)
        db.row_factory = sqlite3.Row
        try:
            yield db
        finally:
            db.close()

    def overview(self) -> dict:
        with self.connect() as db:
            capture = dict(db.execute("SELECT * FROM capture WHERE id=1").fetchone())
            capture.pop("provenance_json")
            capture["counts"] = {name: db.execute(f"SELECT COUNT(*) FROM {name}").fetchone()[0]
                                 for name in ("mods", "items", "recipes", "blocks", "properties")}
            return capture

    def filters(self) -> dict:
        with self.connect() as db:
            mods = [dict(row) for row in db.execute(
                "SELECT mods.id, mods.name, mods.version, COUNT(items.id) AS item_count FROM mods "
                "LEFT JOIN items ON items.mod_id=mods.id GROUP BY mods.id ORDER BY lower(mods.name)")]
            recipe_namespaces = {row["namespace"]: row["recipe_count"] for row in db.execute(
                "SELECT namespace, COUNT(*) AS recipe_count FROM recipes GROUP BY namespace")}
            known = {mod["id"] for mod in mods}
            for mod in mods:
                mod["recipe_count"] = recipe_namespaces.get(mod["id"], 0)
            mods.extend({"id": namespace, "name": namespace + " (namespace)",
                         "item_count": 0, "recipe_count": amount}
                        for namespace, amount in recipe_namespaces.items() if namespace not in known)
            mods.sort(key=lambda mod: mod["name"].lower())
            types = [dict(row) for row in db.execute(
                "SELECT type, COUNT(*) AS recipe_count FROM recipes GROUP BY type ORDER BY type")]
            return {"mods": mods, "recipe_types": types}

    def mods(self, q: str = "", include_empty: bool = False, limit: int = 50, offset: int = 0) -> dict:
        source = (" FROM mods "
                  "LEFT JOIN (SELECT mod_id, COUNT(*) AS amount FROM items GROUP BY mod_id) item_counts "
                  "ON item_counts.mod_id=mods.id "
                  "LEFT JOIN (SELECT namespace, COUNT(*) AS amount FROM recipes GROUP BY namespace) recipe_counts "
                  "ON recipe_counts.namespace=mods.id")
        clauses, params = [], []
        if not include_empty:
            clauses.append("COALESCE(item_counts.amount, 0)>0")
        if q:
            clauses.append("(lower(mods.id) LIKE ? ESCAPE '\\' OR lower(mods.name) LIKE ? ESCAPE '\\')")
            params.extend((_like(q), _like(q)))
        where = " WHERE " + " AND ".join(clauses) if clauses else ""
        with self.connect() as db:
            total = db.execute("SELECT COUNT(*)" + source + where, params).fetchone()[0]
            rows = [dict(row) for row in db.execute(
                "SELECT mods.id, mods.name, mods.version, "
                "COALESCE(item_counts.amount, 0) AS item_count, "
                "COALESCE(recipe_counts.amount, 0) AS recipe_count "
                + source + where +
                " ORDER BY lower(mods.name), mods.id LIMIT ? OFFSET ?",
                [*params, max(1, min(limit, 100)), max(0, offset)])]
        return {"total": total, "mods": rows}

    def _item_where(self, q: str, mod: str, coverage: str) -> tuple[str, list]:
        clauses, params = [], []
        if q:
            clauses.append("(lower(items.id) LIKE ? ESCAPE '\\' OR lower(items.display_name) LIKE ? ESCAPE '\\')")
            params.extend((_like(q), _like(q)))
        if mod:
            clauses.append("items.mod_id=?")
            params.append(mod)
        if coverage == "incomplete":
            clauses.append("(items.detail_status!='collected' OR items.component_status!='collected' "
                           "OR items.block_entity_type_status='unavailable')")
        return (" WHERE " + " AND ".join(clauses)) if clauses else "", params

    def items(self, q: str = "", mod: str = "", coverage: str = "all",
              limit: int = 50, offset: int = 0) -> dict:
        where, params = self._item_where(q, mod, coverage)
        with self.connect() as db:
            total = db.execute("SELECT COUNT(*) FROM items" + where, params).fetchone()[0]
            rows = [dict(row) for row in db.execute(
                "SELECT items.id, items.display_name, items.mod_id, items.max_stack_size, "
                "items.rarity, items.block_id, items.detail_status, items.component_status, "
                "items.block_entity_type_status, mods.name AS mod_name "
                "FROM items LEFT JOIN mods ON mods.id=items.mod_id" + where +
                " ORDER BY lower(items.display_name), items.id LIMIT ? OFFSET ?",
                [*params, max(1, min(limit, 100)), max(0, offset)])]
        return {"total": total, "items": rows}

    def item(self, item_id: str) -> dict:
        with self.connect() as db:
            result = item_report(db, item_id)
            block_id = result.get("block_id")
            if block_id:
                block = db.execute("SELECT * FROM blocks WHERE id=?", (block_id,)).fetchone()
                result["block"] = dict(block) if block else None
                result["block_state_properties"] = [dict(row) for row in db.execute(
                    "SELECT name, allowed_values_json FROM block_properties WHERE block_id=? ORDER BY name", (block_id,))]
            else:
                result["block"] = None
                result["block_state_properties"] = []
            for component in result["components"]:
                value = component.pop("value_json")
                component["value"] = json.loads(value) if value is not None else None
            for prop in result["properties"]:
                value = prop.pop("value_json")
                prop["value"] = json.loads(value) if value is not None else None
            for block_property in result["block_state_properties"]:
                block_property["allowed_values"] = json.loads(block_property.pop("allowed_values_json"))
            return result

    def _recipe_where(self, q: str, recipe_type: str, mod: str, coverage: str) -> tuple[str, list]:
        clauses, params = [], []
        if q:
            clauses.append("(lower(recipes.id) LIKE ? ESCAPE '\\' OR lower(recipes.result_item_id) LIKE ? ESCAPE '\\')")
            params.extend((_like(q), _like(q)))
        if recipe_type:
            clauses.append("recipes.type=?")
            params.append(recipe_type)
        if mod:
            clauses.append("recipes.namespace=?")
            params.append(mod)
        if coverage == "incomplete":
            clauses.append("(recipes.detail_status!='collected' OR recipes.input_status!='collected' "
                           "OR recipes.output_status!='collected' OR recipes.semantic_status!='core_fields')")
        return (" WHERE " + " AND ".join(clauses)) if clauses else "", params

    def recipes(self, q: str = "", recipe_type: str = "", mod: str = "", coverage: str = "all",
                limit: int = 50, offset: int = 0) -> dict:
        where, params = self._recipe_where(q, recipe_type, mod, coverage)
        with self.connect() as db:
            total = db.execute("SELECT COUNT(*) FROM recipes" + where, params).fetchone()[0]
            rows = [dict(row) for row in db.execute(
                "SELECT id, type, serializer, namespace, result_item_id, result_count, source_pack_id, "
                "detail_status, input_status, output_status, semantic_status "
                "FROM recipes" + where + " ORDER BY id LIMIT ? OFFSET ?",
                [*params, max(1, min(limit, 100)), max(0, offset)])]
        return {"total": total, "recipes": rows}

    def recipe(self, recipe_id: str) -> dict:
        with self.connect() as db:
            row = db.execute("SELECT * FROM recipes WHERE id=?", (recipe_id,)).fetchone()
            if row is None:
                raise ValueError(f"recipe not found: {recipe_id}")
            result = dict(row)
            result["detail"] = json.loads(result.pop("detail_json")) if result["detail_json"] else None
            result["terms"] = [dict(term) for term in db.execute(
                "SELECT role, sequence_step, path, kind, target_id, quantity, chance, definition_json, origin "
                "FROM recipe_terms WHERE recipe_id=? ORDER BY id", (recipe_id,))]
            for term in result["terms"]:
                term["definition"] = json.loads(term.pop("definition_json")) if term["definition_json"] else None
            return result

    def coverage(self) -> dict:
        with self.connect() as db:
            def grouped(query: str) -> list[dict]:
                return [dict(row) for row in db.execute(query)]
            return {
                "item_details": grouped("SELECT detail_status AS status, COUNT(*) AS count FROM items GROUP BY detail_status"),
                "item_components": grouped("SELECT status, COUNT(*) AS count FROM item_components GROUP BY status"),
                "block_entity_types": grouped("SELECT block_entity_type_status AS status, COUNT(*) AS count "
                                              "FROM items GROUP BY block_entity_type_status"),
                "recipe_inputs": grouped("SELECT input_status AS status, COUNT(*) AS count FROM recipes GROUP BY input_status"),
                "recipe_outputs": grouped("SELECT output_status AS status, COUNT(*) AS count FROM recipes GROUP BY output_status"),
                "recipe_semantics": grouped("SELECT semantic_status AS status, COUNT(*) AS count FROM recipes GROUP BY semantic_status"),
                "properties": grouped("SELECT status, COUNT(*) AS count FROM properties GROUP BY status"),
                "incomplete_recipe_types": grouped("SELECT COALESCE(type, '<unknown>') AS type, COUNT(*) AS count "
                                                   "FROM recipes WHERE input_status!='collected' OR "
                                                   "output_status!='collected' OR semantic_status!='core_fields' "
                                                   "GROUP BY type ORDER BY count DESC LIMIT 30"),
            }

    def export(self, kind: str, fmt: str, q: str = "", mod: str = "", recipe_type: str = "",
               coverage: str = "all") -> tuple[str, bytes]:
        import csv
        from io import StringIO
        if kind == "items":
            where, params = self._item_where(q, mod, coverage)
            query = ("SELECT items.id, items.display_name, items.mod_id, mods.version AS mod_version, "
                     "items.max_stack_size, items.max_damage, items.rarity, items.block_id, "
                     "items.detail_status, items.component_status FROM items "
                     "LEFT JOIN mods ON mods.id=items.mod_id" + where + " ORDER BY items.id")
        elif kind == "recipes":
            where, params = self._recipe_where(q, recipe_type, mod, coverage)
            query = ("SELECT recipes.id, recipes.type, recipes.serializer, recipes.namespace, "
                     "recipes.result_item_id, recipes.result_count, recipes.source_pack_id, "
                     "recipes.input_status, recipes.output_status, recipes.semantic_status "
                     "FROM recipes" + where + " ORDER BY recipes.id")
        else:
            raise ValueError("export kind must be items or recipes")
        with self.connect() as db:
            rows = [dict(row) for row in db.execute(query, params)]
        if fmt == "json":
            return "application/json", json.dumps(rows, ensure_ascii=False, indent=2).encode("utf-8")
        if fmt == "csv":
            output = StringIO(newline="")
            writer = csv.DictWriter(output, fieldnames=list(rows[0]) if rows else [])
            if rows:
                writer.writeheader()
                writer.writerows(rows)
            return "text/csv; charset=utf-8", output.getvalue().encode("utf-8-sig")
        raise ValueError("export format must be json or csv")
