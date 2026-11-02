"""Synthetic-only first-party clinical-note -> original-source provenance bridge.

This stores append-only *references* to the existing clinical note and
CaseStore source version owners. It does not create or normalize patient
records, source bytes, observations, signatures, clinical conclusions or an
authorization service. Canonical PAT-* to synthetic CASE-* identity mapping
MUST be independently resolved by an injected, trusted binder; the binder
used in tests is only a fictional fixture, never a real identity proof.
"""
from __future__ import annotations

import re
import sqlite3
from collections.abc import Callable

from .patient_registry import PatientRegistry, PatientRegistryError, PatientRegistryDenied
from .store import CaseStore, InvalidInput, now_utc


class ClinicalSourceLinkDenied(PermissionError):
    """Unverified patient/case binding, actor, or purpose."""


class ClinicalSourceLinkError(InvalidInput):
    """The requested immutable source or clinical-note version is ineligible."""


Authorizer = Callable[[str, str, str, str], bool]
CaseBinding = Callable[[str, str, str, str], bool]

ACTOR = re.compile(r"[A-Za-z0-9][A-Za-z0-9_.:-]{2,99}\Z")
PURPOSES = frozenset({"care", "operations", "research"})

SCHEMA = """
CREATE TABLE IF NOT EXISTS clinical_note_source_refs (
  id INTEGER PRIMARY KEY,
  patient_id TEXT NOT NULL REFERENCES identity_patients(patient_id),
  case_id TEXT NOT NULL REFERENCES cases(case_id),
  note_version_id INTEGER NOT NULL REFERENCES clinical_note_versions(id),
  source_version_id INTEGER NOT NULL REFERENCES source_versions(id),
  source_line INTEGER NOT NULL CHECK(source_line > 0),
  linked_by TEXT NOT NULL,
  linked_at TEXT NOT NULL,
  UNIQUE(note_version_id, source_version_id, source_line)
);
CREATE INDEX IF NOT EXISTS idx_clinical_note_source_refs_patient
  ON clinical_note_source_refs(patient_id, note_version_id);
CREATE TRIGGER IF NOT EXISTS clinical_note_source_refs_immutable_update
BEFORE UPDATE ON clinical_note_source_refs BEGIN
 SELECT RAISE(ABORT, 'Clinical source reference is immutable');
END;
CREATE TRIGGER IF NOT EXISTS clinical_note_source_refs_immutable_delete
BEFORE DELETE ON clinical_note_source_refs BEGIN
 SELECT RAISE(ABORT, 'Clinical source reference is immutable');
END;
"""


class ClinicalSourceProvenance:
    """First-party note-to-source *reference* join over one original SQLite host.

    A trusted layer must supply both the actor authorizer and a persistent,
    revocable patient-to-case binding. We do not infer mapping from names,
    similar dates or shared records. The existing CaseStore is only an
    independent synthetic source adapter, not the production patient owner.
    """

    def __init__(self, registry: PatientRegistry, sources: CaseStore,
                 authorizer: Authorizer | None = None,
                 case_binding: CaseBinding | None = None):
        if registry.db is not sources.db:
            raise ClinicalSourceLinkError(
                "Clinical and source references require the same transaction host")
        if registry.db.in_transaction:
            raise ClinicalSourceLinkError("Install source-link schema outside transactions")
        self.db = registry.db
        self.registry = registry
        self.sources = sources
        self.authorizer = authorizer
        self.case_binding = case_binding
        self.db.executescript(SCHEMA)

    def _allow(self, patient_id: str, case_id: str, *,
               actor: str, purpose: str, action: str) -> None:
        if not isinstance(actor, str) or not ACTOR.fullmatch(actor) or purpose not in PURPOSES:
            raise ClinicalSourceLinkDenied("Invalid actor or purpose")
        try:
            allowed = bool(self.authorizer and
                           self.authorizer(actor, patient_id, action, purpose))
            bound = bool(self.case_binding and
                         self.case_binding(patient_id, case_id, actor, purpose))
        except Exception:
            allowed, bound = False, False
        if not (allowed and bound):
            raise ClinicalSourceLinkDenied("Clinical source access denied")
        try:
            self.registry.require_patient(patient_id)
        except (PatientRegistryError, PatientRegistryDenied):
            raise ClinicalSourceLinkDenied("Unknown patient") from None

    @staticmethod
    def _version(value: int, name: str) -> int:
        if type(value) is not int or value < 1:
            raise ClinicalSourceLinkError(f"{name} must be a positive integer")
        return value

    def _note_version(self, patient_id: str, note_version_id: int) -> sqlite3.Row:
        row = self.db.execute(
            """SELECT v.id,v.status,v.version,v.sha256,n.id AS note_id,
                      e.id AS encounter_id,e.patient_id
               FROM clinical_note_versions v
               JOIN clinical_note_headers n ON n.id=v.note_id
               JOIN clinical_encounters e ON e.id=n.encounter_id
               WHERE e.patient_id=? AND v.id=?""",
            (patient_id, note_version_id),
        ).fetchone()
        if row is None:
            raise ClinicalSourceLinkError("Note version not in this patient")
        return row

    def attach(self, patient_id: str, case_id: str, note_version_id: int,
               source_version_id: int, source_line: int, *,
               actor: str, purpose: str) -> dict:
        """Attach only to a draft and a current, case-matched assertion line.

        An attested version cannot acquire citations after its attestation;
        corrections and source amendments produce new versions/review work.
        Returns a receipt, not verified clinical source authenticity.
        """
        self._allow(patient_id, case_id, actor=actor, purpose=purpose,
                    action="note.provenance_link")
        self._version(note_version_id, "note_version_id")
        self._version(source_version_id, "source_version_id")
        self._version(source_line, "source_line")
        if self.db.in_transaction:
            raise ClinicalSourceLinkError("Source-link write requires its own transaction")
        with self.db:
            self.db.execute("BEGIN IMMEDIATE")
            note = self._note_version(patient_id, note_version_id)
            if note["status"] not in ("draft", "draft_correction"):
                raise ClinicalSourceLinkError(
                    "Only a draft version can receive new source references")
            source = self.db.execute(
                """SELECT id FROM source_versions
                   WHERE id=? AND case_id=? AND state='current'""",
                (source_version_id, case_id),
            ).fetchone()
            if source is None:
                raise ClinicalSourceLinkError(
                    "Source version is absent, other-case or superseded")
            line = self.db.execute(
                """SELECT 1 FROM assertions
                   WHERE case_id=? AND source_version_id=? AND source_line=?""",
                (case_id, source_version_id, source_line),
            ).fetchone()
            if line is None:
                raise ClinicalSourceLinkError("Source line is not a current exact assertion")
            old = self.db.execute(
                """SELECT id FROM clinical_note_source_refs
                   WHERE note_version_id=? AND source_version_id=? AND source_line=?""",
                (note_version_id, source_version_id, source_line),
            ).fetchone()
            if old is not None:
                return {"link_id": old["id"], "duplicate": True}
            inserted = self.db.execute(
                """INSERT INTO clinical_note_source_refs (
                     patient_id,case_id,note_version_id,source_version_id,
                     source_line,linked_by,linked_at) VALUES (?,?,?,?,?,?,?)""",
                (patient_id, case_id, note_version_id, source_version_id,
                 source_line, actor, now_utc()),
            )
            self.registry.append_event(
                patient_id, "clinical_note_source_linked",
                case_id=case_id, note_version_id=note_version_id,
                source_version_id=source_version_id, source_line=source_line,
                actor=actor, purpose=purpose,
            )
            return {"link_id": inserted.lastrowid, "duplicate": False}

    def note_sources(self, patient_id: str, case_id: str, note_version_id: int,
                     *, actor: str, purpose: str) -> list[dict]:
        """Read exact source anchors and *current freshness*, never rewrite history.

        An amendment marks prior links review-required in this read projection.
        It does not rewrite the clinical note, claim clinician review, or
        silently transfer an old link to a corrected note version.
        """
        self._allow(patient_id, case_id, actor=actor, purpose=purpose,
                    action="note.provenance_read")
        self._version(note_version_id, "note_version_id")
        self._note_version(patient_id, note_version_id)
        rows = self.db.execute(
            """SELECT r.id AS link_id, r.note_version_id, r.source_version_id,
                      r.source_line, r.linked_by, r.linked_at,
                      s.document_id, s.version AS document_version,
                      s.sha256 AS source_sha256,s.event_date,s.issued_at,
                      s.specimen_id,s.state AS source_state,
                      a.finding_key, a.certainty, a.quote AS original_statement
               FROM clinical_note_source_refs r
               JOIN source_versions s ON s.id=r.source_version_id
               JOIN assertions a ON a.source_version_id=r.source_version_id
                    AND a.source_line=r.source_line
               WHERE r.patient_id=? AND r.case_id=? AND r.note_version_id=?
               ORDER BY r.id""",
            (patient_id, case_id, note_version_id),
        ).fetchall()
        return [
            {
                **dict(row),
                "provenance_state": (
                    "current_source_unreviewed" if row["source_state"] == "current"
                    else "source_superseded_review_required"
                ),
                "clinical_review_state": "not_established_by_source_link",
            }
            for row in rows
        ]
