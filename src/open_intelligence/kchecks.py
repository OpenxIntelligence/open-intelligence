"""Deterministic K-checks K1-K7 for bounded investigation output.

Program plan slice C2; spec Notion OI-09 section 4.6 ("Checks,
abstention codes and the adversarial set"). This module is the
verification dimension's deterministic half: it checks claims the
structural validator (`open_intelligence.investigation.validate_output`)
already kept, against the case ledger, and drops any claim that fails
a check. A failure goes to `dropped` with a typed reason, never
silently repaired.

The checks, in the order they run over each kept claim:

- K1 citation format: identifier tokens in claim text (registry
  numbers, publication ids, object ids) must be well formed.
  (Citation existence itself is the structural validator's job.)
- K3 cite rule: a claim may only cite a version recorded at or before
  the run snapshot. Internal version date order (specimen <= report
  <= received) and slot range order are case-data findings, not
  drops: they say the ledger is inconsistent, not that the claim is.
- K5 staleness: a claim may not cite a version outside the snapshot,
  and a changed snapshot hash or ruleset is a run-level finding.
  (Citing a superseded version is caught earlier, in the structural
  validator, which consults this module's context and drops it with
  reason ``k5_stale`` instead of ``unresolved_citation``.)
- K2 slot-field match: every (field, value) pair the claim asserts
  must equal the cited facet for that field, after normalisation.
  A claim that asserts a field none of its cited sources covers is
  dropped. The condition-scope sub-check keeps a broader/narrower
  relation with a limits note and drops an unrelated one.
- K6 scope guard: the vertical's extra scope patterns, beyond the
  structural validator's language guard.
- K7 support: every number, identifier, and named-substance token in
  the claim must appear in the cited evidence. Low-tier or
  case-report-only or preclinical support must carry the fixed limits
  phrase. K7+ injection: markers of injected instructions in the
  claim text or in the cited evidence drop the claim.
- K4 contradiction: over the survivors, two claims asserting
  different normalised values for the same subject and field, with
  overlapping valid time and no supersession between their versions,
  contradict; the later claim is dropped. Different specimens or
  assays never auto-supersede, and neither does a mere difference:
  both present and different means no contradiction.

Vertical neutrality
-------------------
This module is domain-free: it contains no vertical knowledge of its
own. Every vertical-specific input arrives as a parameter — the
synonym map, the scope patterns, the condition terms, the
scope-relation callable, the named-substance list, and the evidence
tiers. The caller (the vertical wiring in `investigation.py` and
`__main__.py`) supplies them. A test scans this module's source for
forbidden vertical literals; if a vertical term ever leaks in here,
that test fails.

Honest limits of the deterministic layer
----------------------------------------
- Slot assertion is derived lexically: a claim is read as asserting a
  (field, value) pair when it names a derived field and, within two
  words of that mention, a value word from the closed vocabulary of
  the case's own values (after synonym normalisation). The nearest
  value word wins, preferring the one after the mention on a tie; a
  tie between different values on the same side yields no slot. A
  claim that paraphrases a value outside that vocabulary is not
  slot-checked: indeterminate, never a violation.
- K7 covers numbers, formatted identifiers, and the supplied
  named-substance list. Free-text entity invention outside those
  classes is not deterministically detectable without a vocabulary;
  judging prose meaning is the Skeptic's job (slice C4), not this
  module's.
- The condition-scope, evidence-tier, and named-substance sub-checks
  are interface-complete but data-pending in the live path: no
  relation data, tier data, or substance vocabulary exists in the
  runtime yet, so the wiring passes empty values and those sub-checks
  skip live. They run in tests.
- K7+ atomic statement (every hypothesis sentence carrying an inline
  derived-from id) needs per-sentence citations, a schema and prompt
  change, and is out of this slice.
- Findings are returned on the validated result but are not persisted
  by `save_investigation` in this slice; persisting them is a schema
  change and a follow-up.
"""

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass, field
from datetime import datetime

# Fixed limits phrase a claim must carry when its support is low-tier,
# case-report-only, or preclinical. The spec names "the fixed limits
# phrase" without giving its text; this constant is this slice's
# definition of it, and tests pin it verbatim.
TIER_LIMITS_PHRASE = (
    "Limited evidence: low-tier, case-report-only, or preclinical support. "
    "Treat as a hypothesis for expert review, not a conclusion."
)

# Evidence tiers that trigger the K7 tier guard. Compared lower-cased
# after stripping; the caller supplies the tier per cited item.
LOW_TIERS = frozenset({"d", "e", "e-", "case-report", "case report", "preclinical"})

# Generic markers of injected instructions, in claim text or in cited
# evidence. These are instruction-shaped phrases, not vertical content.
INJECTION_MARKERS = (
    "ignore previous instructions",
    "ignore the above",
    "ignore all previous",
    "disregard previous",
    "disregard the above",
    "you must recommend",
    "you should recommend",
    "system prompt",
    "override",
    "jailbreak",
    "do not mention",
    "do not disclose",
    "new instructions",
    "as an ai",
)

# Identifier formats (K1). A token that looks like one of these but is
# not well formed is a K1 failure; a well-formed token is checked for
# support by K7.
_NCT_TOKEN_RE = re.compile(r"\bNCT[0-9A-Za-z]*\b")
_NCT_OK_RE = re.compile(r"^NCT\d{8}$")
_PMID_TOKEN_RE = re.compile(r"\bPMID\s*:?\s*([0-9A-Za-z]+)?")
_DOI_TOKEN_RE = re.compile(r"10\.\d{4,}(?:/[^\s,;)]*)?")
_DOI_OK_RE = re.compile(r"^10\.\d{4,9}/[^\s,;)]+$")
_FICT_TOKEN_RE = re.compile(r"\bFICT-[A-Z0-9]+(?:-[A-Z0-9]+)*\b")
_ENSG_TOKEN_RE = re.compile(r"\bENSG\d{11}\b")
_NUMBER_RE = re.compile(r"(?<!\w)(\d+(?:\.\d+)?)(?!\w)")
_DATE_RE = re.compile(r"\b\d{4}-\d{2}-\d{2}\b")

# Nearest-value window for lexical slot derivation, in words. Kept
# tight so a value word is not attributed to a field mentioned
# earlier in the same sentence about something else.
_SLOT_WINDOW = 2


@dataclass
class SourceVersionInfo:
    """One ledger version, as the K-checks need it. Dates are the
    ledger's own strings; specimen_date is the event date, report_date
    the issued date, received_date the receipt timestamp."""

    id: int
    specimen_date: str | None = None
    report_date: str | None = None
    received_date: str | None = None
    state: str = "current"
    supersedes_id: int | None = None
    sha256: str = ""
    specimen_id: str | None = None
    kind: str | None = None


@dataclass
class Slot:
    """One derived slot: a (field, value) pair asserted by the ledger
    for a subject, with its evidence text and provenance. The value is
    the ledger's own certainty word for the field; `quote` is the exact
    source text the value rests on."""

    subject: str
    field: str
    value: str
    source_version_id: int
    specimen: str | None = None
    assay: str | None = None
    valid_from: str | None = None
    valid_to: str | None = None
    quote: str = ""


@dataclass
class KCheckContext:
    """Everything the K-checks need, assembled by the caller from the
    ledger. All vertical knowledge arrives here as data; none of it
    lives in this module."""

    subject: str
    source_versions: dict[int, SourceVersionInfo] = field(default_factory=dict)
    derived_slots: list[Slot] = field(default_factory=list)
    # Assessment id -> human-authored statement text.
    assessment_statements: dict[int, str] = field(default_factory=dict)
    # ISO instant the run snapshot was taken; versions received after
    # it may not be cited.
    snapshot_as_of: str | None = None
    # Source version ids in the snapshot. Empty means no snapshot is
    # pinned and the membership sub-check skips.
    snapshot_source_ids: set[int] = field(default_factory=set)
    # Snapshot content hash at facts time vs at validation time.
    # Both supplied and different means the snapshot changed mid-run.
    expected_snapshot_hash: str | None = None
    current_snapshot_hash: str | None = None
    # Ruleset version at facts time vs at validation time.
    lot_ruleset: str | None = None
    current_lot_ruleset: str | None = None
    # Phrase -> canonical value, e.g. "not tested" -> "not-reported".
    # Keys are matched after normalisation; see normalise_value.
    synonyms: dict[str, str] = field(default_factory=dict)
    # Extra scope patterns beyond the structural language guard
    # (compiled regexes, supplied by the vertical wiring).
    scope_patterns: list = field(default_factory=list)
    # Terms naming a condition, for the "you have" scope pattern.
    condition_terms: list[str] = field(default_factory=list)
    # Callable (case_condition, mentioned_term) -> one of "related",
    # "broader", "narrower", "unrelated". None means the sub-check
    # skips (no relation data yet).
    scope_relation: object = None
    case_condition: str | None = None
    # Named-substance vocabulary of the vertical (empty: skipped).
    substance_names: list[str] = field(default_factory=list)
    # Cited-item id -> evidence tier string (empty: skipped).
    evidence_tiers: dict[int, str] = field(default_factory=dict)


@dataclass
class KCheckResult:
    kept: list[dict]
    dropped: list[dict]
    findings: list[dict]


def _normalise_words(text: str) -> str:
    """Lower-case and collapse every non-alphanumeric run to one space."""
    return re.sub(r"[^a-z0-9]+", " ", text.lower()).strip()


def normalise_value(value: str, synonyms: dict[str, str]) -> str:
    """Normalise a value word through the synonym map. Both the value
    and the map keys are normalised first, so "not-reported", "not
    reported" and "not tested" all land on the same canonical form."""
    normalised = _normalise_words(value)
    table = {_normalise_words(key): target for key, target in synonyms.items()}
    return _normalise_words(table.get(normalised, normalised))


def _parse_partial_date(value: str | None):
    """Parse YYYY, YYYY-MM, or YYYY-MM-DD. Returns (precision, (year,
    month, day)) with missing parts 0, or None when unparseable."""
    if not isinstance(value, str):
        return None
    text = value.strip()
    for separator in ("T", " "):
        if separator in text:
            text = text.split(separator)[0]
    match = re.fullmatch(r"(\d{4})(?:-(\d{2})(?:-(\d{2}))?)?", text)
    if not match:
        return None
    year = int(match.group(1))
    month = int(match.group(2)) if match.group(2) else 0
    day = int(match.group(3)) if match.group(3) else 0
    if month and not 1 <= month <= 12:
        return None
    if day and not 1 <= day <= 31:
        return None
    precision = 3 if match.group(3) else (2 if match.group(2) else 1)
    return (precision, (year, month, day))


def compare_partial_dates(first: str | None, second: str | None):
    """Compare two partial dates at the coarser precision. Returns -1,
    0, or 1, or None when the comparison is indeterminate: the two
    agree at the coarser precision, or either is unparseable. An
    indeterminate comparison is never a violation."""
    parsed_first = _parse_partial_date(first)
    parsed_second = _parse_partial_date(second)
    if parsed_first is None or parsed_second is None:
        return None
    precision = min(parsed_first[0], parsed_second[0])
    left = parsed_first[1][:precision]
    right = parsed_second[1][:precision]
    if left == right:
        return None
    return -1 if left < right else 1


def _parse_instant(value: str | None):
    """Parse an ISO instant (with Z, offset, or fractional seconds) to
    a datetime, or None when unparseable."""
    if not isinstance(value, str) or not value.strip():
        return None
    text = value.strip()
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    try:
        return datetime.fromisoformat(text)
    except ValueError:
        return None


def snapshot_hash(source_version_rows) -> str:
    """Content hash of the current source versions of a case: sha256
    over the sorted per-version digests. A changed hash means the
    snapshot's contents changed."""
    digests = sorted(
        str(row["sha256"]) for row in source_version_rows
        if row.get("state") == "current" and row.get("sha256")
    )
    return hashlib.sha256("\n".join(digests).encode("utf-8")).hexdigest()


def _supersedes(versions: dict[int, SourceVersionInfo], newer_id: int, older_id: int) -> bool:
    """True when the version chain from `newer_id` reaches `older_id`
    through supersedes links."""
    seen = set()
    current = versions.get(newer_id)
    while current is not None and current.supersedes_id is not None:
        if current.supersedes_id == older_id:
            return True
        if current.supersedes_id in seen:
            return False
        seen.add(current.supersedes_id)
        current = versions.get(current.supersedes_id)
    return False


def _value_vocabulary(slots: list[Slot], synonyms: dict[str, str]) -> dict[str, str]:
    """The closed vocabulary of values a claim can assert: every
    normalised phrase that maps to a canonical value present in the
    derived slots, including synonym expansions of those values."""
    vocabulary: dict[str, str] = {}
    canonicals = {normalise_value(slot.value, synonyms) for slot in slots}
    for phrase, target in synonyms.items():
        canonical = normalise_value(target, synonyms)
        if canonical in canonicals:
            vocabulary[_normalise_words(phrase)] = canonical
    for canonical in canonicals:
        vocabulary[canonical] = canonical
    return vocabulary


def derive_claim_slots(claim_text: str, slots: list[Slot],
                       synonyms: dict[str, str]) -> list[dict]:
    """Lexically derive the (field, value) pairs a claim asserts.

    A claim asserts a pair when it names a derived field and, within
    two words of that mention, a value word from the closed vocabulary
    (after synonym normalisation). The nearest value word wins; a tie
    between different values yields no slot. A claim that paraphrases
    a value outside the vocabulary asserts nothing here: indeterminate,
    never a violation. Returns [{"field", "value"}] with canonical
    values."""
    words = _normalise_words(claim_text).split()
    if not words or not slots:
        return []
    vocabulary = _value_vocabulary(slots, synonyms)
    occurrences: list[tuple[int, int, str]] = []
    for phrase, canonical in vocabulary.items():
        phrase_words = phrase.split()
        for start in range(len(words) - len(phrase_words) + 1):
            if words[start:start + len(phrase_words)] == phrase_words:
                occurrences.append((start, start + len(phrase_words), canonical))
    key_words = {slot.field: set(_normalise_words(slot.field).split()) for slot in slots}
    phrase_mentions: list[tuple[int, int, str]] = []
    word_mentions: list[tuple[int, int, str]] = []
    for slot in slots:
        field_words = _normalise_words(slot.field).split()
        for start in range(len(words) - len(field_words) + 1):
            if words[start:start + len(field_words)] == field_words:
                phrase_mentions.append((start, start + len(field_words), slot.field))
        for word in field_words:
            if len(word) < 4:
                continue
            owners = [name for name, words_in_key in key_words.items() if word in words_in_key]
            if len(owners) != 1:
                continue
            for index, candidate in enumerate(words):
                if candidate == word:
                    word_mentions.append((index, index + 1, slot.field))
    # A single-word mention inside a phrase mention for the same field
    # is the same mention, not a second one: drop it, or it would
    # overwrite the phrase mention's attribution with a nearer value
    # word that belongs to the neighbouring field.
    mentions = list(phrase_mentions)
    for start, end, field_name in word_mentions:
        if any(start < phrase_end and phrase_start < end and name == field_name
               for phrase_start, phrase_end, name in phrase_mentions):
            continue
        mentions.append((start, end, field_name))
    asserted: dict[str, str] = {}
    for mention_start, mention_end, field_name in mentions:
        best: tuple[int, int, str | None] | None = None
        for value_start, value_end, canonical in occurrences:
            if value_end <= mention_start:
                distance = mention_start - value_end
                follows = 0
            elif mention_end <= value_start:
                distance = value_start - mention_end
                follows = 1
            else:
                distance = 0
                follows = 1
            if distance > _SLOT_WINDOW:
                continue
            # Nearest wins; on a tie prefer the value after the mention
            # (the value normally follows its subject), and a tie between
            # different values on the same side is indeterminate.
            if best is None or distance < best[0] or (
                    distance == best[0] and follows > best[1]):
                best = (distance, follows, canonical)
            elif distance == best[0] and follows == best[1] and best[2] != canonical:
                best = (distance, follows, None)
        if best is not None and best[2] is not None:
            asserted[field_name] = best[2]
    return [{"field": name, "value": value} for name, value in asserted.items()]


def malformed_identifiers(text: str) -> list[dict]:
    """Identifier tokens in the text that are not well formed, as
    {"token", "kind"} with kind nct, pmid, or doi. A well-formed
    token is not malformed; whether it is supported is K7's job."""
    found: list[dict] = []
    for token in _NCT_TOKEN_RE.findall(text):
        if not _NCT_OK_RE.match(token):
            found.append({"token": token, "kind": "nct"})
    for match in _PMID_TOKEN_RE.finditer(text):
        digits = match.group(1)
        if digits is None or not digits.isdigit():
            found.append({"token": match.group(0).strip(), "kind": "pmid"})
    for token in _DOI_TOKEN_RE.findall(text):
        if not _DOI_OK_RE.match(token):
            found.append({"token": token, "kind": "doi"})
    return found


def _identifier_tokens(text: str) -> list[dict]:
    """Well-formed identifier tokens in the text, as {"token", "kind"}."""
    tokens: list[dict] = []
    for token in _NCT_TOKEN_RE.findall(text):
        if _NCT_OK_RE.match(token):
            tokens.append({"token": token, "kind": "nct"})
    for match in _PMID_TOKEN_RE.finditer(text):
        digits = match.group(1)
        if digits is not None and digits.isdigit():
            tokens.append({"token": digits, "kind": "pmid"})
    for token in _DOI_TOKEN_RE.findall(text):
        if _DOI_OK_RE.match(token):
            tokens.append({"token": token, "kind": "doi"})
    for token in _FICT_TOKEN_RE.findall(text):
        tokens.append({"token": token, "kind": "fictional"})
    for token in _ENSG_TOKEN_RE.findall(text):
        tokens.append({"token": token, "kind": "ensembl"})
    return tokens


def _strip_identifiers(text: str) -> str:
    """Replace identifier tokens with spaces so their digits are not
    mistaken for asserted numbers by the K7 number check."""
    stripped = _NCT_TOKEN_RE.sub(" ", text)
    stripped = _PMID_TOKEN_RE.sub(" ", stripped)
    stripped = _DOI_TOKEN_RE.sub(" ", stripped)
    stripped = _FICT_TOKEN_RE.sub(" ", stripped)
    stripped = _ENSG_TOKEN_RE.sub(" ", stripped)
    return stripped


def _cited_source_ids(claim: dict) -> list[int]:
    return [cite["id"] for cite in claim.get("citations", [])
            if isinstance(cite, dict) and cite.get("type") == "source"
            and type(cite.get("id")) is int]


def _cited_assessment_ids(claim: dict) -> list[int]:
    return [cite["id"] for cite in claim.get("citations", [])
            if isinstance(cite, dict) and cite.get("type") == "assessment"
            and type(cite.get("id")) is int]


def _cited_slots(claim: dict, context: KCheckContext) -> list[Slot]:
    cited = set(_cited_source_ids(claim))
    return [slot for slot in context.derived_slots if slot.source_version_id in cited]


def _cited_evidence_text(claim: dict, context: KCheckContext) -> str:
    """All evidence text a claim rests on: the quotes, field names,
    and values of its cited slots, plus its cited assessment
    statements. A token counts as supported only when it appears
    here, not merely somewhere in the case."""
    parts: list[str] = []
    for slot in _cited_slots(claim, context):
        parts.append(slot.quote)
        parts.append(slot.field)
        parts.append(slot.value)
    for assessment_id in _cited_assessment_ids(claim):
        parts.append(context.assessment_statements.get(assessment_id, ""))
    return "\n".join(parts)


def _drop(claim: dict, check: str, reason: str, detail: dict | None = None) -> dict:
    record: dict = {"claim": claim, "reason": reason, "check": check}
    if detail is not None:
        record["detail"] = detail
    return record


def _check_k1_format(claim: dict) -> dict | None:
    bad = malformed_identifiers(claim["text"])
    if not bad:
        return None
    return _drop(claim, "K1", "k1_citation_format", {"identifiers": bad})


def _check_k3_cite(claim: dict, context: KCheckContext) -> dict | None:
    """Cite only versions recorded at or before the snapshot."""
    if context.snapshot_as_of is None:
        return None
    as_of = _parse_instant(context.snapshot_as_of)
    if as_of is None:
        return None
    for source_id in _cited_source_ids(claim):
        version = context.source_versions.get(source_id)
        if version is None or version.received_date is None:
            continue
        received = _parse_instant(version.received_date)
        if received is None:
            continue
        if received > as_of:
            return _drop(claim, "K3", "k3_cite_after_snapshot", {
                "source_version_id": source_id,
                "received_at": version.received_date,
                "snapshot_as_of": context.snapshot_as_of,
            })
    return None


def _check_k5_snapshot(claim: dict, context: KCheckContext) -> dict | None:
    """Cites a version outside the snapshot. The superseded-version
    arm lives in the structural validator (see module docstring)."""
    if not context.snapshot_source_ids:
        return None
    for source_id in _cited_source_ids(claim):
        if source_id not in context.snapshot_source_ids:
            return _drop(claim, "K5", "k5_stale", {"source_version_id": source_id})
    return None


def _check_k2(claim: dict, context: KCheckContext) -> dict | None:
    """Slot-field match against the cited facets, plus the
    condition-scope sub-check."""
    text = claim["text"]
    asserted = derive_claim_slots(text, context.derived_slots, context.synonyms)
    cited = _cited_slots(claim, context)
    by_field: dict[str, list[Slot]] = {}
    for slot in cited:
        by_field.setdefault(slot.field, []).append(slot)
    for pair in asserted:
        facets = by_field.get(pair["field"])
        if not facets:
            return _drop(claim, "K2", "k2_no_cited_facet", {"field": pair["field"]})
        for facet in facets:
            cited_value = normalise_value(facet.value, context.synonyms)
            if cited_value != pair["value"]:
                return _drop(claim, "K2", "k2_slot_mismatch", {
                    "field": pair["field"],
                    "asserted": pair["value"],
                    "cited": cited_value,
                })
    if context.scope_relation is not None and context.condition_terms:
        lowered = text.lower()
        for term in context.condition_terms:
            if term.lower() not in lowered:
                continue
            relation = context.scope_relation(context.case_condition, term)
            if relation == "unrelated":
                return _drop(claim, "K2", "k2_condition_scope", {
                    "term": term, "relation": relation,
                })
            if relation in ("broader", "narrower"):
                limits = claim.get("limits") or ""
                note = f"Scope note: the cited condition is {relation} than the case condition."
                if note not in limits:
                    claim["limits"] = (limits + " " + note).strip()
    return None


def _check_k6(claim: dict, context: KCheckContext) -> dict | None:
    """The vertical's extra scope patterns, beyond the structural
    language guard. The patterns arrive as data; this module does not
    know what they say."""
    for pattern in context.scope_patterns:
        match = pattern.search(claim["text"])
        if match:
            return _drop(claim, "K6", "k6_scope", {
                "pattern": pattern.pattern,
                "matched": match.group(0),
            })
    return None


def _check_k7(claim: dict, context: KCheckContext) -> dict | None:
    """Support: every number, identifier, and named-substance token
    in the claim must appear in the cited evidence. Low-tier support
    must carry the fixed limits phrase."""
    evidence = _cited_evidence_text(claim, context)
    evidence_lower = evidence.lower()
    for token in _identifier_tokens(claim["text"]):
        if token["token"].lower() not in evidence_lower:
            return _drop(claim, "K7", "k7_unsupported_token", {
                "token": token["token"], "kind": token["kind"],
            })
    numbers = _NUMBER_RE.findall(_strip_identifiers(claim["text"]))
    supported_numbers = set(_NUMBER_RE.findall(evidence))
    for source_id in _cited_source_ids(claim):
        version = context.source_versions.get(source_id)
        if version is None:
            continue
        for raw_date in (version.specimen_date, version.report_date, version.received_date):
            if raw_date:
                supported_numbers.update(_NUMBER_RE.findall(raw_date))
    for number in numbers:
        if number not in supported_numbers:
            return _drop(claim, "K7", "k7_unsupported_token", {
                "token": number, "kind": "number",
            })
    for name in context.substance_names:
        if name.lower() in claim["text"].lower() and name.lower() not in evidence_lower:
            return _drop(claim, "K7", "k7_unsupported_token", {
                "token": name, "kind": "substance",
            })
    for cited_id in _cited_source_ids(claim) + _cited_assessment_ids(claim):
        tier = context.evidence_tiers.get(cited_id)
        if tier is None:
            continue
        if tier.strip().lower() in LOW_TIERS and TIER_LIMITS_PHRASE not in (claim.get("limits") or ""):
            return _drop(claim, "K7", "k7_tier_limits", {
                "cited_id": cited_id, "tier": tier,
            })
    return None


def _check_k7plus_injection(claim: dict, context: KCheckContext) -> dict | None:
    """Injected instructions in the claim text or in the cited
    evidence taint the claim. This catches instruction-shaped text
    planted in a document; it does not claim to catch a planted
    fabrication — a number absent from all cited sources is K7's
    catch, and that is the honest planted-fabrication fixture."""
    lowered = claim["text"].lower()
    for marker in INJECTION_MARKERS:
        if marker in lowered:
            return _drop(claim, "K7+", "k7plus_injection", {
                "marker": marker, "location": "claim",
            })
    evidence_lower = _cited_evidence_text(claim, context).lower()
    for marker in INJECTION_MARKERS:
        if marker in evidence_lower:
            return _drop(claim, "K7+", "k7plus_injection", {
                "marker": marker, "location": "evidence",
            })
    return None


def _ranges_overlap(first: Slot, second: Slot) -> bool:
    """True when two slots' valid times overlap. A missing range is
    treated as overlapping: the absence of a validity window is not
    evidence the two do not overlap. Only two present, disjoint
    ranges mean no overlap."""
    if first.valid_from is None or first.valid_to is None:
        return True
    if second.valid_from is None or second.valid_to is None:
        return True
    if compare_partial_dates(first.valid_to, second.valid_from) == -1:
        return False
    if compare_partial_dates(second.valid_to, first.valid_from) == -1:
        return False
    return True


def _check_k4(kept: list[dict], context: KCheckContext) -> tuple[list[dict], list[dict]]:
    """Contradiction over the survivors. Two claims asserting
    different normalised values for the same subject and field, with
    overlapping valid time and no supersession between their versions,
    contradict; the later claim is dropped. Both specimens present
    and different, or both assays present and different, means no
    contradiction: different specimens or assays never auto-supersede,
    and neither does a mere difference."""
    asserted_by_claim: list[list[dict]] = []
    for claim in kept:
        asserted_by_claim.append(derive_claim_slots(
            claim["text"], context.derived_slots, context.synonyms))
    dropped: list[dict] = []
    survivors: list[dict] = []
    dropped_indices: set[int] = set()
    for later_index, later_claim in enumerate(kept):
        contradiction: dict | None = None
        for later_pair in asserted_by_claim[later_index]:
            if contradiction is not None:
                break
            later_facets = [slot for slot in _cited_slots(later_claim, context)
                            if slot.field == later_pair["field"]]
            if not later_facets:
                continue
            for earlier_index in range(later_index):
                if earlier_index in dropped_indices:
                    continue
                for earlier_pair in asserted_by_claim[earlier_index]:
                    if earlier_pair["field"] != later_pair["field"]:
                        continue
                    if earlier_pair["value"] == later_pair["value"]:
                        continue
                    earlier_claim = kept[earlier_index]
                    earlier_facets = [slot for slot in _cited_slots(earlier_claim, context)
                                      if slot.field == earlier_pair["field"]]
                    for later_slot in later_facets:
                        for earlier_slot in earlier_facets:
                            if (later_slot.specimen is not None
                                    and earlier_slot.specimen is not None
                                    and later_slot.specimen != earlier_slot.specimen):
                                continue
                            if (later_slot.assay is not None
                                    and earlier_slot.assay is not None
                                    and later_slot.assay != earlier_slot.assay):
                                continue
                            if _supersedes(context.source_versions,
                                           later_slot.source_version_id,
                                           earlier_slot.source_version_id):
                                continue
                            if _supersedes(context.source_versions,
                                           earlier_slot.source_version_id,
                                           later_slot.source_version_id):
                                continue
                            if not _ranges_overlap(later_slot, earlier_slot):
                                continue
                            contradiction = {
                                "subject": context.subject,
                                "field": later_pair["field"],
                                "values": [earlier_pair["value"], later_pair["value"]],
                                "claim_indices": [earlier_index, later_index],
                                "source_version_ids": [
                                    earlier_slot.source_version_id,
                                    later_slot.source_version_id,
                                ],
                            }
                            break
                        if contradiction is not None:
                            break
                    if contradiction is not None:
                        break
                if contradiction is not None:
                    break
        if contradiction is not None:
            dropped.append(_drop(later_claim, "K4", "k4_contradiction", contradiction))
            dropped_indices.add(later_index)
        else:
            survivors.append(later_claim)
    return survivors, dropped


def _run_findings(context: KCheckContext) -> list[dict]:
    """Run-level findings: case-data issues and snapshot changes.
    These do not drop a claim; they say the ledger or the snapshot is
    inconsistent, and the question is for a later slice to reopen."""
    findings: list[dict] = []
    for version in context.source_versions.values():
        if (compare_partial_dates(version.specimen_date, version.report_date) == 1
                or compare_partial_dates(version.report_date, version.received_date) == 1
                or compare_partial_dates(version.specimen_date, version.received_date) == 1):
            findings.append({
                "check": "K3", "reason": "k3_temporal_order",
                "detail": {
                    "source_version_id": version.id,
                    "specimen_date": version.specimen_date,
                    "report_date": version.report_date,
                    "received_date": version.received_date,
                },
            })
    for slot in context.derived_slots:
        if (slot.valid_from is not None and slot.valid_to is not None
                and compare_partial_dates(slot.valid_from, slot.valid_to) == 1):
            findings.append({
                "check": "K3", "reason": "k3_range_order",
                "detail": {
                    "field": slot.field,
                    "valid_from": slot.valid_from,
                    "valid_to": slot.valid_to,
                },
            })
    if (context.expected_snapshot_hash is not None
            and context.current_snapshot_hash is not None
            and context.expected_snapshot_hash != context.current_snapshot_hash):
        findings.append({
            "check": "K5", "reason": "k5_snapshot_changed",
            "detail": {
                "expected_snapshot_hash": context.expected_snapshot_hash,
                "current_snapshot_hash": context.current_snapshot_hash,
            },
        })
    if (context.lot_ruleset is not None
            and context.current_lot_ruleset is not None
            and context.lot_ruleset != context.current_lot_ruleset):
        findings.append({
            "check": "K5", "reason": "k5_lot_ruleset_changed",
            "detail": {
                "lot_ruleset": context.lot_ruleset,
                "current_lot_ruleset": context.current_lot_ruleset,
            },
        })
    return findings


def run_kchecks(claims: list[dict], context: KCheckContext) -> KCheckResult:
    """Run K1-K7 over claims the structural validator already kept.
    Returns the survivors, the K-drops (each {"claim", "reason",
    "check", "detail"}), and the run-level findings. Per-claim checks
    run in K-number order; K4 runs pairwise over the survivors."""
    per_claim_checks = (
        _check_k1_format,
        lambda claim: _check_k3_cite(claim, context),
        lambda claim: _check_k5_snapshot(claim, context),
        lambda claim: _check_k2(claim, context),
        lambda claim: _check_k6(claim, context),
        lambda claim: _check_k7(claim, context),
        lambda claim: _check_k7plus_injection(claim, context),
    )
    kept: list[dict] = []
    dropped: list[dict] = []
    for claim in claims:
        failure = None
        for check in per_claim_checks:
            failure = check(claim)
            if failure is not None:
                break
        if failure is not None:
            dropped.append(failure)
        else:
            kept.append(claim)
    survivors, contradictions = _check_k4(kept, context)
    dropped.extend(contradictions)
    return KCheckResult(kept=survivors, dropped=dropped, findings=_run_findings(context))


def build_kcheck_context(facts: dict, source_version_rows, *, case_id: str,
                         snapshot_as_of: str | None = None,
                         synonyms: dict[str, str] | None = None,
                         scope_patterns=None,
                         condition_terms=None,
                         scope_relation=None,
                         case_condition: str | None = None,
                         substance_names=None,
                         evidence_tiers: dict[int, str] | None = None,
                         expected_snapshot_hash: str | None = None,
                         current_snapshot_hash: str | None = None,
                         lot_ruleset: str | None = None,
                         current_lot_ruleset: str | None = None) -> KCheckContext:
    """Assemble a KCheckContext from a ledger read: `facts` is the
    `investigation_facts` result for the case and question, and
    `source_version_rows` are the `source_version_facts` rows for the
    case (all versions, current and superseded). Derived slots are the
    assertions of the cited sources: finding key is the field,
    certainty is the value, quote is the evidence text."""
    versions: dict[int, SourceVersionInfo] = {}
    for row in source_version_rows:
        versions[row["id"]] = SourceVersionInfo(
            id=row["id"],
            specimen_date=row.get("event_date"),
            report_date=row.get("issued_at"),
            received_date=row.get("received_at"),
            state=row.get("state", "current"),
            supersedes_id=row.get("supersedes_id"),
            sha256=row.get("sha256", ""),
            specimen_id=row.get("specimen_id"),
            kind=row.get("kind"),
        )
    slots: list[Slot] = []
    for item in facts.get("assertions", []):
        version = versions.get(item.get("source_version_id"))
        slots.append(Slot(
            subject=case_id,
            field=item.get("finding_key", ""),
            value=item.get("certainty", ""),
            source_version_id=item.get("source_version_id"),
            specimen=version.specimen_id if version is not None else None,
            quote=item.get("quote") or "",
        ))
    assessment_statements = {
        item["id"]: item.get("statement") or ""
        for item in facts.get("assessments", [])
        if isinstance(item, dict) and type(item.get("id")) is int
    }
    return KCheckContext(
        subject=case_id,
        source_versions=versions,
        derived_slots=slots,
        assessment_statements=assessment_statements,
        snapshot_as_of=snapshot_as_of,
        snapshot_source_ids={version.id for version in versions.values()
                             if version.state == "current"},
        expected_snapshot_hash=expected_snapshot_hash,
        current_snapshot_hash=current_snapshot_hash,
        lot_ruleset=lot_ruleset,
        current_lot_ruleset=current_lot_ruleset,
        synonyms=dict(synonyms or {}),
        scope_patterns=list(scope_patterns or []),
        condition_terms=list(condition_terms or []),
        scope_relation=scope_relation,
        case_condition=case_condition,
        substance_names=list(substance_names or []),
        evidence_tiers=dict(evidence_tiers or {}),
    )
