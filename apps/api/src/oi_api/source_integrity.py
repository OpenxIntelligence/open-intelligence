"""Pure validation of stored PostgreSQL originals, using the source owner's parser."""

from __future__ import annotations

from collections import Counter, defaultdict
from collections.abc import Mapping, Sequence
from datetime import date, datetime
import hashlib
import re

from open_intelligence.store import MAX_SOURCE_BYTES, parse_report
from .laboratory_fhir_r4 import prepare_laboratory_bundle


class SourceIntegrityError(RuntimeError):
    """Stored source corruption; deliberately contains no original or DB details."""


def validate_snapshot(rows: Sequence[Mapping[str, object]], assertions: Sequence[tuple], *,
                      requested_case_id: str,
                      fhir_sources: Mapping[str, Mapping[str, object]] | None = None,
                      fhir_observations: Mapping[str, Sequence[Mapping[str, object]]] | None = None
                      ) -> dict[tuple[str, int], dict]:
    """Verify current finding tuples and return their explicit oncology attributions.

    Reuses the source owner's parser and exact-original checks. Historical bytes
    are checked too: an otherwise valid current amendment cannot hide corrupted
    originals or an incomplete version chain. No repair, normalization or new
    clinical assertion is performed here.
    """
    try:
        by_id = {row["source_id"]: row for row in rows}
        if len(by_id) != len(rows):
            raise ValueError()
        fhir_sources = dict(fhir_sources or {})
        fhir_observations = dict(fhir_observations or {})
        if (set(fhir_sources) - set(by_id)
                or set(fhir_observations) - set(fhir_sources)):
            raise ValueError()
        histories = defaultdict(list)
        expected = []
        oncology_by_line = {}
        for row in rows:
            source_id = row["source_id"]
            if source_id in fhir_sources:
                raw = validate_fhir_laboratory_original(
                    row, fhir_sources[source_id], fhir_observations.get(source_id, ()),
                    requested_case_id=requested_case_id,
                    predecessor=by_id.get(row["supersedes_id"]),
                )
            else:
                raw = validate_original(
                    row, requested_case_id=requested_case_id,
                    predecessor=by_id.get(row["supersedes_id"]),
                )
            histories[row["document_id"]].append(row)
            if row["state"] == "current" and source_id not in fhir_sources:
                for finding in parse_report(raw, allow_oncology=True).findings:
                    expected.append((source_id, finding.key, finding.state, finding.quote, finding.line))
                    if finding.oncology is not None:
                        oncology_by_line[(source_id, finding.line)] = {
                            "role": finding.oncology.role, "episode_id": finding.oncology.episode_id,
                        }
        for history in histories.values():
            if len({row["source_id"] in fhir_sources for row in history}) != 1:
                raise ValueError()
            history.sort(key=lambda row: row["version"])
            for version, row in enumerate(history, start=1):
                if (row["version"] != version
                        or row["state"] != ("current" if version == len(history) else "superseded")):
                    raise ValueError()
        # Counted equality catches missing/extra findings as well as changed
        # keys, states, quotations and literal line anchors.
        if Counter(expected) != Counter(tuple(assertion) for assertion in assertions):
            raise ValueError()
        return oncology_by_line
    except Exception:
        raise SourceIntegrityError("Stored source snapshot integrity check failed") from None


def validate_original(row: Mapping[str, object], *, requested_case_id: str,
                      predecessor: Mapping[str, object] | None = None) -> bytes:
    """Return the exact original after verifying context, hash and amendment lineage.

    ``event_date`` and ``issued_at`` must be datetime.date objects, as returned
    for PostgreSQL date columns by the existing driver; strings and datetime
    objects are not silently normalized. ``raw`` may be bytes, bytearray or a
    memoryview of bytea. All other input comes from the same source-owner row.

    For version > 1, the caller supplies the exact predecessor row with fields
    source_id, case_id, document_id, version, kind, event_date, specimen_id and
    state. This validates one amendment edge, not an entire reviewed history.
    Source freshness never establishes clinical review or source authenticity.
    """
    try:
        if not isinstance(row, Mapping):
            raise ValueError()
        for name in ("source_id", "case_id", "sha256", "document_id", "state", "kind"):
            if type(row[name]) is not str:
                raise ValueError()
        if (type(requested_case_id) is not str
                or re.fullmatch(r"CASE-[A-Z0-9-]{1,35}", requested_case_id) is None
                or row["case_id"] != requested_case_id
                or re.fullmatch(r"SRC-[0-9A-F]{32}", row["source_id"]) is None):
            raise ValueError()

        supplied = row["raw"]
        if not isinstance(supplied, (bytes, bytearray, memoryview)):
            raise ValueError()
        size = supplied.nbytes if isinstance(supplied, memoryview) else len(supplied)
        if not 1 <= size <= MAX_SOURCE_BYTES:
            raise ValueError()
        raw = bytes(supplied)
        if len(raw) != size or hashlib.sha256(raw).hexdigest() != row["sha256"]:
            raise ValueError()
        parsed = parse_report(raw, allow_oncology=True)
        if type(row["event_date"]) is not date or type(row["issued_at"]) is not date:
            raise ValueError()
        context = (row["case_id"], row["document_id"], row["kind"],
                   row["event_date"].isoformat(), row["issued_at"].isoformat(), row["specimen_id"])
        if context != (parsed.patient_id, parsed.document_id, parsed.kind,
                       parsed.event_date, parsed.issued_at, parsed.specimen_id):
            raise ValueError()
        version = row["version"]
        if type(version) is not int or version < 1 or row["state"] not in ("current", "superseded"):
            raise ValueError()

        if version == 1:
            if parsed.amends is not None or row["supersedes_id"] is not None or predecessor is not None:
                raise ValueError()
        else:
            supersedes_id = row["supersedes_id"]
            if (type(supersedes_id) is not str
                    or re.fullmatch(r"SRC-[0-9A-F]{32}", supersedes_id) is None
                    or supersedes_id == row["source_id"]
                    or parsed.amends != (row["document_id"], version - 1)
                    or not isinstance(predecessor, Mapping)):
                raise ValueError()
            if type(predecessor["version"]) is not int or type(predecessor["event_date"]) is not date:
                raise ValueError()
            previous = tuple(predecessor[name] for name in
                             ("source_id", "case_id", "document_id", "version", "kind",
                              "event_date", "specimen_id", "state"))
            expected = (supersedes_id, row["case_id"], row["document_id"], version - 1,
                        row["kind"], row["event_date"], row["specimen_id"], "superseded")
            if previous != expected:
                raise ValueError()
        return raw
    except Exception:
        # Callers map this stored-data failure to unavailability, not a request
        # validation error. Never expose parser text, SQL, originals or causes.
        raise SourceIntegrityError("Stored source integrity check failed") from None


def _instant(value: object) -> datetime:
    if isinstance(value, datetime) and value.tzinfo is not None and value.utcoffset() is not None:
        return value
    if type(value) is str:
        try:
            parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError:
            raise ValueError() from None
        if parsed.tzinfo is not None and parsed.utcoffset() is not None:
            return parsed
    raise ValueError()


def validate_fhir_laboratory_original(
        row: Mapping[str, object], metadata: Mapping[str, object],
        observations: Sequence[Mapping[str, object]], *,
        requested_case_id: str, predecessor: Mapping[str, object] | None = None) -> bytes:
    """Verify one FHIR laboratory source from immutable raw bytes and typed children."""
    try:
        if not isinstance(row, Mapping) or not isinstance(metadata, Mapping):
            raise ValueError()
        supplied = row["raw"]
        if not isinstance(supplied, (bytes, bytearray, memoryview)):
            raise ValueError()
        raw = bytes(supplied)
        if (not 1 <= len(raw) <= MAX_SOURCE_BYTES
                or hashlib.sha256(raw).hexdigest() != row["sha256"]
                or row["case_id"] != requested_case_id
                or row["kind"] != "laboratory"):
            raise ValueError()
        if (type(metadata.get("source_id")) is not str
                or metadata["source_id"] != row["source_id"]
                or type(metadata.get("subject_reference")) is not str):
            raise ValueError()
        prepared = prepare_laboratory_bundle(
            raw, expected_subject_reference=metadata["subject_reference"])
        if prepared.report_reference is None:
            raise ValueError()
        report_id = prepared.report_reference.split("/", 1)[1]
        specimen_id = prepared.specimen_reference.split("/", 1)[1]
        if (row["document_id"] != report_id or row["specimen_id"] != specimen_id
                or type(row["event_date"]) is not date or type(row["issued_at"]) is not date
                or row["event_date"].isoformat() != prepared.report_effective_at[:10]
                or row["issued_at"].isoformat() != prepared.report_issued_at[:10]):
            raise ValueError()

        exact_metadata = {
            "source_id": row["source_id"],
            "subject_reference": prepared.subject_reference,
            "specimen_reference": prepared.specimen_reference,
            "specimen_type_text": prepared.specimen_type_text,
            "specimen_collected_at": _instant(prepared.specimen_collected_at),
            "report_reference": prepared.report_reference,
            "report_effective_at": _instant(prepared.report_effective_at),
            "report_issued_at": _instant(prepared.report_issued_at),
            "fhir_release": "R4",
            "profile_contract": "oi.fhir-r4-laboratory-custody/1",
            "observation_count": len(prepared.observations),
        }
        for key, expected_value in exact_metadata.items():
            actual = metadata.get(key)
            if isinstance(expected_value, datetime):
                actual = _instant(actual)
            if actual != expected_value:
                raise ValueError()

        normalized = []
        for item in observations:
            if not isinstance(item, Mapping):
                raise ValueError()
            normalized.append({
                "reference": item["observation_reference"],
                "loinc_code": item["loinc_code"],
                "effective_at": _instant(item["effective_at"]),
                "issued_at": _instant(item["issued_at"]),
                "status": item["status"],
                "value_text": item["value_text"],
                "unit_code": item["unit_code"],
                "absent_reason": item["absent_reason"],
                "source_reported": item["source_reported"],
                "clinical_review": item["clinical_review"],
                "position": item["position"],
            })
        expected_observations = [{
            "reference": item["reference"], "loinc_code": item["loinc_code"],
            "effective_at": _instant(item["effective_at"]),
            "issued_at": _instant(item["issued_at"]), "status": item["status"],
            "value_text": item["value_text"], "unit_code": item["unit_code"],
            "absent_reason": item["absent_reason"], "source_reported": True,
            "clinical_review": "not_performed", "position": position,
        } for position, item in enumerate(prepared.observations, 1)]
        if normalized != expected_observations:
            raise ValueError()

        version = row["version"]
        if type(version) is not int or version < 1 or row["state"] not in ("current", "superseded"):
            raise ValueError()
        if version == 1:
            if row["supersedes_id"] is not None or predecessor is not None:
                raise ValueError()
        else:
            if not isinstance(predecessor, Mapping):
                raise ValueError()
            previous = tuple(predecessor[name] for name in
                             ("source_id", "case_id", "document_id", "version", "kind",
                              "event_date", "specimen_id", "state"))
            expected_previous = (
                row["supersedes_id"], row["case_id"], row["document_id"], version - 1,
                "laboratory", row["event_date"], row["specimen_id"], "superseded")
            if previous != expected_previous:
                raise ValueError()
        return raw
    except Exception:
        raise SourceIntegrityError("Stored FHIR laboratory integrity check failed") from None
