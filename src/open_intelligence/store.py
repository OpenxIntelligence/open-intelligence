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

from .rights import RightsError, check_link_content, normalize_permissions

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

# OI-020: one minimal BiologicalAsset abstraction. Originals have no parent;
# derivatives require a same-case, same-episode parent of an allowed kind.
# Kind and parent are immutable after creation, so lineage can never be
# grafted across cases or episodes by a later write: there is no update path.
ASSET_KINDS = frozenset({"ffpe_block", "fresh_frozen_aliquot", "slide", "digital_wsi", "genomics_data_pointer"})
DERIVATIVE_PARENTS = {
    "slide": frozenset({"ffpe_block"}),
    "digital_wsi": frozenset({"slide"}),
    "genomics_data_pointer": frozenset({"ffpe_block", "fresh_frozen_aliquot"}),
}
FIELD_STATES = frozenset({"known", "unknown"})


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
CREATE TABLE IF NOT EXISTS rights_sources (
  id INTEGER PRIMARY KEY, source_key TEXT NOT NULL, version_label TEXT NOT NULL,
  owner TEXT NOT NULL, retrieved_at TEXT NOT NULL, attribution TEXT, retention TEXT,
  state TEXT NOT NULL CHECK(state IN ('active','revoked','superseded')),
  created_at TEXT NOT NULL, previous_id INTEGER REFERENCES rights_sources(id),
  UNIQUE(source_key, version_label)
);
CREATE TABLE IF NOT EXISTS rights_permissions (
  rights_source_id INTEGER NOT NULL REFERENCES rights_sources(id),
  item TEXT NOT NULL, use TEXT NOT NULL,
  permission TEXT NOT NULL CHECK(permission IN ('allowed','denied','unknown')),
  PRIMARY KEY(rights_source_id, item, use)
);
CREATE TABLE IF NOT EXISTS broker_links (
  id INTEGER PRIMARY KEY, case_id TEXT NOT NULL REFERENCES cases(case_id),
  question_id INTEGER NOT NULL REFERENCES questions(id),
  rights_source_id INTEGER NOT NULL REFERENCES rights_sources(id),
  relation TEXT NOT NULL CHECK(relation IN ('supports','contradicts','context','unknown')),
  applicability TEXT NOT NULL CHECK(applicability IN ('applicable','limited','not_applicable','unknown')),
  rationale TEXT NOT NULL, citation_title TEXT, excerpt TEXT,
  mode TEXT NOT NULL CHECK(mode IN ('full','metadata_only','citation_only')),
  created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS snapshot_broker_links (
  snapshot_id INTEGER NOT NULL REFERENCES snapshots(id),
  broker_link_id INTEGER NOT NULL REFERENCES broker_links(id),
  PRIMARY KEY(snapshot_id, broker_link_id)
);
CREATE TABLE IF NOT EXISTS rights_events (
  id INTEGER PRIMARY KEY, rights_source_id INTEGER NOT NULL REFERENCES rights_sources(id),
  kind TEXT NOT NULL CHECK(kind IN ('registered','revoked','superseded','link_created','link_reviewed')),
  reason TEXT NOT NULL, recorded_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS investigations (
  id INTEGER PRIMARY KEY,
  case_id TEXT NOT NULL REFERENCES cases(case_id),
  question_id INTEGER NOT NULL REFERENCES questions(id),
  template TEXT NOT NULL,
  status TEXT NOT NULL CHECK(status IN ('completed','abstained','blocked_by_policy','failed')),
  mode TEXT NOT NULL CHECK(mode IN ('live','replay')),
  model TEXT NOT NULL,
  claims_json TEXT NOT NULL,
  abstentions_json TEXT NOT NULL,
  dropped_json TEXT NOT NULL,
  stale INTEGER NOT NULL DEFAULT 0,
  created_at TEXT NOT NULL
);
-- Discovery-to-rights linkage: an item may be bound to one rights row at
-- import (NULL means unlinked: rights unknown, never assumed permitted),
-- and a link may cite broker links. Revocation/correction of a rights row
-- marks dependent links invalid with a cause; rows are never deleted.
CREATE TABLE IF NOT EXISTS discovery_items (
  id INTEGER PRIMARY KEY, discovery_key TEXT NOT NULL UNIQUE,
  kind TEXT NOT NULL CHECK(kind IN ('trial','literature')),
  title TEXT NOT NULL, registry_id TEXT, doi TEXT,
  issued_at TEXT NOT NULL, summary TEXT NOT NULL, status TEXT,
  rights TEXT NOT NULL CHECK(rights='original-synthetic'),
  rights_source_id INTEGER REFERENCES rights_sources(id),
  raw BLOB NOT NULL, created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS discovery_links (
  id INTEGER PRIMARY KEY,
  case_id TEXT NOT NULL REFERENCES cases(case_id),
  question_id INTEGER NOT NULL REFERENCES questions(id),
  discovery_id INTEGER NOT NULL REFERENCES discovery_items(id),
  applicability TEXT NOT NULL CHECK(applicability IN ('applicable','limited','not_applicable','unknown')),
  rationale TEXT NOT NULL, created_at TEXT NOT NULL,
  state TEXT NOT NULL DEFAULT 'valid' CHECK(state IN ('valid','invalid')),
  invalidated_cause TEXT CHECK(invalidated_cause IN ('revocation','correction')),
  invalidated_rights_source_id INTEGER REFERENCES rights_sources(id),
  invalidated_at TEXT,
  UNIQUE(case_id,question_id,discovery_id)
);
CREATE TABLE IF NOT EXISTS discovery_link_broker_links (
  discovery_link_id INTEGER NOT NULL REFERENCES discovery_links(id),
  broker_link_id INTEGER NOT NULL REFERENCES broker_links(id),
  PRIMARY KEY(discovery_link_id, broker_link_id)
);
CREATE INDEX IF NOT EXISTS idx_assessments_evidence ON evidence_assessments(evidence_version_id);
CREATE INDEX IF NOT EXISTS idx_snapshot_evidence_assessment ON snapshot_evidence(assessment_id);
CREATE INDEX IF NOT EXISTS idx_sources_case ON source_versions(case_id, document_id, version);
CREATE INDEX IF NOT EXISTS idx_assertions_source ON assertions(source_version_id);
CREATE INDEX IF NOT EXISTS idx_snapshot_sources_source ON snapshot_sources(source_version_id);
-- OI-020 biological-asset provenance: an extension of the existing case and
-- source model, NOT a second ledger. Assets are immutable rows anchored to
-- one exact source version at creation; liveness lives only in the separate
-- inventory assertions, which go stale anchor-exactly like snapshots do.
-- No rollup of assertions is ever computed: readers always see each
-- assertion with its own anchor, attributor, and state.
CREATE TABLE IF NOT EXISTS biological_assets (
  id INTEGER PRIMARY KEY, case_id TEXT NOT NULL REFERENCES cases(case_id),
  asset_id TEXT NOT NULL,
  kind TEXT NOT NULL CHECK(kind IN ('ffpe_block','fresh_frozen_aliquot','slide','digital_wsi','genomics_data_pointer')),
  episode_id TEXT NOT NULL, specimen_id TEXT,
  specimen_state TEXT NOT NULL CHECK(specimen_state IN ('recorded','unknown')),
  parent_asset_id INTEGER REFERENCES biological_assets(id),
  observed_date TEXT NOT NULL,
  anchor_source_version_id INTEGER NOT NULL REFERENCES source_versions(id),
  pointer_label TEXT, created_at TEXT NOT NULL,
  UNIQUE(case_id,asset_id)
);
CREATE TABLE IF NOT EXISTS biological_inventory_assertions (
  id INTEGER PRIMARY KEY, case_id TEXT NOT NULL REFERENCES cases(case_id),
  asset_id INTEGER NOT NULL REFERENCES biological_assets(id),
  source_version_id INTEGER NOT NULL REFERENCES source_versions(id),
  asserted_by TEXT NOT NULL,
  location_state TEXT NOT NULL CHECK(location_state IN ('known','unknown')), location_value TEXT,
  quantity_state TEXT NOT NULL CHECK(quantity_state IN ('known','unknown')), quantity_value TEXT,
  custody_state TEXT NOT NULL CHECK(custody_state IN ('known','unknown')), custody_value TEXT,
  consent_state TEXT NOT NULL CHECK(consent_state IN ('known','unknown')), consent_value TEXT,
  rights_state TEXT NOT NULL CHECK(rights_state IN ('known','unknown')), rights_value TEXT,
  state TEXT NOT NULL CHECK(state IN ('current','stale')), created_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_biological_assets_case ON biological_assets(case_id, asset_id);
CREATE INDEX IF NOT EXISTS idx_inventory_assertions_asset ON biological_inventory_assertions(asset_id);
CREATE INDEX IF NOT EXISTS idx_inventory_assertions_source ON biological_inventory_assertions(source_version_id);
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
        self._migrate_discovery_rights()

    def _migrate_discovery_rights(self) -> None:
        """Add rights-linkage columns to pre-existing discovery tables.

        Fresh databases get the columns from SCHEMA. Databases created by
        earlier slices keep every row; the new columns default to
        unlinked/valid, so old items stay listable and old links stay
        valid. This migrates only the discovery tables it names.
        """
        migrations = (
            ("discovery_items", "rights_source_id",
             "ALTER TABLE discovery_items ADD COLUMN rights_source_id INTEGER REFERENCES rights_sources(id)"),
            ("discovery_links", "state",
             "ALTER TABLE discovery_links ADD COLUMN state TEXT NOT NULL DEFAULT 'valid' CHECK(state IN ('valid','invalid'))"),
            ("discovery_links", "invalidated_cause",
             "ALTER TABLE discovery_links ADD COLUMN invalidated_cause TEXT CHECK(invalidated_cause IN ('revocation','correction'))"),
            ("discovery_links", "invalidated_rights_source_id",
             "ALTER TABLE discovery_links ADD COLUMN invalidated_rights_source_id INTEGER REFERENCES rights_sources(id)"),
            ("discovery_links", "invalidated_at",
             "ALTER TABLE discovery_links ADD COLUMN invalidated_at TEXT"),
        )
        for table, column, ddl in migrations:
            names = {row["name"] for row in self.db.execute(f"PRAGMA table_info({table})").fetchall()}
            if column not in names:
                try:
                    self.db.execute(ddl)
                except sqlite3.OperationalError:
                    # A concurrent first open may have added the column;
                    # re-check rather than masking a real failure.
                    names = {row["name"] for row in self.db.execute(
                        f"PRAGMA table_info({table})").fetchall()}
                    if column not in names:
                        raise
        self.db.commit()

    def close(self) -> None:
        self.db.close()

    @staticmethod
    def _dicts(rows: list[sqlite3.Row]) -> list[dict]:
        return [dict(x) for x in rows]

    def _event(self, case_id: str, kind: str, **details: object) -> None:
        self.db.execute("INSERT INTO events (case_id,kind,details,occurred_at) VALUES (?,?,?,?)",
                        (case_id, kind, json.dumps(details, sort_keys=True), now_utc()))

    # Adapter-contract hooks (OI-017): these write ONLY to the existing
    # events ledger and the existing quarantine table. They create no second
    # source ledger; source bytes still enter only via import_report.
    ADAPTER_EVENT_KINDS = frozenset({
        "adapter_delivery_accepted", "adapter_delivery_rejected",
        "adapter_delivery_quarantined", "adapter_loss_receipt",
        "adapter_authorization_revoked",
    })

    def record_adapter_event(self, case_id: str, kind: str, **details: object) -> None:
        """Append an adapter receipt/revocation event to the existing ledger."""
        self._case(case_id)
        if kind not in self.ADAPTER_EVENT_KINDS:
            raise InvalidInput("Unknown adapter event kind")
        with self.db:
            self._event(case_id, kind, **details)

    def quarantine_adapter_delivery(self, case_id: str, raw: bytes,
                                    declared_patient_id: str, reason: str) -> dict:
        """Quarantine a rejected adapter delivery in the existing table.

        Idempotent on (case, sha256, reason): a repeated rejected delivery
        returns the original quarantine id and emits no new event.
        """
        case_id = self._case(case_id)
        if not isinstance(raw, bytes) or not raw:
            raise InvalidInput("Quarantined delivery requires raw bytes")
        digest = hashlib.sha256(raw).hexdigest()
        with self.db:
            self.db.execute("BEGIN IMMEDIATE")
            existing = self.db.execute(
                "SELECT id FROM quarantine WHERE target_case_id=? AND sha256=? AND reason=? ORDER BY id LIMIT 1",
                (case_id, digest, reason)).fetchone()
            if existing:
                return {"result": "quarantined", "reason": reason,
                        "quarantine_id": existing["id"], "duplicate": True}
            cur = self.db.execute(
                "INSERT INTO quarantine (target_case_id,declared_patient_id,sha256,raw,reason,received_at) VALUES (?,?,?,?,?,?)",
                (case_id, declared_patient_id, digest, raw, reason, now_utc()))
            self._event(case_id, "source_quarantined", quarantine_id=cur.lastrowid, reason=reason)
            return {"result": "quarantined", "reason": reason, "quarantine_id": cur.lastrowid}

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
                    # An amendment changes freshness for investigations too:
                    # they cite the superseded source's facts, so mark them stale
                    # rather than silently leaving them current.
                    self.db.execute("UPDATE investigations SET stale=1 WHERE case_id=? AND stale=0", (case_id,))
            invalidated_inventory = []
            if previous:
                # Anchor-exact, like snapshots: only assertions citing the
                # superseded version go stale. Assertions on other versions,
                # assets themselves, and all historic rows are preserved.
                # Deliberate scope boundary (OI-020): staleness does NOT
                # propagate transitively to derivative assets; each child's
                # own assertion anchor and parent chain stay visible, so a
                # reader can see a parent's assertions went stale.
                invalidated_inventory = [row[0] for row in self.db.execute(
                    """SELECT id FROM biological_inventory_assertions
                    WHERE case_id=? AND source_version_id=? AND state='current'""",
                    (case_id, previous["id"])).fetchall()]
                if invalidated_inventory:
                    marks = ",".join("?" for _ in invalidated_inventory)
                    self.db.execute(f"UPDATE biological_inventory_assertions SET state='stale' WHERE id IN ({marks})",
                                    invalidated_inventory)
            self._event(case_id, "source_imported", document_id=report.document_id,
                        version=version, source_id=source_id, amends_id=previous["id"] if previous else None,
                        invalidated_snapshots=invalidated, invalidated_inventory_assertions=invalidated_inventory)
            return {"result": "imported", "source_id": source_id, "version": version,
                    "invalidated_snapshots": invalidated,
                    "invalidated_inventory_assertions": invalidated_inventory}


    def _invalidate_evidence_version(self, evidence_version_id: int, *, reason: str) -> list[int]:
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
        return invalidated

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
            invalidated = []
            if previous:
                self.db.execute("UPDATE evidence_versions SET state='superseded' WHERE id=?", (previous["id"],))
                self.db.execute("INSERT INTO evidence_changes (evidence_version_id,kind,reason,recorded_at) VALUES (?,'amended',?,?)",
                                (previous["id"], "Explicit synthetic source version replacement", now_utc()))
                invalidated = self._invalidate_evidence_version(previous["id"], reason="amendment")
            cur = self.db.execute("""INSERT INTO evidence_versions
                (evidence_key,version,sha256,raw,title,issued_at,received_at,
                 statement,statement_line,rights,state,previous_id)
                VALUES (?,?,?,?,?,?,?,?,?,'original-synthetic','current',?)""",
                (item.evidence_key, version, digest, raw, item.title, item.issued_at,
                 now_utc(), item.statement, item.statement_line,
                 previous["id"] if previous else None))
            return {"result": "imported", "evidence_version_id": int(cur.lastrowid),
                    "version": version, "invalidated_snapshots": invalidated}

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
            affected = self._invalidate_evidence_version(evidence_version_id, reason="withdrawal")
            return {"result": "withdrawn", "invalidated_snapshots": affected}

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

    def import_discovery(self, raw: bytes, rights_source_id: int | None = None) -> dict:
        """Import one fictional discovery fixture, optionally bound to a rights row.

        Keys and bindings are immutable: a re-import of identical bytes is a
        duplicate; changed bytes under an existing key are rejected rather
        than silently overwritten, and so is a binding claim that differs
        from the stored one. The binding records which rights manifest this
        item's case use depends on, so a later revocation or correction can
        invalidate dependent links. A rights record that claims permission
        is not proof of permission — the existing broker language governs.
        An item with no rights row is unlinked (rights unknown), never
        assumed permitted.
        """
        from .discovery import DiscoveryInputError, parse_discovery
        try:
            item = parse_discovery(raw)
        except DiscoveryInputError as error:
            raise InvalidInput(str(error)) from None
        if rights_source_id is not None:
            if type(rights_source_id) is not int or rights_source_id < 1:
                raise InvalidInput("Rights source ID must be a positive integer")
        with self.db:
            self.db.execute("BEGIN IMMEDIATE")
            if rights_source_id is not None:
                bound = self.db.execute(
                    "SELECT state FROM rights_sources WHERE id=?", (rights_source_id,)).fetchone()
                if not bound:
                    raise InvalidInput("Rights source not found")
                if bound["state"] != "active":
                    raise InvalidInput("Discovery items bind only to an active rights source")
            existing = self.db.execute(
                "SELECT id, raw, rights_source_id FROM discovery_items WHERE discovery_key=?",
                (item.discovery_key,)).fetchone()
            if existing:
                if bytes(existing["raw"]) == raw:
                    stored = existing["rights_source_id"]
                    if rights_source_id is not None and stored is not None \
                            and int(stored) != rights_source_id:
                        raise InvalidInput("Discovery item is already bound to a different rights source")
                    if rights_source_id is not None and stored is None:
                        raise InvalidInput("Discovery item binding is immutable once imported unlinked")
                    return {"result": "duplicate", "discovery_id": existing["id"],
                            "rights_source_id": stored}
                raise InvalidInput("Discovery key already exists with different content")
            cur = self.db.execute("""INSERT INTO discovery_items
                (discovery_key,kind,title,registry_id,doi,issued_at,summary,status,rights,rights_source_id,raw,created_at)
                VALUES (?,?,?,?,?,?,?,?,?,?,?,?)""",
                (item.discovery_key, item.kind, item.title, item.registry_id, item.doi,
                 item.issued_at, item.summary,
                 "not-verified" if item.kind == "trial" else None,
                 "original-synthetic", rights_source_id, raw, now_utc()))
            return {"result": "imported", "discovery_id": int(cur.lastrowid),
                    "rights_source_id": rights_source_id}
    def list_discovery(self) -> list[dict]:
        from .discovery import project_item
        rows = self.db.execute("""SELECT d.*, rs.state AS rights_state FROM discovery_items d
            LEFT JOIN rights_sources rs ON rs.id=d.rights_source_id
            ORDER BY d.id""").fetchall()
        out = []
        for row in rows:
            row = dict(row)
            projected = project_item(row)
            projected["rights_source_id"] = row["rights_source_id"]
            projected["rights_state"] = row["rights_state"] \
                if row["rights_source_id"] is not None else "unlinked"
            out.append(projected)
        return out
    def link_discovery(self, case_id: str, question_id: int, discovery_id: int,
                       applicability: str, rationale: str,
                       broker_link_ids: list[int] | None = None) -> int:
        """Persist a HUMAN-entered applicability link, optionally bound to rights.

        Applicability is an assessment label, never a determination of
        eligibility, efficacy, or treatment relevance; unknown stays
        first-class. A link depends on rights through its item's bound row
        and through any cited broker links; revocation or correction of
        those rows later marks the link invalid with its cause, preserving
        history. New links fail closed: an item bound to a non-active row,
        and broker links that are revoked, wrong-case, or wrong-question,
        are rejected.
        """
        from .discovery import APPLICABILITY, _check_language, DiscoveryInputError
        case_id = self._case(case_id)
        if type(question_id) is not int or type(discovery_id) is not int:
            raise InvalidInput("Question and discovery IDs must be integers")
        if not isinstance(applicability, str) or applicability not in APPLICABILITY:
            raise InvalidInput("Invalid discovery applicability")
        if not isinstance(rationale, str) or not 15 <= len(rationale.strip()) <= 800:
            raise InvalidInput("Discovery link rationale must have 15-800 characters")
        try:
            _check_language("Rationale", rationale)
        except DiscoveryInputError as error:
            raise InvalidInput(str(error)) from None
        broker_link_ids = [] if broker_link_ids is None else broker_link_ids
        if (not isinstance(broker_link_ids, list) or
            len(broker_link_ids) != len(set(str(x) for x in broker_link_ids)) or
            len(broker_link_ids) > 50 or
            any(type(x) is not int or x < 1 for x in broker_link_ids)):
            raise InvalidInput("Broker link IDs must be unique positive integers; maximum 50")
        with self.db:
            self.db.execute("BEGIN IMMEDIATE")
            if not self.db.execute("SELECT 1 FROM questions WHERE id=? AND case_id=?",
                                   (question_id, case_id)).fetchone():
                raise InvalidInput("Question not in this case")
            item = self.db.execute(
                "SELECT rights_source_id FROM discovery_items WHERE id=?", (discovery_id,)).fetchone()
            if not item:
                raise InvalidInput("Discovery item not found")
            if item["rights_source_id"] is not None:
                bound = self.db.execute(
                    "SELECT state FROM rights_sources WHERE id=?", (item["rights_source_id"],)).fetchone()
                if not bound or bound["state"] != "active":
                    raise InvalidInput("Discovery item's rights source is not active")
            for lid in broker_link_ids:
                linked = self.db.execute("""SELECT 1 FROM broker_links bl
                    JOIN rights_sources rs ON rs.id=bl.rights_source_id
                    WHERE bl.id=? AND bl.case_id=? AND bl.question_id=?
                    AND rs.state='active'
                    AND NOT (bl.relation='supports' AND bl.applicability='not_applicable')""",
                    (lid, case_id, question_id)).fetchone()
                if not linked:
                    raise InvalidInput("Broker link is missing, revoked, or outside this question")
            try:
                cur = self.db.execute("""INSERT INTO discovery_links
                    (case_id,question_id,discovery_id,applicability,rationale,created_at)
                    VALUES (?,?,?,?,?,?)""", (case_id, question_id, discovery_id,
                       applicability, rationale.strip(), now_utc()))
            except sqlite3.IntegrityError:
                raise InvalidInput("Discovery item already linked to this question") from None
            for lid in broker_link_ids:
                self.db.execute("INSERT INTO discovery_link_broker_links VALUES (?,?)",
                                (cur.lastrowid, lid))
            self._event(case_id, "discovery_linked",
                        link_id=cur.lastrowid, discovery_id=discovery_id,
                        broker_link_ids=list(broker_link_ids))
            return int(cur.lastrowid)
    def case_discovery_links(self, case_id: str) -> list[dict]:
        from .discovery import project_item
        case_id = self._case(case_id)
        rows = self.db.execute("""SELECT l.id AS link_id, l.question_id, l.applicability,
            l.rationale, l.created_at AS link_created_at, l.state AS link_state,
            l.invalidated_cause, l.invalidated_rights_source_id, l.invalidated_at,
            d.*, rs.state AS rights_state FROM discovery_links l
            JOIN discovery_items d ON d.id=l.discovery_id
            LEFT JOIN rights_sources rs ON rs.id=d.rights_source_id
            WHERE l.case_id=? ORDER BY l.id""", (case_id,)).fetchall()
        out = []
        for row in rows:
            row = dict(row)
            item = project_item({k: row[k] for k in (
                "id", "discovery_key", "kind", "title", "registry_id", "doi",
                "issued_at", "summary", "status")})
            item["rights_source_id"] = row["rights_source_id"]
            item["rights_state"] = row["rights_state"] \
                if row["rights_source_id"] is not None else "unlinked"
            broker_ids = [r[0] for r in self.db.execute(
                "SELECT broker_link_id FROM discovery_link_broker_links"
                " WHERE discovery_link_id=? ORDER BY broker_link_id",
                (row["link_id"],)).fetchall()]
            out.append({"link_id": row["link_id"], "question_id": row["question_id"],
                        "applicability": row["applicability"], "rationale": row["rationale"],
                        "created_at": row["link_created_at"], "state": row["link_state"],
                        "invalidated_cause": row["invalidated_cause"],
                        "invalidated_rights_source_id": row["invalidated_rights_source_id"],
                        "invalidated_at": row["invalidated_at"],
                        "broker_link_ids": broker_ids, "item": item})
        return out
    # ---- Rights-qualified external evidence broker (issue #2) ----
    # A broker link never fetches external content and never verifies that
    # a rights record is legally true. It only enforces, deterministically,
    # what the record says: unknown means no. Revocation and correction
    # invalidate dependent drafts the same way withdrawal does for
    # synthetic evidence, and prior rows are kept, never overwritten.

    @staticmethod
    def _valid_source_key(value: object) -> str:
        if not isinstance(value, str) or not 1 <= len(value.strip()) <= 120 \
                or any(ch.isspace() or ord(ch) < 33 or ord(ch) > 126 for ch in value):
            raise InvalidInput("Rights source key must be 1–120 printable non-space characters")
        return value.strip()

    @staticmethod
    def _valid_optional_text(value: object, *, max_len: int, field: str) -> str | None:
        if value is None:
            return None
        if not isinstance(value, str) or not value.strip() or len(value.strip()) > max_len:
            raise InvalidInput(f"{field} must be 1–{max_len} characters")
        return value.strip()

    def _rights_row(self, rights_source_id: int) -> sqlite3.Row:
        row = self.db.execute(
            "SELECT * FROM rights_sources WHERE id=?", (rights_source_id,)).fetchone()
        if not row:
            raise InvalidInput("Rights source not found")
        return row

    def _rights_permissions(self, rights_source_id: int) -> dict[str, dict[str, str]]:
        rows = self.db.execute(
            "SELECT item, use, permission FROM rights_permissions WHERE rights_source_id=?",
            (rights_source_id,)).fetchall()
        permissions: dict[str, dict[str, str]] = {}
        for row in rows:
            permissions.setdefault(row["item"], {})[row["use"]] = row["permission"]
        return permissions

    def _invalidate_broker_source(self, rights_source_id: int, *, reason: str) -> list[int]:
        """Invalidate non-stale snapshots citing this rights source row.

        Caller must own a write transaction. History is retained: the
        snapshot rows stay, marked stale, and their questions reopen.
        """
        rows = self.db.execute("""SELECT DISTINCT s.id,s.case_id,s.question_id
            FROM snapshots s JOIN snapshot_broker_links sbl ON sbl.snapshot_id=s.id
            JOIN broker_links bl ON bl.id=sbl.broker_link_id
            WHERE bl.rights_source_id=? AND s.state!='stale'""",
            (rights_source_id,)).fetchall()
        invalidated = [int(row["id"]) for row in rows]
        if invalidated:
            ids = ",".join("?" for _ in invalidated)
            self.db.execute(f"UPDATE snapshots SET state='stale' WHERE id IN ({ids})", invalidated)
            self.db.execute(f"""UPDATE questions SET state='open' WHERE id IN
                (SELECT DISTINCT question_id FROM snapshots WHERE id IN ({ids}))""", invalidated)
            affected = {str(row["case_id"]) for row in rows}
            for case_id in sorted(affected):
                changed = [int(row["id"]) for row in rows if row["case_id"] == case_id]
                self._event(case_id, "broker_invalidated",
                            rights_source_id=rights_source_id,
                            reason=reason, invalidated_snapshots=changed)
        return invalidated

    def _invalidate_discovery_source(self, rights_source_id: int, *, reason: str) -> list[int]:
        """Invalidate valid discovery links depending on this rights source row.

        Caller must own a write transaction. A link depends on the row when
        its item is bound to it or when it cites a broker link that is.
        Links are marked invalid with their cause — never deleted — so the
        rationale, applicability, broker bindings, and item stay readable
        as history. Unlinked items and unrelated links are untouched.
        """
        rows = self.db.execute("""SELECT DISTINCT l.id,l.case_id
            FROM discovery_links l
            JOIN discovery_items d ON d.id=l.discovery_id
            LEFT JOIN discovery_link_broker_links dlbl ON dlbl.discovery_link_id=l.id
            LEFT JOIN broker_links bl ON bl.id=dlbl.broker_link_id
            WHERE l.state='valid' AND (d.rights_source_id=? OR bl.rights_source_id=?)""",
            (rights_source_id, rights_source_id)).fetchall()
        invalidated = [int(row["id"]) for row in rows]
        if invalidated:
            stamped = now_utc()
            ids = ",".join("?" for _ in invalidated)
            self.db.execute(f"""UPDATE discovery_links SET state='invalid',
                invalidated_cause=?, invalidated_rights_source_id=?, invalidated_at=?
                WHERE id IN ({ids})""", [reason, rights_source_id, stamped, *invalidated])
            affected = {str(row["case_id"]) for row in rows}
            for case_id in sorted(affected):
                changed = [int(row["id"]) for row in rows if row["case_id"] == case_id]
                self._event(case_id, "discovery_invalidated",
                            rights_source_id=rights_source_id,
                            reason=reason, invalidated_discovery_links=changed)
        return invalidated

    def register_rights_source(self, source_key: object, owner: object, version_label: object,
                               retrieved_at: object, permissions: object,
                               attribution: object = None, retention: object = None) -> dict:
        """Record one versioned rights manifest. Unknown permissions fail closed."""
        key = self._valid_source_key(source_key)
        if not isinstance(owner, str) or not 2 <= len(owner.strip()) <= 200:
            raise InvalidInput("Rights source owner must be 2–200 characters")
        if not isinstance(version_label, str) or not 1 <= len(version_label.strip()) <= 80:
            raise InvalidInput("Rights version label must be 1–80 characters")
        retrieved = valid_date(retrieved_at) if isinstance(retrieved_at, str) else None
        if retrieved is None:
            raise InvalidInput("Dates must use YYYY-MM-DD")
        try:
            normalized = normalize_permissions(permissions)
        except RightsError as error:
            raise InvalidInput(str(error)) from error
        attribution_text = self._valid_optional_text(attribution, max_len=300, field="Attribution")
        retention_text = self._valid_optional_text(retention, max_len=300, field="Retention")
        with self.db:
            self.db.execute("BEGIN IMMEDIATE")
            try:
                cur = self.db.execute("""INSERT INTO rights_sources
                    (source_key,version_label,owner,retrieved_at,attribution,retention,state,created_at,previous_id)
                    VALUES (?,?,?,?,?,?, 'active',?,NULL)""",
                    (key, version_label.strip(), owner.strip(), retrieved,
                     attribution_text, retention_text, now_utc()))
            except sqlite3.IntegrityError as error:
                raise InvalidInput("Rights source version already recorded") from error
            rights_id = int(cur.lastrowid)
            for item in sorted(normalized):
                for use in sorted(normalized[item]):
                    self.db.execute("""INSERT INTO rights_permissions
                        (rights_source_id,item,use,permission) VALUES (?,?,?,?)""",
                        (rights_id, item, use, normalized[item][use]))
            self.db.execute("""INSERT INTO rights_events
                (rights_source_id,kind,reason,recorded_at) VALUES (?,'registered',?,?)""",
                (rights_id, "Rights manifest recorded", now_utc()))
            return {"rights_source_id": rights_id, "mode": "registered"}

    def revoke_rights_source(self, rights_source_id: int, reason: str) -> dict:
        """Revoke an ACTIVE rights row; dependent drafts and discovery links invalidate. History kept."""
        if type(rights_source_id) is not int or rights_source_id < 1:
            raise InvalidInput("Invalid rights source ID")
        if not isinstance(reason, str) or not 10 <= len(reason.strip()) <= 600:
            raise InvalidInput("Revocation requires a 10–600 character reason")
        with self.db:
            self.db.execute("BEGIN IMMEDIATE")
            row = self._rights_row(rights_source_id)
            if row["state"] != "active":
                raise InvalidInput("Only an active rights source can be revoked")
            self.db.execute("UPDATE rights_sources SET state='revoked' WHERE id=?", (rights_source_id,))
            self.db.execute("""INSERT INTO rights_events
                (rights_source_id,kind,reason,recorded_at) VALUES (?,'revoked',?,?)""",
                (rights_source_id, reason.strip(), now_utc()))
            invalidated = self._invalidate_broker_source(rights_source_id, reason="revocation")
            invalidated_discovery = self._invalidate_discovery_source(rights_source_id, reason="revocation")
            return {"result": "revoked", "invalidated_snapshots": invalidated,
                    "invalidated_discovery_links": invalidated_discovery}

    def correct_rights_source(self, rights_source_id: int, version_label: object,
                              permissions: object, reason: str,
                              retrieved_at: object = None) -> dict:
        """Supersede an ACTIVE rights row with a new versioned manifest.

        The old row is kept (state 'superseded'), drafts citing it go
        stale, dependent discovery links go invalid, and new drafts must
        use the new row. Nothing is silently re-permitted: the new row's
        own permissions gate its links.
        """
        if type(rights_source_id) is not int or rights_source_id < 1:
            raise InvalidInput("Invalid rights source ID")
        if not isinstance(reason, str) or not 10 <= len(reason.strip()) <= 600:
            raise InvalidInput("Correction requires a 10–600 character reason")
        with self.db:
            self.db.execute("BEGIN IMMEDIATE")
            old = self._rights_row(rights_source_id)
            if old["state"] != "active":
                raise InvalidInput("Only an active rights source can be corrected")
            if not isinstance(version_label, str) or not 1 <= len(version_label.strip()) <= 80:
                raise InvalidInput("Rights version label must be 1–80 characters")
            if version_label.strip() == old["version_label"]:
                raise InvalidInput("Correction requires a new version label")
            try:
                normalized = normalize_permissions(permissions)
            except RightsError as error:
                raise InvalidInput(str(error)) from error
            retrieved = old["retrieved_at"]
            if retrieved_at is not None:
                retrieved = valid_date(retrieved_at) if isinstance(retrieved_at, str) else None
                if retrieved is None:
                    raise InvalidInput("Dates must use YYYY-MM-DD")
            try:
                cur = self.db.execute("""INSERT INTO rights_sources
                    (source_key,version_label,owner,retrieved_at,attribution,retention,state,created_at,previous_id)
                    VALUES (?,?,?,?,?,?, 'active',?,?)""",
                    (old["source_key"], version_label.strip(), old["owner"], retrieved,
                     old["attribution"], old["retention"], now_utc(), rights_source_id))
            except sqlite3.IntegrityError as error:
                raise InvalidInput("Rights source version already recorded") from error
            new_id = int(cur.lastrowid)
            for item in sorted(normalized):
                for use in sorted(normalized[item]):
                    self.db.execute("""INSERT INTO rights_permissions
                        (rights_source_id,item,use,permission) VALUES (?,?,?,?)""",
                        (new_id, item, use, normalized[item][use]))
            self.db.execute("UPDATE rights_sources SET state='superseded' WHERE id=?", (rights_source_id,))
            self.db.execute("""INSERT INTO rights_events
                (rights_source_id,kind,reason,recorded_at) VALUES (?,'superseded',?,?)""",
                (rights_source_id, reason.strip(), now_utc()))
            self.db.execute("""INSERT INTO rights_events
                (rights_source_id,kind,reason,recorded_at) VALUES (?,'registered',?,?)""",
                (new_id, reason.strip(), now_utc()))
            invalidated = self._invalidate_broker_source(rights_source_id, reason="correction")
            invalidated_discovery = self._invalidate_discovery_source(rights_source_id, reason="correction")
            return {"rights_source_id": new_id, "superseded_id": rights_source_id,
                    "invalidated_snapshots": invalidated,
                    "invalidated_discovery_links": invalidated_discovery}

    def create_broker_link(self, case_id: str, question_id: int, rights_source_id: int,
                           relation: str, applicability: str, rationale: str,
                           citation_title: object = None, excerpt: object = None) -> dict:
        """Attach one rights-gated external source to one case question.

        No content is stored beyond what the rights row permits: an
        excerpt only in full mode, a title only with metadata (or full)
        permission, otherwise citation identity alone. The link carries a
        human-entered review (relation/applicability), never a model
        verdict; unknown states are first-class, not errors.
        """
        self._case(case_id)
        if type(question_id) is not int or type(rights_source_id) is not int:
            raise InvalidInput("Question and rights source IDs must be integers")
        if relation not in EVIDENCE_RELATIONS or applicability not in EVIDENCE_APPLICABILITY:
            raise InvalidInput("Invalid evidence relationship or applicability")
        if relation == "supports" and applicability == "not_applicable":
            raise InvalidInput("An inapplicable source cannot be labelled as supporting this question")
        if not isinstance(rationale, str) or not 15 <= len(rationale.strip()) <= 800:
            raise InvalidInput("Broker link rationale must be 15–800 characters")
        title = self._valid_optional_text(citation_title, max_len=180, field="Citation title")
        if excerpt is not None:
            if not isinstance(excerpt, str) or not 10 <= len(excerpt.strip()) <= 1200:
                raise InvalidInput("Excerpt must be 10–1200 characters")
            excerpt = excerpt.strip()
        with self.db:
            self.db.execute("BEGIN IMMEDIATE")
            if not self.db.execute("SELECT 1 FROM questions WHERE id=? AND case_id=?",
                                   (question_id, case_id)).fetchone():
                raise InvalidInput("Question not in this case")
            row = self._rights_row(rights_source_id)
            if row["state"] != "active":
                raise InvalidInput("Rights source is not active")
            permissions = self._rights_permissions(rights_source_id)
            try:
                mode = check_link_content(permissions, citation_title=title, excerpt=excerpt)
            except RightsError as error:
                raise InvalidInput(str(error)) from error
            cur = self.db.execute("""INSERT INTO broker_links
                (case_id,question_id,rights_source_id,relation,applicability,rationale,
                 citation_title,excerpt,mode,created_at)
                VALUES (?,?,?,?,?,?,?,?,?,?)""",
                (case_id, question_id, rights_source_id, relation, applicability,
                 rationale.strip(), title, excerpt, mode, now_utc()))
            link_id = int(cur.lastrowid)
            self.db.execute("""INSERT INTO rights_events
                (rights_source_id,kind,reason,recorded_at) VALUES (?,'link_created',?,?)""",
                (rights_source_id, f"Broker link {link_id} for case {case_id}", now_utc()))
            self._event(case_id, "broker_link_created",
                        broker_link_id=link_id, rights_source_id=rights_source_id, mode=mode)
            return {"broker_link_id": link_id, "mode": mode}

    def review_broker_link(self, case_id: str, broker_link_id: int, relation: str,
                           applicability: str, rationale: str) -> dict:
        """Human re-review of a broker link, scoped to its own case.

        Revoked sources cannot be re-blessed. A re-review changes what
        the link means, so drafts already citing it go stale rather than
        silently changing meaning — the same rule as an amendment.
        """
        self._case(case_id)
        if type(broker_link_id) is not int or broker_link_id < 1:
            raise InvalidInput("Invalid broker link ID")
        if relation not in EVIDENCE_RELATIONS or applicability not in EVIDENCE_APPLICABILITY:
            raise InvalidInput("Invalid evidence relationship or applicability")
        if relation == "supports" and applicability == "not_applicable":
            raise InvalidInput("An inapplicable source cannot be labelled as supporting this question")
        if not isinstance(rationale, str) or not 15 <= len(rationale.strip()) <= 800:
            raise InvalidInput("Broker link rationale must be 15–800 characters")
        with self.db:
            self.db.execute("BEGIN IMMEDIATE")
            link = self.db.execute("SELECT * FROM broker_links WHERE id=?", (broker_link_id,)).fetchone()
            if not link or link["case_id"] != case_id:
                raise InvalidInput("Broker link not found in this case")
            row = self._rights_row(int(link["rights_source_id"]))
            if row["state"] != "active":
                raise InvalidInput("Cannot review a link whose rights source is not active")
            self.db.execute("""UPDATE broker_links SET relation=?,applicability=?,rationale=?
                WHERE id=?""", (relation, applicability, rationale.strip(), broker_link_id))
            self.db.execute("""INSERT INTO rights_events
                (rights_source_id,kind,reason,recorded_at) VALUES (?,'link_reviewed',?,?)""",
                (int(link["rights_source_id"]), f"Broker link {broker_link_id} re-reviewed", now_utc()))
            rows = self.db.execute("""SELECT DISTINCT s.id,s.case_id,s.question_id
                FROM snapshots s JOIN snapshot_broker_links sbl ON sbl.snapshot_id=s.id
                WHERE sbl.broker_link_id=? AND s.state!='stale'""", (broker_link_id,)).fetchall()
            invalidated = [int(r["id"]) for r in rows]
            if invalidated:
                ids = ",".join("?" for _ in invalidated)
                self.db.execute(f"UPDATE snapshots SET state='stale' WHERE id IN ({ids})", invalidated)
                self.db.execute(f"""UPDATE questions SET state='open' WHERE id IN
                    (SELECT DISTINCT question_id FROM snapshots WHERE id IN ({ids}))""", invalidated)
                self._event(case_id, "broker_invalidated",
                            broker_link_id=broker_link_id,
                            reason="review", invalidated_snapshots=invalidated)
            return {"result": "reviewed", "broker_link_id": broker_link_id,
                    "invalidated_snapshots": invalidated}

    def rights_sources(self) -> list[dict]:
        """All rights manifests with their permission maps, for inspection."""
        rows = self._dicts(self.db.execute(
            "SELECT * FROM rights_sources ORDER BY source_key, id").fetchall())
        for row in rows:
            row["permissions"] = self._rights_permissions(int(row["id"]))
        return rows

    def synthetic_evidence_text(self, evidence_version_id: int) -> str:
        if type(evidence_version_id) is not int or evidence_version_id < 1:
            raise InvalidInput("Invalid evidence version ID")
        row = self.db.execute("SELECT raw FROM evidence_versions WHERE id=?",
                              (evidence_version_id,)).fetchone()
        if not row:
            raise InvalidInput("Evidence version not found")
        return bytes(row["raw"]).decode("utf-8")

    def add_biological_asset(self, case_id: str, asset_id: str, kind: str, episode_id: str,
                             observed_date: str, anchor_source_version_id: int,
                             specimen_state: str = "unknown", specimen_id: str | None = None,
                             parent_asset_id: int | None = None, pointer_label: str | None = None) -> int:
        """Register one synthetic biological asset inside the existing case model.

        No bytes, images, or genome files are stored: digital_wsi and
        genomics_data_pointer carry only a short descriptive pointer label, and
        that label may not be a URL or filesystem path. The anchor source
        version is creation provenance only; it is never a liveness claim.
        Liveness lives in inventory assertions. No release, shipment, or
        outside-service operation exists anywhere in this module.
        """
        case_id = self._case(case_id)
        asset_id = valid_id(asset_id)
        episode_id = valid_id(episode_id)
        observed_date = valid_date(observed_date)
        if kind not in ASSET_KINDS:
            raise InvalidInput("Unknown biological asset kind")
        if type(anchor_source_version_id) is not int or anchor_source_version_id < 1:
            raise InvalidInput("Anchor source version ID must be a positive integer")
        if specimen_state not in ("recorded", "unknown"):
            raise InvalidInput("Specimen state must be recorded or unknown")
        if specimen_state == "recorded":
            if specimen_id is None:
                raise InvalidInput("Recorded specimen requires a specimen ID")
            specimen_id = valid_id(specimen_id)
        elif specimen_id is not None:
            raise InvalidInput("Unknown specimen must not carry a specimen ID")
        if kind in DERIVATIVE_PARENTS:
            if type(parent_asset_id) is not int or parent_asset_id < 1:
                raise InvalidInput("A derivative asset requires its parent asset")
        elif parent_asset_id is not None:
            raise InvalidInput("An original asset has no parent asset")
        if pointer_label is not None:
            if kind not in ("digital_wsi", "genomics_data_pointer"):
                raise InvalidInput("A pointer label applies only to digital WSI and genomics data pointers")
            if (not isinstance(pointer_label, str) or not 1 <= len(pointer_label.strip()) <= 200
                    or "://" in pointer_label or pointer_label.strip().startswith("/")):
                raise InvalidInput("Pointer label must be 1-200 characters, not a URL or path")
            pointer_label = pointer_label.strip()
        with self.db:
            self.db.execute("BEGIN IMMEDIATE")
            anchor = self.db.execute(
                "SELECT state FROM source_versions WHERE id=? AND case_id=?",
                (anchor_source_version_id, case_id)).fetchone()
            if not anchor or anchor["state"] != "current":
                raise InvalidInput("Anchor source is missing, superseded, or belongs to another case")
            if parent_asset_id is not None:
                parent = self.db.execute(
                    "SELECT kind,episode_id FROM biological_assets WHERE id=? AND case_id=?",
                    (parent_asset_id, case_id)).fetchone()
                if not parent:
                    raise InvalidInput("Parent asset not in this case")
                if parent["episode_id"] != episode_id:
                    raise InvalidInput("A derivative must share its parent's cancer episode; tumors never merge")
                if parent["kind"] not in DERIVATIVE_PARENTS[kind]:
                    raise InvalidInput("Parent asset kind cannot derive this asset kind")
            try:
                cur = self.db.execute("""INSERT INTO biological_assets
                    (case_id,asset_id,kind,episode_id,specimen_id,specimen_state,parent_asset_id,
                     observed_date,anchor_source_version_id,pointer_label,created_at)
                    VALUES (?,?,?,?,?,?,?,?,?,?,?)""",
                    (case_id, asset_id, kind, episode_id, specimen_id, specimen_state,
                     parent_asset_id, observed_date, anchor_source_version_id, pointer_label, now_utc()))
            except sqlite3.IntegrityError:
                raise InvalidInput("Biological asset already exists in this case") from None
            self._event(case_id, "biological_asset_created", biological_asset_id=int(cur.lastrowid),
                        asset_id=asset_id, asset_kind=kind, episode_id=episode_id)
            return int(cur.lastrowid)

    @staticmethod
    def _inventory_field(state: object, value: object, name: str) -> str | None:
        if state not in FIELD_STATES:
            raise InvalidInput(f"Inventory {name} state must be known or unknown")
        if state == "known":
            if not isinstance(value, str) or not 1 <= len(value.strip()) <= 200:
                raise InvalidInput(f"Known inventory {name} requires a 1-200 character value")
            return value.strip()
        if value is not None:
            raise InvalidInput(f"Unknown inventory {name} must not carry a value")
        return None

    def add_inventory_assertion(self, case_id: str, asset_pk: int, source_version_id: int,
                                asserted_by: str, *, location_state: str, location_value: str | None,
                                quantity_state: str, quantity_value: str | None,
                                custody_state: str, custody_value: str | None,
                                consent_state: str, consent_value: str | None,
                                rights_state: str, rights_value: str | None) -> int:
        """Record one separately attributed inventory assertion for one asset.

        UNKNOWN is an explicit stored state with a NULL value; it is never
        treated as absent, and an asset with no assertion row at all is
        reported as 'no inventory assertion recorded', which is distinct from
        an all-unknown assertion. Rights/consent values are descriptive only:
        nothing in this module gates, releases, or ships on them, so no
        query can fail open through them.
        """
        case_id = self._case(case_id)
        if type(asset_pk) is not int or asset_pk < 1 or type(source_version_id) is not int or source_version_id < 1:
            raise InvalidInput("Asset and source version IDs must be positive integers")
        if not isinstance(asserted_by, str) or not 2 <= len(asserted_by.strip()) <= 80:
            raise InvalidInput("Provide an inventory attributor label")
        values = {
            "location": self._inventory_field(location_state, location_value, "location"),
            "quantity": self._inventory_field(quantity_state, quantity_value, "quantity"),
            "custody": self._inventory_field(custody_state, custody_value, "custody"),
            "consent": self._inventory_field(consent_state, consent_value, "consent"),
            "rights": self._inventory_field(rights_state, rights_value, "rights"),
        }
        with self.db:
            self.db.execute("BEGIN IMMEDIATE")
            if not self.db.execute("SELECT 1 FROM biological_assets WHERE id=? AND case_id=?",
                                   (asset_pk, case_id)).fetchone():
                raise InvalidInput("Biological asset not in this case")
            source = self.db.execute(
                "SELECT state FROM source_versions WHERE id=? AND case_id=?",
                (source_version_id, case_id)).fetchone()
            if not source or source["state"] != "current":
                raise InvalidInput("Inventory source is missing, superseded, or belongs to another case")
            cur = self.db.execute("""INSERT INTO biological_inventory_assertions
                (case_id,asset_id,source_version_id,asserted_by,
                 location_state,location_value,quantity_state,quantity_value,
                 custody_state,custody_value,consent_state,consent_value,
                 rights_state,rights_value,state,created_at)
                VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?, 'current',?)""",
                (case_id, asset_pk, source_version_id, asserted_by.strip(),
                 location_state, values["location"], quantity_state, values["quantity"],
                 custody_state, values["custody"], consent_state, values["consent"],
                 rights_state, values["rights"], now_utc()))
            self._event(case_id, "biological_inventory_asserted",
                        inventory_assertion_id=int(cur.lastrowid), asset_id=asset_pk,
                        source_version_id=source_version_id)
            return int(cur.lastrowid)

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
                        evidence_assessment_ids: list[int] | None = None,
                        broker_link_ids: list[int] | None = None) -> int:
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
        broker_link_ids = [] if broker_link_ids is None else broker_link_ids
        if (not isinstance(broker_link_ids, list) or
            len(broker_link_ids) != len(set(str(x) for x in broker_link_ids)) or
            len(broker_link_ids) > 50 or
            any(type(x) is not int or x < 1 for x in broker_link_ids)):
            raise InvalidInput("Broker link IDs must be unique positive integers; maximum 50")
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
            for lid in broker_link_ids:
                linked = self.db.execute("""SELECT 1 FROM broker_links bl
                    JOIN rights_sources rs ON rs.id=bl.rights_source_id
                    WHERE bl.id=? AND bl.case_id=? AND bl.question_id=?
                    AND rs.state='active'
                    AND NOT (bl.relation='supports' AND bl.applicability='not_applicable')""",
                    (lid, case_id, question_id)).fetchone()
                if not linked:
                    raise InvalidInput("Broker link is missing, revoked, or outside this question")
            for lid in broker_link_ids:
                self.db.execute("INSERT INTO snapshot_broker_links VALUES (?,?)", (snapshot_id, lid))
            self._event(case_id, "draft_created", snapshot_id=snapshot_id, question_id=question_id,
                        evidence_assessment_ids=evidence_assessment_ids,
                        broker_link_ids=broker_link_ids)
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

    def investigation_facts(self, case_id: str, question_id: int) -> dict:
        """Facts the investigation prompt may use: question, current assertions, assessments."""
        self._case(case_id)
        if type(question_id) is not int:
            raise InvalidInput("Question id must be an integer")
        question = self.db.execute("SELECT * FROM questions WHERE id=? AND case_id=?",
                                   (question_id, case_id)).fetchone()
        if not question:
            raise InvalidInput("Question not in this case")
        assertions = self._dicts(self.db.execute(
            """SELECT assertions.id,source_version_id,finding_key,certainty,quote,source_line
            FROM assertions JOIN source_versions ON source_versions.id=assertions.source_version_id
            WHERE assertions.case_id=? AND source_versions.state='current' ORDER BY assertions.id""",
            (case_id,)).fetchall())
        assessments = self._dicts(self.db.execute(
            """SELECT a.id,a.relation,a.applicability,a.rationale,v.statement
            FROM evidence_assessments a JOIN evidence_versions v ON v.id=a.evidence_version_id
            WHERE a.case_id=? AND a.question_id=? AND v.state='current' AND v.rights='original-synthetic'
            ORDER BY a.id""", (case_id, question_id)).fetchall())
        return {
            "question": dict(question),
            "assertions": assertions,
            "assessments": assessments,
            "valid_sources": {int(a["source_version_id"]) for a in assertions},
            "valid_assessments": {int(a["id"]) for a in assessments},
        }

    def save_investigation(self, case_id: str, question_id: int, template: str,
                           validated, mode: str) -> int:
        self._case(case_id)
        with self.db:
            cur = self.db.execute(
                """INSERT INTO investigations
                (case_id,question_id,template,status,mode,model,claims_json,abstentions_json,dropped_json,created_at)
                VALUES (?,?,?,?,?,?,?,?,?,?)""",
                (case_id, question_id, template, validated.status, mode, validated.model,
                 json.dumps(validated.claims), json.dumps(validated.abstentions),
                 json.dumps(validated.dropped), now_utc()))
            investigation_id = int(cur.lastrowid)
            self.db.execute("UPDATE questions SET state='addressed' WHERE id=? AND case_id=?",
                            (question_id, case_id))
            self._event(case_id, "investigation_created", investigation_id=investigation_id,
                        template=template, status=validated.status, mode=mode)
            return investigation_id

    def get_investigation(self, case_id: str, investigation_id: int) -> dict:
        self._case(case_id)
        row = self.db.execute("SELECT * FROM investigations WHERE id=? AND case_id=?",
                              (investigation_id, case_id)).fetchone()
        if not row:
            raise InvalidInput("Investigation not in this case")
        data = dict(row)
        data["claims"] = json.loads(data.pop("claims_json"))
        data["abstentions"] = json.loads(data.pop("abstentions_json"))
        data["dropped"] = json.loads(data.pop("dropped_json"))
        data["kind"] = "hypothesis"
        data["review_state"] = "pending"
        data["disclaimer"] = ("Research demonstration only. Hypotheses are unreviewed, "
                              "fictional-data based, and not medical advice.")
        return data

    def list_investigations(self, case_id: str) -> list[dict]:
        self._case(case_id)
        rows = self._dicts(self.db.execute(
            "SELECT id,question_id,template,status,mode,model,stale,created_at "
            "FROM investigations WHERE case_id=? ORDER BY id DESC", (case_id,)).fetchall())
        for row in rows:
            row["kind"] = "hypothesis"
            row["review_state"] = "pending"
        return rows

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
            for snapshot in snapshot_rows:
                snapshot["broker_link_ids"] = [r[0] for r in self.db.execute(
                    "SELECT broker_link_id FROM snapshot_broker_links WHERE snapshot_id=? ORDER BY broker_link_id",
                    (snapshot["id"],)).fetchall()]
            broker_rows = self._dicts(self.db.execute("""SELECT bl.*, rs.source_key, rs.version_label,
                rs.owner, rs.state AS rights_state FROM broker_links bl
                JOIN rights_sources rs ON rs.id=bl.rights_source_id
                WHERE bl.case_id=? ORDER BY bl.id DESC""", (case_id,)).fetchall())
            # Provenance is retained, but revoked/superseded content is not
            # served: the link and its mode stay visible, the stored title
            # and excerpt do not.
            for broker_row in broker_rows:
                if broker_row["rights_state"] != "active":
                    broker_row["citation_title"] = None
                    broker_row["excerpt"] = None
                    broker_row["content_redacted"] = True
                else:
                    broker_row["content_redacted"] = False
            rights_rows = self._dicts(self.db.execute(
                "SELECT * FROM rights_sources ORDER BY source_key, id").fetchall())
            for rights_row in rights_rows:
                rights_row["permissions"] = self._rights_permissions(int(rights_row["id"]))
            evidence_rows = self._dicts(self.db.execute("""SELECT id,evidence_key,version,sha256,title,
                issued_at,received_at,statement,statement_line,rights,state,previous_id
                FROM evidence_versions ORDER BY evidence_key,version""").fetchall())
            assessments = self._dicts(self.db.execute("""SELECT a.*,v.evidence_key,v.version,v.state AS evidence_state,
                v.title,v.statement,v.statement_line,v.sha256
                FROM evidence_assessments a JOIN evidence_versions v ON v.id=a.evidence_version_id
                WHERE a.case_id=? ORDER BY a.id DESC""", (case_id,)).fetchall())
            return {
                "broker_links": broker_rows,
                "rights_sources": rights_rows,
                "biological_assets": self._dicts(self.db.execute(
                    "SELECT * FROM biological_assets WHERE case_id=? ORDER BY id", (case_id,)).fetchall()),
                "biological_inventory_assertions": self._dicts(self.db.execute(
                    "SELECT * FROM biological_inventory_assertions WHERE case_id=? ORDER BY id",
                    (case_id,)).fetchall()),
                "evidence": evidence_rows,
                "evidence_changes": self._dicts(self.db.execute(
                    "SELECT id,evidence_version_id,kind,reason,recorded_at FROM evidence_changes ORDER BY id DESC").fetchall()),
                "evidence_assessments": assessments,
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
