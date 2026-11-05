"""Per-agent write contract (program plan section 5.4; Notion OI-09 section 5.4).

This module is the single owner of the write contract. Every agent/model
write carries:

- writeId: unique id for this write
- agentId: stable id of the writing agent
- agentRole: one of A1-A6 (A1 Intake & Extraction, A2 Longitudinal,
  A3 Molecular, A4 Literature, A5 Trials, A6 Skeptic)
- agentVersion: version of the agent implementation that wrote
- promptVersion: version of the prompt template that was used
- modelId: model that produced the output
- runId: unique id for the run this write belongs to
- routeId: id of the route decision that produced this run
- snapshotAt: the L1 as-of marker (ledger event anchor + timestamp)
- inputs: one entry per input the run read, each identified by exactly
  one of sourceVersionId / assertionId / evidenceSnapshotId plus a
  contentHash of the input as read
- toolCalls: one entry per tool call the run made, in order

A write missing any contract field is rejected with a typed reason
(``WriteContractRejected`` carries ``reason`` and ``field``); nothing
is stored without a complete, validated contract. The store enforces
this at ``save_investigation``: a call with no contract, an invalid
contract, a contract bound to a different route, or a contract whose
model does not match the validated output is rejected.

Slice-1 mapping decisions (provisional until the roster/pipeline
slices land; the contract shape itself is final):

- The single existing model call is the roster's first writer. It
  writes as A1 (Intake & Extraction) for every template, with
  agentId ``agent-A1``. Parallel role agents (slices 3-4) take over
  their own roles; this bridge mapping is recorded here, not in the
  investigation module, so there is exactly one place to change it.
- ``routeId`` is deterministic: ``route:<case_id>:<template>:<question_id>``.
  No ``route.decided`` record exists yet (that is pipeline work); the
  id is derived from the route decision's inputs, so a replay can
  recover the template and question from the contract alone.
- ``snapshotAt`` is ``{"as_of": <ISO-8601 UTC>, "event_id": <latest
  ledger event id for the case, or None>}``. The event id is the L1
  as-of anchor; the per-input content hashes are what a replay
  verifies against the ledger.
- ``evidenceSnapshotId`` carries an evidence-assessment id. In the
  vanilla tree the assessable evidence unit is the evidence
  assessment (``evidence_assessments.id``); its content hash covers
  the assessment row plus the statement of the evidence version it
  rests on. A dedicated L1 evidence-snapshot record is later work.
- ``toolCalls`` is empty: no toolsets exist yet (T1-T4 arrive in
  slice 4). The run's replay cache is its recorded ``inputs`` plus
  the route: given the route, the snapshot inputs, and the stored
  claims, a replay re-derives the prompt inputs and re-validates the
  stored claims. An empty toolCalls list is a complete contract, not
  a missing field.

Replay (``check_replay``) reproduces a run from {routeId, snapshotAt,
toolCall cache}: it re-reads every recorded input from the ledger and
requires an exact content-hash match with the source version still
current, then re-validates the stored claims against the recorded
input ids and requires the identical kept claims. A superseded source
version, a changed input, a missing input, a route mismatch, or a
tampered contract all make the replay not reproducible, with a typed
reason. Replay checks the snapshot, not current freshness: a new
source that the ledger marks stale does not by itself invalidate a
replay whose recorded inputs are intact.

Fictional data only. No treatment selection, no clinical inference,
no autonomous decision: stored output stays kind="hypothesis" and
review_state="pending" at the investigation layer.
"""

from __future__ import annotations

import hashlib
import json
import uuid
from datetime import datetime

from .investigation import TEMPLATES, validate_output
from .store import InvalidInput, now_utc

# Roster (DEC-09-P1/P2/P3): five LLM role agents plus the Skeptic.
AGENT_ROLES = {
    "A1": "Intake & Extraction",
    "A2": "Longitudinal",
    "A3": "Molecular",
    "A4": "Literature",
    "A5": "Trials",
    "A6": "Skeptic",
}

# The contract fields, in canonical order. Exactly one place defines them.
CONTRACT_FIELDS = (
    "writeId",
    "agentId",
    "agentRole",
    "agentVersion",
    "promptVersion",
    "modelId",
    "runId",
    "routeId",
    "snapshotAt",
    "inputs",
    "toolCalls",
)

AGENT_VERSION = "1.0.0"
PROMPT_VERSION = "1"

# Slice-1 bridge: the single existing model call writes as A1 for every
# template until the roster wires parallel role agents.
TEMPLATE_AGENT_ROLE = {template: "A1" for template in TEMPLATES}

# Typed rejection reasons. "missing_field" / "invalid_field" /
# "invalid_role" / "invalid_inputs" / "invalid_tool_calls" /
# "invalid_snapshot" are raised by validation; "missing_write_contract"
# when no contract is supplied at all; "contract_mismatch" when the
# contract's model or route does not match the investigation it is
# attached to; "route_mismatch" / "stale_snapshot" / "missing_input" /
# "inputs_changed" / "claims_not_reproducible" are replay verdicts.
REJECTION_REASONS = frozenset({
    "missing_field",
    "invalid_field",
    "invalid_role",
    "invalid_inputs",
    "invalid_tool_calls",
    "invalid_snapshot",
    "invalid_contract",
    "missing_write_contract",
    "contract_mismatch",
    "route_mismatch",
    "stale_snapshot",
    "missing_input",
    "inputs_changed",
    "claims_not_reproducible",
})


class WriteContractRejected(InvalidInput):
    """A write contract is missing, incomplete, or does not bind to its run.

    ``reason`` is one of REJECTION_REASONS; ``field`` names the contract
    field at fault when one applies. Subclasses InvalidInput so the HTTP
    layer reports it as a 422 like every other bad input.
    """

    def __init__(self, reason: str, field: str | None = None, detail: str = ""):
        self.reason = reason
        self.field = field
        self.detail = detail
        message = f"Write contract rejected: {reason}"
        if field is not None:
            message += f" (field: {field})"
        if detail:
            message += f": {detail}"
        super().__init__(message)


def content_hash(value: object) -> str:
    """SHA-256 of the canonical JSON encoding of ``value``."""
    canonical = json.dumps(value, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def _is_hash(value: object) -> bool:
    return (
        isinstance(value, str)
        and len(value) == 64
        and all(char in "0123456789abcdef" for char in value)
    )


def build_route_id(case_id: str, template: str, question_id: int) -> str:
    """Deterministic route id for a route decision (case, template, question)."""
    return f"route:{case_id}:{template}:{question_id}"


def parse_route_id(route_id: object) -> tuple[str, str, int]:
    """Split a route id back into (case_id, template, question_id)."""
    if not isinstance(route_id, str) or not route_id.startswith("route:"):
        raise WriteContractRejected("invalid_field", "routeId", "route id malformed")
    parts = route_id.split(":")
    if len(parts) != 4:
        raise WriteContractRejected("invalid_field", "routeId", "route id malformed")
    _, case_id, template, question_raw = parts
    try:
        question_id = int(question_raw)
    except ValueError:
        raise WriteContractRejected(
            "invalid_field", "routeId", "route question id is not an integer"
        ) from None
    if not case_id or not template or str(question_id) != question_raw:
        raise WriteContractRejected("invalid_field", "routeId", "route id malformed")
    return case_id, template, question_id


def _validate_snapshot_at(value: object) -> dict:
    if not isinstance(value, dict):
        raise WriteContractRejected("invalid_snapshot", "snapshotAt", "must be an object")
    as_of = value.get("as_of")
    if not isinstance(as_of, str) or not as_of:
        raise WriteContractRejected("invalid_snapshot", "snapshotAt", "as_of is required")
    try:
        datetime.fromisoformat(as_of)
    except ValueError:
        raise WriteContractRejected(
            "invalid_snapshot", "snapshotAt", "as_of is not ISO-8601"
        ) from None
    event_id = value.get("event_id")
    if event_id is not None and type(event_id) is not int:
        raise WriteContractRejected(
            "invalid_snapshot", "snapshotAt", "event_id must be an integer or null"
        )
    return {"as_of": as_of, "event_id": event_id}


def _validate_inputs(value: object) -> list[dict]:
    if not isinstance(value, list):
        raise WriteContractRejected("invalid_inputs", "inputs", "must be a list")
    normalized: list[dict] = []
    id_keys = ("sourceVersionId", "assertionId", "evidenceSnapshotId")
    for entry in value:
        if not isinstance(entry, dict):
            raise WriteContractRejected("invalid_inputs", "inputs", "entry must be an object")
        present = [key for key in id_keys if key in entry]
        if len(present) != 1:
            raise WriteContractRejected(
                "invalid_inputs", "inputs",
                "entry needs exactly one of sourceVersionId, assertionId, evidenceSnapshotId",
            )
        key = present[0]
        if type(entry[key]) is not int:
            raise WriteContractRejected(
                "invalid_inputs", "inputs", f"{key} must be an integer"
            )
        content_hash_value = entry.get("contentHash")
        if not _is_hash(content_hash_value):
            raise WriteContractRejected(
                "invalid_inputs", "inputs", "contentHash must be a SHA-256 hex digest"
            )
        normalized.append({key: entry[key], "contentHash": content_hash_value})
    return normalized


def _validate_tool_calls(value: object) -> list[dict]:
    if not isinstance(value, list):
        raise WriteContractRejected("invalid_tool_calls", "toolCalls", "must be a list")
    normalized: list[dict] = []
    for entry in value:
        if not isinstance(entry, dict):
            raise WriteContractRejected(
                "invalid_tool_calls", "toolCalls", "entry must be an object"
            )
        tool = entry.get("tool")
        if not isinstance(tool, str) or not tool:
            raise WriteContractRejected(
                "invalid_tool_calls", "toolCalls", "tool is required"
            )
        arguments = entry.get("arguments")
        if not isinstance(arguments, dict):
            raise WriteContractRejected(
                "invalid_tool_calls", "toolCalls", "arguments must be an object"
            )
        result_hash = entry.get("resultHash")
        if not _is_hash(result_hash):
            raise WriteContractRejected(
                "invalid_tool_calls", "toolCalls",
                "resultHash must be a SHA-256 hex digest",
            )
        normalized.append(
            {"tool": tool, "arguments": dict(arguments), "resultHash": result_hash}
        )
    return normalized


def validate_write_contract(data: object) -> dict:
    """Validate a write contract; return its normalized form or reject it.

    Every missing field is rejected with reason "missing_field" naming
    the field. Extra fields are dropped: the normalized contract holds
    exactly CONTRACT_FIELDS, so the contract has one canonical shape.
    """
    if not isinstance(data, dict):
        raise WriteContractRejected("invalid_contract", None, "contract must be an object")
    for field in CONTRACT_FIELDS:
        if field not in data:
            raise WriteContractRejected("missing_field", field)
    for field in ("writeId", "agentId", "agentVersion", "promptVersion", "modelId", "runId", "routeId"):
        value = data[field]
        if not isinstance(value, str) or not value:
            raise WriteContractRejected("invalid_field", field, "must be a non-empty string")
    role = data["agentRole"]
    if not isinstance(role, str) or role not in AGENT_ROLES:
        raise WriteContractRejected(
            "invalid_role", "agentRole", f"must be one of {sorted(AGENT_ROLES)}"
        )
    parse_route_id(data["routeId"])
    return {
        "writeId": data["writeId"],
        "agentId": data["agentId"],
        "agentRole": role,
        "agentVersion": data["agentVersion"],
        "promptVersion": data["promptVersion"],
        "modelId": data["modelId"],
        "runId": data["runId"],
        "routeId": data["routeId"],
        "snapshotAt": _validate_snapshot_at(data["snapshotAt"]),
        "inputs": _validate_inputs(data["inputs"]),
        "toolCalls": _validate_tool_calls(data["toolCalls"]),
    }


def build_write_contract(*, agent_role: str, model_id: str, route_id: str,
                         snapshot_at: dict, inputs: list[dict],
                         tool_calls: list[dict] | None = None,
                         agent_id: str | None = None,
                         agent_version: str = AGENT_VERSION,
                         prompt_version: str,
                         write_id: str | None = None,
                         run_id: str | None = None) -> dict:
    """Build and validate a write contract, generating fresh ids as needed."""
    contract = validate_write_contract({
        "writeId": write_id or uuid.uuid4().hex,
        "agentId": agent_id or f"agent-{agent_role}",
        "agentRole": agent_role,
        "agentVersion": agent_version,
        "promptVersion": prompt_version,
        "modelId": model_id,
        "runId": run_id or uuid.uuid4().hex,
        "routeId": route_id,
        "snapshotAt": snapshot_at,
        "inputs": list(inputs),
        "toolCalls": list(tool_calls) if tool_calls is not None else [],
    })
    return contract


def _latest_event_id(store, case_id: str) -> int | None:
    row = store.db.execute(
        "SELECT id FROM events WHERE case_id=? ORDER BY id DESC LIMIT 1",
        (case_id,),
    ).fetchone()
    return int(row[0]) if row is not None else None


def _source_hashes(store, source_ids: set[int]) -> dict[int, str]:
    if not source_ids:
        return {}
    placeholders = ",".join("?" for _ in source_ids)
    rows = store.db.execute(
        f"SELECT id, sha256 FROM source_versions WHERE id IN ({placeholders})",
        tuple(sorted(source_ids)),
    ).fetchall()
    return {int(row[0]): str(row[1]) for row in rows}


def build_investigation_contract(store, case_id: str, question_id: int,
                                 template: str, model_id: str,
                                 facts: dict | None = None) -> dict:
    """Build the write contract for one investigation run.

    Derives the route id, the L1 as-of snapshot marker, and the input
    list (source versions, assertions, evidence assessments) from the
    ledger state the run actually read. The caller passes ``facts``
    from ``store.investigation_facts`` when it already has them.
    """
    if template not in TEMPLATES:
        raise InvalidInput("Unknown investigation template")
    if facts is None:
        facts = store.investigation_facts(case_id, question_id)
    assertions = facts["assertions"]
    assessments = facts["assessments"]
    source_ids = {int(item["source_version_id"]) for item in assertions}
    hashes = _source_hashes(store, source_ids)
    missing = source_ids - set(hashes)
    if missing:
        raise WriteContractRejected(
            "missing_input", "inputs", f"source versions missing: {sorted(missing)}"
        )
    inputs: list[dict] = []
    for source_id in sorted(source_ids):
        inputs.append({"sourceVersionId": source_id, "contentHash": hashes[source_id]})
    for item in sorted(assertions, key=lambda entry: int(entry["id"])):
        inputs.append({
            "assertionId": int(item["id"]),
            "contentHash": content_hash({
                "source_version_id": int(item["source_version_id"]),
                "finding_key": item["finding_key"],
                "certainty": item["certainty"],
                "quote": item["quote"],
                "source_line": item["source_line"],
            }),
        })
    for item in sorted(assessments, key=lambda entry: int(entry["id"])):
        # evidenceSnapshotId is the evidence-assessment id in the vanilla
        # tree (see module docstring); the hash covers the assessment
        # plus the statement of the evidence version it rests on.
        inputs.append({
            "evidenceSnapshotId": int(item["id"]),
            "contentHash": content_hash({
                "relation": item["relation"],
                "applicability": item["applicability"],
                "rationale": item["rationale"],
                "statement": item["statement"],
            }),
        })
    return build_write_contract(
        agent_role=TEMPLATE_AGENT_ROLE[template],
        model_id=model_id,
        route_id=build_route_id(case_id, template, question_id),
        snapshot_at={"as_of": now_utc(), "event_id": _latest_event_id(store, case_id)},
        inputs=inputs,
        tool_calls=[],
        prompt_version=f"{template}:{PROMPT_VERSION}",
    )


def _replay_failure(reason: str, **extra: object) -> dict:
    result: dict = {"reproducible": False, "reason": reason}
    result.update(extra)
    return result


def check_replay(store, case_id: str, investigation_id: int) -> dict:
    """Check whether a stored investigation run is reproducible.

    Re-reads every recorded input from the ledger and requires an exact
    content-hash match with the source version still current, then
    re-validates the stored claims against the recorded input ids and
    requires the identical kept claims. Returns
    ``{"reproducible": True, ...}`` or ``{"reproducible": False,
    "reason": <typed>}``; never raises for a stored-contract problem.
    """
    investigation = store.get_investigation(case_id, investigation_id)
    contract = investigation.get("write_contract")
    if contract is None:
        return _replay_failure(
            "missing_write_contract", investigation_id=investigation_id,
            detail="Investigation was stored before the write contract existed.",
        )
    try:
        normalized = validate_write_contract(contract)
    except WriteContractRejected as error:
        return _replay_failure(
            "invalid_write_contract", investigation_id=investigation_id,
            detail=str(error),
        )
    try:
        route_case, route_template, route_question = parse_route_id(normalized["routeId"])
    except WriteContractRejected as error:
        return _replay_failure(
            "route_mismatch", investigation_id=investigation_id, detail=str(error)
        )
    if (
        route_case != case_id
        or route_template != investigation["template"]
        or route_question != int(investigation["question_id"])
    ):
        return _replay_failure(
            "route_mismatch", investigation_id=investigation_id,
            detail=f"Contract route {normalized['routeId']} does not match "
            f"investigation {investigation['template']} "
            f"question {investigation['question_id']}.",
        )
    if normalized["modelId"] != investigation["model"]:
        return _replay_failure(
            "contract_mismatch", investigation_id=investigation_id,
            detail=f"Contract model {normalized['modelId']} does not match "
            f"investigation model {investigation['model']}.",
        )
    valid_sources: set[int] = set()
    valid_assessments: set[int] = set()
    for entry in normalized["inputs"]:
        if "sourceVersionId" in entry:
            source_id = entry["sourceVersionId"]
            row = store.db.execute(
                "SELECT sha256, state FROM source_versions WHERE id=?", (source_id,)
            ).fetchone()
            if row is None:
                return _replay_failure(
                    "missing_input", investigation_id=investigation_id,
                    detail=f"Source version {source_id} no longer exists.",
                )
            if str(row[0]) != entry["contentHash"]:
                return _replay_failure(
                    "inputs_changed", investigation_id=investigation_id,
                    detail=f"Source version {source_id} content hash changed.",
                )
            if str(row[1]) != "current":
                return _replay_failure(
                    "stale_snapshot", investigation_id=investigation_id,
                    detail=f"Source version {source_id} is {row[1]}; "
                    "the snapshot it was read from is stale.",
                )
            valid_sources.add(source_id)
        elif "assertionId" in entry:
            assertion_id = entry["assertionId"]
            row = store.db.execute(
                """SELECT source_version_id, finding_key, certainty, quote, source_line
                FROM assertions WHERE id=? AND case_id=?""",
                (assertion_id, case_id),
            ).fetchone()
            if row is None:
                return _replay_failure(
                    "missing_input", investigation_id=investigation_id,
                    detail=f"Assertion {assertion_id} no longer exists.",
                )
            actual = content_hash({
                "source_version_id": int(row[0]),
                "finding_key": row[1],
                "certainty": row[2],
                "quote": row[3],
                "source_line": row[4],
            })
            if actual != entry["contentHash"]:
                return _replay_failure(
                    "inputs_changed", investigation_id=investigation_id,
                    detail=f"Assertion {assertion_id} content hash changed.",
                )
        else:
            assessment_id = entry["evidenceSnapshotId"]
            row = store.db.execute(
                """SELECT a.relation, a.applicability, a.rationale, v.statement, v.state
                FROM evidence_assessments a
                JOIN evidence_versions v ON v.id=a.evidence_version_id
                WHERE a.id=? AND a.case_id=?""",
                (assessment_id, case_id),
            ).fetchone()
            if row is None:
                return _replay_failure(
                    "missing_input", investigation_id=investigation_id,
                    detail=f"Evidence assessment {assessment_id} no longer exists.",
                )
            actual = content_hash({
                "relation": row[0],
                "applicability": row[1],
                "rationale": row[2],
                "statement": row[3],
            })
            if actual != entry["contentHash"]:
                return _replay_failure(
                    "inputs_changed", investigation_id=investigation_id,
                    detail=f"Evidence assessment {assessment_id} content hash changed.",
                )
            if str(row[4]) != "current":
                return _replay_failure(
                    "stale_snapshot", investigation_id=investigation_id,
                    detail=f"Evidence version for assessment {assessment_id} "
                    f"is {row[4]}; the snapshot it was read from is stale.",
                )
            valid_assessments.add(assessment_id)
    revalidated = validate_output(
        {"claims": investigation["claims"], "abstentions": investigation["abstentions"]},
        valid_sources,
        valid_assessments,
    )
    if (
        revalidated.claims != investigation["claims"]
        or revalidated.abstentions != investigation["abstentions"]
        or revalidated.status != investigation["status"]
    ):
        return _replay_failure(
            "claims_not_reproducible", investigation_id=investigation_id,
            detail="Re-validating the stored claims against the recorded "
            "inputs does not reproduce the stored run.",
        )
    return {
        "reproducible": True,
        "reason": None,
        "investigation_id": investigation_id,
        "writeId": normalized["writeId"],
        "runId": normalized["runId"],
        "routeId": normalized["routeId"],
        "snapshotAt": normalized["snapshotAt"],
        "checked_inputs": len(normalized["inputs"]),
        "toolCalls": len(normalized["toolCalls"]),
        "claims": len(investigation["claims"]),
    }
