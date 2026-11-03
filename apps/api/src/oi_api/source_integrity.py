"""Pure validation of stored PostgreSQL originals, using the source owner's parser."""

from __future__ import annotations

from collections import Counter, defaultdict
from collections.abc import Mapping, Sequence
from datetime import date
import hashlib
import re

from open_intelligence.store import MAX_SOURCE_BYTES, parse_report


class SourceIntegrityError(RuntimeError):
    """Stored source corruption; deliberately contains no original or DB details."""


def validate_snapshot(rows: Sequence[Mapping[str, object]], assertions: Sequence[tuple], *,
                      requested_case_id: str) -> None:
    """Verify complete current finding tuples against the original source history.

    Reuses the source owner's parser and exact-original checks. Historical bytes
    are checked too: an otherwise valid current amendment cannot hide corrupted
    originals or an incomplete version chain. No repair, normalization or new
    clinical assertion is performed here.
    """
    try:
        by_id = {row["source_id"]: row for row in rows}
        if len(by_id) != len(rows):
            raise ValueError()
        histories = defaultdict(list)
        expected = []
        for row in rows:
            raw = validate_original(
                row, requested_case_id=requested_case_id,
                predecessor=by_id.get(row["supersedes_id"]),
            )
            histories[row["document_id"]].append(row)
            if row["state"] == "current":
                expected.extend((row["source_id"], finding.key, finding.state,
                                 finding.quote, finding.line)
                                for finding in parse_report(raw).findings)
        for history in histories.values():
            history.sort(key=lambda row: row["version"])
            for version, row in enumerate(history, start=1):
                if (row["version"] != version
                        or row["state"] != ("current" if version == len(history) else "superseded")):
                    raise ValueError()
        # Counted equality catches missing/extra findings as well as changed
        # keys, states, quotations and literal line anchors.
        if Counter(expected) != Counter(tuple(assertion) for assertion in assertions):
            raise ValueError()
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
        parsed = parse_report(raw)
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
