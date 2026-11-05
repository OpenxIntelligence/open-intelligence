"""The oncology vertical: the starting domain's own rules, behind the
vertical interface (program plan slice V1).

Content moved verbatim from ``investigation.py`` (program plan slice C2)
— only its location changed. No rule's content changed in this slice:
the synonyms map, the condition terms, and the scope patterns are the
C2 values, and the evidence kinds and link templates are the
``evidence_catalog.py`` values. The vertical is the single source of
truth for them now; the core resolves them through the registry in
``vertical.py`` and never imports this module by name.
"""
from __future__ import annotations

from .vertical import Vertical, build_scope_patterns, register_vertical

# SYNONYMS maps value paraphrases to the case's own certainty words.
# It is grounded in the seeded case vocabulary (reported,
# not-reported, indeterminate, pending, not-assessed) and in the seed
# documents' own phrasings for those states.
SYNONYMS = {
    "not tested": "not-reported",
    "not reported": "not-reported",
    "present": "reported",
    "detected": "reported",
    "found": "reported",
    "observed": "reported",
    "unclear": "indeterminate",
    "uncertain": "indeterminate",
    "cannot be assessed": "indeterminate",
    "could not be assessed": "indeterminate",
    "awaiting": "pending",
    "unavailable": "pending",
    "not assessed": "not-assessed",
    "not evaluated": "not-assessed",
}

# Condition terms for the K6 "you have" scope pattern.
CONDITION_TERMS = [
    "cancer", "carcinoma", "neoplasm", "malignancy", "malignant", "tumour", "tumor",
]

# The line-of-therapy ruleset version label. An opaque string the K5
# check compares for change; it names no guideline and carries no
# guideline content (no guideline text is ingested anywhere).
LOT_RULESET = "lot-rules-1"

# Evidence bindings: the source kinds this vertical recognizes, and
# the link template per kind. Same values as ``evidence_catalog.py``;
# ``tests/test_vertical_boundary.py`` binds the two — the vertical is
# the declaration, the catalog is the storage-side contract.
EVIDENCE_KINDS = frozenset(
    {"civic", "nci_thesaurus", "crossref", "clinicaltrials_gov", "fictional"}
)
LINK_TEMPLATES = {
    "civic": "https://example.invalid/civic/{id}/{version}",
    "nci_thesaurus": "https://example.invalid/nci/{id}/{version}",
    "crossref": "https://example.invalid/crossref/{id}/{version}",
    "clinicaltrials_gov": "https://example.invalid/clinicaltrials/{id}/{version}",
    "fictional": "https://example.invalid/fictional/{id}/{version}",
}

ONCOLOGY = Vertical(
    name="oncology",
    synonyms=dict(SYNONYMS),
    condition_terms=tuple(CONDITION_TERMS),
    scope_patterns=tuple(build_scope_patterns(CONDITION_TERMS)),
    lot_ruleset=LOT_RULESET,
    evidence_kinds=frozenset(EVIDENCE_KINDS),
    link_templates=dict(LINK_TEMPLATES),
)

register_vertical(ONCOLOGY)
