"""Deterministic presentation of saved hypotheses for the existing review ledger.

This module neither runs a model nor decides that a finding is clinically true.
Every citation must first resolve against the caller's case/question transaction.
"""
from __future__ import annotations

MAX_REVIEW_DRAFT = 65536
GROUPS = (("supports", "Supporting findings"),
          ("contradicts", "Contradicting findings"),
          ("context", "Context findings"))
REASONS = frozenset({"no_evidence", "insufficient_evidence", "out_of_scope", "conflicting_evidence"})


def render_review_draft(run: dict, available: dict[tuple[str, int], dict]) -> tuple[str, list[dict]]:
    """Return plain text and the exact resolved citations, rejecting malformed output.

    Original model output is retained by CaseStore. No invalid claim is repaired
    here, and dropped claim text is never copied into a review draft.
    """
    claims, abstentions, dropped = run["claims"], run["abstentions"], run["dropped"]
    if not all(isinstance(value, list) for value in (claims, abstentions, dropped)):
        raise ValueError("Saved investigation output is malformed; a new run is required")
    grouped = {key: [] for key, _ in GROUPS}
    used: dict[tuple[str, int], dict] = {}
    for claim in claims:
        if (not isinstance(claim, dict) or
            claim.get("support") not in grouped or
            claim.get("uncertainty") not in ("low", "moderate", "high") or
            not isinstance(claim.get("text"), str) or not claim["text"].strip() or
            not isinstance(claim.get("limits"), str) or
            not isinstance(claim.get("citations"), list) or not claim["citations"]):
            raise ValueError("Saved investigation claim is malformed; a new run is required")
        labels = []
        for citation in claim["citations"]:
            if (not isinstance(citation, dict) or citation.get("type") not in ("source", "assessment") or
                type(citation.get("id")) is not int or citation["id"] < 1):
                raise ValueError("Saved investigation citation must use a positive integer identifier")
            key = (citation["type"], citation["id"])
            if key not in available:
                raise ValueError("Saved investigation citation is unavailable in this case and question")
            resolved = available[key]
            used[key] = resolved
            labels.append(resolved["label"])
        grouped[claim["support"]].append(
            [claim["text"], "Uncertainty: " + claim["uncertainty"],
             "Limits: " + (claim["limits"] or "None supplied; reviewer must assess limitations."),
             "Citations: " + "; ".join(labels), ""])
    lines = ["Model-assisted review draft — unreviewed hypotheses", "",
             f"Model investigation #{run['id']} | Mode: {run['mode']} | Model: {run['model']}",
             f"Template: {run['template']} | Run status: {run['status']}",
             "Preparation does not acknowledge human review.", ""]
    for key, heading in GROUPS:
        lines.extend([heading, ""])
        for finding in grouped[key]:
            lines.extend(finding)
        if not grouped[key]:
            lines.extend(["No validated findings in this category.", ""])
    lines.extend(["Missing information and abstentions", ""])
    for abstention in abstentions:
        if (not isinstance(abstention, dict) or not isinstance(abstention.get("topic"), str) or
            not abstention["topic"].strip() or abstention.get("reason") not in REASONS):
            raise ValueError("Saved investigation abstention is malformed; a new run is required")
        lines.append(abstention["topic"] + " — " + abstention["reason"])
    if not abstentions:
        lines.append("No explicit abstentions supplied; completeness has not been established.")
    lines.extend(["", f"Validation omitted {len(dropped)} claim(s); rejected text is not part of this report.",
                  "All findings remain hypotheses. Synthetic research demonstration only; not medical advice."])
    text = "\n".join(lines)
    if len(text) > MAX_REVIEW_DRAFT:
        raise ValueError("Generated review draft exceeds the local limit; a smaller new run is required")
    return text, list(used.values())
