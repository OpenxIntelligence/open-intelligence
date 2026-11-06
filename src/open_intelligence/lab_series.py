"""T2 Lab/marker series: deterministic numeric series from lab assertions
(program plan slice D3).

T2 turns a case's laboratory assertions into numeric series — one per
analyte — computed deterministically, never by a model. An analyte is a
finding key asserted on a current ``laboratory``-kind source version;
the ledger, not a key-name guess, decides what is a lab finding.

Number parsing is strict and fail-closed. A quote is parsed only when
it contains exactly one number:

* exactly one number -> a parseable point (value + the unit token that
  follows it, if any; a missing unit is recorded as ``unit_not_stated``,
  never guessed);
* zero numbers -> the point is ``unparseable`` (listed with its quote,
  never silently dropped, never given a value);
* more than one number -> the point is ``ambiguous`` (listed, never
  guessed — the toolset cannot know which number is the measurement).

Deltas are arithmetic between consecutive parseable points: absolute
difference and percent change. A delta is computed only when the two
points carry the same unit; a unit change is reported as
``unit_mismatch`` and no delta is computed across it. A percent change
is undefined when the earlier value is zero (``percent_undefined``).
No trend word ("rising", "falling", "improving") is ever attached —
trend views are slice D4's work; T2 reports points and deltas only.

Terminology codings are enrichment, not input: when a ``codings_for``
callable is supplied (the D2 ``terminology.codings_for`` signature —
vertical first, then shared modality packs), each analyte carries its
codings; a key with no binding is listed as ``unbound``, never given a
fabricated code. Without a callable the series is still computed and
every analyte is ``unbound``.

Cross-specimen series consult the specimen chain the way D1's note
requires: when consecutive points come from different specimens and a
``validate_chain`` callable is supplied (the D1
``specimen_chain.validate_specimen_chain`` signature), the toolset
consults it for every biological asset anchored to either point's
source version and records any break on the transition. When no
validator is supplied the transition is recorded as
``chain_not_checked``; when no asset anchors either source it is
recorded as ``no_anchored_assets``. A break never silently blocks the
series — it is a typed record on the transition.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field as dc_field

from .store import InvalidInput

_NUMBER_RE = re.compile(r"-?\d+(?:\.\d+)?")
_UNIT_RE = re.compile(r"[A-Za-z][A-Za-z/%^0-9.\u00b5\u03bc-]*\Z")


def _parse_quote(quote: str) -> dict:
    """Parse one lab quote into a value, a unit, or a typed failure."""
    numbers = _NUMBER_RE.findall(quote)
    if not numbers:
        return {"parse_status": "unparseable", "value": None, "unit": None}
    if len(numbers) > 1:
        return {"parse_status": "ambiguous", "value": None, "unit": None}
    raw = numbers[0]
    rest = quote[quote.index(raw) + len(raw):].strip()
    unit = None
    if rest:
        token = rest.split()[0].rstrip(".,;")
        if _UNIT_RE.fullmatch(token):
            unit = token
    return {
        "parse_status": "parseable",
        "value": float(raw),
        "unit": unit if unit is not None else "unit_not_stated",
    }


@dataclass
class LabSeries:
    """One case's lab series, read from the ledger.

    ``series`` maps each analyte finding key to its ordered points and
    deltas. ``unbound`` lists analyte keys with no terminology coding.
    ``chain_transitions`` records the specimen-chain status of every
    cross-specimen transition in every series.
    """

    case_id: str
    series: dict[str, dict] = dc_field(default_factory=dict)
    unbound: list[str] = dc_field(default_factory=list)
    chain_transitions: list[dict] = dc_field(default_factory=list)


def _chain_status(store, case_id, source_a, source_b, validate_chain):
    """Chain status for a transition between two source versions.

    Returns a dict with ``checked`` and either ``breaks`` (typed records)
    or a ``reason`` (``no_chain_validator`` / ``no_anchored_assets``).
    """
    if validate_chain is None:
        return {"checked": False, "reason": "no_chain_validator", "breaks": []}
    asset_pks = []
    for source_id in (source_a, source_b):
        rows = store.db.execute(
            "SELECT id FROM biological_assets WHERE anchor_source_version_id=?",
            (source_id,)).fetchall()
        asset_pks.extend(int(row["id"]) for row in rows)
    if not asset_pks:
        return {"checked": False, "reason": "no_anchored_assets", "breaks": []}
    breaks = []
    for asset_pk in sorted(set(asset_pks)):
        validation = validate_chain(store, case_id, asset_pk)
        breaks.extend(dict(b) for b in validation.breaks)
    return {"checked": True, "reason": None, "breaks": breaks}


def lab_series(store, case_id: str, *, codings_for=None, vertical=None,
               validate_chain=None) -> LabSeries:
    """Build the lab series for one case. Reads only; writes nothing."""
    if not isinstance(case_id, str) or not case_id:
        raise InvalidInput("case_id must be a non-empty string")
    if codings_for is not None and not callable(codings_for):
        raise InvalidInput("codings_for must be a callable")
    if validate_chain is not None and not callable(validate_chain):
        raise InvalidInput("validate_chain must be a callable")
    with store.db:
        store.db.execute("BEGIN")
        case = store.db.execute(
            "SELECT case_id FROM cases WHERE case_id=?", (case_id,)).fetchone()
        if not case:
            raise InvalidInput("Unknown case")
        rows = [dict(row) for row in store.db.execute(
            """SELECT a.finding_key,a.certainty,a.quote,a.source_line,
            a.source_version_id,s.event_date,s.issued_at,s.received_at,
            s.document_id,s.version,s.specimen_id
            FROM assertions a JOIN source_versions s
              ON s.id=a.source_version_id
            WHERE a.case_id=? AND s.state='current' AND s.kind='laboratory'
            ORDER BY s.event_date,s.issued_at,s.received_at,
              s.document_id,s.version,s.id,a.finding_key""",
            (case_id,)).fetchall()]
    grouped: dict[str, list[dict]] = {}
    for row in rows:
        parsed = _parse_quote(row["quote"])
        grouped.setdefault(row["finding_key"], []).append({
            "occurred": row["event_date"],
            "documented": row["issued_at"],
            "received": row["received_at"],
            "certainty": row["certainty"],
            "source_version_id": int(row["source_version_id"]),
            "document_id": row["document_id"],
            "version": int(row["version"]),
            "specimen_id": row["specimen_id"],
            "quote": row["quote"],
            "source_line": int(row["source_line"]),
            **parsed,
        })
    series: dict[str, dict] = {}
    unbound: list[str] = []
    chain_transitions: list[dict] = []
    for key in sorted(grouped):
        points = grouped[key]
        codings = ()
        if codings_for is not None:
            codings = tuple(dict(c) for c in codings_for(key, vertical))
        if not codings:
            unbound.append(key)
        deltas = []
        for earlier, later in zip(points, points[1:]):
            if earlier["specimen_id"] != later["specimen_id"]:
                status = _chain_status(
                    store, case_id, earlier["source_version_id"],
                    later["source_version_id"], validate_chain)
                chain_transitions.append({
                    "finding_key": key,
                    "from_specimen_id": earlier["specimen_id"],
                    "to_specimen_id": later["specimen_id"],
                    "from_source_version_id": earlier["source_version_id"],
                    "to_source_version_id": later["source_version_id"],
                    **status,
                })
            if (earlier["parse_status"] != "parseable"
                    or later["parse_status"] != "parseable"):
                continue
            if earlier["unit"] != later["unit"]:
                deltas.append({
                    "from_occurred": earlier["occurred"],
                    "to_occurred": later["occurred"],
                    "delta_status": "unit_mismatch",
                    "from_unit": earlier["unit"],
                    "to_unit": later["unit"],
                    "absolute": None,
                    "percent": None,
                })
                continue
            absolute = later["value"] - earlier["value"]
            percent = (None if earlier["value"] == 0 else
                       absolute / earlier["value"] * 100.0)
            deltas.append({
                "from_occurred": earlier["occurred"],
                "to_occurred": later["occurred"],
                "delta_status": ("percent_undefined" if percent is None
                                 else "computed"),
                "from_unit": earlier["unit"],
                "to_unit": later["unit"],
                "absolute": absolute,
                "percent": percent,
            })
        series[key] = {
            "finding_key": key,
            "codings": list(codings),
            "points": points,
            "deltas": deltas,
        }
    chain_transitions.sort(key=lambda t: (t["finding_key"],
                                          t["from_source_version_id"],
                                          t["to_source_version_id"]))
    return LabSeries(case_id=case_id, series=series, unbound=sorted(unbound),
                     chain_transitions=chain_transitions)
