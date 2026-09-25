"""Validate a GDE-backed guide's citations against one captured snapshot.

Every cited finding must be accepted, present as a reviewed claim, formula, or
relationship, and backed by evidence matching an installed artifact or runtime
capture. Optional reference recording updates only this guide's reference set.
"""

from __future__ import annotations

import argparse
import hashlib
from pathlib import Path
import re
import sqlite3
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from knowledge_store import capture_identity


REFERENCE = re.compile(r"powergrid:(?:stage33_revalidated|stage33|source_followup|source_completion):[a-z0-9_]+")
TABLES = {"claim": "claims", "relation": "relations", "formula": "formulas"}


def validate(capture: Path, knowledge: Path, guide: Path, record_refs: bool = False) -> dict:
    snapshot, _, _ = capture_identity(capture)
    text = guide.read_text(encoding="utf-8")
    ids = sorted(set(REFERENCE.findall(text)))
    if not ids:
        raise ValueError("guide has no reviewed GDE references")
    with sqlite3.connect(knowledge) as db:
        db.execute("PRAGMA foreign_keys=ON")
        artifact_hashes = {row[0] for row in db.execute(
            "SELECT artifact_sha256 FROM snapshot_artifacts WHERE snapshot_id=? AND mod_id='powergrid'",
            (snapshot,))}
        if not artifact_hashes:
            raise ValueError("Power Grid artifact is absent from this snapshot")
        refs: list[tuple[str, str]] = []
        for identifier in ids:
            finding = db.execute("SELECT status FROM findings WHERE snapshot_id=? AND id=?",
                                 (snapshot, identifier)).fetchone()
            if finding != ("accepted",):
                raise ValueError(f"reference is not accepted in this snapshot: {identifier}")
            matches = []
            for kind, table in TABLES.items():
                row = db.execute(f"SELECT evidence_id FROM {table} WHERE snapshot_id=? AND id=?",
                                 (snapshot, identifier)).fetchone()
                if row:
                    matches.append((kind, row[0]))
            if len(matches) != 1:
                raise ValueError(f"reference does not resolve to exactly one reviewed record: {identifier}")
            kind, evidence_id = matches[0]
            evidence = db.execute("SELECT kind,locator,artifact_sha256,source_revision "
                                  "FROM evidence WHERE snapshot_id=? AND id=?",
                                  (snapshot, evidence_id)).fetchone()
            if not evidence or not evidence[1]:
                raise ValueError(f"missing accepted evidence: {identifier}")
            evidence_kind, _, artifact_hash, revision = evidence
            if evidence_kind == "installed_artifact" and artifact_hash not in artifact_hashes:
                raise ValueError(f"evidence artifact differs from installed pack: {identifier}")
            if evidence_kind == "exact_source" and not (revision or artifact_hash in artifact_hashes):
                raise ValueError(f"source revision is not tied to this pack: {identifier}")
            if evidence_kind not in {"installed_artifact", "installed_runtime", "exact_source", "test"}:
                raise ValueError(f"unknown evidence kind: {identifier}")
            refs.append((kind, identifier))
        if record_refs:
            guide_id = guide.stem
            with db:
                db.execute("DELETE FROM guide_refs WHERE snapshot_id=? AND guide_id=?",
                           (snapshot, guide_id))
                db.executemany("INSERT INTO guide_refs(snapshot_id,guide_id,record_kind,record_id) "
                               "VALUES(?,?,?,?)",
                               [(snapshot, guide_id, kind, identifier) for kind, identifier in refs])
    return {"snapshot_id": snapshot, "references": len(refs),
            "sha256": hashlib.sha256(guide.read_bytes()).hexdigest(), "guide": str(guide)}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--capture", type=Path, required=True)
    parser.add_argument("--knowledge", type=Path, required=True)
    parser.add_argument("--guide", type=Path, required=True)
    parser.add_argument("--record-refs", action="store_true")
    args = parser.parse_args()
    print(validate(args.capture, args.knowledge, args.guide, args.record_refs))


if __name__ == "__main__":
    main()
