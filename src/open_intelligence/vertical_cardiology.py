"""The cardiology vertical: a minimal synthetic second domain, registered
through the vertical interface (program plan slice V1).

This is V1's stub vertical, made concrete: it proves the core is
domain-free by running the same pipeline — route, K-checks, Skeptic,
T6 — under cardiology predicates resolved through the registry, with
no core change beyond the interface itself. It is deliberately
minimal: synonyms, condition terms, scope patterns, a ruleset version
label, and evidence bindings. No guideline text is ingested; no real
cardiology data is used; every fixture value is independently
authored synthetic data. The full cardiology vertical — domain
toolsets, the investigation dimensions against cardiology fixtures,
the care loop — is slice V2, after the dimensions exist.
"""
from __future__ import annotations

from .vertical import Vertical, build_scope_patterns, register_vertical

# SYNONYMS maps value paraphrases to the case's own canonical
# certainty words (reported, not-reported, indeterminate, pending,
# not-assessed). The cardiology-distinctive entries — "not performed",
# "not done", "seen", "identified", "noted", "demonstrated" — are
# what make a cardiology slot resolve where the oncology vertical
# would not, and vice versa for "not tested" / "detected" / "found" /
# "observed".
SYNONYMS = {
    "not performed": "not-reported",
    "not done": "not-reported",
    "not obtained": "not-reported",
    "seen": "reported",
    "identified": "reported",
    "noted": "reported",
    "demonstrated": "reported",
    "unclear": "indeterminate",
    "uncertain": "indeterminate",
    "cannot be assessed": "indeterminate",
    "could not be assessed": "indeterminate",
    "awaiting": "pending",
    "unavailable": "pending",
    "not assessed": "not-assessed",
    "not evaluated": "not-assessed",
}

# Condition terms for the K6 "you have" scope pattern. Plain
# cardiology vocabulary, synthetic fixtures only.
CONDITION_TERMS = [
    "heart failure", "myocardial infarction", "arrhythmia",
    "coronary artery disease", "atrial fibrillation", "cardiomyopathy",
    "angina", "aortic stenosis",
]

# The therapy-ruleset version label: cardiology's line-of-therapy
# equivalent, as an opaque string the K5 check compares for change.
# It names no guideline and carries no guideline content.
LOT_RULESET = "therapy-rules-1"

# Evidence bindings for this vertical. The kinds are plain labels for
# the evidence this domain produces (ECG, echocardiogram, cardiac
# labs); the link templates mirror the catalog's example.invalid
# shape. Per-vertical catalog resolution is V2 work; until then the
# catalog still validates against the oncology binding.
EVIDENCE_KINDS = frozenset(
    {"ecg", "echocardiogram", "cardiac-lab", "fictional"}
)
LINK_TEMPLATES = {
    "ecg": "https://example.invalid/ecg/{id}/{version}",
    "echocardiogram": "https://example.invalid/echocardiogram/{id}/{version}",
    "cardiac-lab": "https://example.invalid/cardiac-lab/{id}/{version}",
    "fictional": "https://example.invalid/fictional/{id}/{version}",
}

CARDIOLOGY = Vertical(
    name="cardiology",
    synonyms=dict(SYNONYMS),
    condition_terms=tuple(CONDITION_TERMS),
    scope_patterns=tuple(build_scope_patterns(CONDITION_TERMS)),
    lot_ruleset=LOT_RULESET,
    evidence_kinds=frozenset(EVIDENCE_KINDS),
    link_templates=dict(LINK_TEMPLATES),
)

register_vertical(CARDIOLOGY)
