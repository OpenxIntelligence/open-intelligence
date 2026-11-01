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
from datetime import date, datetime, timedelta, timezone
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



EVIDENCE_RELATIONS = frozenset({"supports", "contradicts", "context", "unknown"})
EVIDENCE_APPLICABILITY = frozenset({"applicable", "limited", "not_applicable", "unknown"})


@dataclass(frozen=True)
class ParsedEvidence:
    evidence_key: str
    title: str
    issued_at: str
    statement: str
    statement_line: int
    amends: tuple[str, int] | None
    raw: bytes


def parse_synthetic_evidence(raw: bytes) -> ParsedEvidence:
    """Parse fictional research evidence authored for tests, never external articles.

    The declared rights field is NOT legal clearance of arbitrarily supplied
    text. Production evidence requires an independently verified rights service.
    """
    if not isinstance(raw, bytes) or not 0 < len(raw) <= 32768:
        raise InvalidInput("Synthetic evidence must be nonempty UTF-8, at most 32 KiB")
    try:
        text = raw.decode("utf-8", errors="strict")
    except UnicodeDecodeError:
        raise InvalidInput("Synthetic evidence must be UTF-8") from None
    if "\r" in text or "\x00" in text:
        raise InvalidInput("CR and NUL are not supported")
    lines = text.splitlines()
    if not lines or lines[0] != "OI-SYNTHETIC-EVIDENCE/1":
        raise InvalidInput("Only OI-SYNTHETIC-EVIDENCE/1 is accepted")
    allowed = {"Evidence", "Title", "Issued-At", "Rights", "Statement", "Amends"}
    values: dict[str, str] = {}
    statement_line = 0
    for line_number, line in enumerate(lines[1:], start=2):
        if not line.strip():
            continue
        if ": " not in line:
            raise InvalidInput(f"Evidence line {line_number}: expected 'Field: value'")
        label, value = line.split(": ", 1)
        if label not in allowed or label in values or not value.strip():
            raise InvalidInput(f"Evidence line {line_number}: unknown, duplicate, or empty field")
        values[label] = value.strip()
        if label == "Statement":
            statement_line = line_number
    if not {"Evidence", "Title", "Issued-At", "Rights", "Statement"} <= values.keys():
        raise InvalidInput("Synthetic evidence requires Evidence, Title, Issued-At, Rights, Statement")
    key = valid_id(values["Evidence"])
    title = values["Title"]
    if not 4 <= len(title) <= 180:
        raise InvalidInput("Evidence title must have 4–180 characters")
    issued_at = valid_date(values["Issued-At"])
    if values["Rights"] != "original-synthetic":
        raise InvalidInput("Only explicitly original synthetic example text is supported")
    statement = values["Statement"]
    if not 10 <= len(statement) <= 1200:
        raise InvalidInput("Evidence statement must have 10–1200 characters")
    amends = None
    if "Amends" in values:
        match = re.fullmatch(r"([A-Z][A-Z0-9-]{1,39})@([1-9][0-9]*)", values["Amends"])
        if not match or match.group(1) != key:
            raise InvalidInput("Evidence Amends must be EVIDENCE-ID@VERSION")
        amends = (key, int(match.group(2)))
    return ParsedEvidence(key, title, issued_at, statement, statement_line, amends, raw)

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
CREATE TABLE IF NOT EXISTS evidence_versions (
  id INTEGER PRIMARY KEY, evidence_key TEXT NOT NULL, version INTEGER NOT NULL,
  sha256 TEXT NOT NULL, raw BLOB NOT NULL, title TEXT NOT NULL,
  issued_at TEXT NOT NULL, received_at TEXT NOT NULL,
  statement TEXT NOT NULL, statement_line INTEGER NOT NULL,
  rights TEXT NOT NULL CHECK(rights='original-synthetic'),
  state TEXT NOT NULL CHECK(state IN ('current','superseded','withdrawn')),
  previous_id INTEGER REFERENCES evidence_versions(id),
  UNIQUE(evidence_key,version), UNIQUE(evidence_key,sha256)
);
CREATE TABLE IF NOT EXISTS evidence_assessments (
  id INTEGER PRIMARY KEY,
  case_id TEXT NOT NULL REFERENCES cases(case_id),
  question_id INTEGER NOT NULL REFERENCES questions(id),
  evidence_version_id INTEGER NOT NULL REFERENCES evidence_versions(id),
  relation TEXT NOT NULL CHECK(relation IN ('supports','contradicts','context','unknown')),
  applicability TEXT NOT NULL CHECK(applicability IN ('applicable','limited','not_applicable','unknown')),
  rationale TEXT NOT NULL, created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS snapshot_evidence (
  snapshot_id INTEGER NOT NULL REFERENCES snapshots(id),
  assessment_id INTEGER NOT NULL REFERENCES evidence_assessments(id),
  PRIMARY KEY(snapshot_id,assessment_id)
);
CREATE TABLE IF NOT EXISTS evidence_changes (
  id INTEGER PRIMARY KEY,
  evidence_version_id INTEGER NOT NULL REFERENCES evidence_versions(id),
  kind TEXT NOT NULL CHECK(kind IN ('amended','withdrawn')),
  reason TEXT NOT NULL, recorded_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_assessments_evidence ON evidence_assessments(evidence_version_id);
CREATE INDEX IF NOT EXISTS idx_snapshot_evidence_assessment ON snapshot_evidence(assessment_id);
CREATE INDEX IF NOT EXISTS idx_sources_case ON source_versions(case_id, document_id, version);
CREATE INDEX IF NOT EXISTS idx_assertions_source ON assertions(source_version_id);
CREATE INDEX IF NOT EXISTS idx_snapshot_sources_source ON snapshot_sources(source_version_id);
-- OI-021: derived option/dependency projection over the existing ledger.
-- Options are proposals tied to an investigation snapshot; they are never a
-- second canonical ledger, never a clinical recommendation, and never an
-- order. Status columns hold the CURRENT state only; history is preserved in
-- option_review_events (never deleted) and in the immutable snapshots.
CREATE TABLE IF NOT EXISTS options (
  id INTEGER PRIMARY KEY, case_id TEXT NOT NULL REFERENCES cases(case_id),
  snapshot_id INTEGER NOT NULL REFERENCES snapshots(id),
  label TEXT NOT NULL, description TEXT NOT NULL,
  epistemic_status TEXT NOT NULL CHECK(epistemic_status IN ('supported','contradicted','unsupported','unknown')),
  operational_status TEXT NOT NULL CHECK(operational_status IN ('proposed','reviewed','held','rejected','withdrawn','expired')),
  review_state TEXT NOT NULL CHECK(review_state IN ('current','needs_review')),
  created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS preparation_tasks (
  id INTEGER PRIMARY KEY, case_id TEXT NOT NULL REFERENCES cases(case_id),
  option_id INTEGER NOT NULL REFERENCES options(id),
  label TEXT NOT NULL, owner_label TEXT NOT NULL,
  status TEXT NOT NULL CHECK(status IN ('not_started','in_progress','done','blocked','cancelled')),
  lead_time_days INTEGER, created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS optionality_threats (
  id INTEGER PRIMARY KEY, option_id INTEGER NOT NULL REFERENCES options(id),
  kind TEXT NOT NULL CHECK(kind IN ('expiring_window','dependency_loss','evidence_withdrawal','other')),
  description TEXT NOT NULL, threat_date TEXT,
  threat_basis TEXT NOT NULL CHECK(threat_basis IN ('sourced','unknown')),
  anchor TEXT NOT NULL, created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS option_dependencies (
  id INTEGER PRIMARY KEY, option_id INTEGER NOT NULL REFERENCES options(id),
  kind TEXT NOT NULL CHECK(kind IN ('source','evidence_assessment','preparation_task','option')),
  source_version_id INTEGER REFERENCES source_versions(id),
  evidence_assessment_id INTEGER REFERENCES evidence_assessments(id),
  preparation_task_id INTEGER REFERENCES preparation_tasks(id),
  depends_on_option_id INTEGER REFERENCES options(id),
  lead_time_days INTEGER, deadline_date TEXT,
  deadline_basis TEXT NOT NULL CHECK(deadline_basis IN ('sourced','unknown')),
  anchor TEXT NOT NULL, created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS option_review_events (
  id INTEGER PRIMARY KEY, option_id INTEGER NOT NULL REFERENCES options(id),
  reviewer_label TEXT NOT NULL,
  action TEXT NOT NULL CHECK(action IN ('approve','reject','abstain','reconfirm','withdraw','expire')),
  scope TEXT NOT NULL, snapshot_id INTEGER REFERENCES snapshots(id), noted_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_options_case ON options(case_id, snapshot_id);
CREATE INDEX IF NOT EXISTS idx_option_deps_option ON option_dependencies(option_id);
CREATE INDEX IF NOT EXISTS idx_option_deps_source ON option_dependencies(source_version_id);
CREATE INDEX IF NOT EXISTS idx_option_deps_assessment ON option_dependencies(evidence_assessment_id);
CREATE INDEX IF NOT EXISTS idx_option_deps_target ON option_dependencies(depends_on_option_id);
CREATE INDEX IF NOT EXISTS idx_option_tasks_option ON preparation_tasks(option_id);
CREATE INDEX IF NOT EXISTS idx_option_threats_option ON optionality_threats(option_id);
CREATE INDEX IF NOT EXISTS idx_option_reviews_option ON option_review_events(option_id);
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
                # Idempotent quarantine across repeated wrong-case deliveries.
                existing = self.db.execute(
                    "SELECT id FROM quarantine WHERE target_case_id=? AND sha256=? ORDER BY id LIMIT 1",
                    (case_id, digest)).fetchone()
                if existing:
                    return {"result": "quarantined", "reason": "patient_mismatch",
                            "quarantine_id": existing["id"], "duplicate": True}
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
            invalidated_options = []
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
                # OI-021, same transaction: only options in THIS case that
                # cite the superseded version or a stale snapshot reopen.
                invalidated_options = self._invalidate_options(
                    snapshot_ids=set(invalidated), source_version_ids={previous["id"]},
                    evidence_version_ids=set())
                if invalidated_options:
                    self._event(case_id, "option_review_reopened",
                                source_version_id=previous["id"],
                                invalidated_options=invalidated_options)
            self._event(case_id, "source_imported", document_id=report.document_id,
                        version=version, source_id=source_id, amends_id=previous["id"] if previous else None,
                        invalidated_snapshots=invalidated, invalidated_options=invalidated_options)
            return {"result": "imported", "source_id": source_id, "version": version,
                    "invalidated_snapshots": invalidated, "invalidated_options": invalidated_options}


    # ---- OI-021: reviewed option/dependency view (derived projection) ----
    OPTION_EPISTEMIC = frozenset({"supported", "contradicted", "unsupported", "unknown"})
    OPTION_OPERATIONAL = frozenset({"proposed", "reviewed", "held", "rejected", "withdrawn", "expired"})
    OPTION_REVIEW_ACTIONS = frozenset({"approve", "reject", "abstain", "reconfirm", "withdraw", "expire"})
    TASK_STATUSES = frozenset({"not_started", "in_progress", "done", "blocked", "cancelled"})
    THREAT_KINDS = frozenset({"expiring_window", "dependency_loss", "evidence_withdrawal", "other"})
    # Imperative clinical language is rejected at proposal time. This is a
    # narrow guard, not a clinical-language classifier: the disclaimer on
    # every view states what the view is not, and human review remains the
    # gate. The guard covers the fields a proposal author controls.
    _CLINICAL_LANGUAGE = re.compile(
        r"\b(recommend\w*|prescrib\w*|eligible)\b"
        r"|\bshould\s+(receive|undergo|get|start)\b"
        r"|\bmust\s+(receive|undergo)\b"
        r"|\border\s+(this|the)\s+(treatment|therapy|procedure)\b"
        r"|\bstart\s+treatment\b", re.IGNORECASE)

    @staticmethod
    def _check_no_clinical_language(text: str, field: str) -> str:
        if not isinstance(text, str) or not text.strip():
            raise InvalidInput(f"{field} is required")
        if CaseStore._CLINICAL_LANGUAGE.search(text):
            raise InvalidInput(f"{field} must not state a clinical recommendation, order, or eligibility claim")
        return text.strip()

    @staticmethod
    def _check_lead(value: object) -> int | None:
        if value is None:
            return None
        if type(value) is not int or not 0 <= value <= 3650:
            raise InvalidInput("Lead time must be an integer of 0–3650 days or absent")
        return value

    @staticmethod
    def _check_sourced_date(date_value: object, basis: object, anchor: object, field: str) -> tuple[str | None, str, str]:
        """A date is only as good as its attested anchor in this demo.

        Sourced means: a human supplied a date AND an anchor text (10–300
        chars) AND, for dependencies, the edge itself is a source or evidence
        edge (enforced by the caller). The anchor is a human attestation, not
        verified citation — the same honesty level as existing assessments.
        Unknown means: no date, full stop.
        """
        if basis not in ("sourced", "unknown"):
            raise InvalidInput(f"{field} basis must be 'sourced' or 'unknown'")
        if date_value is None:
            if basis != "unknown":
                raise InvalidInput(f"{field} with no date must use basis 'unknown'")
            anchor_text = anchor if isinstance(anchor, str) else ""
            if len(anchor_text) > 300:
                raise InvalidInput(f"{field} anchor must be at most 300 characters")
            return None, "unknown", anchor_text.strip()
        if basis != "sourced":
            raise InvalidInput(f"{field} with a date must use basis 'sourced'")
        anchor_text = CaseStore._check_no_clinical_language(anchor, f"{field} anchor")
        if not 10 <= len(anchor_text) <= 300:
            raise InvalidInput(f"{field} anchor must have 10–300 characters")
        return valid_date(date_value), "sourced", anchor_text

    def _option_row(self, case_id: str, option_id: int) -> sqlite3.Row:
        if type(option_id) is not int or option_id < 1:
            raise InvalidInput("Invalid option ID")
        row = self.db.execute("SELECT * FROM options WHERE id=? AND case_id=?", (option_id, case_id)).fetchone()
        if not row:
            raise InvalidInput("Option not in this case")
        return row

    def _option_contradicted(self, option_id: int) -> bool:
        direct = self.db.execute("SELECT epistemic_status FROM options WHERE id=?", (option_id,)).fetchone()
        if direct and direct["epistemic_status"] == "contradicted":
            return True
        row = self.db.execute("""SELECT 1 FROM option_dependencies d
            JOIN evidence_assessments a ON a.id=d.evidence_assessment_id
            WHERE d.option_id=? AND a.relation='contradicts' LIMIT 1""", (option_id,)).fetchone()
        return row is not None

    def _invalidate_options(self, *, snapshot_ids: set[int], source_version_ids: set[int],
                            evidence_version_ids: set[int],
                            option_ids: set[int] | None = None) -> list[int]:
        """Mark ONLY dependent option proposals needs_review, transitively
        through option->option edges. Caller must own a write transaction.
        Returns the invalidated option IDs. Other cases/options untouched,
        except evidence invalidation, which (like existing snapshot evidence
        invalidation) is global because evidence versions are shared."""
        seeded: set[int] = set(option_ids or ())
        if snapshot_ids:
            marks = ",".join("?" for _ in snapshot_ids)
            seeded.update(r[0] for r in self.db.execute(
                f"SELECT id FROM options WHERE snapshot_id IN ({marks}) AND review_state='current'",
                sorted(snapshot_ids)).fetchall())
        if source_version_ids:
            marks = ",".join("?" for _ in source_version_ids)
            seeded.update(r[0] for r in self.db.execute(
                f"""SELECT DISTINCT option_id FROM option_dependencies
                WHERE source_version_id IN ({marks})""", sorted(source_version_ids)).fetchall())
        if evidence_version_ids:
            marks = ",".join("?" for _ in evidence_version_ids)
            seeded.update(r[0] for r in self.db.execute(
                f"""SELECT DISTINCT d.option_id FROM option_dependencies d
                JOIN evidence_assessments a ON a.id=d.evidence_assessment_id
                WHERE a.evidence_version_id IN ({marks})""", sorted(evidence_version_ids)).fetchall())
        # Transitive closure over option->option dependencies.
        changed = set(seeded)
        frontier = set(seeded)
        while frontier:
            marks = ",".join("?" for _ in frontier)
            nxt = {r[0] for r in self.db.execute(
                f"""SELECT DISTINCT option_id FROM option_dependencies
                WHERE depends_on_option_id IN ({marks})""", sorted(frontier)).fetchall()}
            nxt -= changed
            changed |= nxt
            frontier = nxt
        invalidated = sorted(changed)
        if invalidated:
            marks = ",".join("?" for _ in invalidated)
            self.db.execute(f"UPDATE options SET review_state='needs_review' WHERE id IN ({marks}) AND review_state='current'",
                            invalidated)
        return invalidated

    def _reopen_option_dependents(self, case_id: str, option_id: int, reason: str,
                                  *, include_reviewed_self: bool = True) -> None:
        """Preserve endorsements as history, but invalidate their changed basis.

        The caller owns a write transaction. Unreviewed proposals can still
        be assembled without requiring reconfirmation after every form field.
        Downstream options are reconsidered even when the changed parent has
        not itself been endorsed. No unrelated case or snapshot is touched.
        """
        seeds = {r[0] for r in self.db.execute(
            "SELECT option_id FROM option_dependencies WHERE depends_on_option_id=?",
            (option_id,)).fetchall()}
        option = self._option_row(case_id, option_id)
        if include_reviewed_self:
            # Assembly of unreviewed drafts is not a stale-review event.
            # Traverse through them to reach any endorsed downstream basis.
            candidates, frontier = set(seeds), set(seeds)
            while frontier:
                marks = ",".join("?" for _ in frontier)
                following = {r[0] for r in self.db.execute(
                    f"SELECT option_id FROM option_dependencies WHERE depends_on_option_id IN ({marks})",
                    sorted(frontier)).fetchall()} - candidates
                candidates |= following
                frontier = following
            seeds = {oid for oid in candidates
                     if self._option_row(case_id, oid)["operational_status"] == "reviewed"}
            if option["operational_status"] == "reviewed":
                seeds.add(option_id)
        changed = self._invalidate_options(snapshot_ids=set(), source_version_ids=set(),
                                            evidence_version_ids=set(), option_ids=seeds)
        if changed:
            self._event(case_id, "option_review_reopened", option_id=option_id,
                        reason=reason, invalidated_options=changed)

    def _require_current_option_dependencies(self, case_id: str, option_id: int) -> None:
        """Reject endorsement against stale, withdrawn or terminal premises.

        Changing the snapshot pointer does not replace old dependency edges.
        An amended premise needs a new proposal with explicit current inputs;
        the old option and its reason for review remain inspectable.
        """
        pending, seen = [option_id], set()
        while pending:
            current = pending.pop()
            if current in seen:
                continue
            seen.add(current)
            for dep in self.db.execute("SELECT * FROM option_dependencies WHERE option_id=?",
                                       (current,)).fetchall():
                if dep["kind"] == "source":
                    row = self.db.execute("SELECT state FROM source_versions WHERE id=? AND case_id=?",
                                          (dep["source_version_id"], case_id)).fetchone()
                    if not row or row["state"] != "current":
                        raise InvalidInput("Source dependency is not current; preserve this option and create a new proposal")
                elif dep["kind"] == "evidence_assessment":
                    row = self.db.execute("""SELECT v.state FROM evidence_assessments a
                        JOIN evidence_versions v ON v.id=a.evidence_version_id
                        WHERE a.id=? AND a.case_id=?""", (dep["evidence_assessment_id"], case_id)).fetchone()
                    if not row or row["state"] != "current":
                        raise InvalidInput("Evidence dependency is not current; preserve this option and create a new proposal")
                elif dep["kind"] == "option":
                    target = self._option_row(case_id, dep["depends_on_option_id"])
                    if (target["review_state"] != "current" or
                        target["operational_status"] in ("rejected", "withdrawn", "expired") or
                        self._option_contradicted(target["id"])):
                        raise InvalidInput("Prerequisite option is not current or is held; review its basis first")
                    pending.append(target["id"])

    def create_option(self, case_id: str, snapshot_id: int, label: str, description: str,
                      epistemic_status: str) -> int:
        self._case(case_id)
        label = self._check_no_clinical_language(label, "Option label")
        if not 1 <= len(label) <= 120:
            raise InvalidInput("Option label must have 1–120 characters")
        description = self._check_no_clinical_language(description, "Option description")
        if not 10 <= len(description) <= 1000:
            raise InvalidInput("Option description must have 10–1000 characters")
        if epistemic_status not in self.OPTION_EPISTEMIC:
            raise InvalidInput("Invalid epistemic status")
        with self.db:
            self.db.execute("BEGIN IMMEDIATE")
            snap = self.db.execute("SELECT state FROM snapshots WHERE id=? AND case_id=?",
                                   (snapshot_id, case_id)).fetchone()
            if not snap:
                raise InvalidInput("Investigation snapshot not in this case")
            if snap["state"] == "stale":
                raise InvalidInput("Options cannot be proposed on a stale investigation snapshot")
            cur = self.db.execute("""INSERT INTO options
                (case_id,snapshot_id,label,description,epistemic_status,operational_status,review_state,created_at)
                VALUES (?,?,?,?,?,'proposed','current',?)""",
                (case_id, snapshot_id, label, description, epistemic_status, now_utc()))
            self._event(case_id, "option_created", option_id=cur.lastrowid, snapshot_id=snapshot_id)
            return int(cur.lastrowid)

    def add_option_dependency(self, case_id: str, option_id: int, kind: str, *,
                              source_version_id: int | None = None,
                              evidence_assessment_id: int | None = None,
                              preparation_task_id: int | None = None,
                              depends_on_option_id: int | None = None,
                              lead_time_days: int | None = None,
                              deadline_date: str | None = None,
                              deadline_basis: str = "unknown",
                              anchor: str = "") -> int:
        self._case(case_id)
        if kind not in ("source", "evidence_assessment", "preparation_task", "option"):
            raise InvalidInput("Invalid dependency kind")
        targets = [x for x in (source_version_id, evidence_assessment_id,
                               preparation_task_id, depends_on_option_id) if x is not None]
        if len(targets) != 1:
            raise InvalidInput("Exactly one dependency target is required")
        expected = {"source": source_version_id, "evidence_assessment": evidence_assessment_id,
                    "preparation_task": preparation_task_id, "option": depends_on_option_id}[kind]
        if expected is None or type(expected) is not int or expected < 1:
            raise InvalidInput("Dependency target does not match its kind")
        lead = self._check_lead(lead_time_days)
        if kind not in ("source", "evidence_assessment") and deadline_date is not None:
            raise InvalidInput("A sourced deadline date is only allowed on a source or evidence dependency")
        date_value, basis, anchor_text = self._check_sourced_date(
            deadline_date, deadline_basis, anchor, "Dependency deadline")
        with self.db:
            self.db.execute("BEGIN IMMEDIATE")
            option = self._option_row(case_id, option_id)
            if option["operational_status"] in ("rejected", "withdrawn", "expired"):
                raise InvalidInput("Preserve the terminal option; create a new proposal for new dependencies")
            if kind == "source":
                source = self.db.execute("SELECT state FROM source_versions WHERE id=? AND case_id=?",
                                         (source_version_id, case_id)).fetchone()
                if not source:
                    raise InvalidInput("Source version not in this case")
                if source["state"] != "current":
                    raise InvalidInput("A new source dependency must be current")
            elif kind == "evidence_assessment":
                assessment = self.db.execute("""SELECT v.state FROM evidence_assessments a
                    JOIN evidence_versions v ON v.id=a.evidence_version_id
                    WHERE a.id=? AND a.case_id=?""", (evidence_assessment_id, case_id)).fetchone()
                if not assessment:
                    raise InvalidInput("Evidence assessment not in this case")
                if assessment["state"] != "current":
                    raise InvalidInput("A new evidence dependency must be current")
            elif kind == "preparation_task":
                task = self.db.execute("SELECT option_id FROM preparation_tasks WHERE id=? AND case_id=?",
                                       (preparation_task_id, case_id)).fetchone()
                if not task or task["option_id"] != option_id:
                    raise InvalidInput("Preparation task must belong to this option")
            else:
                target = self.db.execute("SELECT case_id,operational_status,review_state FROM options WHERE id=?",
                                         (depends_on_option_id,)).fetchone()
                if not target or target["case_id"] != case_id:
                    raise InvalidInput("Dependent option not in this case")
                if depends_on_option_id == option_id:
                    raise InvalidInput("An option cannot depend on itself")
                if target["operational_status"] in ("rejected", "withdrawn", "expired"):
                    raise InvalidInput("An option cannot depend on a rejected, withdrawn, or expired option")
                if target["review_state"] != "current" or self._option_contradicted(depends_on_option_id):
                    raise InvalidInput("Dependent option is not current or is held")
                self._require_current_option_dependencies(case_id, depends_on_option_id)
                # Cycle check inside the immediate transaction.
                seen, frontier = set(), {depends_on_option_id}
                while frontier:
                    if option_id in frontier:
                        raise InvalidInput("Option dependency would create a cycle")
                    seen |= frontier
                    marks = ",".join("?" for _ in frontier)
                    frontier = {r[0] for r in self.db.execute(
                        f"""SELECT DISTINCT depends_on_option_id FROM option_dependencies
                        WHERE option_id IN ({marks}) AND depends_on_option_id IS NOT NULL""",
                        sorted(frontier)).fetchall()} - seen
            cur = self.db.execute("""INSERT INTO option_dependencies
                (option_id,kind,source_version_id,evidence_assessment_id,preparation_task_id,
                 depends_on_option_id,lead_time_days,deadline_date,deadline_basis,anchor,created_at)
                VALUES (?,?,?,?,?,?,?,?,?,?,?)""",
                (option_id, kind, source_version_id, evidence_assessment_id, preparation_task_id,
                 depends_on_option_id, lead, date_value, basis, anchor_text, now_utc()))
            self._event(case_id, "option_dependency_added", option_id=option_id,
                        dependency_id=cur.lastrowid, dependency_kind=kind)
            self._reopen_option_dependents(case_id, option_id, "dependency_added")
            return int(cur.lastrowid)

    def add_preparation_task(self, case_id: str, option_id: int, label: str,
                             owner_label: str, lead_time_days: int | None = None) -> int:
        self._case(case_id)
        label = self._check_no_clinical_language(label, "Preparation task label")
        if not 1 <= len(label) <= 120:
            raise InvalidInput("Preparation task label must have 1–120 characters")
        if not isinstance(owner_label, str) or not 2 <= len(owner_label.strip()) <= 80:
            raise InvalidInput("Preparation task requires a human owner label")
        lead = self._check_lead(lead_time_days)
        with self.db:
            self.db.execute("BEGIN IMMEDIATE")
            self._option_row(case_id, option_id)
            cur = self.db.execute("""INSERT INTO preparation_tasks
                (case_id,option_id,label,owner_label,status,lead_time_days,created_at)
                VALUES (?,?,?,?,'not_started',?,?)""",
                (case_id, option_id, label, owner_label.strip(), lead, now_utc()))
            self._event(case_id, "preparation_task_created", option_id=option_id, task_id=cur.lastrowid)
            self._reopen_option_dependents(case_id, option_id, "preparation_task_added")
            return int(cur.lastrowid)

    def set_preparation_task_status(self, case_id: str, task_id: int, status: str) -> None:
        self._case(case_id)
        if status not in self.TASK_STATUSES:
            raise InvalidInput("Invalid preparation task status")
        with self.db:
            self.db.execute("BEGIN IMMEDIATE")
            row = self.db.execute("SELECT option_id,status FROM preparation_tasks WHERE id=? AND case_id=?",
                                  (task_id, case_id)).fetchone()
            if not row:
                raise InvalidInput("Preparation task not in this case")
            if row["status"] == status:
                return
            self.db.execute("UPDATE preparation_tasks SET status=? WHERE id=?", (status, task_id))
            self._event(case_id, "preparation_task_status_changed", option_id=row["option_id"],
                        task_id=task_id, previous_status=row["status"], status=status)
            self._reopen_option_dependents(case_id, row["option_id"], "preparation_task_changed")

    def add_optionality_threat(self, case_id: str, option_id: int, kind: str, description: str,
                               threat_date: str | None = None, threat_basis: str = "unknown",
                               anchor: str = "") -> int:
        self._case(case_id)
        if kind not in self.THREAT_KINDS:
            raise InvalidInput("Invalid optionality threat kind")
        description = self._check_no_clinical_language(description, "Threat description")
        if not 10 <= len(description) <= 500:
            raise InvalidInput("Threat description must have 10–500 characters")
        date_value, basis, anchor_text = self._check_sourced_date(
            threat_date, threat_basis, anchor, "Threat date")
        with self.db:
            self.db.execute("BEGIN IMMEDIATE")
            self._option_row(case_id, option_id)
            cur = self.db.execute("""INSERT INTO optionality_threats
                (option_id,kind,description,threat_date,threat_basis,anchor,created_at)
                VALUES (?,?,?,?,?,?,?)""",
                (option_id, kind, description, date_value, basis, anchor_text, now_utc()))
            self._event(case_id, "optionality_threat_added", option_id=option_id, threat_id=cur.lastrowid)
            self._reopen_option_dependents(case_id, option_id, "threat_added")
            return int(cur.lastrowid)

    def review_option(self, case_id: str, option_id: int, reviewer_label: str, action: str,
                      scope: str, snapshot_id: int | None = None) -> dict:
        """Record one reviewer action. Approve is re-checked inside the
        immediate transaction: contradicted or needs_review proposals cannot
        slip through on a stale read. A failed approve records nothing, the
        same as the existing snapshot-review pattern; the held state remains
        visible in the derived view."""
        self._case(case_id)
        if action not in self.OPTION_REVIEW_ACTIONS:
            raise InvalidInput("Invalid option review action")
        if not isinstance(reviewer_label, str) or not 2 <= len(reviewer_label.strip()) <= 80:
            raise InvalidInput("Provide a reviewer label")
        scope = self._check_no_clinical_language(scope, "Review scope")
        if not 10 <= len(scope) <= 300:
            raise InvalidInput("Review scope must have 10–300 characters")
        with self.db:
            self.db.execute("BEGIN IMMEDIATE")
            option = self._option_row(case_id, option_id)
            operational = option["operational_status"]
            if operational in ("withdrawn", "expired") and action != "abstain":
                raise InvalidInput("A withdrawn or expired option cannot change state further")
            if operational == "rejected" and action == "reconfirm":
                raise InvalidInput("A rejected option remains historical; create a new proposal to reconsider it")
            if action in ("approve", "reconfirm"):
                self._require_current_option_dependencies(case_id, option_id)
            if action == "approve":
                if option["review_state"] != "current":
                    raise InvalidInput("Option review is not current; reconfirm it after amendment before approval")
                snap = self.db.execute("SELECT state FROM snapshots WHERE id=?",
                                       (option["snapshot_id"],)).fetchone()
                if not snap or snap["state"] == "stale":
                    raise InvalidInput("Option review is not current; reconfirm it after amendment before approval")
                if self._option_contradicted(option_id):
                    raise InvalidInput("A contradicted option cannot be approved; record a rejection or abstention")
                if operational == "reviewed":
                    raise InvalidInput("Option is already reviewed")
                if operational in ("rejected",):
                    raise InvalidInput("A rejected option cannot be approved without a new proposal")
                self.db.execute("UPDATE options SET operational_status='reviewed' WHERE id=?", (option_id,))
                target_snapshot = option["snapshot_id"]
            elif action == "reject":
                if operational == "reviewed":
                    raise InvalidInput("A reviewed option cannot be rejected without a new proposal")
                self.db.execute("UPDATE options SET operational_status='rejected' WHERE id=?", (option_id,))
                target_snapshot = option["snapshot_id"]
            elif action == "abstain":
                target_snapshot = option["snapshot_id"]
            elif action == "reconfirm":
                if option["review_state"] != "needs_review":
                    raise InvalidInput("Only an option awaiting re-review can be reconfirmed")
                if snapshot_id is None or type(snapshot_id) is not int:
                    raise InvalidInput("Reconfirmation requires a replacement investigation snapshot")
                snap = self.db.execute("SELECT state FROM snapshots WHERE id=? AND case_id=?",
                                       (snapshot_id, case_id)).fetchone()
                if not snap or snap["state"] == "stale":
                    raise InvalidInput("Replacement snapshot is missing or stale")
                if self._option_contradicted(option_id):
                    raise InvalidInput("A contradicted option cannot be reconfirmed; record a rejection or abstention")
                self.db.execute("""UPDATE options SET snapshot_id=?,review_state='current',
                    operational_status='proposed' WHERE id=?""", (snapshot_id, option_id))
                target_snapshot = snapshot_id
            elif action == "withdraw":
                if operational == "withdrawn":
                    raise InvalidInput("Option is already withdrawn")
                self.db.execute("UPDATE options SET operational_status='withdrawn' WHERE id=?", (option_id,))
                target_snapshot = option["snapshot_id"]
            else:  # expire
                if operational == "expired":
                    raise InvalidInput("Option is already expired")
                self.db.execute("UPDATE options SET operational_status='expired' WHERE id=?", (option_id,))
                target_snapshot = option["snapshot_id"]
            timestamp = now_utc()
            cur = self.db.execute("""INSERT INTO option_review_events
                (option_id,reviewer_label,action,scope,snapshot_id,noted_at)
                VALUES (?,?,?,?,?,?)""",
                (option_id, reviewer_label.strip(), action, scope, target_snapshot, timestamp))
            self._event(case_id, "option_reviewed", option_id=option_id, action=action,
                        review_event_id=cur.lastrowid)
            if action in ("reject", "withdraw", "expire", "reconfirm"):
                self._reopen_option_dependents(case_id, option_id, "prerequisite_" + action,
                                               include_reviewed_self=False)
            return {"result": action, "review_event_id": int(cur.lastrowid)}

    def _potential_discussion_deadline(self, option_id: int) -> dict:
        """Conditional planning arithmetic, not a clinical or verified date.

        Follow every required path through the acyclic dependency graph.
        Revisit shared nodes when reached with a longer lead. Unknown, blocked,
        cancelled or stale prerequisites cause abstention rather than treating
        missing information as zero. An absent edge-level delay adds no extra
        annotation; an explicitly registered task with no duration is unknown.
        """
        best: tuple[str, list[str]] | None = None
        longest: dict[int, int] = {}
        unresolved: set[str] = set()

        def walk(current_id: int, accumulated_lead: int, path: list[int]) -> None:
            nonlocal best
            if current_id in path or len(path) >= 200:
                unresolved.add("cyclic or overlong dependency chain")
                return
            if accumulated_lead <= longest.get(current_id, -1):
                return
            longest[current_id] = accumulated_lead
            current = self.db.execute("""SELECT o.*,s.state AS snapshot_state FROM options o
                JOIN snapshots s ON s.id=o.snapshot_id WHERE o.id=?""", (current_id,)).fetchone()
            if (not current or current["review_state"] != "current" or
                current["snapshot_state"] == "stale" or
                current["operational_status"] in ("rejected", "withdrawn", "expired") or
                self._option_contradicted(current_id)):
                unresolved.add("prerequisite requires review or is unavailable")
                return
            path = path + [current_id]
            deps = self.db.execute("SELECT * FROM option_dependencies WHERE option_id=? ORDER BY id",
                                   (current_id,)).fetchall()
            prep_lead, seen_tasks = 0, set()
            for dep in deps:
                if dep["kind"] != "preparation_task" or dep["preparation_task_id"] in seen_tasks:
                    continue
                seen_tasks.add(dep["preparation_task_id"])
                task = self.db.execute("SELECT status,lead_time_days FROM preparation_tasks WHERE id=?",
                                       (dep["preparation_task_id"],)).fetchone()
                if not task or task["status"] in ("blocked", "cancelled"):
                    unresolved.add("preparation is missing, blocked or cancelled")
                elif task["status"] != "done":
                    if task["lead_time_days"] is None:
                        unresolved.add("preparation duration is unknown")
                    else:
                        prep_lead += int(task["lead_time_days"])
            for dep in deps:
                edge_lead = int(dep["lead_time_days"]) if dep["lead_time_days"] is not None else 0
                if dep["kind"] == "option" and dep["depends_on_option_id"] is not None:
                    walk(int(dep["depends_on_option_id"]),
                         accumulated_lead + prep_lead + edge_lead, path)
                elif dep["kind"] in ("source", "evidence_assessment"):
                    if dep["kind"] == "source":
                        premise = self.db.execute("SELECT state FROM source_versions WHERE id=?",
                                                  (dep["source_version_id"],)).fetchone()
                    else:
                        premise = self.db.execute("""SELECT v.state FROM evidence_assessments a
                            JOIN evidence_versions v ON v.id=a.evidence_version_id WHERE a.id=?""",
                            (dep["evidence_assessment_id"],)).fetchone()
                    if not premise or premise["state"] != "current":
                        unresolved.add("source or evidence premise is not current")
                        continue
                    if not dep["deadline_date"]:
                        continue
                    try:
                        effective = (date.fromisoformat(dep["deadline_date"])
                                     - timedelta(days=accumulated_lead + prep_lead + edge_lead)).isoformat()
                    except (ValueError, OverflowError):
                        unresolved.add("date calculation is outside the supported range")
                        continue
                    label_path = " → ".join([f"option #{oid}" for oid in path] +
                                            [f"dependency #{dep['id']}"])
                    if best is None or effective < best[0]:
                        best = (effective, [label_path])
        walk(option_id, 0, [])
        if unresolved or best is None:
            reasons = sorted(unresolved) or ["no sourced deadline in the dependency chain"]
            return {"date": None, "basis": "unknown",
                    "label": "Potential discussion deadline: unknown — " + "; ".join(reasons) +
                             ". This is not a clinical deadline.",
                    "path": [], "unresolved": reasons}
        return {"date": best[0], "basis": "sourced",
                "label": "Potential discussion deadline (not a clinical deadline): " + best[0],
                "path": best[1], "unresolved": []}

    def option_view(self, case_id: str, snapshot_id: int | None = None) -> dict:
        """Current state with preserved proposal/review associations.

        A snapshot filter includes original proposals and subsequent review
        associations, so reconfirmation cannot hide an option from its origin.
        This is NOT as-known-at replay: statuses, dependencies and tasks are
        current. The response explicitly declares that boundary. A future
        time-frozen replay contract must be separately implemented and tested.
        """
        self._case(case_id)
        if snapshot_id is not None:
            if type(snapshot_id) is not int or not self.db.execute(
                    "SELECT 1 FROM snapshots WHERE id=? AND case_id=?", (snapshot_id, case_id)).fetchone():
                raise InvalidInput("Investigation snapshot not in this case")
        # Original association is already durable in the existing event ledger.
        # Do not introduce another source of truth or infer it from current state.
        origins: dict[int, int] = {}
        for event in self.db.execute("""SELECT details FROM events
            WHERE case_id=? AND kind='option_created' ORDER BY id""", (case_id,)).fetchall():
            details = json.loads(event["details"])
            origins.setdefault(int(details["option_id"]), int(details["snapshot_id"]))
        options = []
        for option in self.db.execute("SELECT * FROM options WHERE case_id=? ORDER BY id", (case_id,)).fetchall():
            option_id = int(option["id"])
            reviews = self._dicts(self.db.execute(
                "SELECT * FROM option_review_events WHERE option_id=? ORDER BY id", (option_id,)).fetchall())
            associations = {int(option["snapshot_id"])}
            if option_id in origins:
                associations.add(origins[option_id])
            associations.update(int(r["snapshot_id"]) for r in reviews if r["snapshot_id"] is not None)
            if snapshot_id is not None and snapshot_id not in associations:
                continue
            snap = self.db.execute("SELECT state FROM snapshots WHERE id=?",
                                   (option["snapshot_id"],)).fetchone()
            deps = []
            for dep in self.db.execute("SELECT * FROM option_dependencies WHERE option_id=? ORDER BY id",
                                       (option_id,)).fetchall():
                target = ""
                if dep["kind"] == "source" and dep["source_version_id"] is not None:
                    src = self.db.execute("SELECT document_id,version,state FROM source_versions WHERE id=?",
                                          (dep["source_version_id"],)).fetchone()
                    target = f"{src['document_id']}@{src['version']} ({src['state']})" if src else "missing source"
                elif dep["kind"] == "evidence_assessment" and dep["evidence_assessment_id"] is not None:
                    asm = self.db.execute("""SELECT a.relation,v.evidence_key,v.version,v.state FROM evidence_assessments a
                        JOIN evidence_versions v ON v.id=a.evidence_version_id WHERE a.id=?""",
                        (dep["evidence_assessment_id"],)).fetchone()
                    target = (f"{asm['evidence_key']}@{asm['version']} ({asm['state']}) · {asm['relation']}"
                              if asm else "missing assessment")
                elif dep["kind"] == "preparation_task" and dep["preparation_task_id"] is not None:
                    task = self.db.execute("SELECT label,status FROM preparation_tasks WHERE id=?",
                                           (dep["preparation_task_id"],)).fetchone()
                    target = f"{task['label']} ({task['status']})" if task else "missing task"
                elif dep["kind"] == "option" and dep["depends_on_option_id"] is not None:
                    other = self.db.execute("SELECT label,operational_status FROM options WHERE id=?",
                                            (dep["depends_on_option_id"],)).fetchone()
                    target = f"{other['label']} ({other['operational_status']})" if other else "missing option"
                deps.append({**dict(dep), "target": target})
            contradicted = option["epistemic_status"] == "contradicted" or self._option_contradicted(option_id)
            derived_epistemic = "contradicted" if contradicted else option["epistemic_status"]
            display_operational = option["operational_status"]
            if contradicted and display_operational in ("proposed", "reviewed"):
                display_operational = "held"
            options.append({
                **dict(option),
                "snapshot_state": snap["state"] if snap else "missing",
                "derived_epistemic_status": derived_epistemic,
                "display_operational_status": display_operational,
                "dependencies": deps,
                "preparation_tasks": self._dicts(self.db.execute(
                    "SELECT * FROM preparation_tasks WHERE option_id=? ORDER BY id", (option_id,)).fetchall()),
                "threats": self._dicts(self.db.execute(
                    "SELECT * FROM optionality_threats WHERE option_id=? ORDER BY id", (option_id,)).fetchall()),
                "review_events": reviews,
                "proposal_snapshot_id": origins.get(option_id),
                "associated_snapshot_ids": sorted(associations),
                "potential_discussion_deadline": self._potential_discussion_deadline(option_id),
            })
        return {
            "case_id": case_id,
            # Deprecated legacy label: never claim time-travel from a filter.
            "as_known_at_snapshot_id": None,
            "snapshot_filter_id": snapshot_id,
            "historical_replay_supported": False,
            "projection_mode": "current_state_with_review_history",
            "disclaimer": ("For discussion only. This view states no clinical eligibility, safety, or next step. "
                           "A potential discussion deadline is not a clinical deadline. "
                           "Snapshot filtering shows current state and recorded associations, not as-known-at replay."),
            "options": options,
        }

    def _invalidate_evidence_version(self, evidence_version_id: int, *, reason: str) -> tuple[list[int], list[int]]:
        """Invalidate dependent snapshots across ALL synthetic cases, retaining history.

        Caller must own a write transaction. Only snapshots citing this exact
        immutable evidence version are affected.
        """
        rows = self.db.execute("""SELECT DISTINCT s.id,s.case_id,s.question_id
            FROM snapshots s JOIN snapshot_evidence se ON se.snapshot_id=s.id
            JOIN evidence_assessments a ON a.id=se.assessment_id
            WHERE a.evidence_version_id=? AND s.state!='stale'""",
            (evidence_version_id,)).fetchall()
        invalidated = [int(row["id"]) for row in rows]
        if invalidated:
            ids = ",".join("?" for _ in invalidated)
            self.db.execute(f"UPDATE snapshots SET state='stale' WHERE id IN ({ids})", invalidated)
            self.db.execute(f"""UPDATE questions SET state='open' WHERE id IN
                (SELECT DISTINCT question_id FROM snapshots WHERE id IN ({ids}))""", invalidated)
            affected = {str(row["case_id"]) for row in rows}
            for case_id in sorted(affected):
                changed = [int(row["id"]) for row in rows if row["case_id"] == case_id]
                self._event(case_id, "evidence_invalidated",
                            evidence_version_id=evidence_version_id,
                            reason=reason, invalidated_snapshots=changed)
        # OI-021: same transaction, dependent options only. Evidence versions
        # are shared, so this fan-out is global exactly like the snapshot
        # fan-out above; case/source amendments stay case-scoped.
        invalidated_options = self._invalidate_options(
            snapshot_ids=set(invalidated), source_version_ids=set(),
            evidence_version_ids={evidence_version_id})
        if invalidated_options:
            option_cases = {str(r[0]) for r in self.db.execute(
                "SELECT DISTINCT case_id FROM options WHERE id IN (%s)" %
                ",".join("?" for _ in invalidated_options), invalidated_options).fetchall()}
            for case_id in sorted(option_cases):
                per_case = [oid for oid in invalidated_options if self.db.execute(
                    "SELECT case_id FROM options WHERE id=?", (oid,)).fetchone()["case_id"] == case_id]
                self._event(case_id, "option_review_reopened",
                            evidence_version_id=evidence_version_id, reason=reason,
                            invalidated_options=per_case)
        return invalidated, invalidated_options

    def import_synthetic_evidence(self, raw: bytes) -> dict:
        """Version original fictional research text; no live article import is supported."""
        item = parse_synthetic_evidence(raw)
        digest = hashlib.sha256(raw).hexdigest()
        with self.db:
            self.db.execute("BEGIN IMMEDIATE")
            duplicate = self.db.execute(
                "SELECT id,version FROM evidence_versions WHERE evidence_key=? AND sha256=?",
                (item.evidence_key, digest)).fetchone()
            if duplicate:
                return {"result": "duplicate", "evidence_version_id": duplicate["id"],
                        "version": duplicate["version"], "invalidated_snapshots": []}
            previous = self.db.execute("""SELECT id,version,state FROM evidence_versions
                WHERE evidence_key=? ORDER BY version DESC LIMIT 1""",
                (item.evidence_key,)).fetchone()
            if previous:
                if previous["state"] != "current":
                    raise InvalidInput("Withdrawn evidence cannot be silently replaced")
                if item.amends != (item.evidence_key, previous["version"]):
                    raise InvalidInput("Changed evidence requires Amends: EVIDENCE-ID@LATEST-VERSION")
            elif item.amends is not None:
                raise InvalidInput("Initial evidence cannot specify Amends")
            version = previous["version"] + 1 if previous else 1
            invalidated: list[int] = []
            invalidated_options: list[int] = []
            if previous:
                self.db.execute("UPDATE evidence_versions SET state='superseded' WHERE id=?", (previous["id"],))
                self.db.execute("INSERT INTO evidence_changes (evidence_version_id,kind,reason,recorded_at) VALUES (?,'amended',?,?)",
                                (previous["id"], "Explicit synthetic source version replacement", now_utc()))
                invalidated, invalidated_options = self._invalidate_evidence_version(previous["id"], reason="amendment")
            cur = self.db.execute("""INSERT INTO evidence_versions
                (evidence_key,version,sha256,raw,title,issued_at,received_at,
                 statement,statement_line,rights,state,previous_id)
                VALUES (?,?,?,?,?,?,?,?,?,'original-synthetic','current',?)""",
                (item.evidence_key, version, digest, raw, item.title, item.issued_at,
                 now_utc(), item.statement, item.statement_line,
                 previous["id"] if previous else None))
            return {"result": "imported", "evidence_version_id": int(cur.lastrowid),
                    "version": version, "invalidated_snapshots": invalidated,
                    "invalidated_options": invalidated_options}

    def withdraw_synthetic_evidence(self, evidence_version_id: int, reason: str) -> dict:
        """Withdraw a CURRENT fictional item; invalidate related drafts everywhere."""
        if type(evidence_version_id) is not int or evidence_version_id < 1:
            raise InvalidInput("Invalid evidence version ID")
        if not isinstance(reason, str) or not 10 <= len(reason.strip()) <= 600:
            raise InvalidInput("Withdrawal requires a 10–600 character reason")
        with self.db:
            self.db.execute("BEGIN IMMEDIATE")
            row = self.db.execute("SELECT state FROM evidence_versions WHERE id=?",
                                  (evidence_version_id,)).fetchone()
            if not row or row["state"] != "current":
                raise InvalidInput("Evidence not current")
            self.db.execute("UPDATE evidence_versions SET state='withdrawn' WHERE id=?",
                            (evidence_version_id,))
            self.db.execute("INSERT INTO evidence_changes (evidence_version_id,kind,reason,recorded_at) VALUES (?,'withdrawn',?,?)",
                            (evidence_version_id, reason.strip(), now_utc()))
            affected, affected_options = self._invalidate_evidence_version(evidence_version_id, reason="withdrawal")
            return {"result": "withdrawn", "invalidated_snapshots": affected,
                    "invalidated_options": affected_options}

    def assess_synthetic_evidence(self, case_id: str, question_id: int,
                                  evidence_version_id: int, relation: str,
                                  applicability: str, rationale: str) -> int:
        """Persist a HUMAN-authored assessment, not validated clinical appraisal."""
        self._case(case_id)
        if type(question_id) is not int or type(evidence_version_id) is not int:
            raise InvalidInput("Question and evidence IDs must be integers")
        if not isinstance(relation, str) or not isinstance(applicability, str) or relation not in EVIDENCE_RELATIONS or applicability not in EVIDENCE_APPLICABILITY:
            raise InvalidInput("Invalid evidence relationship or applicability")
        if relation == "supports" and applicability == "not_applicable":
            raise InvalidInput("An inapplicable source cannot be labelled as supporting this question")
        if not isinstance(rationale, str) or not 15 <= len(rationale.strip()) <= 800:
            raise InvalidInput("Assessment rationale must have 15–800 characters")
        with self.db:
            self.db.execute("BEGIN IMMEDIATE")
            if not self.db.execute("SELECT 1 FROM questions WHERE id=? AND case_id=?",
                                   (question_id, case_id)).fetchone():
                raise InvalidInput("Question not in this case")
            current = self.db.execute("""SELECT 1 FROM evidence_versions WHERE id=?
                AND state='current' AND rights='original-synthetic'""",
                (evidence_version_id,)).fetchone()
            if not current:
                raise InvalidInput("Evidence not current or not permitted for synthetic assessment")
            cur = self.db.execute("""INSERT INTO evidence_assessments
                (case_id,question_id,evidence_version_id,relation,applicability,rationale,created_at)
                VALUES (?,?,?,?,?,?,?)""", (case_id, question_id, evidence_version_id,
                   relation, applicability, rationale.strip(), now_utc()))
            self._event(case_id, "synthetic_evidence_assessed",
                        assessment_id=cur.lastrowid, evidence_version_id=evidence_version_id)
            return int(cur.lastrowid)

    def synthetic_evidence_text(self, evidence_version_id: int) -> str:
        if type(evidence_version_id) is not int or evidence_version_id < 1:
            raise InvalidInput("Invalid evidence version ID")
        row = self.db.execute("SELECT raw FROM evidence_versions WHERE id=?",
                              (evidence_version_id,)).fetchone()
        if not row:
            raise InvalidInput("Evidence version not found")
        return bytes(row["raw"]).decode("utf-8")

    def add_question(self, case_id: str, question: str) -> int:
        self._case(case_id)
        if not isinstance(question, str) or not 5 <= len(question.strip()) <= 500:
            raise InvalidInput("Question must have 5–500 characters")
        with self.db:
            cur = self.db.execute("INSERT INTO questions (case_id,question,state,created_at) VALUES (?,?,?,?)",
                                  (case_id, question.strip(), "open", now_utc()))
            self._event(case_id, "question_created", question_id=cur.lastrowid)
        return int(cur.lastrowid)

    def create_snapshot(self, case_id: str, question_id: int, summary: str, source_ids: list[int],
                        evidence_assessment_ids: list[int] | None = None) -> int:
        self._case(case_id)
        if not isinstance(summary, str) or not 10 <= len(summary.strip()) <= MAX_SUMMARY:
            raise InvalidInput("Draft must have 10–3000 characters")
        if not isinstance(source_ids, list) or not source_ids or any(type(x) is not int for x in source_ids):
            raise InvalidInput("Select one or more current source versions")
        if len(source_ids) != len(set(source_ids)) or len(source_ids) > 50:
            raise InvalidInput("Source IDs must be unique; maximum 50")
        evidence_assessment_ids = [] if evidence_assessment_ids is None else evidence_assessment_ids
        if (not isinstance(evidence_assessment_ids, list) or
            len(evidence_assessment_ids) != len(set(str(x) for x in evidence_assessment_ids)) or
            len(evidence_assessment_ids) > 50 or
            any(type(x) is not int or x < 1 for x in evidence_assessment_ids)):
            raise InvalidInput("Evidence assessment IDs must be unique positive integers; maximum 50")
        with self.db:
            self.db.execute("BEGIN IMMEDIATE")  # Serialize against incoming amendments and evidence changes.
            question = self.db.execute("SELECT id FROM questions WHERE id=? AND case_id=?", (question_id, case_id)).fetchone()
            if not question:
                raise InvalidInput("Question not in this case")
            for sid in source_ids:
                if not self.db.execute("SELECT 1 FROM source_versions WHERE id=? AND case_id=? AND state='current'",
                                       (sid, case_id)).fetchone():
                    raise InvalidInput("Source is missing, superseded, or belongs to another case")
            for aid in evidence_assessment_ids:
                linked = self.db.execute("""SELECT 1 FROM evidence_assessments a
                    JOIN evidence_versions v ON v.id=a.evidence_version_id
                    WHERE a.id=? AND a.case_id=? AND a.question_id=?
                    AND v.state='current' AND v.rights='original-synthetic'""",
                    (aid, case_id, question_id)).fetchone()
                if not linked:
                    raise InvalidInput("Evidence assessment is missing, stale, or outside this question")
            cur = self.db.execute("""INSERT INTO snapshots (case_id,question_id,summary,state,created_at)
                VALUES (?,?,?,'draft',?)""", (case_id, question_id, summary.strip(), now_utc()))
            snapshot_id = int(cur.lastrowid)
            for sid in source_ids:
                self.db.execute("INSERT INTO snapshot_sources VALUES (?,?)", (snapshot_id, sid))
            for aid in evidence_assessment_ids:
                self.db.execute("INSERT INTO snapshot_evidence VALUES (?,?)", (snapshot_id, aid))
            self._event(case_id, "draft_created", snapshot_id=snapshot_id, question_id=question_id,
                        evidence_assessment_ids=evidence_assessment_ids)
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
        # A single read transaction is required across versions, assertions,
        # questions, review state and events. Otherwise concurrent amendments
        # can expose mutually inconsistent case snapshots to the browser.
        with self.db:
            self.db.execute("BEGIN")
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
            for snapshot in snapshot_rows:
                snapshot["evidence_assessment_ids"] = [r[0] for r in self.db.execute(
                    "SELECT assessment_id FROM snapshot_evidence WHERE snapshot_id=? ORDER BY assessment_id",
                    (snapshot["id"],)).fetchall()]
            evidence_rows = self._dicts(self.db.execute("""SELECT id,evidence_key,version,sha256,title,
                issued_at,received_at,statement,statement_line,rights,state,previous_id
                FROM evidence_versions ORDER BY evidence_key,version""").fetchall())
            assessments = self._dicts(self.db.execute("""SELECT a.*,v.evidence_key,v.version,v.state AS evidence_state,
                v.title,v.statement,v.statement_line,v.sha256
                FROM evidence_assessments a JOIN evidence_versions v ON v.id=a.evidence_version_id
                WHERE a.case_id=? ORDER BY a.id DESC""", (case_id,)).fetchall())
            option_projection = self.option_view(case_id)
            return {
                "evidence": evidence_rows,
                "evidence_changes": self._dicts(self.db.execute(
                    "SELECT id,evidence_version_id,kind,reason,recorded_at FROM evidence_changes ORDER BY id DESC").fetchall()),
                "evidence_assessments": assessments,
                "case": dict(self.db.execute("SELECT * FROM cases WHERE case_id=?", (case_id,)).fetchone()),
                "sources": source_rows,
                "assertions": assert_rows,
                "questions": self._dicts(self.db.execute("SELECT * FROM questions WHERE case_id=? ORDER BY id DESC", (case_id,)).fetchall()),
                "snapshots": snapshot_rows,
                # OI-021 derived projection: same ledger, no second state.
                "options": option_projection["options"],
                "option_disclaimer": option_projection["disclaimer"],
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
        # Explicit read transaction keeps status and source/evidence versions
        # consistent if an amendment or withdrawal commits during export.
        with self.db:
            self.db.execute("BEGIN")
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
                raw_text = bytes(source["raw"]).decode("utf-8")
                # Prevent raw input from escaping Markdown source fences.
                longest = max((len(run) for run in re.findall(r"`+", raw_text)), default=0)
                fence = "`" * max(3, longest + 1)
                lines.extend([f"### {source['document_id']}@{source['version']} — {source['state']}", "",
                              f"SHA-256: `{source['sha256']}` | Event: {source['event_date']} | Issued: {source['issued_at']}", "",
                              fence + "text", raw_text, fence, ""])
            evidence = self.db.execute("""SELECT a.*,v.evidence_key,v.version,v.state AS evidence_state,
                v.title,v.sha256,v.raw,v.rights,v.statement_line FROM snapshot_evidence se
                JOIN evidence_assessments a ON a.id=se.assessment_id
                JOIN evidence_versions v ON v.id=a.evidence_version_id
                WHERE se.snapshot_id=? ORDER BY a.id""", (snapshot_id,)).fetchall()
            lines.extend(["## Fictional evidence assessments", ""])
            if not evidence:
                lines.extend(["None included; no external study appraisal performed.", ""])
            for assessment in evidence:
                evidence_text = bytes(assessment["raw"]).decode("utf-8")
                longest = max((len(run) for run in re.findall(r"`+", evidence_text)), default=0)
                fence = "`" * max(3, longest + 1)
                lines.extend([f"### {assessment['evidence_key']}@{assessment['version']}: {assessment['title']}",
                              "", f"Evidence state: {assessment['evidence_state']} | Rights: {assessment['rights']}",
                              f"SHA-256: `{assessment['sha256']}` | Source line: {assessment['statement_line']}",
                              f"Human-assigned relationship: {assessment['relation']} | Applicability: {assessment['applicability']}",
                              "", f"Rationale: {assessment['rationale']}", "", fence + "text",
                              evidence_text, fence, ""])
            lines.extend(["## Limitations", "",
                          "- Evidence items above are fictional, independently authored examples; no real publication, guideline or trial was appraised.",
                          "- Declared synthetic rights are not legal verification of user-supplied content.",
                          "- The reports, questions, and narrative are synthetic and not clinically appraised.",
                          "- An acknowledgment in this demo is not clinician credential verification or a clinical sign-off.",
                          "- Amendments can make previous investigations stale; see the state above.", ""])
            return "\n".join(lines)
