"""D4 patient analytics: lab trends, symptom progression, record
completeness, outcomes tracking (program plan slice D4, design-first).

Design (drafted first, in this docstring and in the D4 section of
``docs/IMPLEMENTATION_STATUS.md``; the build implements exactly this
design and the draft PR is the vehicle for its correction):

The record becomes longitudinal understanding, not just a list. All
four views are read-only derivations of stored data — they never
re-derive workflow state, never write, and never call a model. Each
view says what the record shows and names what it cannot show; a
missing element is flagged as missing, never filled in.

* Lab trends build on the T2 lab series (slice D3): one trend per
  analyte, computed from the T2 points. The trend function takes the
  T2 series as a plain mapping (the ``dataclasses.asdict`` shape of a
  T2 ``LabSeries``) — it never imports the T2 module, so the
  import-graph tripwire stays green and the caller wires the two
  together. A trend is computed over the longest run of consecutive
  parseable points sharing one unit; unparseable, ambiguous, and
  unit-changed points are listed as excluded with their reason, never
  silently dropped. The trend word is direction only —
  ``rising`` / ``falling`` / ``stable`` — from the first-to-last value
  of the run: |percent| >= 1% rises or falls, |percent| < 1% is
  stable. The 1% band is a pinned display convention, recorded here:
  it exists only so floating-point dust does not read as a trend; it
  is not a clinical threshold. Direction follows numeric value change,
  including negative baselines; percent retains the signed-baseline
  arithmetic convention. No improvement/worsening claim is
  ever attached. A zero first value leaves the percent undefined
  (``undefined_zero_baseline``) and the direction follows the sign of
  the last value. Fewer than two same-unit parseable points is
  ``not_computable`` with reason ``insufficient_points``.
* Symptom progression reads the patient's own symptom notes
  (``patient_notes`` kind ``symptom``), verbatim, in noted-date order.
  Progression here is an ordered record plus two markers: ``repeat``
  when the exact text was noted before (a persisting report) and
  ``amended`` when the wording changed (earlier versions preserved
  alongside). Recurrence is exact-text only — a reworded repeat is a
  new first report of different wording, never silently merged. No
  severity is ever scored and no improvement or worsening is ever
  inferred: the record holds no severity data, so none is invented.
* Record completeness is a pinned checklist: each item names what it
  is, whether it is present, how many there are, and what it enables.
  The checklist is this module's own convention — it is derived from
  what the platform's views need (labs for trends, sources for the
  longitudinal picture, therapy lines for outcomes tracking), not from
  any clinical guideline. A missing item is listed as missing with
  what it blocks.
* Outcomes tracking assembles the current state of each
  outcome-bearing record — therapy lines (current vs stale, by
  ruleset), patient goals (current status + version history), and
  follow-through tasks (counts by status, overdue only when the
  caller supplies ``today``). Every value is a recorded state; no
  response, progression, benefit, or eligibility claim is ever made
  — a therapy line is a regimen course, a goal status is the
  patient's own recorded status, a completed task is a completed
  task, nothing more.

Hard limits: no model call exists anywhere in this module (an AST
test pins that); no dimension module is imported (the T2 series
arrives as data, the chain validator and terminology bindings are
not needed here — trends need points, not codings); no vertical
predicate is read or moved. The module reads only the ledger and
the store's own list methods. Dates are YYYY-MM-DD strings, ordered
lexicographically, exactly as the rest of the ledger does.
"""

from __future__ import annotations

from .store import InvalidInput, valid_date

# Pinned display convention for lab trends: |percent| below this band
# reads as stable. It exists only so floating-point dust does not read
# as a trend; it is not a clinical threshold.
STABLE_BAND_PERCENT = 1.0


def _require_case(store, case_id: str) -> None:
    """Raise unless the case exists. Reads only."""
    if not isinstance(case_id, str) or not case_id:
        raise InvalidInput("case_id must be a non-empty string")
    with store.db:
        store.db.execute("BEGIN")
        row = store.db.execute(
            "SELECT case_id FROM cases WHERE case_id=?", (case_id,)).fetchone()
    if not row:
        raise InvalidInput("Unknown case")


def _check_today(today):
    """Validate an optional YYYY-MM-DD ``today``; None means not supplied."""
    if today is None:
        return None
    if not isinstance(today, str) or valid_date(today) is None:
        raise InvalidInput("today must use YYYY-MM-DD")
    return today


# ---------------------------------------------------------------------------
# Lab trends (over a T2 lab series, supplied as a plain mapping)
# ---------------------------------------------------------------------------

def _trend_runs(points):
    """Split ordered points into maximal same-unit parseable runs.

    Returns (runs, excluded): runs is a list of point lists; excluded
    is a list of {occurred, reason, quote} for points that cannot join
    any run (unparseable / ambiguous) — a unit change closes the
    current run and starts a new one, so it excludes nothing by
    itself.
    """
    runs: list[list[dict]] = []
    excluded: list[dict] = []
    current: list[dict] = []
    current_unit = None
    for point in points:
        if point.get("parse_status") != "parseable":
            if current:
                runs.append(current)
                current = []
                current_unit = None
            excluded.append({
                "occurred": point.get("occurred"),
                "reason": point.get("parse_status") or "unparseable",
                "quote": point.get("quote"),
            })
            continue
        unit = point.get("unit")
        if current and unit != current_unit:
            runs.append(current)
            current = []
        current.append(point)
        current_unit = unit
    if current:
        runs.append(current)
    return runs, excluded


def _direction_changes(run):
    """Sign changes among consecutive non-zero differences in a run."""
    signs = []
    for earlier, later in zip(run, run[1:]):
        diff = later["value"] - earlier["value"]
        if diff > 0:
            signs.append(1)
        elif diff < 0:
            signs.append(-1)
    changes = 0
    for first, second in zip(signs, signs[1:]):
        if first != second:
            changes += 1
    return changes


def _one_trend(finding_key, points):
    """One analyte's trend from its ordered T2 points."""
    runs, excluded = _trend_runs(points)
    usable = [run for run in runs if len(run) >= 2]
    if not usable:
        # Every point must remain inspectable even when no run can be used.
        for run in runs:
            excluded.extend({"occurred": p.get("occurred"),
                             "reason": "insufficient_points",
                             "quote": p.get("quote")} for p in run)
        excluded.sort(key=lambda e: (e["occurred"] or "", e["reason"]))
        return {
            "finding_key": finding_key,
            "trend": "not_computable",
            "trend_reason": "insufficient_points",
            "unit": None,
            "first_value": None,
            "last_value": None,
            "first_occurred": None,
            "last_occurred": None,
            "percent_change": None,
            "percent_status": "not_computed",
            "points_used": 0,
            "points_total": len(points),
            "direction_changes": 0,
            "monotone": False,
            "excluded_points": excluded,
        }
    # Longest run wins; ties go to the earliest run.
    best_len = max(len(r) for r in usable)
    run = min((r for r in usable if len(r) == best_len),
              key=lambda r: r[0].get("occurred") or "")
    first, last = run[0], run[-1]
    if first["value"] == 0:
        if last["value"] == 0:
            trend, percent, percent_status = "stable", 0.0, "computed"
        else:
            trend = "rising" if last["value"] > 0 else "falling"
            percent, percent_status = None, "undefined_zero_baseline"
    else:
        percent = (last["value"] - first["value"]) / first["value"] * 100.0
        percent_status = "computed"
        if abs(percent) < STABLE_BAND_PERCENT:
            trend = "stable"
        elif last["value"] > first["value"]:
            trend = "rising"
        else:
            trend = "falling"
    used_ids = {id(point) for point in run}
    excluded_points = list(excluded)
    for point in points:
        if id(point) in used_ids:
            continue
        if point.get("parse_status") != "parseable":
            continue  # already listed above
        reason = ("unit_change" if point.get("unit") != run[0].get("unit")
                  else "shorter_run")
        excluded_points.append({
            "occurred": point.get("occurred"),
            "reason": reason,
            "quote": point.get("quote"),
        })
    excluded_points.sort(key=lambda e: (e["occurred"] or "", e["reason"]))
    return {
        "finding_key": finding_key,
        "trend": trend,
        "trend_reason": None,
        "unit": run[0].get("unit"),
        "first_value": first["value"],
        "last_value": last["value"],
        "first_occurred": first.get("occurred"),
        "last_occurred": last.get("occurred"),
        "percent_change": percent,
        "percent_status": percent_status,
        "points_used": len(run),
        "points_total": len(points),
        "direction_changes": _direction_changes(run),
        "monotone": _direction_changes(run) == 0,
        "excluded_points": excluded_points,
    }


def lab_trends(series) -> dict:
    """Lab-trend views over a T2 lab series supplied as a plain mapping.

    ``series`` is the ``dataclasses.asdict`` shape of a T2
    ``LabSeries``: {"case_id", "series": {key: {"points": [...]}},
    ...}. Only the points are read. Returns {"case_id", "trends",
    "analytes_with_trend", "analytes_not_computable"}.
    """
    if not isinstance(series, dict) or not isinstance(series.get("series"), dict):
        raise InvalidInput("lab series must be a T2 LabSeries mapping")
    case_id = series.get("case_id")
    if not isinstance(case_id, str) or not case_id:
        raise InvalidInput("lab series must carry a case_id")
    trends = {}
    for key in sorted(series["series"]):
        analyte = series["series"][key]
        if not isinstance(analyte, dict) or not isinstance(
                analyte.get("points"), list):
            raise InvalidInput("lab series analyte must carry points")
        trends[key] = _one_trend(key, analyte["points"])
    return {
        "case_id": case_id,
        "trends": trends,
        "analytes_with_trend": sum(
            1 for t in trends.values() if t["trend"] != "not_computable"),
        "analytes_not_computable": sorted(
            key for key, t in trends.items() if t["trend"] == "not_computable"),
    }


# ---------------------------------------------------------------------------
# Symptom progression (patient-reported notes, verbatim)
# ---------------------------------------------------------------------------

def symptom_progression(store, case_id: str) -> dict:
    """Symptom progression: ordered symptom notes + recurrence markers.

    Reads ``store.patient_notes`` and keeps kind ``symptom`` only, in
    noted-date order. Each entry carries its verbatim text, whether
    the exact text was noted before (``repeat`` — a persisting
    report) or is new (``first_report``), and whether the wording was
    amended (earlier versions preserved alongside). No severity is
    scored and no improvement or worsening is inferred.
    """
    _require_case(store, case_id)
    notes = [n for n in store.patient_notes(case_id) if n["kind"] == "symptom"]
    entries = []
    seen_texts: set[str] = set()
    for note in sorted(notes, key=lambda n: (
            (n["current"] or {}).get("noted_date") or "",
            n["note_id"])):
        current = note["current"] or {}
        text = current.get("note_text")
        recurrence = "repeat" if text in seen_texts else "first_report"
        seen_texts.add(text)
        versions = note.get("versions") or []
        entries.append({
            "note_id": note["note_id"],
            "noted_date": current.get("noted_date"),
            "note_text": text,
            "recurrence": recurrence,
            "amended": len(versions) > 1,
            "version": current.get("version"),
            "previous_versions": [
                {"version": v.get("version"),
                 "noted_date": v.get("noted_date"),
                 "note_text": v.get("note_text")}
                for v in versions if v.get("record_state") == "superseded"
            ],
        })
    return {
        "case_id": case_id,
        "status": "has_symptom_notes" if entries else "no_symptom_notes",
        "notes": entries,
        "note_count": len(entries),
        "repeat_count": sum(1 for e in entries if e["recurrence"] == "repeat"),
    }


# ---------------------------------------------------------------------------
# Record completeness (pinned checklist, missing is missing)
# ---------------------------------------------------------------------------

# Each check: key, label, what it enables, and the count query. The
# checklist is this module's own convention, derived from what the
# platform's views need — not from any clinical guideline.
_COMPLETENESS_CHECKS = (
    ("sources", "Current sources on the record",
     "the longitudinal picture and every derived view",
     "SELECT COUNT(*) FROM source_versions WHERE case_id=? AND state='current'"),
    ("laboratory_sources", "Current laboratory sources",
     "lab trends",
     "SELECT COUNT(*) FROM source_versions WHERE case_id=? AND state='current' AND kind='laboratory'"),
    ("imaging_sources", "Current imaging sources",
     "imaging comparison",
     "SELECT COUNT(*) FROM source_versions WHERE case_id=? AND state='current' AND kind='imaging'"),
    ("molecular_sources", "Current molecular sources",
     "molecular evidence links",
     "SELECT COUNT(*) FROM source_versions WHERE case_id=? AND state='current' AND kind='molecular'"),
    ("longitudinal_coverage", "Finding keys with 2+ points on current sources",
     "the longitudinal picture",
     """SELECT COUNT(*) FROM (
         SELECT a.finding_key FROM assertions a
         JOIN source_versions s ON s.id=a.source_version_id
         WHERE a.case_id=? AND s.state='current'
         GROUP BY a.finding_key HAVING COUNT(*) >= 2)"""),
    ("therapy_lines", "Current therapy lines",
     "outcomes tracking",
     "SELECT COUNT(*) FROM therapy_lines WHERE case_id=? AND state='current'"),
    ("symptom_notes", "Current symptom notes",
     "symptom progression",
     """SELECT COUNT(*) FROM patient_notes n
        JOIN patient_note_versions v ON v.note_id=n.id
        WHERE n.case_id=? AND n.kind='symptom' AND v.record_state='current'"""),
    ("patient_goals", "Patient goals",
     "outcomes tracking",
     "SELECT COUNT(*) FROM patient_goals WHERE case_id=?"),
    ("questions", "Durable questions",
     "investigation and review",
     "SELECT COUNT(*) FROM questions WHERE case_id=?"),
    ("investigations", "Investigations run",
     "K-checked claims and the Skeptic's review",
     "SELECT COUNT(*) FROM investigations WHERE case_id=?"),
    ("specimen_assets", "Biological assets on the record",
     "specimen-chain checks",
     "SELECT COUNT(*) FROM biological_assets WHERE case_id=?"),
)


def record_completeness(store, case_id: str) -> dict:
    """Record-completeness analytics: what the record holds, what it lacks.

    Every check is a count over current stored data. A missing item is
    listed as missing with what it blocks — never filled in, never
    guessed.
    """
    _require_case(store, case_id)
    checks = []
    with store.db:
        store.db.execute("BEGIN")
        for key, label, enables, sql in _COMPLETENESS_CHECKS:
            count = int(store.db.execute(sql, (case_id,)).fetchone()[0])
            checks.append({
                "key": key,
                "label": label,
                "status": "present" if count > 0 else "missing",
                "count": count,
                "enables": enables,
            })
    return {
        "case_id": case_id,
        "checks": checks,
        "present": sum(1 for c in checks if c["status"] == "present"),
        "missing": sum(1 for c in checks if c["status"] == "missing"),
        "missing_keys": [c["key"] for c in checks if c["status"] == "missing"],
    }


# ---------------------------------------------------------------------------
# Outcomes tracking (recorded states only)
# ---------------------------------------------------------------------------

def outcomes_tracking(store, case_id: str, *, today=None) -> dict:
    """Outcomes tracking: the current state of outcome-bearing records.

    Therapy lines (current vs stale, by ruleset), patient goals
    (current status + version history), and follow-through tasks
    (counts by status; overdue only when ``today`` is supplied).
    Every value is a recorded state — no response, progression,
    benefit, or eligibility claim is ever made.
    """
    today = _check_today(today)
    _require_case(store, case_id)
    with store.db:
        store.db.execute("BEGIN")
        current_lines = [dict(r) for r in store.db.execute(
            """SELECT line_number, regimen_key, first_occurred,
            last_occurred, ruleset_version, computed_at
            FROM therapy_lines WHERE case_id=? AND state='current'
            ORDER BY line_number""", (case_id,)).fetchall()]
        stale_rows = [dict(r) for r in store.db.execute(
            """SELECT stale_reason, COUNT(*) AS n FROM therapy_lines
            WHERE case_id=? AND state='stale' GROUP BY stale_reason""",
            (case_id,)).fetchall()]
        tasks = [dict(r) for r in store.db.execute(
            """SELECT t.id, t.title, t.status, t.due_date, t.review_trigger,
            COUNT(e.id) AS event_count, MAX(e.noted_at) AS last_event_at
            FROM followthrough_tasks t
            LEFT JOIN followthrough_task_events e ON e.task_id=t.id
            WHERE t.case_id=? GROUP BY t.id ORDER BY t.id""",
            (case_id,)).fetchall()]
    goals = store.patient_goals(case_id)
    goal_entries = []
    for goal in goals:
        versions = goal.get("versions") or []
        statuses = [v.get("status") for v in versions]
        changes = sum(1 for a, b in zip(statuses, statuses[1:]) if a != b)
        current = goal.get("current") or {}
        goal_entries.append({
            "goal_id": goal["goal_id"],
            "status": current.get("status"),
            "stated_date": current.get("stated_date"),
            "review_date": current.get("review_date"),
            "review_trigger": current.get("review_trigger"),
            "status_reason": current.get("status_reason"),
            "version_count": len(versions),
            "status_changes": changes,
            "status_history": [
                {"version": v.get("version"), "status": v.get("status"),
                 "stated_date": v.get("stated_date")}
                for v in versions
            ],
        })
    by_status: dict[str, int] = {}
    overdue = 0
    for task in tasks:
        by_status[task["status"]] = by_status.get(task["status"], 0) + 1
        if (today is not None and task["due_date"] and task["due_date"] < today
                and task["status"] not in ("completed", "deferred")):
            overdue += 1
    return {
        "case_id": case_id,
        "therapy_lines": {
            "current": [{
                "line_number": int(r["line_number"]),
                "regimen_key": r["regimen_key"],
                "first_occurred": r["first_occurred"],
                "last_occurred": r["last_occurred"],
                "ruleset_version": r["ruleset_version"],
                "computed_at": r["computed_at"],
            } for r in current_lines],
            "current_count": len(current_lines),
            "stale_count": sum(int(r["n"]) for r in stale_rows),
            "stale_by_reason": {r["stale_reason"]: int(r["n"]) for r in stale_rows},
        },
        "patient_goals": {
            "goals": goal_entries,
            "goal_count": len(goal_entries),
            "by_status": {s: sum(1 for g in goal_entries if g["status"] == s)
                          for s in sorted({g["status"] for g in goal_entries})},
        },
        "followthrough_tasks": {
            "tasks": [{
                "task_id": int(t["id"]),
                "title": t["title"],
                "status": t["status"],
                "due_date": t["due_date"],
                "review_trigger": t["review_trigger"],
                "event_count": int(t["event_count"]),
                "last_event_at": t["last_event_at"],
            } for t in tasks],
            "task_count": len(tasks),
            "by_status": by_status,
            "overdue": overdue if today is not None else None,
            "overdue_status": ("computed" if today is not None
                               else "not_computed_no_today"),
        },
    }


# ---------------------------------------------------------------------------
# Aggregator
# ---------------------------------------------------------------------------

def patient_analytics(store, case_id: str, *, lab_series=None,
                      today=None) -> dict:
    """All four patient-analytics views for one case, read-only.

    ``lab_series`` is the T2 lab series as a plain mapping (the
    ``dataclasses.asdict`` shape); when it is None the lab-trend view
    is reported as not computed with its reason. A series for a
    different case is rejected, never silently used.
    """
    if lab_series is not None:
        if not isinstance(lab_series, dict):
            raise InvalidInput("lab series must be a T2 LabSeries mapping")
        if lab_series.get("case_id") != case_id:
            raise InvalidInput("lab series is for a different case")
    trends = (lab_trends(lab_series) if lab_series is not None else {
        "case_id": case_id,
        "status": "not_computed",
        "reason": "no_lab_series_supplied",
        "trends": {},
        "analytes_with_trend": 0,
        "analytes_not_computable": [],
    })
    return {
        "case_id": case_id,
        "lab_trends": trends,
        "symptom_progression": symptom_progression(store, case_id),
        "record_completeness": record_completeness(store, case_id),
        "outcomes_tracking": outcomes_tracking(store, case_id, today=today),
    }
