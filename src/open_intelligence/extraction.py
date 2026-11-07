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

from dataclasses import dataclass, field as dc_field

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


def validate_extraction_proposal(store, case_id, source_version_id, fields):
    """Validate an extraction proposal against the case ledger.

    The source version is proposal-level: it must be a positive integer
    id, exist, belong to ``case_id``, and be ``current``. A bad source
    drops every field with the same typed reason. Each field is then
    checked on its own: the finding key must match the ledger's key
    pattern, the certainty must be a known finding state, the quote must
    be present (1-1200 characters), the source line must be a positive
    integer, the key must not repeat inside the proposal, and the key
    must not already be asserted for this source version.
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
        "SELECT case_id, state FROM source_versions WHERE id=?",
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
    """Validate a proposal and store its kept fields as assertions.

    Dropped fields are reported in the returned validation, never stored.
    If the caller is already inside a write transaction (as the
    report-import path is), the inserts join that transaction; otherwise
    this function opens its own. Assertions are the stored form of an
    accepted extraction proposal — the same rows the import path has
    always written.
    """
    validation = validate_extraction_proposal(
        store, case_id, source_version_id, fields)
    if not validation.kept:
        return validation
    if store.db.in_transaction:
        validation.inserted_assertion_ids = _insert_assertions(
            store, case_id, source_version_id, validation.kept)
    else:
        with store.db:
            store.db.execute("BEGIN IMMEDIATE")
            validation.inserted_assertion_ids = _insert_assertions(
                store, case_id, source_version_id, validation.kept)
    return validation
