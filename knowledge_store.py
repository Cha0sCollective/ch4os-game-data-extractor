"""Persistent, snapshot-scoped reviewed knowledge for GDE captures.

Capture databases remain disposable projections of their ZIPs. This database is
kept separately so importing a newer pack cannot overwrite reviewed research.
"""

from __future__ import annotations

from contextlib import closing, contextmanager
import hashlib
import json
from pathlib import Path
import re
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
CREATE TABLE IF NOT EXISTS reviewed_artifact_links (
    snapshot_id TEXT NOT NULL,
    mod_id TEXT NOT NULL,
    artifact_sha256 TEXT NOT NULL,
    link_json TEXT NOT NULL,
    PRIMARY KEY (snapshot_id, mod_id, artifact_sha256),
    FOREIGN KEY (snapshot_id, mod_id) REFERENCES snapshot_mods(snapshot_id, mod_id)
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
CREATE TABLE IF NOT EXISTS coverage_history (
    snapshot_id TEXT NOT NULL REFERENCES snapshots(id),
    finding_id TEXT NOT NULL,
    subject_kind TEXT NOT NULL,
    subject_id TEXT NOT NULL,
    area TEXT NOT NULL,
    previous_status TEXT,
    new_status TEXT NOT NULL,
    explanation TEXT NOT NULL,
    reviewed_at_utc TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ','now')),
    PRIMARY KEY (snapshot_id, finding_id)
);
CREATE INDEX IF NOT EXISTS coverage_history_by_subject
    ON coverage_history(snapshot_id, subject_kind, subject_id, area);
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
    review_note TEXT,
    reviewed_at_utc TEXT,
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
CREATE TABLE IF NOT EXISTS adapter_tasks (
    snapshot_id TEXT NOT NULL REFERENCES snapshots(id),
    finding_id TEXT NOT NULL,
    mod_id TEXT NOT NULL,
    subject_kind TEXT NOT NULL,
    subject_id TEXT NOT NULL,
    description TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'open' CHECK (status IN ('open', 'resolved')),
    resolution TEXT,
    PRIMARY KEY (snapshot_id, finding_id),
    FOREIGN KEY (snapshot_id, finding_id) REFERENCES findings(snapshot_id, id)
);
CREATE INDEX IF NOT EXISTS adapter_tasks_by_mod ON adapter_tasks(snapshot_id, mod_id, status);
"""


def _canonical(value: object) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def artifact_hashes(db: sqlite3.Connection, snapshot_id: str, mod_id: str | None = None) -> set[str]:
    """Captured artifacts plus explicitly reviewed, snapshot-scoped lineage.

    Read older knowledge databases without requiring a schema migration.
    """
    result = set()
    for table in ("snapshot_artifacts", "reviewed_artifact_links"):
        if not db.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name=?", (table,)).fetchone():
            continue
        query = f"SELECT artifact_sha256 FROM {table} WHERE snapshot_id=?"
        params = [snapshot_id]
        if mod_id is not None:
            query += " AND mod_id=?"
            params.append(mod_id)
        result.update(row[0] for row in db.execute(query, params))
    return result


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
            columns = {row[1] for row in db.execute("PRAGMA table_info(revalidation)")}
            if "review_note" not in columns:
                db.execute("ALTER TABLE revalidation ADD COLUMN review_note TEXT")
            if "reviewed_at_utc" not in columns:
                db.execute("ALTER TABLE revalidation ADD COLUMN reviewed_at_utc TEXT")

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
            db.execute("INSERT OR IGNORE INTO snapshots VALUES (?, ?, ?, ?, ?)",
                       (snapshot_id, _canonical(provenance), provenance.get("generated_at_utc"),
                        provenance.get("minecraft_version"), provenance.get("neoforge_version")))
            db.executemany("INSERT OR IGNORE INTO snapshot_mods VALUES (?, ?, ?)",
                           ((snapshot_id, mod_id, version) for mod_id, version in mods))
            db.executemany("INSERT OR IGNORE INTO snapshot_artifacts VALUES (?, ?, ?, ?)", artifacts)
            current_rowid = db.execute("SELECT rowid FROM snapshots WHERE id=?", (snapshot_id,)).fetchone()[0]
            reviewed = {(row[0], row[1].split(":", 1)[0])
                        for table in ("claims", "relations", "formulas", "coverage")
                        for row in db.execute(f"SELECT DISTINCT snapshot_id,subject_id FROM {table} "
                                              "WHERE instr(subject_id, ':') > 0")}
            latest_reviewed: dict[str, tuple[str, str | None]] = {}
            for row in db.execute("SELECT s.id,sm.mod_id,sm.version FROM snapshots s "
                                  "JOIN snapshot_mods sm ON sm.snapshot_id=s.id "
                                  "WHERE s.rowid<? ORDER BY s.rowid DESC", (current_rowid,)):
                if row[1] not in latest_reviewed and (row[0], row[1]) in reviewed:
                    latest_reviewed[row[1]] = (row[0], row[2])
            for mod_id, version in mods:
                if mod_id not in latest_reviewed:
                    continue
                prior_id, prior_version = latest_reviewed[mod_id]
                reason = "mod_version_changed" if version != prior_version else "pack_snapshot_changed"
                db.execute("INSERT OR IGNORE INTO revalidation "
                           "(snapshot_id,mod_id,prior_snapshot_id,reason,status) "
                           "VALUES (?, ?, ?, ?, 'pending')",
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
            coverage_history = [dict(row) for row in db.execute(
                "SELECT area,previous_status,new_status,explanation,finding_id,reviewed_at_utc "
                "FROM coverage_history WHERE snapshot_id=? AND subject_kind=? AND subject_id=? "
                "ORDER BY rowid", (snapshot_id, kind, subject_id))]
        for row in claims:
            row["value"] = json.loads(row.pop("value_json"))
            row["conditions"] = json.loads(row.pop("conditions_json"))
        for row in relations:
            row["conditions"] = json.loads(row.pop("conditions_json"))
        for row in formulas:
            row["expression"] = json.loads(row.pop("expression_json"))
            row["conditions"] = json.loads(row.pop("conditions_json"))
        return {"claims": claims, "relations": relations, "formulas": formulas,
                "coverage": coverage, "coverage_history": coverage_history}

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
                "SELECT prior_snapshot_id,reason,status,review_note,reviewed_at_utc "
                "FROM revalidation WHERE snapshot_id=? AND mod_id=?",
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

    def review_artifact_links(self, capture_db: Path, links: list[dict], note: str) -> None:
        """Retain an offline review separately from the authenticated capture.

        Call artifact_lineage inspectors to construct links from actual bytes.
        Platform links establish the captured version, not a captured binary hash.
        """
        snapshot_id = capture_identity(capture_db)[0]
        if not isinstance(note, str) or not note.strip():
            raise ValueError("artifact review needs a note")
        with self.connect() as db:
            for link in links:
                mod = db.execute("SELECT version FROM snapshot_mods WHERE snapshot_id=? AND mod_id=?",
                                 (snapshot_id, link.get("mod_id"))).fetchone()
                if mod is None or mod[0] != link.get("version"):
                    raise ValueError("artifact module/version differs from this snapshot")
                if not re.fullmatch(r"[a-f0-9]{64}", link.get("artifact_sha256", "")):
                    raise ValueError("artifact link needs a SHA-256")
                if link.get("kind") == "nested":
                    if db.execute("SELECT 1 FROM snapshot_artifacts WHERE snapshot_id=? AND artifact_sha256=?",
                                  (snapshot_id, link.get("root_sha256"))).fetchone() is None:
                        raise ValueError("nested artifact root is not installed in this snapshot")
                    if not link.get("entry_path") or not link.get("parent_sha256"):
                        raise ValueError("nested artifact needs parent and entry lineage")
                elif link.get("kind") == "platform_version":
                    if link.get("mod_id") != "minecraft" or link.get("metadata_version") != mod[0]:
                        raise ValueError("platform artifact version differs from captured Minecraft")
                else:
                    raise ValueError("unsupported artifact link kind")
                reviewed = {**link, "snapshot_id": snapshot_id, "review_note": note}
                encoded = _canonical(reviewed)
                key = (snapshot_id, link["mod_id"], link["artifact_sha256"])
                old = db.execute("SELECT link_json FROM reviewed_artifact_links WHERE snapshot_id=? "
                                 "AND mod_id=? AND artifact_sha256=?", key).fetchone()
                if old and old[0] != encoded:
                    raise ValueError("reviewed artifact link is immutable")
                db.execute("INSERT OR IGNORE INTO reviewed_artifact_links VALUES (?,?,?,?)", (*key, encoded))

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
            inserted = db.execute("INSERT OR IGNORE INTO findings (snapshot_id,id,job_id,record_type,finding_json) "
                                  "VALUES (?,?,?,?,?)", (finding["snapshot_id"], finding["finding_id"],
                                                       finding["job_id"], finding["record_type"], encoded)).rowcount
            if inserted:
                db.execute("UPDATE research_jobs SET status='submitted' WHERE snapshot_id=? AND id=?",
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

    def list_adapter_tasks(self, snapshot_id: str, mod_id: str = "") -> list[dict]:
        query = "SELECT * FROM adapter_tasks WHERE snapshot_id=?"
        params = [snapshot_id]
        if mod_id:
            query += " AND mod_id=?"
            params.append(mod_id)
        with self.connect() as db:
            return [dict(row) for row in db.execute(query + " ORDER BY status,mod_id,finding_id", params)]

    def resolve_adapter_task(self, snapshot_id: str, finding_id: str, resolution: str) -> None:
        if not isinstance(resolution, str) or not resolution.strip():
            raise ValueError("resolution needs evidence or a capture reference")
        with self.connect() as db:
            changed = db.execute("UPDATE adapter_tasks SET status='resolved',resolution=? "
                                 "WHERE snapshot_id=? AND finding_id=? AND status='open'",
                                 (resolution, snapshot_id, finding_id)).rowcount
            if not changed:
                raise ValueError("open adapter task not found")

    def review_revalidation(self, snapshot_id: str, mod_id: str, note: str) -> None:
        if not isinstance(note, str) or not note.strip():
            raise ValueError("revalidation needs a review note with evidence")
        with self.connect() as db:
            outstanding = db.execute(
                "SELECT COUNT(*) FROM findings f JOIN research_jobs j "
                "ON j.snapshot_id=f.snapshot_id AND j.id=f.job_id "
                "WHERE f.snapshot_id=? AND j.mod_id=? AND f.status='pending'",
                (snapshot_id, mod_id)).fetchone()[0]
            if outstanding:
                raise ValueError("pending findings must be reviewed before revalidation closes")
            accepted = db.execute(
                "SELECT COUNT(*) FROM findings f JOIN research_jobs j "
                "ON j.snapshot_id=f.snapshot_id AND j.id=f.job_id "
                "WHERE f.snapshot_id=? AND j.mod_id=? AND f.status='accepted'",
                (snapshot_id, mod_id)).fetchone()[0]
            if not accepted:
                raise ValueError("revalidation needs accepted findings for this snapshot")
            changed = db.execute(
                "UPDATE revalidation SET status='reviewed',review_note=?,"
                "reviewed_at_utc=strftime('%Y-%m-%dT%H:%M:%fZ','now') "
                "WHERE snapshot_id=? AND mod_id=? AND status='pending'",
                (note.strip(), snapshot_id, mod_id)).rowcount
            if not changed:
                raise ValueError("pending revalidation not found")

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
            if record_type == "adapter_request":
                db.execute("INSERT INTO adapter_tasks "
                           "(snapshot_id,finding_id,mod_id,subject_kind,subject_id,description) "
                           "VALUES (?,?,?,?,?,?)", (snapshot_id, finding["finding_id"], mod_id,
                           finding["subject_kind"], finding["subject_id"], finding["description"]))
            return
        if record_type == "coverage":
            if finding.get("status") not in {"verified", "not_applicable", "unresolved"}:
                raise ValueError("invalid coverage status")
            if not isinstance(finding.get("area"), str) or not finding["area"]:
                raise ValueError("coverage needs an area")
            explanation = finding.get("explanation")
            if not isinstance(explanation, str) or not explanation.strip():
                raise ValueError("coverage needs an explanation")
            previous = db.execute("SELECT status FROM coverage WHERE snapshot_id=? AND subject_kind=? "
                                  "AND subject_id=? AND area=?", (snapshot_id, finding["subject_kind"],
                                  finding["subject_id"], finding["area"])).fetchone()
            db.execute("INSERT INTO coverage VALUES (?,?,?,?,?,?) ON CONFLICT "
                       "(snapshot_id,subject_kind,subject_id,area) DO UPDATE SET "
                       "status=excluded.status,explanation=excluded.explanation",
                       (snapshot_id, finding["subject_kind"], finding["subject_id"],
                        finding["area"], finding["status"], explanation))
            db.execute("INSERT INTO coverage_history "
                       "(snapshot_id,finding_id,subject_kind,subject_id,area,previous_status,new_status,explanation) "
                       "VALUES (?,?,?,?,?,?,?,?)", (snapshot_id, finding["finding_id"], finding["subject_kind"],
                       finding["subject_id"], finding["area"], previous[0] if previous else None,
                       finding["status"], explanation))
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
            owner = evidence.get("mod_id", mod_id)
            if not isinstance(owner, str) or not owner.strip():
                raise ValueError("source evidence needs a module owner")
            if evidence.get("artifact_sha256") not in artifact_hashes(db, snapshot_id, owner):
                raise ValueError("source artifact SHA-256 is not installed for this mod in this snapshot")
        if evidence["kind"] == "installed_artifact":
            if "mod_id" in evidence and (not isinstance(evidence["mod_id"], str) or not evidence["mod_id"].strip()):
                raise ValueError("artifact evidence needs a module owner")
            if evidence.get("artifact_sha256") not in artifact_hashes(db, snapshot_id, evidence.get("mod_id")):
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
