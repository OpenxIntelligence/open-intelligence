"""Terminology bindings for exchange (program plan slice D2).

Modality schema packs: the code-system bindings organized by modality,
each pack naming its system, its pinned codes, and the availability of
the system. This module is deterministic code, not a terminology server:
it proves the binding mechanics (attach on export, validate on import,
refuse what is unknown or unlicensed) on a pinned fixture table, not
terminology completeness.

Honesty rules, enforced here and nowhere else:

* A code enters the pinned table only as a long-stable public code from
  the publisher's own listing (LOINC from Regenstrief, ICD-10 from WHO).
  No code is invented, guessed, or "close enough". A finding key with no
  pinned code is unbound, and the export says so — it never receives a
  fabricated coding.
* SNOMED CT is BLOCKED, not merely absent: it requires an affiliate
  license (IHTSDO), which is unresolved in this slice. No SNOMED code
  is ever emitted or accepted; a bundle carrying one is rejected with
  ``terminology_system_blocked``. This follows the catalog's own
  ``BLOCKED_SOURCES`` precedent (``evidence_catalog.py``).
* RxNorm is registered with no pinned codes yet: the system is free
  (U.S. National Library of Medicine) but no medication finding exists
  in the runtime to bind, so bindings arrive with a medication surface,
  not before.
* Every entry carries its provenance as a comment at the declaration
  site. The table is a fixture: verify each code against the publisher
  before any clinical use; the tests pin the table's exact contents so
  drift is caught.

Domain bindings live on the vertical (``Vertical.terminology_bindings``,
resolved through the registry in ``vertical.py``); the shared packs here
hold only domain-free bindings (laboratory analytes). Lookup order is
vertical first, then shared packs.
"""
from __future__ import annotations

from .store import InvalidInput

# Code-system registry: canonical URI -> availability record. The URI is
# the FHIR canonical system URI; ``availability`` is one of "available"
# (codes may be emitted and accepted), "no_pinned_codes" (the system is
# registered and free, but this slice pins no codes in it), or "blocked"
# (the system must never appear in an emitted or accepted coding).
TERMINOLOGY_SYSTEMS = {
    "http://loinc.org": {
        "name": "LOINC",
        "availability": "available",
        "license": "Freely available from the Regenstrief Institute.",
    },
    "http://hl7.org/fhir/sid/icd-10": {
        "name": "ICD-10",
        "availability": "available",
        "license": "Published by the World Health Organization.",
    },
    "http://www.nlm.nih.gov/research/umls/rxnorm": {
        "name": "RxNorm",
        "availability": "no_pinned_codes",
        "license": "Freely available from the U.S. National Library of Medicine.",
    },
    "http://snomed.info/sct": {
        "name": "SNOMED CT",
        "availability": "blocked",
        "license": "Requires an IHTSDO affiliate license; unresolved in this slice.",
    },
}

LOINC = "http://loinc.org"
ICD10 = "http://hl7.org/fhir/sid/icd-10"
RXNORM = "http://www.nlm.nih.gov/research/umls/rxnorm"
SNOMED = "http://snomed.info/sct"

# Shared modality packs: domain-free bindings, keyed by finding key.
# Each coding is {"system", "code", "display"}. The displays are the
# publishers' canonical long names for these long-stable codes.
MODALITY_PACKS = {
    "laboratory": {
        "systems": (LOINC,),
        "bindings": {
            # LOINC 718-7 Hemoglobin [Mass/volume] in Blood.
            "hemoglobin": (
                {"system": LOINC, "code": "718-7",
                 "display": "Hemoglobin [Mass/volume] in Blood"},
            ),
            # LOINC 2339-0 Glucose [Mass/volume] in Serum or Plasma.
            "glucose": (
                {"system": LOINC, "code": "2339-0",
                 "display": "Glucose [Mass/volume] in Serum or Plasma"},
            ),
            # LOINC 2160-0 Creatinine [Mass/volume] in Serum or Plasma.
            "creatinine": (
                {"system": LOINC, "code": "2160-0",
                 "display": "Creatinine [Mass/volume] in Serum or Plasma"},
            ),
        },
    },
    "pathology": {
        "systems": (ICD10,),
        "bindings": {},
    },
    "imaging": {
        "systems": (),
        "bindings": {},
    },
    "clinical": {
        "systems": (RXNORM,),
        "bindings": {},
    },
}


def system_status(system: str) -> dict:
    """Availability record for a code system URI, or a typed rejection."""
    record = TERMINOLOGY_SYSTEMS.get(system)
    if record is None:
        raise InvalidInput(f"unknown_terminology_system: {system}")
    return dict(record)


def codings_for(finding_key: str, vertical=None) -> tuple[dict, ...]:
    """Codings bound to a finding key: the vertical's first, then shared packs.

    A key with no binding returns an empty tuple — unbound, never
    fabricated. The caller (the FHIR export) records the unbound state
    instead of inventing a code.
    """
    if not isinstance(finding_key, str) or not finding_key:
        raise InvalidInput("finding key is required for a terminology lookup")
    if vertical is not None:
        bound = vertical.terminology_bindings.get(finding_key)
        if bound:
            return tuple(dict(coding) for coding in bound)
    for pack in MODALITY_PACKS.values():
        bound = pack["bindings"].get(finding_key)
        if bound:
            return tuple(dict(coding) for coding in bound)
    return ()


def _pinned_codes() -> set[tuple[str, str]]:
    """Every (system, code) the pinned table knows, verticals included."""
    known = set()
    for pack in MODALITY_PACKS.values():
        for codings in pack["bindings"].values():
            for coding in codings:
                known.add((coding["system"], coding["code"]))
    return known


def validate_coding(system: str, code: str, vertical=None) -> dict:
    """Validate one coding against the pinned table; fail closed.

    Unknown systems, blocked systems, and codes absent from the pinned
    table are all rejected with typed reasons — an inbound bundle can
    never smuggle in a code this slice cannot vouch for. Returns the
    canonical coding dict (system, code, display) from the table.
    """
    if not isinstance(system, str) or not isinstance(code, str) \
            or not system or not code:
        raise InvalidInput("terminology coding requires a system and a code")
    record = TERMINOLOGY_SYSTEMS.get(system)
    if record is None:
        raise InvalidInput(f"unknown_terminology_system: {system}")
    if record["availability"] == "blocked":
        raise InvalidInput(
            f"terminology_system_blocked: {record['name']} requires a license "
            "that is unresolved in this slice")
    known = _pinned_codes()
    if vertical is not None:
        for codings in vertical.terminology_bindings.values():
            for coding in codings:
                known.add((coding["system"], coding["code"]))
    if (system, code) not in known:
        raise InvalidInput(f"unknown_terminology_code: {system}|{code}")
    # Return the canonical display from wherever the code is pinned.
    if vertical is not None:
        for codings in vertical.terminology_bindings.values():
            for coding in codings:
                if coding["system"] == system and coding["code"] == code:
                    return dict(coding)
    for pack in MODALITY_PACKS.values():
        for codings in pack["bindings"].values():
            for coding in codings:
                if coding["system"] == system and coding["code"] == code:
                    return dict(coding)
    raise InvalidInput(f"unknown_terminology_code: {system}|{code}")


def terminology_table(vertical=None) -> dict:
    """The exchange terminology surface, for the GET terminology route.

    Systems with their availability and license notes, the modality
    packs with their pinned codes, and the vertical's own bindings —
    so a reader can see exactly what is bound, what is unbound, and
    what is blocked, with no silent gaps.
    """
    return {
        "systems": {uri: dict(record) for uri, record in TERMINOLOGY_SYSTEMS.items()},
        "modality_packs": {
            name: {
                "systems": list(pack["systems"]),
                "bindings": {
                    key: [dict(coding) for coding in codings]
                    for key, codings in pack["bindings"].items()
                },
            }
            for name, pack in MODALITY_PACKS.items()
        },
        "vertical": vertical.name if vertical is not None else None,
        "vertical_bindings": {
            key: [dict(coding) for coding in codings]
            for key, codings in (vertical.terminology_bindings.items()
                                 if vertical is not None else [])
        },
    }
