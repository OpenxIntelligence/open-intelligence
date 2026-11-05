"""Synthetic-only, source-preserving case investigation ledger.

This module is a research/engineering reference implementation, NOT a medical
record system. No patient authentication, PHI handling, or clinical validation.
"""

from __future__ import annotations

import hashlib
import hmac
import json
import re
import secrets
import sqlite3
from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

from .rights import RightsError, check_link_content, normalize_permissions
from .care_records import (
    SECOND_OPINION_DISCLAIMER,
    SURVIVORSHIP_DISCLAIMER,
    CareRecordInputError,
    check_descriptive,
)
from .scoped_review import (
    check_claim_ref,
    check_note,
    check_reviewer_label,
    check_scope,
    derive_status,
    render_scoped_review_lines,
)
from . import task_receipts

ID = re.compile(r"[A-Z][A-Z0-9-]{1,39}\Z")
KEY = re.compile(r"[a-z][a-z0-9_-]{0,59}\Z")
STATES = frozenset({"reported", "negative", "pending", "indeterminate", "not-reported", "not-assessed", "conflicting"})
TYPES = frozenset({"pathology", "molecular", "imaging", "laboratory", "clinical", "other"})
MAX_SOURCE_BYTES = 65536
MAX_SUMMARY = 3000
# Slice 1 local demo accounts: operator-created only, stdlib password
# hashing, server-side sessions. Accounts are local labels, not verified
# identities; the fictional-demo framing is unchanged.
ACCOUNT_ROLES = frozenset({"operator", "clinician", "patient", "auditor"})
SESSION_TTL_SECONDS = 24 * 3600
PASSWORD_MIN_LENGTH = 8
_PBKDF2_ITERATIONS = 200_000
# Sentinel for "argument absent" in follow-through updates, distinct from an
# explicit null (which clears the field it names).
_KEEP = object()
# B-02: fictional attribution for auto-created re-review tasks. This is a
# placeholder owner label at the same honesty level as preparation-task
# owner labels — never a real user, never a notification target.
DEFAULT_RE_REVIEW_ASSIGNEE = "FICTIONAL-REVIEWER"


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


def today_utc() -> str:
    return datetime.now(timezone.utc).date().isoformat()


PURPOSE = re.compile(r"[a-z][a-z0-9-]{0,63}\Z")


def valid_purpose(value: object) -> str:
    """A grant purpose is an exact lowercase token (`individual-access`).
    Empty, whitespace, uppercase, and glob-style (`*`) purposes are rejected:
    this slice has no wildcard grants and no silent grant expansion. A grant
    authorizes only requests whose required purpose equals its stated purpose."""
    if not isinstance(value, str) or not PURPOSE.fullmatch(value):
        raise InvalidInput("Grant purpose must be a lowercase token such as individual-access; wildcards are not permitted")
    return value


@dataclass(frozen=True)
class OncologyAttribution:
    """Explicit case-local attribution on an authored synthetic source line."""
    role: str
    episode_id: str | None


@dataclass(frozen=True)
class Finding:
    key: str
    state: str
    quote: str
    line: int
    oncology: OncologyAttribution | None = None


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


def parse_report(raw: bytes, *, allow_oncology: bool = False) -> ParsedReport:
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
    oncology_format = allow_oncology and text.partition("\n")[0] == "OI-SYNTHETIC-REPORT/2"
    if oncology_format and re.search(r"[\v\f\x1c-\x1e\x85\u2028\u2029]", text):
        raise InvalidInput("Version 2 reports require LF line separators")
    lines = text.splitlines()
    if not oncology_format and (not lines or lines[0] != "OI-SYNTHETIC-REPORT/1"):
        raise InvalidInput("Unsupported synthetic report format" if allow_oncology else "Only OI-SYNTHETIC-REPORT/1 is supported")
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
        if label == "Finding" or (oncology_format and label == "Oncology-Finding"):
            oncology = None
            if label == "Oncology-Finding":
                parts = value.split("|", 4)
                if len(parts) != 5:
                    raise InvalidInput(f"Line {line_number}: expected key|role|episode|state|quotation")
                key, role, episode, state, quote = parts
                if role not in ("primary", "metastasis"):
                    raise InvalidInput(f"Line {line_number}: unknown oncology role")
                if episode != "?" and not re.fullmatch(r"EP-[A-Z0-9][A-Z0-9-]{0,35}", episode):
                    raise InvalidInput(f"Line {line_number}: expected case-local EP- identifier or ?")
                oncology = OncologyAttribution(role, None if episode == "?" else episode)
                parts = [key, state, quote]
            else:
                parts = value.split("|", 2)
            if len(parts) != 3:
                raise InvalidInput(f"Line {line_number}: finding needs key|state|source quotation")
            key, state, quote = (part.strip() for part in parts)
            if not KEY.fullmatch(key) or state not in STATES or not quote or key in used_keys:
                raise InvalidInput(f"Line {line_number}: invalid or repeated finding key/status/quotation")
            if len(quote) > 1200:
                raise InvalidInput(f"Line {line_number}: quotation too long")
            findings.append(Finding(key, state, quote, line_number, oncology))
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

# B-06: orthogonal workflow marker on questions. This never replaces the
# open/addressed lifecycle and carries no clinical meaning: it records only
# whether a fictional owner label has been attached and how a human sorted
# the question for follow-up.
QUESTION_TRIAGE = frozenset({"unsorted", "owned", "awaiting_evidence", "ready_for_review"})

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

# Longitudinal biological explanation: an assay observation anchors to one
# physical tissue block only. Slides, WSI views, and genomics pointers are
# derivatives, not tissue sources, so they cannot silently stand in for one.
BIO_TISSUE_BLOCK_KINDS = frozenset({"ffpe_block", "fresh_frozen_aliquot"})

# Narrow guard, not a clinical-language classifier: biological-explanation
# text must stay a fictional context record. It must not state staging,
# grading, variant interpretation, response/progression, eligibility, or
# treatment claims. A human author rewords the text; nothing is repaired.
BIO_GUARDED_LANGUAGE = re.compile(
    r"\b(stag\w*|grad\w*|respond\w*|response|progress\w*|pathogenic\w*|actionable|"
    r"eligib\w*|recommend\w*|prescrib\w*|treat\w*|benefit|efficacy|"
    r"remission|relaps\w*|mutation burden|tumor burden)\b", re.IGNORECASE)


def _check_bio_language(text: object, field: str) -> str:
    if not isinstance(text, str) or not text.strip():
        raise InvalidInput(f"{field} is required")
    if BIO_GUARDED_LANGUAGE.search(text):
        raise InvalidInput(
            f"{field} must not state staging, grading, variant interpretation, "
            "response/progression, eligibility, or treatment claims; "
            "rephrase as a fictional context record")
    return text.strip()


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
CREATE TABLE IF NOT EXISTS document_intake_metadata (
  source_version_id INTEGER PRIMARY KEY REFERENCES source_versions(id),
  filename TEXT NOT NULL, media_type TEXT NOT NULL,
  extraction_method TEXT NOT NULL, annotation_method TEXT NOT NULL,
  manual_transcription_confirmed INTEGER NOT NULL CHECK(manual_transcription_confirmed=1),
  clinical_review TEXT NOT NULL CHECK(clinical_review='not_performed'),
  review_sha256 TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS questions (
  id INTEGER PRIMARY KEY, case_id TEXT NOT NULL REFERENCES cases(case_id),
  question TEXT NOT NULL, state TEXT NOT NULL CHECK(state IN ('open','addressed')),
  owner_label TEXT,
  triage TEXT NOT NULL DEFAULT 'unsorted'
    CHECK(triage IN ('unsorted','owned','awaiting_evidence','ready_for_review')),
  created_at TEXT NOT NULL
);
-- B-06 owned scientific questions: owner labels are fictional attribution,
-- never authorization. Owner history and needed-evidence notes are
-- append-only: rows are inserted, never updated or deleted. The triage
-- column is an orthogonal workflow marker; the open/addressed lifecycle
-- (investigation/review -> addressed, amendment/evidence invalidation ->
-- open) is unchanged and triage is never silently reinterpreted as state.
CREATE TABLE IF NOT EXISTS question_owner_history (
  id INTEGER PRIMARY KEY, case_id TEXT NOT NULL REFERENCES cases(case_id),
  question_id INTEGER NOT NULL REFERENCES questions(id),
  owner_label TEXT NOT NULL, assigned_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS question_evidence_notes (
  id INTEGER PRIMARY KEY, case_id TEXT NOT NULL REFERENCES cases(case_id),
  question_id INTEGER NOT NULL REFERENCES questions(id),
  version INTEGER NOT NULL, note TEXT NOT NULL, created_at TEXT NOT NULL,
  UNIQUE(question_id, version)
);
CREATE INDEX IF NOT EXISTS idx_question_owner_history_question ON question_owner_history(question_id);
CREATE INDEX IF NOT EXISTS idx_question_evidence_notes_question ON question_evidence_notes(question_id);
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
-- B-05 explicit subject binding. One row per imported source version,
-- recording the declared subject id and the declared-ID-equality match
-- decision. Append-only: no update path exists, so a recorded decision is
-- never changed in place. source_version_id is UNIQUE so one source
-- version can never bind to two cases (no silent merges).
CREATE TABLE IF NOT EXISTS subject_links (
  id INTEGER PRIMARY KEY, case_id TEXT NOT NULL REFERENCES cases(case_id),
  source_version_id INTEGER NOT NULL UNIQUE REFERENCES source_versions(id),
  declared_subject_id TEXT NOT NULL,
  decision TEXT NOT NULL CHECK(decision='bound_by_declared_id_equality'),
  decided_at TEXT NOT NULL, actor_label TEXT NOT NULL
);
-- B-05 reversible-correction dispositions for quarantined deliveries.
-- Append-only: at most one row per quarantine id; the quarantine row
-- itself is never deleted or edited and keeps the original bytes.
CREATE TABLE IF NOT EXISTS quarantine_corrections (
  quarantine_id INTEGER PRIMARY KEY REFERENCES quarantine(id),
  source_case_id TEXT NOT NULL REFERENCES cases(case_id),
  destination_case_id TEXT NOT NULL REFERENCES cases(case_id),
  destination_source_id INTEGER NOT NULL REFERENCES source_versions(id),
  corrected_at TEXT NOT NULL, actor_label TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_subject_links_case ON subject_links(case_id, source_version_id);
CREATE INDEX IF NOT EXISTS idx_quarantine_corrections_dest ON quarantine_corrections(destination_case_id);
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
-- Slice 1 (program plan section 5.4): the per-agent write contract.
-- Exactly one row per stored investigation, holding the full contract
-- JSON; the investigations table itself is unchanged so pre-slice rows
-- keep reading (their contract is NULL). The contract is the single
-- attribution/replay record for the run; no second copy is kept.
CREATE TABLE IF NOT EXISTS agent_writes (
  id INTEGER PRIMARY KEY,
  write_id TEXT NOT NULL UNIQUE,
  investigation_id INTEGER NOT NULL REFERENCES investigations(id),
  case_id TEXT NOT NULL REFERENCES cases(case_id),
  contract_json TEXT NOT NULL,
  created_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_agent_writes_investigation ON agent_writes(investigation_id);
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
-- Counterevidence and safety-uncertainty surfacing: append-only records over
-- the existing option ledger. No row here is ever updated or deleted; a hold
-- or invalidation stays visible as history even after its triggering source
-- or evidence version is superseded or withdrawn. These tables add
-- new state only; they never replace snapshots, options, or review history.
CREATE TABLE IF NOT EXISTS option_counterevidence (
  id INTEGER PRIMARY KEY, case_id TEXT NOT NULL REFERENCES cases(case_id),
  option_id INTEGER NOT NULL REFERENCES options(id),
  effect TEXT NOT NULL CHECK(effect IN ('hold','invalidate')),
  reason TEXT NOT NULL,
  source_version_id INTEGER REFERENCES source_versions(id),
  evidence_assessment_id INTEGER REFERENCES evidence_assessments(id),
  created_at TEXT NOT NULL,
  CHECK((source_version_id IS NULL) != (evidence_assessment_id IS NULL))
);
CREATE TABLE IF NOT EXISTS option_safety_flags (
  id INTEGER PRIMARY KEY, case_id TEXT NOT NULL REFERENCES cases(case_id),
  option_id INTEGER NOT NULL REFERENCES options(id),
  category TEXT NOT NULL CHECK(category IN
    ('expression_only','tracer_only','preclinical_only','cross_modal_gap','other')),
  detail TEXT NOT NULL,
  source_version_id INTEGER REFERENCES source_versions(id),
  evidence_assessment_id INTEGER REFERENCES evidence_assessments(id),
  created_at TEXT NOT NULL,
  CHECK(source_version_id IS NULL OR evidence_assessment_id IS NULL)
);
CREATE INDEX IF NOT EXISTS idx_counterevidence_option ON option_counterevidence(option_id);
CREATE INDEX IF NOT EXISTS idx_safety_flags_option ON option_safety_flags(option_id);
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
-- Visit records: plain recorded history, never directives or due dates.
-- visits holds one logical record identity per case; visit_versions holds
-- the append-only version chain. An amendment supersedes the old version
-- and appends a new current version with a previous_id link; history rows
-- are never updated or deleted. review_state is always 'recorded': visits
-- are unreviewed history, never a clinical conclusion or instruction.
CREATE TABLE IF NOT EXISTS visits (
  id INTEGER PRIMARY KEY, case_id TEXT NOT NULL REFERENCES cases(case_id),
  created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS visit_versions (
  id INTEGER PRIMARY KEY, visit_id INTEGER NOT NULL REFERENCES visits(id),
  case_id TEXT NOT NULL REFERENCES cases(case_id),
  version INTEGER NOT NULL,
  recorded_date TEXT NOT NULL,
  visit_type TEXT NOT NULL,
  notes TEXT NOT NULL,
  source_anchor TEXT,
  review_state TEXT NOT NULL CHECK(review_state IN ('recorded')),
  state TEXT NOT NULL CHECK(state IN ('current','superseded')),
  previous_id INTEGER REFERENCES visit_versions(id),
  created_at TEXT NOT NULL,
  UNIQUE(visit_id,version)
);
CREATE INDEX IF NOT EXISTS idx_visits_case ON visits(case_id, id);
CREATE INDEX IF NOT EXISTS idx_visit_versions_visit ON visit_versions(visit_id, version);
CREATE INDEX IF NOT EXISTS idx_visit_versions_case ON visit_versions(case_id, state);
-- Investigation workspace: durable questions that survive amendments and stay
-- linked to exact source versions. Questions are never auto-answered: only an
-- explicit recorded status change moves them, and an amendment only reopens an
-- answered question to needs_review. Links are append-only records; unlinking
-- supersedes a link row, never deletes it. History rows are never updated.
CREATE TABLE IF NOT EXISTS workspace_questions (
  id INTEGER PRIMARY KEY, case_id TEXT NOT NULL REFERENCES cases(case_id),
  question TEXT NOT NULL,
  status TEXT NOT NULL CHECK(status IN ('open','in_progress','answered','needs_review')),
  answer TEXT, created_at TEXT NOT NULL, updated_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS workspace_question_history (
  id INTEGER PRIMARY KEY,
  question_id INTEGER NOT NULL REFERENCES workspace_questions(id),
  case_id TEXT NOT NULL REFERENCES cases(case_id),
  previous_status TEXT CHECK(previous_status IN ('open','in_progress','answered','needs_review')),
  new_status TEXT NOT NULL CHECK(new_status IN ('open','in_progress','answered','needs_review')),
  reason TEXT NOT NULL, answer TEXT, recorded_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS workspace_question_links (
  id INTEGER PRIMARY KEY,
  question_id INTEGER NOT NULL REFERENCES workspace_questions(id),
  case_id TEXT NOT NULL REFERENCES cases(case_id),
  source_version_id INTEGER NOT NULL REFERENCES source_versions(id),
  state TEXT NOT NULL CHECK(state IN ('active','superseded')),
  reason TEXT NOT NULL, created_at TEXT NOT NULL,
  superseded_at TEXT, superseded_reason TEXT
);
CREATE INDEX IF NOT EXISTS idx_workspace_questions_case ON workspace_questions(case_id, id);
CREATE INDEX IF NOT EXISTS idx_workspace_history_question ON workspace_question_history(question_id, id);
CREATE INDEX IF NOT EXISTS idx_workspace_links_question ON workspace_question_links(question_id, id);
CREATE INDEX IF NOT EXISTS idx_workspace_links_source ON workspace_question_links(source_version_id);
-- Consent & identity slice: display and history only. No identity
-- resolution, matching, or cross-case logic. Consent versions are
-- append-only; withdrawal adds a withdrawn version and updates only the
-- current-status pointer. Qualifiers are notes attached to source anchors
-- the case already has; they never alter identity fields.
CREATE TABLE IF NOT EXISTS consent_records (
  id INTEGER PRIMARY KEY, case_id TEXT NOT NULL REFERENCES cases(case_id),
  scope_text TEXT NOT NULL, date_recorded TEXT NOT NULL,
  status TEXT NOT NULL CHECK(status IN ('active','withdrawn')),
  anchor_source_version_id INTEGER REFERENCES source_versions(id),
  review_state TEXT NOT NULL CHECK(review_state IN ('display_only')) DEFAULT 'display_only',
  created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS consent_versions (
  id INTEGER PRIMARY KEY, consent_id INTEGER NOT NULL REFERENCES consent_records(id),
  version INTEGER NOT NULL, status TEXT NOT NULL CHECK(status IN ('active','withdrawn')),
  reason TEXT, date_recorded TEXT NOT NULL, recorded_at TEXT NOT NULL,
  UNIQUE(consent_id, version)
);
CREATE TABLE IF NOT EXISTS identity_qualifiers (
  id INTEGER PRIMARY KEY, case_id TEXT NOT NULL REFERENCES cases(case_id),
  qualifier_text TEXT NOT NULL, anchor_source_version_id INTEGER NOT NULL REFERENCES source_versions(id),
  anchor_line INTEGER, date_recorded TEXT NOT NULL,
  review_state TEXT NOT NULL CHECK(review_state IN ('display_only')) DEFAULT 'display_only',
  created_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_consents_case ON consent_records(case_id);
CREATE INDEX IF NOT EXISTS idx_consent_versions_consent ON consent_versions(consent_id);
CREATE INDEX IF NOT EXISTS idx_identity_qualifiers_case ON identity_qualifiers(case_id);
CREATE INDEX IF NOT EXISTS idx_identity_qualifiers_anchor ON identity_qualifiers(anchor_source_version_id);
-- Evidence quality and limitations (append-only, descriptive only): one row
-- per human-authored note about one exact source version. No rating, score,
-- or inference is stored here; absence of a row means "not assessed", never
-- a guessed quality. Rows are never updated or deleted; an amendment leaves
-- old rows attached to the superseded version.
CREATE TABLE IF NOT EXISTS evidence_quality_assessments (
  id INTEGER PRIMARY KEY, case_id TEXT NOT NULL REFERENCES cases(case_id),
  source_version_id INTEGER NOT NULL REFERENCES source_versions(id),
  assessor_label TEXT NOT NULL,
  date_recorded TEXT NOT NULL,
  completeness_note TEXT NOT NULL,
  limitations_text TEXT NOT NULL,
  conflict_note TEXT NOT NULL,
  created_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_eq_assessments_source ON evidence_quality_assessments(source_version_id);
CREATE INDEX IF NOT EXISTS idx_eq_assessments_case ON evidence_quality_assessments(case_id, source_version_id);
-- Second-opinion and survivorship care records: append-only, amendment-aware,
-- descriptive-only. A second-opinion response is a separate record that never
-- overwrites the original case conclusion; both stay visible side by side.
-- Survivorship items are plain recorded plans, never directives. Rows are
-- never deleted; review_state moves to needs_review when an anchored source
-- version is superseded, and a new request or item is authored instead.
CREATE TABLE IF NOT EXISTS second_opinion_requests (
  id INTEGER PRIMARY KEY, case_id TEXT NOT NULL REFERENCES cases(case_id),
  question_id INTEGER NOT NULL REFERENCES questions(id),
  snapshot_id INTEGER REFERENCES snapshots(id),
  question_text TEXT NOT NULL,
  status TEXT NOT NULL CHECK(status IN ('requested','response_recorded')),
  review_state TEXT NOT NULL CHECK(review_state IN ('pending','reviewed_in_demo','needs_review')),
  created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS second_opinion_materials (
  request_id INTEGER NOT NULL REFERENCES second_opinion_requests(id),
  source_version_id INTEGER NOT NULL REFERENCES source_versions(id),
  PRIMARY KEY(request_id,source_version_id)
);
CREATE TABLE IF NOT EXISTS second_opinion_responses (
  id INTEGER PRIMARY KEY, request_id INTEGER NOT NULL UNIQUE REFERENCES second_opinion_requests(id),
  responder_label TEXT NOT NULL, response_text TEXT NOT NULL,
  anchor_source_version_id INTEGER NOT NULL REFERENCES source_versions(id),
  created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS second_opinion_review_events (
  id INTEGER PRIMARY KEY, request_id INTEGER NOT NULL REFERENCES second_opinion_requests(id),
  reviewer_label TEXT NOT NULL,
  action TEXT NOT NULL CHECK(action IN ('acknowledge')),
  scope TEXT NOT NULL, noted_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS survivorship_plans (
  id INTEGER PRIMARY KEY, case_id TEXT NOT NULL REFERENCES cases(case_id),
  title TEXT NOT NULL, created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS survivorship_items (
  id INTEGER PRIMARY KEY, plan_id INTEGER NOT NULL REFERENCES survivorship_plans(id),
  case_id TEXT NOT NULL REFERENCES cases(case_id),
  kind TEXT NOT NULL CHECK(kind IN ('followup','watch','trigger')),
  description TEXT NOT NULL, recorded_date TEXT,
  anchor_source_version_id INTEGER NOT NULL REFERENCES source_versions(id),
  state TEXT NOT NULL CHECK(state IN ('recorded','triggered')),
  review_state TEXT NOT NULL CHECK(review_state IN ('pending','reviewed_in_demo','needs_review')),
  created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS survivorship_review_events (
  id INTEGER PRIMARY KEY, item_id INTEGER NOT NULL REFERENCES survivorship_items(id),
  reviewer_label TEXT NOT NULL,
  action TEXT NOT NULL CHECK(action IN ('acknowledge')),
  scope TEXT NOT NULL, noted_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_so_requests_case ON second_opinion_requests(case_id);
CREATE INDEX IF NOT EXISTS idx_so_materials_source ON second_opinion_materials(source_version_id);
CREATE INDEX IF NOT EXISTS idx_so_responses_anchor ON second_opinion_responses(anchor_source_version_id);
CREATE INDEX IF NOT EXISTS idx_surv_items_plan ON survivorship_items(plan_id);
CREATE INDEX IF NOT EXISTS idx_surv_items_anchor ON survivorship_items(anchor_source_version_id);
-- Follow-through: human-owned records of agreed case work. The task row
-- holds CURRENT state only; every status change appends one event row
-- with who/when/why, and event rows are never updated or deleted.
-- Completed tasks stay readable as history. Nothing here performs an
-- action: completion is only a recorded acknowledgment path.
CREATE TABLE IF NOT EXISTS followthrough_tasks (
  id INTEGER PRIMARY KEY, case_id TEXT NOT NULL REFERENCES cases(case_id),
  title TEXT NOT NULL, detail TEXT NOT NULL DEFAULT '',
  owner_label TEXT, due_date TEXT, review_trigger TEXT NOT NULL DEFAULT '',
  status TEXT NOT NULL CHECK(status IN ('created','assigned','acknowledged','completed','deferred')),
  question_id INTEGER REFERENCES questions(id),
  source_version_id INTEGER REFERENCES source_versions(id),
  created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS followthrough_task_events (
  id INTEGER PRIMARY KEY, task_id INTEGER NOT NULL REFERENCES followthrough_tasks(id),
  previous_status TEXT CHECK(previous_status IN ('created','assigned','acknowledged','completed','deferred')),
  new_status TEXT NOT NULL CHECK(new_status IN ('created','assigned','acknowledged','completed','deferred')),
  actor_label TEXT NOT NULL, reason TEXT NOT NULL, noted_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_followthrough_tasks_case ON followthrough_tasks(case_id);
CREATE INDEX IF NOT EXISTS idx_followthrough_events_task ON followthrough_task_events(task_id);
-- Clinician review queue sign-off receipts: append-only acknowledgment
-- records. The queue itself is a derived projection over the existing
-- ledger (snapshots, model investigations, amendments, held options,
-- evidence assessments); only these receipts are new durable state.
-- A receipt never authorizes treatment; it records that a person looked.
CREATE TABLE IF NOT EXISTS review_receipts (
  id INTEGER PRIMARY KEY, case_id TEXT NOT NULL REFERENCES cases(case_id),
  queue_key TEXT NOT NULL, kind TEXT NOT NULL
    CHECK(kind IN ('investigation','amendment','held-option','new-evidence')),
  target_id INTEGER NOT NULL, fingerprint TEXT NOT NULL,
  action TEXT NOT NULL CHECK(action IN ('reviewed','acknowledged','returned')),
  reviewer_label TEXT NOT NULL, reason TEXT, created_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_review_receipts_case ON review_receipts(case_id, queue_key);
-- Patient goals + lived experience (Notion vision page 01 slice): durable,
-- source-anchored, amendable patient words. Never a clinical interpretation.
-- Goals and notes are versioned rows; old versions stay with
-- record_state='superseded'. Rows are never deleted. A status change creates
-- a new version, never an overwrite. No diagnosis, staging, or response
-- fields exist anywhere in these tables.
CREATE TABLE IF NOT EXISTS patient_goals (
  id INTEGER PRIMARY KEY, case_id TEXT NOT NULL REFERENCES cases(case_id),
  created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS patient_goal_versions (
  id INTEGER PRIMARY KEY, goal_id INTEGER NOT NULL REFERENCES patient_goals(id),
  version INTEGER NOT NULL,
  statement TEXT NOT NULL,
  stated_date TEXT NOT NULL,
  review_trigger TEXT NOT NULL,
  review_date TEXT,
  status TEXT NOT NULL CHECK(status IN ('active','achieved','changed','abandoned')),
  status_reason TEXT,
  record_state TEXT NOT NULL CHECK(record_state IN ('current','superseded')),
  previous_id INTEGER REFERENCES patient_goal_versions(id),
  created_at TEXT NOT NULL,
  UNIQUE(goal_id,version)
);
CREATE TABLE IF NOT EXISTS patient_notes (
  id INTEGER PRIMARY KEY, case_id TEXT NOT NULL REFERENCES cases(case_id),
  kind TEXT NOT NULL CHECK(kind IN ('lived_experience','symptom')),
  created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS patient_note_versions (
  id INTEGER PRIMARY KEY, note_id INTEGER NOT NULL REFERENCES patient_notes(id),
  version INTEGER NOT NULL,
  note_text TEXT NOT NULL,
  noted_date TEXT NOT NULL,
  record_state TEXT NOT NULL CHECK(record_state IN ('current','superseded')),
  previous_id INTEGER REFERENCES patient_note_versions(id),
  created_at TEXT NOT NULL,
  UNIQUE(note_id,version)
);
CREATE INDEX IF NOT EXISTS idx_patient_goals_case ON patient_goals(case_id);
CREATE INDEX IF NOT EXISTS idx_patient_goal_versions_goal ON patient_goal_versions(goal_id);
CREATE INDEX IF NOT EXISTS idx_patient_notes_case ON patient_notes(case_id);
CREATE INDEX IF NOT EXISTS idx_patient_note_versions_note ON patient_note_versions(note_id);
-- Option portfolio slice: append-only documented reasons (objections,
-- deferrals, reservations) and four-dimension reviewable notes. A derived
-- projection over the existing ledger like OI-021: no second canonical
-- state, no recommendation, and no eligibility/benefit/authorization
-- declaration. Rows are never deleted; open items change only through
-- recorded resolve/reopen/acknowledge events, and terminal or held entries
-- stay visible with their recorded reasons.
CREATE TABLE IF NOT EXISTS option_flags (
  id INTEGER PRIMARY KEY, option_id INTEGER NOT NULL REFERENCES options(id),
  kind TEXT NOT NULL CHECK(kind IN ('objection','deferred','reserved')),
  label TEXT NOT NULL, reason TEXT NOT NULL,
  source_version_id INTEGER REFERENCES source_versions(id),
  evidence_assessment_id INTEGER REFERENCES evidence_assessments(id),
  state TEXT NOT NULL CHECK(state IN ('open','resolved')),
  created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS option_flag_events (
  id INTEGER PRIMARY KEY, flag_id INTEGER NOT NULL REFERENCES option_flags(id),
  reviewer_label TEXT NOT NULL,
  action TEXT NOT NULL CHECK(action IN ('raise','resolve','reopen')),
  scope TEXT NOT NULL, noted_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS option_dimension_notes (
  id INTEGER PRIMARY KEY, option_id INTEGER NOT NULL REFERENCES options(id),
  dimension TEXT NOT NULL CHECK(dimension IN
    ('scientific_plausibility','technical_feasibility','access','clinical_authorization')),
  note TEXT NOT NULL, anchor TEXT NOT NULL,
  source_version_id INTEGER REFERENCES source_versions(id),
  evidence_assessment_id INTEGER REFERENCES evidence_assessments(id),
  reviewer_label TEXT NOT NULL,
  state TEXT NOT NULL CHECK(state IN ('pending','acknowledged')),
  created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS option_dimension_events (
  id INTEGER PRIMARY KEY, note_id INTEGER NOT NULL REFERENCES option_dimension_notes(id),
  reviewer_label TEXT NOT NULL,
  action TEXT NOT NULL CHECK(action IN ('record','acknowledge')),
  scope TEXT NOT NULL, noted_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_option_flags_option ON option_flags(option_id);
CREATE INDEX IF NOT EXISTS idx_option_flags_source ON option_flags(source_version_id);
CREATE INDEX IF NOT EXISTS idx_option_flags_assessment ON option_flags(evidence_assessment_id);
CREATE INDEX IF NOT EXISTS idx_option_flag_events_flag ON option_flag_events(flag_id);
CREATE INDEX IF NOT EXISTS idx_option_dim_notes_option ON option_dimension_notes(option_id);
CREATE INDEX IF NOT EXISTS idx_option_dim_events_note ON option_dimension_events(note_id);
-- Longitudinal biological explanation: human-authored, source-anchored
-- context records inside the existing case model, NOT a second ledger.
-- Explanations are never auto-superseded: competing hypotheses for one
-- question survive side by side as separate rows. Assay observations each
-- cite exactly one tissue block (or explicitly unknown), so assays from
-- different blocks can never silently pool. Both tables go stale
-- anchor-exactly on source amendment, like snapshots and inventory rows.
-- No rollup is ever computed: readers see each row with its own anchor,
-- context, and state. Nothing here states staging, grading, variant
-- interpretation, or response/progression; guarded text rejects that language.
CREATE TABLE IF NOT EXISTS bio_explanations (
  id INTEGER PRIMARY KEY, case_id TEXT NOT NULL REFERENCES cases(case_id),
  question_id INTEGER NOT NULL REFERENCES questions(id),
  label TEXT NOT NULL, mechanism_text TEXT NOT NULL,
  episode_id TEXT NOT NULL,
  specimen_state TEXT NOT NULL CHECK(specimen_state IN ('recorded','unknown')),
  specimen_id TEXT,
  lesion_state TEXT NOT NULL CHECK(lesion_state IN ('recorded','unknown')),
  lesion_id TEXT,
  clinical_context_state TEXT NOT NULL CHECK(clinical_context_state IN ('known','unknown')),
  clinical_context_value TEXT,
  source_version_id INTEGER NOT NULL REFERENCES source_versions(id),
  state TEXT NOT NULL CHECK(state IN ('current','stale')), created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS bio_assay_observations (
  id INTEGER PRIMARY KEY, case_id TEXT NOT NULL REFERENCES cases(case_id),
  explanation_id INTEGER NOT NULL REFERENCES bio_explanations(id),
  method_label TEXT NOT NULL,
  tissue_block_state TEXT NOT NULL CHECK(tissue_block_state IN ('recorded','unknown')),
  tissue_block_asset_id INTEGER REFERENCES biological_assets(id),
  matched_control_state TEXT NOT NULL CHECK(matched_control_state IN ('recorded','missing','unknown')),
  matched_control_specimen TEXT,
  reference_kind TEXT NOT NULL CHECK(reference_kind IN ('patient_normal','external_population','unknown')),
  result_note TEXT NOT NULL,
  source_version_id INTEGER NOT NULL REFERENCES source_versions(id),
  state TEXT NOT NULL CHECK(state IN ('current','stale')), created_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_bio_explanations_case ON bio_explanations(case_id, question_id);
CREATE INDEX IF NOT EXISTS idx_bio_explanations_source ON bio_explanations(source_version_id);
CREATE INDEX IF NOT EXISTS idx_bio_assay_case ON bio_assay_observations(case_id, explanation_id);
CREATE INDEX IF NOT EXISTS idx_bio_assay_source ON bio_assay_observations(source_version_id);
CREATE INDEX IF NOT EXISTS idx_bio_assay_block ON bio_assay_observations(tissue_block_asset_id);
-- B-01 fictional-actor grants: workflow governance for the synthetic case
-- workspace, NOT identity proofing, NOT credential verification, NOT a
-- production-security control. A grant authorizes one fictional actor for one
-- case under one stated purpose inside a date window; revocation marks the
-- row, never deletes it. Access grants and content rights (rights.py) are
-- distinct systems; neither references the other.
CREATE TABLE IF NOT EXISTS actor_grants (
  id INTEGER PRIMARY KEY, actor_id TEXT NOT NULL,
  case_id TEXT NOT NULL REFERENCES cases(case_id),
  purpose TEXT NOT NULL, granted_at TEXT NOT NULL, expires_at TEXT NOT NULL,
  revoked_at TEXT, created_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_actor_grants_lookup ON actor_grants(actor_id, case_id, purpose);
-- Audit of case-route access decisions. Deliberately NO foreign key on
-- case_id: attempts against unknown case ids are logged too. Rows record
-- actor/case/route/result only — never source text, quotes, or finding keys.
CREATE TABLE IF NOT EXISTS access_log (
  id INTEGER PRIMARY KEY, actor TEXT NOT NULL, case_id TEXT NOT NULL,
  route TEXT NOT NULL, result TEXT NOT NULL CHECK(result IN ('allowed','denied')),
  occurred_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_access_log_case ON access_log(case_id, id);
-- Slice 1 local demo accounts and sessions. Accounts are operator-created
-- local labels (display name, role, status), never verified identities.
-- Passwords are stored only as pbkdf2_hmac digests with a per-account salt;
-- plaintext is never stored. A patient account binds to one case at
-- creation (own_case_id); the operator assigns it. Sessions store only a
-- SHA-256 hash of the token; the token itself is never stored. Revocation
-- marks rows, never deletes them.
CREATE TABLE IF NOT EXISTS accounts (
  account_id TEXT PRIMARY KEY,
  display_name TEXT NOT NULL,
  role TEXT NOT NULL CHECK(role IN ('operator','clinician','patient','auditor')),
  status TEXT NOT NULL CHECK(status IN ('active','disabled')),
  own_case_id TEXT REFERENCES cases(case_id),
  password_hash TEXT, password_salt TEXT,
  created_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_accounts_role ON accounts(role, status);
CREATE TABLE IF NOT EXISTS sessions (
  token_hash TEXT PRIMARY KEY,
  account_id TEXT NOT NULL REFERENCES accounts(account_id),
  expires_at TEXT NOT NULL, revoked_at TEXT, created_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_sessions_account ON sessions(account_id, expires_at);
-- B-08 contradiction synthesis: human-entered limitation notes on one
-- evidence assessment or one broker link. Append-only: rows are never
-- updated or deleted, so note history is preserved. Notes are descriptive
-- text only; no quality number is computed anywhere in this slice.
CREATE TABLE IF NOT EXISTS limitation_notes (
  id INTEGER PRIMARY KEY, case_id TEXT NOT NULL REFERENCES cases(case_id),
  question_id INTEGER NOT NULL REFERENCES questions(id),
  assessment_id INTEGER REFERENCES evidence_assessments(id),
  broker_link_id INTEGER REFERENCES broker_links(id),
  note TEXT NOT NULL, author_label TEXT NOT NULL, created_at TEXT NOT NULL,
  CHECK ((assessment_id IS NOT NULL AND broker_link_id IS NULL)
      OR (assessment_id IS NULL AND broker_link_id IS NOT NULL))
);
CREATE INDEX IF NOT EXISTS idx_limitation_notes_question ON limitation_notes(case_id, question_id);
CREATE INDEX IF NOT EXISTS idx_limitation_notes_targets ON limitation_notes(assessment_id, broker_link_id);
-- B-04 scoped human review: per-snapshot scope notes (extraction vs
-- interpretation decided independently), per-claim dissent, and handoff.
-- All three tables are append-only: rows are inserted, never updated or
-- deleted, and no write path copies them across snapshots or cases. Each
-- row pins the snapshot basis (source/evidence/broker ids) it was recorded
-- against, so pins stay readable as history after an amendment while the
-- replacement draft starts unreviewed. Record-state notes only: never a
-- credential check, a clinical sign-off, or a treatment decision.
CREATE TABLE IF NOT EXISTS scoped_review_decisions (
  id INTEGER PRIMARY KEY, case_id TEXT NOT NULL REFERENCES cases(case_id),
  snapshot_id INTEGER NOT NULL REFERENCES snapshots(id),
  reviewer_label TEXT NOT NULL,
  scope TEXT NOT NULL CHECK(scope IN ('extraction_accepted','interpretation_endorsed','left_open')),
  source_version_ids TEXT NOT NULL, evidence_assessment_ids TEXT NOT NULL,
  broker_link_ids TEXT NOT NULL,
  note TEXT NOT NULL, decided_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS scoped_review_dissents (
  id INTEGER PRIMARY KEY, case_id TEXT NOT NULL REFERENCES cases(case_id),
  snapshot_id INTEGER NOT NULL REFERENCES snapshots(id),
  reviewer_label TEXT NOT NULL, claim_ref TEXT NOT NULL,
  source_version_ids TEXT NOT NULL, rationale TEXT NOT NULL, dissented_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS scoped_review_handoffs (
  id INTEGER PRIMARY KEY, case_id TEXT NOT NULL REFERENCES cases(case_id),
  snapshot_id INTEGER NOT NULL REFERENCES snapshots(id),
  from_reviewer TEXT NOT NULL, to_reviewer TEXT NOT NULL,
  source_version_ids TEXT NOT NULL, prior_decision_ids TEXT NOT NULL,
  handed_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_scoped_decisions_snapshot ON scoped_review_decisions(snapshot_id);
CREATE INDEX IF NOT EXISTS idx_scoped_dissents_snapshot ON scoped_review_dissents(snapshot_id);
CREATE INDEX IF NOT EXISTS idx_scoped_handoffs_snapshot ON scoped_review_handoffs(snapshot_id);
-- B-02 owned re-review tasks: one append-only row per newly stale snapshot.
-- A task pins the prior snapshot, the superseding version (when the cause is
-- an amendment), the mechanical finding-key diff, the invalidating event, and
-- a fictional assignee label. A task closes only by referencing a new draft
-- bound to current sources or by recording an explicit no-change note.
-- Completion sets the close fields and appends an event row; rows are never
-- deleted. No task path changes any snapshot's state.
CREATE TABLE IF NOT EXISTS re_review_tasks (
  id INTEGER PRIMARY KEY, case_id TEXT NOT NULL REFERENCES cases(case_id),
  snapshot_id INTEGER NOT NULL REFERENCES snapshots(id),
  question_id INTEGER NOT NULL REFERENCES questions(id),
  cause TEXT NOT NULL CHECK(cause IN ('source_amendment','evidence_change','revocation','correction','review')),
  superseding_source_version_id INTEGER REFERENCES source_versions(id),
  superseded_source_version_id INTEGER REFERENCES source_versions(id),
  finding_diff_json TEXT NOT NULL,
  evidence_version_id INTEGER REFERENCES evidence_versions(id),
  rights_source_id INTEGER REFERENCES rights_sources(id),
  superseding_rights_source_id INTEGER REFERENCES rights_sources(id),
  broker_link_id INTEGER REFERENCES broker_links(id),
  invalidating_event_id INTEGER NOT NULL REFERENCES events(id),
  assignee_label TEXT NOT NULL,
  due_date TEXT,
  status TEXT NOT NULL CHECK(status IN ('open','done')),
  close_note TEXT,
  closing_snapshot_id INTEGER REFERENCES snapshots(id),
  created_at TEXT NOT NULL, closed_at TEXT
);
CREATE INDEX IF NOT EXISTS idx_re_review_tasks_case ON re_review_tasks(case_id, status, id);
CREATE INDEX IF NOT EXISTS idx_re_review_tasks_snapshot ON re_review_tasks(snapshot_id);
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
        # B-09: append-only completion receipts; IF NOT EXISTS keeps old DBs intact.
        self.db.executescript(task_receipts.RECEIPT_SCHEMA)
        self._migrate_discovery_rights()
        self._migrate_owned_questions()

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

    def _migrate_owned_questions(self) -> None:
        """Add B-06 owner/triage columns to pre-existing questions tables.

        Fresh databases get the columns from SCHEMA. Databases created by
        earlier slices keep every row; old questions surface with no owner
        and triage 'unsorted'. This migrates only the questions table;
        the new history/note tables arrive via CREATE TABLE IF NOT EXISTS.
        """
        migrations = (
            ("questions", "owner_label",
             "ALTER TABLE questions ADD COLUMN owner_label TEXT"),
            ("questions", "triage",
             "ALTER TABLE questions ADD COLUMN triage TEXT NOT NULL DEFAULT 'unsorted' "
             "CHECK(triage IN ('unsorted','owned','awaiting_evidence','ready_for_review'))"),
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

    def _event(self, case_id: str, kind: str, **details: object) -> int:
        cur = self.db.execute("INSERT INTO events (case_id,kind,details,occurred_at) VALUES (?,?,?,?)",
                              (case_id, kind, json.dumps(details, sort_keys=True), now_utc()))
        return int(cur.lastrowid)

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

    # Route decisions (program plan C3): a route.decided event is the
    # ledger record of an assignment. The orchestrator builds and
    # validates the record; the store only appends it to the existing
    # events ledger and reads it back. No second ledger is created.
    def record_route_decided(self, case_id: str, route_record: dict) -> int:
        """Append a validated route.decided event; return its event id."""
        from .orchestrator import validate_route_record
        self._case(case_id)
        record = validate_route_record(route_record)
        with self.db:
            return self._event(case_id, "route.decided", **record)

    def get_route_decided(self, case_id: str, route_id: str) -> dict | None:
        """Latest route.decided record for a route id, or None.

        A plain ledger read: the record is returned as stored. Callers
        that enforce on it validate through the orchestrator.
        """
        self._case(case_id)
        rows = self.db.execute(
            """SELECT id, details FROM events
            WHERE case_id=? AND kind='route.decided' ORDER BY id DESC""",
            (case_id,),
        ).fetchall()
        for row in rows:
            try:
                record = json.loads(row[1])
            except (json.JSONDecodeError, TypeError):
                continue
            if isinstance(record, dict) and record.get("routeId") == route_id:
                # The event id does not exist until the insert, so the
                # stored record carries None; the row id is the event id.
                record["eventId"] = int(row[0])
                return record
        return None

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

    # ---- B-01 fictional-actor grants (workflow governance, not identity) ----
    # Free-text labels (reviewer_label, owner_label, asserted_by) remain
    # non-authoritative attribution after this slice; they are never consulted
    # here. Grants never touch rights.py: access grants and content rights are
    # distinct systems.

    def require_case(self, case_id: str) -> str:
        """Public existence check with the existing unknown-case contract.

        The HTTP grant gate calls this BEFORE any grant check so unknown case
        ids keep returning 422 "Unknown case" (no new existence oracle).
        """
        return self._case(case_id)

    def create_grant(self, actor_id: str, case_id: str, purpose: str,
                     granted_at: str, expires_at: str) -> int:
        """Record one fictional-actor grant row (ledger insert, never an edit).

        Mirrors the AuthorizationReceipt field discipline in patient_access.py:
        purpose/scope(case)/window/revocation. `individual-access` is the
        purpose the case routes require; other exact-token purposes may exist
        but authorize no case route in this slice.
        """
        actor_id = valid_id(actor_id)
        self._case(case_id)
        purpose = valid_purpose(purpose)
        granted_at = valid_date(granted_at)
        expires_at = valid_date(expires_at)
        if expires_at < granted_at:
            raise InvalidInput("Grant expiry precedes grant start")
        with self.db:
            self.db.execute("BEGIN IMMEDIATE")
            cur = self.db.execute("""INSERT INTO actor_grants
                (actor_id,case_id,purpose,granted_at,expires_at,revoked_at,created_at)
                VALUES (?,?,?,?,?,NULL,?)""",
                (actor_id, case_id, purpose, granted_at, expires_at, now_utc()))
            self._event(case_id, "actor_grant_created", grant_id=cur.lastrowid,
                        actor_id=actor_id, purpose=purpose, expires_at=expires_at)
            return int(cur.lastrowid)

    def revoke_grant(self, grant_id: int, reason: str) -> dict:
        """Mark a grant revoked (supersede-never-delete: the row stays).

        Revocation blocks future reads. It deletes nothing: previously
        imported sources, events, review events, and snapshot rows are
        untouched, and still-authorized actors keep querying them.
        """
        if type(grant_id) is not int or grant_id < 1:
            raise InvalidInput("Invalid grant ID")
        if not isinstance(reason, str) or not 10 <= len(reason.strip()) <= 600:
            raise InvalidInput("Revocation requires a 10–600 character reason")
        with self.db:
            self.db.execute("BEGIN IMMEDIATE")
            row = self.db.execute("SELECT case_id,revoked_at FROM actor_grants WHERE id=?",
                                  (grant_id,)).fetchone()
            if not row:
                raise InvalidInput("Grant not found")
            if row["revoked_at"] is not None:
                return {"result": "revoked", "grant_id": grant_id, "duplicate": True}
            self.db.execute("UPDATE actor_grants SET revoked_at=? WHERE id=?",
                            (now_utc(), grant_id))
            self._event(row["case_id"], "actor_grant_revoked",
                        grant_id=grant_id, reason=reason.strip())
            return {"result": "revoked", "grant_id": grant_id}

    def has_active_grant(self, actor_id: str, case_id: str, purpose: str) -> bool:
        """True only for a live grant: exact (actor, case, purpose) triple,
        inside the [granted_at, expires_at] window, not revoked. Deny by
        default: anything else — unknown actor, other purpose, expired,
        revoked — is False. Never raises for unknown ids."""
        if not isinstance(actor_id, str) or not isinstance(case_id, str) \
                or not isinstance(purpose, str):
            return False
        today = today_utc()
        row = self.db.execute("""SELECT 1 FROM actor_grants
            WHERE actor_id=? AND case_id=? AND purpose=? AND revoked_at IS NULL
            AND granted_at<=? AND expires_at>=? LIMIT 1""",
            (actor_id, case_id, purpose, today, today)).fetchone()
        return row is not None

    def granted_cases(self, actor_id: str, purpose: str) -> list[dict]:
        """Cases this fictional actor may list: same row shape as cases(),
        filtered to live grants. Empty list when none — never an error."""
        if not isinstance(actor_id, str) or not isinstance(purpose, str):
            return []
        today = today_utc()
        return self._dicts(self.db.execute(
            """SELECT c.case_id,c.label,c.synthetic FROM cases c WHERE EXISTS (
                SELECT 1 FROM actor_grants g WHERE g.actor_id=? AND g.case_id=c.case_id
                AND g.purpose=? AND g.revoked_at IS NULL
                AND g.granted_at<=? AND g.expires_at>=?)
            ORDER BY c.case_id""", (actor_id, purpose, today, today)).fetchall())

    ACCESS_RESULTS = frozenset({"allowed", "denied"})

    def record_access(self, actor_label: str, case_id: str, route: str, result: str) -> int:
        """Append one access-decision row. Arguments are identifiers only —
        never source text, quotes, or finding keys — so the log cannot leak
        case content. Unknown case ids are loggable by design."""
        if not isinstance(actor_label, str) or not 1 <= len(actor_label) <= 128:
            raise InvalidInput("Access log actor label must have 1–128 characters")
        valid_id(case_id)
        if not isinstance(route, str) or not route.startswith("/api/cases/") or len(route) > 256:
            raise InvalidInput("Access log route must be a case route path")
        if result not in self.ACCESS_RESULTS:
            raise InvalidInput("Access log result must be allowed or denied")
        with self.db:
            self.db.execute("BEGIN IMMEDIATE")
            cur = self.db.execute("""INSERT INTO access_log
                (actor,case_id,route,result,occurred_at) VALUES (?,?,?,?,?)""",
                (actor_label, case_id, route, result, now_utc()))
            return int(cur.lastrowid)

    def access_log(self, case_id: str) -> list[dict]:
        """Access-decision rows for one case (per-case isolation preserved)."""
        self._case(case_id)
        return self._dicts(self.db.execute(
            "SELECT id,actor,case_id,route,result,occurred_at FROM access_log "
            "WHERE case_id=? ORDER BY id", (case_id,)).fetchall())

    # -- Slice 1 local demo accounts and sessions -------------------------
    # Accounts are operator-created local labels, not verified identities.
    # An account id doubles as the B-01 actor id, so seeded grants keep
    # working unchanged when the demo actor becomes a demo account.

    @staticmethod
    def _public_account(row: sqlite3.Row) -> dict:
        """Account row without credential material (never leaves the store)."""
        return {"account_id": row["account_id"], "display_name": row["display_name"],
                "role": row["role"], "status": row["status"],
                "own_case_id": row["own_case_id"], "created_at": row["created_at"]}

    @staticmethod
    def _hash_password(password: str, salt: bytes) -> str:
        return hashlib.pbkdf2_hmac(
            "sha256", password.encode("utf-8"), salt, _PBKDF2_ITERATIONS).hex()

    def create_account(self, account_id: str, display_name: str, role: str,
                       password: str | None = None,
                       own_case_id: str | None = None) -> dict:
        """Operator-created account. Password is optional at creation: an
        account without one cannot sign in until an operator sets it.
        A patient account must bind to exactly one case at creation; other
        roles bind to no case."""
        account_id = valid_id(account_id)
        if not isinstance(display_name, str) or not 1 <= len(display_name.strip()) <= 128:
            raise InvalidInput("Account display name must have 1–128 characters")
        if role not in ACCOUNT_ROLES:
            raise InvalidInput("Account role must be operator, clinician, patient, or auditor")
        if role == "patient":
            if own_case_id is None:
                raise InvalidInput("A patient account binds to one case at creation")
            self._case(own_case_id)
        elif own_case_id is not None:
            raise InvalidInput("Only a patient account binds to a case")
        if password is not None:
            if not isinstance(password, str) or len(password) < PASSWORD_MIN_LENGTH:
                raise InvalidInput(
                    f"Account password must have at least {PASSWORD_MIN_LENGTH} characters")
        password_hash = password_salt = None
        if password is not None:
            salt = secrets.token_bytes(16)
            password_salt = salt.hex()
            password_hash = self._hash_password(password, salt)
        with self.db:
            self.db.execute("BEGIN IMMEDIATE")
            existing = self.db.execute(
                "SELECT 1 FROM accounts WHERE account_id=?", (account_id,)).fetchone()
            if existing is not None:
                raise InvalidInput("Account already exists")
            self.db.execute(
                """INSERT INTO accounts
                   (account_id,display_name,role,status,own_case_id,
                    password_hash,password_salt,created_at)
                   VALUES (?,?,?,'active',?,?,?,?)""",
                (account_id, display_name.strip(), role, own_case_id,
                 password_hash, password_salt, now_utc()))
            row = self.db.execute(
                "SELECT * FROM accounts WHERE account_id=?", (account_id,)).fetchone()
            return self._public_account(row)

    def set_account_password(self, account_id: str, password: str) -> dict:
        """Operator-set password for an existing account. No password is ever
        stored or returned; only its salted digest is kept."""
        account_id = valid_id(account_id)
        if not isinstance(password, str) or len(password) < PASSWORD_MIN_LENGTH:
            raise InvalidInput(
                f"Account password must have at least {PASSWORD_MIN_LENGTH} characters")
        salt = secrets.token_bytes(16)
        with self.db:
            self.db.execute("BEGIN IMMEDIATE")
            cur = self.db.execute(
                "UPDATE accounts SET password_hash=?, password_salt=? WHERE account_id=?",
                (self._hash_password(password, salt), salt.hex(), account_id))
            if cur.rowcount == 0:
                raise InvalidInput("Account not found")
            row = self.db.execute(
                "SELECT * FROM accounts WHERE account_id=?", (account_id,)).fetchone()
            return self._public_account(row)

    def set_account_status(self, account_id: str, status: str) -> dict:
        """Disable or re-enable an account. Disabling also revokes every
        live session for the account; the rows stay for audit."""
        account_id = valid_id(account_id)
        if status not in ("active", "disabled"):
            raise InvalidInput("Account status must be active or disabled")
        with self.db:
            self.db.execute("BEGIN IMMEDIATE")
            cur = self.db.execute(
                "UPDATE accounts SET status=? WHERE account_id=?", (status, account_id))
            if cur.rowcount == 0:
                raise InvalidInput("Account not found")
            if status == "disabled":
                self.db.execute(
                    "UPDATE sessions SET revoked_at=? WHERE account_id=? AND revoked_at IS NULL",
                    (now_utc(), account_id))
            row = self.db.execute(
                "SELECT * FROM accounts WHERE account_id=?", (account_id,)).fetchone()
            return self._public_account(row)

    def get_account(self, account_id: str) -> dict | None:
        """Public account record, or None when unknown. Never raises for
        unknown ids and never exposes credential material."""
        if not isinstance(account_id, str):
            return None
        row = self.db.execute(
            "SELECT * FROM accounts WHERE account_id=?", (account_id,)).fetchone()
        return None if row is None else self._public_account(row)

    def list_accounts(self) -> list[dict]:
        """All accounts, ordered by id, without credential material."""
        return [self._public_account(row) for row in self.db.execute(
            "SELECT * FROM accounts ORDER BY account_id").fetchall()]

    def verify_password(self, account_id: str, password: str) -> bool:
        """True only for an active account with a set password that matches.
        Deny by default: unknown, disabled, or passwordless accounts are
        False. Never raises for unknown ids."""
        if not isinstance(account_id, str) or not isinstance(password, str):
            return False
        row = self.db.execute(
            "SELECT * FROM accounts WHERE account_id=?", (account_id,)).fetchone()
        if row is None or row["status"] != "active":
            return False
        if row["password_hash"] is None or row["password_salt"] is None:
            return False
        try:
            salt = bytes.fromhex(row["password_salt"])
        except ValueError:
            return False
        digest = self._hash_password(password, salt)
        return hmac.compare_digest(digest, row["password_hash"])

    def issue_session(self, account_id: str) -> tuple[str, dict]:
        """Create a 24-hour session for an active account. Returns the bearer
        token (never stored; only its hash is kept) and the session record."""
        account = self.get_account(account_id)
        if account is None or account["status"] != "active":
            raise InvalidInput("Account is disabled or missing")
        token = secrets.token_urlsafe(32)
        token_hash = hashlib.sha256(token.encode("ascii")).hexdigest()
        created = datetime.now(timezone.utc)
        expires = (created + timedelta(seconds=SESSION_TTL_SECONDS)).isoformat(timespec="seconds")
        with self.db:
            self.db.execute("BEGIN IMMEDIATE")
            self.db.execute(
                """INSERT INTO sessions (token_hash,account_id,expires_at,revoked_at,created_at)
                   VALUES (?,?,?,NULL,?)""",
                (token_hash, account_id, expires, created.isoformat(timespec="seconds")))
        return token, {"account_id": account_id, "expires_at": expires,
                       "created_at": created.isoformat(timespec="seconds")}

    def validate_session(self, token: str) -> dict | None:
        """Account for a live session token, or None. Expired and revoked
        sessions are None. Never raises for malformed tokens."""
        if not isinstance(token, str) or not token:
            return None
        token_hash = hashlib.sha256(token.encode("utf-8", errors="ignore")).hexdigest()
        row = self.db.execute(
            """SELECT a.* FROM sessions s JOIN accounts a ON a.account_id=s.account_id
               WHERE s.token_hash=? AND s.revoked_at IS NULL AND s.expires_at>?""",
            (token_hash, now_utc())).fetchone()
        if row is None:
            return None
        if row["status"] != "active":
            return None
        return self._public_account(row)

    def revoke_session(self, token: str) -> bool:
        """Revoke one session token. True when a live session was revoked."""
        if not isinstance(token, str) or not token:
            return False
        token_hash = hashlib.sha256(token.encode("utf-8", errors="ignore")).hexdigest()
        with self.db:
            self.db.execute("BEGIN IMMEDIATE")
            cur = self.db.execute(
                "UPDATE sessions SET revoked_at=? WHERE token_hash=? AND revoked_at IS NULL",
                (now_utc(), token_hash))
            return cur.rowcount > 0

    def revoke_account_sessions(self, account_id: str) -> int:
        """Revoke every live session for one account. Returns the count."""
        if not isinstance(account_id, str):
            return 0
        with self.db:
            self.db.execute("BEGIN IMMEDIATE")
            cur = self.db.execute(
                "UPDATE sessions SET revoked_at=? WHERE account_id=? AND revoked_at IS NULL",
                (now_utc(), account_id))
            return int(cur.rowcount)


    def _stale_case_model_investigations(self, case_id: str) -> list[int]:
        """Invalidate model runs when their case-wide source context changes.

        Every live/replay prompt can inspect current case assertions. Its final
        citations, or even an abstention with no claims, are not a complete
        dependency record. Until captured input dependencies are persisted,
        source imports conservatively stale all current runs for THIS case.
        Independently authored snapshots retain anchor-specific invalidation.
        Caller owns the source-import transaction; no extra event is emitted.
        """
        if not self.db.in_transaction:
            raise InvalidInput("Model invalidation requires the source transaction")
        rows = self.db.execute(
            "SELECT id FROM investigations WHERE case_id=? AND stale=0 ORDER BY id",
            (case_id,)).fetchall()
        if not rows:
            return []
        # Reopen only questions belonging to runs that are newly stale.
        self.db.execute(
            """UPDATE questions SET state='open' WHERE case_id=? AND id IN
            (SELECT question_id FROM investigations WHERE case_id=? AND stale=0)""",
            (case_id, case_id))
        self.db.execute(
            "UPDATE investigations SET stale=1 WHERE case_id=? AND stale=0",
            (case_id,))
        return [int(row["id"]) for row in rows]

    def import_report(self, case_id: str, raw: bytes, *,
                      assignee_label: str | None = None, due_date: str | None = None) -> dict:
        """Durably ingest bytes. An explicit amendment is required for changed text.

        Unknown/cross-case patient data is quarantined, never asserted as fact.
        The transaction includes invalidation; duplicates cannot emit events.
        An amendment that marks snapshots stale also opens one re-review task
        per newly stale snapshot in the same transaction.
        """
        case_id = self._case(case_id)
        report = parse_report(raw)
        digest = hashlib.sha256(raw).hexdigest()
        with self.db:
            self.db.execute("BEGIN IMMEDIATE")
            return self._import_report_in_transaction(
                case_id, raw, report, digest,
                assignee_label=assignee_label, due_date=due_date)

    def preview_document(self, case_id: str, raw: bytes, filename: str) -> dict:
        """Read-only plain-text preview; no inferred assertions or persistent upload."""
        from .document_intake import preview_text
        case_id = self._case(case_id)
        return {"case_id": case_id, **preview_text(raw, filename)}

    def _document_intake_receipts(self, case_id: str) -> dict[int, dict]:
        """Read existing source-linked receipts inside the caller snapshot."""
        rows = self._dicts(self.db.execute(
            """SELECT d.* FROM document_intake_metadata d
            JOIN source_versions s ON s.id=d.source_version_id WHERE s.case_id=?""",
            (case_id,)).fetchall())
        receipts = {}
        for row in rows:
            source_id = row.pop("source_version_id")
            row["manual_transcription_confirmed"] = bool(row["manual_transcription_confirmed"])
            receipts[source_id] = row
        return receipts

    def import_document(self, case_id: str, raw: bytes, filename: str,
                        metadata: dict, findings: list[dict],
                        expected_sha256: str, confirmed_case_id: str) -> dict:
        """Commit explicitly confirmed manual transcription to the original ledger.

        The reviewed annotations are immutable for a given original. A filename
        change is an idempotent retry, retaining the original upload filename.
        All source, freshness, event and intake receipt writes share one lock.
        """
        from .document_intake import review_text
        case_id = self._case(case_id)
        report, receipt = review_text(case_id, raw, filename, metadata, findings,
                                      expected_sha256, confirmed_case_id)
        digest = hashlib.sha256(raw).hexdigest()
        with self.db:
            self.db.execute("BEGIN IMMEDIATE")
            # Check the original across this case, so changing a document ID
            # cannot silently reuse identical bytes with different annotations.
            duplicate = self.db.execute(
                """SELECT s.id,s.version,d.review_sha256 FROM source_versions s
                LEFT JOIN document_intake_metadata d ON d.source_version_id=s.id
                WHERE s.case_id=? AND s.sha256=? ORDER BY s.id LIMIT 1""",
                (case_id, digest)).fetchone()
            if duplicate is not None:
                if duplicate["review_sha256"] != receipt["review_sha256"]:
                    raise InvalidInput("Original bytes already exist with different metadata or findings")
                return {"result": "duplicate", "source_id": duplicate["id"], "version": duplicate["version"]}
            result = self._import_report_in_transaction(case_id, raw, report, digest)
            self.db.execute(
                """INSERT INTO document_intake_metadata
                (source_version_id,filename,media_type,extraction_method,annotation_method,
                 manual_transcription_confirmed,clinical_review,review_sha256)
                VALUES (?,?,?,?,?,?,?,?)""",
                (result["source_id"], receipt["filename"], receipt["media_type"],
                 receipt["extraction_method"], receipt["annotation_method"],
                 int(receipt["manual_transcription_confirmed"]), receipt["clinical_review"],
                 receipt["review_sha256"]))
            self._event(case_id, "document_transcription_confirmed",
                        source_id=result["source_id"], sha256=digest,
                        review_sha256=receipt["review_sha256"],
                        extraction_method=receipt["extraction_method"],
                        annotation_method=receipt["annotation_method"],
                        clinical_review="not_performed")
            return result

    def _import_report_in_transaction(self, case_id: str, raw: bytes,
                                      report: ParsedReport, digest: str, *,
                                      assignee_label: str | None = None,
                                      due_date: str | None = None) -> dict:
        """Shared source/version/assertion persistence under the caller write lock."""
        if not self.db.in_transaction:
            raise InvalidInput("Source import requires its owning write transaction")
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
        invalidated_workspace = []
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
            # Investigation workspace, same transaction: only ANSWERED
            # questions in THIS case with an ACTIVE link to the superseded
            # version reopen to needs_review. The system never answers a
            # question; it only asks for another human review, preserving
            # the prior answer in history.
            invalidated_workspace = self._reopen_workspace_questions(
                case_id, previous["id"], report.document_id, version)
        # Even a new, non-amended source can change the model's case-wide input.
        newly_stale_model_ids = self._stale_case_model_investigations(case_id)
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
        invalidated_bio_explanations = []
        invalidated_bio_assays = []
        if previous:
            # Anchor-exact, like snapshots and inventory rows: only
            # explanations and assay observations citing the superseded
            # version go stale. Competing hypotheses on other versions
            # survive untouched, and history is preserved.
            invalidated_bio_explanations = [row[0] for row in self.db.execute(
                """SELECT id FROM bio_explanations
                WHERE case_id=? AND source_version_id=? AND state='current'""",
                (case_id, previous["id"])).fetchall()]
            if invalidated_bio_explanations:
                marks = ",".join("?" for _ in invalidated_bio_explanations)
                self.db.execute(f"UPDATE bio_explanations SET state='stale' WHERE id IN ({marks})",
                                invalidated_bio_explanations)
            invalidated_bio_assays = [row[0] for row in self.db.execute(
                """SELECT id FROM bio_assay_observations
                WHERE case_id=? AND source_version_id=? AND state='current'""",
                (case_id, previous["id"])).fetchall()]
            if invalidated_bio_assays:
                marks = ",".join("?" for _ in invalidated_bio_assays)
                self.db.execute(f"UPDATE bio_assay_observations SET state='stale' WHERE id IN ({marks})",
                                invalidated_bio_assays)
        # Second-opinion and survivorship records stay case-scoped and
        # anchor-exact like snapshots: only rows pinning the superseded
        # version (or the invalidated original conclusion) reopen.
        invalidated_second_opinions, invalidated_survivorship = self._invalidate_care_records(
            case_id, previous["id"] if previous else None, invalidated)
        # B-05: record the explicit match decision that bound these bytes
        # to this case. Duplicates return before this point, so the
        # original link is never duplicated either.
        self.db.execute(
            """INSERT INTO subject_links
            (case_id,source_version_id,declared_subject_id,decision,decided_at,actor_label)
            VALUES (?,?,?,?,?,?)""",
            (case_id, source_id, report.patient_id,
             self.SUBJECT_LINK_DECISION, now_utc(), self.SUBJECT_LINK_ACTOR))
        event_id = self._event(case_id, "source_imported", document_id=report.document_id,
                    version=version, source_id=source_id, amends_id=previous["id"] if previous else None,
                    invalidated_snapshots=invalidated, invalidated_options=invalidated_options,
                    invalidated_model_investigation_ids=newly_stale_model_ids,
                    invalidated_inventory_assertions=invalidated_inventory,
                    invalidated_bio_explanations=invalidated_bio_explanations,
                    invalidated_bio_assay_observations=invalidated_bio_assays,
                    invalidated_second_opinions=invalidated_second_opinions,
                    invalidated_survivorship_items=invalidated_survivorship,
                    invalidated_workspace_questions=invalidated_workspace)
        if previous is not None and invalidated:
            self._create_re_review_tasks(
                case_id=case_id, snapshot_ids=invalidated, cause="source_amendment",
                invalidating_event_id=event_id, assignee_label=assignee_label, due_date=due_date,
                superseding_source_version_id=source_id,
                superseded_source_version_id=previous["id"],
                finding_diff=self._source_finding_diff(previous["id"], source_id))
        return {"result": "imported", "source_id": source_id, "version": version,
                "invalidated_snapshots": invalidated, "invalidated_options": invalidated_options,
                "invalidated_model_investigation_ids": newly_stale_model_ids,
                "invalidated_inventory_assertions": invalidated_inventory,
                "invalidated_bio_explanations": invalidated_bio_explanations,
                "invalidated_bio_assay_observations": invalidated_bio_assays,
                "invalidated_second_opinions": invalidated_second_opinions,
                "invalidated_survivorship_items": invalidated_survivorship,
                "invalidated_workspace_questions": invalidated_workspace}
    # ---- B-05: explicit subject binding + reversible quarantine correction ----
    SUBJECT_LINK_DECISION = "bound_by_declared_id_equality"
    SUBJECT_LINK_ACTOR = "declared-id-equality"

    def list_subject_links(self, case_id: str) -> list[dict]:
        """Every recorded match decision binding a source version to this case.

        Read-only projection over the append-only subject_links ledger. A
        source version appears at most once across ALL cases (UNIQUE
        source_version_id), so disjoint per-case listings also prove no
        source version is bound to two cases.
        """
        self._case(case_id)
        return self._dicts(self.db.execute(
            """SELECT l.id,l.case_id,l.source_version_id,v.document_id,v.version,
            l.declared_subject_id,l.decision,l.decided_at,l.actor_label
            FROM subject_links l JOIN source_versions v ON v.id=l.source_version_id
            WHERE l.case_id=? ORDER BY l.id""", (case_id,)).fetchall())

    def correct_quarantined_delivery(self, source_case_id: str, quarantine_id: int,
                                     destination_case_id: str,
                                     actor_label: str | None = None) -> dict:
        """Move quarantined bytes into the right case via the import path.

        This is the ONLY path that binds quarantined bytes to a case: the
        original bytes are imported into the destination via import_report
        (same validation, versions, anchors, invalidation), a disposition
        row records quarantine_id -> destination source, and receipt events
        land on both cases (quarantine_resolved_out on the source case;
        the normal source_imported plus quarantine_resolved_in on the
        destination). The quarantine row is never deleted or edited and
        keeps the original bytes. Declared-identifier equality only: the
        destination must equal the report's declared subject id, no fuzzy
        matching, no silent merges. A repeat correction returns the
        original disposition with duplicate=True and emits nothing new.
        """
        self._case(source_case_id)
        self._case(destination_case_id)
        if type(quarantine_id) is not int or quarantine_id < 1:
            raise InvalidInput("Invalid quarantine ID")
        if actor_label is None:
            actor = "unlabeled-correction"
        elif isinstance(actor_label, str) and 2 <= len(actor_label.strip()) <= 80:
            actor = actor_label.strip()
        else:
            raise InvalidInput("Correction actor label must have 2–80 characters")
        row = self.db.execute(
            "SELECT * FROM quarantine WHERE id=? AND target_case_id=?",
            (quarantine_id, source_case_id)).fetchone()
        if not row:
            raise InvalidInput("Quarantined delivery not in this case")
        existing = self.db.execute(
            "SELECT * FROM quarantine_corrections WHERE quarantine_id=?",
            (quarantine_id,)).fetchone()
        if existing:
            return {"result": "corrected", "quarantine_id": quarantine_id,
                    "source_case_id": existing["source_case_id"],
                    "destination_case_id": existing["destination_case_id"],
                    "destination_source_id": existing["destination_source_id"],
                    "duplicate": True}
        raw = bytes(row["raw"])
        parsed = parse_report(raw)
        if parsed.patient_id != destination_case_id:
            raise InvalidInput("Correction destination must equal the quarantined report's declared subject id")
        outcome = self.import_report(destination_case_id, raw)
        if outcome["result"] == "quarantined":
            # Unreachable after the equality check above; a correction must
            # never mint a second quarantine row in the destination.
            raise InvalidInput("Correction destination quarantined the bytes again")
        try:
            with self.db:
                self.db.execute("BEGIN IMMEDIATE")
                again = self.db.execute(
                    "SELECT * FROM quarantine_corrections WHERE quarantine_id=?",
                    (quarantine_id,)).fetchone()
                if again:
                    return {"result": "corrected", "quarantine_id": quarantine_id,
                            "source_case_id": again["source_case_id"],
                            "destination_case_id": again["destination_case_id"],
                            "destination_source_id": again["destination_source_id"],
                            "duplicate": True}
                self.db.execute(
                    """INSERT INTO quarantine_corrections
                    (quarantine_id,source_case_id,destination_case_id,destination_source_id,corrected_at,actor_label)
                    VALUES (?,?,?,?,?,?)""",
                    (quarantine_id, source_case_id, destination_case_id,
                     outcome["source_id"], now_utc(), actor))
                self._event(source_case_id, "quarantine_resolved_out",
                            quarantine_id=quarantine_id,
                            destination_case_id=destination_case_id,
                            destination_source_id=outcome["source_id"],
                            actor_label=actor)
                self._event(destination_case_id, "quarantine_resolved_in",
                            quarantine_id=quarantine_id,
                            source_case_id=source_case_id,
                            destination_source_id=outcome["source_id"],
                            actor_label=actor)
        except sqlite3.IntegrityError:
            # A concurrent correction won the disposition insert; surface
            # the original disposition instead of a second receipt.
            final = self.db.execute(
                "SELECT * FROM quarantine_corrections WHERE quarantine_id=?",
                (quarantine_id,)).fetchone()
            if final:
                return {"result": "corrected", "quarantine_id": quarantine_id,
                        "source_case_id": final["source_case_id"],
                        "destination_case_id": final["destination_case_id"],
                        "destination_source_id": final["destination_source_id"],
                        "duplicate": True}
            raise
        return {"result": "corrected", "quarantine_id": quarantine_id,
                "source_case_id": source_case_id,
                "destination_case_id": destination_case_id,
                "destination_source_id": outcome["source_id"],
                "version": outcome["version"], "import_result": outcome["result"]}


    # ---- OI-021: reviewed option/dependency view (derived projection) ----
    OPTION_EPISTEMIC = frozenset({"supported", "contradicted", "unsupported", "unknown"})
    OPTION_OPERATIONAL = frozenset({"proposed", "reviewed", "held", "rejected", "withdrawn", "expired"})
    OPTION_REVIEW_ACTIONS = frozenset({"approve", "reject", "abstain", "reconfirm", "withdraw", "expire"})
    TASK_STATUSES = frozenset({"not_started", "in_progress", "done", "blocked", "cancelled"})
    THREAT_KINDS = frozenset({"expiring_window", "dependency_loss", "evidence_withdrawal", "other"})
    # Portfolio slice: documented reasons that hold an option, and the four
    # reviewable dimensions. Display-only additions: options without flags or
    # notes behave exactly as before.
    OPTION_FLAG_KINDS = frozenset({"objection", "deferred", "reserved"})
    OPTION_FLAG_RESOLVE_ACTIONS = frozenset({"resolve", "reopen"})
    OPTION_DIMENSIONS = ("scientific_plausibility", "technical_feasibility",
                         "access", "clinical_authorization")
    OPTION_DIMENSION_LABELS = {
        "scientific_plausibility": "Scientific plausibility",
        "technical_feasibility": "Technical feasibility",
        "access": "Access",
        "clinical_authorization": "Clinical authorization",
    }
    PORTFOLIO_DISCLAIMER = (
        "For discussion only. Every entry is a reviewable record for a clinician, with sources cited. "
        "This surface states no eligibility, benefit, safety, next step, or authorization. "
        "Deferred, rejected, and reserved entries are preserved history and are never silently dropped. "
        "Fictional demo data only.")
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

    # Portfolio records must never declare eligibility, benefit, or
    # authorization: they stay reviewable notes for a clinician.
    _PORTFOLIO_CLAIM_LANGUAGE = re.compile(
        r"\b(eligib\w*|authori[sz]\w*|benefit\w*)\b", re.IGNORECASE)

    @staticmethod
    def _check_no_portfolio_claim(text: str, field: str) -> str:
        cleaned = CaseStore._check_no_clinical_language(text, field)
        if CaseStore._PORTFOLIO_CLAIM_LANGUAGE.search(cleaned):
            raise InvalidInput(
                f"{field} must not declare eligibility, benefit, or authorization; "
                "record a reviewable note instead")
        return cleaned
    # ---- Counterevidence and safety-uncertainty surfacing ----
    # New evidence can hold or invalidate a promising option; the reason and
    # its triggering source or evidence assessment are recorded append-only.
    # Single-modality notes (tumor expression alone, tracer uptake alone)
    # never establish benefit or toxicity, and preclinical notes are always
    # labeled preclinical, never a patient response or permission.
    COUNTEREFFECTS = frozenset({"hold", "invalidate"})
    SAFETY_CATEGORIES = frozenset({
        "expression_only", "tracer_only", "preclinical_only",
        "cross_modal_gap", "other"})
    SAFETY_LABELS = {
        "expression_only": ("Tumor expression alone — does not establish benefit or "
                            "toxicity. Fictional data only."),
        "tracer_only": ("Tracer uptake alone — does not establish benefit or "
                        "toxicity. Fictional data only."),
        "preclinical_only": ("Preclinical only — not an observed patient response; "
                             "not permission to administer. Fictional data only."),
        "cross_modal_gap": ("Cross-modal safety uncertainty — stays visible before any "
                            "promotion. Fictional data only."),
        "other": ("Safety uncertainty — for clinician review. Fictional data only."),
    }
    # Narrow guards, not classifiers: the canonical labels above carry the
    # meaning, and human review remains the gate.
    _ESTABLISHED_BENEFIT = re.compile(
        r"\b(benefit|toxicity|efficac\w*|effective\w*)\b.{0,60}"
        r"\b(established|proven|confirmed|shown|demonstrated)\b"
        r"|\b(established|proven|confirmed)\b.{0,60}"
        r"\b(benefit|toxicity|efficac\w*)\b", re.IGNORECASE | re.DOTALL)
    _PATIENT_RESPONSE_OR_PERMISSION = re.compile(
        r"(observed|patient)\s+(response|benefit)"
        r"|permission to administer|may administer"
        r"|administer to (the )?patient|safe to administer"
        r"|observed patient improvement", re.IGNORECASE)
    _DOSING = re.compile(r"\b\d+\s*(mg|mcg|microgram|gram)s?\b|\b\d+\s*ml\b", re.IGNORECASE)

    @staticmethod
    def _check_counterevidence_reason(reason: object) -> str:
        text = CaseStore._check_no_clinical_language(reason, "Counterevidence reason")
        if not 10 <= len(text) <= 600:
            raise InvalidInput("Counterevidence reason must have 10–600 characters")
        return text

    @staticmethod
    def _check_safety_detail(category: str, detail: object) -> str:
        text = CaseStore._check_no_clinical_language(detail, "Safety detail")
        if not 10 <= len(text) <= 600:
            raise InvalidInput("Safety detail must have 10–600 characters")
        if CaseStore._DOSING.search(text):
            raise InvalidInput("Safety detail must not state dosing")
        if category in ("expression_only", "tracer_only") and CaseStore._ESTABLISHED_BENEFIT.search(text):
            raise InvalidInput("Tumor expression or tracer uptake alone never establishes benefit or toxicity")
        if category == "preclinical_only" and CaseStore._PATIENT_RESPONSE_OR_PERMISSION.search(text):
            raise InvalidInput("Preclinical notes are never an observed patient response or permission to administer")
        return text

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
            if anchor is not None and not isinstance(anchor, str):
                raise InvalidInput(f"{field} anchor must be a string")
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

    def _option_has_open_flag(self, option_id: int) -> bool:
        row = self.db.execute(
            "SELECT 1 FROM option_flags WHERE option_id=? AND state='open' LIMIT 1",
            (option_id,)).fetchone()
        return row is not None

    def _check_portfolio_premise(self, case_id: str, source_version_id: int | None,
                                 evidence_assessment_id: int | None) -> None:
        """Zero or one current same-case premise. IDs are pre-checked as
        positive integers or None by the caller; currency is checked inside
        the caller's immediate transaction."""
        if source_version_id is not None and evidence_assessment_id is not None:
            raise InvalidInput("A portfolio record cites at most one source or evidence premise")
        if source_version_id is not None:
            row = self.db.execute("SELECT state FROM source_versions WHERE id=? AND case_id=?",
                                  (source_version_id, case_id)).fetchone()
            if not row:
                raise InvalidInput("Source premise not in this case")
            if row["state"] != "current":
                raise InvalidInput("Source premise is not current")
        if evidence_assessment_id is not None:
            row = self.db.execute("""SELECT v.state FROM evidence_assessments a
                JOIN evidence_versions v ON v.id=a.evidence_version_id
                WHERE a.id=? AND a.case_id=?""",
                (evidence_assessment_id, case_id)).fetchone()
            if not row:
                raise InvalidInput("Evidence premise not in this case")
            if row["state"] != "current":
                raise InvalidInput("Evidence premise is not current")

    def _portfolio_premise_text(self, source_version_id: int | None,
                                evidence_assessment_id: int | None) -> str | None:
        if source_version_id is not None:
            src = self.db.execute("SELECT document_id,version,state FROM source_versions WHERE id=?",
                                  (source_version_id,)).fetchone()
            return f"{src['document_id']}@{src['version']} ({src['state']})" if src else "missing source"
        if evidence_assessment_id is not None:
            asm = self.db.execute("""SELECT a.relation,v.evidence_key,v.version,v.state
                FROM evidence_assessments a
                JOIN evidence_versions v ON v.id=a.evidence_version_id WHERE a.id=?""",
                (evidence_assessment_id,)).fetchone()
            return (f"{asm['evidence_key']}@{asm['version']} ({asm['state']}) · {asm['relation']}"
                    if asm else "missing assessment")
        return None
    def _option_blocked_by_counterevidence(self, option_id: int) -> bool:
        """Any recorded hold or invalidation blocks promotion, permanently.

        The record is append-only history: a later amendment never deletes
        it, and reconfirmation cannot clear it. A new proposal on current
        inputs is the only path forward, mirroring contradicted handling.
        """
        row = self.db.execute("SELECT 1 FROM option_counterevidence WHERE option_id=? LIMIT 1",
                              (option_id,)).fetchone()
        return row is not None

    def _option_safety_block(self, option_id: int) -> str | None:
        """Why safety uncertainty blocks promotion, or None when clear.

        Every flag stays visible in the derived view; promotion is refused
        while any flag exists, so uncertainty is surfaced for clinician
        review and never resolved by the platform itself.
        """
        rows = self.db.execute(
            "SELECT category FROM option_safety_flags WHERE option_id=? ORDER BY id",
            (option_id,)).fetchall()
        if not rows:
            return None
        categories = [r["category"] for r in rows]
        if "expression_only" in categories or "tracer_only" in categories:
            return "Tumor expression or tracer uptake alone never establishes benefit or toxicity"
        if "preclinical_only" in categories:
            return ("Preclinical only — not an observed patient response; "
                    "not permission to administer")
        if "cross_modal_gap" in categories:
            return "Cross-modal safety uncertainty stays visible before any promotion"
        return "Safety uncertainty stays visible before any promotion"

    def _counterevidence_trigger(self, case_id: str, source_version_id: int | None,
                                 evidence_assessment_id: int | None) -> tuple[str, str]:
        """Human-readable trigger label plus its current freshness state."""
        if source_version_id is not None:
            src = self.db.execute(
                "SELECT document_id,version,state FROM source_versions WHERE id=?",
                (source_version_id,)).fetchone()
            if not src:
                return "missing source", "missing"
            return f"{src['document_id']}@{src['version']}", str(src["state"])
        asm = self.db.execute("""SELECT a.relation,v.evidence_key,v.version,v.state
            FROM evidence_assessments a JOIN evidence_versions v ON v.id=a.evidence_version_id
            WHERE a.id=?""", (evidence_assessment_id,)).fetchone()
        if not asm:
            return "missing assessment", "missing"
        return (f"{asm['evidence_key']}@{asm['version']} · {asm['relation']}", str(asm["state"]))

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
            # Portfolio slice: an option held for a documented reason anchored
            # to this source reopens when the reason's premise changes.
            seeded.update(r[0] for r in self.db.execute(
                f"""SELECT DISTINCT option_id FROM option_flags
                WHERE state='open' AND source_version_id IN ({marks})""",
                sorted(source_version_ids)).fetchall())
        if evidence_version_ids:
            marks = ",".join("?" for _ in evidence_version_ids)
            seeded.update(r[0] for r in self.db.execute(
                f"""SELECT DISTINCT d.option_id FROM option_dependencies d
                JOIN evidence_assessments a ON a.id=d.evidence_assessment_id
                WHERE a.evidence_version_id IN ({marks})""", sorted(evidence_version_ids)).fetchall())
            seeded.update(r[0] for r in self.db.execute(
                f"""SELECT DISTINCT f.option_id FROM option_flags f
                JOIN evidence_assessments a ON a.id=f.evidence_assessment_id
                WHERE f.state='open' AND a.evidence_version_id IN ({marks})""",
                sorted(evidence_version_ids)).fetchall())
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
                        self._option_contradicted(target["id"]) or
                        self._option_has_open_flag(target["id"]) or
                        self._option_blocked_by_counterevidence(target["id"]) or
                        self._option_safety_block(target["id"]) is not None):
                        raise InvalidInput("Prerequisite option is not current or is held; review its basis first")
                    pending.append(target["id"])

    def create_option(self, case_id: str, snapshot_id: int, label: str, description: str,
                      epistemic_status: str) -> int:
        self._case(case_id)
        if type(snapshot_id) is not int:
            raise InvalidInput("Snapshot id must be an integer")
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
                if (target["review_state"] != "current" or self._option_contradicted(depends_on_option_id)
                        or self._option_has_open_flag(depends_on_option_id)
                        or self._option_blocked_by_counterevidence(depends_on_option_id)
                        or self._option_safety_block(depends_on_option_id) is not None):
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
            option = self._option_row(case_id, option_id)
            if option["operational_status"] in ("rejected", "withdrawn", "expired"):
                raise InvalidInput("Preserve the terminal option; create a new proposal for new tasks")
            cur = self.db.execute("""INSERT INTO preparation_tasks
                (case_id,option_id,label,owner_label,status,lead_time_days,created_at)
                VALUES (?,?,?,?,'not_started',?,?)""",
                (case_id, option_id, label, owner_label.strip(), lead, now_utc()))
            self._event(case_id, "preparation_task_created", option_id=option_id, task_id=cur.lastrowid)
            self._reopen_option_dependents(case_id, option_id, "preparation_task_added")
            return int(cur.lastrowid)

    def set_preparation_task_status(self, case_id: str, task_id: int, status: str,
                                    acting_label: str | None = None) -> dict | None:
        """Human-driven task transition; ``done`` additionally writes a receipt.

        The existing lifecycle and its ``preparation_task_status_changed``
        events are unchanged. A transition to ``done`` pins the option's
        basis (snapshot + source/evidence premise ids) into one immutable
        ``task_completion_receipts`` row and emits a
        ``task_completion_receipted`` event in the same transaction.
        Completion against a superseded basis is rejected (documented B-09
        rule): the status, events, and receipts are left untouched. The
        acting label defaults to the task owner's label when omitted;
        authorized-actor binding waits on B-01. The label is validated
        only on done transitions; other transitions ignore it. Returns
        None when the status is unchanged, else the transition outcome;
        receipt_id is set only on done transitions (the new or preserved
        receipt id). Nothing auto-completes: only this explicit call
        writes receipts.
        """
        self._case(case_id)
        if type(task_id) is not int or task_id < 1:
            raise InvalidInput("Preparation task id must be a positive integer")
        if status not in self.TASK_STATUSES:
            raise InvalidInput("Invalid preparation task status")
        with self.db:
            self.db.execute("BEGIN IMMEDIATE")
            row = self.db.execute("SELECT option_id,status,owner_label FROM preparation_tasks WHERE id=? AND case_id=?",
                                  (task_id, case_id)).fetchone()
            if not row:
                raise InvalidInput("Preparation task not in this case")
            if row["status"] == status:
                return None
            actor: str | None = None
            if status == "done":
                actor = row["owner_label"] if acting_label is None else task_receipts.valid_acting_label(acting_label)
                problems = task_receipts.current_basis_problems(self.db, case_id, int(row["option_id"]))
                if problems:
                    raise InvalidInput(
                        "Task basis is superseded (" + "; ".join(problems) + "); "
                        "preserve this record and complete a new task on a current proposal")
            self.db.execute("UPDATE preparation_tasks SET status=? WHERE id=?", (status, task_id))
            self._event(case_id, "preparation_task_status_changed", option_id=row["option_id"],
                        task_id=task_id, previous_status=row["status"], status=status)
            receipt_id: int | None = None
            # actor is set if and only if this is a done transition (above).
            if actor is not None:
                outcome = task_receipts.write_completion_receipt(
                    self.db, case_id=case_id, task_id=task_id, option_id=int(row["option_id"]),
                    owner_label=row["owner_label"], acting_label=actor, recorded_at=now_utc())
                receipt_id = int(outcome["receipt_id"])
                if outcome["created"]:
                    basis = outcome["basis"]
                    self._event(case_id, "task_completion_receipted", option_id=row["option_id"],
                                task_id=task_id, receipt_id=receipt_id,
                                snapshot_id=basis["snapshot_id"],
                                source_version_ids=basis["source_version_ids"],
                                evidence_version_ids=basis["evidence_version_ids"])
            self._reopen_option_dependents(case_id, row["option_id"], "preparation_task_changed")
            return {"task_id": task_id, "previous_status": row["status"],
                    "status": status, "receipt_id": receipt_id}

    def get_task_receipt(self, case_id: str, task_id: int) -> dict | None:
        """Read one immutable completion receipt, or None when absent.

        There is deliberately no update or delete path: receipts are
        append-only. Returns None for tasks outside this case.
        """
        self._case(case_id)
        if type(task_id) is not int or task_id < 1:
            raise InvalidInput("Invalid preparation task ID")
        return task_receipts.get_receipt(self.db, case_id, task_id)

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
            option = self._option_row(case_id, option_id)
            if option["operational_status"] in ("rejected", "withdrawn", "expired"):
                raise InvalidInput("Preserve the terminal option; create a new proposal for new threats")
            cur = self.db.execute("""INSERT INTO optionality_threats
                (option_id,kind,description,threat_date,threat_basis,anchor,created_at)
                VALUES (?,?,?,?,?,?,?)""",
                (option_id, kind, description, date_value, basis, anchor_text, now_utc()))
            self._event(case_id, "optionality_threat_added", option_id=option_id, threat_id=cur.lastrowid)
            self._reopen_option_dependents(case_id, option_id, "threat_added")
            return int(cur.lastrowid)

    def add_option_counterevidence(self, case_id: str, option_id: int, effect: str, reason: str, *,
                                   source_version_id: int | None = None,
                                   evidence_assessment_id: int | None = None) -> int:
        """Record that newly arrived evidence holds or invalidates an option.

        Append-only: the row keeps its reason and triggering evidence even
        after later amendments supersede that trigger. A hold blocks
        promotion and shows the option as held; an invalidation additionally
        reopens review of the option and its dependents. Neither is ever
        cleared by reconfirmation; a new proposal is the only path forward.
        """
        self._case(case_id)
        if effect not in self.COUNTEREFFECTS:
            raise InvalidInput("Counterevidence effect must be 'hold' or 'invalidate'")
        reason_text = self._check_counterevidence_reason(reason)
        triggers = [x for x in (source_version_id, evidence_assessment_id) if x is not None]
        if len(triggers) != 1 or type(triggers[0]) is not int or triggers[0] < 1:
            raise InvalidInput("Counterevidence requires exactly one triggering source or evidence assessment")
        with self.db:
            self.db.execute("BEGIN IMMEDIATE")
            option = self._option_row(case_id, option_id)
            if option["operational_status"] in ("rejected", "withdrawn", "expired"):
                raise InvalidInput("Preserve the terminal option; create a new proposal instead")
            if source_version_id is not None:
                src = self.db.execute("SELECT state FROM source_versions WHERE id=? AND case_id=?",
                                      (source_version_id, case_id)).fetchone()
                if not src:
                    raise InvalidInput("Triggering source version not in this case")
                if src["state"] != "current":
                    raise InvalidInput("Triggering source must be current when recorded")
            else:
                asm = self.db.execute("""SELECT v.state FROM evidence_assessments a
                    JOIN evidence_versions v ON v.id=a.evidence_version_id
                    WHERE a.id=? AND a.case_id=?""",
                    (evidence_assessment_id, case_id)).fetchone()
                if not asm:
                    raise InvalidInput("Triggering evidence assessment not in this case")
                if asm["state"] != "current":
                    raise InvalidInput("Triggering evidence must be current when recorded")
            cur = self.db.execute("""INSERT INTO option_counterevidence
                (case_id,option_id,effect,reason,source_version_id,evidence_assessment_id,created_at)
                VALUES (?,?,?,?,?,?,?)""",
                (case_id, option_id, effect, reason_text, source_version_id,
                 evidence_assessment_id, now_utc()))
            self._event(case_id, "option_counterevidence_recorded", option_id=option_id,
                        counterevidence_id=cur.lastrowid, effect=effect)
            if effect == "invalidate":
                changed = self._invalidate_options(snapshot_ids=set(), source_version_ids=set(),
                                                    evidence_version_ids=set(), option_ids={option_id})
                if changed:
                    self._event(case_id, "option_review_reopened", option_id=option_id,
                                reason="counterevidence_invalidate", invalidated_options=changed)
            else:
                self._reopen_option_dependents(case_id, option_id, "counterevidence_hold",
                                               include_reviewed_self=False)
            return int(cur.lastrowid)

    def add_option_safety_flag(self, case_id: str, option_id: int, category: str, detail: str, *,
                               source_version_id: int | None = None,
                               evidence_assessment_id: int | None = None) -> int:
        """Record a visible safety uncertainty for an option.

        Append-only: flags stay in the derived view before any promotion and
        are never stripped or auto-resolved. Each flag carries a canonical
        plain-language label from the server, so the UI cannot show a
        single-modality note as established benefit/toxicity or a
        preclinical note as a patient response or permission.
        """
        self._case(case_id)
        if category not in self.SAFETY_CATEGORIES:
            raise InvalidInput("Invalid safety category")
        detail_text = self._check_safety_detail(category, detail)
        if source_version_id is not None and evidence_assessment_id is not None:
            raise InvalidInput("Safety flag takes at most one triggering source or assessment")
        for value in (source_version_id, evidence_assessment_id):
            if value is not None and (type(value) is not int or value < 1):
                raise InvalidInput("Safety trigger IDs must be positive integers")
        with self.db:
            self.db.execute("BEGIN IMMEDIATE")
            option = self._option_row(case_id, option_id)
            if option["operational_status"] in ("rejected", "withdrawn", "expired"):
                raise InvalidInput("Preserve the terminal option; create a new proposal instead")
            if source_version_id is not None:
                src = self.db.execute("SELECT state FROM source_versions WHERE id=? AND case_id=?",
                                      (source_version_id, case_id)).fetchone()
                if not src:
                    raise InvalidInput("Triggering source version not in this case")
                if src["state"] != "current":
                    raise InvalidInput("Triggering source must be current when recorded")
            if evidence_assessment_id is not None:
                asm = self.db.execute("""SELECT v.state FROM evidence_assessments a
                    JOIN evidence_versions v ON v.id=a.evidence_version_id
                    WHERE a.id=? AND a.case_id=?""",
                    (evidence_assessment_id, case_id)).fetchone()
                if not asm:
                    raise InvalidInput("Triggering evidence assessment not in this case")
                if asm["state"] != "current":
                    raise InvalidInput("Triggering evidence must be current when recorded")
            cur = self.db.execute("""INSERT INTO option_safety_flags
                (case_id,option_id,category,detail,source_version_id,evidence_assessment_id,created_at)
                VALUES (?,?,?,?,?,?,?)""",
                (case_id, option_id, category, detail_text, source_version_id,
                 evidence_assessment_id, now_utc()))
            self._event(case_id, "option_safety_flag_recorded", option_id=option_id,
                        safety_flag_id=cur.lastrowid, category=category)
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
        if action in ("approve", "reconfirm"):
            # Promotion-time wording guard (narrow, not a classifier): a
            # reviewer scope that itself claims established benefit/toxicity
            # or a patient response/permission is refused, so single-modality
            # or preclinical notes cannot be promoted into such a claim.
            if self._ESTABLISHED_BENEFIT.search(scope):
                raise InvalidInput("Tumor expression or tracer uptake alone never establishes benefit or toxicity")
            if self._PATIENT_RESPONSE_OR_PERMISSION.search(scope):
                raise InvalidInput("Preclinical notes are never an observed patient response or permission to administer")
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
                if self._option_has_open_flag(option_id):
                    raise InvalidInput("An option with an open objection, deferral, or reservation "
                                       "cannot be approved; resolve the recorded reason first")
                if self._option_blocked_by_counterevidence(option_id):
                    raise InvalidInput("Option is held by recorded counterevidence; create a new proposal instead")
                safety_block = self._option_safety_block(option_id)
                if safety_block is not None:
                    raise InvalidInput(safety_block + "; create a new proposal after clinician review")
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
                if self._option_has_open_flag(option_id):
                    raise InvalidInput("An option with an open objection, deferral, or reservation "
                                       "cannot be reconfirmed; resolve the recorded reason first")
                if self._option_blocked_by_counterevidence(option_id):
                    raise InvalidInput("Option is held by recorded counterevidence; create a new proposal instead")
                safety_block = self._option_safety_block(option_id)
                if safety_block is not None:
                    raise InvalidInput(safety_block + "; create a new proposal after clinician review")
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
            # If this option was in the review queue before this human
            # decision, append a queue receipt in the same transaction so it
            # leaves with a recorded decision, never silently. Abstention is
            # an acknowledgment; every other option action is a review.
            pre_held = (option["epistemic_status"] == "contradicted"
                        or self._option_contradicted(option_id)) \
                and operational in ("proposed", "reviewed")
            if operational not in ("rejected", "withdrawn", "expired") \
                    and (pre_held or option["review_state"] == "needs_review"):
                post = self.db.execute("SELECT * FROM options WHERE id=?", (option_id,)).fetchone()
                post_snap = self.db.execute("SELECT state FROM snapshots WHERE id=?",
                                            (post["snapshot_id"],)).fetchone()
                queue_action = "acknowledged" if action == "abstain" else "reviewed"
                self.db.execute("""INSERT INTO review_receipts
                    (case_id,queue_key,kind,target_id,fingerprint,action,reviewer_label,reason,created_at)
                    VALUES (?,?,?,?,?,?,?,?,?)""",
                    (case_id, f"option:{option_id}", "held-option", option_id,
                     f"{post['operational_status']}:{post['review_state']}:"
                     f"{post['snapshot_id']}:{post_snap['state'] if post_snap else 'missing'}:"
                     f"{post['epistemic_status']}",
                     queue_action, reviewer_label.strip(),
                     f"Recorded together with the existing option review ({action}); "
                     f"not a clinical authorization. Scope: {scope}",
                     timestamp))
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
                self._option_contradicted(current_id) or
                self._option_blocked_by_counterevidence(current_id) or
                self._option_safety_block(current_id) is not None):
                unresolved.add("prerequisite requires review or is unavailable")
                return
            if self._option_has_open_flag(current_id):
                # The walk starts at the option itself (path empty), then
                # follows prerequisites; an open hold abstains either way.
                unresolved.add("option has an open objection, deferral, or reservation"
                               if not path else "prerequisite requires review or is unavailable")
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

        Open portfolio flags (objections, deferrals, reservations) reframe the
        display status of proposed/reviewed options as held/deferred/reserved;
        terminal states are preserved verbatim. Options without flags behave
        exactly as before.
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
            held_by_counterevidence = self._option_blocked_by_counterevidence(option_id)
            safety_block = self._option_safety_block(option_id)
            derived_epistemic = "contradicted" if contradicted else option["epistemic_status"]
            flags = []
            for flag in self.db.execute("SELECT * FROM option_flags WHERE option_id=? ORDER BY id",
                                        (option_id,)).fetchall():
                flag_events = self._dicts(self.db.execute(
                    "SELECT * FROM option_flag_events WHERE flag_id=? ORDER BY id",
                    (flag["id"],)).fetchall())
                flags.append({**dict(flag),
                              "premise": self._portfolio_premise_text(
                                  flag["source_version_id"], flag["evidence_assessment_id"]),
                              "events": flag_events})
            open_kinds = {item["kind"] for item in flags if item["state"] == "open"}
            display_operational = option["operational_status"]
            # Terminal states are preserved verbatim; holds only reframe
            # proposed/reviewed options, and only when flags exist.
            # Counterevidence holds join the hold sources at the same
            # precedence: deferred, then reserved, then any hold.
            if display_operational in ("proposed", "reviewed"):
                if "deferred" in open_kinds:
                    display_operational = "deferred"
                elif "reserved" in open_kinds:
                    display_operational = "reserved"
                elif contradicted or held_by_counterevidence or "objection" in open_kinds:
                    display_operational = "held"
            counterevidence = []
            for row in self.db.execute(
                    "SELECT * FROM option_counterevidence WHERE option_id=? ORDER BY id",
                    (option_id,)).fetchall():
                label, trigger_state = self._counterevidence_trigger(
                    case_id, row["source_version_id"], row["evidence_assessment_id"])
                counterevidence.append({**dict(row), "trigger": label, "trigger_state": trigger_state})
            safety_flags = []
            for row in self.db.execute(
                    "SELECT * FROM option_safety_flags WHERE option_id=? ORDER BY id",
                    (option_id,)).fetchall():
                if row["source_version_id"] is None and row["evidence_assessment_id"] is None:
                    label, trigger_state = "no single trigger (general uncertainty)", "not_applicable"
                else:
                    label, trigger_state = self._counterevidence_trigger(
                        case_id, row["source_version_id"], row["evidence_assessment_id"])
                safety_flags.append({**dict(row), "trigger": label, "trigger_state": trigger_state,
                                     "display_label": self.SAFETY_LABELS[str(row["category"])]})
            # B-09: receipt markers + open-vs-receipted grouping are derived
            # annotations; the stored task rows and review meanings are unchanged.
            task_rows = self._dicts(self.db.execute(
                "SELECT * FROM preparation_tasks WHERE option_id=? ORDER BY id", (option_id,)).fetchall())
            task_rows, task_receipt_summary = task_receipts.annotate_tasks_with_receipts(self.db, task_rows)
            options.append({
                **dict(option),
                "snapshot_state": snap["state"] if snap else "missing",
                "derived_epistemic_status": derived_epistemic,
                "display_operational_status": display_operational,
                "held_by_counterevidence": held_by_counterevidence,
                "safety_block": safety_block,
                "dependencies": deps,
                "flags": flags,
                "dependency_loss": task_receipts.derive_dependency_loss(self.db, case_id, option_id),
                "preparation_tasks": task_rows,
                "open_task_ids": task_receipt_summary["open_task_ids"],
                "receipted_task_ids": task_receipt_summary["receipted_task_ids"],
                "threats": self._dicts(self.db.execute(
                    "SELECT * FROM optionality_threats WHERE option_id=? ORDER BY id", (option_id,)).fetchall()),
                "counterevidence": counterevidence,
                "safety_flags": safety_flags,
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
                           "Snapshot filtering shows current state and recorded associations, not as-known-at replay. "
                           "Recorded counterevidence holds and safety uncertainties stay visible; "
                           "single-modality or preclinical notes never establish benefit, toxicity, "
                           "patient response, or permission to administer."),
            "receipt_disclaimer": task_receipts.RECEIPT_DISCLAIMER,
            "options": options,
        }

    # ---- Option portfolio: flags, dimension notes, derived view ----
    def add_option_flag(self, case_id: str, option_id: int, kind: str, label: str,
                        reason: str, author_label: str,
                        source_version_id: int | None = None,
                        evidence_assessment_id: int | None = None) -> int:
        """Record a documented objection, deferral, or reservation.

        Append-only: the flag and its raise event stay in history; only the
        open/resolved state changes, through recorded resolve/reopen events.
        An open flag holds the option: it cannot be approved or reconfirmed
        until the recorded reason is resolved, and resolving the reason
        reopens review of the option and its followers.
        """
        self._case(case_id)
        if kind not in self.OPTION_FLAG_KINDS:
            raise InvalidInput("Invalid option flag kind")
        label = self._check_no_portfolio_claim(label, "Flag label")
        if not 1 <= len(label) <= 120:
            raise InvalidInput("Flag label must have 1–120 characters")
        reason = self._check_no_portfolio_claim(reason, "Flag reason")
        if not 10 <= len(reason) <= 500:
            raise InvalidInput("Flag reason must have 10–500 characters")
        if not isinstance(author_label, str) or not 2 <= len(author_label.strip()) <= 80:
            raise InvalidInput("Provide the recorder label for this flag")
        for value, name in ((source_version_id, "Source premise"),
                            (evidence_assessment_id, "Evidence premise")):
            if value is not None and (type(value) is not int or value < 1):
                raise InvalidInput(f"{name} must be a positive integer")
        with self.db:
            self.db.execute("BEGIN IMMEDIATE")
            option = self._option_row(case_id, option_id)
            if option["operational_status"] in ("rejected", "withdrawn", "expired"):
                raise InvalidInput("Preserve the terminal option; record new reasons on a new proposal")
            if kind in ("deferred", "reserved"):
                existing = self.db.execute(
                    """SELECT 1 FROM option_flags WHERE option_id=?
                    AND kind IN ('deferred','reserved') AND state='open' LIMIT 1""",
                    (option_id,)).fetchone()
                if existing:
                    raise InvalidInput("Resolve the open deferral or reservation before recording another")
            self._check_portfolio_premise(case_id, source_version_id, evidence_assessment_id)
            timestamp = now_utc()
            cur = self.db.execute("""INSERT INTO option_flags
                (option_id,kind,label,reason,source_version_id,evidence_assessment_id,state,created_at)
                VALUES (?,?,?,?,?,?,'open',?)""",
                (option_id, kind, label, reason, source_version_id,
                 evidence_assessment_id, timestamp))
            self.db.execute("""INSERT INTO option_flag_events
                (flag_id,reviewer_label,action,scope,noted_at) VALUES (?,?,?,?,?)""",
                (cur.lastrowid, author_label.strip(), "raise", reason, timestamp))
            self._event(case_id, "option_flag_added", option_id=option_id,
                        flag_id=cur.lastrowid, flag_kind=kind)
            self._reopen_option_dependents(case_id, option_id, "flag_added")
            return int(cur.lastrowid)

    def resolve_option_flag(self, case_id: str, flag_id: int, reviewer_label: str,
                            action: str, scope: str) -> dict:
        """Resolve or reopen a documented flag. Either way the underlying
        reason changed, so the option and its followers need re-review.
        History is preserved: the flag row and every event stay inspectable.
        """
        self._case(case_id)
        if action not in self.OPTION_FLAG_RESOLVE_ACTIONS:
            raise InvalidInput("Flag action must be resolve or reopen")
        if not isinstance(reviewer_label, str) or not 2 <= len(reviewer_label.strip()) <= 80:
            raise InvalidInput("Provide a reviewer label")
        scope = self._check_no_portfolio_claim(scope, "Flag review scope")
        if not 10 <= len(scope) <= 300:
            raise InvalidInput("Flag review scope must have 10–300 characters")
        if type(flag_id) is not int or flag_id < 1:
            raise InvalidInput("Invalid flag ID")
        with self.db:
            self.db.execute("BEGIN IMMEDIATE")
            flag = self.db.execute("""SELECT f.*,o.case_id AS option_case FROM option_flags f
                JOIN options o ON o.id=f.option_id WHERE f.id=?""", (flag_id,)).fetchone()
            if not flag or flag["option_case"] != case_id:
                raise InvalidInput("Flag not in this case")
            if action == "resolve":
                if flag["state"] != "open":
                    raise InvalidInput("Flag is already resolved")
                new_state = "resolved"
            elif flag["state"] != "resolved":
                raise InvalidInput("Only a resolved flag can be reopened")
            else:
                new_state = "open"
            self.db.execute("UPDATE option_flags SET state=? WHERE id=?", (new_state, flag_id))
            cur = self.db.execute("""INSERT INTO option_flag_events
                (flag_id,reviewer_label,action,scope,noted_at) VALUES (?,?,?,?,?)""",
                (flag_id, reviewer_label.strip(), action, scope, now_utc()))
            changed = self._invalidate_options(snapshot_ids=set(), source_version_ids=set(),
                                               evidence_version_ids=set(),
                                               option_ids={int(flag["option_id"])})
            self._event(case_id, "option_flag_" + action, flag_id=flag_id,
                        option_id=int(flag["option_id"]), invalidated_options=changed)
            if changed:
                self._event(case_id, "option_review_reopened", flag_id=flag_id,
                            reason="flag_" + action, invalidated_options=changed)
            return {"result": action, "flag_event_id": int(cur.lastrowid),
                    "invalidated_options": changed}

    def add_option_dimension_note(self, case_id: str, option_id: int, dimension: str,
                                  note: str, anchor: str, reviewer_label: str,
                                  source_version_id: int | None = None,
                                  evidence_assessment_id: int | None = None) -> int:
        """Record a reviewable note on one of the four portfolio dimensions.

        The note stays pending until a clinician acknowledges it, and an
        acknowledgment is a record of review — never a declaration of
        eligibility, benefit, or authorization.
        """
        self._case(case_id)
        if dimension not in self.OPTION_DIMENSIONS:
            raise InvalidInput("Invalid option dimension")
        note = self._check_no_portfolio_claim(note, "Dimension note")
        if not 10 <= len(note) <= 800:
            raise InvalidInput("Dimension note must have 10–800 characters")
        anchor = self._check_no_portfolio_claim(anchor, "Dimension anchor")
        if not 10 <= len(anchor) <= 300:
            raise InvalidInput("Dimension anchor must have 10–300 characters")
        if not isinstance(reviewer_label, str) or not 2 <= len(reviewer_label.strip()) <= 80:
            raise InvalidInput("Provide the recorder label for this note")
        for value, name in ((source_version_id, "Source premise"),
                            (evidence_assessment_id, "Evidence premise")):
            if value is not None and (type(value) is not int or value < 1):
                raise InvalidInput(f"{name} must be a positive integer")
        with self.db:
            self.db.execute("BEGIN IMMEDIATE")
            option = self._option_row(case_id, option_id)
            if option["operational_status"] in ("rejected", "withdrawn", "expired"):
                raise InvalidInput("Preserve the terminal option; record new notes on a new proposal")
            self._check_portfolio_premise(case_id, source_version_id, evidence_assessment_id)
            timestamp = now_utc()
            cur = self.db.execute("""INSERT INTO option_dimension_notes
                (option_id,dimension,note,anchor,source_version_id,evidence_assessment_id,
                 reviewer_label,state,created_at)
                VALUES (?,?,?,?,?,?,?, 'pending',?)""",
                (option_id, dimension, note, anchor, source_version_id,
                 evidence_assessment_id, reviewer_label.strip(), timestamp))
            self.db.execute("""INSERT INTO option_dimension_events
                (note_id,reviewer_label,action,scope,noted_at) VALUES (?,?,?,?,?)""",
                (cur.lastrowid, reviewer_label.strip(), "record", anchor, timestamp))
            self._event(case_id, "option_dimension_recorded", option_id=option_id,
                        note_id=cur.lastrowid, dimension=dimension)
            self._reopen_option_dependents(case_id, option_id, "dimension_note_added")
            return int(cur.lastrowid)

    def acknowledge_option_dimension_note(self, case_id: str, note_id: int,
                                          reviewer_label: str, scope: str) -> dict:
        """Acknowledge a dimension note as seen. This records that a reviewer
        acted; it states no eligibility, benefit, or authorization, and it
        does not itself review the option."""
        self._case(case_id)
        if not isinstance(reviewer_label, str) or not 2 <= len(reviewer_label.strip()) <= 80:
            raise InvalidInput("Provide a reviewer label")
        scope = self._check_no_portfolio_claim(scope, "Acknowledgment scope")
        if not 10 <= len(scope) <= 300:
            raise InvalidInput("Acknowledgment scope must have 10–300 characters")
        if type(note_id) is not int or note_id < 1:
            raise InvalidInput("Invalid dimension note ID")
        with self.db:
            self.db.execute("BEGIN IMMEDIATE")
            note = self.db.execute("""SELECT n.*,o.case_id AS option_case FROM option_dimension_notes n
                JOIN options o ON o.id=n.option_id WHERE n.id=?""", (note_id,)).fetchone()
            if not note or note["option_case"] != case_id:
                raise InvalidInput("Dimension note not in this case")
            if note["state"] != "pending":
                raise InvalidInput("Dimension note is already acknowledged")
            self.db.execute("UPDATE option_dimension_notes SET state='acknowledged' WHERE id=?",
                            (note_id,))
            cur = self.db.execute("""INSERT INTO option_dimension_events
                (note_id,reviewer_label,action,scope,noted_at) VALUES (?,?,?,?,?)""",
                (note_id, reviewer_label.strip(), "acknowledge", scope, now_utc()))
            self._event(case_id, "option_dimension_acknowledged",
                        note_id=note_id, option_id=int(note["option_id"]))
            return {"result": "acknowledged", "dimension_event_id": int(cur.lastrowid)}

    def _portfolio_readiness(self, option: dict, open_flags: list[dict],
                             dimensions: dict) -> list[str]:
        """Plain-language list of what is still missing. Never a declaration
        of readiness, eligibility, benefit, or authorization."""
        operational = option["operational_status"]
        if operational in ("rejected", "withdrawn", "expired"):
            return [f"Preserved as {operational}. No further review action is recorded."]
        items = []
        if option["review_state"] == "needs_review":
            items.append("Needs another review: its basis changed since the last review.")
        objections = [item for item in open_flags if item["kind"] == "objection"]
        if objections:
            items.append(f"{len(objections)} open objection(s) with a recorded reason.")
        for item in open_flags:
            if item["kind"] in ("deferred", "reserved"):
                items.append(f"Marked {item['kind']}: {item['label']}.")
        for dimension in self.OPTION_DIMENSIONS:
            if dimensions[dimension]["state"] != "acknowledged":
                items.append(f"No acknowledged note on "
                             f"{self.OPTION_DIMENSION_LABELS[dimension].lower()}.")
        unfinished = [task for task in option["preparation_tasks"] if task["status"] != "done"]
        if unfinished:
            items.append(f"{len(unfinished)} preparation step(s) not finished.")
        if any(task["status"] != "done" and task["lead_time_days"] is None
               for task in option["preparation_tasks"]):
            items.append("Some preparation durations are unknown.")
        if option["potential_discussion_deadline"]["date"] is None:
            items.append("Potential discussion timing is unknown; this is not a clinical deadline.")
        if not items:
            items.append("No open items recorded. A clinician must still review this record; "
                         "nothing here states eligibility, benefit, or authorization.")
        return items

    def _portfolio_triggers(self, option: dict, open_flags: list[dict]) -> list[str]:
        triggers = []
        if option["review_state"] == "needs_review":
            triggers.append("Re-review trigger: the basis changed; record a new review.")
        if option["snapshot_state"] == "stale":
            triggers.append("Based on a stale investigation; a new proposal may be needed.")
        for item in open_flags:
            triggers.append(f"Open {item['kind']}: {item['label']}.")
        for threat in option["threats"]:
            if threat["threat_date"]:
                triggers.append(f"Threat ({threat['kind']}): {threat['description']} — "
                                f"{threat['threat_date']} ({threat['threat_basis']}).")
            else:
                triggers.append(f"Threat ({threat['kind']}): {threat['description']} — date unknown.")
        return triggers

    def option_portfolio(self, case_id: str) -> dict:
        """Derived per-case option portfolio: every option ever proposed, with
        prerequisites, objections, access notes, readiness, timing, and
        expiration/review triggers. Read-only projection over the existing
        ledger plus portfolio records; terminal and held entries stay visible
        with their recorded reasons, never silently dropped."""
        self._case(case_id)
        view = self.option_view(case_id)
        entries = []
        for option in view["options"]:
            option_id = int(option["id"])
            notes = []
            for row in self.db.execute(
                    "SELECT * FROM option_dimension_notes WHERE option_id=? ORDER BY id",
                    (option_id,)).fetchall():
                events = self._dicts(self.db.execute(
                    "SELECT * FROM option_dimension_events WHERE note_id=? ORDER BY id",
                    (row["id"],)).fetchall())
                notes.append({**dict(row),
                              "premise": self._portfolio_premise_text(
                                  row["source_version_id"], row["evidence_assessment_id"]),
                              "events": events})
            dimensions = {}
            for dimension in self.OPTION_DIMENSIONS:
                dimension_notes = [item for item in notes if item["dimension"] == dimension]
                if any(item["state"] == "acknowledged" for item in dimension_notes):
                    dimension_state = "acknowledged"
                elif dimension_notes:
                    dimension_state = "pending"
                else:
                    dimension_state = "not_recorded"
                dimensions[dimension] = {
                    "label": self.OPTION_DIMENSION_LABELS[dimension],
                    "state": dimension_state, "notes": dimension_notes}
            open_flags = [item for item in option["flags"] if item["state"] == "open"]
            entries.append({
                "id": option_id,
                "label": option["label"],
                "description": option["description"],
                "portfolio_status": option["display_operational_status"],
                "operational_status": option["operational_status"],
                "epistemic_status": option["derived_epistemic_status"],
                "review_state": option["review_state"],
                "proposal_snapshot_id": option["proposal_snapshot_id"],
                "current_snapshot_id": option["snapshot_id"],
                "snapshot_state": option["snapshot_state"],
                "prerequisites": [
                    {"kind": dep["kind"], "target": dep["target"],
                     "deadline_date": dep["deadline_date"],
                     "deadline_basis": dep["deadline_basis"],
                     "lead_time_days": dep["lead_time_days"]}
                    for dep in option["dependencies"]],
                "preparation_tasks": option["preparation_tasks"],
                "objections": {
                    "open": [item for item in open_flags if item["kind"] == "objection"],
                    "resolved": [item for item in option["flags"]
                                 if item["kind"] == "objection" and item["state"] == "resolved"]},
                "holds": [item for item in open_flags if item["kind"] in ("deferred", "reserved")],
                "past_holds": [item for item in option["flags"]
                               if item["kind"] in ("deferred", "reserved")
                               and item["state"] == "resolved"],
                "dimensions": dimensions,
                "readiness": self._portfolio_readiness(option, open_flags, dimensions),
                "lead_time": option["potential_discussion_deadline"],
                "triggers": self._portfolio_triggers(option, open_flags),
                "review_events": option["review_events"],
                "created_at": option["created_at"],
            })
        counts: dict[str, int] = {}
        for entry in entries:
            counts[entry["portfolio_status"]] = counts.get(entry["portfolio_status"], 0) + 1
        return {"case_id": case_id,
                "projection_mode": "current_state_with_review_history",
                "disclaimer": self.PORTFOLIO_DISCLAIMER,
                "counts": counts,
                "options": entries}

    def _invalidate_evidence_version(self, evidence_version_id: int, *, reason: str,
                                     assignee_label: str | None = None,
                                     due_date: str | None = None) -> tuple[list[int], list[int]]:
        """Invalidate dependent snapshots across ALL synthetic cases, retaining history.

        Caller must own a write transaction. Only snapshots citing this exact
        immutable evidence version are affected. Each newly stale snapshot
        also gets one open re-review task in the same transaction.
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
                event_id = self._event(case_id, "evidence_invalidated",
                                       evidence_version_id=evidence_version_id,
                                       reason=reason, invalidated_snapshots=changed)
                self._create_re_review_tasks(
                    case_id=case_id, snapshot_ids=changed, cause="evidence_change",
                    invalidating_event_id=event_id, assignee_label=assignee_label,
                    due_date=due_date, evidence_version_id=evidence_version_id)
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

    def import_synthetic_evidence(self, raw: bytes, *,
                                  assignee_label: str | None = None,
                                  due_date: str | None = None) -> dict:
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
                invalidated, invalidated_options = self._invalidate_evidence_version(
                    previous["id"], reason="amendment",
                    assignee_label=assignee_label, due_date=due_date)
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

    def withdraw_synthetic_evidence(self, evidence_version_id: int, reason: str, *,
                                    assignee_label: str | None = None,
                                    due_date: str | None = None) -> dict:
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
            affected, affected_options = self._invalidate_evidence_version(
                evidence_version_id, reason="withdrawal",
                assignee_label=assignee_label, due_date=due_date)
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

    def _invalidate_broker_source(self, rights_source_id: int, *, reason: str,
                                  assignee_label: str | None = None,
                                  due_date: str | None = None,
                                  superseding_rights_source_id: int | None = None) -> list[int]:
        """Invalidate non-stale snapshots citing this rights source row.

        Caller must own a write transaction. History is retained: the
        snapshot rows stay, marked stale, and their questions reopen. Each
        newly stale snapshot also gets one open re-review task in the same
        transaction. The reason is the task cause (revocation/correction).
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
                event_id = self._event(case_id, "broker_invalidated",
                                       rights_source_id=rights_source_id,
                                       reason=reason, invalidated_snapshots=changed)
                self._create_re_review_tasks(
                    case_id=case_id, snapshot_ids=changed, cause=reason,
                    invalidating_event_id=event_id, assignee_label=assignee_label,
                    due_date=due_date, rights_source_id=rights_source_id,
                    superseding_rights_source_id=superseding_rights_source_id)
        # OI-021: same transaction, dependent options only. Rights sources
        # are shared, so this fan-out is global exactly like the snapshot
        # fan-out above; mirrors _invalidate_evidence_version.
        invalidated_options = self._invalidate_options(
            snapshot_ids=set(invalidated), source_version_ids=set(),
            evidence_version_ids=set())
        if invalidated_options:
            option_cases = {str(r[0]) for r in self.db.execute(
                "SELECT DISTINCT case_id FROM options WHERE id IN (%s)" %
                ",".join("?" for _ in invalidated_options), invalidated_options).fetchall()}
            for case_id in sorted(option_cases):
                per_case = [oid for oid in invalidated_options if self.db.execute(
                    "SELECT case_id FROM options WHERE id=?", (oid,)).fetchone()["case_id"] == case_id]
                self._event(case_id, "option_review_reopened",
                            rights_source_id=rights_source_id, reason=reason,
                            invalidated_options=per_case)
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

    def revoke_rights_source(self, rights_source_id: int, reason: str, *,
                             assignee_label: str | None = None,
                             due_date: str | None = None) -> dict:
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
            invalidated = self._invalidate_broker_source(
                rights_source_id, reason="revocation",
                assignee_label=assignee_label, due_date=due_date)
            invalidated_discovery = self._invalidate_discovery_source(rights_source_id, reason="revocation")
            return {"result": "revoked", "invalidated_snapshots": invalidated,
                    "invalidated_discovery_links": invalidated_discovery}

    def correct_rights_source(self, rights_source_id: int, version_label: object,
                              permissions: object, reason: str,
                              retrieved_at: object = None, *,
                              assignee_label: str | None = None,
                              due_date: str | None = None) -> dict:
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
            invalidated = self._invalidate_broker_source(
                rights_source_id, reason="correction",
                assignee_label=assignee_label, due_date=due_date,
                superseding_rights_source_id=new_id)
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
                           applicability: str, rationale: str, *,
                           assignee_label: str | None = None,
                           due_date: str | None = None) -> dict:
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
            # Keep-history: the cited basis must survive the re-review, so the
            # superseded meaning is recorded in both audit rows below before
            # the link row is updated in place.
            prior_relation = link["relation"]
            prior_applicability = link["applicability"]
            prior_rationale = link["rationale"]
            self.db.execute("""UPDATE broker_links SET relation=?,applicability=?,rationale=?
                WHERE id=?""", (relation, applicability, rationale.strip(), broker_link_id))
            self.db.execute("""INSERT INTO rights_events
                (rights_source_id,kind,reason,recorded_at) VALUES (?,'link_reviewed',?,?)""",
                (int(link["rights_source_id"]),
                 f"Broker link {broker_link_id} re-reviewed; prior meaning kept: "
                 f"{prior_relation}/{prior_applicability}: {prior_rationale}", now_utc()))
            rows = self.db.execute("""SELECT DISTINCT s.id,s.case_id,s.question_id
                FROM snapshots s JOIN snapshot_broker_links sbl ON sbl.snapshot_id=s.id
                WHERE sbl.broker_link_id=? AND s.state!='stale'""", (broker_link_id,)).fetchall()
            invalidated = [int(r["id"]) for r in rows]
            if invalidated:
                ids = ",".join("?" for _ in invalidated)
                self.db.execute(f"UPDATE snapshots SET state='stale' WHERE id IN ({ids})", invalidated)
                self.db.execute(f"""UPDATE questions SET state='open' WHERE id IN
                    (SELECT DISTINCT question_id FROM snapshots WHERE id IN ({ids}))""", invalidated)
                event_id = self._event(case_id, "broker_invalidated",
                            broker_link_id=broker_link_id,
                            reason="review", invalidated_snapshots=invalidated,
                            prior_relation=prior_relation,
                            prior_applicability=prior_applicability,
                            prior_rationale=prior_rationale)
                self._create_re_review_tasks(
                    case_id=case_id, snapshot_ids=invalidated, cause="review",
                    invalidating_event_id=event_id, assignee_label=assignee_label,
                    due_date=due_date, rights_source_id=int(link["rights_source_id"]),
                    broker_link_id=broker_link_id)
            # OI-021: same transaction, dependent options only. The staled
            # snapshots are all in this case (broker links are case-scoped),
            # so a single case event suffices.
            invalidated_options = self._invalidate_options(
                snapshot_ids=set(invalidated), source_version_ids=set(),
                evidence_version_ids=set())
            if invalidated_options:
                self._event(case_id, "option_review_reopened",
                            broker_link_id=broker_link_id, reason="review",
                            invalidated_options=invalidated_options)
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
            stripped = pointer_label.strip() if isinstance(pointer_label, str) else ""
            if (not isinstance(pointer_label, str) or not 1 <= len(stripped) <= 200
                    or "://" in pointer_label or stripped.startswith("/")
                    or stripped.startswith("\\") or re.match(r"[A-Za-z]:", stripped)):
                raise InvalidInput("Pointer label must be 1-200 characters, not a URL or path")
            pointer_label = stripped
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

    # ---- Consent & identity records: display/history only ----
    # No identity resolution, matching, or cross-case logic. Consents are
    # append-only version chains (active -> withdrawn); qualifiers are notes
    # attached to source anchors the case already has. Neither alters any
    # existing identity field, and withdrawal touches only its own chain.
    CONSENT_STATUSES = frozenset({"active", "withdrawn"})

    @staticmethod
    def _check_consent_scope(value: object) -> str:
        if not isinstance(value, str) or not 5 <= len(value.strip()) <= 500:
            raise InvalidInput("Consent scope must have 5–500 characters")
        return value.strip()

    @staticmethod
    def _check_qualifier_text(value: object) -> str:
        if not isinstance(value, str) or not 5 <= len(value.strip()) <= 500:
            raise InvalidInput("Identity note must have 5–500 characters")
        return value.strip()

    @staticmethod
    def _check_withdraw_reason(value: object) -> str:
        if not isinstance(value, str) or not 10 <= len(value.strip()) <= 600:
            raise InvalidInput("Withdrawal requires a 10–600 character reason")
        return value.strip()

    def _consent_anchor_label(self, anchor_id: int | None) -> str | None:
        if anchor_id is None:
            return None
        row = self.db.execute(
            "SELECT document_id,version FROM source_versions WHERE id=?",
            (anchor_id,)).fetchone()
        if not row:
            return None
        return f"{row['document_id']}@{row['version']} (# {anchor_id})"

    def record_consent(self, case_id: str, scope_text: object, date_recorded: object,
                       anchor_source_version_id: object = None) -> int:
        """Record one fictional consent as active (version 1). Display only."""
        case_id = self._case(case_id)
        scope = self._check_consent_scope(scope_text)
        recorded = valid_date(date_recorded) if isinstance(date_recorded, str) else None
        if recorded is None:
            raise InvalidInput("Dates must use YYYY-MM-DD")
        if anchor_source_version_id is not None:
            if type(anchor_source_version_id) is not int or anchor_source_version_id < 1:
                raise InvalidInput("Anchor source version ID must be a positive integer")
        with self.db:
            self.db.execute("BEGIN IMMEDIATE")
            if anchor_source_version_id is not None:
                anchor = self.db.execute(
                    "SELECT 1 FROM source_versions WHERE id=? AND case_id=?",
                    (anchor_source_version_id, case_id)).fetchone()
                if not anchor:
                    raise InvalidInput("Anchor source not in this case")
            stamped = now_utc()
            cur = self.db.execute("""INSERT INTO consent_records
                (case_id,scope_text,date_recorded,status,anchor_source_version_id,review_state,created_at)
                VALUES (?,?,?,'active',?,'display_only',?)""",
                (case_id, scope, recorded, anchor_source_version_id, stamped))
            consent_id = int(cur.lastrowid)
            self.db.execute("""INSERT INTO consent_versions
                (consent_id,version,status,reason,date_recorded,recorded_at)
                VALUES (?,1,'active',NULL,?,?)""",
                (consent_id, recorded, stamped))
            self._event(case_id, "consent_recorded", consent_id=consent_id, version=1)
            return consent_id

    def withdraw_consent(self, case_id: str, consent_id: int, reason: object,
                         date_recorded: object = None) -> int:
        """Append a withdrawn version; prior active version stays in history.

        Only this consent's status pointer and its own version chain change.
        No other consent, qualifier, source, question, or snapshot is touched.
        """
        case_id = self._case(case_id)
        if type(consent_id) is not int or consent_id < 1:
            raise InvalidInput("Invalid consent ID")
        why = self._check_withdraw_reason(reason)
        if date_recorded is None:
            recorded = datetime.now(timezone.utc).date().isoformat()
        elif isinstance(date_recorded, str):
            recorded = valid_date(date_recorded)
        else:
            raise InvalidInput("Dates must use YYYY-MM-DD")
        with self.db:
            self.db.execute("BEGIN IMMEDIATE")
            row = self.db.execute(
                "SELECT status FROM consent_records WHERE id=? AND case_id=?",
                (consent_id, case_id)).fetchone()
            if not row:
                raise InvalidInput("Consent not in this case")
            if row["status"] == "withdrawn":
                raise InvalidInput("Consent is already withdrawn")
            latest = self.db.execute(
                "SELECT MAX(version) AS v FROM consent_versions WHERE consent_id=?",
                (consent_id,)).fetchone()
            new_version = int(latest["v"] or 0) + 1
            self.db.execute("""INSERT INTO consent_versions
                (consent_id,version,status,reason,date_recorded,recorded_at)
                VALUES (?,?,'withdrawn',?,?,?)""",
                (consent_id, new_version, why, recorded, now_utc()))
            self.db.execute("UPDATE consent_records SET status='withdrawn' WHERE id=?",
                            (consent_id,))
            self._event(case_id, "consent_withdrawn",
                        consent_id=consent_id, version=new_version)
            return new_version

    def list_consents(self, case_id: str) -> list[dict]:
        """Current consents with full ordered history, this case only."""
        case_id = self._case(case_id)
        rows = self.db.execute(
            "SELECT * FROM consent_records WHERE case_id=? ORDER BY id",
            (case_id,)).fetchall()
        out: list[dict] = []
        for row in rows:
            item = dict(row)
            versions = self._dicts(self.db.execute(
                "SELECT version,status,reason,date_recorded,recorded_at"
                " FROM consent_versions WHERE consent_id=? ORDER BY version",
                (item["id"],)).fetchall())
            item["versions"] = versions
            item["anchor_label"] = self._consent_anchor_label(item["anchor_source_version_id"])
            item["fictional"] = True
            item["synthetic"] = True
            out.append(item)
        return out

    def add_identity_qualifier(self, case_id: str, qualifier_text: object,
                               anchor_source_version_id: object, date_recorded: object,
                               anchor_line: object = None) -> int:
        """Record one fictional note attached to an anchor this case already has.

        No identity field is created, matched, merged, or altered. The anchor
        must be a source version in this same case; cross-case anchors fail.
        """
        case_id = self._case(case_id)
        text = self._check_qualifier_text(qualifier_text)
        recorded = valid_date(date_recorded) if isinstance(date_recorded, str) else None
        if recorded is None:
            raise InvalidInput("Dates must use YYYY-MM-DD")
        if type(anchor_source_version_id) is not int or anchor_source_version_id < 1:
            raise InvalidInput("Anchor source version ID must be a positive integer")
        if anchor_line is not None:
            if type(anchor_line) is not int or anchor_line < 1:
                raise InvalidInput("Anchor line must be a positive integer")
        with self.db:
            self.db.execute("BEGIN IMMEDIATE")
            source = self.db.execute(
                "SELECT raw FROM source_versions WHERE id=? AND case_id=?",
                (anchor_source_version_id, case_id)).fetchone()
            if not source:
                raise InvalidInput("Anchor source not in this case")
            if anchor_line is not None:
                line_count = len(bytes(source["raw"]).decode("utf-8").splitlines())
                if anchor_line > line_count:
                    raise InvalidInput("Anchor line not in source version")
            cur = self.db.execute("""INSERT INTO identity_qualifiers
                (case_id,qualifier_text,anchor_source_version_id,anchor_line,
                 date_recorded,review_state,created_at)
                VALUES (?,?,?,?,?,'display_only',?)""",
                (case_id, text, anchor_source_version_id, anchor_line,
                 recorded, now_utc()))
            qualifier_id = int(cur.lastrowid)
            self._event(case_id, "identity_qualifier_added",
                        qualifier_id=qualifier_id,
                        anchor_source_version_id=anchor_source_version_id)
            return qualifier_id

    def list_identity_qualifiers(self, case_id: str) -> list[dict]:
        """Qualifier notes with anchors, this case only. No resolution."""
        case_id = self._case(case_id)
        rows = self.db.execute(
            """SELECT q.*, s.document_id, s.version AS source_version
            FROM identity_qualifiers q
            LEFT JOIN source_versions s ON s.id=q.anchor_source_version_id
            WHERE q.case_id=? ORDER BY q.id""",
            (case_id,)).fetchall()
        out: list[dict] = []
        for row in rows:
            item = dict(row)
            if item["document_id"] is None:
                label = f"source #{item['anchor_source_version_id']} (unavailable)"
            else:
                label = f"{item['document_id']}@{item['source_version']} (# {item['anchor_source_version_id']})"
            if item["anchor_line"] is not None:
                label += f", line {item['anchor_line']}"
            item["anchor_label"] = label
            item["fictional"] = True
            item["synthetic"] = True
            out.append(item)
        return out

    # ---- Patient goals + lived experience (fictional patient words) ----
    # Patient words stay patient words. These methods never create
    # assertions, snapshots, options, or mission entries, and they accept
    # no diagnosis, staging, or response fields. Every version keeps its
    # stated date, receipt time, and previous-version link as its anchor.
    PATIENT_GOAL_STATUSES = frozenset({"active", "achieved", "changed", "abandoned"})
    PATIENT_NOTE_KINDS = frozenset({"lived_experience", "symptom"})
    PATIENT_DISCLAIMER = ("Fictional patient's own words, for discussion only. "
                          "Never a diagnosis, staging, response claim, or recommendation.")

    @staticmethod
    def _patient_text(value: object, field: str, low: int, high: int) -> str:
        if not isinstance(value, str) or not low <= len(value.strip()) <= high:
            raise InvalidInput(f"{field} must have {low}–{high} characters")
        return value.strip()

    @staticmethod
    def _patient_optional_date(value: object) -> str | None:
        if value is None or value == "":
            return None
        if not isinstance(value, str):
            raise InvalidInput("Dates must use YYYY-MM-DD")
        return valid_date(value)

    def add_patient_goal(self, case_id: str, statement: object, stated_date: object,
                         review_trigger: object, review_date: object = None) -> dict:
        """Record a new fictional patient goal in the patient's own words."""
        case_id = self._case(case_id)
        text = self._patient_text(statement, "Goal statement", 4, 1000)
        stated = valid_date(stated_date) if isinstance(stated_date, str) else None
        if stated is None:
            raise InvalidInput("Dates must use YYYY-MM-DD")
        trigger = self._patient_text(review_trigger, "Review trigger", 4, 300)
        review = self._patient_optional_date(review_date)
        with self.db:
            self.db.execute("BEGIN IMMEDIATE")
            stamped = now_utc()
            head = self.db.execute("INSERT INTO patient_goals (case_id,created_at) VALUES (?,?)",
                                   (case_id, stamped))
            goal_id = int(head.lastrowid)
            cur = self.db.execute("""INSERT INTO patient_goal_versions
                (goal_id,version,statement,stated_date,review_trigger,review_date,
                 status,status_reason,record_state,previous_id,created_at)
                VALUES (?,?,?,?,?,?,'active',NULL,'current',NULL,?)""",
                (goal_id, 1, text, stated, trigger, review, stamped))
            self._event(case_id, "patient_goal_created", goal_id=goal_id,
                        version=1, version_id=int(cur.lastrowid))
            return {"goal_id": goal_id, "version": 1, "version_id": int(cur.lastrowid)}

    def _current_goal_version(self, case_id: str, goal_id: int) -> sqlite3.Row:
        if type(goal_id) is not int or goal_id < 1:
            raise InvalidInput("Invalid patient goal ID")
        head = self.db.execute("SELECT case_id FROM patient_goals WHERE id=?", (goal_id,)).fetchone()
        if not head or head["case_id"] != case_id:
            raise InvalidInput("Patient goal not in this case")
        current = self.db.execute("""SELECT * FROM patient_goal_versions
            WHERE goal_id=? AND record_state='current'""", (goal_id,)).fetchone()
        if not current:
            raise InvalidInput("Patient goal has no current version")
        return current

    def amend_patient_goal(self, case_id: str, goal_id: int, statement: object,
                           stated_date: object, review_trigger: object,
                           review_date: object = None) -> dict:
        """Amend a goal's words, dates, or trigger. The old version is preserved."""
        case_id = self._case(case_id)
        text = self._patient_text(statement, "Goal statement", 4, 1000)
        stated = valid_date(stated_date) if isinstance(stated_date, str) else None
        if stated is None:
            raise InvalidInput("Dates must use YYYY-MM-DD")
        trigger = self._patient_text(review_trigger, "Review trigger", 4, 300)
        review = self._patient_optional_date(review_date)
        with self.db:
            self.db.execute("BEGIN IMMEDIATE")
            current = self._current_goal_version(case_id, goal_id)
            if (text == current["statement"] and stated == current["stated_date"]
                    and trigger == current["review_trigger"]
                    and review == current["review_date"]):
                raise InvalidInput("Amendment must change the wording, dates, or review trigger")
            self.db.execute("UPDATE patient_goal_versions SET record_state='superseded' WHERE id=?",
                            (current["id"],))
            nxt = int(current["version"]) + 1
            stamped = now_utc()
            cur = self.db.execute("""INSERT INTO patient_goal_versions
                (goal_id,version,statement,stated_date,review_trigger,review_date,
                 status,status_reason,record_state,previous_id,created_at)
                VALUES (?,?,?,?,?,?,?,?,'current',?,?)""",
                (goal_id, nxt, text, stated, trigger, review,
                 current["status"], current["status_reason"], current["id"], stamped))
            self._event(case_id, "patient_goal_amended", goal_id=goal_id,
                        version=nxt, version_id=int(cur.lastrowid),
                        supersedes_version_id=int(current["id"]))
            return {"goal_id": goal_id, "version": nxt, "version_id": int(cur.lastrowid)}

    def set_patient_goal_status(self, case_id: str, goal_id: int, status: object,
                                reason: object) -> dict:
        """Mark a goal achieved, changed, or abandoned with a reason.

        Any status change creates a new preserved version; nothing is
        overwritten. The reason is required so the change stays reviewable.
        """
        case_id = self._case(case_id)
        if status not in self.PATIENT_GOAL_STATUSES:
            raise InvalidInput("Goal status must be active, achieved, changed, or abandoned")
        why = self._patient_text(reason, "Status reason", 4, 300)
        with self.db:
            self.db.execute("BEGIN IMMEDIATE")
            current = self._current_goal_version(case_id, goal_id)
            if status == current["status"]:
                raise InvalidInput(f"Goal is already marked {status}")
            self.db.execute("UPDATE patient_goal_versions SET record_state='superseded' WHERE id=?",
                            (current["id"],))
            nxt = int(current["version"]) + 1
            stamped = now_utc()
            cur = self.db.execute("""INSERT INTO patient_goal_versions
                (goal_id,version,statement,stated_date,review_trigger,review_date,
                 status,status_reason,record_state,previous_id,created_at)
                VALUES (?,?,?,?,?,?,?,?,'current',?,?)""",
                (goal_id, nxt, current["statement"], current["stated_date"],
                 current["review_trigger"], current["review_date"],
                 status, why, current["id"], stamped))
            self._event(case_id, "patient_goal_status_changed", goal_id=goal_id,
                        version=nxt, version_id=int(cur.lastrowid), status=status)
            return {"goal_id": goal_id, "version": nxt,
                    "version_id": int(cur.lastrowid), "status": status}

    def patient_goals(self, case_id: str) -> list[dict]:
        """Current goals with full preserved version history, oldest first."""
        case_id = self._case(case_id)
        goals = []
        for head in self.db.execute("SELECT * FROM patient_goals WHERE case_id=? ORDER BY id",
                                    (case_id,)).fetchall():
            versions = self._dicts(self.db.execute(
                "SELECT * FROM patient_goal_versions WHERE goal_id=? ORDER BY version",
                (head["id"],)).fetchall())
            current = next((v for v in versions if v["record_state"] == "current"), None)
            goals.append({"goal_id": head["id"], "case_id": head["case_id"],
                          "created_at": head["created_at"],
                          "provenance": "fictional-patient-words",
                          "patient_reported": True, "clinical_interpretation": None,
                          "current": current, "versions": versions})
        return goals

    def add_patient_note(self, case_id: str, kind: object, text: object,
                         noted_date: object) -> dict:
        """Record a lived-experience or symptom note in the patient's own words.

        Symptom notes are stored verbatim as patient-reported text. They are
        never parsed into findings and never create clinical records.
        """
        case_id = self._case(case_id)
        if kind not in self.PATIENT_NOTE_KINDS:
            raise InvalidInput("Note kind must be lived_experience or symptom")
        body = self._patient_text(text, "Note text", 4, 1000)
        noted = valid_date(noted_date) if isinstance(noted_date, str) else None
        if noted is None:
            raise InvalidInput("Dates must use YYYY-MM-DD")
        with self.db:
            self.db.execute("BEGIN IMMEDIATE")
            stamped = now_utc()
            head = self.db.execute("INSERT INTO patient_notes (case_id,kind,created_at) VALUES (?,?,?)",
                                   (case_id, kind, stamped))
            note_id = int(head.lastrowid)
            cur = self.db.execute("""INSERT INTO patient_note_versions
                (note_id,version,note_text,noted_date,record_state,previous_id,created_at)
                VALUES (?,?,?,?,'current',NULL,?)""",
                (note_id, 1, body, noted, stamped))
            self._event(case_id, "patient_note_created", note_id=note_id,
                        note_kind=kind, version=1, version_id=int(cur.lastrowid))
            return {"note_id": note_id, "version": 1, "version_id": int(cur.lastrowid)}

    def amend_patient_note(self, case_id: str, note_id: int, text: object,
                           noted_date: object) -> dict:
        """Amend a note's wording or date. The old version is preserved."""
        case_id = self._case(case_id)
        if type(note_id) is not int or note_id < 1:
            raise InvalidInput("Invalid patient note ID")
        body = self._patient_text(text, "Note text", 4, 1000)
        noted = valid_date(noted_date) if isinstance(noted_date, str) else None
        if noted is None:
            raise InvalidInput("Dates must use YYYY-MM-DD")
        with self.db:
            self.db.execute("BEGIN IMMEDIATE")
            head = self.db.execute("SELECT case_id FROM patient_notes WHERE id=?",
                                   (note_id,)).fetchone()
            if not head or head["case_id"] != case_id:
                raise InvalidInput("Patient note not in this case")
            current = self.db.execute("""SELECT * FROM patient_note_versions
                WHERE note_id=? AND record_state='current'""", (note_id,)).fetchone()
            if not current:
                raise InvalidInput("Patient note has no current version")
            if body == current["note_text"] and noted == current["noted_date"]:
                raise InvalidInput("Amendment must change the wording or noted date")
            self.db.execute("UPDATE patient_note_versions SET record_state='superseded' WHERE id=?",
                            (current["id"],))
            nxt = int(current["version"]) + 1
            stamped = now_utc()
            cur = self.db.execute("""INSERT INTO patient_note_versions
                (note_id,version,note_text,noted_date,record_state,previous_id,created_at)
                VALUES (?,?,?,?,'current',?,?)""",
                (note_id, nxt, body, noted, current["id"], stamped))
            self._event(case_id, "patient_note_amended", note_id=note_id,
                        version=nxt, version_id=int(cur.lastrowid),
                        supersedes_version_id=int(current["id"]))
            return {"note_id": note_id, "version": nxt, "version_id": int(cur.lastrowid)}

    def patient_notes(self, case_id: str) -> list[dict]:
        """Current notes with full preserved version history, oldest first."""
        case_id = self._case(case_id)
        notes = []
        for head in self.db.execute("SELECT * FROM patient_notes WHERE case_id=? ORDER BY id",
                                    (case_id,)).fetchall():
            versions = self._dicts(self.db.execute(
                "SELECT * FROM patient_note_versions WHERE note_id=? ORDER BY version",
                (head["id"],)).fetchall())
            current = next((v for v in versions if v["record_state"] == "current"), None)
            notes.append({"note_id": head["id"], "case_id": head["case_id"],
                          "kind": head["kind"], "created_at": head["created_at"],
                          "provenance": "fictional-patient-words",
                          "patient_reported": True, "clinical_interpretation": None,
                          "current": current, "versions": versions})
        return notes

    def add_bio_explanation(self, case_id: str, question_id: int, label: str,
                            mechanism_text: str, episode_id: str,
                            source_version_id: int,
                            specimen_state: str = "unknown",
                            specimen_id: str | None = None,
                            lesion_state: str = "unknown",
                            lesion_id: str | None = None,
                            clinical_context_state: str = "unknown",
                            clinical_context_value: str | None = None) -> int:
        """Propose one human-authored biological explanation for one question.

        Competing hypotheses survive side by side: creation never alters,
        supersedes, or withdraws a sibling explanation. Context states are
        explicit — unknown is stored, never defaulted — and a recorded
        specimen that contradicts the anchored source's specimen is rejected,
        so a new specimen is never confused with an amendment of an old one.
        The anchor source is creation provenance; amendment staleness follows
        the same anchor-exact rule as snapshots and inventory assertions.
        """
        case_id = self._case(case_id)
        label = _check_bio_language(label, "Explanation label")
        if not 1 <= len(label) <= 120:
            raise InvalidInput("Explanation label must have 1–120 characters")
        mechanism_text = _check_bio_language(mechanism_text, "Mechanism text")
        if not 10 <= len(mechanism_text) <= 1000:
            raise InvalidInput("Mechanism text must have 10–1000 characters")
        episode_id = valid_id(episode_id)
        if type(question_id) is not int or question_id < 1:
            raise InvalidInput("Question ID must be a positive integer")
        if type(source_version_id) is not int or source_version_id < 1:
            raise InvalidInput("Source version ID must be a positive integer")
        if specimen_state not in ("recorded", "unknown"):
            raise InvalidInput("Specimen state must be recorded or unknown")
        if specimen_state == "recorded":
            if specimen_id is None:
                raise InvalidInput("Recorded specimen requires a specimen ID")
            specimen_id = valid_id(specimen_id)
        elif specimen_id is not None:
            raise InvalidInput("Unknown specimen must not carry a specimen ID")
        if lesion_state not in ("recorded", "unknown"):
            raise InvalidInput("Lesion state must be recorded or unknown")
        if lesion_state == "recorded":
            if lesion_id is None:
                raise InvalidInput("Recorded lesion requires a lesion ID")
            lesion_id = valid_id(lesion_id)
        elif lesion_id is not None:
            raise InvalidInput("Unknown lesion must not carry a lesion ID")
        if clinical_context_state not in FIELD_STATES:
            raise InvalidInput("Clinical context state must be known or unknown")
        if clinical_context_state == "known":
            if not isinstance(clinical_context_value, str) or not 1 <= len(clinical_context_value.strip()) <= 120:
                raise InvalidInput("Known clinical context requires a 1–120 character label")
            clinical_context_value = _check_bio_language(
                clinical_context_value.strip(), "Clinical context label")
        elif clinical_context_value is not None:
            raise InvalidInput("Unknown clinical context must not carry a label")
        with self.db:
            self.db.execute("BEGIN IMMEDIATE")
            if not self.db.execute("SELECT 1 FROM questions WHERE id=? AND case_id=?",
                                   (question_id, case_id)).fetchone():
                raise InvalidInput("Question not in this case")
            source = self.db.execute(
                "SELECT specimen_id, state FROM source_versions WHERE id=? AND case_id=?",
                (source_version_id, case_id)).fetchone()
            if not source or source["state"] != "current":
                raise InvalidInput("Explanation source is missing, superseded, or belongs to another case")
            if (specimen_state == "recorded" and source["specimen_id"] is not None
                    and source["specimen_id"] != specimen_id):
                raise InvalidInput(
                    "Explanation specimen does not match the anchored source's specimen; "
                    "a new specimen is a distinct context, never an amendment")
            cur = self.db.execute("""INSERT INTO bio_explanations
                (case_id,question_id,label,mechanism_text,episode_id,
                 specimen_state,specimen_id,lesion_state,lesion_id,
                 clinical_context_state,clinical_context_value,
                 source_version_id,state,created_at)
                VALUES (?,?,?,?,?,?,?,?,?,?,?,?, 'current',?)""",
                (case_id, question_id, label, mechanism_text, episode_id,
                 specimen_state, specimen_id, lesion_state, lesion_id,
                 clinical_context_state, clinical_context_value,
                 source_version_id, now_utc()))
            self._event(case_id, "bio_explanation_proposed",
                        bio_explanation_id=int(cur.lastrowid), question_id=question_id,
                        source_version_id=source_version_id)
            return int(cur.lastrowid)

    def record_bio_assay_observation(self, case_id: str, explanation_id: int,
                                     method_label: str, result_note: str,
                                     source_version_id: int, reference_kind: str,
                                     tissue_block_state: str = "unknown",
                                     tissue_block_asset_id: int | None = None,
                                     matched_control_state: str = "unknown",
                                     matched_control_specimen: str | None = None) -> int:
        """Record one assay observation against exactly one tissue context.

        Each observation cites at most one tissue block, and a recorded block
        must share the explanation's episode, so assays from different blocks
        or tumors are never silently pooled. A missing matched control is a
        first-class stored state, and the reference kind explicitly separates
        the patient's own normal tissue from an external reference population.
        Unknown is stored, never defaulted: every context dimension requires
        an explicit state, and values are rejected unless their state allows.
        A stale explanation cannot grow new observations; propose anew, so a
        changed basis is never silently extended.
        """
        case_id = self._case(case_id)
        method_label = _check_bio_language(method_label, "Assay method label")
        if not 1 <= len(method_label) <= 120:
            raise InvalidInput("Assay method label must have 1–120 characters")
        result_note = _check_bio_language(result_note, "Result note")
        if not 10 <= len(result_note) <= 500:
            raise InvalidInput("Result note must have 10–500 characters")
        if type(explanation_id) is not int or explanation_id < 1:
            raise InvalidInput("Explanation ID must be a positive integer")
        if type(source_version_id) is not int or source_version_id < 1:
            raise InvalidInput("Source version ID must be a positive integer")
        if reference_kind not in ("patient_normal", "external_population", "unknown"):
            raise InvalidInput("Reference kind must be patient_normal, external_population, or unknown")
        if tissue_block_state not in ("recorded", "unknown"):
            raise InvalidInput("Tissue block state must be recorded or unknown")
        if tissue_block_state == "recorded":
            if type(tissue_block_asset_id) is not int or tissue_block_asset_id < 1:
                raise InvalidInput("Recorded tissue block requires a biological asset ID")
        elif tissue_block_asset_id is not None:
            raise InvalidInput("Unknown tissue block must not carry an asset ID")
        if matched_control_state not in ("recorded", "missing", "unknown"):
            raise InvalidInput("Matched control state must be recorded, missing, or unknown")
        if matched_control_state == "recorded":
            if matched_control_specimen is None:
                raise InvalidInput("Recorded matched control requires a specimen ID")
            matched_control_specimen = valid_id(matched_control_specimen)
        elif matched_control_specimen is not None:
            raise InvalidInput("A missing or unknown matched control must not carry a specimen ID")
        with self.db:
            self.db.execute("BEGIN IMMEDIATE")
            explanation = self.db.execute(
                "SELECT episode_id, state FROM bio_explanations WHERE id=? AND case_id=?",
                (explanation_id, case_id)).fetchone()
            if not explanation:
                raise InvalidInput("Biological explanation not in this case")
            if explanation["state"] != "current":
                raise InvalidInput(
                    "Biological explanation is stale; propose a new explanation "
                    "instead of extending it")
            source = self.db.execute(
                "SELECT specimen_id, state FROM source_versions WHERE id=? AND case_id=?",
                (source_version_id, case_id)).fetchone()
            if not source or source["state"] != "current":
                raise InvalidInput("Assay source is missing, superseded, or belongs to another case")
            if tissue_block_state == "recorded":
                block = self.db.execute(
                    "SELECT kind, episode_id, specimen_id, specimen_state FROM biological_assets "
                    "WHERE id=? AND case_id=?", (tissue_block_asset_id, case_id)).fetchone()
                if not block:
                    raise InvalidInput("Tissue block asset not in this case")
                if block["kind"] not in BIO_TISSUE_BLOCK_KINDS:
                    raise InvalidInput(
                        "Assay tissue must be a physical tissue block (ffpe_block or "
                        "fresh_frozen_aliquot); derivatives cannot silently stand in for one")
                if block["episode_id"] != explanation["episode_id"]:
                    raise InvalidInput(
                        "Assay tissue block must share the explanation's episode; "
                        "tumors are never pooled across episodes")
                if (block["specimen_state"] == "recorded" and source["specimen_id"] is not None
                        and block["specimen_id"] != source["specimen_id"]):
                    raise InvalidInput(
                        "Tissue block specimen does not match the anchored source's specimen; "
                        "a new specimen is a distinct context, never an amendment")
            cur = self.db.execute("""INSERT INTO bio_assay_observations
                (case_id,explanation_id,method_label,tissue_block_state,tissue_block_asset_id,
                 matched_control_state,matched_control_specimen,reference_kind,result_note,
                 source_version_id,state,created_at)
                VALUES (?,?,?,?,?,?,?,?,?,?, 'current',?)""",
                (case_id, explanation_id, method_label, tissue_block_state, tissue_block_asset_id,
                 matched_control_state, matched_control_specimen, reference_kind, result_note,
                 source_version_id, now_utc()))
            self._event(case_id, "bio_assay_observed",
                        bio_assay_observation_id=int(cur.lastrowid),
                        explanation_id=explanation_id, source_version_id=source_version_id)
            return int(cur.lastrowid)

    def add_question(self, case_id: str, question: str, owner_label: str | None = None) -> int:
        self._case(case_id)
        if not isinstance(question, str) or not 5 <= len(question.strip()) <= 500:
            raise InvalidInput("Question must have 5–500 characters")
        owner = self._check_owner_label(owner_label) if owner_label is not None else None
        triage = "owned" if owner else "unsorted"
        with self.db:
            cur = self.db.execute(
                "INSERT INTO questions (case_id,question,state,owner_label,triage,created_at) VALUES (?,?,?,?,?,?)",
                (case_id, question.strip(), "open", owner, triage, now_utc()))
            question_id = int(cur.lastrowid)
            self._event(case_id, "question_created", question_id=question_id)
            if owner:
                self.db.execute(
                    "INSERT INTO question_owner_history (case_id,question_id,owner_label,assigned_at) VALUES (?,?,?,?)",
                    (case_id, question_id, owner, now_utc()))
                self._event(case_id, "question_owner_assigned", question_id=question_id)
        return question_id

    @staticmethod
    def _check_owner_label(owner_label: object) -> str:
        """Validate a fictional owner label. Attribution only, never authorization."""
        if not isinstance(owner_label, str) or not 2 <= len(owner_label.strip()) <= 80:
            raise InvalidInput("Question owner label must have 2–80 characters")
        return owner_label.strip()

    def _question_row(self, case_id: str, question_id: int) -> sqlite3.Row:
        if type(question_id) is not int:
            raise InvalidInput("Question id must be an integer")
        row = self.db.execute("SELECT * FROM questions WHERE id=? AND case_id=?",
                              (question_id, case_id)).fetchone()
        if not row:
            raise InvalidInput("Question not in this case")
        return row

    def assign_question_owner(self, case_id: str, question_id: int, owner_label: str) -> int:
        """Attach a fictional owner label; every assignment appends history.

        The questions row keeps only the current label; the full sequence of
        assignments is preserved in question_owner_history, which is never
        updated or deleted. Owner labels are attribution, not authorization.
        """
        self._case(case_id)
        owner = self._check_owner_label(owner_label)
        with self.db:
            self.db.execute("BEGIN IMMEDIATE")
            row = self._question_row(case_id, question_id)
            self.db.execute("UPDATE questions SET owner_label=? WHERE id=?", (owner, question_id))
            if row["triage"] == "unsorted":
                self.db.execute("UPDATE questions SET triage='owned' WHERE id=?", (question_id,))
            cur = self.db.execute(
                "INSERT INTO question_owner_history (case_id,question_id,owner_label,assigned_at) VALUES (?,?,?,?)",
                (case_id, question_id, owner, now_utc()))
            self._event(case_id, "question_owner_assigned", question_id=question_id,
                        history_id=cur.lastrowid)
            return int(cur.lastrowid)

    def set_question_triage(self, case_id: str, question_id: int, triage: str) -> None:
        """Set the orthogonal workflow marker; the open/addressed state is untouched."""
        self._case(case_id)
        if not isinstance(triage, str) or triage not in QUESTION_TRIAGE:
            raise InvalidInput("Invalid question triage value")
        with self.db:
            self.db.execute("BEGIN IMMEDIATE")
            row = self._question_row(case_id, question_id)
            if row["triage"] == triage:
                return
            self.db.execute("UPDATE questions SET triage=? WHERE id=?", (triage, question_id))
            self._event(case_id, "question_triage_changed", question_id=question_id,
                        previous_triage=row["triage"], triage=triage)

    def add_question_evidence_note(self, case_id: str, question_id: int, note: str) -> int:
        """Append a versioned human-authored needed-evidence note. Append-only."""
        self._case(case_id)
        if not isinstance(note, str) or not 15 <= len(note.strip()) <= 800:
            raise InvalidInput("Needed-evidence note must have 15–800 characters")
        with self.db:
            self.db.execute("BEGIN IMMEDIATE")
            self._question_row(case_id, question_id)
            current = self.db.execute(
                "SELECT COALESCE(MAX(version),0) AS top FROM question_evidence_notes WHERE question_id=?",
                (question_id,)).fetchone()
            version = int(current["top"]) + 1
            cur = self.db.execute(
                """INSERT INTO question_evidence_notes
                (case_id,question_id,version,note,created_at) VALUES (?,?,?,?,?)""",
                (case_id, question_id, version, note.strip(), now_utc()))
            self._event(case_id, "question_evidence_note_added", question_id=question_id,
                        note_id=cur.lastrowid, version=version)
            return int(cur.lastrowid)

    def list_question_owner_history(self, case_id: str, question_id: int) -> list[dict]:
        self._case(case_id)
        self._question_row(case_id, question_id)
        return self._dicts(self.db.execute(
            """SELECT id,owner_label,assigned_at FROM question_owner_history
            WHERE case_id=? AND question_id=? ORDER BY id""",
            (case_id, question_id)).fetchall())

    def list_question_evidence_notes(self, case_id: str, question_id: int) -> list[dict]:
        self._case(case_id)
        self._question_row(case_id, question_id)
        return self._dicts(self.db.execute(
            """SELECT id,version,note,created_at FROM question_evidence_notes
            WHERE case_id=? AND question_id=? ORDER BY version""",
            (case_id, question_id)).fetchall())

    # ---- Follow-through: records of agreed human work, never actions ----
    # Creation and every status change append one history row (who/when/why).
    # History rows are never updated or deleted. Completion requires a prior
    # recorded acknowledgment, so no path can claim human action was taken
    # without one. Anchors (question/source) are immutable after creation.

    def create_followthrough_task(self, case_id: str, title: str, *,
                                 detail: str | None = None,
                                 due_date: str | None = None,
                                 review_trigger: str | None = None,
                                 question_id: int | None = None,
                                 source_version_id: int | None = None,
                                 actor_label: str, reason: str | None = None) -> int:
        from .followthrough import (FollowthroughInputError, check_actor,
                                    check_due_date, check_optional_text,
                                    check_task_text)
        self._case(case_id)
        try:
            title_text = check_task_text(title, "Task title", min_len=1, max_len=120)
            detail_text = check_optional_text(detail, "Task detail", max_len=1000)
            trigger_text = check_optional_text(review_trigger, "Review trigger", max_len=300)
            actor = check_actor(actor_label)
            reason_text = check_optional_text(reason, "Creation note", max_len=600)
            due = check_due_date(due_date)
        except FollowthroughInputError as error:
            raise InvalidInput(str(error)) from error
        if question_id is not None and (type(question_id) is not int or question_id < 1):
            raise InvalidInput("Question ID must be a positive integer")
        if source_version_id is not None and (type(source_version_id) is not int or source_version_id < 1):
            raise InvalidInput("Source version ID must be a positive integer")
        with self.db:
            self.db.execute("BEGIN IMMEDIATE")
            if question_id is not None and not self.db.execute(
                    "SELECT 1 FROM questions WHERE id=? AND case_id=?",
                    (question_id, case_id)).fetchone():
                raise InvalidInput("Question not in this case")
            if source_version_id is not None and not self.db.execute(
                    "SELECT 1 FROM source_versions WHERE id=? AND case_id=? AND state='current'",
                    (source_version_id, case_id)).fetchone():
                raise InvalidInput("Source is missing, superseded, or belongs to another case")
            timestamp = now_utc()
            cur = self.db.execute("""INSERT INTO followthrough_tasks
                (case_id,title,detail,owner_label,due_date,review_trigger,status,
                 question_id,source_version_id,created_at)
                VALUES (?,?,?,NULL,?,?, 'created',?,?,?)""",
                (case_id, title_text, detail_text, due, trigger_text,
                 question_id, source_version_id, timestamp))
            task_id = int(cur.lastrowid)
            self.db.execute("""INSERT INTO followthrough_task_events
                (task_id,previous_status,new_status,actor_label,reason,noted_at)
                VALUES (?,NULL,'created',?,?,?)""",
                (task_id, actor, reason_text, timestamp))
            self._event(case_id, "followthrough_task_created", task_id=task_id)
            return task_id

    def update_followthrough_task(self, case_id: str, task_id: int, new_status: str, *,
                                 actor_label: str, reason: str,
                                 owner_label: str | None = None,
                                 due_date: object = _KEEP) -> dict:
        from .followthrough import (FollowthroughInputError, STATUSES,
                                    TRANSITIONS, check_actor, check_due_date,
                                    check_task_text)
        self._case(case_id)
        if type(task_id) is not int or task_id < 1:
            raise InvalidInput("Invalid follow-through task ID")
        if new_status not in STATUSES:
            raise InvalidInput("Invalid follow-through status")
        try:
            actor = check_actor(actor_label)
            reason_text = check_task_text(reason, "Change reason", min_len=10, max_len=600)
        except FollowthroughInputError as error:
            raise InvalidInput(str(error)) from error
        owner_text: str | None = None
        if new_status == "assigned":
            try:
                owner_text = check_task_text(owner_label, "Owner label", min_len=2, max_len=80)
            except FollowthroughInputError as error:
                raise InvalidInput(str(error)) from error
        elif owner_label is not None:
            raise InvalidInput("An owner is recorded only when a task is assigned")
        due_provided = due_date is not _KEEP
        try:
            due_value = check_due_date(due_date) if due_provided else None
        except FollowthroughInputError as error:
            raise InvalidInput(str(error)) from error
        with self.db:
            self.db.execute("BEGIN IMMEDIATE")
            row = self.db.execute("SELECT status FROM followthrough_tasks WHERE id=? AND case_id=?",
                                  (task_id, case_id)).fetchone()
            if not row:
                raise InvalidInput("Follow-through task not in this case")
            previous = row["status"]
            if new_status not in TRANSITIONS[previous]:
                if previous == "completed":
                    raise InvalidInput("A completed task stays in history; record a new task for further work")
                raise InvalidInput(
                    f"Cannot move a task from {previous} to {new_status}; "
                    "completion requires a recorded acknowledgment first")
            timestamp = now_utc()
            if new_status == "assigned":
                self.db.execute("UPDATE followthrough_tasks SET status='assigned',owner_label=? WHERE id=?",
                                (owner_text, task_id))
            else:
                self.db.execute("UPDATE followthrough_tasks SET status=? WHERE id=?",
                                (new_status, task_id))
            if due_provided:
                self.db.execute("UPDATE followthrough_tasks SET due_date=? WHERE id=?",
                                (due_value, task_id))
            cur = self.db.execute("""INSERT INTO followthrough_task_events
                (task_id,previous_status,new_status,actor_label,reason,noted_at)
                VALUES (?,?,?,?,?,?)""",
                (task_id, previous, new_status, actor, reason_text, timestamp))
            self._event(case_id, "followthrough_task_status_changed",
                        task_id=task_id, previous_status=previous, new_status=new_status)
            return {"result": new_status, "task_id": task_id,
                    "previous_status": previous, "event_id": int(cur.lastrowid)}

    def create_snapshot(self, case_id: str, question_id: int, summary: str, source_ids: list[int],
                        evidence_assessment_ids: list[int] | None = None,
                        broker_link_ids: list[int] | None = None) -> int:
        self._case(case_id)
        if type(question_id) is not int:
            raise InvalidInput("Question id must be an integer")
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
        if type(snapshot_id) is not int:
            raise InvalidInput("Snapshot id must be an integer")
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
            # The review queue derives from the same ledger, so this human
            # decision also appends a queue receipt in the same transaction:
            # the item leaves the queue with a recorded decision, never
            # silently. The receipt is an acknowledgment, not an authorization.
            self.db.execute("""INSERT INTO review_receipts
                (case_id,queue_key,kind,target_id,fingerprint,action,reviewer_label,reason,created_at)
                VALUES (?,?,?,?,?,?,?,?,?)""",
                (case_id, f"snapshot:{snapshot_id}", "investigation", snapshot_id,
                 "reviewed_in_demo", "acknowledged", reviewer_label.strip(),
                 "Recorded together with the existing demo acknowledgment; not a clinical authorization.",
                 timestamp))
            self._event(case_id, "demo_review_acknowledged", snapshot_id=snapshot_id)

    # ---- Investigation workspace: durable questions linked to source versions ----
    WORKSPACE_STATUSES = frozenset({"open", "in_progress", "answered", "needs_review"})

    def _workspace_question(self, case_id: str, question_id: int) -> sqlite3.Row:
        if type(question_id) is not int or question_id < 1:
            raise InvalidInput("Invalid investigation question ID")
        row = self.db.execute("SELECT * FROM workspace_questions WHERE id=? AND case_id=?",
                              (question_id, case_id)).fetchone()
        if not row:
            raise InvalidInput("Investigation question not in this case")
        return row

    @staticmethod
    def _workspace_reason(reason: object) -> str:
        if not isinstance(reason, str) or not 5 <= len(reason.strip()) <= 600:
            raise InvalidInput("A status change requires a recorded reason of 5–600 characters")
        return reason.strip()

    @staticmethod
    def _workspace_answer(answer: object) -> str:
        if not isinstance(answer, str) or not 10 <= len(answer.strip()) <= 3000:
            raise InvalidInput("A recorded answer must have 10–3000 characters")
        return answer.strip()

    def create_workspace_question(self, case_id: str, question: str) -> int:
        """Record one durable investigation question, starting open with no answer."""
        self._case(case_id)
        if not isinstance(question, str) or not 5 <= len(question.strip()) <= 500:
            raise InvalidInput("Question must have 5–500 characters")
        with self.db:
            self.db.execute("BEGIN IMMEDIATE")
            stamp = now_utc()
            cur = self.db.execute("""INSERT INTO workspace_questions
                (case_id,question,status,answer,created_at,updated_at) VALUES (?,?,?,NULL,?,?)""",
                (case_id, question.strip(), "open", stamp, stamp))
            question_id = int(cur.lastrowid)
            self.db.execute("""INSERT INTO workspace_question_history
                (question_id,case_id,previous_status,new_status,reason,answer,recorded_at)
                VALUES (?,?,NULL,?,?,NULL,?)""",
                (question_id, case_id, "open", "Question recorded", stamp))
            self._event(case_id, "workspace_question_created", workspace_question_id=question_id)
            return question_id

    def link_workspace_source(self, case_id: str, question_id: int,
                              source_version_id: int, reason: object = None) -> int:
        """Link one current source version to one question in the same case.

        Links are append-only records. Only one ACTIVE link per
        (question, source version) may exist; unlinking supersedes the old
        row so the same version can be linked again as a new record.
        """
        self._case(case_id)
        if type(source_version_id) is not int or source_version_id < 1:
            raise InvalidInput("Source version ID must be a positive integer")
        link_reason = ""
        if reason is not None:
            if not isinstance(reason, str) or not reason.strip() or len(reason.strip()) > 600:
                raise InvalidInput("Link reason must have 1–600 characters")
            link_reason = reason.strip()
        with self.db:
            self.db.execute("BEGIN IMMEDIATE")
            self._workspace_question(case_id, question_id)
            source = self.db.execute("SELECT state FROM source_versions WHERE id=? AND case_id=?",
                                     (source_version_id, case_id)).fetchone()
            if not source:
                raise InvalidInput("Source version not in this case")
            if source["state"] != "current":
                raise InvalidInput("Only a current source version can be newly linked")
            existing = self.db.execute("""SELECT id FROM workspace_question_links
                WHERE question_id=? AND source_version_id=? AND state='active'""",
                (question_id, source_version_id)).fetchone()
            if existing:
                raise InvalidInput("This source version is already linked to the question")
            cur = self.db.execute("""INSERT INTO workspace_question_links
                (question_id,case_id,source_version_id,state,reason,created_at)
                VALUES (?,?,?,?,?,?)""",
                (question_id, case_id, source_version_id, "active", link_reason, now_utc()))
            self._event(case_id, "workspace_question_linked",
                        workspace_question_id=question_id, link_id=cur.lastrowid,
                        source_version_id=source_version_id)
            return int(cur.lastrowid)

    def unlink_workspace_source(self, case_id: str, question_id: int,
                                link_id: int, reason: object = None) -> dict:
        """Supersede one active link. The row is kept as history, never deleted."""
        self._case(case_id)
        if type(link_id) is not int or link_id < 1:
            raise InvalidInput("Invalid link ID")
        with self.db:
            self.db.execute("BEGIN IMMEDIATE")
            self._workspace_question(case_id, question_id)
            link = self.db.execute("""SELECT state FROM workspace_question_links
                WHERE id=? AND question_id=? AND case_id=?""",
                (link_id, question_id, case_id)).fetchone()
            if not link:
                raise InvalidInput("Link not found for this question")
            if link["state"] != "active":
                raise InvalidInput("This link is already superseded")
            superseded_reason = None
            if reason is not None:
                if not isinstance(reason, str) or not reason.strip() or len(reason.strip()) > 600:
                    raise InvalidInput("Unlink reason must have 1–600 characters")
                superseded_reason = reason.strip()
            self.db.execute("""UPDATE workspace_question_links
                SET state='superseded', superseded_at=?, superseded_reason=? WHERE id=?""",
                (now_utc(), superseded_reason, link_id))
            self._event(case_id, "workspace_question_unlinked",
                        workspace_question_id=question_id, link_id=link_id)
            return {"result": "unlinked", "link_id": link_id}

    def set_workspace_question_status(self, case_id: str, question_id: int,
                                      status: str, reason: str, answer: object = None) -> dict:
        """Record one HUMAN status change. Nothing in this module moves a
        question to 'answered' on its own: the system never auto-answers."""
        self._case(case_id)
        if not isinstance(status, str) or status not in self.WORKSPACE_STATUSES:
            raise InvalidInput("Unknown investigation question status")
        clean_reason = self._workspace_reason(reason)
        with self.db:
            self.db.execute("BEGIN IMMEDIATE")
            current = self._workspace_question(case_id, question_id)
            previous = current["status"]
            if status == "answered":
                clean_answer = self._workspace_answer(answer)
                if previous == "answered" and current["answer"] == clean_answer:
                    raise InvalidInput("Question already has this status and answer")
            else:
                if answer is not None:
                    raise InvalidInput("Answer text is only accepted when marking a question answered")
                clean_answer = None
                if previous == status:
                    raise InvalidInput("Question already has this status")
            preserved = current["answer"] if previous == "answered" else None
            history_answer = clean_answer if status == "answered" else preserved
            stamp = now_utc()
            self.db.execute("UPDATE workspace_questions SET status=?, answer=?, updated_at=? WHERE id=?",
                            (status, clean_answer, stamp, question_id))
            self.db.execute("""INSERT INTO workspace_question_history
                (question_id,case_id,previous_status,new_status,reason,answer,recorded_at)
                VALUES (?,?,?,?,?,?,?)""",
                (question_id, case_id, previous, status, clean_reason, history_answer, stamp))
            self._event(case_id, "workspace_question_status_changed",
                        workspace_question_id=question_id,
                        previous_status=previous, status=status)
            return {"result": "status_recorded", "workspace_question_id": question_id,
                    "previous_status": previous, "status": status}

    def _reopen_workspace_questions(self, case_id: str, superseded_source_id: int,
                                    document_id: str, new_version: int) -> list[int]:
        """Reopen ANSWERED questions with an ACTIVE link to a superseded version.

        Caller must own a write transaction. Only the given case is touched.
        The prior answer is preserved in history; the question itself keeps no
        current answer until a human records a new one.
        """
        rows = self.db.execute("""SELECT DISTINCT q.id,q.answer FROM workspace_questions q
            JOIN workspace_question_links l ON l.question_id=q.id
            WHERE q.case_id=? AND l.case_id=? AND l.source_version_id=?
            AND l.state='active' AND q.status='answered' ORDER BY q.id""",
            (case_id, case_id, superseded_source_id)).fetchall()
        reopened = []
        for row in rows:
            stamp = now_utc()
            self.db.execute("UPDATE workspace_questions SET status='needs_review', answer=NULL, updated_at=? WHERE id=?",
                            (stamp, row["id"]))
            self.db.execute("""INSERT INTO workspace_question_history
                (question_id,case_id,previous_status,new_status,reason,answer,recorded_at)
                VALUES (?,?, 'answered','needs_review',?,?,?)""",
                (row["id"], case_id,
                 f"Linked source {document_id} was amended to version {new_version}; "
                 "the recorded answer needs human review.",
                 row["answer"], stamp))
            reopened.append(int(row["id"]))
        if reopened:
            self._event(case_id, "workspace_question_reopened",
                        source_version_id=superseded_source_id, reopened_questions=reopened)
        return reopened

    def list_workspace_questions(self, case_id: str) -> list[dict]:
        """Durable questions with their links and full status history.

        The current answer is exposed ONLY while the status is answered;
        unanswered questions always read back answer None even though prior
        answers remain visible inside their own history entries.
        """
        self._case(case_id)
        out = []
        for row in self.db.execute("SELECT * FROM workspace_questions WHERE case_id=? ORDER BY id",
                                   (case_id,)).fetchall():
            question_id = int(row["id"])
            links = []
            for link in self.db.execute("""SELECT l.*,
                v.document_id, v.version, v.state AS source_state
                FROM workspace_question_links l
                JOIN source_versions v ON v.id=l.source_version_id
                WHERE l.question_id=? ORDER BY l.id""", (question_id,)).fetchall():
                links.append({**dict(link),
                              "source_anchor": f"{link['document_id']}@{link['version']}"})
            history = self._dicts(self.db.execute(
                "SELECT * FROM workspace_question_history WHERE question_id=? ORDER BY id",
                (question_id,)).fetchall())
            data = dict(row)
            data["created_date"] = data["created_at"][:10]
            if data["status"] != "answered":
                data["answer"] = None
            data["links"] = links
            data["history"] = history
            out.append(data)
        return out
    # ---- Clinician review queue + sign-off receipts ----
    # The queue is a derived projection over the existing ledger: human
    # investigation drafts, model investigations, amended source versions,
    # held or re-review options, and fictional evidence assessments. It
    # creates no second ledger. Sign-off receipts are the only new durable
    # state, and they are append-only: there is no update or delete path.
    # A receipt records that a person looked; it never authorizes treatment.
    REVIEW_QUEUE_KINDS = frozenset({"investigation", "amendment", "held-option", "new-evidence"})
    REVIEW_RECEIPT_ACTIONS = frozenset({"reviewed", "acknowledged", "returned"})
    REVIEW_QUEUE_DISCLAIMER = (
        "Fictional demo only. A sign-off records that a person looked at the listed item; "
        "it does not approve, authorize, or recommend any treatment, test, or procedure. "
        "Items stay visible until a person records a decision; nothing is auto-approved, "
        "auto-dismissed, or removed because of age."
    )

    @staticmethod
    def _review_age_days(created_at: str) -> int:
        try:
            parsed = datetime.fromisoformat(created_at)
        except (TypeError, ValueError):
            return 0
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone.utc)
        return max(0, int((datetime.now(timezone.utc) - parsed).total_seconds() // 86400))

    def _review_queue_items(self, case_id: str) -> list[dict]:
        """Derive the current queue from the existing ledger. Reads only.

        Membership follows the ledger: every investigation draft, model
        investigation, amendment, and evidence assessment is listed, and an
        option is listed while it is visibly held (contradicted) or awaiting
        re-review after an amendment. Terminal options (rejected, withdrawn,
        expired) are historical and are not queued; their recorded decisions
        remain in the review history. Each item carries a fingerprint of the
        ledger state a receipt must match, so an amendment reopens the item
        instead of silently carrying the old decision forward.
        """
        items: list[dict] = []
        for snap in self.db.execute(
                "SELECT id,question_id,summary,state,created_at FROM snapshots"
                " WHERE case_id=? ORDER BY id", (case_id,)).fetchall():
            items.append({
                "queue_key": f"snapshot:{snap['id']}", "kind": "investigation",
                "target_id": snap["id"], "fingerprint": snap["state"],
                "title": f"Fictional investigation #{snap['id']} (question Q{snap['question_id']})",
                "detail": f"State: {snap['state']}. {snap['summary'][:160]}",
                "created_at": snap["created_at"],
                "age_days": self._review_age_days(snap["created_at"]),
            })
        for inv in self.db.execute(
                "SELECT id,question_id,template,status,stale,created_at FROM investigations"
                " WHERE case_id=? ORDER BY id", (case_id,)).fetchall():
            items.append({
                "queue_key": f"model-investigation:{inv['id']}", "kind": "investigation",
                "target_id": inv["id"], "fingerprint": f"{inv['stale']}:{inv['status']}",
                "title": f"Fictional model investigation #{inv['id']} ({inv['template']})",
                "detail": f"Status: {inv['status']}; {'stale after amendment' if inv['stale'] else 'current'}. "
                          "Hypothesis pending review, not a conclusion.",
                "created_at": inv["created_at"],
                "age_days": self._review_age_days(inv["created_at"]),
            })
        for src in self.db.execute(
                """SELECT id,document_id,version,kind,event_date,received_at FROM source_versions
                WHERE case_id=? AND supersedes_id IS NOT NULL ORDER BY id""", (case_id,)).fetchall():
            items.append({
                "queue_key": f"amendment:{src['id']}", "kind": "amendment",
                "target_id": src["id"], "fingerprint": f"v{src['version']}",
                "title": f"Fictional amended report {src['document_id']} version {src['version']}",
                "detail": f"{src['kind']} report for event {src['event_date']}; "
                          "a corrected version arrived and dependent work may need another look.",
                "created_at": src["received_at"],
                "age_days": self._review_age_days(src["received_at"]),
            })
        for opt in self.db.execute(
                "SELECT * FROM options WHERE case_id=? ORDER BY id", (case_id,)).fetchall():
            if opt["operational_status"] in ("rejected", "withdrawn", "expired"):
                continue
            contradicted = opt["epistemic_status"] == "contradicted" \
                or self._option_contradicted(opt["id"])
            held = contradicted and opt["operational_status"] in ("proposed", "reviewed")
            if not held and opt["review_state"] != "needs_review":
                continue
            snap = self.db.execute("SELECT state FROM snapshots WHERE id=?",
                                   (opt["snapshot_id"],)).fetchone()
            snap_state = snap["state"] if snap else "missing"
            items.append({
                "queue_key": f"option:{opt['id']}", "kind": "held-option",
                "target_id": opt["id"],
                "fingerprint": f"{opt['operational_status']}:{opt['review_state']}:"
                               f"{opt['snapshot_id']}:{snap_state}:{opt['epistemic_status']}",
                "title": f"Fictional held discussion item #{opt['id']}: {opt['label']}",
                "detail": ("Held: contradictory fictional notes are linked. " if held else "")
                          + (f"Awaiting re-review after a change. " if opt["review_state"] == "needs_review" else "")
                          + "For discussion only; not a recommendation.",
                "created_at": opt["created_at"],
                "age_days": self._review_age_days(opt["created_at"]),
            })
        for asm in self.db.execute(
                """SELECT a.id,a.question_id,a.relation,a.applicability,a.rationale,a.created_at,
                v.evidence_key,v.version,v.state AS evidence_state,v.title
                FROM evidence_assessments a JOIN evidence_versions v ON v.id=a.evidence_version_id
                WHERE a.case_id=? ORDER BY a.id""", (case_id,)).fetchall():
            items.append({
                "queue_key": f"evidence-assessment:{asm['id']}", "kind": "new-evidence",
                "target_id": asm["id"],
                "fingerprint": f"{asm['evidence_state']}:{asm['relation']}:{asm['applicability']}",
                "title": f"Fictional evidence note #{asm['id']}: {asm['evidence_key']}@{asm['version']}",
                "detail": f"{asm['title'][:120]} — {asm['relation']} / {asm['applicability']} "
                          f"(evidence {asm['evidence_state']}). Human-labelled demo data.",
                "created_at": asm["created_at"],
                "age_days": self._review_age_days(asm["created_at"]),
            })
        items.sort(key=lambda x: (x["created_at"], x["queue_key"]))
        return items

    def review_queue(self, case_id: str) -> dict:
        """Current review inbox with age, status, and full receipt history.

        An item is awaiting until a terminal receipt (reviewed or
        acknowledged) matches its current fingerprint. A returned item keeps
        its reason and stays awaiting. A resolved item whose ledger state
        later changes reopens with its prior receipts preserved. Nothing is
        removed by age or by any automatic step: only a recorded human
        decision resolves the current version of an item.
        """
        self._case(case_id)
        with self.db:
            self.db.execute("BEGIN")
            items = self._review_queue_items(case_id)
            receipts = self._dicts(self.db.execute(
                "SELECT * FROM review_receipts WHERE case_id=? ORDER BY id", (case_id,)).fetchall())
            by_key: dict[str, list[dict]] = {}
            for receipt in receipts:
                by_key.setdefault(receipt["queue_key"], []).append(receipt)
            awaiting: list[dict] = []
            resolved: list[dict] = []
            for item in items:
                history = by_key.get(item["queue_key"], [])
                matching = [r for r in history if r["fingerprint"] == item["fingerprint"]]
                prior = [r for r in history if r["fingerprint"] != item["fingerprint"]]
                terminal = [r for r in matching if r["action"] in ("reviewed", "acknowledged")]
                prior_terminal = [r for r in prior if r["action"] in ("reviewed", "acknowledged")]
                item["receipts"] = matching
                item["prior_receipts"] = prior
                item["reopened_after_change"] = bool(prior_terminal) and not terminal
                if terminal:
                    item["status"] = "resolved"
                    item["resolved_by"] = terminal[-1]
                    resolved.append(item)
                else:
                    if matching and matching[-1]["action"] == "returned":
                        item["status"] = "returned"
                        item["return_reason"] = matching[-1]["reason"]
                        item["returned_by"] = matching[-1]["reviewer_label"]
                    else:
                        item["status"] = "awaiting_review"
                    awaiting.append(item)
            return {
                "case_id": case_id, "synthetic": True,
                "disclaimer": self.REVIEW_QUEUE_DISCLAIMER,
                "awaiting": awaiting, "resolved": resolved, "receipts": receipts,
            }

    def add_review_receipt(self, case_id: str, queue_key: str, action: str,
                           reviewer_label: str, reason: str | None = None) -> dict:
        """Append one sign-off receipt. Reviewed and acknowledged resolve the
        current version of the item; returned keeps it visibly queued with
        its reason. Receipts are never updated or deleted."""
        self._case(case_id)
        if action not in self.REVIEW_RECEIPT_ACTIONS:
            raise InvalidInput("Receipt action must be reviewed, acknowledged, or returned")
        reviewer_label = self._check_no_clinical_language(reviewer_label, "Reviewer label")
        if not 2 <= len(reviewer_label) <= 80:
            raise InvalidInput("Reviewer label must have 2–80 characters")
        if action == "returned":
            if not isinstance(reason, str) or not 10 <= len(reason.strip()) <= 600:
                raise InvalidInput("A returned item requires a 10–600 character reason")
            reason_text = self._check_no_clinical_language(reason.strip(), "Return reason")
        elif reason is None or (isinstance(reason, str) and not reason.strip()):
            reason_text = None
        else:
            if not isinstance(reason, str) or not 10 <= len(reason.strip()) <= 600:
                raise InvalidInput("Receipt reason must have 10–600 characters")
            reason_text = self._check_no_clinical_language(reason.strip(), "Receipt reason")
        with self.db:
            self.db.execute("BEGIN IMMEDIATE")
            items = {x["queue_key"]: x for x in self._review_queue_items(case_id)}
            item = items.get(queue_key)
            if item is None:
                raise InvalidInput("Review queue item not found in this case")
            prior_terminal = self.db.execute(
                """SELECT 1 FROM review_receipts WHERE case_id=? AND queue_key=?
                AND fingerprint=? AND action IN ('reviewed','acknowledged') LIMIT 1""",
                (case_id, queue_key, item["fingerprint"])).fetchone()
            if prior_terminal:
                raise InvalidInput("This review item is already resolved for its current version")
            cur = self.db.execute("""INSERT INTO review_receipts
                (case_id,queue_key,kind,target_id,fingerprint,action,reviewer_label,reason,created_at)
                VALUES (?,?,?,?,?,?,?,?,?)""",
                (case_id, queue_key, item["kind"], item["target_id"], item["fingerprint"],
                 action, reviewer_label, reason_text, now_utc()))
            self._event(case_id, "review_receipt_recorded", queue_key=queue_key,
                        action=action, receipt_id=cur.lastrowid)
            return {"result": action, "receipt_id": int(cur.lastrowid),
                    "queue_key": queue_key, "fingerprint": item["fingerprint"]}
    # ---- B-04 scoped human review: sign-off, dissent, handoff ----
    # Record-state notes only (acknowledgment/scope recording): never a
    # credential check, a clinical sign-off, or a treatment decision.
    # Decisions are per-snapshot with independent extraction and
    # interpretation dimensions; dissent names one finding key inside the
    # snapshot basis; handoff carries the pinned basis to another fictional
    # reviewer. All writes are INSERT-only; nothing here updates or deletes
    # a prior row, and nothing copies rows across snapshots or cases.

    @staticmethod
    def _scoped_checked(func, *args):
        try:
            return func(*args)
        except ValueError as error:
            raise InvalidInput(str(error)) from None

    def _snapshot_in_case(self, case_id: str, snapshot_id: int) -> None:
        if type(snapshot_id) is not int or snapshot_id < 1:
            raise InvalidInput("Invalid investigation snapshot")
        if not self.db.execute("SELECT 1 FROM snapshots WHERE id=? AND case_id=?",
                               (snapshot_id, case_id)).fetchone():
            raise InvalidInput("Investigation snapshot not in this case")

    def _snapshot_basis(self, snapshot_id: int) -> tuple[list[int], list[int], list[int]]:
        sources = [r[0] for r in self.db.execute(
            "SELECT source_version_id FROM snapshot_sources WHERE snapshot_id=? ORDER BY source_version_id",
            (snapshot_id,)).fetchall()]
        assessments = [r[0] for r in self.db.execute(
            "SELECT assessment_id FROM snapshot_evidence WHERE snapshot_id=? ORDER BY assessment_id",
            (snapshot_id,)).fetchall()]
        brokers = [r[0] for r in self.db.execute(
            "SELECT broker_link_id FROM snapshot_broker_links WHERE snapshot_id=? ORDER BY broker_link_id",
            (snapshot_id,)).fetchall()]
        return [int(x) for x in sources], [int(x) for x in assessments], [int(x) for x in brokers]

    def scoped_review_for_snapshot(self, case_id: str, snapshot_id: int) -> dict:
        """Read-only projection of one snapshot's scoped review state."""
        self._case(case_id)
        self._snapshot_in_case(case_id, snapshot_id)
        decisions = self._dicts(self.db.execute(
            "SELECT * FROM scoped_review_decisions WHERE snapshot_id=? AND case_id=? ORDER BY id",
            (snapshot_id, case_id)).fetchall())
        for row in decisions:
            row["source_version_ids"] = json.loads(row["source_version_ids"])
            row["evidence_assessment_ids"] = json.loads(row["evidence_assessment_ids"])
            row["broker_link_ids"] = json.loads(row["broker_link_ids"])
        dissents = self._dicts(self.db.execute(
            "SELECT * FROM scoped_review_dissents WHERE snapshot_id=? AND case_id=? ORDER BY id",
            (snapshot_id, case_id)).fetchall())
        for row in dissents:
            row["source_version_ids"] = json.loads(row["source_version_ids"])
        handoffs = self._dicts(self.db.execute(
            "SELECT * FROM scoped_review_handoffs WHERE snapshot_id=? AND case_id=? ORDER BY id",
            (snapshot_id, case_id)).fetchall())
        for row in handoffs:
            row["source_version_ids"] = json.loads(row["source_version_ids"])
            row["prior_decision_ids"] = json.loads(row["prior_decision_ids"])
        status = derive_status(decisions)
        return {
            **status,
            "decisions": decisions,
            "dissents": dissents,
            "handoffs": handoffs,
            "assignee": handoffs[-1]["to_reviewer"] if handoffs else None,
        }

    def record_scoped_decision(self, case_id: str, snapshot_id: int, reviewer_label: str,
                               scope: str, note: str) -> dict:
        """Record one reviewer's scope note on a snapshot, pinning its basis.

        The snapshot's current source/evidence/broker ids are copied into the
        row, so the pins stay readable as history after an amendment. Any
        snapshot state is accepted: a note recorded against a superseded
        basis is history, not a current endorsement, and replacement drafts
        always start unreviewed.
        """
        self._case(case_id)
        reviewer = self._scoped_checked(check_reviewer_label, reviewer_label)
        scope_value = self._scoped_checked(check_scope, scope)
        note_text = self._scoped_checked(check_note, note, "Decision note")
        with self.db:
            self.db.execute("BEGIN IMMEDIATE")
            self._snapshot_in_case(case_id, snapshot_id)
            sources, assessments, brokers = self._snapshot_basis(snapshot_id)
            stamped = now_utc()
            cur = self.db.execute("""INSERT INTO scoped_review_decisions
                (case_id,snapshot_id,reviewer_label,scope,source_version_ids,
                 evidence_assessment_ids,broker_link_ids,note,decided_at)
                VALUES (?,?,?,?,?,?,?,?,?)""",
                (case_id, snapshot_id, reviewer, scope_value, json.dumps(sources),
                 json.dumps(assessments), json.dumps(brokers), note_text, stamped))
            self._event(case_id, "scoped_review_decided", snapshot_id=snapshot_id,
                        decision_id=cur.lastrowid, scope=scope_value)
            return {"decision_id": int(cur.lastrowid), "scope": scope_value,
                    "pinned_source_ids": sources,
                    "pinned_evidence_assessment_ids": assessments,
                    "pinned_broker_link_ids": brokers, "decided_at": stamped}

    def record_scoped_dissent(self, case_id: str, snapshot_id: int, reviewer_label: str,
                              claim_ref: str, rationale: str) -> dict:
        """Record disagreement on one finding key without touching prior rows.

        The claim reference must be a finding key present in the snapshot's
        pinned basis. The dissent row lives in its own table: no write here
        updates or deletes a decision, so both views stay visible.
        """
        self._case(case_id)
        reviewer = self._scoped_checked(check_reviewer_label, reviewer_label)
        claim = self._scoped_checked(check_claim_ref, claim_ref)
        rationale_text = self._scoped_checked(check_note, rationale, "Dissent rationale")
        with self.db:
            self.db.execute("BEGIN IMMEDIATE")
            self._snapshot_in_case(case_id, snapshot_id)
            sources, _, _ = self._snapshot_basis(snapshot_id)
            marks = ",".join("?" for _ in sources)
            found = self.db.execute(
                f"SELECT 1 FROM assertions WHERE finding_key=? AND source_version_id IN ({marks}) LIMIT 1",
                [claim, *sources]).fetchone() if sources else None
            if not found:
                raise InvalidInput("Claim reference is not a finding in this snapshot's basis")
            stamped = now_utc()
            cur = self.db.execute("""INSERT INTO scoped_review_dissents
                (case_id,snapshot_id,reviewer_label,claim_ref,source_version_ids,rationale,dissented_at)
                VALUES (?,?,?,?,?,?,?)""",
                (case_id, snapshot_id, reviewer, claim, json.dumps(sources), rationale_text, stamped))
            self._event(case_id, "scoped_review_dissent", snapshot_id=snapshot_id,
                        dissent_id=cur.lastrowid, claim_ref=claim)
            return {"dissent_id": int(cur.lastrowid), "claim_ref": claim,
                    "pinned_source_ids": sources, "dissented_at": stamped}

    def record_scoped_handoff(self, case_id: str, snapshot_id: int,
                              from_reviewer: str, to_reviewer: str) -> dict:
        """Hand open review items to another fictional reviewer, losslessly.

        The handoff row pins the snapshot id, its current source versions,
        and every prior decision id, and the full history stays in place:
        nothing is rewritten. Handoff requires at least one open dimension.
        """
        self._case(case_id)
        sender = self._scoped_checked(check_reviewer_label, from_reviewer)
        recipient = self._scoped_checked(check_reviewer_label, to_reviewer)
        if sender == recipient:
            raise InvalidInput("Handoff requires a different receiving reviewer")
        with self.db:
            self.db.execute("BEGIN IMMEDIATE")
            self._snapshot_in_case(case_id, snapshot_id)
            sources, _, _ = self._snapshot_basis(snapshot_id)
            prior = [int(r[0]) for r in self.db.execute(
                "SELECT id FROM scoped_review_decisions WHERE snapshot_id=? AND case_id=? ORDER BY id",
                (snapshot_id, case_id)).fetchall()]
            existing = self._dicts(self.db.execute(
                "SELECT scope FROM scoped_review_decisions WHERE snapshot_id=? AND case_id=?",
                (snapshot_id, case_id)).fetchall())
            if not derive_status(existing)["open_items"]:
                raise InvalidInput("No open review items to hand off; both dimensions already have a settled note")
            stamped = now_utc()
            cur = self.db.execute("""INSERT INTO scoped_review_handoffs
                (case_id,snapshot_id,from_reviewer,to_reviewer,source_version_ids,prior_decision_ids,handed_at)
                VALUES (?,?,?,?,?,?,?)""",
                (case_id, snapshot_id, sender, recipient, json.dumps(sources), json.dumps(prior), stamped))
            self._event(case_id, "scoped_review_handoff", snapshot_id=snapshot_id,
                        handoff_id=cur.lastrowid, to_reviewer=recipient)
            return {"handoff_id": int(cur.lastrowid), "snapshot_id": snapshot_id,
                    "pinned_source_ids": sources, "prior_decision_ids": prior,
                    "handed_at": stamped}
    # ---- B-02: owned re-review tasks on every invalidation ----
    RE_REVIEW_CAUSES = frozenset({"source_amendment", "evidence_change", "revocation", "correction", "review"})

    @staticmethod
    def _valid_task_assignee(value: object) -> str:
        if value is None:
            return DEFAULT_RE_REVIEW_ASSIGNEE
        if not isinstance(value, str) or not 2 <= len(value.strip()) <= 80:
            raise InvalidInput("Re-review task assignee must be a 2–80 character fictional label")
        return value.strip()

    @staticmethod
    def _valid_task_due_date(value: object) -> str | None:
        if value is None:
            return None
        if not isinstance(value, str):
            raise InvalidInput("Dates must use YYYY-MM-DD")
        return valid_date(value)

    def _source_finding_diff(self, old_source_id: int, new_source_id: int) -> dict:
        """Mechanical finding-key diff between two source versions.

        Reuses the exact changes._finding_diff shape pinned on re-review
        tasks. The import is function-local because changes.py imports this
        module; importing it here (at call time) avoids a module cycle.
        """
        from .changes import _finding_diff
        old_rows = [dict(row) for row in self.db.execute(
            "SELECT finding_key,certainty FROM assertions WHERE source_version_id=?",
            (old_source_id,)).fetchall()]
        new_rows = [dict(row) for row in self.db.execute(
            "SELECT finding_key,certainty FROM assertions WHERE source_version_id=?",
            (new_source_id,)).fetchall()]
        return _finding_diff(old_rows, new_rows)

    def _create_re_review_tasks(self, *, case_id: str, snapshot_ids: list[int], cause: str,
                                invalidating_event_id: int,
                                assignee_label: str | None = None,
                                due_date: str | None = None,
                                superseding_source_version_id: int | None = None,
                                superseded_source_version_id: int | None = None,
                                finding_diff: dict | None = None,
                                evidence_version_id: int | None = None,
                                rights_source_id: int | None = None,
                                superseding_rights_source_id: int | None = None,
                                broker_link_id: int | None = None) -> list[int]:
        """Open one task per newly stale snapshot. Caller owns the write transaction.

        Non-amendment causes carry the empty finding-key diff shape (no source
        versions were compared). Snapshots that already have a task row are
        skipped, so an overlapping invalidation can never duplicate ownership.
        """
        if cause not in self.RE_REVIEW_CAUSES:
            raise InvalidInput("Unknown re-review cause")
        if type(invalidating_event_id) is not int or invalidating_event_id < 1:
            raise InvalidInput("Invalid invalidating event ID")
        owner = self._valid_task_assignee(assignee_label)
        due = self._valid_task_due_date(due_date)
        diff = {"added_finding_keys": [], "removed_finding_keys": [],
                "reported_state_changes": []} if finding_diff is None else finding_diff
        created: list[int] = []
        for snapshot_id in sorted(set(snapshot_ids)):
            question = self.db.execute(
                "SELECT question_id FROM snapshots WHERE id=? AND case_id=?",
                (snapshot_id, case_id)).fetchone()
            if not question:
                continue
            already = self.db.execute(
                "SELECT 1 FROM re_review_tasks WHERE snapshot_id=?", (snapshot_id,)).fetchone()
            if already:
                continue
            cur = self.db.execute("""INSERT INTO re_review_tasks
                (case_id,snapshot_id,question_id,cause,
                 superseding_source_version_id,superseded_source_version_id,finding_diff_json,
                 evidence_version_id,rights_source_id,superseding_rights_source_id,broker_link_id,
                 invalidating_event_id,assignee_label,due_date,status,created_at)
                VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,'open',?)""",
                (case_id, snapshot_id, question["question_id"], cause,
                 superseding_source_version_id, superseded_source_version_id,
                 json.dumps(diff, sort_keys=True),
                 evidence_version_id, rights_source_id, superseding_rights_source_id,
                 broker_link_id, invalidating_event_id, owner, due, now_utc()))
            created.append(int(cur.lastrowid))
        return created

    def list_re_review_tasks(self, case_id: str) -> list[dict]:
        """Per-case re-review task list. Read-only; writes nothing.

        Overdue rule: status is open AND a due date is set AND the due date is
        before today's UTC date. No priority is inferred; rows are ordered by
        creation (id), open and done alike, so the full lifecycle stays
        visible after completion.
        """
        self._case(case_id)
        today = datetime.now(timezone.utc).date().isoformat()
        rows = self._dicts(self.db.execute(
            "SELECT * FROM re_review_tasks WHERE case_id=? ORDER BY id", (case_id,)).fetchall())
        for row in rows:
            row["finding_key_diff"] = json.loads(row.pop("finding_diff_json"))
            row["overdue"] = bool(row["status"] == "open" and row["due_date"] is not None
                                  and row["due_date"] < today)
        return rows

    def close_re_review_task(self, case_id: str, task_id: int,
                             closing_snapshot_id: int | None = None,
                             no_change_note: str | None = None) -> dict:
        """Close one open task by replacement draft or explicit no-change note.

        Exactly one of closing_snapshot_id / no_change_note is required. A
        closing draft must be in this case, address the task's question, not
        be stale, and bind only current source versions. Closing never
        changes any snapshot's state: the prior snapshot stays stale as
        history and the new draft stays a draft until the human review
        action. Completion appends a re_review_task_closed event row.
        """
        self._case(case_id)
        if type(task_id) is not int or task_id < 1:
            raise InvalidInput("Invalid re-review task ID")
        has_draft = closing_snapshot_id is not None
        has_note = no_change_note is not None
        if has_draft == has_note:
            raise InvalidInput("Close a re-review task with either a replacement draft or a no-change note, not both or neither")
        note_text = ""
        if has_note:
            if not isinstance(no_change_note, str) or not 10 <= len(no_change_note.strip()) <= 600:
                raise InvalidInput("A no-change note must have 10–600 characters")
            note_text = no_change_note.strip()
        if has_draft and (type(closing_snapshot_id) is not int or closing_snapshot_id < 1):
            raise InvalidInput("Invalid closing snapshot ID")
        with self.db:
            self.db.execute("BEGIN IMMEDIATE")
            task = self.db.execute(
                "SELECT * FROM re_review_tasks WHERE id=? AND case_id=?",
                (task_id, case_id)).fetchone()
            if not task:
                raise InvalidInput("Re-review task not in this case")
            if task["status"] != "open":
                raise InvalidInput("Re-review task is already closed")
            if has_draft:
                draft = self.db.execute(
                    "SELECT id,question_id,state FROM snapshots WHERE id=? AND case_id=?",
                    (closing_snapshot_id, case_id)).fetchone()
                if not draft:
                    raise InvalidInput("Closing draft is missing or belongs to another case")
                if draft["question_id"] != task["question_id"]:
                    raise InvalidInput("Closing draft must address the task's question")
                if draft["state"] == "stale":
                    raise InvalidInput("Closing draft is stale; prepare a draft on current sources")
                stale_basis = self.db.execute(
                    """SELECT 1 FROM snapshot_sources ss
                    JOIN source_versions v ON v.id=ss.source_version_id
                    WHERE ss.snapshot_id=? AND v.state!='current' LIMIT 1""",
                    (closing_snapshot_id,)).fetchone()
                if stale_basis:
                    raise InvalidInput("Closing draft is bound to a superseded source version")
                self.db.execute(
                    "UPDATE re_review_tasks SET status='done',closing_snapshot_id=?,closed_at=? WHERE id=?",
                    (closing_snapshot_id, now_utc(), task_id))
                self._event(case_id, "re_review_task_closed", task_id=task_id,
                            snapshot_id=task["snapshot_id"], mode="draft",
                            closing_snapshot_id=closing_snapshot_id)
            else:
                self.db.execute(
                    "UPDATE re_review_tasks SET status='done',close_note=?,closed_at=? WHERE id=?",
                    (note_text, now_utc(), task_id))
                self._event(case_id, "re_review_task_closed", task_id=task_id,
                            snapshot_id=task["snapshot_id"], mode="note")
            return {"result": "task_closed", "task_id": task_id, "status": "done"}

    def source_version_facts(self, case_id: str) -> list[dict]:
        """All source versions of a case, current and superseded, with
        the dates, specimen, state, and supersession link the K-checks
        need. Read-only; used to build the K-check context for an
        investigation run."""
        self._case(case_id)
        return self._dicts(self.db.execute(
            """SELECT id,document_id,version,sha256,kind,event_date,issued_at,received_at,
            specimen_id,state,supersedes_id FROM source_versions
            WHERE case_id=? ORDER BY id""", (case_id,)).fetchall())

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
        from .document_intake import classification_provenance
        intake_by_source = self._document_intake_receipts(case_id)
        for assertion in assertions:
            if assertion["source_version_id"] in intake_by_source:
                assertion.update(classification_provenance(intake_by_source[assertion["source_version_id"]]))
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
                           validated, mode: str, write_contract: dict | None = None) -> int:
        from .agent_writes import (
            WriteContractRejected,
            parse_route_id,
            validate_write_contract,
        )
        from .investigation import TEMPLATES
        self._case(case_id)
        if mode not in ("live", "replay"):
            raise InvalidInput("Mode must be live or replay")
        if template not in TEMPLATES:
            raise InvalidInput("Unknown investigation template")
        # Slice 1 write contract (program plan section 5.4): no write is
        # stored without a complete, validated contract bound to this run.
        if write_contract is None:
            raise WriteContractRejected("missing_write_contract")
        contract = validate_write_contract(write_contract)
        route_case, route_template, route_question = parse_route_id(contract["routeId"])
        if (route_case, route_template, route_question) != (case_id, template, question_id):
            raise WriteContractRejected(
                "route_mismatch", "routeId",
                "contract route does not match this investigation",
            )
        if contract["modelId"] != validated.model:
            raise WriteContractRejected(
                "contract_mismatch", "modelId",
                "contract model does not match the validated output model",
            )
        # Slice 3 assignment (program plan C3): when a route.decided
        # record exists for this route, the writing role must be among
        # the route's assigned agents and the assignment's lease must
        # still hold. A write whose route was never decided is not
        # rejected here (pre-C3 rows): the replay is the check that
        # catches a missing route.
        from .orchestrator import check_assignment
        check_assignment(
            self, case_id, contract["routeId"], contract["agentRole"],
            require_route=False,
        )
        with self.db:
            self.db.execute("BEGIN IMMEDIATE")
            if not self.db.execute("SELECT 1 FROM questions WHERE id=? AND case_id=?",
                                   (question_id, case_id)).fetchone():
                raise InvalidInput("Question not in this case")
            cur = self.db.execute(
                """INSERT INTO investigations
                (case_id,question_id,template,status,mode,model,claims_json,abstentions_json,dropped_json,created_at)
                VALUES (?,?,?,?,?,?,?,?,?,?)""",
                (case_id, question_id, template, validated.status, mode, validated.model,
                 json.dumps(validated.claims), json.dumps(validated.abstentions),
                 json.dumps(validated.dropped), now_utc()))
            investigation_id = int(cur.lastrowid)
            self.db.execute(
                """INSERT INTO agent_writes
                (write_id,investigation_id,case_id,contract_json,created_at)
                VALUES (?,?,?,?,?)""",
                (contract["writeId"], investigation_id, case_id,
                 json.dumps(contract, sort_keys=True), now_utc()))
            # An abstention states there is no answer: it must not hide the
            # question as addressed. Only a non-abstained result addresses
            # it here; human drafts address on acknowledgment instead.
            if validated.status != "abstained":
                self.db.execute("UPDATE questions SET state='addressed' WHERE id=? AND case_id=?",
                                (question_id, case_id))
            self._event(case_id, "investigation_created", investigation_id=investigation_id,
                        template=template, status=validated.status, mode=mode,
                        write_id=contract["writeId"])
            return investigation_id

    def get_write_contract(self, case_id: str, investigation_id: int) -> dict | None:
        """Return the stored write contract for an investigation, or None.

        None means the investigation was stored before the write contract
        existed (pre-slice rows); such rows keep reading, and replay
        reports them as missing_write_contract rather than failing.
        """
        self._case(case_id)
        if type(investigation_id) is not int:
            raise InvalidInput("Investigation id must be an integer")
        row = self.db.execute(
            """SELECT contract_json FROM agent_writes
            WHERE investigation_id=? AND case_id=?""",
            (investigation_id, case_id)).fetchone()
        if not row:
            return None
        try:
            value = json.loads(row[0])
        except (json.JSONDecodeError, TypeError):
            return None
        return value if isinstance(value, dict) else None

    def get_investigation(self, case_id: str, investigation_id: int) -> dict:
        self._case(case_id)
        if type(investigation_id) is not int:
            raise InvalidInput("Investigation id must be an integer")
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
        data["write_contract"] = self.get_write_contract(case_id, investigation_id)
        data["disclaimer"] = ("Research demonstration only. Hypotheses are unreviewed, "
                              "fictional-data based, and not medical advice.")
        return data

    def list_investigations(self, case_id: str) -> list[dict]:
        self._case(case_id)
        rows = self._dicts(self.db.execute(
            """SELECT i.id,i.question_id,i.template,i.status,i.mode,i.model,i.stale,i.created_at,
            w.write_id,w.contract_json
            FROM investigations i LEFT JOIN agent_writes w ON w.investigation_id=i.id
            WHERE i.case_id=? ORDER BY i.id DESC""", (case_id,)).fetchall())
        for row in rows:
            row["kind"] = "hypothesis"
            row["review_state"] = "pending"
            contract_json = row.pop("contract_json")
            try:
                contract = json.loads(contract_json) if contract_json else None
            except (json.JSONDecodeError, TypeError):
                contract = None
            row["agent_role"] = contract.get("agentRole") if isinstance(contract, dict) else None
            row["route_id"] = contract.get("routeId") if isinstance(contract, dict) else None
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
            from .document_intake import classification_provenance
            intake_by_source = self._document_intake_receipts(case_id)
            for source in source_rows:
                if source["id"] in intake_by_source:
                    receipt = intake_by_source[source["id"]]
                    source["document_intake"] = receipt
                    source.update(classification_provenance(receipt))
            assert_rows = self._dicts(self.db.execute(
                """SELECT assertions.id,source_version_id,finding_key,certainty,quote,source_line
                FROM assertions JOIN source_versions ON source_versions.id=assertions.source_version_id
                WHERE assertions.case_id=? AND source_versions.state='current' ORDER BY assertions.id""",
                (case_id,)).fetchall())
            for assertion in assert_rows:
                if assertion["source_version_id"] in intake_by_source:
                    assertion.update(classification_provenance(intake_by_source[assertion["source_version_id"]]))
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
            for snapshot in snapshot_rows:
                # B-04 read-only projection; adds no rows and changes no state.
                snapshot["scoped_review"] = self.scoped_review_for_snapshot(case_id, snapshot["id"])
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
            option_projection = self.option_view(case_id)
            consent_rows = self.list_consents(case_id)
            qualifier_rows = self.list_identity_qualifiers(case_id)
            from .followthrough import followthrough_view_in_transaction
            followthrough_projection = followthrough_view_in_transaction(self, case_id)
            return {
                "followthrough": followthrough_projection,
                "broker_links": broker_rows,
                "rights_sources": rights_rows,
                "consents": consent_rows,
                "identity_qualifiers": qualifier_rows,
                "biological_assets": self._dicts(self.db.execute(
                    "SELECT * FROM biological_assets WHERE case_id=? ORDER BY id", (case_id,)).fetchall()),
                "biological_inventory_assertions": self._dicts(self.db.execute(
                    "SELECT * FROM biological_inventory_assertions WHERE case_id=? ORDER BY id",
                    (case_id,)).fetchall()),
                "bio_explanations": self._dicts(self.db.execute(
                    "SELECT * FROM bio_explanations WHERE case_id=? ORDER BY id",
                    (case_id,)).fetchall()),
                "bio_assay_observations": self._dicts(self.db.execute(
                    "SELECT * FROM bio_assay_observations WHERE case_id=? ORDER BY id",
                    (case_id,)).fetchall()),
                "evidence": evidence_rows,
                "evidence_changes": self._dicts(self.db.execute(
                    "SELECT id,evidence_version_id,kind,reason,recorded_at FROM evidence_changes ORDER BY id DESC").fetchall()),
                "evidence_assessments": assessments,
                "case": dict(self.db.execute("SELECT * FROM cases WHERE case_id=?", (case_id,)).fetchone()),
                "sources": source_rows,
                "assertions": assert_rows,
                "questions": self._dicts(self.db.execute("SELECT * FROM questions WHERE case_id=? ORDER BY id DESC", (case_id,)).fetchall()),
                "question_owner_history": self._dicts(self.db.execute(
                    """SELECT id,question_id,owner_label,assigned_at FROM question_owner_history
                    WHERE case_id=? ORDER BY id""", (case_id,)).fetchall()),
                "question_evidence_notes": self._dicts(self.db.execute(
                    """SELECT id,question_id,version,note,created_at FROM question_evidence_notes
                    WHERE case_id=? ORDER BY question_id,version""", (case_id,)).fetchall()),
                "snapshots": snapshot_rows,
                # OI-021 derived projection: same ledger, no second state.
                "options": option_projection["options"],
                "option_disclaimer": option_projection["disclaimer"],
                # Second-opinion and survivorship records: separate descriptive
                # records over the same ledger, never overwrites of originals.
                "second_opinions": self.second_opinion_view(case_id)["requests"],
                "second_opinion_disclaimer": SECOND_OPINION_DISCLAIMER,
                "survivorship_plans": self.survivorship_view(case_id)["plans"],
                "survivorship_disclaimer": SURVIVORSHIP_DISCLAIMER,
                "patient_goals": self.patient_goals(case_id),
                "patient_notes": self.patient_notes(case_id),
                "patient_words_disclaimer": self.PATIENT_DISCLAIMER,
                # Portfolio slice: same ledger plus portfolio records, read-only.
                "portfolio": self.option_portfolio(case_id),
                "subject_links": self._dicts(self.db.execute(
                    """SELECT l.id,l.case_id,l.source_version_id,v.document_id,v.version,
                    l.declared_subject_id,l.decision,l.decided_at,l.actor_label
                    FROM subject_links l JOIN source_versions v ON v.id=l.source_version_id
                    WHERE l.case_id=? ORDER BY l.id""", (case_id,)).fetchall()),
                "option_receipt_disclaimer": option_projection["receipt_disclaimer"],
                "quarantines": self._dicts(self.db.execute(
                    """SELECT q.id,q.declared_patient_id,q.sha256,q.reason,q.received_at,
                    qc.destination_case_id AS resolved_destination_case_id,
                    qc.destination_source_id AS resolved_destination_source_id,
                    qc.corrected_at AS resolved_at,
                    qc.actor_label AS correction_actor_label
                    FROM quarantine q LEFT JOIN quarantine_corrections qc
                    ON qc.quarantine_id=q.id WHERE q.target_case_id=? ORDER BY q.id DESC""",
                    (case_id,)).fetchall()),
                "events": self._dicts(self.db.execute(
                    "SELECT id,kind,details,occurred_at FROM events WHERE case_id=? ORDER BY id DESC LIMIT 40",
                    (case_id,)).fetchall()),
            }

    def source_text(self, case_id: str, source_id: int) -> str:
        self._case(case_id)
        if type(source_id) is not int:
            raise InvalidInput("Source id must be an integer")
        row = self.db.execute("SELECT raw FROM source_versions WHERE case_id=? AND id=?",
                              (case_id, source_id)).fetchone()
        if not row:
            raise InvalidInput("Source not in this case")
        return bytes(row["raw"]).decode("utf-8")

    def source_document(self, case_id: str, source_id: int) -> dict:
        """Retrieve exact original bytes and safe download metadata for one case."""
        self._case(case_id)
        if type(source_id) is not int or not 1 <= source_id <= 9223372036854775807:
            raise InvalidInput("Source ID must be a bounded positive integer")
        row = self.db.execute(
            """SELECT s.id,s.document_id,s.version,s.raw,s.sha256,d.filename,d.media_type,
            d.extraction_method,d.annotation_method,d.manual_transcription_confirmed
            FROM source_versions s LEFT JOIN document_intake_metadata d ON d.source_version_id=s.id
            WHERE s.case_id=? AND s.id=?""", (case_id, source_id)).fetchone()
        if row is None:
            raise InvalidInput("Source not in this case")
        raw = bytes(row["raw"])
        return {
            "source_id": row["id"], "document_id": row["document_id"], "version": row["version"],
            "raw": raw, "sha256": row["sha256"], "byte_count": len(raw),
            "filename": row["filename"] or f"{row['document_id']}-v{row['version']}.txt",
            "media_type": row["media_type"] or "text/plain; charset=utf-8",
            "extraction_method": row["extraction_method"] or "synthetic-authored-format-v1",
            "annotation_method": row["annotation_method"] or "source-authored-finding-lines",
            "manual_transcription_confirmed": bool(row["manual_transcription_confirmed"]),
            "clinical_review": "not_performed",
        }

    def export_markdown(self, case_id: str, snapshot_id: int) -> str:
        self._case(case_id)
        if type(snapshot_id) is not int or snapshot_id < 1:
            raise InvalidInput("Invalid investigation ID")
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
            intake_by_source = self._document_intake_receipts(case_id)
            lines = ["# Open Intelligence — synthetic investigation", "",
                     "> Research demonstration only. No clinical review or patient-specific treatment recommendation.", "",
                     f"Case: `{case_id}` | Investigation: {snapshot_id} | State: **{snapshot['state']}**",
                     f"Created: {snapshot['created_at']} | Demo acknowledgment: {snapshot['reviewed_at'] or 'None'}", "",
                     "## Question", "", snapshot["question"], "", "## Draft (human-authored)", "",
                     snapshot["summary"], ""]
            # B-04: per-dimension scope status beside the existing state label
            # above (kept verbatim, including State: **stale** after amendment).
            lines.extend(render_scoped_review_lines(
                self.scoped_review_for_snapshot(case_id, snapshot_id)))
            lines.extend(["## Source versions and original text", ""])
            for source in sources:
                raw_text = bytes(source["raw"]).decode("utf-8")
                # Prevent raw input from escaping Markdown source fences.
                longest = max((len(run) for run in re.findall(r"`+", raw_text)), default=0)
                fence = "`" * max(3, longest + 1)
                lines.extend([f"### {source['document_id']}@{source['version']} — {source['state']}", "",
                              f"SHA-256: `{source['sha256']}` | Event: {source['event_date']} | Issued: {source['issued_at']}", ""])
                if source["id"] in intake_by_source:
                    receipt = intake_by_source[source["id"]]
                    lines.extend([
                        "Manual transcription provenance: `classification_origin=user_selected` | "
                        f"`annotation_method={receipt['annotation_method']}` | `clinical_review=not_performed`",
                        f"Transcription review SHA-256: `{receipt['review_sha256']}`",
                        "The literal quote is primary; user-selected classifications are not source-authored "
                        "or clinically verified. Transcription confirmation is not clinical approval.", "",
                    ])
                lines.extend([fence + "text", raw_text, fence, ""])
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

    # ---- Visit records: plain recorded history, never directives ----
    VISIT_RECORDED_DATE_LABEL = "recorded date — not a clinical due date"
    VISIT_MISSING_SOURCE_LABEL = "no source recorded"
    VISIT_DISCLAIMER = ("Fictional visit history only. Visits record what happened, "
                        "never what should happen next. Dates are recorded dates, "
                        "not clinical due dates. No directive, recommendation, "
                        "or treatment guidance is stored here.")
    # Descriptive-only guard, same class as the existing option/discovery
    # clinical-language guards: directive and prescriptive wording is rejected
    # at write time in every author-controlled text field. Base verb forms
    # (order, start treatment) are rejected while past-tense history
    # (ordered, started) stays writable, so a recorded event can still be
    # described. This is a narrow guard, not a language classifier: human
    # review remains the gate, and the disclaimer states what visits are not.
    _VISIT_DIRECTIVE_LANGUAGE = re.compile(
        r"\bshould\b"
        r"|\bmust\b"
        r"|\bneed\s+to\b|\bneeds?\b"
        r"|\border\b"
        r"|\bstart\s+(treatment|therapy|medication|drug|infusion)\b"
        r"|\bstop\s+(treatment|therapy|medication|drug|infusion)\b"
        r"|\bseek\b"
        r"|\bwatch\s+for\b"
        r"|\beffectiv\w*\b|\befficac\w*\b"
        r"|\bproven\b|\bbenefit\w*\b"
        r"|\brecommend\w*\b|\bprescri\w*\b|\beligib\w*\b"
        r"|\bdos(e|age)\b"
        r"|\bbest\s+(treatment|therapy|option|drug)\b", re.IGNORECASE)

    @staticmethod
    def _check_visit_text(text: object, field: str, low: int, high: int) -> str:
        if not isinstance(text, str) or not low <= len(text.strip()) <= high:
            raise InvalidInput(f"Visit {field} must have {low}–{high} characters")
        if CaseStore._VISIT_DIRECTIVE_LANGUAGE.search(text):
            raise InvalidInput(f"Visit {field} must be descriptive history only; "
                               "directive or prescriptive wording is not accepted")
        return text.strip()

    @staticmethod
    def _check_visit_anchor(anchor: object) -> str | None:
        if anchor is None:
            return None
        if not isinstance(anchor, str):
            raise InvalidInput("Visit source anchor must be text or absent")
        if not anchor.strip():
            return None
        return CaseStore._check_visit_text(anchor, "source anchor", 1, 300)

    @staticmethod
    def _project_visit_version(row: dict) -> dict:
        anchor = row["source_anchor"]
        return {
            "id": row["id"],
            "visit_id": row["visit_id"],
            "version": row["version"],
            "recorded_date": row["recorded_date"],
            "recorded_date_label": CaseStore.VISIT_RECORDED_DATE_LABEL,
            "visit_type": row["visit_type"],
            "notes": row["notes"],
            "source_anchor": anchor,
            "source_display": anchor if anchor else CaseStore.VISIT_MISSING_SOURCE_LABEL,
            "review_state": row["review_state"],
            "state": row["state"],
            "previous_id": row["previous_id"],
            "created_at": row["created_at"],
        }

    def record_visit(self, case_id: str, recorded_date: str, visit_type: str,
                     notes: str, source_anchor: str | None = None) -> dict:
        """Record one fictional visit as plain history (version 1, current).

        A missing source anchor is allowed and stays NULL; readers render it
        as 'no source recorded'. The recorded date is history only, never a
        due date. Emits only a visit_recorded event; no other record changes.
        """
        case_id = self._case(case_id)
        recorded_date = valid_date(recorded_date)
        visit_type = self._check_visit_text(visit_type, "visit type", 1, 120)
        notes = self._check_visit_text(notes, "notes", 1, 2000)
        source_anchor = self._check_visit_anchor(source_anchor)
        with self.db:
            self.db.execute("BEGIN IMMEDIATE")
            cur = self.db.execute("INSERT INTO visits (case_id,created_at) VALUES (?,?)",
                                  (case_id, now_utc()))
            visit_id = int(cur.lastrowid)
            vcur = self.db.execute("""INSERT INTO visit_versions
                (visit_id,case_id,version,recorded_date,visit_type,notes,source_anchor,
                 review_state,state,previous_id,created_at)
                VALUES (?,?,1,?,?,?,?,'recorded','current',NULL,?)""",
                (visit_id, case_id, recorded_date, visit_type, notes,
                 source_anchor, now_utc()))
            version_id = int(vcur.lastrowid)
            self._event(case_id, "visit_recorded", visit_id=visit_id,
                        version_id=version_id, version=1)
            return {"visit_id": visit_id, "version_id": version_id, "version": 1}

    def amend_visit(self, case_id: str, visit_id: int, recorded_date: str,
                    visit_type: str, notes: str,
                    source_anchor: str | None = None) -> dict:
        """Append a new current version; the old version is superseded.

        History rows are never updated or deleted: only the single previous
        current row flips to superseded, and only within this visit. No other
        visit, source, question, or investigation is touched.
        """
        case_id = self._case(case_id)
        if type(visit_id) is not int or visit_id < 1:
            raise InvalidInput("Invalid visit ID")
        recorded_date = valid_date(recorded_date)
        visit_type = self._check_visit_text(visit_type, "visit type", 1, 120)
        notes = self._check_visit_text(notes, "notes", 1, 2000)
        source_anchor = self._check_visit_anchor(source_anchor)
        with self.db:
            self.db.execute("BEGIN IMMEDIATE")
            if not self.db.execute("SELECT 1 FROM visits WHERE id=? AND case_id=?",
                                   (visit_id, case_id)).fetchone():
                raise InvalidInput("Visit not in this case")
            current = self.db.execute("""SELECT * FROM visit_versions
                WHERE visit_id=? AND case_id=? AND state='current'
                ORDER BY version DESC LIMIT 1""", (visit_id, case_id)).fetchone()
            if not current:
                raise InvalidInput("Visit has no current version to amend")
            new_version = int(current["version"]) + 1
            vcur = self.db.execute("""INSERT INTO visit_versions
                (visit_id,case_id,version,recorded_date,visit_type,notes,source_anchor,
                 review_state,state,previous_id,created_at)
                VALUES (?,?,?,?,?,?,?,'recorded','current',?,?)""",
                (visit_id, case_id, new_version, recorded_date, visit_type,
                 notes, source_anchor, current["id"], now_utc()))
            self.db.execute("UPDATE visit_versions SET state='superseded' WHERE id=?",
                            (current["id"],))
            version_id = int(vcur.lastrowid)
            self._event(case_id, "visit_amended", visit_id=visit_id,
                        version_id=version_id, version=new_version,
                        supersedes_id=current["id"])
            return {"visit_id": visit_id, "version_id": version_id,
                    "version": new_version, "supersedes_id": current["id"]}

    def list_visits(self, case_id: str) -> dict:
        """List this case's visits with full version history, oldest first.

        Strictly case-scoped: only rows carrying this case_id are read.
        History arrays are in version order; the current version is also
        projected separately for convenient rendering.
        """
        self._case(case_id)
        with self.db:
            self.db.execute("BEGIN")
            visits = self._dicts(self.db.execute(
                "SELECT id,case_id,created_at FROM visits WHERE case_id=? ORDER BY id",
                (case_id,)).fetchall())
            out = []
            for visit in visits:
                versions = self._dicts(self.db.execute(
                    "SELECT * FROM visit_versions WHERE visit_id=? AND case_id=? ORDER BY version",
                    (visit["id"], case_id)).fetchall())
                projected = [self._project_visit_version(v) for v in versions]
                current = next((v for v in projected if v["state"] == "current"), None)
                out.append({
                    "visit_id": visit["id"],
                    "created_at": visit["created_at"],
                    "current": current,
                    "history": projected,
                })
            return {
                "visits": out,
                "recorded_date_label": self.VISIT_RECORDED_DATE_LABEL,
                "disclaimer": self.VISIT_DISCLAIMER,
                "synthetic": True,
            }
    # ---- Evidence quality and limitations (descriptive only) ----
    # Append-only human notes about one exact source version. Recording
    # never updates source_versions, assertions, questions, snapshots, or
    # any review state; it only inserts one row plus a ledger event.
    # No rating or score exists: absence of rows means "not assessed".

    @staticmethod
    def _check_quality_note(value: object, field: str) -> str:
        if not isinstance(value, str) or not 1 <= len(value.strip()) <= 1000:
            raise InvalidInput(f"{field} must have 1-1000 characters")
        return value.strip()

    def record_evidence_quality(self, case_id: str, source_version_id: int,
                                assessor_label: object, date_recorded: object,
                                completeness_note: object, limitations_text: object,
                                conflict_note: object) -> int:
        """Append one descriptive quality note to one exact source version."""
        case_id = self._case(case_id)
        if type(source_version_id) is not int or source_version_id < 1:
            raise InvalidInput("Invalid source version ID")
        if not isinstance(assessor_label, str) or not 2 <= len(assessor_label.strip()) <= 80:
            raise InvalidInput("Provide an assessor label")
        recorded = valid_date(date_recorded) if isinstance(date_recorded, str) else None
        if recorded is None:
            raise InvalidInput("Dates must use YYYY-MM-DD")
        completeness = self._check_quality_note(completeness_note, "Completeness note")
        limitations = self._check_quality_note(limitations_text, "Limitations text")
        conflict = self._check_quality_note(conflict_note, "Conflict note")
        with self.db:
            self.db.execute("BEGIN IMMEDIATE")
            source = self.db.execute(
                "SELECT id FROM source_versions WHERE id=? AND case_id=?",
                (source_version_id, case_id)).fetchone()
            if not source:
                raise InvalidInput("Source not in this case")
            cur = self.db.execute("""INSERT INTO evidence_quality_assessments
                (case_id,source_version_id,assessor_label,date_recorded,
                 completeness_note,limitations_text,conflict_note,created_at)
                VALUES (?,?,?,?,?,?,?,?)""",
                (case_id, source_version_id, assessor_label.strip(), recorded,
                 completeness, limitations, conflict, now_utc()))
            self._event(case_id, "evidence_quality_recorded",
                        assessment_id=int(cur.lastrowid),
                        source_version_id=source_version_id)
            return int(cur.lastrowid)

    def evidence_quality(self, case_id: str) -> dict:
        """One entry per source version in this case only, current first.

        Each entry carries its source id, document id, citation anchor, and
        its own assessments in recorded order. Entries with no assessments
        carry assessment_status 'not_assessed' with an empty list; no
        quality is ever inferred. Superseded versions appear separately
        with their own assessments intact.
        """
        self._case(case_id)
        with self.db:
            self.db.execute("BEGIN")
            current_rows = self._dicts(self.db.execute(
                """SELECT id,document_id,version,state FROM source_versions
                WHERE case_id=? AND state='current'
                ORDER BY document_id,version,id""", (case_id,)).fetchall())
            superseded_rows = self._dicts(self.db.execute(
                """SELECT id,document_id,version,state FROM source_versions
                WHERE case_id=? AND state='superseded'
                ORDER BY document_id,version,id""", (case_id,)).fetchall())

            def entry(row: dict) -> dict:
                notes = self._dicts(self.db.execute(
                    """SELECT id,source_version_id,assessor_label,date_recorded,
                    completeness_note,limitations_text,conflict_note,created_at
                    FROM evidence_quality_assessments
                    WHERE case_id=? AND source_version_id=? ORDER BY id""",
                    (case_id, row["id"])).fetchall())
                return {
                    "source_id": row["id"],
                    "document_id": row["document_id"],
                    "version": row["version"],
                    "state": row["state"],
                    "citation_anchor": (
                        f"{row['document_id']}@{row['version']}, "
                        f"source version #{row['id']}"
                    ),
                    "assessment_status": "assessed" if notes else "not_assessed",
                    "assessments": notes,
                }

            return {
                "case_id": case_id,
                "synthetic": True,
                "disclaimer": ("Fictional demo data only. Quality notes are "
                               "human-authored descriptions, not ratings, scores, "
                               "or clinical judgments. 'Not assessed' means no note "
                               "was recorded; no quality is inferred."),
                "current": [entry(row) for row in current_rows],
                "superseded": [entry(row) for row in superseded_rows],
            }
    # ---- Second-opinion and survivorship care records ----
    # Additive slice over the same ledger. A second-opinion response is a
    # separate record that never overwrites the original case conclusion;
    # survivorship items are plain recorded plans, never directives. Every
    # row keeps its source anchor and review state; amendments reopen only
    # dependent rows in the amended case.

    @staticmethod
    def _descriptive(field: str, value: object, min_len: int, max_len: int) -> str:
        try:
            return check_descriptive(field, value, min_len, max_len)
        except CareRecordInputError as error:
            raise InvalidInput(str(error)) from error

    @staticmethod
    def _record_label(value: object, field: str) -> str:
        if not isinstance(value, str) or not 2 <= len(value.strip()) <= 80:
            raise InvalidInput(f"Provide a {field}")
        return value.strip()

    def _invalidate_care_records(self, case_id: str, superseded_source_id: int | None,
                                 invalidated_snapshot_ids: list[int]) -> tuple[list[int], list[int]]:
        """Mark dependent care records needs_review. Caller owns a write transaction.

        Only rows in THIS case whose pinned material, response/item anchor,
        or linked original snapshot was superseded are affected. History is
        preserved; other cases are untouched.
        """
        if superseded_source_id is None:
            return [], []
        so_ids: set[int] = set()
        for row in self.db.execute(
                """SELECT DISTINCT r.id FROM second_opinion_requests r
                JOIN second_opinion_materials m ON m.request_id=r.id
                WHERE r.case_id=? AND m.source_version_id=? AND r.review_state!='needs_review'""",
                (case_id, superseded_source_id)).fetchall():
            so_ids.add(row[0])
        for row in self.db.execute(
                """SELECT DISTINCT r.id FROM second_opinion_requests r
                JOIN second_opinion_responses resp ON resp.request_id=r.id
                WHERE r.case_id=? AND resp.anchor_source_version_id=? AND r.review_state!='needs_review'""",
                (case_id, superseded_source_id)).fetchall():
            so_ids.add(row[0])
        if invalidated_snapshot_ids:
            marks = ",".join("?" for _ in invalidated_snapshot_ids)
            for row in self.db.execute(
                    f"""SELECT id FROM second_opinion_requests WHERE case_id=?
                    AND snapshot_id IN ({marks}) AND review_state!='needs_review'""",
                    [case_id, *invalidated_snapshot_ids]).fetchall():
                so_ids.add(row[0])
        invalidated_so = sorted(so_ids)
        if invalidated_so:
            marks = ",".join("?" for _ in invalidated_so)
            self.db.execute(f"UPDATE second_opinion_requests SET review_state='needs_review' WHERE id IN ({marks})",
                            invalidated_so)
            self._event(case_id, "second_opinion_review_reopened",
                        source_version_id=superseded_source_id, invalidated_requests=invalidated_so)
        surv_rows = self.db.execute(
            """SELECT id FROM survivorship_items
            WHERE case_id=? AND anchor_source_version_id=? AND review_state!='needs_review'""",
            (case_id, superseded_source_id)).fetchall()
        invalidated_surv = [row[0] for row in surv_rows]
        if invalidated_surv:
            marks = ",".join("?" for _ in invalidated_surv)
            self.db.execute(f"UPDATE survivorship_items SET review_state='needs_review' WHERE id IN ({marks})",
                            invalidated_surv)
            self._event(case_id, "survivorship_review_reopened",
                        source_version_id=superseded_source_id, invalidated_items=invalidated_surv)
        return invalidated_so, invalidated_surv

    def create_second_opinion_request(self, case_id: str, question_id: int, question_text: str,
                                      source_version_ids: list[int],
                                      snapshot_id: int | None = None) -> int:
        """Record a second-opinion request: question, shared materials, status.

        Materials are pinned by exact source version. The optional snapshot
        links the original case conclusion under discussion; the request and
        any later response never modify it.
        """
        case_id = self._case(case_id)
        if type(question_id) is not int:
            raise InvalidInput("Question ID must be an integer")
        text = self._descriptive("Second-opinion question", question_text, 5, 500)
        if (not isinstance(source_version_ids, list) or not source_version_ids
                or len(source_version_ids) != len(set(source_version_ids))
                or len(source_version_ids) > 50
                or any(type(x) is not int or x < 1 for x in source_version_ids)):
            raise InvalidInput("Shared materials must be 1\u201350 unique source version IDs")
        if snapshot_id is not None and (type(snapshot_id) is not int or snapshot_id < 1):
            raise InvalidInput("Original snapshot ID must be a positive integer")
        with self.db:
            self.db.execute("BEGIN IMMEDIATE")
            if not self.db.execute("SELECT 1 FROM questions WHERE id=? AND case_id=?",
                                   (question_id, case_id)).fetchone():
                raise InvalidInput("Question not in this case")
            if snapshot_id is not None and not self.db.execute(
                    "SELECT 1 FROM snapshots WHERE id=? AND case_id=?", (snapshot_id, case_id)).fetchone():
                raise InvalidInput("Original investigation snapshot not in this case")
            for sid in source_version_ids:
                if not self.db.execute(
                        "SELECT 1 FROM source_versions WHERE id=? AND case_id=? AND state='current'",
                        (sid, case_id)).fetchone():
                    raise InvalidInput("Shared material is missing, superseded, or belongs to another case")
            cur = self.db.execute("""INSERT INTO second_opinion_requests
                (case_id,question_id,snapshot_id,question_text,status,review_state,created_at)
                VALUES (?,?,?,?,'requested','pending',?)""",
                (case_id, question_id, snapshot_id, text, now_utc()))
            request_id = int(cur.lastrowid)
            for sid in source_version_ids:
                self.db.execute("INSERT INTO second_opinion_materials VALUES (?,?)", (request_id, sid))
            self._event(case_id, "second_opinion_requested", request_id=request_id,
                        question_id=question_id, snapshot_id=snapshot_id,
                        material_source_version_ids=list(source_version_ids))
            return request_id

    def record_second_opinion_response(self, case_id: str, request_id: int, responder_label: str,
                                       response_text: str, anchor_source_version_id: int) -> int:
        """Record one response as a separate record. The original is untouched.

        Exactly one response per request: follow-up needs a new request, so
        no response can silently replace an earlier one.
        """
        case_id = self._case(case_id)
        if type(request_id) is not int or request_id < 1:
            raise InvalidInput("Invalid second-opinion request ID")
        responder = self._record_label(responder_label, "responder label")
        text = self._descriptive("Second-opinion response", response_text, 10, 2000)
        if type(anchor_source_version_id) is not int or anchor_source_version_id < 1:
            raise InvalidInput("Anchor source version ID must be a positive integer")
        with self.db:
            self.db.execute("BEGIN IMMEDIATE")
            row = self.db.execute("SELECT status FROM second_opinion_requests WHERE id=? AND case_id=?",
                                  (request_id, case_id)).fetchone()
            if not row:
                raise InvalidInput("Second-opinion request not in this case")
            if row["status"] != "requested":
                raise InvalidInput("A response is already recorded for this request; create a new request for follow-up")
            anchor = self.db.execute("SELECT state FROM source_versions WHERE id=? AND case_id=?",
                                     (anchor_source_version_id, case_id)).fetchone()
            if not anchor or anchor["state"] != "current":
                raise InvalidInput("Response anchor is missing, superseded, or belongs to another case")
            try:
                cur = self.db.execute("""INSERT INTO second_opinion_responses
                    (request_id,responder_label,response_text,anchor_source_version_id,created_at)
                    VALUES (?,?,?,?,?)""", (request_id, responder, text, anchor_source_version_id, now_utc()))
            except sqlite3.IntegrityError:
                raise InvalidInput("A response is already recorded for this request; create a new request for follow-up") from None
            self.db.execute("UPDATE second_opinion_requests SET status='response_recorded' WHERE id=?", (request_id,))
            self._event(case_id, "second_opinion_response_recorded", request_id=request_id,
                        response_id=int(cur.lastrowid), anchor_source_version_id=anchor_source_version_id)
            return int(cur.lastrowid)

    def review_second_opinion(self, case_id: str, request_id: int, reviewer_label: str, scope: str) -> dict:
        """Demo-acknowledge a second-opinion request record. History is kept."""
        case_id = self._case(case_id)
        if type(request_id) is not int or request_id < 1:
            raise InvalidInput("Invalid second-opinion request ID")
        reviewer = self._record_label(reviewer_label, "reviewer label")
        scope_text = self._descriptive("Review scope", scope, 10, 300)
        with self.db:
            self.db.execute("BEGIN IMMEDIATE")
            row = self.db.execute("SELECT review_state FROM second_opinion_requests WHERE id=? AND case_id=?",
                                  (request_id, case_id)).fetchone()
            if not row:
                raise InvalidInput("Second-opinion request not in this case")
            if row["review_state"] == "needs_review":
                raise InvalidInput("Shared materials changed since this request; preserve it and create a new request")
            if row["review_state"] == "reviewed_in_demo":
                raise InvalidInput("Second-opinion request is already reviewed in this demo")
            self.db.execute("UPDATE second_opinion_requests SET review_state='reviewed_in_demo' WHERE id=?", (request_id,))
            cur = self.db.execute("""INSERT INTO second_opinion_review_events
                (request_id,reviewer_label,action,scope,noted_at) VALUES (?,?,'acknowledge',?,?)""",
                (request_id, reviewer, scope_text, now_utc()))
            self._event(case_id, "second_opinion_reviewed", request_id=request_id,
                        review_event_id=int(cur.lastrowid))
            return {"result": "acknowledged_in_demo", "review_event_id": int(cur.lastrowid)}

    def second_opinion_view(self, case_id: str) -> dict:
        """Original conclusions and second-opinion responses, side by side.

        The response is a separate record; this projection never merges it
        into the original snapshot. Both stay visible with their own states.
        """
        self._case(case_id)
        requests: list[dict] = []
        for req in self.db.execute(
                "SELECT * FROM second_opinion_requests WHERE case_id=? ORDER BY id", (case_id,)).fetchall():
            req = dict(req)
            question = self.db.execute("SELECT question FROM questions WHERE id=?",
                                       (req["question_id"],)).fetchone()
            materials = self._dicts(self.db.execute(
                """SELECT v.id,v.document_id,v.version,v.state FROM second_opinion_materials m
                JOIN source_versions v ON v.id=m.source_version_id
                WHERE m.request_id=? ORDER BY v.document_id,v.version""", (req["id"],)).fetchall())
            original = None
            if req["snapshot_id"] is not None:
                snap = self.db.execute(
                    "SELECT id,question_id,summary,state,created_at,reviewed_at FROM snapshots WHERE id=?",
                    (req["snapshot_id"],)).fetchone()
                original = dict(snap) if snap else {"id": req["snapshot_id"], "missing": True}
            response = self.db.execute(
                "SELECT * FROM second_opinion_responses WHERE request_id=?", (req["id"],)).fetchone()
            response_view = None
            if response:
                response_view = dict(response)
                anchor = self.db.execute(
                    "SELECT document_id,version,state FROM source_versions WHERE id=?",
                    (response["anchor_source_version_id"],)).fetchone()
                response_view["anchor"] = dict(anchor) if anchor else {"missing": True}
            requests.append({
                **req,
                "question": question["question"] if question else None,
                "materials": materials,
                "original_snapshot": original,
                "response": response_view,
                "review_events": self._dicts(self.db.execute(
                    "SELECT * FROM second_opinion_review_events WHERE request_id=? ORDER BY id",
                    (req["id"],)).fetchall()),
            })
        return {"case_id": case_id, "disclaimer": SECOND_OPINION_DISCLAIMER, "requests": requests}

    def create_survivorship_plan(self, case_id: str, title: str) -> int:
        """Create a survivorship care plan record: a container for plain recorded items."""
        case_id = self._case(case_id)
        title_text = self._descriptive("Survivorship plan title", title, 1, 120)
        with self.db:
            cur = self.db.execute("INSERT INTO survivorship_plans (case_id,title,created_at) VALUES (?,?,?)",
                                  (case_id, title_text, now_utc()))
            plan_id = int(cur.lastrowid)
            self._event(case_id, "survivorship_plan_created", plan_id=plan_id)
            return plan_id

    def add_survivorship_item(self, case_id: str, plan_id: int, kind: str, description: str,
                              anchor_source_version_id: int, recorded_date: str | None = None) -> int:
        """Record one follow-up, watch, or trigger item as a plain description.

        A recorded date is a ledger note, never a clinical due date. New
        items must anchor to a current source version in this case.
        """
        case_id = self._case(case_id)
        if type(plan_id) is not int or plan_id < 1:
            raise InvalidInput("Invalid survivorship plan ID")
        if kind not in ("followup", "watch", "trigger"):
            raise InvalidInput("Survivorship item kind must be followup, watch, or trigger")
        text = self._descriptive("Survivorship item", description, 10, 500)
        if type(anchor_source_version_id) is not int or anchor_source_version_id < 1:
            raise InvalidInput("Anchor source version ID must be a positive integer")
        recorded = None
        if recorded_date is not None:
            if not isinstance(recorded_date, str):
                raise InvalidInput("Dates must use YYYY-MM-DD")
            recorded = valid_date(recorded_date)
        with self.db:
            self.db.execute("BEGIN IMMEDIATE")
            if not self.db.execute("SELECT 1 FROM survivorship_plans WHERE id=? AND case_id=?",
                                   (plan_id, case_id)).fetchone():
                raise InvalidInput("Survivorship plan not in this case")
            anchor = self.db.execute("SELECT state FROM source_versions WHERE id=? AND case_id=?",
                                     (anchor_source_version_id, case_id)).fetchone()
            if not anchor or anchor["state"] != "current":
                raise InvalidInput("Item anchor is missing, superseded, or belongs to another case")
            cur = self.db.execute("""INSERT INTO survivorship_items
                (plan_id,case_id,kind,description,recorded_date,anchor_source_version_id,
                 state,review_state,created_at)
                VALUES (?,?,?,?,?,?,'recorded','pending',?)""",
                (plan_id, case_id, kind, text, recorded, anchor_source_version_id, now_utc()))
            item_id = int(cur.lastrowid)
            self._event(case_id, "survivorship_item_recorded", plan_id=plan_id, item_id=item_id, item_kind=kind)
            return item_id

    def review_survivorship_item(self, case_id: str, item_id: int, reviewer_label: str, scope: str) -> dict:
        """Demo-acknowledge one survivorship item. History is kept."""
        case_id = self._case(case_id)
        if type(item_id) is not int or item_id < 1:
            raise InvalidInput("Invalid survivorship item ID")
        reviewer = self._record_label(reviewer_label, "reviewer label")
        scope_text = self._descriptive("Review scope", scope, 10, 300)
        with self.db:
            self.db.execute("BEGIN IMMEDIATE")
            row = self.db.execute("SELECT review_state FROM survivorship_items WHERE id=? AND case_id=?",
                                  (item_id, case_id)).fetchone()
            if not row:
                raise InvalidInput("Survivorship item not in this case")
            if row["review_state"] == "needs_review":
                raise InvalidInput("Item anchor changed since recording; preserve it and record a new item")
            if row["review_state"] == "reviewed_in_demo":
                raise InvalidInput("Survivorship item is already reviewed in this demo")
            self.db.execute("UPDATE survivorship_items SET review_state='reviewed_in_demo' WHERE id=?", (item_id,))
            cur = self.db.execute("""INSERT INTO survivorship_review_events
                (item_id,reviewer_label,action,scope,noted_at) VALUES (?,?,'acknowledge',?,?)""",
                (item_id, reviewer, scope_text, now_utc()))
            self._event(case_id, "survivorship_item_reviewed", item_id=item_id,
                        review_event_id=int(cur.lastrowid))
            return {"result": "acknowledged_in_demo", "review_event_id": int(cur.lastrowid)}

    def mark_survivorship_trigger(self, case_id: str, item_id: int, reason: str) -> dict:
        """Record that a review trigger's described condition was observed.

        Only trigger items can be marked, exactly once. The reason describes
        the observed record; it never directs care.
        """
        case_id = self._case(case_id)
        if type(item_id) is not int or item_id < 1:
            raise InvalidInput("Invalid survivorship item ID")
        reason_text = self._descriptive("Trigger observation", reason, 10, 300)
        with self.db:
            self.db.execute("BEGIN IMMEDIATE")
            row = self.db.execute("SELECT kind,state,review_state FROM survivorship_items WHERE id=? AND case_id=?",
                                  (item_id, case_id)).fetchone()
            if not row:
                raise InvalidInput("Survivorship item not in this case")
            if row["kind"] != "trigger":
                raise InvalidInput("Only a review-trigger item can be marked as observed")
            if row["state"] == "triggered":
                raise InvalidInput("Trigger is already marked as observed")
            if row["review_state"] == "needs_review":
                raise InvalidInput("Item anchor changed since recording; preserve it and record a new item")
            self.db.execute("UPDATE survivorship_items SET state='triggered' WHERE id=?", (item_id,))
            self._event(case_id, "survivorship_trigger_marked", item_id=item_id, reason=reason_text)
            return {"result": "triggered", "item_id": item_id}

    def survivorship_view(self, case_id: str) -> dict:
        """Recorded follow-up plans: plain descriptions with anchors and review state."""
        self._case(case_id)
        plans: list[dict] = []
        for plan in self.db.execute(
                "SELECT * FROM survivorship_plans WHERE case_id=? ORDER BY id", (case_id,)).fetchall():
            plan = dict(plan)
            items = []
            for item in self.db.execute(
                    "SELECT * FROM survivorship_items WHERE plan_id=? ORDER BY id", (plan["id"],)).fetchall():
                item = dict(item)
                anchor = self.db.execute(
                    "SELECT document_id,version,state FROM source_versions WHERE id=?",
                    (item["anchor_source_version_id"],)).fetchone()
                items.append({
                    **item,
                    "anchor": dict(anchor) if anchor else {"missing": True},
                    "recorded_date_label": ("Recorded date (not a clinical due date): " + item["recorded_date"]
                                            if item["recorded_date"] else "No recorded date"),
                    "review_events": self._dicts(self.db.execute(
                        "SELECT * FROM survivorship_review_events WHERE item_id=? ORDER BY id",
                        (item["id"],)).fetchall()),
                })
            plans.append({**plan, "items": items})
        return {"case_id": case_id, "disclaimer": SURVIVORSHIP_DISCLAIMER, "plans": plans}

    # ---- B-08: contradiction synthesis + bounded reports (append-only) ----
    # New ledger table (limitation_notes, see SCHEMA) plus thin read/write
    # methods. Existing behavior — assess_synthetic_evidence,
    # create_snapshot, export_markdown — is reused unchanged.

    def add_limitation_note(self, case_id: str, question_id: int, *,
                            assessment_id: int | None = None,
                            broker_link_id: int | None = None,
                            note: str = "", author_label: str = "") -> int:
        """Append one HUMAN-entered limitation note; history is preserved.

        Exactly one target (an assessment or a broker link in this case and
        question) is required. Notes are never updated or deleted: there is
        no update or delete path, only this append. No quality number is
        computed from notes anywhere.
        """
        self._case(case_id)
        if type(question_id) is not int:
            raise InvalidInput("Question id must be an integer")
        targets = [value for value in (assessment_id, broker_link_id) if value is not None]
        if len(targets) != 1 or type(targets[0]) is not int or targets[0] < 1:
            raise InvalidInput("A limitation note needs exactly one assessment or broker link target")
        if not isinstance(note, str) or not 15 <= len(note.strip()) <= 800:
            raise InvalidInput("Limitation note must have 15–800 characters")
        if not isinstance(author_label, str) or not 2 <= len(author_label.strip()) <= 80:
            raise InvalidInput("Provide a note author label")
        with self.db:
            self.db.execute("BEGIN IMMEDIATE")
            if not self.db.execute("SELECT 1 FROM questions WHERE id=? AND case_id=?",
                                   (question_id, case_id)).fetchone():
                raise InvalidInput("Question not in this case")
            if assessment_id is not None:
                target = self.db.execute("""SELECT 1 FROM evidence_assessments
                    WHERE id=? AND case_id=? AND question_id=?""",
                    (assessment_id, case_id, question_id)).fetchone()
                if not target:
                    raise InvalidInput("Evidence assessment not in this case and question")
            else:
                target = self.db.execute("""SELECT 1 FROM broker_links
                    WHERE id=? AND case_id=? AND question_id=?""",
                    (broker_link_id, case_id, question_id)).fetchone()
                if not target:
                    raise InvalidInput("Broker link not in this case and question")
            cur = self.db.execute("""INSERT INTO limitation_notes
                (case_id,question_id,assessment_id,broker_link_id,note,author_label,created_at)
                VALUES (?,?,?,?,?,?,?)""",
                (case_id, question_id, assessment_id, broker_link_id,
                 note.strip(), author_label.strip(), now_utc()))
            self._event(case_id, "limitation_noted", note_id=cur.lastrowid,
                        question_id=question_id, assessment_id=assessment_id,
                        broker_link_id=broker_link_id)
            return int(cur.lastrowid)

    def list_limitation_notes(self, case_id: str, question_id: int) -> list[dict]:
        """List a question's limitation notes, earliest first. Reads only."""
        self._case(case_id)
        if type(question_id) is not int:
            raise InvalidInput("Question id must be an integer")
        if not self.db.execute("SELECT 1 FROM questions WHERE id=? AND case_id=?",
                               (question_id, case_id)).fetchone():
            raise InvalidInput("Question not in this case")
        return self._dicts(self.db.execute(
            """SELECT id,question_id,assessment_id,broker_link_id,note,author_label,created_at
            FROM limitation_notes WHERE case_id=? AND question_id=? ORDER BY id""",
            (case_id, question_id)).fetchall())

    def question_synthesis(self, case_id: str, question_id: int) -> dict:
        """Per-question support/contradict synthesis. Reads only; writes nothing."""
        from .synthesis import question_synthesis as build
        return build(self, case_id, question_id)

    def snapshot_synthesis(self, case_id: str, snapshot_id: int) -> dict:
        """Per-snapshot synthesis with cutoff and basis status. Reads only."""
        from .synthesis import snapshot_synthesis as build
        return build(self, case_id, snapshot_id)

    def synthesis_report(self, case_id: str, snapshot_id: int) -> str:
        """Bounded workspace report with cutoff and REVIEW-PENDING. Reads only."""
        from .synthesis import render_bounded_report as render
        return render(self, case_id, snapshot_id)

    def synthesis_patient_report(self, case_id: str, snapshot_id: int) -> str:
        """Plain-words bounded report over the same cutoff. Reads only."""
        from .synthesis import render_patient_report as render
        return render(self, case_id, snapshot_id)
