"""Contract regressions for the canonical H1 source/question projection bridge."""
import pytest

from open_intelligence.h1_semantic_bridge import bind_authorized_h1_question
from open_intelligence.semantic_contract import (
    Concept, Relationship, SemanticContractError, SemanticRegistry,
)

SID = "SRC-" + "A" * 32
QID = "QUESTION-" + "B" * 32
DIGEST = "c" * 64


def registry():
    return SemanticRegistry(
        (Concept("oi:observation", 1, "Source report"),
         Concept("oi:investigation", 1, "Saved question")),
        (Relationship("oi:source-to-question", 1, "oi:observation", "oi:investigation"),),
    )


def projections():
    question = dict(patient_id="P1", case_id="CASE-1", source_id=SID, question_id=QID,
                    source_sha256=DIGEST, source_version=1, source_line=2,
                    source_context_state="current_unreviewed_question",
                    human_review_state="not_submitted", clinical_approval=False)
    source = dict(source_id=SID, sha256=DIGEST, version=1)
    return question, source


def bind(q, s):
    return bind_authorized_h1_question(
        registry=registry(), question=q, source=s,
        authorized_patient_id="P1", authorized_case_id="CASE-1",
    )


def test_bind_exact_source_version():
    q, s = projections()
    result = bind(q, s)
    assert result.source.record_id == SID
    assert result.question.record_id == QID
    assert result.source.source_version_id == result.question.source_version_id
    assert not result.requires_reassessment


def test_stale_question_remains_unreviewed():
    q, s = projections()
    q["source_context_state"] = "source_reassessment_required"
    assert bind(q, s).requires_reassessment


@pytest.mark.parametrize("target,value,reason", [
    ("patient_id", "P2", "scope_mismatch"),
    ("case_id", "CASE-2", "scope_mismatch"),
    ("source_id", "SRC-other", "invalid_owner_identity"),
    ("source_sha256", "wrong", "invalid_owner_identity"),
    ("source_version", 2, "source_version_mismatch"),
    ("source_line", 0, "source_version_mismatch"),
    ("human_review_state", "approved", "unsupported_review_claim"),
    ("clinical_approval", True, "unsupported_review_claim"),
    ("source_context_state", "reviewed", "unknown_question_state"),
])
def test_invalid_question_projection(target, value, reason):
    q, s = projections()
    q[target] = value
    with pytest.raises(SemanticContractError) as error:
        bind(q, s)
    assert error.value.code == reason


@pytest.mark.parametrize("target,value", [
    ("source_id", "SRC-" + "D" * 32),
    ("sha256", "d" * 64),
    ("version", 2),
])
def test_reject_mismatched_source_projection(target, value):
    q, s = projections()
    s[target] = value
    with pytest.raises(SemanticContractError) as error:
        bind(q, s)
    assert error.value.code == "source_version_mismatch"
