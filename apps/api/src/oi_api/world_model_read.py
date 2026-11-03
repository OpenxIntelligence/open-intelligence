"""Authorized H1 source-to-world-model projection over the ONE PostgreSQL source owner.

Reuses the first-party synthetic_world_model pure observation/conflict semantics
from the clinical reference branch. The CaseStore-shaped view exists *only in
memory* for that projector and uses ordinal IDs only there. No SQLite, second
patient record, copied clinical ledger, model execution, question/review write
or medical conclusion. All externally visible source IDs remain exact SRC-*.
"""
from __future__ import annotations

import hashlib
import json

from open_intelligence.patient_registry import (
    PatientRegistryDenied, PatientRegistryError, _key,
)
from open_intelligence.postgres_registry import PostgresPatientRegistry
from open_intelligence.store import InvalidInput, parse_report
from open_intelligence.world_model import synthetic_world_model

from .case_bindings import _case_id
from .sources import PostgresSourceVersions

MAX_VERSIONS = 128
MAX_ASSERTIONS = 512


class PostgresWorldModelRead:
    """One transactionally consistent source-derived, unreviewed projection."""

    def __init__(self, registry: PostgresPatientRegistry):
        if not isinstance(registry, PostgresPatientRegistry):
            raise TypeError("Canonical PostgreSQL patient registry required")
        self.registry = registry

    def read(self, patient_id: str, case_id: str, *, organization: str) -> dict:
        patient_id = _key(patient_id, "patient_id")
        case_id = _case_id(case_id)
        organization = _key(organization, "organization")
        with self.registry.transaction():
            # Holds the source owner's existing case-binding row lock. Source
            # import/amendment and binding revocation take that same row lock,
            # so this view cannot stitch two source generations together.
            PostgresSourceVersions(self.registry)._binding(
                patient_id, case_id, organization
            )
            source_rows = self.registry._fetchall(
                "SELECT source_id,document_id,version,sha256,raw,kind,"
                "event_date,issued_at,received_at,specimen_id,state,supersedes_id "
                "FROM clinical_source.source_versions WHERE case_id=%s "
                "ORDER BY document_id,version,source_id",
                (case_id,),
            )
            if len(source_rows) > MAX_VERSIONS:
                raise PatientRegistryError("Source projection exceeds bounded version limit")
            id_map = {row[0]: i + 1 for i, row in enumerate(source_rows)}
            if len(id_map) != len(source_rows):
                raise PatientRegistryError("Duplicate original source identity")
            reverse = {ordinal: sid for sid, ordinal in id_map.items()}
            internal_sources = []
            parsed_by_id = {}
            fingerprint_sources = []
            for (sid, doc, version, digest, raw, kind, event_date, issued_at,
                 received_at, specimen_id, state, supersedes_id) in source_rows:
                original = bytes(raw)
                if hashlib.sha256(original).hexdigest() != digest:
                    raise PatientRegistryError("Original source hash mismatch")
                try:
                    parsed = parse_report(original)
                except InvalidInput:
                    raise PatientRegistryError("Stored original failed source validation") from None
                if (parsed.patient_id != case_id or parsed.document_id != doc
                        or parsed.kind != kind or parsed.event_date != event_date.isoformat()
                        or parsed.issued_at != issued_at.isoformat()
                        or parsed.specimen_id != specimen_id or version < 1
                        or state not in ("current", "superseded")
                        or (supersedes_id is not None and supersedes_id not in id_map)):
                    raise PatientRegistryError("Original source metadata integrity mismatch")
                parsed_by_id[sid] = parsed
                internal_sources.append({
                    "id": id_map[sid], "document_id": doc, "version": version,
                    "sha256": digest, "kind": kind, "specimen_id": specimen_id,
                    "event_date": event_date.isoformat(),
                    "issued_at": issued_at.isoformat(),
                    "received_at": received_at.isoformat(),
                    "state": state,
                    "supersedes_id": id_map[supersedes_id] if supersedes_id else None,
                })
                fingerprint_sources.append([sid,doc,version,digest,state,supersedes_id])
            assertion_rows = self.registry._fetchall(
                "SELECT a.assertion_id,a.source_id,a.finding_key,a.certainty,"
                "a.quote,a.source_line FROM clinical_source.assertions a "
                "JOIN clinical_source.source_versions s ON s.source_id=a.source_id "
                "WHERE s.case_id=%s AND s.state='current' "
                "ORDER BY a.source_id,a.source_line,a.assertion_id",
                (case_id,),
            )
            if len(assertion_rows) > MAX_ASSERTIONS:
                raise PatientRegistryError("Source projection exceeds bounded assertion limit")
            internal_assertions = []
            fingerprint_assertions = []
            actual_by_source = {}
            for aid, sid, key, certainty, quote, line in assertion_rows:
                if sid not in id_map:
                    raise PatientRegistryError("Unexpected cross-case assertion")
                actual_by_source.setdefault(sid, []).append((key, certainty, quote, line))
                internal_assertions.append({
                    "id": aid, "source_version_id": id_map[sid],
                    "finding_key": key, "certainty": certainty,
                    "quote": quote, "source_line": line,
                })
                fingerprint_assertions.append([aid,sid,key,certainty,quote,line])
            # The source owner recorded explicit statement lines. Recompare
            # them to the literal parsed source bytes, not only DB assertions.
            for (sid, _, _, _, _, _, _, _, _, _, state, _) in source_rows:
                if state != "current":
                    continue
                expected = sorted(
                    (f.key, f.state, f.quote, f.line)
                    for f in parsed_by_id[sid].findings
                )
                observed = sorted(actual_by_source.get(sid, []))
                if expected != observed:
                    raise PatientRegistryError("Source quote/line provenance mismatch")

            # Existing first-party projector is a *pure function* over a
            # prepared canonical snapshot; it never writes to any store.
            snapshot = {
                "case": {"case_id": case_id},
                "sources": internal_sources,
                "assertions": internal_assertions,
                "questions": [], "snapshots": [], "events": [],
            }
            try:
                core = synthetic_world_model(snapshot, case_id)
            except (InvalidInput, KeyError, TypeError, ValueError):
                raise PatientRegistryError("World Model source projection rejected input") from None

            def source_view(row):
                return {
                    **row,
                    "source_version_id": reverse[row["source_version_id"]],
                    "supersedes_source_id": (
                        reverse[row["supersedes_source_id"]]
                        if row["supersedes_source_id"] is not None else None
                    ),
                }

            def observation(row):
                return {**row, "source_version_id": reverse[row["source_version_id"]]}

            def conflict(row):
                return {
                    **row,
                    "observation_refs": [
                        {**ref, "source_version_id": reverse[ref["source_version_id"]]}
                        for ref in row["observation_refs"]
                    ],
                }

            checksum = hashlib.sha256(json.dumps(
                [fingerprint_sources, fingerprint_assertions],
                sort_keys=True, separators=(",", ":"), ensure_ascii=False,
            ).encode("utf-8")).hexdigest()
            # Never leak the surrogate integer IDs or the original clinical
            # reference project's unpopulated question/review status.
            return {
                "contract": "oi.synthetic-postgres-world-model-sources/1",
                "synthetic": True,
                "patient_id": patient_id, "case_id": case_id,
                "source_snapshot_sha256": checksum,
                "authority": "source_report_only_unreviewed",
                "clinical_interpretation": "not_generated",
                "clinical_approval": False,
                "review_workflow_connected": False,
                "summary": core["summary"],
                "current_sources": [source_view(s) for s in core["current_sources"]],
                "history": [source_view(s) for s in core["history"]],
                "observations": [observation(o) for o in core["observations"]],
                "unresolved": [observation(o) for o in core["unresolved"]],
                "conflicts": [conflict(c) for c in core["conflicts"]],
                "limitations": [
                    "Only current authored fictional source statements; not medical facts.",
                    "No inference of diagnosis, progression, treatment response or eligibility.",
                    "Question, Composer, biomedical rights and durable review are not yet connected to this PostgreSQL view.",
                    "No real identity verification, clinical authorization, consent or PHI use.",
                ],
            }
