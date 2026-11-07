"""Pure typed origin classification for canonical saved questions.

This is a validation primitive, not an authorization or database read.
Callers must obtain records through the existing scoped source/question owners.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Literal

QUESTION_ID = re.compile(r"QUESTION-[0-9A-F]{32}\Z")
SOURCE_ID = re.compile(r"SRC-[0-9A-F]{32}\Z")
OBSERVATION = re.compile(r"Observation/[A-Za-z0-9.-]{1,64}\Z")


@dataclass(frozen=True)
class QuestionOrigin:
    kind: Literal["source_line", "fhir_observation"]
    question_id: str
    source_id: str
    line: int | None = None
    observation_reference: str | None = None


def classify_question_origin(*, question_id: str, source_id: str,
                             source_line: int | None,
                             observation_reference: str | None) -> QuestionOrigin:
    """Reject missing, ambiguous or malformed anchors; never guess a kind."""
    if (type(question_id) is not str or not QUESTION_ID.fullmatch(question_id)
            or type(source_id) is not str or not SOURCE_ID.fullmatch(source_id)):
        raise ValueError("Invalid canonical question or source identifier")
    if source_line is not None:
        if (type(source_line) is not int or not 1 <= source_line <= 10000
                or observation_reference is not None):
            raise ValueError("Question origin must have exactly one valid anchor")
        return QuestionOrigin("source_line", question_id, source_id, line=source_line)
    if (type(observation_reference) is not str
            or not OBSERVATION.fullmatch(observation_reference)):
        raise ValueError("Question origin must have exactly one valid anchor")
    return QuestionOrigin("fhir_observation", question_id, source_id,
                          observation_reference=observation_reference)


def classify_stored_question_origin(*, question_id: str, source_id: str,
                                    source_line: int | None,
                                    observation_reference: str | None,
                                    anchor_source_id: str | None) -> QuestionOrigin:
    """Validate the canonical question row together with its optional typed child.

    The child must be absent for a source-line question and must match the
    canonical source for a laboratory question. This pure helper never queries
    storage, confers authority, or changes question freshness.
    """
    origin = classify_question_origin(
        question_id=question_id, source_id=source_id,
        source_line=source_line, observation_reference=observation_reference,
    )
    if origin.kind == "source_line":
        if anchor_source_id is not None:
            raise ValueError("Text-line question must not have a laboratory child")
    elif anchor_source_id != source_id:
        raise ValueError("Laboratory question child must match canonical source")
    return origin
