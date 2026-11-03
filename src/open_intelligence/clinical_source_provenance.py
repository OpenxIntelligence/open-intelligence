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
from .document_intake import classification_provenance
from .source_provenance import PROVENANCE_FIELDS, source_provenance, assertion_provenance


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
  annotation_revision_id INTEGER REFERENCES document_annotation_revisions(id),
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
        # Older links recorded only an original and line. Their manual
        # selection version cannot be inferred after corrections; preserve
        # the unknown binding instead of attaching today's annotations.
        columns = {row["name"] for row in self.db.execute(
            "PRAGMA table_info(clinical_note_source_refs)")}
        if "annotation_revision_id" not in columns:
            with self.db:
                self.db.execute("""ALTER TABLE clinical_note_source_refs ADD COLUMN
                    annotation_revision_id INTEGER REFERENCES document_annotation_revisions(id)""")

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
               actor: str, purpose: str,
               expected_annotation_revision: int | None = None) -> dict:
        """Attach only to a draft and a current, case-matched assertion line.

        An attested version cannot acquire citations after its attestation;
        corrections and source amendments produce new versions/review work.
        Initial manual intake defaults to revision 1 for older callers. After
        correction, the caller must explicitly name the inspected revision.
        Returns a receipt, not verified clinical source authenticity.
        """
        self._allow(patient_id, case_id, actor=actor, purpose=purpose,
                    action="note.provenance_link")
        self._version(note_version_id, "note_version_id")
        self._version(source_version_id, "source_version_id")
        self._version(source_line, "source_line")
        if (expected_annotation_revision is not None and
                (type(expected_annotation_revision) is not int or
                 not 1 <= expected_annotation_revision <= 2147483647)):
            raise ClinicalSourceLinkError(
                "Expected annotation revision must be a bounded positive integer")
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
            manual = self.db.execute(
                "SELECT 1 FROM document_intake_metadata WHERE source_version_id=?",
                (source_version_id,),
            ).fetchone()
            revision_id = None
            if manual:
                revision = self.db.execute("""SELECT id,revision FROM document_annotation_revisions
                    WHERE source_version_id=? ORDER BY revision DESC LIMIT 1""",
                    (source_version_id,)).fetchone()
                if revision is None:
                    raise ClinicalSourceLinkError("Manual annotation history is unavailable")
                expected = 1 if expected_annotation_revision is None else expected_annotation_revision
                if expected != revision["revision"]:
                    raise ClinicalSourceLinkError(
                        "Source annotations changed; refresh before linking this note")
                revision_id = revision["id"]
            elif expected_annotation_revision is not None:
                raise ClinicalSourceLinkError(
                    "Annotation revision supplied for a non-manual source")
            old = self.db.execute(
                """SELECT id,annotation_revision_id FROM clinical_note_source_refs
                   WHERE note_version_id=? AND source_version_id=? AND source_line=?""",
                (note_version_id, source_version_id, source_line),
            ).fetchone()
            if old is not None:
                if old["annotation_revision_id"] != revision_id:
                    raise ClinicalSourceLinkError(
                        "Existing note reference has different or unrecorded annotations; "
                        "inspect the change and use a new note version")
                return {"link_id": old["id"], "duplicate": True}
            inserted = self.db.execute(
                """INSERT INTO clinical_note_source_refs (
                     patient_id,case_id,note_version_id,source_version_id,
                     source_line,annotation_revision_id,linked_by,linked_at) VALUES (?,?,?,?,?,?,?,?)""",
                (patient_id, case_id, note_version_id, source_version_id,
                 source_line, revision_id, actor, now_utc()),
            )
            self.registry.append_event(
                patient_id, "clinical_note_source_linked",
                case_id=case_id, note_version_id=note_version_id,
                source_version_id=source_version_id, source_line=source_line,
                actor=actor, purpose=purpose,
                **({"annotation_revision_id": revision_id} if revision_id is not None else {}),
            )
            return {"link_id": inserted.lastrowid, "duplicate": False}

    def note_sources(self, patient_id: str, case_id: str, note_version_id: int,
                     *, actor: str, purpose: str) -> list[dict]:
        """Read exact source anchors and *current freshness*, never rewrite history.

        Amendments and annotation corrections mark prior links review-required.
        Bound manual selections come from their immutable revision, including
        after deletion from the current projection. An older link without a
        captured revision stays visible, with its selection explicitly unknown.
        """
        self._allow(patient_id, case_id, actor=actor, purpose=purpose,
                    action="note.provenance_read")
        self._version(note_version_id, "note_version_id")
        if self.db.in_transaction:
            self._note_version(patient_id, note_version_id)
            return self._linked_sources(patient_id, case_id, note_version_id)
        with self.db:
            self.db.execute("BEGIN")
            self._note_version(patient_id, note_version_id)
            return self._linked_sources(patient_id, case_id, note_version_id)

    def _linked_sources(self, patient_id: str, case_id: str,
                        note_version_id: int | None = None, *,
                        include_findings: bool = True) -> list[dict]:
        """Read captured selections and current freshness in the caller snapshot."""
        note_filter = " AND r.note_version_id=?" if note_version_id is not None else ""
        parameters = (patient_id, case_id, patient_id)
        if note_version_id is not None:
            parameters += (note_version_id,)
        rows = self.db.execute(
            """SELECT r.id AS link_id,r.annotation_revision_id AS captured_revision_id,
                      r.note_version_id,r.source_version_id,
                      r.source_line, r.linked_by, r.linked_at,
                      s.document_id, s.version AS document_version,
                      s.sha256 AS source_sha256,s.event_date,s.issued_at,
                      s.specimen_id,s.state AS source_state
               FROM clinical_note_source_refs r
               JOIN source_versions s ON s.id=r.source_version_id
               JOIN clinical_note_versions v ON v.id=r.note_version_id
               JOIN clinical_note_headers n ON n.id=v.note_id
               JOIN clinical_encounters e ON e.id=n.encounter_id
               WHERE r.patient_id=? AND r.case_id=? AND e.patient_id=?"""
            + note_filter + " ORDER BY r.id", parameters,
        ).fetchall()
        receipts = self.sources._document_intake_receipts(case_id)
        result = []
        for record in rows:
            row = dict(record)
            captured_id = row.pop("captured_revision_id")
            source_id = row["source_version_id"]
            current = receipts.get(source_id)
            freshness = "current_source_unreviewed"
            if current is not None and captured_id is None:
                # A pre-binding reference has no recoverable claim about
                # which selection was seen. Never substitute the latest one.
                row["annotation_capture_state"] = "not_recorded"
                findings = [{"finding_key": None, "certainty": None, "original_statement": None}]
                freshness = "annotation_revision_unrecorded_review_required"
            elif current is not None:
                captured = self.db.execute("""SELECT * FROM document_annotation_revisions
                    WHERE id=? AND source_version_id=?""", (captured_id, source_id)).fetchone()
                if captured is None:
                    raise ClinicalSourceLinkError("Captured annotation revision is unavailable")
                revision = self.sources._annotation_revision_data(captured)
                findings = [{"finding_key": finding["key"], "certainty": finding["state"],
                             "original_statement": finding["quote"]}
                            for finding in revision["findings"] if finding["line"] == row["source_line"]]
                if not findings:
                    raise ClinicalSourceLinkError("Captured annotation does not contain the linked line")
                receipt = {**current, "annotation_revision_id": captured_id,
                           "annotation_revision": revision["revision"],
                           "review_sha256": revision["review_sha256"]}
                origin = source_provenance({"document_intake": receipt,
                                            **classification_provenance(receipt)})
                self.sources._annotate_source_assertions([row], {source_id: receipt})
                assertion_provenance(row, origin, row["source_line"])
                row["annotation_capture_state"] = "recorded"
                if captured_id != current["annotation_revision_id"]:
                    freshness = "annotation_revision_changed_review_required"
            else:
                if captured_id is not None:
                    raise ClinicalSourceLinkError("Annotation binding has no manual source receipt")
                findings = [dict(finding) for finding in self.db.execute("""SELECT
                    finding_key,certainty,quote AS original_statement FROM assertions
                    WHERE case_id=? AND source_version_id=? AND source_line=? ORDER BY id""",
                    (case_id, source_id, row["source_line"])).fetchall()]
                if not findings:
                    raise ClinicalSourceLinkError("Linked source assertion is unavailable")
            if row["source_state"] != "current":
                freshness = "source_superseded_review_required"
            row["provenance_state"] = freshness
            row["clinical_review_state"] = "not_established_by_source_link"
            if include_findings:
                result.extend({**row, **finding} for finding in findings)
            else:
                result.append(row)
        return result

    def _annotate_provenance(self, case_id: str, assertions: list[dict],
                             sources: list[dict] | None = None) -> None:
        """Keep original transcription status on clinical source references.

        The same source owner supplies immutable receipts and PDF rendition
        anchors. Callers retain their existing transaction/read boundaries;
        this helper adds no record, interpretation or clinical approval.
        """
        receipts = self.sources._document_intake_receipts(case_id)
        provenance = {
            source_id: source_provenance({
                "document_intake": receipt, **classification_provenance(receipt),
            }) for source_id, receipt in receipts.items()
        }
        self.sources._annotate_source_assertions(assertions, receipts)
        for row in assertions:
            assertion_provenance(
                row, provenance.get(row["source_version_id"], {}), row["source_line"])
        for row in sources or []:
            source_id = row["source_version_id"]
            if source_id in receipts:
                row.update(provenance[source_id])
                row["document_intake"] = dict(receipts[source_id])

    def context_snapshot(self, patient_id: str, case_id: str, *,
                         actor: str, purpose: str) -> dict:
        """Read one authorized clinical/source context; never synthesize diagnosis.

        This is a *synthetic adapter projection*, not a complete Patient World
        Model, live Composer API or normalized duplicate store. It presents
        authoritative references, known original-source assertions, and
        review-required provenance links for a future governed interface.
        No clinical note narrative or source raw bytes are copied here.
        """
        self._allow(patient_id, case_id, actor=actor, purpose=purpose,
                    action="patient_context.read")
        if self.db.in_transaction:
            raise ClinicalSourceLinkError("Patient context requires isolated read")
        with self.db:
            self.db.execute("BEGIN")
            encounters = [
                dict(x) for x in self.db.execute(
                    """SELECT id,external_key,kind,service_date,status,revision
                       FROM clinical_encounters WHERE patient_id=?
                       ORDER BY service_date,id""", (patient_id,)
                ).fetchall()
            ]
            notes = [
                dict(x) for x in self.db.execute(
                    """SELECT v.id AS note_version_id,n.id AS note_id,
                              e.id AS encounter_id,v.version,v.status,v.sha256,
                              v.supersedes_id,v.created_at
                       FROM clinical_note_versions v
                       JOIN clinical_note_headers n ON n.id=v.note_id
                       JOIN clinical_encounters e ON e.id=n.encounter_id
                       WHERE e.patient_id=? ORDER BY v.id""", (patient_id,)
                ).fetchall()
            ]
            sources = [
                dict(x) for x in self.db.execute(
                    """SELECT id AS source_version_id,document_id,version,state,
                              sha256,kind,event_date,issued_at,received_at,
                              specimen_id,supersedes_id
                       FROM source_versions WHERE case_id=?
                       ORDER BY event_date,document_id,version""", (case_id,)
                ).fetchall()
            ]
            current_observations = [
                dict(x) for x in self.db.execute(
                    """SELECT a.source_version_id,a.source_line,a.finding_key,
                              a.certainty,a.quote
                       FROM assertions a JOIN source_versions s
                         ON s.id=a.source_version_id
                       WHERE a.case_id=? AND s.state='current'
                       ORDER BY a.id""", (case_id,)
                ).fetchall()
            ]
            self._annotate_provenance(case_id, current_observations, sources)
            link_fields = ("link_id", "note_version_id", "source_version_id", "source_line",
                           "source_state", "provenance_state", "annotation_capture_state") + PROVENANCE_FIELDS
            links = [{key: row[key] for key in link_fields if key in row}
                     for row in self._linked_sources(patient_id, case_id, include_findings=False)]
            return {
                "contract": "oi.synthetic-clinical-context/1",
                "patient_id": patient_id,
                "synthetic_case_id": case_id,
                "encounters": encounters,
                "note_versions": notes,
                "source_versions": sources,
                "source_reported_assertions": current_observations,
                "note_source_links": links,
                "note_versions_requiring_source_review": sorted({
                    link["note_version_id"] for link in links
                    if link["provenance_state"] != "current_source_unreviewed"
                }),
                "clinical_interpretation": "not_generated",
                "source_coverage": (
                    "source_linked_authored_and_manually_classified_observations"
                    if any("document_intake" in source for source in sources)
                    else "bounded_original_synthetic_reports_only"),
            }
