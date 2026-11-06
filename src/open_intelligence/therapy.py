"""T4 Line of therapy: the versioned-ruleset calculation (program plan
slice D3).

T4 counts lines of therapy from the case ledger — computed
deterministically, never by a model. A *line* is one regimen course:
the distinct therapy regimens a case received, in first-occurrence
order. The counting rule is a *versioned ruleset*: the ruleset version
comes from the case's vertical (``Vertical.lot_ruleset`` — the
oncology label is ``lot-rules-1``) and is recorded on every computed
row, so a ruleset change marks the rows computed under the old version
stale instead of silently reinterpreting them.

Rulesets are synthetic fixture rules, not guideline content — the
labels are opaque version strings and no guideline text is ingested
anywhere:

* ``lot-rules-1``: one line per distinct regimen key in
  first-occurrence order; a regimen that re-appears after a different
  regimen starts a NEW line (an interruption followed by a return is a
  new course).
* ``lot-rules-2``: one line per distinct regimen key in
  first-occurrence order; a regimen that re-appears after a different
  regimen RESUMES its earlier line (no new line).

An unknown ruleset label fails closed with
``unknown_ruleset_version`` — the toolset never silently applies one
version's rules under another version's label. A vertical whose
ruleset has no pinned entry here (cardiology's ``therapy-rules-1``)
is unknown until its ruleset is defined, and is reported as such.

Input contract: therapy regimens are named explicitly by the caller
(``therapy_finding_keys`` — the finding keys that denote therapy
regimens). The module never guesses from key names: the ledger holds
no administered-therapy table yet, so which keys are regimens is a
caller declaration, recorded in the computation. Only assertions with
certainty ``reported`` count as a regimen occurrence; a regimen key
asserted with any other certainty is listed as ``not_counted`` with
its certainty — a negative or pending state is never counted as a
received regimen.

This is not a RECIST calculator (program plan, per DEC-09-07): T4
counts regimen lines only. It never computes response, progression,
staging, grading, eligibility, or benefit, and no measurement is
compared here.

Persistence: ``record_therapy_lines`` writes one batch of rows to the
ledger's ``therapy_lines`` table (append-only; rows are never updated
or deleted). Recording marks the case's previous current rows stale —
reason ``ruleset_changed`` when their ruleset version differs from
the new batch, ``recomputed`` when the same version recomputes after
new evidence arrived. ``mark_therapy_lines_stale`` marks current rows
stale for a ruleset change without recomputing. Stale rows remain
readable history; ``therapy_lines`` returns current rows by default.
"""

from __future__ import annotations

from dataclasses import dataclass, field as dc_field
from datetime import datetime, timezone

from .store import KEY, InvalidInput
from .vertical import default_vertical


def _rule_v1(occurrences):
    """lot-rules-1: a re-appearing regimen starts a new line."""
    lines = []
    current_key = None
    for occurrence in occurrences:
        if occurrence["finding_key"] != current_key:
            lines.append({
                "line_number": len(lines) + 1,
                "regimen_key": occurrence["finding_key"],
                "first_occurred": occurrence["occurred"],
                "last_occurred": occurrence["occurred"],
            })
            current_key = occurrence["finding_key"]
        else:
            lines[-1]["last_occurred"] = occurrence["occurred"]
    return lines


def _rule_v2(occurrences):
    """lot-rules-2: a re-appearing regimen resumes its earlier line."""
    lines = []
    by_key = {}
    for occurrence in occurrences:
        if occurrence["finding_key"] not in by_key:
            line = {
                "line_number": len(lines) + 1,
                "regimen_key": occurrence["finding_key"],
                "first_occurred": occurrence["occurred"],
                "last_occurred": occurrence["occurred"],
            }
            lines.append(line)
            by_key[occurrence["finding_key"]] = line
        else:
            by_key[occurrence["finding_key"]]["last_occurred"] = occurrence["occurred"]
    return lines


#: Pinned synthetic rulesets: version label -> counting rule. The
#: labels are opaque strings from the vertical; the rules are fixture
#: logic, not guideline content.
LOT_RULESETS = {
    "lot-rules-1": _rule_v1,
    "lot-rules-2": _rule_v2,
}


def _now_utc() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


@dataclass
class TherapyLines:
    """Result of computing or recording therapy lines for one case.

    ``lines`` holds the computed lines in order. ``not_counted`` holds
    regimen-key assertions that did not count (non-``reported``
    certainty), with their reason. ``ruleset_version`` is the version
    that computed them. ``recorded_ids`` is filled in by
    :func:`record_therapy_lines` for the rows it stored.
    """

    case_id: str
    ruleset_version: str
    lines: list[dict] = dc_field(default_factory=list)
    not_counted: list[dict] = dc_field(default_factory=list)
    recorded_ids: list[int] = dc_field(default_factory=list)


def _resolve_ruleset(vertical, ruleset_version):
    """Resolve the ruleset version and rule, failing closed on unknown labels."""
    if ruleset_version is not None:
        if not isinstance(ruleset_version, str) or not ruleset_version:
            raise InvalidInput("ruleset_version must be a non-empty string")
        label = ruleset_version
    else:
        label = (vertical.lot_ruleset if vertical is not None
                 else default_vertical().lot_ruleset)
    rule = LOT_RULESETS.get(label)
    if rule is None:
        raise InvalidInput(f"unknown_ruleset_version: {label!r}")
    return label, rule


def _validate_regimen_keys(therapy_finding_keys):
    if not isinstance(therapy_finding_keys, (list, tuple)) \
            or not therapy_finding_keys:
        raise InvalidInput(
            "therapy_finding_keys must be a non-empty list of finding keys")
    keys = []
    for key in therapy_finding_keys:
        if not isinstance(key, str) or KEY.fullmatch(key) is None:
            raise InvalidInput(f"invalid therapy finding key: {key!r}")
        if key not in keys:
            keys.append(key)
    return tuple(keys)


def _occurrences(store, case_id, regimen_keys):
    """Regimen assertions on current sources, in timeline order."""
    placeholders = ",".join("?" for _ in regimen_keys)
    rows = [dict(row) for row in store.db.execute(
        f"""SELECT a.finding_key,a.certainty,a.source_version_id,
        s.event_date,s.issued_at,s.received_at,s.document_id,s.version
        FROM assertions a JOIN source_versions s ON s.id=a.source_version_id
        WHERE a.case_id=? AND s.state='current'
          AND a.finding_key IN ({placeholders})
        ORDER BY s.event_date,s.issued_at,s.received_at,
          s.document_id,s.version,s.id,a.finding_key""",
        (case_id, *regimen_keys)).fetchall()]
    counted = []
    not_counted = []
    for row in rows:
        entry = {
            "finding_key": row["finding_key"],
            "occurred": row["event_date"],
            "documented": row["issued_at"],
            "received": row["received_at"],
            "certainty": row["certainty"],
            "source_version_id": int(row["source_version_id"]),
            "document_id": row["document_id"],
            "version": int(row["version"]),
        }
        if row["certainty"] == "reported":
            counted.append(entry)
        else:
            not_counted.append({**entry, "reason": "not_reported_certainty"})
    return counted, not_counted


def compute_therapy_lines(store, case_id: str, therapy_finding_keys, *,
                          vertical=None, ruleset_version=None) -> TherapyLines:
    """Compute therapy lines for one case. Reads only; writes nothing."""
    if not isinstance(case_id, str) or not case_id:
        raise InvalidInput("case_id must be a non-empty string")
    label, rule = _resolve_ruleset(vertical, ruleset_version)
    regimen_keys = _validate_regimen_keys(therapy_finding_keys)
    with store.db:
        store.db.execute("BEGIN")
        case = store.db.execute(
            "SELECT case_id FROM cases WHERE case_id=?", (case_id,)).fetchone()
        if not case:
            raise InvalidInput("Unknown case")
        counted, not_counted = _occurrences(store, case_id, regimen_keys)
    return TherapyLines(case_id=case_id, ruleset_version=label,
                        lines=rule(counted), not_counted=not_counted)


def record_therapy_lines(store, case_id: str, therapy_finding_keys, *,
                         vertical=None, ruleset_version=None) -> TherapyLines:
    """Compute therapy lines and record the batch in the ledger.

    Previous current rows for the case are marked stale: reason
    ``ruleset_changed`` when their ruleset version differs from this
    batch, ``recomputed`` when the same version recomputes. The new
    batch is inserted as current.
    """
    result = compute_therapy_lines(
        store, case_id, therapy_finding_keys,
        vertical=vertical, ruleset_version=ruleset_version)
    computed_at = _now_utc()
    with store.db:
        store.db.execute("BEGIN IMMEDIATE")
        previous = store.db.execute(
            """SELECT id,ruleset_version FROM therapy_lines
            WHERE case_id=? AND state='current'""", (case_id,)).fetchall()
        for row in previous:
            reason = ("ruleset_changed" if row["ruleset_version"] != result.ruleset_version
                      else "recomputed")
            store.db.execute(
                "UPDATE therapy_lines SET state='stale',stale_reason=? WHERE id=?",
                (reason, row["id"]))
        for line in result.lines:
            cur = store.db.execute(
                """INSERT INTO therapy_lines
                (case_id,line_number,regimen_key,first_occurred,last_occurred,
                 ruleset_version,state,stale_reason,computed_at)
                VALUES (?,?,?,?,?,?,'current',NULL,?)""",
                (case_id, line["line_number"], line["regimen_key"],
                 line["first_occurred"], line["last_occurred"],
                 result.ruleset_version, computed_at))
            result.recorded_ids.append(int(cur.lastrowid))
    return result


def mark_therapy_lines_stale(store, case_id: str, ruleset_version: str) -> int:
    """Mark current rows stale for a ruleset change, without recomputing.

    Only rows computed under a different ruleset version are marked
    (reason ``ruleset_changed``); rows already under the given version
    stay current. Returns the number of rows marked.
    """
    if not isinstance(case_id, str) or not case_id:
        raise InvalidInput("case_id must be a non-empty string")
    if not isinstance(ruleset_version, str) or not ruleset_version:
        raise InvalidInput("ruleset_version must be a non-empty string")
    with store.db:
        store.db.execute("BEGIN IMMEDIATE")
        case = store.db.execute(
            "SELECT case_id FROM cases WHERE case_id=?", (case_id,)).fetchone()
        if not case:
            raise InvalidInput("Unknown case")
        cur = store.db.execute(
            """UPDATE therapy_lines SET state='stale',stale_reason='ruleset_changed'
            WHERE case_id=? AND state='current' AND ruleset_version!=?""",
            (case_id, ruleset_version))
        return int(cur.rowcount)


def therapy_lines(store, case_id: str, *, include_stale: bool = False) -> list[dict]:
    """Recorded therapy lines for one case, current first, in line order."""
    if not isinstance(case_id, str) or not case_id:
        raise InvalidInput("case_id must be a non-empty string")
    with store.db:
        store.db.execute("BEGIN")
        case = store.db.execute(
            "SELECT case_id FROM cases WHERE case_id=?", (case_id,)).fetchone()
        if not case:
            raise InvalidInput("Unknown case")
        query = """SELECT id,line_number,regimen_key,first_occurred,last_occurred,
            ruleset_version,state,stale_reason,computed_at FROM therapy_lines
            WHERE case_id=?"""
        if not include_stale:
            query += " AND state='current'"
        query += " ORDER BY line_number, id"
        return [dict(row) for row in store.db.execute(query, (case_id,)).fetchall()]
