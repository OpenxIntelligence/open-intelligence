"""Bounded Meta Model API investigation for synthetic cases.

This module is the ONLY place that talks to a model. It is deliberately
narrow, following the repository rule that model outputs are inspectable
proposals governed by a typed task contract:

- The caller supplies a case, an existing question id, and a template id.
  There is no free-text prompt to the model: the prompt is assembled
  server-side from a fixed template plus the case's own current
  assertions and evidence assessments.
- The model may only return claims and abstentions. Every claim is
  validated before storage: its citations must resolve to a current
  source version or an assessment for this question, its uncertainty
  must be low/moderate/high, and its text must pass the language guard.
  A claim that fails any check is dropped and recorded as dropped,
  never silently repaired.
- Stored output is always kind="hypothesis" and reviewState="pending".
  Nothing here recommends treatment, selects therapy, doses, or
  diagnoses. A template that asks for any of those is rejected by the
  policy gate before any model call or token is spent.
- The model API key comes only from the operator environment
  (META_API_KEY), is used server-side only, and is never logged,
  stored, or sent to the browser. No case identifiers beyond the
  fictional case id, and no patient-like fields, are in the payload.
- Replay mode uses a recorded, human-authored fixture so the full
  demo path runs offline. Replay output goes through the same
  citation validation and language guard, and is labeled mode="replay"
  and model="recorded-replay" — never presented as a live run.
"""

from __future__ import annotations

import json
import os
import re
import urllib.request
from dataclasses import dataclass

META_API_URL = "https://api.meta.ai/v1/messages"
META_MODEL = "muse-spark-1.3"

TEMPLATES = {
    "evidence-summary": (
        "Summarize, in plain language, what the case sources and the "
        "fictional evidence assessments say that is relevant to the "
        "question. Do not recommend treatment, do not select therapy, "
        "do not dose, and do not diagnose. State uncertainty for every "
        "claim. If the evidence is thin, conflicting, or absent, abstain "
        "on that part instead of guessing."
    ),
    "timeline-gaps": (
        "Identify gaps, conflicts, and missing dates in the case timeline "
        "that are relevant to the question, using only the sources and "
        "assessments given. Do not infer disease progression, benefit, "
        "or clinical meaning beyond what the sources state. Abstain where "
        "the record does not support an answer."
    ),
    "evidence-applicability": (
        "Summarize the human-authored applicability assessments for this "
        "question and what limits them. Do not determine trial "
        "eligibility, treatment efficacy, or clinical relevance. "
        "Abstain where no assessment applies."
    ),
}

# Output language that must never reach storage as a claim. The guard
# runs on model output only, never on the (human-authored) question.
GUARD_PATTERNS = [
    re.compile(r"\brecommend\w*\b", re.IGNORECASE),
    re.compile(r"\bshould (receive|be treated|take|undergo|start|stop)\b", re.IGNORECASE),
    re.compile(r"\bprescri\w*\b", re.IGNORECASE),
    re.compile(r"\bdos(e|age)\b", re.IGNORECASE),
    re.compile(r"\bbest (treatment|therapy|option|drug)\b", re.IGNORECASE),
    re.compile(r"\byou should\b", re.IGNORECASE),
]

UNCERTAINTIES = frozenset({"low", "moderate", "high"})
ABSTAIN_REASONS = frozenset(
    {"no_evidence", "insufficient_evidence", "out_of_scope", "conflicting_evidence"}
)


class InvestigationError(ValueError):
    """A bounded investigation could not be run or validated."""


@dataclass
class ValidatedInvestigation:
    status: str  # completed | abstained | blocked_by_policy | failed
    claims: list[dict]
    abstentions: list[dict]
    dropped: list[dict]
    model: str
    mode: str


def build_prompt(template_id: str, question: str, assertions: list[dict],
                 assessments: list[dict]) -> str:
    """Assemble the fixed model prompt. No caller-supplied free text."""
    if template_id not in TEMPLATES:
        raise InvestigationError("Unknown investigation template")
    lines = [
        "You are helping with a fictional, synthetic oncology case used "
        "for a software demonstration. No real patient is involved.",
        "",
        "Task: " + TEMPLATES[template_id],
        "",
        "Question: " + question,
        "",
        "Case assertions (source statements, with source version ids):",
    ]
    for item in assertions[:100]:
        lines.append(
            f"- source_version_id={item.get('source_version_id')} "
            f"finding={item.get('finding_key')} certainty={item.get('certainty')} "
            f"quote={item.get('quote')!r}"
        )
    lines.append("")
    lines.append("Fictional evidence assessments (human-authored):")
    for item in assessments[:50]:
        lines.append(
            f"- assessment_id={item.get('id')} relation={item.get('relation')} "
            f"applicability={item.get('applicability')} "
            f"statement={item.get('statement')!r} rationale={item.get('rationale')!r}"
        )
    lines.append("")
    lines.append(
        "Reply with JSON only, in exactly this shape: "
        '{"claims": [{"text": "...", "support": "supports|contradicts|context", '
        '"citations": [{"type": "source|assessment", "id": 0}], '
        '"uncertainty": "low|moderate|high", "limits": "..."}], '
        '"abstentions": [{"topic": "...", '
        '"reason": "no_evidence|insufficient_evidence|out_of_scope|conflicting_evidence"}]}'
    )
    lines.append(
        "Every claim must cite at least one source version or assessment "
        "listed above. Do not cite anything else. Do not recommend "
        "treatment, select therapy, dose, or diagnose."
    )
    return "\n".join(lines)


def validate_output(payload: object, valid_sources: set[int],
                    valid_assessments: set[int]) -> ValidatedInvestigation:
    """Validate raw model JSON. Returns only kept claims; drops the rest."""
    if not isinstance(payload, dict):
        raise InvestigationError("Model output was not a JSON object")
    claims: list[dict] = []
    dropped: list[dict] = []
    for raw in payload.get("claims", []) if isinstance(payload.get("claims", []), list) else []:
        if not isinstance(raw, dict) or not isinstance(raw.get("text"), str) or not raw["text"].strip():
            dropped.append({"claim": raw, "reason": "missing_text"})
            continue
        if raw.get("uncertainty") not in UNCERTAINTIES:
            dropped.append({"claim": raw, "reason": "invalid_uncertainty"})
            continue
        if raw.get("support") not in ("supports", "contradicts", "context"):
            dropped.append({"claim": raw, "reason": "invalid_support"})
            continue
        if any(pattern.search(raw["text"]) for pattern in GUARD_PATTERNS):
            dropped.append({"claim": raw, "reason": "language_guard"})
            continue
        citations = raw.get("citations")
        if not isinstance(citations, list) or not citations:
            dropped.append({"claim": raw, "reason": "missing_citations"})
            continue
        resolved = True
        for cite in citations:
            if not isinstance(cite, dict):
                resolved = False
                break
            if cite.get("type") == "source" and isinstance(cite.get("id"), int) and cite["id"] in valid_sources:
                continue
            if cite.get("type") == "assessment" and isinstance(cite.get("id"), int) and cite["id"] in valid_assessments:
                continue
            resolved = False
            break
        if not resolved:
            dropped.append({"claim": raw, "reason": "unresolved_citation"})
            continue
        claims.append({
            "text": raw["text"].strip(),
            "kind": "hypothesis",
            "support": raw["support"],
            "citations": citations,
            "uncertainty": raw["uncertainty"],
            "limits": raw.get("limits", "") if isinstance(raw.get("limits"), str) else "",
        })
    abstentions: list[dict] = []
    for raw in payload.get("abstentions", []) if isinstance(payload.get("abstentions", []), list) else []:
        if isinstance(raw, dict) and isinstance(raw.get("topic"), str) and raw.get("reason") in ABSTAIN_REASONS:
            abstentions.append({"topic": raw["topic"], "reason": raw["reason"]})
    status = "completed" if claims else "abstained"
    if not claims and not abstentions:
        abstentions.append({"topic": "question", "reason": "insufficient_evidence"})
    return ValidatedInvestigation(
        status=status, claims=claims, abstentions=abstentions,
        dropped=dropped, model=META_MODEL, mode="live",
    )



# Server-owned adapter contract for the existing investigation function.
# These are configuration identifiers, not endpoints, secrets, authority grants
# or user-selected providers. Individual adapters require separate rights,
# security and clinical-data review before they may be installed.
PROVIDER_ID = re.compile(r"[a-z][a-z0-9_-]{0,39}\\Z")
MODEL_ID = re.compile(r"[A-Za-z0-9][A-Za-z0-9._:-]{0,79}\\Z")
MAX_PROVIDER_PROMPT_CHARS = 32000


def execute_bounded_model(
    template_id: str,
    facts: dict,
    *,
    invoke,
    provider_id: str,
    model_id: str,
    data_class: str = "synthetic",
    allowed_effects: tuple[str, ...] = ("propose_hypothesis",),
) -> ValidatedInvestigation:
    """Use one native evidence-and-review contract with any vetted adapter.

    This function deliberately has NO access to the CaseStore, HTTP request,
    credentials, tool bus, clinical approvals or writable medical operations.
    Only the server may select/inject an adapter; the current HTTP surface
    still exposes only the original Meta adapter and separately labeled replay.
    Returning a structured object does not create an authoritative finding.
    """
    if data_class != "synthetic":
        raise InvestigationError("Only synthetic demonstration data is permitted")
    if allowed_effects != ("propose_hypothesis",):
        raise InvestigationError("Only a review-pending hypothesis is permitted; clinical actions blocked")
    if (not isinstance(provider_id, str) or
            PROVIDER_ID.fullmatch(provider_id) is None):
        raise InvestigationError("Invalid server-selected provider identifier")
    if (not isinstance(model_id, str) or
            MODEL_ID.fullmatch(model_id) is None):
        raise InvestigationError("Invalid registered model identifier")
    if not callable(invoke):
        raise InvestigationError("No approved model adapter was supplied")
    if (not isinstance(facts, dict) or
            not isinstance(facts.get("question"), dict) or
            not isinstance(facts["question"].get("question"), str) or
            not isinstance(facts.get("assertions"), list) or
            not isinstance(facts.get("assessments"), list) or
            not isinstance(facts.get("valid_sources"), (set, frozenset)) or
            not isinstance(facts.get("valid_assessments"), (set, frozenset))):
        raise InvestigationError("Invalid source-bound model task context")
    for identifiers in (facts["valid_sources"], facts["valid_assessments"]):
        if any(type(item) is not int or item < 1 for item in identifiers):
            raise InvestigationError("Model citation identifiers must be positive integers")
    prompt = build_prompt(
        template_id, facts["question"]["question"], facts["assertions"],
        facts["assessments"])
    if len(prompt) > MAX_PROVIDER_PROMPT_CHARS:
        raise InvestigationError("Model prompt exceeds the bounded synthetic task limit")
    # The adapter gets only the already-scoped prompt. Secrets are resolved
    # within its server-owned closure and never included in model result rows.
    payload = invoke(prompt)
    if not isinstance(payload, dict):
        raise InvestigationError("Model adapter response must be structured JSON")
    if set(payload) - {"claims", "abstentions"}:
        raise InvestigationError("Model response contains unexpected action or data fields")
    validated = validate_output(
        payload, facts["valid_sources"], facts["valid_assessments"])
    # The model must not self-report its identity: label the result using the
    # server-selected adapter metadata, then preserve old source/review rules.
    validated.model = model_id
    validated.mode = "live"
    return validated


def call_meta_api(prompt: str, api_key: str) -> dict:
    """One bounded Meta Model API call. Raises InvestigationError on failure."""
    body = json.dumps({
        "model": META_MODEL,
        "messages": [{"role": "user", "content": prompt}],
        "max_tokens": 4096,
    }).encode("utf-8")
    request = urllib.request.Request(
        META_API_URL, data=body,
        headers={"Content-Type": "application/json", "Authorization": f"Bearer {api_key}"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=90) as response:
            data = json.loads(response.read().decode("utf-8"))
    except Exception as error:  # network, HTTP, or decode failure: no partial claim
        raise InvestigationError(f"Meta Model API call failed: {type(error).__name__}") from error
    texts = []
    for block in data.get("content", []) if isinstance(data.get("content"), list) else []:
        if isinstance(block, dict) and block.get("type") == "text" and isinstance(block.get("text"), str):
            texts.append(block["text"])
    joined = "\n".join(texts)
    start = joined.find("{")
    end = joined.rfind("}")
    if start < 0 or end <= start:
        raise InvestigationError("Meta Model API output contained no JSON object")
    try:
        return json.loads(joined[start:end + 1])
    except json.JSONDecodeError as error:
        raise InvestigationError("Meta Model API output was not valid JSON") from error


def meta_api_key() -> str:
    key = os.environ.get("META_API_KEY", "")
    if not key:
        raise InvestigationError(
            "META_API_KEY is not set; run with mode=replay for the recorded "
            "offline demonstration, or set the operator key and retry"
        )
    return key
