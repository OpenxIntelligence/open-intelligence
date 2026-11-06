"""HYPOTHESIS composition (REQ-09-10) + T5 deterministic report assembly (program plan slice D5).

Design (drafted first, per the plan's design-first rule for slices
that add a user-facing surface; implemented exactly as drafted):

HYPOTHESIS composition — a composed hypothesis is a proposal, never
an assertion. ``compose_hypothesis`` takes structured sentences,
each with its own claim-id citations, and a list of kept claims,
and returns either ``composed`` or ``rejected`` with typed
violations. The rules are REQ-09-10, enforced in code:

- ``over_length``: the joined text is at most 280 characters.
- ``missing_citation``: every sentence cites at least one claim id.
- ``unknown_claim``: every cited claim id resolves to a kept claim.
  Claim ids are deterministic: ``claim_id(investigation_id, index)``
  is ``inv{investigation_id}:c{index}`` (1-based within that
  investigation's kept claims), so a citation is checkable without
  any new table.
- ``unsupported_number`` / ``unsupported_identifier`` /
  ``unsupported_substance``: every number, identifier, and named
  substance in a sentence must appear in the text of the claims
  that sentence cites. A token absent from its cited claims is a
  new number/id/drug and the sentence is rejected. Token shapes
  mirror the K-checks (``kchecks.py`` is the canonical definition;
  the patterns are repeated here with that pointer so this module
  stays self-contained). Numbers compare by value (``31`` and
  ``31.0`` are the same number); identifiers compare lower-cased.
  The substance arm runs only when the caller supplies a
  ``substance_names`` vocabulary; with none supplied it is skipped
  and the result says so.
- ``scope_language``: no sentence may carry advice or verdict
  language — the domain-free guard (recommend, prescribe, dose,
  best treatment/therapy/option/drug, "you should", "should
  receive/take/undergo/start/stop") or any eligibility predicate
  (``eligible``, ``qualifies for``, ``can enroll``, ``meets the
  criteria``, ``inclusion criteria met``, ``enroll in this``). The
  eligibility predicates are mirrored in ``trials.py``; the D5 test
  file pins the two modules to agree on a shared probe set.
- ``malformed_identifier``: a malformed NCT/PMID/DOI token is
  rejected, using the K-checks' own ``malformed_identifiers``.
- ``missing_limits_phrase``: when the caller supplies evidence
  tiers and every cited claim with a known tier is low-tier (D/E,
  per ``kchecks.LOW_TIERS``), the joined text must carry the fixed
  limits phrase (``kchecks.TIER_LIMITS_PHRASE``) verbatim. With no
  tiers supplied, or no cited claim with a known tier, the arm is
  skipped and the result says so.
- A rejected composition returns no text: ``text`` is None, so a
  failed hypothesis can never be rendered as if it passed.

T5 report assembly — ``assemble_hypothesis_report`` deterministically
assembles the hypothesis-generation report from kept claims, pinned
literature records, pinned trial listings, an optional composed
hypothesis, and recorded abstentions. Fixed section order, lists
sorted by id, no timestamps unless the caller supplies ``as_of``.
The report states its own limits in its labels: the hypothesis is
"proposed, not asserted"; trial listings are "not eligibility
determinations"; literature is "metadata only". An empty input
produces an empty section, never invented content. No composed
hypothesis stored yet is reported as ``not_composed`` with its
reason — persistence of composed hypotheses is a follow-up (it
needs a store table and write-contract treatment), not something
this slice invents.

This module imports ``kchecks`` (core verification — allowed: only
dimension-to-dimension imports are forbidden) and no other
dimension module.
"""

from __future__ import annotations

import copy
import re

from .kchecks import LOW_TIERS, TIER_LIMITS_PHRASE, malformed_identifiers

MAX_HYPOTHESIS_CHARS = 280

# Scope language a composed hypothesis must never carry: the
# domain-free advice guard (mirroring investigation.GUARD_PATTERNS)
# plus the eligibility predicates (mirroring trials.ELIGIBILITY_PREDICATES).
_SCOPE_PATTERNS: tuple[tuple[str, "re.Pattern[str]"], ...] = (
    ("recommend", re.compile(r"\brecommend\w*\b", re.IGNORECASE)),
    ("should_receive", re.compile(r"\bshould (receive|be treated|take|undergo|start|stop)\b", re.IGNORECASE)),
    ("prescribe", re.compile(r"\bprescri\w*\b", re.IGNORECASE)),
    ("dose", re.compile(r"\bdos(e|age)\b", re.IGNORECASE)),
    ("best_option", re.compile(r"\bbest (treatment|therapy|option|drug)\b", re.IGNORECASE)),
    ("you_should", re.compile(r"\byou should\b", re.IGNORECASE)),
    ("eligible", re.compile(r"\beligib\w*\b", re.IGNORECASE)),
    ("qualifies_for", re.compile(r"\bqualif\w+ for\b", re.IGNORECASE)),
    ("can_enroll", re.compile(r"\b(can|may|could) enroll\b", re.IGNORECASE)),
    ("meets_criteria", re.compile(r"\bmeets? (the )?(inclusion )?criteria\b", re.IGNORECASE)),
    ("criteria_met", re.compile(r"\binclusion criteria (met|satisfied|fulfilled)\b", re.IGNORECASE)),
    ("enroll_in_this", re.compile(r"\benrol\w+ (in|into) this\b", re.IGNORECASE)),
)

# Token shapes, mirroring kchecks.py (the canonical definition).
_NUMBER_RE = re.compile(r"(?<!\w)(\d+(?:\.\d+)?)(?!\w)")
_NCT_TOKEN_RE = re.compile(r"\bNCT[0-9A-Za-z]*\b")
_PMID_TOKEN_RE = re.compile(r"\bPMID\s*:?\s*([0-9A-Za-z]+)?")
_DOI_TOKEN_RE = re.compile(r"10\.\d{4,}(?:/[^\s,;)]*)?")
_FICT_TOKEN_RE = re.compile(r"\bFICT-[A-Z0-9]+(?:-[A-Z0-9]+)*\b")
_ENSG_TOKEN_RE = re.compile(r"\bENSG\d{11}\b")

# Fixed labels carried by every assembled report. Tests pin these verbatim.
HYPOTHESIS_LABEL = "HYPOTHESIS — proposed, not asserted; rests only on the kept claims listed above."
TRIALS_LABEL = "Registry listings — not eligibility determinations."
LITERATURE_LABEL = "Bibliographic metadata only — no full text, no findings."
DATA_LABEL = "Fictional demo data — not a real patient."


def claim_id(investigation_id: int, index: int) -> str:
    """Deterministic claim id: ``inv{investigation_id}:c{index}`` (1-based)."""
    return f"inv{investigation_id}:c{index}"


def _numbers(text: str) -> list[str]:
    return _NUMBER_RE.findall(text or "")


def _number_value(token: str) -> float | None:
    try:
        return float(token)
    except (TypeError, ValueError):
        return None


def _identifiers(text: str) -> list[str]:
    found: list[str] = []
    found.extend(_NCT_TOKEN_RE.findall(text or ""))
    for match in _PMID_TOKEN_RE.finditer(text or ""):
        found.append(match.group(0).strip())
    found.extend(_DOI_TOKEN_RE.findall(text or ""))
    found.extend(_FICT_TOKEN_RE.findall(text or ""))
    found.extend(_ENSG_TOKEN_RE.findall(text or ""))
    return found


def _check_sentence(sentence: dict, index: int, kept_by_id: dict) -> list[dict]:
    """Typed violations for one sentence against its cited kept claims."""
    violations: list[dict] = []
    text = sentence.get("text") if isinstance(sentence, dict) else None
    if not isinstance(text, str) or not text.strip():
        return [{"sentence_index": index, "reason": "missing_text"}]
    text = text.strip()
    for bad in malformed_identifiers(text):
        violations.append({
            "sentence_index": index, "reason": "malformed_identifier",
            "detail": bad,
        })
    claim_ids = sentence.get("claim_ids")
    if not isinstance(claim_ids, list) or not claim_ids:
        violations.append({"sentence_index": index, "reason": "missing_citation"})
        return violations
    cited = []
    for cited_id in claim_ids:
        claim = kept_by_id.get(cited_id)
        if claim is None:
            violations.append({
                "sentence_index": index, "reason": "unknown_claim",
                "detail": {"claim_id": cited_id},
            })
        else:
            cited.append(claim)
    if violations:
        return violations
    for name, pattern in _SCOPE_PATTERNS:
        if pattern.search(text):
            violations.append({
                "sentence_index": index, "reason": "scope_language",
                "detail": {"predicate": name},
            })
            break
    evidence = "\n".join(str(claim.get("text", "")) for claim in cited)
    evidence_numbers = {_number_value(token) for token in _numbers(evidence)}
    evidence_numbers.discard(None)
    for token in _numbers(text):
        if _number_value(token) not in evidence_numbers:
            violations.append({
                "sentence_index": index, "reason": "unsupported_number",
                "detail": {"token": token},
            })
    evidence_identifiers = {token.lower() for token in _identifiers(evidence)}
    for token in _identifiers(text):
        if token.lower() not in evidence_identifiers:
            violations.append({
                "sentence_index": index, "reason": "unsupported_identifier",
                "detail": {"token": token},
            })
    return violations


def _check_substances(sentence_text: str, index: int, cited: list[dict],
                      substance_names) -> list[dict]:
    """A named substance in the sentence must appear in its cited claims."""
    violations: list[dict] = []
    evidence = "\n".join(str(claim.get("text", "")) for claim in cited).lower()
    for substance in substance_names or ():
        if substance.lower() in sentence_text.lower() and substance.lower() not in evidence:
            violations.append({
                "sentence_index": index, "reason": "unsupported_substance",
                "detail": {"substance": substance},
            })
    return violations


def compose_hypothesis(sentences, kept_claims, *, tiers=None, substance_names=()):
    """Validate a structured HYPOTHESIS composition per REQ-09-10.

    ``sentences`` is a list of ``{"text": str, "claim_ids": [str]}``;
    ``kept_claims`` is a list of ``{"id": str, "text": str, ...}``.
    ``tiers`` optionally maps claim id to evidence tier; ``substance_names``
    optionally supplies the named-substance vocabulary. Returns
    ``{"status": "composed"|"rejected", "text": str|None, "sentences": [...],
    "claim_ids": [...], "char_count": int, "violations": [...],
    "substance_check": "checked"|"skipped", "tier_check": "checked"|"skipped"}``.
    A rejected composition returns no text.
    """
    kept_by_id = {}
    for claim in kept_claims or []:
        if isinstance(claim, dict) and isinstance(claim.get("id"), str):
            kept_by_id[claim["id"]] = claim
    violations: list[dict] = []
    if not isinstance(sentences, list) or not sentences:
        violations.append({"sentence_index": None, "reason": "empty_hypothesis"})
        return {
            "status": "rejected", "text": None, "sentences": [],
            "claim_ids": [], "char_count": 0, "violations": violations,
            "substance_check": "skipped", "tier_check": "skipped",
        }
    clean_sentences: list[dict] = []
    all_claim_ids: list[str] = []
    for index, sentence in enumerate(sentences):
        found = _check_sentence(sentence, index, kept_by_id)
        violations.extend(found)
        if isinstance(sentence, dict) and isinstance(sentence.get("text"), str):
            clean_sentences.append({
                "text": sentence["text"].strip(),
                "claim_ids": list(sentence.get("claim_ids") or []),
            })
            all_claim_ids.extend(sentence.get("claim_ids") or [])
        if not found:
            cited = [kept_by_id[cited_id] for cited_id in sentence.get("claim_ids", [])]
            violations.extend(_check_substances(
                sentence["text"], index, cited, substance_names))
    joined = " ".join(item["text"] for item in clean_sentences)
    if len(joined) > MAX_HYPOTHESIS_CHARS:
        violations.append({
            "sentence_index": None, "reason": "over_length",
            "detail": {"chars": len(joined), "limit": MAX_HYPOTHESIS_CHARS},
        })
    substance_check = "checked" if substance_names else "skipped"
    tier_check = "skipped"
    if tiers:
        known = [tiers.get(cited_id) for cited_id in dict.fromkeys(all_claim_ids)
                 if tiers.get(cited_id) is not None]
        if known and all(str(tier).strip().lower() in LOW_TIERS for tier in known):
            tier_check = "checked"
            if TIER_LIMITS_PHRASE not in joined:
                violations.append({
                    "sentence_index": None, "reason": "missing_limits_phrase",
                })
    if violations:
        return {
            "status": "rejected", "text": None, "sentences": clean_sentences,
            "claim_ids": sorted(set(all_claim_ids)), "char_count": len(joined),
            "violations": violations,
            "substance_check": substance_check, "tier_check": tier_check,
        }
    return {
        "status": "composed", "text": joined, "sentences": clean_sentences,
        "claim_ids": sorted(set(all_claim_ids)), "char_count": len(joined),
        "violations": [],
        "substance_check": substance_check, "tier_check": tier_check,
    }


def assemble_hypothesis_report(case_id, kept_claims, literature_records, trial_listings,
                               *, hypothesis=None, abstentions=(), as_of=None):
    """T5: deterministically assemble the hypothesis-generation report.

    ``kept_claims`` is a list of ``{"id", "text", "uncertainty",
    "citations"}``; ``literature_records`` and ``trial_listings`` are
    the pinned A4/A5 records (listings already rendered with their
    fixed label by the caller, or raw listings — both are accepted
    and rendered here); ``hypothesis`` is a ``compose_hypothesis``
    result or None; ``abstentions`` is a list of ``{"topic",
    "reason"}``. The report is a plain dict with fixed section
    order; lists are sorted by id; nothing is invented for empty
    inputs.
    """
    claims = sorted(
        ({"id": claim["id"], "text": claim.get("text", ""),
          "uncertainty": claim.get("uncertainty", ""),
          "citations": copy.deepcopy(claim.get("citations", []))}
         for claim in kept_claims or []
         if isinstance(claim, dict) and isinstance(claim.get("id"), str)),
        key=lambda item: item["id"],
    )
    records = sorted(
        (copy.deepcopy(record) for record in literature_records or []
         if isinstance(record, dict) and isinstance(record.get("record_id"), str)),
        key=lambda item: item["record_id"],
    )
    listings = []
    for listing in trial_listings or []:
        if isinstance(listing, dict) and "listing" in listing:
            listings.append(copy.deepcopy(listing))
        elif isinstance(listing, dict) and isinstance(listing.get("listing_id"), str):
            # Raw listing: attach the per-listing label. The literal
            # mirrors trials.LISTING_LABEL (this module cannot import
            # the trials dimension module); the route passes listings
            # already rendered by trials.render_listing.
            listings.append({"label": "Registry listing — not an eligibility determination.",
                             "listing": copy.deepcopy(listing)})
    listings.sort(key=lambda item: item["listing"].get("listing_id", ""))
    if hypothesis is None:
        hypothesis_section = {
            "status": "not_composed",
            "text": None,
            "claim_ids": [],
            "char_count": 0,
            "reason": "No composed hypothesis stored for this case.",
        }
    else:
        hypothesis_section = {
            "status": hypothesis.get("status"),
            "text": hypothesis.get("text"),
            "claim_ids": list(hypothesis.get("claim_ids", [])),
            "char_count": hypothesis.get("char_count", 0),
            "reason": None,
        }
    return {
        "case_id": case_id,
        "generated_as_of": as_of,
        "labels": {
            "hypothesis": HYPOTHESIS_LABEL,
            "trials": TRIALS_LABEL,
            "literature": LITERATURE_LABEL,
            "data": DATA_LABEL,
        },
        "kept_claims": claims,
        "hypothesis": hypothesis_section,
        "literature": {
            "records": records,
            "note": "Pinned synthetic fixtures, not matched to this case; metadata only.",
        },
        "trials": {
            "listings": listings,
            "note": "Pinned synthetic fixtures, not matched to this case.",
        },
        "abstentions": [{"topic": item.get("topic", ""), "reason": item.get("reason", "")}
                        for item in abstentions or []
                        if isinstance(item, dict)],
        "counts": {
            "kept_claims": len(claims),
            "literature_records": len(records),
            "trial_listings": len(listings),
            "abstentions": len(abstentions or []),
        },
    }
