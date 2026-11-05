"""Deterministic orchestrator: assignment + roster (program plan C3).

This module is code, not a model. It decides, before any agent event,
which named agents work a run; it records that decision in the existing
events ledger as ``route.decided``; it enforces the assignment when a
write is stored; and it answers the roster (who is doing what,
busy/idle). It never calls a model, never fetches external data, and
never writes to any ledger but the case's own events table.

Pipeline position (Notion OI-09 section 4, plan section 5):
``route.decided {templateId, agents[], reason, budget}`` before any
agent event. A run with no ``route.decided`` record is not
reproducible: ``check_replay`` fails it with ``missing_route``.
A write whose ``agentRole`` is not among the route's agents is
rejected at save time (``unassigned_agent``); a write after the
assignment's lease has expired is rejected (``lease_expired``).

Route policy (``route-policy:1``) — the single-writer bridge, carried
over from the slice-1 write contract: the one existing model call
writes as A1 (Intake & Extraction) for every template, so every route
assigns A1 and only A1. The policy function
(``route_agents_for_template``) is the single place that changes when
parallel role agents land: it takes the template and returns the
assigned roles, so per-template assignment arrives as a policy change,
not a rewrite of the enforcement. The Skeptic (A6) is not assigned by
any route in this slice: it arrives with the repair round in C4.

Assignment fields (the route record carries scope + lease + authority):

- ``agents``: the assigned roles (``AGENT_ROLES`` keys).
- ``scope``: the dimensions the assigned agents may work in, derived
  from ``AGENT_SCOPE`` — the union of the assigned roles' dimensions.
  A1 works data-integration; A2/A3 analysis; A4/A5
  hypothesis-generation; A6 verification. Care coordination has no
  role agent in the adopted roster, so no assignment carries it.
- ``leaseUntil``: ``decidedAt`` plus ``lease_seconds`` (default one
  hour). The lease bounds the run's execution window: a write after
  it is rejected. It does not bound the historical record — a replay
  long after the run does not fail on an expired lease.
- ``authority``: the account role that authorized the run
  (``clinician`` or ``operator`` — the #515 role permissions: a
  patient reads only their own bound case, an auditor works no case
  route, so neither may authorize a run).
- ``budget``: ``{"maxModelCalls": 1}`` by default — the pipeline makes
  exactly one model call per run today. The budget is recorded, not
  enforced on call counts: the repair round in C4 will need a second
  call, and the budget grows then.

Roster semantics: an agent is busy while it holds a live assignment —
a ``route.decided`` record whose lease has not expired and whose run
has not yet stored an investigation. A run is complete when an
``investigation_created`` event with a higher event id exists whose
stored contract names the route. Re-deciding a route supersedes the
earlier decision: only the latest ``route.decided`` per route id is
live. A route whose lease expired without a stored investigation is
idle again — the assignment lapsed, it did not complete.

Fictional data only. No treatment selection, no clinical inference,
no autonomous decision: assignment is a deterministic routing record,
never a clinical judgment.
"""

from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone

from .agent_writes import (
    AGENT_ROLES,
    WriteContractRejected,
    build_route_id,
    parse_route_id,
)
from .investigation import TEMPLATES
from .store import InvalidInput, now_utc

ROUTE_KIND = "route.decided"
ROUTE_POLICY_VERSION = "route-policy:1"

# Route policy v1: the single-writer bridge. Every template routes to
# A1 only. The reason is recorded on every route so the record itself
# states why no other role is assigned.
ROUTE_POLICY_REASON = (
    "route-policy:1 single-writer bridge: the one existing model call "
    "writes as A1 for every template; parallel role agents take over "
    "their own roles when the toolsets land"
)

# Role -> dimensions the role may work in (plan D1-D5 + verification).
# Care coordination (D6-D9) has no role agent in the adopted roster.
AGENT_SCOPE = {
    "A1": ["data-integration"],
    "A2": ["analysis"],
    "A3": ["analysis"],
    "A4": ["hypothesis-generation"],
    "A5": ["hypothesis-generation"],
    "A6": ["verification"],
}

# Account roles that may authorize a run (#515 role permissions).
AUTHORIZING_ROLES = frozenset({"clinician", "operator"})

DEFAULT_LEASE_SECONDS = 3600
DEFAULT_BUDGET = {"maxModelCalls": 1}

# The route record fields, in canonical order. Exactly one place
# defines them.
ROUTE_FIELDS = (
    "routeId",
    "caseId",
    "templateId",
    "questionId",
    "agents",
    "reason",
    "budget",
    "authority",
    "scope",
    "decidedAt",
    "leaseUntil",
    "policyVersion",
    "eventId",
)


def _parse_instant(value: object, field: str) -> datetime:
    """Parse an ISO-8601 instant to an aware datetime or reject it."""
    if not isinstance(value, str) or not value:
        raise WriteContractRejected(
            "invalid_route", field, "must be an ISO-8601 timestamp"
        )
    try:
        instant = datetime.fromisoformat(value)
    except ValueError:
        raise WriteContractRejected(
            "invalid_route", field, "must be an ISO-8601 timestamp"
        ) from None
    if instant.tzinfo is None:
        raise WriteContractRejected(
            "invalid_route", field, "must carry a timezone offset"
        )
    return instant


def _now_or(value: str | None) -> datetime:
    if value is None:
        return datetime.now(timezone.utc)
    return _parse_instant(value, "now")


def route_agents_for_template(template: str) -> list[str]:
    """Assigned roles for a template under the current route policy.

    Policy v1 assigns A1 and only A1 for every template: the
    single-writer bridge. This function is the single place that
    changes when parallel role agents land.
    """
    if template not in TEMPLATES:
        raise InvalidInput("Unknown investigation template")
    return ["A1"]


def route_scope_for_agents(agents: list[str]) -> list[str]:
    """Dimensions the assigned roles may work in, in canonical order."""
    dimensions: list[str] = []
    for dimension in (
        "data-integration",
        "analysis",
        "hypothesis-generation",
        "verification",
        "provenance",
        "care-coordination",
    ):
        if any(dimension in AGENT_SCOPE[role] for role in agents):
            dimensions.append(dimension)
    return dimensions


def validate_route_record(data: object) -> dict:
    """Validate a route record; return its normalized form or reject it.

    Every missing field is rejected with reason "invalid_route" naming
    the field; "invalid_authority" names a role that may not authorize
    a run. Extra fields are dropped: the normalized record holds
    exactly ROUTE_FIELDS, so the record has one canonical shape.
    ``eventId`` may be None on a record not yet written to the ledger.
    """
    if not isinstance(data, dict):
        raise WriteContractRejected("invalid_route", None, "route must be an object")
    for field in ROUTE_FIELDS:
        if field not in data:
            raise WriteContractRejected("invalid_route", field, "field is required")
    route_id = data["routeId"]
    if not isinstance(route_id, str) or not route_id:
        raise WriteContractRejected("invalid_route", "routeId", "must be a non-empty string")
    try:
        case_id, template, question_id = parse_route_id(route_id)
    except WriteContractRejected:
        raise WriteContractRejected(
            "invalid_route", "routeId", "route id malformed"
        ) from None
    if data["caseId"] != case_id:
        raise WriteContractRejected(
            "invalid_route", "caseId", "does not match the route id"
        )
    if data["templateId"] != template:
        raise WriteContractRejected(
            "invalid_route", "templateId", "does not match the route id"
        )
    if data["questionId"] != question_id:
        raise WriteContractRejected(
            "invalid_route", "questionId", "does not match the route id"
        )
    if template not in TEMPLATES:
        raise WriteContractRejected(
            "invalid_route", "templateId", "unknown investigation template"
        )
    agents = data["agents"]
    if (
        not isinstance(agents, list)
        or not agents
        or any(not isinstance(role, str) or role not in AGENT_ROLES for role in agents)
        or len(set(agents)) != len(agents)
    ):
        raise WriteContractRejected(
            "invalid_route", "agents",
            f"must be a non-empty list of distinct roles in {sorted(AGENT_ROLES)}",
        )
    reason = data["reason"]
    if not isinstance(reason, str) or not reason:
        raise WriteContractRejected("invalid_route", "reason", "must be a non-empty string")
    budget = data["budget"]
    if not isinstance(budget, dict):
        raise WriteContractRejected("invalid_route", "budget", "must be an object")
    max_calls = budget.get("maxModelCalls")
    if max_calls is not None and (type(max_calls) is not int or max_calls < 1):
        raise WriteContractRejected(
            "invalid_route", "budget", "maxModelCalls must be a positive integer"
        )
    authority = data["authority"]
    if not isinstance(authority, str) or authority not in AUTHORIZING_ROLES:
        raise WriteContractRejected(
            "invalid_authority", "authority",
            f"must be one of {sorted(AUTHORIZING_ROLES)}",
        )
    scope = data["scope"]
    if (
        not isinstance(scope, list)
        or any(not isinstance(item, str) or not item for item in scope)
    ):
        raise WriteContractRejected(
            "invalid_route", "scope", "must be a list of dimension names"
        )
    expected_scope = route_scope_for_agents(list(agents))
    if sorted(scope) != sorted(expected_scope):
        raise WriteContractRejected(
            "invalid_route", "scope",
            f"must be the dimensions of the assigned roles: {expected_scope}",
        )
    decided_at = _parse_instant(data["decidedAt"], "decidedAt")
    lease_until = _parse_instant(data["leaseUntil"], "leaseUntil")
    if lease_until <= decided_at:
        raise WriteContractRejected(
            "invalid_route", "leaseUntil", "must be after decidedAt"
        )
    policy_version = data["policyVersion"]
    if not isinstance(policy_version, str) or not policy_version:
        raise WriteContractRejected(
            "invalid_route", "policyVersion", "must be a non-empty string"
        )
    event_id = data["eventId"]
    if event_id is not None and type(event_id) is not int:
        raise WriteContractRejected(
            "invalid_route", "eventId", "must be an integer or null"
        )
    return {
        "routeId": route_id,
        "caseId": case_id,
        "templateId": template,
        "questionId": question_id,
        "agents": list(agents),
        "reason": reason,
        "budget": dict(budget),
        "authority": authority,
        "scope": list(scope),
        "decidedAt": data["decidedAt"],
        "leaseUntil": data["leaseUntil"],
        "policyVersion": policy_version,
        "eventId": event_id,
    }


def decide_route(store, case_id: str, template: str, question_id: int,
                 authority: str, *, lease_seconds: int = DEFAULT_LEASE_SECONDS,
                 now: str | None = None, budget: dict | None = None,
                 reason: str | None = None) -> dict:
    """Decide a route and record it in the ledger before any agent event.

    Returns the normalized route record, including the ledger
    ``eventId`` of the ``route.decided`` event. Deciding the same
    route twice appends a second event; the latest decision supersedes
    the earlier one. ``now`` is an ISO-8601 override for tests; the
    live path always uses the current time.
    """
    if template not in TEMPLATES:
        raise InvalidInput("Unknown investigation template")
    if type(question_id) is not int:
        raise InvalidInput("question_id must be an integer")
    if not isinstance(authority, str) or authority not in AUTHORIZING_ROLES:
        raise WriteContractRejected(
            "invalid_authority", "authority",
            f"must be one of {sorted(AUTHORIZING_ROLES)}",
        )
    if type(lease_seconds) is not int or lease_seconds < 1:
        raise WriteContractRejected(
            "invalid_route", "leaseUntil", "lease_seconds must be a positive integer"
        )
    decided = _now_or(now)
    lease_until = decided + timedelta(seconds=lease_seconds)
    agents = route_agents_for_template(template)
    record = validate_route_record({
        "routeId": build_route_id(case_id, template, question_id),
        "caseId": case_id,
        "templateId": template,
        "questionId": question_id,
        "agents": agents,
        "reason": reason if reason is not None else ROUTE_POLICY_REASON,
        "budget": dict(budget) if budget is not None else dict(DEFAULT_BUDGET),
        "authority": authority,
        "scope": route_scope_for_agents(agents),
        "decidedAt": decided.isoformat(timespec="seconds"),
        "leaseUntil": lease_until.isoformat(timespec="seconds"),
        "policyVersion": ROUTE_POLICY_VERSION,
        "eventId": None,
    })
    event_id = store.record_route_decided(case_id, record)
    record["eventId"] = event_id
    return record


def get_route(store, case_id: str, route_id: str) -> dict | None:
    """Latest ``route.decided`` record for a route id, or None.

    A malformed stored record is rejected loudly (``invalid_route``):
    the ledger is append-only and trusted, so a record that does not
    validate is a data-integrity problem, not a missing route.
    """
    raw = store.get_route_decided(case_id, route_id)
    if raw is None:
        return None
    return validate_route_record(raw)


def check_assignment(store, case_id: str, route_id: str, agent_role: str,
                     *, now: str | None = None, require_route: bool = True,
                     check_lease: bool = True) -> dict | None:
    """Enforce that a role is assigned to a route.

    Returns the route record when the assignment holds. Raises
    ``WriteContractRejected`` with a typed reason otherwise:

    - ``missing_route`` when no ``route.decided`` record exists and
      ``require_route`` is true;
    - ``unassigned_agent`` when the role is not among the route's
      agents;
    - ``lease_expired`` when the assignment's lease has expired and
      ``check_lease`` is true.

    ``require_route=False`` is the save-time grandfather path: a write
    whose route was never decided (a pre-C3 row) is not rejected at
    save time — the replay is the check that catches it. ``check_lease
    =False`` is the replay path: the lease bounds the run's execution
    window, not the historical record.
    """
    route = get_route(store, case_id, route_id)
    if route is None:
        if require_route:
            raise WriteContractRejected(
                "missing_route", "routeId",
                f"no route.decided record for {route_id}",
            )
        return None
    if agent_role not in route["agents"]:
        raise WriteContractRejected(
            "unassigned_agent", "agentRole",
            f"agent {agent_role} is not assigned to {route_id} "
            f"(assigned: {route['agents']})",
        )
    if check_lease:
        instant = _now_or(now)
        if instant >= _parse_instant(route["leaseUntil"], "leaseUntil"):
            raise WriteContractRejected(
                "lease_expired", "routeId",
                f"assignment for {route_id} expired at {route['leaseUntil']}",
            )
    return route


def roster(store, case_id: str, *, now: str | None = None) -> dict:
    """Roster for a case: every role, busy or idle, with live assignments.

    An assignment is live when it is the latest ``route.decided`` for
    its route, its lease has not expired, and no investigation has
    been stored for the route since the decision. A re-decision
    supersedes the earlier one; an expired lease lapses the assignment
    without completing it.
    """
    instant = _now_or(now)
    events = [
        dict(row)
        for row in store.db.execute(
            "SELECT id, kind, details FROM events WHERE case_id=? ORDER BY id",
            (case_id,),
        ).fetchall()
    ]
    routes: dict[str, dict] = {}
    route_event_ids: dict[str, int] = {}
    for event in events:
        if event["kind"] != ROUTE_KIND:
            continue
        try:
            record = validate_route_record(json.loads(event["details"]))
        except (WriteContractRejected, ValueError, TypeError):
            continue
        routes[record["routeId"]] = record
        route_event_ids[record["routeId"]] = int(event["id"])
    investigation_route: dict[int, str] = {}
    for row in store.db.execute(
        "SELECT investigation_id, contract_json FROM agent_writes WHERE case_id=?",
        (case_id,),
    ).fetchall():
        try:
            contract = json.loads(row[1])
        except (json.JSONDecodeError, TypeError):
            continue
        if isinstance(contract, dict) and isinstance(contract.get("routeId"), str):
            investigation_route[int(row[0])] = contract["routeId"]
    completed: set[str] = set()
    for event in events:
        if event["kind"] != "investigation_created":
            continue
        try:
            details = json.loads(event["details"])
        except (json.JSONDecodeError, TypeError):
            continue
        investigation_id = details.get("investigation_id")
        if type(investigation_id) is not int:
            continue
        route_id = investigation_route.get(investigation_id)
        if route_id is None:
            continue
        if int(event["id"]) > route_event_ids.get(route_id, 0):
            completed.add(route_id)
    agents: dict[str, dict] = {}
    for role in sorted(AGENT_ROLES):
        assignments = []
        for route_id, record in sorted(routes.items()):
            if role not in record["agents"]:
                continue
            if route_id in completed:
                continue
            if instant >= _parse_instant(record["leaseUntil"], "leaseUntil"):
                continue
            assignments.append({
                "routeId": route_id,
                "templateId": record["templateId"],
                "questionId": record["questionId"],
                "scope": list(record["scope"]),
                "authority": record["authority"],
                "decidedAt": record["decidedAt"],
                "leaseUntil": record["leaseUntil"],
            })
        agents[role] = {
            "roleName": AGENT_ROLES[role],
            "status": "busy" if assignments else "idle",
            "assignments": assignments,
        }
    return {
        "caseId": case_id,
        "asOf": instant.isoformat(timespec="seconds"),
        "agents": agents,
    }
