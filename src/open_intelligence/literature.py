"""A4 Literature — bibliographic records, metadata only (program plan slice D5).

Design (drafted first, per the plan's design-first rule for slices
that add a user-facing surface; implemented exactly as drafted):

- A literature record is bibliographic metadata only: record id,
  source registry, title, authors, journal, year, DOI, topics.
  No full text, no findings, no efficacy claim, no conclusion ever
  rides on a record. A record carrying any of those fields is
  rejected by ``validate_literature_record`` with reason
  ``carries_findings`` — metadata only is enforced in code, not
  just in copy.
- The records are pinned synthetic fixtures standing in for the
  three named registries (Europe PMC, Crossref, OpenAlex). No live
  fetch exists in this slice: there is no network call anywhere in
  this module, and no record is presented as a live lookup result.
  Every record carries ``synthetic: True`` and an id in the pinned
  ``LIT-`` namespace; a record without the synthetic flag is
  rejected with ``not_synthetic``. A live fetch against a registry
  is future work, not something this slice pretends to do.
- DOIs use the ``10.0000/`` example prefix (the standard
  documentation prefix, never a real registrant) plus
  ``oi-synth-lit-NNNN``. The DOI shape is checked with the same
  rule as the K-checks' identifier format (``kchecks``); a
  malformed DOI is rejected with ``malformed_doi``.
- Lookup is keyword matching over title and topics, case
  insensitive. It returns copies of the pinned records, never the
  fixtures themselves, so callers cannot mutate the registry.
- This module imports no other dimension module. It is the A4
  toolset; cross-dimension interaction happens only through the
  ledger and ``route.decided``.
"""

from __future__ import annotations

import copy
import re

# The three registries the plan names for A4. A record must name one
# of them; anything else is rejected with ``unknown_source``.
SOURCES = ("europe-pmc", "crossref", "openalex")

# Required metadata fields on every record. ``topics`` may be empty;
# every other field must be present and non-empty.
REQUIRED_FIELDS = ("record_id", "source", "title", "authors", "journal", "year", "doi")

# Keys that must never appear with a value on a record: a literature
# record is metadata only. A record carrying any of these is rejected
# with ``carries_findings``.
FINDINGS_KEYS = ("findings", "efficacy", "conclusion", "results", "abstract")

_DOI_OK_RE = re.compile(r"^10\.\d{4,9}/[^\s,;)]+$")

# Pinned synthetic records. Titles, authors, and journals are
# invented; no record describes a real publication, and no DOI
# resolves to a real registrant (``10.0000`` is the documentation
# prefix). Topics span both built-in verticals so the dimension
# stays vertical-neutral: the vertical interface, not this module,
# carries domain rules.
PINNED_RECORDS: tuple[dict, ...] = (
    {
        "record_id": "LIT-0001",
        "source": "europe-pmc",
        "title": "Longitudinal patterns in synthetic laboratory series: a methods note",
        "authors": ["A. Reyes", "B. Okafor"],
        "journal": "Journal of Synthetic Clinical Methods",
        "year": 2025,
        "doi": "10.0000/oi-synth-lit-0001",
        "topics": ["longitudinal", "laboratory"],
        "synthetic": True,
    },
    {
        "record_id": "LIT-0002",
        "source": "crossref",
        "title": "Specimen chain integrity in multi-site record exchange",
        "authors": ["C. Haddad"],
        "journal": "Synthetic Health Informatics Quarterly",
        "year": 2024,
        "doi": "10.0000/oi-synth-lit-0002",
        "topics": ["specimen", "interoperability"],
        "synthetic": True,
    },
    {
        "record_id": "LIT-0003",
        "source": "openalex",
        "title": "Imaging comparison across synthetic cardiology cohorts",
        "authors": ["D. Kim", "E. Novak"],
        "journal": "Journal of Synthetic Cardiology",
        "year": 2025,
        "doi": "10.0000/oi-synth-lit-0003",
        "topics": ["imaging", "cardiology"],
        "synthetic": True,
    },
    {
        "record_id": "LIT-0004",
        "source": "europe-pmc",
        "title": "Line-of-therapy counting rules: a versioned-ruleset description",
        "authors": ["F. Almeida"],
        "journal": "Synthetic Oncology Review",
        "year": 2023,
        "doi": "10.0000/oi-synth-lit-0004",
        "topics": ["therapy", "oncology"],
        "synthetic": True,
    },
    {
        "record_id": "LIT-0005",
        "source": "crossref",
        "title": "Patient-reported symptom notes as ordered records",
        "authors": ["G. Meyer", "H. Tanaka"],
        "journal": "Journal of Synthetic Care Research",
        "year": 2025,
        "doi": "10.0000/oi-synth-lit-0005",
        "topics": ["symptoms", "patient-reported"],
        "synthetic": True,
    },
    {
        "record_id": "LIT-0006",
        "source": "openalex",
        "title": "Trial registry listings and the eligibility boundary",
        "authors": ["I. Petrov"],
        "journal": "Synthetic Health Informatics Quarterly",
        "year": 2024,
        "doi": "10.0000/oi-synth-lit-0006",
        "topics": ["trials", "eligibility"],
        "synthetic": True,
    },
)


def validate_literature_record(record: object) -> list[dict]:
    """Typed problems with a literature record; empty means valid.

    Reasons: ``not_a_record`` (not a dict), ``missing_field``,
    ``not_synthetic``, ``unknown_source``, ``malformed_doi``,
    ``bad_year``, ``carries_findings``. A record with any problem
    must never be presented as a literature result.
    """
    if not isinstance(record, dict):
        return [{"reason": "not_a_record"}]
    problems: list[dict] = []
    for field_name in REQUIRED_FIELDS:
        value = record.get(field_name)
        if value is None or (isinstance(value, str) and not value.strip()):
            problems.append({"reason": "missing_field", "field": field_name})
        elif field_name == "authors" and not isinstance(value, list):
            problems.append({"reason": "missing_field", "field": field_name})
    if record.get("synthetic") is not True:
        problems.append({"reason": "not_synthetic"})
    source = record.get("source")
    if isinstance(source, str) and source and source not in SOURCES:
        problems.append({"reason": "unknown_source", "source": source})
    doi = record.get("doi")
    if isinstance(doi, str) and doi.strip() and not _DOI_OK_RE.match(doi.strip()):
        problems.append({"reason": "malformed_doi", "doi": doi})
    year = record.get("year")
    if year is not None and (type(year) is not int or not 1900 <= year <= 2100):
        problems.append({"reason": "bad_year", "year": year})
    for key in FINDINGS_KEYS:
        if record.get(key):
            problems.append({"reason": "carries_findings", "field": key})
    return problems


def list_records(topic: str | None = None) -> list[dict]:
    """Pinned synthetic records, optionally filtered by a topic keyword.

    Matching is a case-insensitive substring over the title and the
    topics. Returns deep copies; the pinned registry is never handed
    out mutably. With no topic, every pinned record is returned in
    pinned order.
    """
    records = [copy.deepcopy(record) for record in PINNED_RECORDS]
    if topic is None or not str(topic).strip():
        return records
    needle = str(topic).strip().lower()
    kept = []
    for record in records:
        haystack = " ".join([record["title"]] + list(record.get("topics", []))).lower()
        if needle in haystack:
            kept.append(record)
    return kept


def get_record(record_id: str) -> dict | None:
    """One pinned record by id, or None. Returns a copy."""
    for record in PINNED_RECORDS:
        if record["record_id"] == record_id:
            return copy.deepcopy(record)
    return None
