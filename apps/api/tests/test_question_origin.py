"""Regression checks for the pure canonical question-origin classifier."""
import pytest

from oi_api.question_origin import classify_question_origin, classify_stored_question_origin

Q = "QUESTION-" + "A" * 32
S = "SRC-" + "B" * 32


def test_source_line_origin():
    value = classify_question_origin(question_id=Q, source_id=S, source_line=3,
                                     observation_reference=None)
    assert value.kind == "source_line"
    assert value.line == 3
    assert value.observation_reference is None


def test_fhir_observation_origin():
    value = classify_question_origin(question_id=Q, source_id=S, source_line=None,
                                     observation_reference="Observation/FICTIONAL-OBS-A")
    assert value.kind == "fhir_observation"
    assert value.observation_reference == "Observation/FICTIONAL-OBS-A"
    assert value.line is None


@pytest.mark.parametrize("line,reference", [
    (None, None), (1, "Observation/valid"), (0, None), (10001, None), (True, None),
    (-1, None), (None, "Patient/not-an-observation"),
    (None, "Observation/bad slash"), (None, "Observation/"),
])
def test_invalid_or_ambiguous_origin_rejected(line, reference):
    with pytest.raises(ValueError):
        classify_question_origin(question_id=Q, source_id=S, source_line=line,
                                 observation_reference=reference)


def test_invalid_identifiers_rejected():
    with pytest.raises(ValueError):
        classify_question_origin(question_id="QUESTION-bad", source_id=S,
                                 source_line=1, observation_reference=None)
    with pytest.raises(ValueError):
        classify_question_origin(question_id=Q, source_id="SRC-bad",
                                 source_line=None, observation_reference="Observation/x")


def test_stored_text_question_has_no_laboratory_child():
    value = classify_stored_question_origin(
        question_id=Q, source_id=S, source_line=1,
        observation_reference=None, anchor_source_id=None)
    assert value.kind == "source_line"


def test_stored_laboratory_question_requires_matching_child_source():
    value = classify_stored_question_origin(
        question_id=Q, source_id=S, source_line=None,
        observation_reference="Observation/FICTIONAL-A", anchor_source_id=S)
    assert value.kind == "fhir_observation"
    for wrong in (None, "SRC-" + "C" * 32):
        with pytest.raises(ValueError):
            classify_stored_question_origin(
                question_id=Q, source_id=S, source_line=None,
                observation_reference="Observation/FICTIONAL-A",
                anchor_source_id=wrong)


def test_stored_text_question_rejects_unexpected_laboratory_child():
    with pytest.raises(ValueError):
        classify_stored_question_origin(
            question_id=Q, source_id=S, source_line=1,
            observation_reference=None, anchor_source_id=S)


def test_source_line_upper_bound_matches_assertion_schema():
    value = classify_question_origin(question_id=Q, source_id=S,
                                     source_line=10000, observation_reference=None)
    assert value.line == 10000
