"""Synthetic-only, source-preserving case investigation ledger.

This module is a research/engineering reference implementation, NOT a medical
record system. No patient authentication, PHI handling, or clinical validation.
"""

from __future__ import annotations

import hashlib
import json
import re
import sqlite3
from dataclasses import dataclass
from datetime import date, datetime, timezone
from pathlib import Path

ID = re.compile(r"[A-Z][A-Z0-9-]{1,39}\Z")
KEY = re.compile(r"[a-z][a-z0-9_-]{0,59}\Z")
STATES = frozenset({"reported", "negative", "pending", "indeterminate", "not-reported", "not-assessed", "conflicting"})
TYPES = frozenset({"pathology", "molecular", "imaging", "laboratory", "clinical", "other"})
MAX_SOURCE_BYTES = 65536
MAX_SUMMARY = 3000


class InvalidInput(ValueError):
    """A request does not satisfy the synthetic document contract."""


def now_utc() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def valid_id(value: object) -> str:
    if not isinstance(value, str) or not ID.fullmatch(value):
        raise InvalidInput("Invalid synthetic identifier; use uppercase A–Z, numbers and hyphens")
    return value


def valid_date(value: str) -> str:
    try:
        parsed = date.fromisoformat(value)
    except (TypeError, ValueError):
        raise InvalidInput("Dates must use YYYY-MM-DD") from None
    if parsed.isoformat() != value:
        raise InvalidInput("Dates must use YYYY-MM-DD")
    return value


@dataclass(frozen=True)
class Finding:
    key: str
    state: str
    quote: str
    line: int


@dataclass(frozen=True)
class ParsedReport:
    patient_id: str
    document_id: str
    kind: str
    event_date: str
    issued_at: str
    specimen_id: str | None
    amends: tuple[str, int] | None
    findings: tuple[Finding, ...]
    raw: bytes


def parse_report(raw: bytes) -> ParsedReport:
    """Parse intentionally structured, independently authored OI test reports.

    This is not a general clinical-document extractor. Finding lines are explicit
    annotations authored in the input itself, not AI-derived interpretations.
    """
    if not isinstance(raw, bytes) or len(raw) > MAX_SOURCE_BYTES or not raw:
        raise InvalidInput("Report must be nonempty UTF-8, at most 64 KiB")
    try:
        text = raw.decode("utf-8", errors="strict")
    except UnicodeDecodeError:
        raise InvalidInput("Report must be UTF-8") from None
    if "\x00" in text or "\r" in text:
        raise InvalidInput("NUL and CR characters are not supported in this report format")
    lines = text.splitlines()
    if not lines or lines[0] != "OI-SYNTHETIC-REPORT/1":
        raise InvalidInput("Only OI-SYNTHETIC-REPORT/1 is supported")
    fields: dict[str, str] = {}
    findings: list[Finding] = []
    used_keys: set[str] = set()
    field_names = {"Patient", "Document", "Type", "Event-Date", "Issued-At", "Specimen", "Amends"}
    for line_number, line in enumerate(lines[1:], start=2):
        if not line.strip():
            continue
        if ": " not in line:
            raise InvalidInput(f"Line {line_number}: expected 'Field: value'")
        label, value = line.split(": ", 1)
        if label == "Finding":
            parts = value.split("|", 2)
            if len(parts) != 3:
                raise InvalidInput(f"Line {line_number}: finding needs key|state|source quotation")
            key, state, quote = (part.strip() for part in parts)
            if not KEY.fullmatch(key) or state not in STATES or not quote or key in used_keys:
                raise InvalidInput(f"Line {line_number}: invalid or repeated finding key/status/quotation")
            if len(quote) > 1200:
                raise InvalidInput(f"Line {line_number}: quotation too long")
            findings.append(Finding(key, state, quote, line_number))
            used_keys.add(key)
        elif label in field_names and label not in fields and value.strip():
            fields[label] = value.strip()
        else:
            raise InvalidInput(f"Line {line_number}: unknown, duplicate, or empty field")
    required = {"Patient", "Document", "Type", "Event-Date", "Issued-At"}
    if not required <= fields.keys() or not findings:
        raise InvalidInput("Patient, Document, Type, Event-Date, Issued-At and a Finding are required")
    patient_id = valid_id(fields["Patient"])
    document_id = valid_id(fields["Document"])
    kind = fields["Type"]
    if kind not in TYPES:
        raise InvalidInput("Unknown report type")
    event_date = valid_date(fields["Event-Date"])
    issued_at = valid_date(fields["Issued-At"])
    specimen_id = valid_id(fields["Specimen"]) if "Specimen" in fields else None
    amends = None
    if "Amends" in fields:
        match = re.fullmatch(r"([A-Z][A-Z0-9-]{1,39})@([1-9][0-9]*)", fields["Amends"])
        if not match:
            raise InvalidInput("Amends must be DOCUMENT-ID@VERSION")
        amends = (match.group(1), int(match.group(2)))
        if amends[0] != document_id:
            raise InvalidInput("Amends cannot refer to a different document")
    return ParsedReport(patient_id, document_id, kind, event_date, issued_at, specimen_id, amends, tuple(findings), raw)


SCHEMA = """
PRAGMA foreign_keys = ON;
CREATE TABLE IF NOT EXISTS cases (
  case_id TEXT PRIMARY KEY, label TEXT NOT NULL, synthetic INTEGER NOT NULL CHECK(synthetic=1)
);
CREATE TABLE IF NOT EXISTS source_versions (
  id INTEGER PRIMARY KEY, case_id TEXT NOT NULL REFERENCES cases(case_id),
  document_id TEXT NOT NULL, version INTEGER NOT NULL, sha256 TEXT NOT NULL,
  raw BLOB NOT NULL, kind TEXT NOT NULL, event_date TEXT NOT NULL,
  issued_at TEXT NOT NULL, received_at TEXT NOT NULL, specimen_id TEXT,
  state TEXT NOT NULL CHECK(state IN ('current','superseded')),
  supersedes_id INTEGER REFERENCES source_versions(id),
  UNIQUE(case_id,document_id,version), UNIQUE(case_id,document_id,sha256)
);
CREATE TABLE IF NOT EXISTS assertions (
  id INTEGER PRIMARY KEY, case_id TEXT NOT NULL REFERENCES cases(case_id),
  source_version_id INTEGER NOT NULL REFERENCES source_versions(id),
  finding_key TEXT NOT NULL, certainty TEXT NOT NULL, quote TEXT NOT NULL,
  source_line INTEGER NOT NULL,
  UNIQUE(source_version_id,finding_key)
);
CREATE TABLE IF NOT EXISTS questions (
  id INTEGER PRIMARY KEY, case_id TEXT NOT NULL REFERENCES cases(case_id),
  question TEXT NOT NULL, state TEXT NOT NULL CHECK(state IN ('open','addressed')),
  created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS snapshots (
  id INTEGER PRIMARY KEY, case_id TEXT NOT NULL REFERENCES cases(case_id),
  question_id INTEGER NOT NULL REFERENCES questions(id),
  summary TEXT NOT NULL, state TEXT NOT NULL CHECK(state IN ('draft','reviewed_in_demo','stale')),
  created_at TEXT NOT NULL, reviewed_at TEXT, reviewer_label TEXT
);
CREATE TABLE IF NOT EXISTS snapshot_sources (
  snapshot_id INTEGER NOT NULL REFERENCES snapshots(id),
  source_version_id INTEGER NOT NULL REFERENCES source_versions(id),
  PRIMARY KEY(snapshot_id,source_version_id)
);
CREATE TABLE IF NOT EXISTS review_events (
  id INTEGER PRIMARY KEY, snapshot_id INTEGER NOT NULL REFERENCES snapshots(id),
  reviewer_label TEXT NOT NULL, action TEXT NOT NULL, noted_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS quarantine (
  id INTEGER PRIMARY KEY, target_case_id TEXT NOT NULL REFERENCES cases(case_id),
  declared_patient_id TEXT NOT NULL, sha256 TEXT NOT NULL, raw BLOB NOT NULL,
  reason TEXT NOT NULL, received_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS events (
  id INTEGER PRIMARY KEY, case_id TEXT NOT NULL REFERENCES cases(case_id),
  kind TEXT NOT NULL, details TEXT NOT NULL, occurred_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_sources_case ON source_versions(case_id, document_id, version);
CREATE INDEX IF NOT EXISTS idx_assertions_source ON assertions(source_version_id);
CREATE INDEX IF NOT EXISTS idx_snapshot_sources_source ON snapshot_sources(source_version_id);
"""


class CaseStore:
    def __init__(self, db_path: str | Path):
        self.path = str(db_path)
        if self.path != ":memory:":
            Path(self.path).parent.mkdir(parents=True, exist_ok=True)
        self.db = sqlite3.connect(self.path, timeout=10, isolation_level="DEFERRED")
        self.db.row_factory = sqlite3.Row
        self.db.execute("PRAGMA foreign_keys=ON")
        self.db.executescript(SCHEMA)

    def close(self) -> None:
        self.db.close()

    @staticmethod
    def _dicts(rows: list[sqlite3.Row]) -> list[dict]:
        return [dict(x) for x in rows]

    def _event(self, case_id: str, kind: str, **details: object) -> None:
        self.db.execute("INSERT INTO events (case_id,kind,details,occurred_at) VALUES (?,?,?,?)",
                        (case_id, kind, json.dumps(details, sort_keys=True), now_utc()))

    def _case(self, case_id: str) -> str:
        valid_id(case_id)
        if not self.db.execute("SELECT 1 FROM cases WHERE case_id=?", (case_id,)).fetchone():
            raise InvalidInput("Unknown case")
        return case_id

    def add_case(self, case_id: str, label: str) -> None:
        valid_id(case_id)
        if not isinstance(label, str) or not (1 <= len(label.strip()) <= 80):
            raise InvalidInput("Case label must have 1–80 characters")
        try:
            with self.db:
                self.db.execute("INSERT INTO cases VALUES (?,?,1)", (case_id, label.strip()))
                self._event(case_id, "case_created")
        except sqlite3.IntegrityError:
            raise InvalidInput("Case already exists") from None

    def cases(self) -> list[dict]:
        return self._dicts(self.db.execute("SELECT case_id,label,synthetic FROM cases ORDER BY case_id").fetchall())

    def import_report(self, case_id: str, raw: bytes) -> dict:
        """Durably ingest bytes. An explicit amendment is required for changed text.

        Unknown/cross-case patient data is quarantined, never asserted as fact.
        The transaction includes invalidation; duplicates cannot emit events.
        """
        case_id = self._case(case_id)
        report = parse_report(raw)
        digest = hashlib.sha256(raw).hexdigest()
        with self.db:
            self.db.execute("BEGIN IMMEDIATE")
            if report.patient_id != case_id:
                cur = self.db.execute(
                    "INSERT INTO quarantine (target_case_id,declared_patient_id,sha256,raw,reason,received_at) VALUES (?,?,?,?,?,?)",
                    (case_id, report.patient_id, digest, raw, "patient_mismatch", now_utc()))
                self._event(case_id, "source_quarantined", quarantine_id=cur.lastrowid, reason="patient_mismatch")
                return {"result": "quarantined", "reason": "patient_mismatch", "quarantine_id": cur.lastrowid}
            duplicate = self.db.execute(
                "SELECT id,version FROM source_versions WHERE case_id=? AND document_id=? AND sha256=?",
                (case_id, report.document_id, digest)).fetchone()
            if duplicate:
                return {"result": "duplicate", "source_id": duplicate["id"], "version": duplicate["version"]}
            previous = self.db.execute(
                "SELECT id,version,kind,event_date,specimen_id FROM source_versions WHERE case_id=? AND document_id=? ORDER BY version DESC LIMIT 1",
                (case_id, report.document_id)).fetchone()
            if previous and report.amends != (report.document_id, previous["version"]):
                raise InvalidInput("Changed document requires Amends: DOCUMENT-ID@LATEST-VERSION")
            if not previous and report.amends is not None:
                raise InvalidInput("First document version cannot have Amends")
            if previous and (previous["kind"], previous["event_date"], previous["specimen_id"]) != (report.kind, report.event_date, report.specimen_id):
                raise InvalidInput("Amendment cannot change report type, event date, or specimen; create a distinct document")
            version = previous["version"] + 1 if previous else 1
            if previous:
                self.db.execute("UPDATE source_versions SET state='superseded' WHERE id=?", (previous["id"],))
            cur = self.db.execute(
                """INSERT INTO source_versions
                (case_id,document_id,version,sha256,raw,kind,event_date,issued_at,received_at,specimen_id,state,supersedes_id)
                VALUES (?,?,?,?,?,?,?,?,?,?,?,?)""",
                (case_id, report.document_id, version, digest, raw, report.kind, report.event_date,
                 report.issued_at, now_utc(), report.specimen_id, "current", previous["id"] if previous else None))
            source_id = cur.lastrowid
            for finding in report.findings:
                self.db.execute("""INSERT INTO assertions
                    (case_id,source_version_id,finding_key,certainty,quote,source_line)
                    VALUES (?,?,?,?,?,?)""",
                    (case_id, source_id, finding.key, finding.state, finding.quote, finding.line))
            invalidated = []
            if previous:
                invalidated = [row[0] for row in self.db.execute(
                    """SELECT snapshots.id FROM snapshots JOIN snapshot_sources
                    ON snapshots.id=snapshot_sources.snapshot_id
                    WHERE snapshots.case_id=? AND snapshot_sources.source_version_id=? AND snapshots.state!='stale'""",
                    (case_id, previous["id"])).fetchall()]
                if invalidated:
                    marks = ",".join("?" for _ in invalidated)
                    self.db.execute(f"UPDATE snapshots SET state='stale' WHERE id IN ({marks})", invalidated)
                    self.db.execute(f"""UPDATE questions SET state='open' WHERE case_id=? AND id IN
                        (SELECT question_id FROM snapshots WHERE id IN ({marks}))""", [case_id, *invalidated])
            self._event(case_id, "source_imported", document_id=report.document_id,
                        version=version, source_id=source_id, amends_id=previous["id"] if previous else None,
                        invalidated_snapshots=invalidated)
            return {"result": "imported", "source_id": source_id, "version": version,
                    "invalidated_snapshots": invalidated}

    def add_question(self, case_id: str, question: str) -> int:
        self._case(case_id)
        if not isinstance(question, str) or not 5 <= len(question.strip()) <= 500:
            raise InvalidInput("Question must have 5–500 characters")
        with self.db:
            cur = self.db.execute("INSERT INTO questions (case_id,question,state,created_at) VALUES (?,?,?,?)",
                                  (case_id, question.strip(), "open", now_utc()))
            self._event(case_id, "question_created", question_id=cur.lastrowid)
        return int(cur.lastrowid)

    def create_snapshot(self, case_id: str, question_id: int, summary: str, source_ids: list[int]) -> int:
        self._case(case_id)
        if not isinstance(summary, str) or not 10 <= len(summary.strip()) <= MAX_SUMMARY:
            raise InvalidInput("Draft must have 10–3000 characters")
        if not isinstance(source_ids, list) or not source_ids or any(type(x) is not int for x in source_ids):
            raise InvalidInput("Select one or more current source versions")
        if len(source_ids) != len(set(source_ids)) or len(source_ids) > 50:
            raise InvalidInput("Source IDs must be unique; maximum 50")
        with self.db:
            self.db.execute("BEGIN IMMEDIATE")  # Serialize against incoming amendments.
            question = self.db.execute("SELECT id FROM questions WHERE id=? AND case_id=?", (question_id, case_id)).fetchone()
            if not question:
                raise InvalidInput("Question not in this case")
            for sid in source_ids:
                if not self.db.execute("SELECT 1 FROM source_versions WHERE id=? AND case_id=? AND state='current'",
                                       (sid, case_id)).fetchone():
                    raise InvalidInput("Source is missing, superseded, or belongs to another case")
            cur = self.db.execute("""INSERT INTO snapshots (case_id,question_id,summary,state,created_at)
                VALUES (?,?,?,'draft',?)""", (case_id, question_id, summary.strip(), now_utc()))
            snapshot_id = int(cur.lastrowid)
            for sid in source_ids:
                self.db.execute("INSERT INTO snapshot_sources VALUES (?,?)", (snapshot_id, sid))
            self._event(case_id, "draft_created", snapshot_id=snapshot_id, question_id=question_id)
            return snapshot_id

    def acknowledge_demo_review(self, case_id: str, snapshot_id: int, reviewer_label: str) -> None:
        self._case(case_id)
        if not isinstance(reviewer_label, str) or not 2 <= len(reviewer_label.strip()) <= 80:
            raise InvalidInput("Provide a demo reviewer label")
        with self.db:
            self.db.execute("BEGIN IMMEDIATE")  # Do not acknowledge an invalidated draft.
            row = self.db.execute("SELECT state,question_id FROM snapshots WHERE case_id=? AND id=?",
                                  (case_id, snapshot_id)).fetchone()
            if not row or row["state"] != "draft":
                raise InvalidInput("Only a current draft can be acknowledged")
            timestamp = now_utc()
            self.db.execute("UPDATE snapshots SET state='reviewed_in_demo',reviewed_at=?,reviewer_label=? WHERE id=?",
                            (timestamp, reviewer_label.strip(), snapshot_id))
            self.db.execute("INSERT INTO review_events VALUES (NULL,?,?,?,?)",
                            (snapshot_id, reviewer_label.strip(), "acknowledged_in_demo", timestamp))
            self.db.execute("UPDATE questions SET state='addressed' WHERE case_id=? AND id=?",
                            (case_id, row["question_id"]))
            self._event(case_id, "demo_review_acknowledged", snapshot_id=snapshot_id)

    def state(self, case_id: str) -> dict:
        self._case(case_id)
        source_rows = self._dicts(self.db.execute(
            """SELECT id,document_id,version,sha256,kind,event_date,issued_at,received_at,
            specimen_id,state,supersedes_id FROM source_versions WHERE case_id=?
            ORDER BY event_date,document_id,version""", (case_id,)).fetchall())
        assert_rows = self._dicts(self.db.execute(
            """SELECT assertions.id,source_version_id,finding_key,certainty,quote,source_line
            FROM assertions JOIN source_versions ON source_versions.id=assertions.source_version_id
            WHERE assertions.case_id=? AND source_versions.state='current' ORDER BY assertions.id""",
            (case_id,)).fetchall())
        snapshot_rows = self._dicts(self.db.execute(
            "SELECT * FROM snapshots WHERE case_id=? ORDER BY id DESC", (case_id,)).fetchall())
        for snapshot in snapshot_rows:
            snapshot["source_ids"] = [r[0] for r in self.db.execute(
                "SELECT source_version_id FROM snapshot_sources WHERE snapshot_id=? ORDER BY source_version_id",
                (snapshot["id"],)).fetchall()]
        return {
            "case": dict(self.db.execute("SELECT * FROM cases WHERE case_id=?", (case_id,)).fetchone()),
            "sources": source_rows,
            "assertions": assert_rows,
            "questions": self._dicts(self.db.execute("SELECT * FROM questions WHERE case_id=? ORDER BY id DESC", (case_id,)).fetchall()),
            "snapshots": snapshot_rows,
            "quarantines": self._dicts(self.db.execute(
                "SELECT id,declared_patient_id,sha256,reason,received_at FROM quarantine WHERE target_case_id=? ORDER BY id DESC",
                (case_id,)).fetchall()),
            "events": self._dicts(self.db.execute(
                "SELECT id,kind,details,occurred_at FROM events WHERE case_id=? ORDER BY id DESC LIMIT 40",
                (case_id,)).fetchall()),
        }

    def source_text(self, case_id: str, source_id: int) -> str:
        self._case(case_id)
        row = self.db.execute("SELECT raw FROM source_versions WHERE case_id=? AND id=?",
                              (case_id, source_id)).fetchone()
        if not row:
            raise InvalidInput("Source not in this case")
        return bytes(row["raw"]).decode("utf-8")

    def export_markdown(self, case_id: str, snapshot_id: int) -> str:
        self._case(case_id)
        snapshot = self.db.execute("""SELECT s.*,q.question FROM snapshots s JOIN questions q ON q.id=s.question_id
            WHERE s.case_id=? AND s.id=?""", (case_id, snapshot_id)).fetchone()
        if not snapshot:
            raise InvalidInput("Investigation not in this case")
        sources = self.db.execute("""SELECT v.* FROM source_versions v JOIN snapshot_sources ss ON ss.source_version_id=v.id
            WHERE ss.snapshot_id=? ORDER BY v.document_id,v.version""", (snapshot_id,)).fetchall()
        lines = ["# Open Intelligence — synthetic investigation", "",
                 "> Research demonstration only. No clinical review or patient-specific treatment recommendation.", "",
                 f"Case: `{case_id}` | Investigation: {snapshot_id} | State: **{snapshot['state']}**",
                 f"Created: {snapshot['created_at']} | Demo acknowledgment: {snapshot['reviewed_at'] or 'None'}", "",
                 "## Question", "", snapshot["question"], "", "## Draft (human-authored)", "",
                 snapshot["summary"], "", "## Source versions and original text", ""]
        for source in sources:
            lines.extend([f"### {source['document_id']}@{source['version']} — {source['state']}", "",
                          f"SHA-256: `{source['sha256']}` | Event: {source['event_date']} | Issued: {source['issued_at']}", "",
                          "```text", bytes(source["raw"]).decode("utf-8"), "```", ""])
        lines.extend(["## Limitations", "", "- The reports, questions, and narrative are synthetic and not clinically appraised.",
                      "- An acknowledgment in this demo is not clinician credential verification or a clinical sign-off.",
                      "- Amendments can make previous investigations stale; see the state above.", ""])
        return "\n".join(lines)
