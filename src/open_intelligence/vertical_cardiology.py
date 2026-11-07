"""The cardiology vertical: a minimal synthetic second domain, registered
through the vertical interface (program plan slice V1).

This is V1's stub vertical, made concrete: it proves the core is
domain-free by running the same pipeline — route, K-checks, Skeptic,
T6 — under cardiology predicates resolved through the registry, with
no core change beyond the interface itself. It is deliberately
minimal: synonyms, condition terms, scope patterns, a ruleset version
label, and evidence bindings. No guideline text is ingested; no real
cardiology data is used; every fixture value is independently
authored synthetic data. Slice V2 lands the full cardiology
vertical here: the investigation dimensions run against
cardiology fixtures and the care loop works for the cardiology
case, with zero core changes (see the V2 section of
``docs/IMPLEMENTATION_STATUS.md`` for the core-change
accounting).
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
# shape. Per-vertical catalog resolution was recorded as V2 work in
# the V1 doc, but plan §V2 does not require it and the catalog is
# not in the investigation pipeline path; it remains a follow-up,
# and the catalog still validates against the oncology binding.

# Terminology bindings (V2): pinned only from the publishers' own
# listings, per the terminology honesty rule — a code enters the
# table only as a long-stable public code, never invented or "close
# enough". LOINC 10230-1 "Left ventricular Ejection fraction"
# (Regenstrief LOINC listing; also carried in the HL7 FHIR
# observation-codes value set and DICOM CP-2147) for finding key
# "ejection-fraction"; ICD-10 I50.9 "Heart failure, unspecified"
# (WHO ICD-10, category I50) for finding key "heart-failure".
# SNOMED CT stays blocked (license unresolved); no SNOMED code is
# ever emitted or accepted.
TERMINOLOGY_BINDINGS = {
    "ejection-fraction": (
        {"system": "http://loinc.org", "code": "10230-1",
         "display": "Left ventricular Ejection fraction"},
    ),
    "heart-failure": (
        {"system": "http://hl7.org/fhir/sid/icd-10", "code": "I50.9",
         "display": "Heart failure, unspecified"},
    ),
}

# Substance names (V2): a fixture vocabulary for the K7 substance
# arm only — token matching against cited evidence, never a
# recommendation or a dose. Common cardiology agents used in the
# synthetic fixtures; a claim naming one without citing evidence
# that carries it is dropped as k7_unsupported_token.
SUBSTANCE_NAMES = (
    "metoprolol", "lisinopril", "atorvastatin", "furosemide",
)
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
    substance_names=tuple(SUBSTANCE_NAMES),
    terminology_bindings={
        key: tuple(codings)
        for key, codings in TERMINOLOGY_BINDINGS.items()
    },
)

register_vertical(CARDIOLOGY)
