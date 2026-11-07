"""A1 Intake & Extraction: the deterministic anchor checker (program plan slice D1; Notion OI-09 section 5).

A1 is proposals only: an arriving record becomes an extraction proposal --
a list of fields, each naming a finding key, a certainty, a verbatim quote,
and the exact source line it came from. This module is the one anchor
checker every proposal passes before its fields become stored assertions:
no field is stored without a source version that exists, belongs to the
case, and is current, plus an exact anchor (quote + source line).

A proposal is validated, never silently repaired: each field is kept or
dropped with a typed reason, in the same kept/dropped shape as the
structural validator (``investigation.validate_output``). The
report-import path (``store._import_report_in_transaction``) routes its
parsed findings through this checker, so the checker is on the live
arrival path; PDF, C-CDA, and FHIR arrivals route through it as their
import paths land. Modality schema packs are out of scope for D1 (they
arrive with D2).
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass, field as dc_field
from uuid import uuid4

from .store import InvalidInput, KEY, STATES

QUOTE_MAX_LENGTH = 1200


@dataclass
class ExtractionValidation:
    """Result of validating one extraction proposal.

    ``kept`` holds the normalized fields, each with ``finding_key``,
    ``certainty``, ``quote`` (stripped), and ``source_line``. ``dropped``
    holds one entry per rejected field, each with the original ``field``,
    a typed ``reason``, and ``check`` (always ``"A1"``).
    ``inserted_assertion_ids`` is filled in by
    :func:`record_extraction_proposal` for the fields it stored; it stays
    empty for a validation-only call.
    """

    case_id: str
    source_version_id: int
    kept: list[dict] = dc_field(default_factory=list)
    dropped: list[dict] = dc_field(default_factory=list)
    inserted_assertion_ids: list[int] = dc_field(default_factory=list)


def _drop(field, reason):
    return {"field": field, "reason": reason, "check": "A1"}


def validate_extraction_proposal(store, case_id, source_version_id, fields, *,
                                 verified_source_anchors=None):
    """Validate an extraction proposal against the case ledger.

    The source version is proposal-level: it must be a positive integer
    id, exist, belong to ``case_id``, and be ``current``. A bad source
    drops every field with the same typed reason. Each field is then
    checked against the immutable original's SHA-256 and its literal
    text line before it may become an assertion. A FHIR source's narrative
    is not on its resource ID line: the caller must supply bindings from
    a freshly verified parser of those original bytes. Without such
    bindings, a FHIR proposal fails closed instead of guessing anchors.
    The key must not repeat or already exist on the source version.

    A validation-only result is provisional and does not reserve a write.
    Persistence must validate again inside its owning write transaction.
    """
    if not isinstance(case_id, str) or not case_id:
        raise InvalidInput("case_id must be a non-empty string")
    if not isinstance(fields, (list, tuple)):
        raise InvalidInput("fields must be a list of extraction fields")
    if type(source_version_id) is not int or source_version_id < 1:
        return ExtractionValidation(
            case_id, source_version_id, [],
            [_drop(item, "invalid_source_version_id") for item in fields])
    row = store.db.execute(
        "SELECT case_id, state, kind, raw, sha256 FROM source_versions WHERE id=?",
        (source_version_id,)).fetchone()
    if row is None:
        reason = "unknown_source_version"
    elif row["case_id"] != case_id:
        reason = "wrong_case_source_version"
    elif row["state"] != "current":
        reason = "superseded_source_version"
    else:
        reason = None
    if reason is not None:
        return ExtractionValidation(
            case_id, source_version_id, [],
            [_drop(item, reason) for item in fields])
    original = row["raw"]
    if (not isinstance(original, bytes) or
            hashlib.sha256(original).hexdigest() != row["sha256"]):
        return ExtractionValidation(
            case_id, source_version_id, [],
            [_drop(item, "source_integrity_mismatch") for item in fields])
    source_lines = None
    if row["kind"] != "fhir-bundle":
        try:
            source_lines = original.decode("utf-8", errors="strict").splitlines()
        except UnicodeDecodeError:
            return ExtractionValidation(
                case_id, source_version_id, [],
                [_drop(item, "source_text_unavailable") for item in fields])
    # FHIR bindings are produced by the existing source parser, not by
    # caller-provided field text. Unknown or unverified anchors fail closed.
    fhir_bindings = (set(verified_source_anchors)
                     if verified_source_anchors is not None else None)
    validation = ExtractionValidation(case_id, source_version_id)
    seen_keys = set()
    for item in fields:
        if not isinstance(item, dict):
            validation.dropped.append(_drop(item, "malformed_field"))
            continue
        key = item.get("finding_key")
        if not isinstance(key, str) or not KEY.fullmatch(key):
            validation.dropped.append(_drop(item, "invalid_finding_key"))
            continue
        certainty = item.get("certainty")
        if not isinstance(certainty, str) or certainty not in STATES:
            validation.dropped.append(_drop(item, "invalid_certainty"))
            continue
        quote = item.get("quote")
        if not isinstance(quote, str) or not quote.strip():
            validation.dropped.append(_drop(item, "missing_quote"))
            continue
        if len(quote.strip()) > QUOTE_MAX_LENGTH:
            validation.dropped.append(_drop(item, "quote_too_long"))
            continue
        line = item.get("source_line")
        if type(line) is not int or line < 1:
            validation.dropped.append(_drop(item, "invalid_source_line"))
            continue
        if key in seen_keys:
            validation.dropped.append(_drop(item, "duplicate_finding_key"))
            continue
        already = store.db.execute(
            "SELECT 1 FROM assertions WHERE source_version_id=? AND finding_key=?",
            (source_version_id, key)).fetchone()
        if already is not None:
            validation.dropped.append(
                _drop(item, "finding_already_asserted"))
            continue
        normalized_quote = quote.strip()
        if row["kind"] == "fhir-bundle":
            if fhir_bindings is None:
                validation.dropped.append(_drop(item, "source_anchor_not_verified"))
                continue
            if (key, normalized_quote, line) not in fhir_bindings:
                validation.dropped.append(_drop(item, "source_anchor_mismatch"))
                continue
        elif line > len(source_lines):
            validation.dropped.append(_drop(item, "source_line_out_of_range"))
            continue
        elif normalized_quote not in source_lines[line - 1]:
            validation.dropped.append(_drop(item, "source_quote_mismatch"))
            continue
        seen_keys.add(key)
        validation.kept.append({
            "finding_key": key,
            "certainty": certainty,
            "quote": quote.strip(),
            "source_line": line,
        })
    return validation


def _insert_assertions(store, case_id, source_version_id, kept):
    """Insert kept fields as assertions. Caller owns the transaction."""
    ids = []
    for item in kept:
        cur = store.db.execute(
            """INSERT INTO assertions
                (case_id,source_version_id,finding_key,certainty,quote,source_line)
                VALUES (?,?,?,?,?,?)""",
            (case_id, source_version_id, item["finding_key"],
             item["certainty"], item["quote"], item["source_line"]))
        ids.append(int(cur.lastrowid))
    return ids


def record_extraction_proposal(store, case_id, source_version_id, fields):
    """Validate and store a proposal in one owning write transaction.

    Dropped fields are reported in the returned validation, never stored.
    Standalone calls reserve the writer before checking source freshness,
    original integrity, or duplicate keys, so another writer cannot change
    those facts between validation and insertion. The whole standalone
    batch commits or rolls back together.

    When the caller already owns a transaction, a nested savepoint makes
    this batch atomic without committing or rolling back the caller's
    earlier work. Database-level transaction rollback still takes precedence;
    its original error is preserved. A validation-only call remains read-only
    and cannot authorize a later insert without repeating these checks.
    """
    def validate_and_insert():
        validation = validate_extraction_proposal(
            store, case_id, source_version_id, fields)
        if validation.kept:
            validation.inserted_assertion_ids = _insert_assertions(
                store, case_id, source_version_id, validation.kept)
        return validation

    if store.db.in_transaction:
        # The generated SQL identifier contains only a fixed prefix and hex.
        # A distinct name leaves any caller-owned savepoints untouched.
        savepoint = f"oi_extraction_{uuid4().hex}"
        store.db.execute(f"SAVEPOINT {savepoint}")
        try:
            validation = validate_and_insert()
            store.db.execute(f"RELEASE SAVEPOINT {savepoint}")
        except BaseException:
            # RAISE(ROLLBACK) and some engine failures end the entire outer
            # transaction. Do not mask that error with a missing-savepoint
            # error or try to recreate work the database already rolled back.
            if store.db.in_transaction:
                store.db.execute(f"ROLLBACK TO SAVEPOINT {savepoint}")
                store.db.execute(f"RELEASE SAVEPOINT {savepoint}")
            raise
        return validation
    with store.db:
        store.db.execute("BEGIN IMMEDIATE")
        return validate_and_insert()
