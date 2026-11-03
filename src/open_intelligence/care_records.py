"""Descriptive-only language guard for second-opinion and survivorship records.

Second-opinion and survivorship entries are recorded descriptions of a
fictional case file. They describe what was asked, shared, noted, or
recorded; they never direct care. This module rejects directive and
clinical-claim wording at write time. It is a narrow guard, not a
clinical-language classifier: human review remains the gate, and every
view carries a disclaimer stating what the records are not.
"""

from __future__ import annotations

import re


class CareRecordInputError(ValueError):
    """A care record violates the descriptive-only contract."""


# Each pattern matches wording that directs care or asserts a clinical
# claim. Word-boundary matching avoids false hits on ordinary record
# words ("the report states", "tiredness noted").
_GUARDED = (
    (re.compile(r"\bshould\b", re.IGNORECASE), "should"),
    (re.compile(r"\bmust\b", re.IGNORECASE), "must"),
    (re.compile(r"\bneeds?\s+to\b", re.IGNORECASE), "need(s) to"),
    (re.compile(r"\bhave\s+to\b", re.IGNORECASE), "have to"),
    (re.compile(r"\brecommend\w*\b", re.IGNORECASE), "recommend..."),
    (re.compile(r"\bprescrib\w*\b", re.IGNORECASE), "prescrib..."),
    (re.compile(r"\beligib\w*\b", re.IGNORECASE), "eligib..."),
    (re.compile(r"\border\s+(?:(?:this|the|a|an)\s+)?"
                r"(treatment|therapy|procedure|test|scan|biopsy|imaging|bloodwork)\b",
                re.IGNORECASE), "order ..."),
    (re.compile(r"\bstart\s+(treatment|therapy)\b", re.IGNORECASE), "start treatment/therapy"),
    (re.compile(r"\bstop\s+(treatment|therapy)\b", re.IGNORECASE), "stop treatment/therapy"),
    (re.compile(r"\bwatch\s+for\b", re.IGNORECASE), "watch for"),
    (re.compile(r"\blook\s+out\s+for\b", re.IGNORECASE), "look out for"),
    (re.compile(r"\bseek\s+(care|help|treatment|medical\s+attention)\b", re.IGNORECASE),
     "seek care/help"),
    (re.compile(r"\bgo\s+to\s+(?:the\s+)?(emergency|clinic|hospital|doctor)\b", re.IGNORECASE),
     "go to ..."),
    (re.compile(r"\bcall\s+(your|the)\b", re.IGNORECASE), "call your/the ..."),
    (re.compile(r"\bcontact\s+(your|the)\b", re.IGNORECASE), "contact your/the ..."),
    (re.compile(r"\beffective\b", re.IGNORECASE), "effective"),
    (re.compile(r"\befficac\w*\b", re.IGNORECASE), "efficac..."),
    (re.compile(r"\bproven\b", re.IGNORECASE), "proven"),
    (re.compile(r"\bbenefit\b", re.IGNORECASE), "benefit"),
)


def find_directed_language(value: str) -> str | None:
    """Return the label of the first guarded term found, else None."""
    for pattern, label in _GUARDED:
        if pattern.search(value):
            return label
    return None


def check_descriptive(field: str, value: object, min_len: int, max_len: int) -> str:
    """Validate a record text field: length plus descriptive-only wording."""
    if not isinstance(value, str) or not min_len <= len(value.strip()) <= max_len:
        raise CareRecordInputError(f"{field} must have {min_len}\u2013{max_len} characters")
    text = value.strip()
    hit = find_directed_language(text)
    if hit is not None:
        raise CareRecordInputError(
            f"{field} must describe the recorded plan; it must not direct care "
            f"(guarded wording: {hit})"
        )
    return text


SECOND_OPINION_DISCLAIMER = (
    "Second-opinion records are separate from the original case conclusions. "
    "A response never overwrites the original record; both stay visible side by side. "
    "Fictional demonstration data only \u2014 not clinical advice."
)

SURVIVORSHIP_DISCLAIMER = (
    "Recorded plan only. These notes describe a fictional follow-up record; "
    "they never direct care and are not clinical directives. "
    "A recorded date is not a clinical due date. Fictional demonstration data only."
)
