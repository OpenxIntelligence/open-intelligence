"""Slice 4 (program plan C4): the Skeptic (A6), one repair round, and
reconciliation (T6 grouping + abstention codes).

This module is the verification dimension's agent half. The deterministic
half is `kchecks` (K1-K7); this module adds the machine second opinion
over claims the deterministic checks kept, plus exactly one chance to
repair a failing claim, plus the typed reconciliation record that makes
conflicts visible and blocking instead of silently merged.

The Skeptic (role A6, "Skeptic") is an independent model pass: the same
model (`muse-spark-1.3`), a separate prompt and prompt version, and no
shared context beyond the claims under review and their cited evidence.
Independence is the point: the Skeptic never sees the investigation
template, the question, the other claims, or the author's reasoning, so
it cannot inherit the author's mistake. A claim that cites a real source
but misstates its content is caught here, after K1-K7 passed it.

Pipeline order (program plan section 4): K-checks, then one repair
round, then the Skeptic, then storage. The Skeptic is the last check
before storage, and it produces no writes, so it needs no route
assignment (no route in C3 assigns A6) and no write contract.

Repair round: exactly one attempt per run, ever. Only content failures
whose restatement can align the claim to its cited evidence are
repairable (see `REPAIRABLE_REASONS`). A repaired claim is re-validated
end to end (structural validation + K-checks); still failing, it is
dropped with the new check and reason. A repair is never silent: the
original text, the failure reason, the repaired text, and the re-check
result are recorded in the verification record.

Abstention codes (typed, from Notion OI-09 section 4.6):

- ``AB-CONFLICT`` with an ``origin``: ``agent_divergence`` (an
  unresolved K4 contradiction between the run's own claims),
  ``source_disagreement`` (a T6 source group intersecting the run's
  cited sources), ``skeptic_challenge`` (the Skeptic challenged a kept
  claim). A conflict is a typed, visible, blocking record: the claim
  is held, never merged or voted on, and the code is stored with the
  run.
- ``AB-STALE``: the run's inputs were superseded during the run (a K5
  finding, or a ``k5_stale`` drop). A stale run does not address the
  question: `store.save_investigation` leaves the question open.
- ``AB-BUDGET``: the verification call budget (one Skeptic call, one
  repair call per run) was already spent when a pass was due.
- ``AB-MODEL``: a Skeptic or repair model call failed, or its output
  was schema-invalid after one retry.
- ``AB-ALL-DROPPED``: every attempted claim was dropped after the
  repair round (and the Skeptic), so the run has no answer.

A failed Skeptic or repair call does not fail the run: the K-checked
claims are still stored, with ``AB-MODEL`` attached, so the gap is
visible and blocking instead of losing the whole run. The run's
``status`` stays as computed by `validate_output` (completed /
abstained), except that a run whose last kept claim is held by the
Skeptic flips to abstained.

Replay mode skips both model passes (no model call exists there) and
records the skip; T6 grouping and abstention codes still run, because
they are deterministic.

No live model call is made by the tests in `tests/test_skeptic.py`:
the model calls are injectable, and the live prompt is verified
separately against the Meta Model API on synthetic data.
"""

from __future__ import annotations

import json

from .investigation import InvestigationError, call_meta_api, meta_api_key, validate_output

SKEPTIC_AGENT_ROLE = "A6"
SKEPTIC_AGENT_ID = "agent-A6"
SKEPTIC_PROMPT_VERSION = "skeptic:1"
SKEPTIC_MODEL = "muse-spark-1.3"
REPAIR_PROMPT_VERSION = "repair:1"

# Verification-call budget per run: one Skeptic call and one repair
# call. The route budget's maxModelCalls (program plan C3) covers the
# investigation call itself; these are verification calls, not agent
# calls, so they carry their own budget. Exceeding it records
# AB-BUDGET; it never silently runs a second pass.
MAX_SKEPTIC_CALLS = 1
MAX_REPAIR_CALLS = 1
# One retry on a failed or schema-invalid model call; a second failure
# records AB-MODEL.
MAX_MODEL_ATTEMPTS = 2

REASON_LIMIT = 280

ABSTENTION_CODES = (
    "AB-CONFLICT",
    "AB-STALE",
    "AB-BUDGET",
    "AB-MODEL",
    "AB-ALL-DROPPED",
)
AB_CONFLICT_ORIGINS = (
    "agent_divergence",
    "source_disagreement",
    "skeptic_challenge",
)

SKEPTIC_VERDICTS = ("supported", "challenged", "uncertain")

# K-drop reasons a restatement can fix: the failure is a mismatch
# between the claim text and the cited evidence, and the evidence
# itself holds the correct wording. Not repairable, by design:
# - structural drops (missing text/citations, invalid uncertainty or
#   support, language guard, unresolved citation, stale citation):
#   there is nothing to restate from, or the claim must stay dropped;
# - k4_contradiction: restating one side to match the other would be
#   merging by rewrite, which the reconciliation rule forbids;
# - k6_scope: rephrasing advice into a neutral claim changes what the
#   claim means, it does not repair it;
# - k7plus_injection: tainted content is never repaired into a claim.
REPAIRABLE_REASONS = frozenset({
    "k1_citation_format",
    "k2_no_cited_facet",
    "k2_slot_mismatch",
    "k7_unsupported_token",
    "k7_tier_limits",
})


class SkepticError(Exception):
    """The Skeptic (or repair) model call failed or returned output
    that could not be parsed after one retry. The caller records
    AB-MODEL; this exception is never a reason to drop a claim."""


class VerificationBudgetExceeded(SkepticError):
    """A verification pass was due but its call budget was already
    spent. The caller records AB-BUDGET; the pass is skipped."""


def _live_model_call(prompt: str) -> dict:
    """The default model call: one bounded Meta Model API call."""
    return call_meta_api(prompt, meta_api_key())


def _call_with_retry(call_model, prompt: str) -> dict:
    """Call the model, retrying once on failure. A second failure
    raises SkepticError (the caller records AB-MODEL)."""
    last_error: Exception | None = None
    for _attempt in range(MAX_MODEL_ATTEMPTS):
        try:
            result = call_model(prompt)
        except Exception as error:  # network, HTTP, decode, key: no partial claim
            last_error = error
            continue
        if isinstance(result, dict):
            return result
        last_error = SkepticError("model output was not a JSON object")
    if isinstance(last_error, SkepticError):
        raise last_error
    raise SkepticError(
        f"model call failed after {MAX_MODEL_ATTEMPTS} attempts: "
        f"{type(last_error).__name__}"
    ) from last_error


def cited_evidence(claim: dict, kcheck_context) -> list[dict]:
    """The quoted evidence a claim rests on, from its citations only.

    Each entry is ``{"label": "source <id>" | "assessment <id>",
    "quote": ...}``. A citation with no quoted evidence in the context
    (a source version with no assertions) yields an entry with an
    empty quote, so the Skeptic can see the citation exists but
    carries no quote. Nothing outside the claim's own citations is
    included: the Skeptic must judge the claim against what it cited,
    not against the case at large.
    """
    if kcheck_context is None:
        return []
    evidence: list[dict] = []
    seen: set[tuple[str, str]] = set()
    for cite in claim.get("citations", []) if isinstance(claim.get("citations"), list) else []:
        if not isinstance(cite, dict):
            continue
        if cite.get("type") == "source" and type(cite.get("id")) is int:
            label = f"source {cite['id']}"
            quotes = [
                slot.quote for slot in kcheck_context.derived_slots
                if slot.source_version_id == cite["id"] and slot.quote
            ]
            if not quotes:
                quotes = [""]
            for quote in quotes:
                if (label, quote) not in seen:
                    seen.add((label, quote))
                    evidence.append({"label": label, "quote": quote})
        elif cite.get("type") == "assessment" and type(cite.get("id")) is int:
            label = f"assessment {cite['id']}"
            quote = kcheck_context.assessment_statements.get(cite["id"], "") or ""
            if (label, quote) not in seen:
                seen.add((label, quote))
                evidence.append({"label": label, "quote": quote})
    return evidence


def build_skeptic_prompt(claims_with_evidence: list[dict]) -> str:
    """Build the Skeptic prompt from claims + their cited evidence only.

    The prompt contains the claim text and the quoted evidence listed
    with each claim, and nothing else: no template, no question, no
    other claims' evidence, no author reasoning. That restriction is
    the independence guarantee, and it is testable: the prompt must
    not contain any string the caller did not pass in.
    """
    lines = [
        "You are an independent reviewer of a fictional, synthetic case "
        "used for a software demonstration. No real patient is involved.",
        "",
        "Your job is to check each claim below against ONLY the quoted "
        "evidence listed with it. You have no other context: no question, "
        "no case history, no other claims, no author reasoning. Do not use "
        "outside knowledge. Do not recommend treatment, select therapy, "
        "dose, or diagnose.",
        "",
        "For each claim, give one verdict:",
        '- "supported": every statement in the claim is stated by, or '
        "directly follows from, the quoted evidence listed with it.",
        '- "challenged": the claim asserts something the quoted evidence '
        "does not state, contradicts a quoted statement, or adds a number, "
        "identifier, date, or named substance that is not in the quoted "
        "evidence.",
        '- "uncertain": the quoted evidence neither supports nor '
        "contradicts the claim, so you cannot tell from the evidence alone.",
        "",
        "Reply with JSON only, in exactly this shape: "
        '{"reviews": [{"claim_index": 0, "verdict": '
        '"supported|challenged|uncertain", "reason": "..."}]}',
        "Keep each reason under 280 characters. Give one review per "
        "claim, in the same order as the claims.",
        "",
    ]
    for entry in claims_with_evidence:
        index = entry["claim_index"]
        lines.append(f"Claim {index}:")
        lines.append(str(entry["text"]))
        lines.append(f"Evidence for claim {index}:")
        for item in entry.get("evidence", []):
            quote = item.get("quote") or ""
            lines.append(f"- {item.get('label')}: "
                         f"{json.dumps(quote) if quote else '(no quoted evidence from this citation)'}")
        lines.append("")
    return "\n".join(lines)


def parse_skeptic_output(payload: object, claim_count: int) -> list[dict]:
    """Parse and strictly validate a Skeptic reply.

    Returns one review per claim, in claim order. A claim with no
    review in the reply is "uncertain" with a recorded reason, never
    silently dropped. A review with an unknown verdict, a non-integer
    index, or an index outside the claim range is schema-invalid and
    raises SkepticError (the caller retries once, then records
    AB-MODEL).
    """
    if not isinstance(payload, dict) or not isinstance(payload.get("reviews"), list):
        raise SkepticError("Skeptic output was not an object with a reviews list")
    reviews: dict[int, dict] = {}
    for raw in payload["reviews"]:
        if not isinstance(raw, dict):
            raise SkepticError("Skeptic review was not an object")
        index = raw.get("claim_index")
        if type(index) is not int or not 0 <= index < claim_count:
            raise SkepticError(f"Skeptic review has an invalid claim_index: {index!r}")
        verdict = raw.get("verdict")
        if verdict not in SKEPTIC_VERDICTS:
            raise SkepticError(f"Skeptic review has an unknown verdict: {verdict!r}")
        reason = raw.get("reason")
        if not isinstance(reason, str) or not reason.strip():
            raise SkepticError("Skeptic review has no reason")
        reviews[index] = {
            "claim_index": index,
            "verdict": verdict,
            "reason": reason.strip()[:REASON_LIMIT],
        }
    return [
        reviews.get(index, {
            "claim_index": index,
            "verdict": "uncertain",
            "reason": "no review returned for this claim",
        })
        for index in range(claim_count)
    ]


def run_skeptic(claims_with_evidence: list[dict], *, call_model=None,
                call_budget: dict | None = None) -> dict:
    """Run the Skeptic over the kept claims. Returns the Skeptic
    record: ``{"status": "completed", "model", "prompt_version",
    "reviews": [...], "calls": n}``.

    ``call_model`` is an injectable ``prompt -> dict`` callable; the
    live default is one Meta Model API call. ``call_budget`` is a
    mutable ``{"skeptic_calls": int, "repair_calls": int}`` shared
    across the run's verification passes; a spent budget raises
    SkepticError with the AB-BUDGET marker (the caller records the
    code). A failed or schema-invalid call is retried once, then
    raises SkepticError (the caller records AB-MODEL).
    """
    budget = call_budget if call_budget is not None else {
        "skeptic_calls": 0, "repair_calls": 0}
    if budget.get("skeptic_calls", 0) >= MAX_SKEPTIC_CALLS:
        raise VerificationBudgetExceeded(
            "verification budget spent: no Skeptic call remains")
    prompt = build_skeptic_prompt(claims_with_evidence)
    payload = _call_with_retry(call_model or _live_model_call, prompt)
    budget["skeptic_calls"] = budget.get("skeptic_calls", 0) + 1
    reviews = parse_skeptic_output(payload, len(claims_with_evidence))
    return {
        "status": "completed",
        "model": SKEPTIC_MODEL,
        "prompt_version": SKEPTIC_PROMPT_VERSION,
        "reviews": reviews,
        "calls": budget["skeptic_calls"],
    }


def build_repair_prompt(attempts: list[dict]) -> str:
    """Build the repair prompt from the repairable drops + their cited
    evidence. Like the Skeptic prompt, it carries only the claim, its
    failure reason, and its cited quotes: no template, no question,
    no other claims.
    """
    lines = [
        "You are repairing claims from a fictional, synthetic case used "
        "for a software demonstration. No real patient is involved.",
        "",
        "Each claim below failed a deterministic check, for the reason "
        "given. Restate the claim so it states only what the quoted "
        "evidence listed with it supports, keeping the same meaning "
        "where the evidence allows it. Keep the claim's citations "
        "unchanged. Do not add any number, identifier, date, or named "
        "substance that is not in the quoted evidence. Do not recommend "
        "treatment, select therapy, dose, or diagnose. If the claim "
        "cannot be restated truthfully from the quoted evidence, mark "
        "it cannot_repair.",
        "",
        "Reply with JSON only, in exactly this shape: "
        '{"repairs": [{"claim_index": 0, "repaired_text": "...", '
        '"cannot_repair": false, "reason": "..."}]}',
        "Set repaired_text to null when cannot_repair is true. Keep "
        "each reason under 280 characters.",
        "",
    ]
    for entry in attempts:
        index = entry["claim_index"]
        lines.append(f"Claim {index} (failed: {entry['reason']}):")
        lines.append(str(entry["text"]))
        lines.append(f"Evidence for claim {index}:")
        for item in entry.get("evidence", []):
            quote = item.get("quote") or ""
            lines.append(f"- {item.get('label')}: "
                         f"{json.dumps(quote) if quote else '(no quoted evidence from this citation)'}")
        lines.append("")
    return "\n".join(lines)


def parse_repair_output(payload: object, claim_count: int) -> list[dict]:
    """Parse and strictly validate a repair reply. Returns one repair
    per attempted claim. A repair with an unknown shape or an index
    outside the attempt range is schema-invalid and raises
    SkepticError (the caller retries once, then records AB-MODEL)."""
    if not isinstance(payload, dict) or not isinstance(payload.get("repairs"), list):
        raise SkepticError("Repair output was not an object with a repairs list")
    repairs: dict[int, dict] = {}
    for raw in payload["repairs"]:
        if not isinstance(raw, dict):
            raise SkepticError("Repair entry was not an object")
        index = raw.get("claim_index")
        if type(index) is not int or not 0 <= index < claim_count:
            raise SkepticError(f"Repair entry has an invalid claim_index: {index!r}")
        cannot_repair = raw.get("cannot_repair")
        if type(cannot_repair) is not bool:
            raise SkepticError("Repair entry has no boolean cannot_repair")
        repaired_text = raw.get("repaired_text")
        if cannot_repair:
            if repaired_text is not None:
                raise SkepticError("Repair entry marked cannot_repair with a repaired_text")
        elif not isinstance(repaired_text, str) or not repaired_text.strip():
            raise SkepticError("Repair entry has no repaired_text")
        reason = raw.get("reason")
        if not isinstance(reason, str) or not reason.strip():
            raise SkepticError("Repair entry has no reason")
        repairs[index] = {
            "claim_index": index,
            "repaired_text": repaired_text.strip() if isinstance(repaired_text, str) else None,
            "cannot_repair": cannot_repair,
            "reason": reason.strip()[:REASON_LIMIT],
        }
    return [
        repairs.get(index, {
            "claim_index": index,
            "repaired_text": None,
            "cannot_repair": True,
            "reason": "no repair returned for this claim",
        })
        for index in range(claim_count)
    ]


def run_repair(attempts: list[dict], *, call_model=None,
               call_budget: dict | None = None) -> dict:
    """Run one repair round over the repairable drops. Returns the
    repair record: ``{"status": "completed", "prompt_version",
    "repairs": [...], "calls": n}``. The caller re-validates each
    repaired text and records the outcome; this function only runs
    the model pass. Budget and retry rules are the Skeptic's.
    """
    budget = call_budget if call_budget is not None else {
        "skeptic_calls": 0, "repair_calls": 0}
    if budget.get("repair_calls", 0) >= MAX_REPAIR_CALLS:
        raise VerificationBudgetExceeded(
            "verification budget spent: no repair call remains")
    prompt = build_repair_prompt(attempts)
    payload = _call_with_retry(call_model or _live_model_call, prompt)
    budget["repair_calls"] = budget.get("repair_calls", 0) + 1
    repairs = parse_repair_output(payload, len(attempts))
    return {
        "status": "completed",
        "prompt_version": REPAIR_PROMPT_VERSION,
        "repairs": repairs,
        "calls": budget["repair_calls"],
    }


def compute_abstention_codes(*, kept_count: int, attempted_count: int,
                              k4_present: bool,
                              source_disagreement: bool,
                              skeptic_challenged: bool, stale: bool,
                              budget_exceeded: bool,
                              model_failed: bool) -> list[dict]:
    """Compute the typed abstention codes for a run, from the
    verification outcome. Every code has a precise firing rule; no
    code is ever invented from a hunch.

    - AB-ALL-DROPPED: claims were attempted and none survived.
    - AB-CONFLICT, one entry per origin that fired: a K4 contradiction
      between the run's own claims (agent_divergence), a T6 source
      group intersecting the run's cited sources (source_disagreement),
      a Skeptic challenge (skeptic_challenge).
    - AB-STALE: a K5 finding or a k5_stale drop.
    - AB-BUDGET: a verification pass was refused for budget.
    - AB-MODEL: a verification model call failed or was schema-invalid
      after one retry.
    """
    codes: list[dict] = []
    if k4_present:
        codes.append({"code": "AB-CONFLICT", "origin": "agent_divergence",
                      "detail": "unresolved K4 contradiction between the run's own claims"})
    if source_disagreement:
        codes.append({"code": "AB-CONFLICT", "origin": "source_disagreement",
                      "detail": "a T6 source group disagrees over a source the run cited"})
    if skeptic_challenged:
        codes.append({"code": "AB-CONFLICT", "origin": "skeptic_challenge",
                      "detail": "the Skeptic challenged a kept claim against its cited evidence"})
    if stale:
        codes.append({"code": "AB-STALE",
                      "detail": "inputs were superseded during the run; the question stays open"})
    if budget_exceeded:
        codes.append({"code": "AB-BUDGET",
                      "detail": "the verification call budget was spent before a pass ran"})
    if model_failed:
        codes.append({"code": "AB-MODEL",
                      "detail": "a verification model call failed or was schema-invalid after one retry"})
    if attempted_count > 0 and kept_count == 0:
        codes.append({"code": "AB-ALL-DROPPED",
                      "detail": "every attempted claim was dropped after repair and review"})
    return codes


def run_verification(validated, kcheck_context, facts: dict, *, mode: str,
                     store=None, case_id: str | None = None,
                     skeptic_call=None, repair_call=None,
                     call_budget: dict | None = None) -> dict:
    """Run the C4 verification stage over a K-checked investigation.

    ``validated`` is the `ValidatedInvestigation` from `validate_output`
    (K-checks already applied); it is mutated in place: the repair
    round can add kept claims, the Skeptic can hold kept claims, and
    the status flips to abstained when no kept claim survives. The
    returned verification record is JSON-ready and is stored with the
    run (one row per investigation) and returned in the response.

    Order: T6 grouping (deterministic, always runs) -> one repair
    round (live mode only) -> Skeptic (live mode only). In replay mode
    both model passes are skipped and the skip is recorded; the
    deterministic half still runs. A failed model call records
    AB-MODEL and the run proceeds with its K-checked claims; it never
    fails the run.
    """
    from .synthesis import (
        group_run_contradictions,
        group_source_contradictions,
        group_timeline_conflicts,
        group_timeline_gaps,
    )
    from .timeline import case_timeline

    if mode not in ("live", "replay"):
        raise InvestigationError("Mode must be live or replay")
    budget = call_budget if call_budget is not None else {
        "skeptic_calls": 0, "repair_calls": 0}
    attempted_count = len(validated.claims) + len(validated.dropped)
    claims = list(validated.claims)
    dropped = list(validated.dropped)
    findings = list(validated.findings)

    # --- T6 grouping: deterministic, runs in both modes. -------------
    run_groups = group_run_contradictions(dropped)
    source_groups = group_source_contradictions(kcheck_context) if kcheck_context is not None else []
    cited_source_ids = {
        cite["id"] for claim in claims for cite in claim.get("citations", [])
        if isinstance(cite, dict) and cite.get("type") == "source"
        and type(cite.get("id")) is int
    }
    timeline_data = None
    timeline_error = None
    if store is not None and case_id is not None:
        try:
            timeline_data = case_timeline(store, case_id)
        except Exception as error:  # a broken timeline must not lose the run
            timeline_error = f"{type(error).__name__}: {error}"
    timeline_conflicts = group_timeline_conflicts(timeline_data) if timeline_data is not None else []
    gap_groups = group_timeline_gaps(timeline_data) if timeline_data is not None else []
    if timeline_error is not None:
        gap_groups.append({
            "kind": "gap", "what": "timeline could not be read for gap grouping",
            "evidence_needed": "a readable case timeline", "detail": timeline_error,
        })
    # A source disagreement is question-relevant when it touches a
    # source the run actually cited: the run's answer rests on it.
    disagreement_ids = set()
    for group in source_groups:
        disagreement_ids.update(group.get("source_version_ids", []))
    for group in timeline_conflicts:
        for source in group.get("sources", []):
            if isinstance(source, dict) and type(source.get("source_id")) is int:
                disagreement_ids.add(source["source_id"])
    source_disagreement = bool(cited_source_ids & disagreement_ids)

    # --- One repair round: live mode only, exactly once. -------------
    repair_record: dict = {
        "status": "skipped", "reason": "replay" if mode == "replay" else "no repairable drops",
        "rounds": 0, "attempts": [], "repaired": [], "unrepaired": [],
    }
    model_failed = False
    budget_exceeded = False
    repairable = [
        entry for entry in dropped
        if entry.get("reason") in REPAIRABLE_REASONS
    ]
    if mode == "live" and repairable:
        attempts = [
            {
                "claim_index": index,
                "text": entry["claim"]["text"],
                "reason": entry["reason"],
                "evidence": cited_evidence(entry["claim"], kcheck_context),
            }
            for index, entry in enumerate(repairable)
        ]
        repair_record = {
            "status": "completed", "rounds": 1, "attempts": [],
            "repaired": [], "unrepaired": [],
        }
        try:
            result = run_repair(attempts, call_model=repair_call, call_budget=budget)
            repair_record["prompt_version"] = REPAIR_PROMPT_VERSION
            repair_record["calls"] = result["calls"]
        except VerificationBudgetExceeded:
            budget_exceeded = True
            repair_record = {
                "status": "skipped",
                "reason": "verification budget spent: no repair call remains",
                "rounds": 0, "attempts": [],
                "repaired": [], "unrepaired": [
                    {"claim_index": entry["claim_index"],
                     "reason": entry["reason"], "detail": "repair not attempted"}
                    for entry in attempts
                ],
            }
            result = None
        except SkepticError as error:
            model_failed = True
            repair_record = {
                "status": "failed",
                "reason": str(error), "rounds": 0, "attempts": [],
                "repaired": [], "unrepaired": [
                    {"claim_index": entry["claim_index"],
                     "reason": entry["reason"], "detail": "repair not attempted"}
                    for entry in attempts
                ],
            }
            result = None
        if result is not None:
            valid_sources = set(facts.get("valid_sources", set()))
            valid_assessments = set(facts.get("valid_assessments", set()))
            for entry, repair in zip(repairable, result["repairs"]):
                original = entry["claim"]
                attempt = {
                    "claim_index": repair["claim_index"],
                    "original_text": original["text"],
                    "reason": entry["reason"],
                    "repaired_text": repair["repaired_text"],
                }
                repair_record["attempts"].append(attempt)
                if repair["cannot_repair"] or repair["repaired_text"] is None:
                    repair_record["unrepaired"].append({
                        **attempt, "detail": repair["reason"]})
                    continue
                rebuilt = {
                    "text": repair["repaired_text"],
                    "support": original["support"],
                    "citations": original["citations"],
                    "uncertainty": original["uncertainty"],
                    "limits": original.get("limits", ""),
                }
                rechecked = validate_output(
                    {"claims": [rebuilt], "abstentions": []},
                    valid_sources, valid_assessments, kcheck_context)
                if rechecked.claims:
                    claims.append(rechecked.claims[0])
                    dropped.remove(entry)
                    repair_record["repaired"].append({
                        **attempt, "recheck": "kept"})
                else:
                    new_drop = rechecked.dropped[0] if rechecked.dropped else {
                        "claim": rebuilt, "reason": "repair_recheck_failed"}
                    dropped.remove(entry)
                    dropped.append({
                        "claim": original,
                        "reason": new_drop.get("reason", "repair_recheck_failed"),
                        "check": new_drop.get("check", "repair"),
                        "detail": {"repaired_text": repair["repaired_text"],
                                   "repair_reason": repair["reason"]},
                    })
                    repair_record["unrepaired"].append({
                        **attempt,
                        "detail": f"re-check dropped: {new_drop.get('reason')}"})

    # --- Skeptic: live mode only, the last check before storage. -----
    skeptic_record: dict
    skeptic_challenged = False
    if mode == "replay":
        skeptic_record = {"status": "skipped", "reason": "replay", "reviews": []}
    else:
        claims_with_evidence = [
            {"claim_index": index, "text": claim["text"],
             "evidence": cited_evidence(claim, kcheck_context)}
            for index, claim in enumerate(claims)
        ]
        try:
            skeptic_record = run_skeptic(
                claims_with_evidence, call_model=skeptic_call, call_budget=budget)
        except VerificationBudgetExceeded:
            budget_exceeded = True
            skeptic_record = {
                "status": "skipped",
                "reason": "verification budget spent: no Skeptic call remains",
                "reviews": [],
            }
        except SkepticError as error:
            model_failed = True
            skeptic_record = {
                "status": "failed",
                "reason": str(error), "reviews": [],
            }
        if skeptic_record.get("status") == "completed":
            held_indices: list[int] = []
            for index, review in enumerate(skeptic_record["reviews"]):
                claim = claims[index]
                if review["verdict"] == "challenged":
                    skeptic_challenged = True
                    held_indices.append(index)
                    dropped.append({
                        "claim": claim,
                        "reason": "skeptic_challenged",
                        "check": "skeptic",
                        "detail": {"verdict": "challenged",
                                   "reason": review["reason"]},
                    })
                elif review["verdict"] == "uncertain":
                    claim = dict(claim)
                    claims[index] = claim
                    claim["uncertainty"] = "high"
                    note = f" Skeptic could not verify: {review['reason']}"
                    claim["limits"] = (claim.get("limits", "") + note).strip()
            # Remove by index, highest first: two identical claim texts
            # must not let the wrong one be held.
            for index in sorted(held_indices, reverse=True):
                del claims[index]

    # --- Abstention codes + final status. ----------------------------
    k4_present = any(entry.get("reason") == "k4_contradiction" for entry in dropped)
    stale = any(
        entry.get("reason") == "k5_stale" for entry in dropped
    ) or any(
        finding.get("check") == "K5" for finding in findings
    )
    codes = compute_abstention_codes(
        kept_count=len(claims), attempted_count=attempted_count,
        k4_present=k4_present, source_disagreement=source_disagreement,
        skeptic_challenged=skeptic_challenged, stale=stale,
        budget_exceeded=budget_exceeded, model_failed=model_failed)

    validated.claims = claims
    validated.dropped = dropped
    # The status is recomputed from the final kept set: the repair round
    # can resurrect a run validate_output abstained (a repaired claim is
    # an answer), and the Skeptic can hold a run's last kept claim (no
    # answer remains). Statuses validate_output never produces are
    # left alone.
    if validated.status in ("completed", "abstained"):
        validated.status = "completed" if claims else "abstained"

    return {
        "skeptic": skeptic_record,
        "repair": repair_record,
        "t6": {
            "contradictions": run_groups + source_groups + timeline_conflicts,
            "gaps": gap_groups,
        },
        "abstention_codes": codes,
        "verification_call_budget": {
            "skeptic_calls": budget.get("skeptic_calls", 0),
            "repair_calls": budget.get("repair_calls", 0),
        },
    }
