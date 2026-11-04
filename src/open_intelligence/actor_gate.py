"""Minimal deny-by-default fictional actor gate, issue 114 (WS-02).

This is a pure, tested contract for the H1 fictional actor, case, and
purpose checks. It is NOT wired to the HTTP routes yet, and it is NOT
production authentication, consent, or clinician credential verification.
Browser role labels must never be treated as clinical verification, and
this gate must never be presented as proof of real identity or consent.

Rules, fail closed:
- An actor that is not in the fictional registry is denied.
- A revoked actor is denied, even if its role and case would otherwise match.
- An actor may only touch cases listed for that actor; any other case,
  including a nonexistent case, is denied as wrong case.
- An actor may only use purposes listed for that actor's role; any other
  purpose is denied.
- Empty or non-string actor, case, or purpose values are denied.

Fictional registry used by the tests:
- clinician-01: role clinician, cases CASE-ALPHA and CASE-BETA,
  purposes read, investigate, review.
- navigator-01: role navigator, case CASE-ALPHA only,
  purposes read, investigate.
- clinician-revoked: a revoked clinician, denied on every request.
"""

from __future__ import annotations

ACTORS = {
    "clinician-01": {
        "role": "clinician",
        "cases": frozenset({"CASE-ALPHA", "CASE-BETA"}),
        "purposes": frozenset({"read", "investigate", "review"}),
        "revoked": False,
    },
    "navigator-01": {
        "role": "navigator",
        "cases": frozenset({"CASE-ALPHA"}),
        "purposes": frozenset({"read", "investigate"}),
        "revoked": False,
    },
    "clinician-revoked": {
        "role": "clinician",
        "cases": frozenset({"CASE-ALPHA", "CASE-BETA"}),
        "purposes": frozenset({"read", "investigate", "review"}),
        "revoked": True,
    },
}


def check(actor_id, case_id, purpose):
    """Return an allowed/denied decision for one fictional request.

    Returns a dict with ``allowed`` (bool) and ``reason`` (str).
    Reasons: allowed, unknown_actor, revoked_actor, wrong_case,
    denied_purpose, invalid_input. Nothing here touches a database,
    a network, or a real identity system.
    """
    if not isinstance(actor_id, str) or not actor_id.strip():
        return {"allowed": False, "reason": "invalid_input"}
    if not isinstance(case_id, str) or not case_id.strip():
        return {"allowed": False, "reason": "invalid_input"}
    if not isinstance(purpose, str) or not purpose.strip():
        return {"allowed": False, "reason": "invalid_input"}
    actor = ACTORS.get(actor_id)
    if actor is None:
        return {"allowed": False, "reason": "unknown_actor"}
    if actor["revoked"]:
        return {"allowed": False, "reason": "revoked_actor"}
    if case_id not in actor["cases"]:
        return {"allowed": False, "reason": "wrong_case"}
    if purpose not in actor["purposes"]:
        return {"allowed": False, "reason": "denied_purpose"}
    return {"allowed": True, "reason": "allowed"}
