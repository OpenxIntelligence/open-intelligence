"""Read-only synthetic lab calculation, scoped to one Composer context snapshot.

This bridges the existing case/question/fingerprint contract to the separately
verified deterministic lab tool. It does not schedule jobs, write medical data,
prove lab QC, grant authorization or perform clinical interpretation.
"""
from __future__ import annotations

import hmac
import re

from .composer import _fingerprint, _snapshot_rows_from_state, composer_context_fingerprint
from .lab_trends import build_lab_trend
from .store import CaseStore, InvalidInput

TOOL_ID = "synthetic-lab-trend-v1"


def composer_lab_trend(store: CaseStore, case_id: str, question_id: int,
                       fingerprint: str, finding_key: str) -> dict:
    """Execute a bounded calculation only against the previewed case snapshot.

    The exact source, question and evidence context hash comes from the same
    canonical state used to calculate the numeric result. A fresh check after
    computing detects concurrent source amendments before returning. No result
    is persisted; do not treat this as a durable run receipt.
    """
    if type(question_id) is not int or question_id < 1:
        raise InvalidInput("Composer question ID must be a positive integer")
    if not isinstance(fingerprint, str) or not re.fullmatch(r"[a-f0-9]{64}", fingerprint):
        raise InvalidInput("Current Composer context fingerprint is required")
    state = store.state(case_id)
    question, sources, assertions, assessments = _snapshot_rows_from_state(state, question_id)
    current = _fingerprint(case_id, question, sources, assertions, assessments)
    if not hmac.compare_digest(fingerprint, current):
        raise InvalidInput("stale Composer context; refresh source preview before calculation")
    result = build_lab_trend(state, finding_key)
    if not hmac.compare_digest(
        current, composer_context_fingerprint(store, case_id, question_id)
    ):
        raise InvalidInput("stale Composer context; source changed during calculation")
    return {
        "tool_id": TOOL_ID,
        "task_kind": "deterministic_synthetic_numeric_comparison",
        "question_id": question_id,
        "context_fingerprint": current,
        "source_cutoff": max((s["received_at"] for s in sources if s["received_at"]), default=None),
        "execution_receipt": "computed_read_only_not_persisted" if result["status"] == "computed"
                             else "not_computed",
        "result": result,
        "status": result["status"],
        "clinical_authorization": "not_verified",
        "clinical_interpretation": "not_performed",
        "disclaimer": (
            "Local fictional data only. The numerical comparison is a tool result, "
            "not clinical advice, a verified assay, a reviewed interpretation, "
            "an EHR order or a persistent agent job. Results can become stale."
        ),
    }
