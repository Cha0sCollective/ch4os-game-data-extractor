"""Persistent, snapshot-scoped reviewed knowledge for GDE captures.

Capture databases remain disposable projections of their ZIPs. This database is
kept separately so importing a newer pack cannot overwrite reviewed research.
"""

from __future__ import annotations

from contextlib import closing, contextmanager
import hashlib
import json
from pathlib import Path
import sqlite3


SCHEMA = """
PRAGMA foreign_keys = ON;
CREATE TABLE IF NOT EXISTS snapshots (
    id TEXT PRIMARY KEY,
    provenance_json TEXT NOT NULL,
    captured_at_utc TEXT,
    minecraft_version TEXT,
    neoforge_version TEXT
);
CREATE TABLE IF NOT EXISTS snapshot_mods (
    snapshot_id TEXT NOT NULL REFERENCES snapshots(id),
    mod_id TEXT NOT NULL,
    version TEXT,
    PRIMARY KEY (snapshot_id, mod_id)
);
CREATE TABLE IF NOT EXISTS snapshot_artifacts (
    snapshot_id TEXT NOT NULL REFERENCES snapshots(id),
    mod_id TEXT NOT NULL,
    artifact_sha256 TEXT NOT NULL,
    file_name TEXT NOT NULL,
    PRIMARY KEY (snapshot_id, mod_id, artifact_sha256)
);
CREATE TABLE IF NOT EXISTS evidence (
    snapshot_id TEXT NOT NULL REFERENCES snapshots(id),
    id TEXT NOT NULL,
    kind TEXT NOT NULL CHECK (kind IN ('installed_runtime', 'installed_artifact', 'exact_source', 'test')),
    locator TEXT NOT NULL,
    artifact_sha256 TEXT,
    source_revision TEXT,
    notes TEXT,
    PRIMARY KEY (snapshot_id, id)
);
CREATE TABLE IF NOT EXISTS claims (
    snapshot_id TEXT NOT NULL REFERENCES snapshots(id),
    id TEXT NOT NULL,
    subject_kind TEXT NOT NULL,
    subject_id TEXT NOT NULL,
    predicate TEXT NOT NULL,
    value_json TEXT NOT NULL,
    unit TEXT,
    conditions_json TEXT NOT NULL,
    evidence_status TEXT NOT NULL CHECK (evidence_status IN ('runtime_confirmed', 'source_derived', 'tested')),
    evidence_id TEXT NOT NULL,
    PRIMARY KEY (snapshot_id, id),
    FOREIGN KEY (snapshot_id, evidence_id) REFERENCES evidence(snapshot_id, id)
);
CREATE INDEX IF NOT EXISTS claims_by_subject ON claims(snapshot_id, subject_kind, subject_id);
CREATE TABLE IF NOT EXISTS relations (
    snapshot_id TEXT NOT NULL REFERENCES snapshots(id),
    id TEXT NOT NULL,
    subject_kind TEXT NOT NULL,
    subject_id TEXT NOT NULL,
    predicate TEXT NOT NULL,
    object_kind TEXT NOT NULL,
    object_id TEXT NOT NULL,
    conditions_json TEXT NOT NULL,
    evidence_status TEXT NOT NULL CHECK (evidence_status IN ('runtime_confirmed', 'source_derived', 'tested')),
    evidence_id TEXT NOT NULL,
    PRIMARY KEY (snapshot_id, id),
    FOREIGN KEY (snapshot_id, evidence_id) REFERENCES evidence(snapshot_id, id)
);
CREATE INDEX IF NOT EXISTS relations_by_subject ON relations(snapshot_id, subject_kind, subject_id);
CREATE INDEX IF NOT EXISTS relations_by_object ON relations(snapshot_id, object_kind, object_id);
CREATE TABLE IF NOT EXISTS formulas (
    snapshot_id TEXT NOT NULL REFERENCES snapshots(id),
    id TEXT NOT NULL,
    subject_kind TEXT NOT NULL,
    subject_id TEXT NOT NULL,
    result_predicate TEXT NOT NULL,
    expression_json TEXT NOT NULL,
    unit TEXT,
    conditions_json TEXT NOT NULL,
    evidence_status TEXT NOT NULL CHECK (evidence_status IN ('runtime_confirmed', 'source_derived', 'tested')),
    evidence_id TEXT NOT NULL,
    PRIMARY KEY (snapshot_id, id),
    FOREIGN KEY (snapshot_id, evidence_id) REFERENCES evidence(snapshot_id, id)
);
CREATE TABLE IF NOT EXISTS coverage (
    snapshot_id TEXT NOT NULL REFERENCES snapshots(id),
    subject_kind TEXT NOT NULL,
    subject_id TEXT NOT NULL,
    area TEXT NOT NULL,
    status TEXT NOT NULL CHECK (status IN ('verified', 'not_applicable', 'unresolved')),
    explanation TEXT NOT NULL,
    PRIMARY KEY (snapshot_id, subject_kind, subject_id, area)
);
CREATE TABLE IF NOT EXISTS guide_refs (
    snapshot_id TEXT NOT NULL REFERENCES snapshots(id),
    guide_id TEXT NOT NULL,
    record_kind TEXT NOT NULL CHECK (record_kind IN ('claim', 'relation', 'formula')),
    record_id TEXT NOT NULL,
    PRIMARY KEY (snapshot_id, guide_id, record_kind, record_id)
);
CREATE TABLE IF NOT EXISTS revalidation (
    snapshot_id TEXT NOT NULL REFERENCES snapshots(id),
    mod_id TEXT NOT NULL,
    prior_snapshot_id TEXT NOT NULL REFERENCES snapshots(id),
    reason TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'pending' CHECK (status IN ('pending', 'reviewed')),
    PRIMARY KEY (snapshot_id, mod_id, prior_snapshot_id)
);
CREATE TABLE IF NOT EXISTS research_jobs (
    snapshot_id TEXT NOT NULL REFERENCES snapshots(id),
    id TEXT NOT NULL,
    mod_id TEXT NOT NULL,
    subsystem TEXT NOT NULL,
    packet_json TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'ready' CHECK (status IN ('ready', 'submitted', 'reviewed')),
    PRIMARY KEY (snapshot_id, id)
);
CREATE INDEX IF NOT EXISTS research_jobs_by_mod ON research_jobs(snapshot_id, mod_id, status);
CREATE TABLE IF NOT EXISTS findings (
    snapshot_id TEXT NOT NULL REFERENCES snapshots(id),
    id TEXT NOT NULL,
    job_id TEXT NOT NULL,
    record_type TEXT NOT NULL CHECK (record_type IN
        ('claim', 'relation', 'formula', 'coverage', 'gap', 'adapter_request')),
    finding_json TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'pending' CHECK (status IN ('pending', 'accepted', 'rejected')),
    review_note TEXT,
    PRIMARY KEY (snapshot_id, id),
    FOREIGN KEY (snapshot_id, job_id) REFERENCES research_jobs(snapshot_id, id)
);
CREATE INDEX IF NOT EXISTS findings_by_status ON findings(snapshot_id, status, job_id);
"""


def _canonical(value: object) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def capture_identity(capture_db: Path) -> tuple[str, dict, list[tuple[str, str | None]]]:
    """Identify equivalent imports by their authenticated capture evidence."""
    with closing(sqlite3.connect(f"file:{capture_db.resolve().as_posix()}?mode=ro", uri=True)) as db:
        row = db.execute("SELECT provenance_json, generated_at_utc, minecraft_version, neoforge_version FROM capture WHERE id=1").fetchone()
        if row is None:
            raise ValueError("capture database has no provenance")
        files = db.execute("SELECT name, bytes, sha256 FROM capture_files ORDER BY name").fetchall()
        mods = db.execute("SELECT id, version FROM mods ORDER BY id").fetchall()
    provenance = json.loads(row[0])
    identity = {"provenance": provenance, "files": files, "mods": mods}
    digest = hashlib.sha256(_canonical(identity).encode("utf-8")).hexdigest()
    return digest, provenance, mods


class KnowledgeStore:
    def __init__(self, path: Path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.connect() as db:
            db.executescript(SCHEMA)

    @contextmanager
    def connect(self):
        with closing(sqlite3.connect(self.path)) as db:
            db.row_factory = sqlite3.Row
            db.execute("PRAGMA foreign_keys=ON")
            with db:
                yield db

    def register_capture(self, capture_db: Path) -> str:
        snapshot_id, provenance, mods = capture_identity(capture_db)
        artifacts = []
        with closing(sqlite3.connect(f"file:{capture_db.resolve().as_posix()}?mode=ro", uri=True)) as capture:
            if capture.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='installed_artifacts'").fetchone():
                for sha, file_name, declared in capture.execute(
                        "SELECT sha256,file_name,declared_mod_ids_json FROM installed_artifacts"):
                    artifacts.extend((snapshot_id, mod_id, sha, file_name) for mod_id in json.loads(declared))
        with self.connect() as db:
            already_known = db.execute("SELECT 1 FROM snapshots WHERE id=?", (snapshot_id,)).fetchone()
            prior = db.execute("SELECT id FROM snapshots WHERE id<>? ORDER BY rowid DESC LIMIT 1", (snapshot_id,)).fetchone()
            db.execute("INSERT OR IGNORE INTO snapshots VALUES (?, ?, ?, ?, ?)",
                       (snapshot_id, _canonical(provenance), provenance.get("generated_at_utc"),
                        provenance.get("minecraft_version"), provenance.get("neoforge_version")))
            db.executemany("INSERT OR IGNORE INTO snapshot_mods VALUES (?, ?, ?)",
                           ((snapshot_id, mod_id, version) for mod_id, version in mods))
            db.executemany("INSERT OR IGNORE INTO snapshot_artifacts VALUES (?, ?, ?, ?)", artifacts)
            if not already_known and prior:
                prior_id = prior[0]
                previous_versions = {row[0]: row[1] for row in db.execute(
                    "SELECT mod_id,version FROM snapshot_mods WHERE snapshot_id=?", (prior_id,))}
                reviewed_mods = {row[0].split(":", 1)[0] for table in ("claims", "relations", "formulas")
                                 for row in db.execute(f"SELECT subject_id FROM {table} WHERE snapshot_id=?", (prior_id,))}
                for mod_id, version in mods:
                    if mod_id not in reviewed_mods or mod_id not in previous_versions:
                        continue
                    reason = "mod_version_changed" if version != previous_versions[mod_id] else "pack_snapshot_changed"
                    db.execute("INSERT INTO revalidation VALUES (?, ?, ?, ?, 'pending')",
                               (snapshot_id, mod_id, prior_id, reason))
            db.commit()
        return snapshot_id

    def read_subject(self, snapshot_id: str, kind: str, subject_id: str) -> dict:
        with self.connect() as db:
            claims = [dict(row) for row in db.execute(
                "SELECT c.*, e.kind AS evidence_kind, e.locator AS evidence_locator, "
                "e.artifact_sha256, e.source_revision FROM claims c JOIN evidence e "
                "ON e.snapshot_id=c.snapshot_id AND e.id=c.evidence_id "
                "WHERE c.snapshot_id=? AND c.subject_kind=? AND c.subject_id=? ORDER BY c.predicate,c.id",
                (snapshot_id, kind, subject_id))]
            relations = [dict(row) for row in db.execute(
                "SELECT r.*, e.kind AS evidence_kind, e.locator AS evidence_locator "
                "FROM relations r JOIN evidence e ON e.snapshot_id=r.snapshot_id AND e.id=r.evidence_id "
                "WHERE r.snapshot_id=? AND ((r.subject_kind=? AND r.subject_id=?) "
                "OR (r.object_kind=? AND r.object_id=?)) ORDER BY r.predicate,r.id",
                (snapshot_id, kind, subject_id, kind, subject_id))]
            formulas = [dict(row) for row in db.execute(
                "SELECT f.*, e.kind AS evidence_kind, e.locator AS evidence_locator "
                "FROM formulas f JOIN evidence e ON e.snapshot_id=f.snapshot_id AND e.id=f.evidence_id "
                "WHERE f.snapshot_id=? AND f.subject_kind=? AND f.subject_id=? ORDER BY f.id",
                (snapshot_id, kind, subject_id))]
            coverage = [dict(row) for row in db.execute(
                "SELECT area,status,explanation FROM coverage WHERE snapshot_id=? AND subject_kind=? AND subject_id=? ORDER BY area",
                (snapshot_id, kind, subject_id))]
        for row in claims:
            row["value"] = json.loads(row.pop("value_json"))
            row["conditions"] = json.loads(row.pop("conditions_json"))
        for row in relations:
            row["conditions"] = json.loads(row.pop("conditions_json"))
        for row in formulas:
            row["expression"] = json.loads(row.pop("expression_json"))
            row["conditions"] = json.loads(row.pop("conditions_json"))
        return {"claims": claims, "relations": relations, "formulas": formulas, "coverage": coverage}

    def mod_coverage(self, snapshot_id: str, mod_id: str, capture_db: Path) -> dict:
        with closing(sqlite3.connect(f"file:{capture_db.resolve().as_posix()}?mode=ro", uri=True)) as capture:
            items = capture.execute("SELECT id FROM items WHERE mod_id=? ORDER BY id", (mod_id,)).fetchall()
        with self.connect() as db:
            grouped = [dict(row) for row in db.execute(
                "SELECT area,status,COUNT(*) AS count FROM coverage WHERE snapshot_id=? "
                "AND subject_kind='item' AND subject_id LIKE ? GROUP BY area,status ORDER BY area,status",
                (snapshot_id, mod_id + ":%"))]
            systems = [dict(row) for row in db.execute(
                "SELECT subject_id,area,status,explanation FROM coverage WHERE snapshot_id=? "
                "AND subject_kind='system' AND subject_id LIKE ? ORDER BY subject_id,area",
                (snapshot_id, mod_id + ":%"))]
            covered = db.execute("SELECT COUNT(DISTINCT subject_id) FROM coverage WHERE snapshot_id=? "
                                 "AND subject_kind='item' AND subject_id LIKE ?", (snapshot_id, mod_id + ":%" )).fetchone()[0]
            revalidation = [dict(row) for row in db.execute(
                "SELECT prior_snapshot_id,reason,status FROM revalidation WHERE snapshot_id=? AND mod_id=?",
                (snapshot_id, mod_id))]
        return {"mod_id": mod_id, "item_count": len(items), "items_with_coverage": covered,
                "items_without_coverage": len(items) - covered, "areas": grouped,
                "system_areas": systems,
                "revalidation": revalidation}

    def add_job(self, packet: dict) -> None:
        with self.connect() as db:
            existing = db.execute("SELECT packet_json FROM research_jobs WHERE snapshot_id=? AND id=?",
                                  (packet["snapshot_id"], packet["job_id"])).fetchone()
            encoded = _canonical(packet)
            if existing and existing[0] != encoded:
                raise ValueError(f"job packet changed for existing id: {packet['job_id']}")
            db.execute("INSERT OR IGNORE INTO research_jobs (snapshot_id,id,mod_id,subsystem,packet_json) "
                       "VALUES (?,?,?,?,?)", (packet["snapshot_id"], packet["job_id"], packet["mod_id"],
                                             packet["subsystem"], encoded))

    def list_jobs(self, snapshot_id: str, mod_id: str = "") -> list[dict]:
        with self.connect() as db:
            query = "SELECT id,mod_id,subsystem,status FROM research_jobs WHERE snapshot_id=?"
            params = [snapshot_id]
            if mod_id:
                query += " AND mod_id=?"
                params.append(mod_id)
            return [dict(row) for row in db.execute(query + " ORDER BY mod_id,subsystem,id", params)]

    def job(self, snapshot_id: str, job_id: str) -> dict:
        with self.connect() as db:
            row = db.execute("SELECT packet_json FROM research_jobs WHERE snapshot_id=? AND id=?",
                             (snapshot_id, job_id)).fetchone()
            if row is None:
                raise ValueError(f"research job not found: {job_id}")
            return json.loads(row[0])

    def submit_finding(self, finding: dict) -> None:
        if finding.get("format") != "ch4os-research-finding-v1":
            raise ValueError("unsupported research finding format")
        for key in ("snapshot_id", "job_id", "finding_id", "record_type", "subject_kind", "subject_id"):
            if not isinstance(finding.get(key), str) or not finding[key]:
                raise ValueError(f"finding needs {key}")
        if finding["record_type"] not in {"claim", "relation", "formula", "coverage", "gap", "adapter_request"}:
            raise ValueError("unsupported finding record type")
        if len(_canonical(finding).encode("utf-8")) > 65536:
            raise ValueError("finding exceeds 64 KiB")
        with self.connect() as db:
            job = db.execute("SELECT mod_id FROM research_jobs WHERE snapshot_id=? AND id=?",
                             (finding["snapshot_id"], finding["job_id"])).fetchone()
            if job is None:
                raise ValueError("finding refers to an unknown job or snapshot")
            encoded = _canonical(finding)
            existing = db.execute("SELECT finding_json FROM findings WHERE snapshot_id=? AND id=?",
                                  (finding["snapshot_id"], finding["finding_id"])).fetchone()
            if existing and existing[0] != encoded:
                raise ValueError("finding ID already has different content")
            db.execute("INSERT OR IGNORE INTO findings (snapshot_id,id,job_id,record_type,finding_json) "
                       "VALUES (?,?,?,?,?)", (finding["snapshot_id"], finding["finding_id"],
                                            finding["job_id"], finding["record_type"], encoded))
            db.execute("UPDATE research_jobs SET status='submitted' WHERE snapshot_id=? AND id=? AND status='ready'",
                       (finding["snapshot_id"], finding["job_id"]))

    def list_findings(self, snapshot_id: str, mod_id: str = "", status: str = "pending") -> list[dict]:
        if status not in {"pending", "accepted", "rejected", "all"}:
            raise ValueError("invalid finding status")
        query = ("SELECT f.id,f.job_id,f.record_type,f.status,f.review_note,f.finding_json "
                 "FROM findings f JOIN research_jobs j ON j.snapshot_id=f.snapshot_id AND j.id=f.job_id "
                 "WHERE f.snapshot_id=?")
        params = [snapshot_id]
        if mod_id:
            query += " AND j.mod_id=?"
            params.append(mod_id)
        if status != "all":
            query += " AND f.status=?"
            params.append(status)
        with self.connect() as db:
            result = []
            for row in db.execute(query + " ORDER BY j.mod_id,f.job_id,f.id", params):
                entry = dict(row)
                entry["finding"] = json.loads(entry.pop("finding_json"))
                result.append(entry)
            return result

    def review_finding(self, snapshot_id: str, finding_id: str, decision: str,
                       capture_db: Path, note: str = "") -> dict:
        if decision not in {"accept", "reject"}:
            raise ValueError("decision must be accept or reject")
        if capture_identity(capture_db)[0] != snapshot_id:
            raise ValueError("review capture does not match the finding snapshot")
        with self.connect() as db:
            row = db.execute("SELECT f.finding_json,f.status,j.mod_id,f.job_id FROM findings f "
                             "JOIN research_jobs j ON j.snapshot_id=f.snapshot_id AND j.id=f.job_id "
                             "WHERE f.snapshot_id=? AND f.id=?", (snapshot_id, finding_id)).fetchone()
            if row is None:
                raise ValueError("finding not found")
            if row[1] != "pending":
                raise ValueError("finding already reviewed")
            finding = json.loads(row[0])
            mod_id = row[2]
            if decision == "accept":
                self._accept(db, capture_db, snapshot_id, mod_id, finding)
            db.execute("UPDATE findings SET status=?,review_note=? WHERE snapshot_id=? AND id=?",
                       ("accepted" if decision == "accept" else "rejected", note, snapshot_id, finding_id))
            pending = db.execute("SELECT 1 FROM findings WHERE snapshot_id=? AND job_id=? AND status='pending' LIMIT 1",
                                 (snapshot_id, row[3])).fetchone()
            if pending is None:
                db.execute("UPDATE research_jobs SET status='reviewed' WHERE snapshot_id=? AND id=?",
                           (snapshot_id, row[3]))
        return {"snapshot_id": snapshot_id, "finding_id": finding_id, "decision": decision}

    def _accept(self, db: sqlite3.Connection, capture_db: Path, snapshot_id: str,
                mod_id: str, finding: dict) -> None:
        record_type = finding["record_type"]
        self._check_endpoint(capture_db, finding["subject_kind"], finding["subject_id"])
        if record_type in {"gap", "adapter_request"}:
            if not isinstance(finding.get("description"), str) or not finding["description"].strip():
                raise ValueError("gap or adapter request needs a description")
            return
        if record_type == "coverage":
            if finding.get("status") not in {"verified", "not_applicable", "unresolved"}:
                raise ValueError("invalid coverage status")
            if not isinstance(finding.get("area"), str) or not finding["area"]:
                raise ValueError("coverage needs an area")
            explanation = finding.get("explanation")
            if not isinstance(explanation, str) or not explanation.strip():
                raise ValueError("coverage needs an explanation")
            db.execute("INSERT INTO coverage VALUES (?,?,?,?,?,?)", (snapshot_id, finding["subject_kind"],
                       finding["subject_id"], finding["area"], finding["status"], explanation))
            return
        evidence = finding.get("evidence")
        if not isinstance(evidence, dict) or evidence.get("kind") not in {
                "installed_runtime", "installed_artifact", "exact_source", "test"}:
            raise ValueError("reviewed fact needs typed evidence")
        locator = evidence.get("locator")
        if not isinstance(locator, str) or not locator.strip():
            raise ValueError("evidence needs a locator")
        if evidence["kind"] == "exact_source":
            if not evidence.get("source_revision") or evidence.get("match_basis") != "exact_installed_version":
                raise ValueError("source fact needs an exact installed-version match and revision")
            matched = db.execute("SELECT 1 FROM snapshot_artifacts WHERE snapshot_id=? AND mod_id=? AND artifact_sha256=?",
                                 (snapshot_id, mod_id, evidence.get("artifact_sha256"))).fetchone()
            if matched is None:
                raise ValueError("source artifact SHA-256 is not installed for this mod in this snapshot")
        if evidence["kind"] == "installed_artifact":
            matched = db.execute("SELECT 1 FROM snapshot_artifacts WHERE snapshot_id=? AND artifact_sha256=?",
                                 (snapshot_id, evidence.get("artifact_sha256"))).fetchone()
            if matched is None:
                raise ValueError("artifact evidence does not match this snapshot")
        if evidence["kind"] == "installed_runtime" and not locator.startswith("capture/"):
            raise ValueError("runtime evidence locator must name a capture record")
        status = {"installed_runtime": "runtime_confirmed", "installed_artifact": "source_derived",
                  "exact_source": "source_derived", "test": "tested"}[evidence["kind"]]
        evidence_id = finding["finding_id"] + ":evidence"
        db.execute("INSERT INTO evidence VALUES (?,?,?,?,?,?,?)", (snapshot_id, evidence_id, evidence["kind"],
                   locator, evidence.get("artifact_sha256"), evidence.get("source_revision"),
                   evidence.get("match_basis")))
        conditions = finding.get("conditions", {})
        if not isinstance(conditions, dict):
            raise ValueError("conditions must be an object")
        condition_json = _canonical(conditions)
        common = (snapshot_id, finding["finding_id"], finding["subject_kind"], finding["subject_id"])
        if record_type == "claim":
            if not finding.get("predicate") or "value" not in finding or finding["value"] is None:
                raise ValueError("claim needs a predicate and non-null value")
            db.execute("INSERT INTO claims VALUES (?,?,?,?,?,?,?,?,?,?)",
                       (*common, finding["predicate"], _canonical(finding["value"]), finding.get("unit"),
                        condition_json, status, evidence_id))
        elif record_type == "relation":
            for field in ("predicate", "object_kind", "object_id"):
                if not isinstance(finding.get(field), str) or not finding[field]:
                    raise ValueError(f"relation needs {field}")
            self._check_endpoint(capture_db, finding["object_kind"], finding["object_id"])
            db.execute("INSERT INTO relations VALUES (?,?,?,?,?,?,?,?,?,?)",
                       (*common, finding["predicate"], finding["object_kind"], finding["object_id"],
                        condition_json, status, evidence_id))
        elif record_type == "formula":
            if not finding.get("result_predicate") or not isinstance(finding.get("expression"), dict):
                raise ValueError("formula needs a result predicate and structured expression")
            db.execute("INSERT INTO formulas VALUES (?,?,?,?,?,?,?,?,?,?)",
                       (*common, finding["result_predicate"], _canonical(finding["expression"]),
                        finding.get("unit"), condition_json, status, evidence_id))

    @staticmethod
    def _check_endpoint(capture_db: Path, kind: str, entry_id: str) -> None:
        table = {"item": "items", "block": "blocks", "recipe": "recipes"}.get(kind)
        if table is None:
            if kind not in {"system", "process", "fluid", "entity", "tag", "config", "interface"}:
                raise ValueError(f"unsupported knowledge subject kind: {kind}")
            if ":" not in entry_id:
                raise ValueError("non-registry knowledge IDs must be namespaced")
            return
        with closing(sqlite3.connect(f"file:{capture_db.resolve().as_posix()}?mode=ro", uri=True)) as capture:
            if capture.execute(f"SELECT 1 FROM {table} WHERE id=?", (entry_id,)).fetchone() is None:
                raise ValueError(f"{kind} is absent from this capture: {entry_id}")
