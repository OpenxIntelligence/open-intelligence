"""Read-only synthetic-fixture metrics projection over the case ledger.

This module computes descriptive workflow counts from ledger facts only:
correction counts, stale-item lag, abstention counts, guard-drop counts,
and invalidated-vs-untouched counts. It never calls a model, never writes
to the ledger, never stores a metric history, and never describes real
cases or clinical performance.

Read-only contract (same as ``mission.py``/``changes.py``/``timeline.py``):
reads only, writes nothing, deterministic. Run records carry a
deterministic run id, a ledger-derived as-of time, and ledger positions,
so two runs over the same ledger state produce byte-identical payloads
and every derived value is recomputable from the ledger. There is no
second ledger of metric truth; a caller that wants trends retains the
returned payloads itself.

Held-out separation: the caller supplies a manifest of dev case ids and
held-out case ids. The two sets are validated disjoint, reported
separately, and never combined into shared counts.

Definitions (all recomputable from the ledger): a correction is a
source_imported event carrying an amendment link or an
evidence_invalidated event. Stale-item lag pairs each correction event
with the first demo-review acknowledgment recorded after it in the same
case (receipt time to re-review completion, in whole seconds from
ledger timestamps); a correction with no later acknowledgment is
pending, never zero-lag. Untouched items for an invalidation event are
the snapshots created before that event (by draft_created ledger order)
that the event did not invalidate. The run id is a hash of the manifest
plus ledger positions, and the as-of time is the latest reflected
ledger timestamp — never wall-clock time, so reruns stay identical.

Payload hygiene: payloads contain fictional case ids, ledger row ids,
counts, reason labels, and ledger timestamps only. They never contain
source text, quotations, finding keys, document ids, evidence keys,
question text, reviewer labels, or any patient-like field.

Every metric surface built from this module must show the synthetic-only
and non-transferable labels carried in each payload.
"""

from __future__ import annotations

import hashlib
import json
import statistics
from datetime import datetime

from .investigation import ABSTAIN_REASONS
from .store import CaseStore, InvalidInput

SYNTHETIC_ONLY_LABEL = "Synthetic fixtures only"
NON_TRANSFERABLE_LABEL = (
    "Non-transferable: these counts describe the synthetic fixtures only and "
    "do not describe real-case or clinical performance"
)
DISCLAIMER = (
    "Fictional synthetic fixtures only. This projection reports descriptive "
    "ledger counts (corrections, stale-item lag, abstentions, guard drops, "
    "invalidated-vs-untouched items). It states no clinical accuracy, benefit, "
    "efficacy, eligibility, quality grade, or recommendation. Small-fixture "
    "counts are non-transferable: success on fixtures does not imply "
    "real-case performance. Metric computation calls no model and writes no "
    "proposal, retraining signal, or ledger row."
)

# Drop reasons produced by investigation.validate_output, reused here as the
# observed vocabulary for guard-drop counts. Any other observed reason string
# is counted under its own key so new reasons stay visible, never merged.
KNOWN_DROP_REASONS = (
    "missing_text",
    "invalid_uncertainty",
    "invalid_support",
    "language_guard",
    "missing_citations",
    "unresolved_citation",
)

# Event kinds that record a correction. Source amendments arrive as
# source_imported events carrying a non-null amends_id; fictional evidence
# amendments/withdrawals fan out as evidence_invalidated events.
_CORRECTION_SOURCE_KIND = "source_imported"
_CORRECTION_EVIDENCE_KIND = "evidence_invalidated"


def _labels() -> dict:
    return {
        "synthetic_only": True,
        "non_transferable": True,
        "labels": [SYNTHETIC_ONLY_LABEL, NON_TRANSFERABLE_LABEL],
        "disclaimer": DISCLAIMER,
    }


def _safe_details(raw: object) -> dict:
    if not isinstance(raw, str):
        return {}
    try:
        value = json.loads(raw)
    except (json.JSONDecodeError, TypeError):
        return {}
    return value if isinstance(value, dict) else {}


def _safe_id_list(value: object) -> list[int]:
    if not isinstance(value, list):
        return []
    return sorted({item for item in value if type(item) is int})


def _safe_json_list(raw: object) -> list:
    if not isinstance(raw, str):
        return []
    try:
        value = json.loads(raw)
    except (json.JSONDecodeError, TypeError):
        return []
    return value if isinstance(value, list) else []


def _lag_seconds(received_at: str, rereview_at: str) -> int:
    return int((datetime.fromisoformat(rereview_at) - datetime.fromisoformat(received_at)).total_seconds())


def _lag_summary(samples: list[dict]) -> dict:
    values = sorted(sample["lag_seconds"] for sample in samples)
    if not values:
        return {"resolved": 0, "min_seconds": None, "max_seconds": None, "median_seconds": None}
    return {
        "resolved": len(values),
        "min_seconds": values[0],
        "max_seconds": values[-1],
        "median_seconds": statistics.median(values),
    }


def case_metrics(store: CaseStore, case_id: str) -> dict:
    """Build the metric projection for one fictional case.

    Reads only; writes nothing. Raises InvalidInput for unknown cases.
    """
    with store.db:
        store.db.execute("BEGIN")
        case = store.db.execute("SELECT case_id FROM cases WHERE case_id=?", (case_id,)).fetchone()
        if not case:
            raise InvalidInput("Unknown case")
        events = [dict(row) for row in store.db.execute(
            "SELECT id,kind,details,occurred_at FROM events WHERE case_id=? ORDER BY id",
            (case_id,)).fetchall()]
        investigations = [dict(row) for row in store.db.execute(
            "SELECT id,abstentions_json,dropped_json FROM investigations WHERE case_id=? ORDER BY id",
            (case_id,)).fetchall()]

        # Correction events: source amendments and evidence invalidations.
        amendment_events: list[dict] = []
        evidence_events: list[dict] = []
        for event in events:
            details = _safe_details(event.get("details"))
            if event.get("kind") == _CORRECTION_SOURCE_KIND and type(details.get("amends_id")) is int:
                amendment_events.append(event)
            elif event.get("kind") == _CORRECTION_EVIDENCE_KIND:
                evidence_events.append(event)
        invalidation_events = sorted(
            amendment_events + evidence_events, key=lambda item: item["id"])

        # Snapshots known before each event, from draft_created ledger order.
        drafts_before: dict[int, set[int]] = {}
        known: set[int] = set()
        for event in events:
            drafts_before[event["id"]] = set(known)
            if event.get("kind") == "draft_created":
                details = _safe_details(event.get("details"))
                if type(details.get("snapshot_id")) is int:
                    known.add(details["snapshot_id"])

        # Re-review completions: demo_review_acknowledged events in order.
        acknowledgments = [
            event for event in events if event.get("kind") == "demo_review_acknowledged"
        ]

        lag_samples: list[dict] = []
        pending_event_ids: list[int] = []
        for event in invalidation_events:
            rereview = next(
                (ack for ack in acknowledgments if ack["id"] > event["id"]), None)
            if rereview is None:
                pending_event_ids.append(event["id"])
            else:
                lag_samples.append({
                    "invalidation_event_id": event["id"],
                    "received_at": event["occurred_at"],
                    "rereview_event_id": rereview["id"],
                    "rereview_at": rereview["occurred_at"],
                    "lag_seconds": _lag_seconds(event["occurred_at"], rereview["occurred_at"]),
                })

        invalidated_vs_untouched: list[dict] = []
        for event in invalidation_events:
            details = _safe_details(event.get("details"))
            invalidated = _safe_id_list(details.get("invalidated_snapshots"))
            existed = drafts_before.get(event["id"], set())
            untouched = len(existed - set(invalidated))
            invalidated_vs_untouched.append({
                "event_id": event["id"],
                "kind": event["kind"],
                "invalidated": len(invalidated),
                "untouched": untouched,
            })

        abstentions_by_reason: dict[str, int] = {reason: 0 for reason in sorted(ABSTAIN_REASONS)}
        abstention_entries = 0
        unrecognized_abstentions = 0
        for row in investigations:
            for entry in _safe_json_list(row.get("abstentions_json")):
                if isinstance(entry, dict) and isinstance(entry.get("reason"), str):
                    reason = entry["reason"]
                    abstentions_by_reason[reason] = abstentions_by_reason.get(reason, 0) + 1
                    abstention_entries += 1
                else:
                    unrecognized_abstentions += 1

        drops_by_reason: dict[str, int] = {reason: 0 for reason in KNOWN_DROP_REASONS}
        drop_entries = 0
        unrecognized_drops = 0
        for row in investigations:
            for entry in _safe_json_list(row.get("dropped_json")):
                if isinstance(entry, dict) and isinstance(entry.get("reason"), str):
                    reason = entry["reason"]
                    drops_by_reason[reason] = drops_by_reason.get(reason, 0) + 1
                    drop_entries += 1
                else:
                    unrecognized_drops += 1

        latest = events[-1] if events else None
        payload = _labels()
        payload.update({
            "case_id": case_id,
            "ledger_position": {
                "latest_event_id": latest["id"] if latest else None,
                "occurred_at": latest["occurred_at"] if latest else None,
            },
            "corrections": {
                "source_amendments": len(amendment_events),
                "evidence_invalidations": len(evidence_events),
                "total": len(amendment_events) + len(evidence_events),
                "correction_event_ids": [event["id"] for event in invalidation_events],
            },
            "abstentions_by_reason": abstentions_by_reason,
            "abstention_entries": abstention_entries,
            "unrecognized_abstention_entries": unrecognized_abstentions,
            "guard_drops_by_reason": drops_by_reason,
            "guard_drop_entries": drop_entries,
            "unrecognized_drop_entries": unrecognized_drops,
            "investigation_count": len(investigations),
            "stale_lag": {
                "samples": lag_samples,
                "pending_invalidation_event_ids": pending_event_ids,
                "invalidations": len(invalidation_events),
                "pending": len(pending_event_ids),
                "summary": _lag_summary(lag_samples),
            },
            "invalidated_vs_untouched": invalidated_vs_untouched,
        })
        return payload


def _aggregate(case_payloads: list[dict]) -> dict:
    corrections = {"source_amendments": 0, "evidence_invalidations": 0, "total": 0}
    abstentions: dict[str, int] = {}
    drops: dict[str, int] = {}
    abstention_entries = 0
    drop_entries = 0
    samples: list[dict] = []
    pending: list[dict] = []
    invalidated_total = 0
    untouched_total = 0
    for payload in case_payloads:
        for key in corrections:
            corrections[key] += payload["corrections"][key]
        for reason in sorted(payload["abstentions_by_reason"]):
            abstentions[reason] = abstentions.get(reason, 0) + payload["abstentions_by_reason"][reason]
        for reason in sorted(payload["guard_drops_by_reason"]):
            drops[reason] = drops.get(reason, 0) + payload["guard_drops_by_reason"][reason]
        abstention_entries += payload["abstention_entries"]
        drop_entries += payload["guard_drop_entries"]
        for sample in payload["stale_lag"]["samples"]:
            samples.append({"case_id": payload["case_id"], **sample})
        for event_id in payload["stale_lag"]["pending_invalidation_event_ids"]:
            pending.append({"case_id": payload["case_id"], "invalidation_event_id": event_id})
        for row in payload["invalidated_vs_untouched"]:
            invalidated_total += row["invalidated"]
            untouched_total += row["untouched"]
    samples.sort(key=lambda item: (item["case_id"], item["invalidation_event_id"]))
    pending.sort(key=lambda item: (item["case_id"], item["invalidation_event_id"]))
    summary = _lag_summary(samples)
    summary["pending"] = len(pending)
    return {
        "case_count": len(case_payloads),
        "corrections": corrections,
        "abstentions_by_reason": abstentions,
        "abstention_entries": abstention_entries,
        "guard_drops_by_reason": drops,
        "guard_drop_entries": drop_entries,
        "stale_lag": {"samples": samples, "pending": pending, "summary": summary},
        "invalidated_total": invalidated_total,
        "untouched_total": untouched_total,
        "invalidation_events": sum(len(payload["invalidated_vs_untouched"]) for payload in case_payloads),
    }


def _check_manifest(names: object, field: str) -> list[str]:
    if not isinstance(names, list) or any(not isinstance(item, str) for item in names):
        raise InvalidInput(f"{field} must be a list of case ids")
    return sorted(set(names))


def fixture_run(store: CaseStore, dev_cases: list[str], held_out_cases: list[str]) -> dict:
    """Build one fixture run over dev and held-out fictional case sets.

    Reads only; writes nothing. The two sets must be disjoint; every named
    case must exist. The dev and held-out aggregates are reported
    separately with no shared counts. The run id and as-of time derive
    from the manifest and ledger positions, so the payload is recomputable
    and byte-identical across runs over the same ledger state.
    """
    dev = _check_manifest(dev_cases, "dev_cases")
    held_out = _check_manifest(held_out_cases, "held_out_cases")
    if not dev:
        raise InvalidInput("dev_cases must name at least one fictional case")
    overlap = sorted(set(dev) & set(held_out))
    if overlap:
        raise InvalidInput("dev_cases and held_out_cases must be disjoint")
    dev_payloads = [case_metrics(store, case_id) for case_id in dev]
    held_out_payloads = [case_metrics(store, case_id) for case_id in held_out]
    positions = {
        payload["case_id"]: payload["ledger_position"]
        for payload in dev_payloads + held_out_payloads
    }
    as_of = max(
        (payload["ledger_position"]["occurred_at"] for payload in dev_payloads + held_out_payloads
         if payload["ledger_position"]["occurred_at"] is not None),
        default=None,
    )
    canonical = json.dumps(
        {"dev_cases": dev, "held_out_cases": held_out, "ledger_positions": positions},
        sort_keys=True,
    )
    run_id = "METRICS-" + hashlib.sha256(canonical.encode("utf-8")).hexdigest()[:12]
    run_block = _labels()
    run_block.update({
        "run_id": run_id,
        "as_of_ledger_time": as_of,
        "ledger_positions": positions,
        "manifest": {"dev_cases": dev, "held_out_cases": held_out},
    })
    dev_block = _labels()
    dev_block.update({
        "cases": {payload["case_id"]: payload for payload in dev_payloads},
        "aggregate": _aggregate(dev_payloads),
    })
    held_out_block = _labels()
    held_out_block.update({
        "cases": {payload["case_id"]: payload for payload in held_out_payloads},
        "aggregate": _aggregate(held_out_payloads),
    })
    return {"run": run_block, "dev": dev_block, "held_out": held_out_block}
