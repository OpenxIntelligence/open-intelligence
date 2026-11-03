"""Source-grounded, read-only synthetic laboratory trend computation.

This is a deterministic demonstration of one potential Composer tool. It is
NOT a clinical lab analyzer, unit converter, medical interpretation, or real
patient-data processor. It never writes an observation or a clinical decision.

Only exact independently authored OI-LAB-VALUE/1 quotations inside *current*
OI-SYNTHETIC-REPORT/1 laboratory sources are eligible. Rejected, missing,
ambiguous and incompatible measurements prevent trend computation.
Manually transcribed document intake remains ineligible, including PDF
extractions; its provenance is retained in an explicit hold for review.
"""
from __future__ import annotations

from decimal import Decimal, InvalidOperation
import re

from .store import CaseStore, InvalidInput

_FORMAT = re.compile(
    r"\AOI-LAB-VALUE/1;value=(-?(?:0|[1-9][0-9]{0,8})(?:\.[0-9]{1,4})?);"
    r"unit=(g/dL|mg/dL|mmol/L|U/L|%|10\^3/uL|10\^9/L);"
    r"qc=(passed|failed|pending|unknown)\Z"
)
_KEY = re.compile(r"\A[a-z][a-z0-9_-]{0,59}\Z")
MAX_MATCHING_RECORDS = 256
DISCLAIMER = (
    "Independently authored fictional records only. Values and QC flags are "
    "source declarations, not verified measurements. This tool computes a "
    "numerical difference, not a trend's clinical significance, a diagnosis, "
    "treatment recommendation, patient safety decision or authorization."
)


def _ref(source: dict, assertion: dict) -> dict:
    result = {
        "source_version_id": source["id"],
        "document_id": source["document_id"],
        "source_version": source["version"],
        "source_sha256": source["sha256"],
        "source_line": assertion["source_line"],
        "finding_key": assertion["finding_key"],
        "reported_state": assertion["certainty"],
        "event_date": source["event_date"],
        "issued_at": source["issued_at"],
        "received_at": source["received_at"],
        "specimen_id": source["specimen_id"],
    }
    for key in ("classification_origin", "annotation_method", "clinical_review",
                "transcription_review_sha256", "text_origin", "extraction_sha256",
                "source_page", "page_line", "page_text_sha256"):
        if key in assertion:
            result[key] = assertion[key]
    if source.get("document_intake") is not None or assertion.get("classification_origin") == "user_selected":
        result["quote"] = assertion["quote"]
    return result


def _decimal_string(value: Decimal) -> str:
    # Exact base-10 arithmetic: never round through a floating-point number.
    return format(value, "f")


def build_lab_trend(state: dict, finding_key: str) -> dict:
    """Compute only from one already case-scoped, canonical CaseStore.state().

    This function accepts one frozen input snapshot; it does not query or
    combine sources across transactions. It deliberately does not import
    semantic normal ranges, convert units, interpret results or infer QC.
    """
    if not isinstance(finding_key, str) or not _KEY.fullmatch(finding_key):
        raise InvalidInput("Invalid synthetic lab finding key")
    if not isinstance(state, dict) or not isinstance(state.get("case"), dict):
        raise InvalidInput("A canonical case state is required")
    case_id = state["case"].get("case_id")
    if not isinstance(case_id, str) or not case_id:
        raise InvalidInput("Case identity missing from state")
    sources = {
        row["id"]: row
        for row in state.get("sources", [])
        if row["state"] == "current" and row["kind"] == "laboratory"
    }
    matches = [
        (sources[item["source_version_id"]], item)
        for item in state.get("assertions", [])
        if item["finding_key"] == finding_key
        and item["source_version_id"] in sources
    ]
    if len(matches) > MAX_MATCHING_RECORDS:
        raise InvalidInput("Too many source measurements for bounded trend analysis")

    points: list[dict] = []
    holds: list[dict] = []
    for source, assertion in matches:
        ref = _ref(source, assertion)
        failure = None
        if source.get("document_intake") is not None or assertion.get("classification_origin") == "user_selected":
            # The numeric tool's qualified input remains the authored
            # synthetic report format. A selected quote and user-selected
            # status must not silently expand that contract or lose origin.
            failure = "manual_transcription_not_eligible"
        elif assertion["certainty"] != "reported":
            failure = "source_state_not_reported"
        elif source["issued_at"] < source["event_date"]:
            failure = "issued_before_event"
        else:
            parsed = _FORMAT.fullmatch(assertion["quote"])
            if parsed is None:
                failure = "unsupported_measurement_format"
            elif parsed.group(3) != "passed":
                failure = "qc_not_passed"
        if failure is not None:
            holds.append({"reason": failure, "source": ref})
            continue
        try:
            value = Decimal(parsed.group(1))
        except InvalidOperation:
            holds.append({"reason": "invalid_decimal", "source": ref})
            continue
        points.append({
            "value": _decimal_string(value),
            "unit": parsed.group(2),
            "qc": "passed_declared_by_synthetic_source_not_independently_verified",
            "source": ref,
        })

    points.sort(key=lambda p: (
        p["source"]["event_date"], p["source"]["issued_at"],
        p["source"]["received_at"], p["source"]["source_version_id"]
    ))
    # No implicit deduplication or selection between two same-day samples.
    days = [point["source"]["event_date"] for point in points]
    if len(set(days)) != len(days):
        holds.append({"reason": "multiple_samples_same_day_no_sequence",
                      "source_version_ids": [point["source"]["source_version_id"]
                                             for point in points]})

    units = {p["unit"] for p in points}
    if len(units) > 1:
        holds.append({"reason": "incompatible_units_no_conversion",
                      "units": sorted(units)})

    as_known_at = state.get("events", [])
    receipt = {
        "kind": "synthetic_laboratory_trend",
        "case_id": case_id,
        "finding_key": finding_key,
        "snapshot_event_id": as_known_at[0]["id"] if as_known_at else None,
        "snapshot_event_time": as_known_at[0]["occurred_at"] if as_known_at else None,
        "points": points,
        "holds": holds,
        "analysis_executed": False,
        "delta": None,
        "direction": None,
        "unit": next(iter(units)) if len(units) == 1 else None,
        "interpretation": "none",
        "clinical_review_state": "not_performed",
        "disclaimer": DISCLAIMER,
    }
    if holds:
        receipt["status"] = "held"
    elif len(points) < 2:
        receipt["status"] = "insufficient_current_measurements"
    else:
        difference = Decimal(points[-1]["value"]) - Decimal(points[0]["value"])
        receipt["status"] = "computed"
        receipt["analysis_executed"] = True
        receipt["delta"] = _decimal_string(difference)
        receipt["direction"] = (
            "numeric_increase" if difference > 0 else
            "numeric_decrease" if difference < 0 else "numeric_unchanged"
        )
        receipt["start_date"] = points[0]["source"]["event_date"]
        receipt["end_date"] = points[-1]["source"]["event_date"]
    return receipt


def case_lab_trend(store: CaseStore, case_id: str, finding_key: str) -> dict:
    """CaseStore.state performs a single case-scoped read transaction."""
    return build_lab_trend(store.state(case_id), finding_key)
