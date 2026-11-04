"""Deterministic mock external specialist-model adapter (issue #15, branch only).

Fictional oncology demonstration harness. No real patients, no clinical use.

What this is: a pure, stdlib-only harness that proves the shapes of the
issue-#15 contracts — ModelRunReceipt, DerivedTimelineCandidate, and the
ModelCapabilityRegistry run gate — without any model, network, database, or
third-party dependency. It has:

- No Nano dependency, no live AlphaGenome integration, no model calls at all.
- No network use: this module imports no networking library and performs no
  I/O. There is no egress path, so no PHI (or any payload) can egress.
- No database access: the caller supplies source/version *references* plus
  field-scoped finding keys, states, and line anchors it already holds. The
  adapter never fetches source bytes and never writes to any ledger. No
  quote, byte, or patient-like field exists in the request schema, so source
  text cannot pass through this module even by accident.
- No clinical recommendations: task types are a closed set limited to
  chronology bookkeeping, and a vocabulary guard rejects clinical-inference
  language in request text and bars it from every output.

Fail-closed behavior: unknown capability state, unknown or denied permission,
revoked/superseded rights, capability task/modality/mode mismatch, unknown
license/retention/training terms, data-class mismatch, or a non-local
execution target never produce silent output: policy failures return a
`blocked` envelope with an inspectable denial receipt. Missing required
context, conflicting inputs, and non-full-date occurred values produce
abstentions, never guesses. Malformed requests (unknown task type, bad
identifiers, prohibited language, superseded anchors) raise `AdapterError`
instead of running.

Execution boundary: the mock *executes* local providers in `local_only` mode
only. A cleared non-local capability record passes the registry gate but the
mock still refuses to execute it (blocked envelope, gate `execution`), and
`authorized_remote` is refused even when listed — the harness has no remote
machinery, so claiming a remote run would be a hollow receipt. Non-local
execution needs a separately qualified path. Passing the registry gate
(`check_capability`) is therefore necessary but not sufficient for the mock
to execute.

Run identity: `run_id` fingerprints the effective execution request
(capability id, provider, case scope, task, modality, mode, input refs,
preprocessing and task-interface versions). Purpose text and rights-evaluation
context are excluded, so rewording a purpose or re-evaluating rights does not
fork run identity; a denial receipt shares its request's `run_id` and is
distinguished by `policy_decision`, `denial_reason`, and `egress_mode`. Do not
key receipt rows by `run_id` alone.

Cross-case isolation is the caller's responsibility: inputs carry no case
field, so the adapter cannot verify they belong to `case_scope`. The caller
must scope inputs before calling; the evaluation's cross-case probe covers
this seam.

Caller-supplied input shape (references plus ledger facets the caller
already holds; no source bytes, quotes, or patient-like fields anywhere):

- `source_version_id` (positive int), `document_id`, `version` (positive
  int), `sha256`, `event_date`, `issued_at` (both full `YYYY-MM-DD`;
  a non-full `event_date` abstains per G-4, a non-full `issued_at` is a
  caller error), `received_at` (ledger timestamp), `state` (must be
  exactly `"current"`: superseded anchors fail creation),
- optional `specimen_id`, `episode_id`, `lesion_id`, `assay_ref`
  (nonempty strings when present),
- `findings`: nonempty list of `finding_key` / `certainty` (ledger
  vocabulary) / `source_line` (positive int).

Every caller-supplied string that can reach an output (`case_scope`,
`modality`, `preprocessing_version`, `document_id`, `specimen_id`,
`episode_id`, `lesion_id`, `assay_ref`, `sha256`, `event_date`,
`issued_at`, `received_at`, `finding_key`, `capability_id`,
`model_provider`, `required_context` keys, `purpose`) is scanned for
clinical-inference vocabulary at request validation; a match fails
the request. Built candidates are re-scanned as a whole before return
(defense in depth).

Permission semantics here are identical to `open_intelligence.rights`:
usable only when explicitly recorded as "allowed" for that item AND that use
on a non-revoked, non-superseded record. The check is implemented inline so
this module stays dependency-free and importable without the application
package; a live path would call `rights.permitted` at the same seam.

Specs: docs/research/ISSUE15_MODEL_RUN_RECEIPT.md,
docs/research/ISSUE15_DERIVED_TIMELINE_CANDIDATE.md,
docs/research/ISSUE15_MODEL_CAPABILITY_REGISTRY.md.
"""

from __future__ import annotations

import hashlib
import json
import re
from datetime import date

TASK_TYPES = frozenset({
    "chronology_extraction",
    "contradiction_detection",
    "missingness_detection",
    "context_preparation",
})

# The mock's structural data class: it performs no I/O, embeds no payload,
# and only ever handles fictional synthetic references, so the class is
# asserted by the harness itself, not claimed by the caller. Evaluated
# against the capability record's allowed/forbidden data classes (gate 8).
DATA_CLASS = "fictional-synthetic"

TASK_INTERFACE_VERSION = "issue15-task/1"
PREPROCESSING_VERSION = "mock-preprocess/1"
MODEL_REF = "mock-specialist/1"
LOCAL_PROVIDERS = frozenset({"local-mock", "local-deterministic"})

# Mirrors the ledger identifier shape (store.ID); the adapter stays
# dependency-free, so the pattern is restated, not imported.
CASE_ID = re.compile(r"[A-Z][A-Z0-9-]{1,39}\Z")

# Finding certainty values must match the ledger vocabulary exactly
# (store.STATES); the adapter copies them verbatim, never reinterprets.
CERTAINTIES = frozenset({
    "reported", "negative", "pending", "indeterminate",
    "not-reported", "not-assessed", "conflicting",
})

DISCLAIMER = (
    "Fictional synthetic demonstration data only. This mock run produced "
    "unreviewed proposals, not findings or clinical determinations. "
    "No model was called; no data left this function call."
)

# Clinical-inference vocabulary barred from request text and every output.
# Mirrors the timeline.py refusals and the investigation.py language guard.
GUARD_PATTERNS = [
    re.compile(r"\brespons\w*\b", re.IGNORECASE),
    re.compile(r"\bprogress\w*\b", re.IGNORECASE),
    re.compile(r"\bstag\w+\b", re.IGNORECASE),
    re.compile(r"\bgrad\w+\b", re.IGNORECASE),
    re.compile(r"\beligib\w*\b", re.IGNORECASE),
    re.compile(r"\befficac\w*\b", re.IGNORECASE),
    re.compile(r"\btreatment\b", re.IGNORECASE),
    re.compile(r"\btherap\w*\b", re.IGNORECASE),
    re.compile(r"\bprescri\w*\b", re.IGNORECASE),
    re.compile(r"\brecommend\w*\b", re.IGNORECASE),
    re.compile(r"\bdos(e|age)\b", re.IGNORECASE),
    re.compile(r"\bdiagnos\w*\b", re.IGNORECASE),
    re.compile(r"\bbenefit\b", re.IGNORECASE),
    re.compile(r"\bsignifican\w*\b", re.IGNORECASE),
]

REQUIRED_TERM_FIELDS = (
    "retention_terms",
    "training_use_terms",
    "dependency_licenses",
    "per_use_rights",
)


class AdapterError(ValueError):
    """A mock-adapter request is malformed or carries prohibited content."""


def contains_clinical_language(text: object) -> bool:
    """True when text carries barred clinical-inference vocabulary."""
    if not isinstance(text, str):
        return False
    return any(pattern.search(text) for pattern in GUARD_PATTERNS)


def _canonical(value: object) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"))


def _fingerprint(value: object) -> str:
    return "sha256:" + hashlib.sha256(_canonical(value).encode("utf-8")).hexdigest()


def _is_full_date(value: object) -> bool:
    """Strict YYYY-MM-DD check, mirroring the ledger's valid_date rule."""
    if not isinstance(value, str):
        return False
    try:
        return date.fromisoformat(value).isoformat() == value
    except ValueError:
        return False


def _is_allowed(permissions: object, item: str, use: str,
               *, revoked: bool = False, superseded: bool = False) -> bool:
    """Fail-closed permission check; identical semantics to rights.permitted."""
    if revoked or superseded:
        return False
    if not isinstance(permissions, dict):
        return False
    uses = permissions.get(item)
    if not isinstance(uses, dict):
        return False
    return uses.get(use) == "allowed"


def _require_shape(request: object) -> dict:
    """Validate the request envelope; raise AdapterError on any defect."""
    if not isinstance(request, dict):
        raise AdapterError("Request must be an object")
    for key in ("task_type", "modality", "purpose", "capability", "inputs", "case_scope"):
        if key not in request:
            raise AdapterError(f"Request is missing {key!r}")
    if not isinstance(request["case_scope"], str) or not CASE_ID.fullmatch(request["case_scope"]):
        raise AdapterError("case_scope must be a valid fictional case identifier")
    if contains_clinical_language(request["case_scope"]):
        raise AdapterError("case_scope carries prohibited clinical-inference language")
    if "investigation_id" in request and (
            type(request["investigation_id"]) is not int or request["investigation_id"] < 1):
        raise AdapterError("investigation_id must be a positive integer")
    if not isinstance(request["task_type"], str) or request["task_type"] not in TASK_TYPES:
        raise AdapterError(f"Unknown task type: {request['task_type']!r}")
    if not isinstance(request["modality"], str) or not request["modality"].strip():
        raise AdapterError("Modality must be a nonempty string")
    if contains_clinical_language(request["modality"]):
        raise AdapterError("Modality carries prohibited clinical-inference language")
    purpose = request["purpose"]
    if not isinstance(purpose, str) or not 5 <= len(purpose.strip()) <= 500:
        raise AdapterError("Purpose must have 5-500 characters")
    if contains_clinical_language(purpose):
        raise AdapterError("Purpose carries prohibited clinical-inference language")
    if not isinstance(request["capability"], dict):
        raise AdapterError("Capability must be an object")
    for key in ("capability_id", "model_provider"):
        if contains_clinical_language(request["capability"].get(key)):
            raise AdapterError(f"Capability {key} carries prohibited clinical-inference language")
    required_names = request["capability"].get("required_context")
    if isinstance(required_names, list):
        for key in required_names:
            if contains_clinical_language(key):
                raise AdapterError(
                    "Capability required_context carries prohibited clinical-inference language")
    if not isinstance(request["inputs"], list) or not request["inputs"]:
        raise AdapterError("Inputs must be a nonempty list")
    for position, item in enumerate(request["inputs"]):
        _require_input(item, position)
    mode = request.get("execution_mode", "local_only")
    if mode not in ("local_only", "authorized_remote"):
        raise AdapterError(f"Unknown execution mode: {mode!r}")
    preprocessing = request.get("preprocessing_version", PREPROCESSING_VERSION)
    if not isinstance(preprocessing, str) or not preprocessing.strip():
        raise AdapterError("preprocessing_version must be a nonempty string")
    if contains_clinical_language(preprocessing):
        raise AdapterError("preprocessing_version carries prohibited clinical-inference language")
    return request  # type: ignore[return-value]


def _require_input(item: object, position: int) -> None:
    if not isinstance(item, dict):
        raise AdapterError(f"Input {position} must be an object")
    for key in ("source_version_id", "document_id", "version", "sha256",
                "event_date", "issued_at", "received_at", "state", "findings"):
        if key not in item:
            raise AdapterError(f"Input {position} is missing {key!r}")
    if item["state"] != "current":
        raise AdapterError(
            f"Input {position} is not a current source version "
            "(superseded anchors fail creation)")
    if type(item["source_version_id"]) is not int or item["source_version_id"] < 1:
        raise AdapterError(f"Input {position} has an invalid source_version_id")
    if type(item["version"]) is not int or item["version"] < 1:
        raise AdapterError(f"Input {position} has an invalid version")
    for key in ("document_id", "sha256", "event_date", "issued_at", "received_at"):
        if not isinstance(item[key], str) or not item[key].strip():
            raise AdapterError(f"Input {position} has an invalid {key}")
    if not _is_full_date(item["issued_at"]):
        raise AdapterError(f"Input {position} has a non-full-date issued_at (caller error)")
    # event_date shape is checked in the run loop, not here: a non-full
    # occurred value abstains (G-4) rather than failing the request.
    for key in ("specimen_id", "episode_id", "lesion_id", "assay_ref"):
        value = item.get(key)
        if value is not None and (not isinstance(value, str) or not value.strip()):
            raise AdapterError(f"Input {position} has an invalid {key}")
    for key in ("document_id", "specimen_id", "episode_id", "lesion_id", "assay_ref",
                "sha256", "event_date", "issued_at", "received_at"):
        if contains_clinical_language(item.get(key)):
            raise AdapterError(
                f"Input {position} field {key} carries prohibited clinical-inference language")
    if not isinstance(item["findings"], list) or not item["findings"]:
        raise AdapterError(f"Input {position} must carry a nonempty findings list")
    for number, finding in enumerate(item["findings"]):
        if not isinstance(finding, dict):
            raise AdapterError(f"Input {position} finding {number} must be an object")
        for key in ("finding_key", "certainty", "source_line"):
            if key not in finding:
                raise AdapterError(f"Input {position} finding {number} is missing {key!r}")
        if not isinstance(finding["finding_key"], str) or not finding["finding_key"].strip():
            raise AdapterError(f"Input {position} finding {number} has an invalid finding_key")
        if contains_clinical_language(finding["finding_key"]):
            raise AdapterError(
                f"Input {position} finding {number} carries prohibited clinical-inference language")
        if not isinstance(finding["certainty"], str) or finding["certainty"] not in CERTAINTIES:
            raise AdapterError(f"Input {position} finding {number} has an invalid certainty")
        if type(finding["source_line"]) is not int or finding["source_line"] < 1:
            raise AdapterError(f"Input {position} finding {number} has an invalid source_line")


def check_capability(capability: dict, *, task_type: str, modality: str,
                     execution_mode: str) -> dict:
    """Evaluate the registry run gate. Returns a decision dict, never raises."""
    if not isinstance(capability, dict):
        return {"outcome": "denied", "record": "unidentified-record",
                "reason": "capability record is malformed (fail closed)"}
    record = capability.get("capability_id", "unidentified-record")
    denied = lambda reason: {"outcome": "denied", "record": record, "reason": reason}
    if capability.get("record_state") != "cleared":
        return denied("capability record is not cleared")
    provider = capability.get("model_provider")
    if not isinstance(provider, str) or not provider.strip():
        return denied("capability record has no model_provider")
    if provider not in LOCAL_PROVIDERS:
        approval = capability.get("provider_approval_ref")
        if not isinstance(approval, str) or not approval.strip():
            return denied("non-local provider lacks a recorded provider approval")
    for schema_key in ("input_schema", "output_schema"):
        schema_id = capability.get(schema_key)
        if not isinstance(schema_id, str) or not schema_id.strip():
            return denied(f"capability record has no {schema_key}")
    if capability.get("task_type") != task_type:
        return denied("capability task type does not match the run")
    if capability.get("modality") != modality:
        return denied("capability modality does not match the run")
    modes = capability.get("execution_modes")
    if not isinstance(modes, list) or execution_mode not in modes:
        return denied("execution mode is not listed on the capability record")
    required_context = capability.get("required_context", [])
    if not isinstance(required_context, list) or any(
            not isinstance(key, str) for key in required_context):
        return denied("capability record has a malformed required_context")
    for field in REQUIRED_TERM_FIELDS:
        value = capability.get(field)
        if not isinstance(value, str) or not value.strip() or value.strip().lower() == "unknown":
            return denied(f"capability term {field} is unknown")
    allowed_classes = capability.get("allowed_data_classes")
    forbidden_classes = capability.get("forbidden_data_classes")
    if not isinstance(allowed_classes, list) or DATA_CLASS not in allowed_classes:
        return denied(f"capability record does not allow the {DATA_CLASS} data class")
    if not isinstance(forbidden_classes, list) or DATA_CLASS in forbidden_classes:
        return denied(f"capability record forbids the {DATA_CLASS} data class")
    return {"outcome": "allowed", "record": record,
            "reason": "capability record cleared for this task, modality, mode, and data class"}


def check_rights(request: dict) -> dict:
    """Evaluate model-input rights. Returns a decision dict, never raises."""
    permissions = request.get("permissions", {})
    flags = request.get("rights_flags", {})
    if not isinstance(flags, dict):
        return {"outcome": "denied", "reason": "rights flags are malformed (fail closed)"}
    revoked = flags.get("revoked", False) is True
    superseded = flags.get("superseded", False) is True
    if revoked or superseded:
        return {"outcome": "denied", "reason": "rights record is revoked or superseded"}
    if not _is_allowed(permissions, "full_text", "ml_use",
                       revoked=revoked, superseded=superseded):
        return {"outcome": "denied",
                "reason": "full_text/ml_use is not explicitly allowed (unknown or denied fails closed)"}
    return {"outcome": "allowed", "reason": "full_text/ml_use explicitly allowed on an active record"}


def _conflicted_specimens(inputs: list[dict]) -> dict[str, list[str]]:
    """Specimens asserting different occurred dates across inputs.

    Non-full dates are excluded: a partial-date input abstains on its own
    (G-4) and must not poison a sibling input that carries a real date.
    """
    by_specimen: dict[str, set[str]] = {}
    for item in inputs:
        specimen = item.get("specimen_id")
        if specimen is not None and _is_full_date(item["event_date"]):
            by_specimen.setdefault(specimen, set()).add(item["event_date"])
    return {specimen: sorted(dates)
            for specimen, dates in by_specimen.items() if len(dates) > 1}


def run_mock_specialist(request: dict) -> dict:
    """Run the deterministic mock. Pure: no I/O, no network, no database.

    Returns an envelope with status completed | abstained | blocked_by_policy,
    a receipt in the ModelRunReceipt shape, extracted_candidate-level
    candidates only, and abstentions. Malformed requests raise AdapterError.
    """
    checked = _require_shape(request)
    task_type = checked["task_type"]
    mode = checked.get("execution_mode", "local_only")
    capability = checked["capability"]
    inputs = checked["inputs"]
    preprocessing = checked.get("preprocessing_version", PREPROCESSING_VERSION)

    input_refs = [{
        "source_version_id": item["source_version_id"],
        "document_id": item["document_id"],
        "version": item["version"],
        "sha256": item["sha256"],
        "finding_scope": sorted(f["finding_key"] for f in item["findings"]),
    } for item in inputs]
    run_id = _fingerprint({
        "capability_id": capability.get("capability_id"),
        "model_provider": capability.get("model_provider"),
        "case_scope": checked["case_scope"],
        "task_type": task_type,
        "modality": checked["modality"],
        "execution_mode": mode,
        "inputs": input_refs,
        "preprocessing_version": preprocessing,
        "task_interface_version": TASK_INTERFACE_VERSION,
    })
    input_fingerprint = _fingerprint(
        {"inputs": input_refs, "preprocessing_version": preprocessing})

    def denial_receipt(reason: str, decision: dict) -> dict:
        return {
            "run_id": run_id,
            "case_scope": checked["case_scope"],
            "investigation_id": checked.get("investigation_id"),
            "task_type": task_type,
            "modality": checked["modality"],
            "purpose": checked["purpose"],
            "task_interface_version": TASK_INTERFACE_VERSION,
            "model_provider": capability.get("model_provider", "unidentified-provider"),
            "model_ref": MODEL_REF,
            "capability_ref": capability.get("capability_id", "unidentified-record"),
            "runtime_location": mode,
            "deterministic_config": {"reproducible": True, "seed": "n/a-deterministic-rules"},
            "input_refs": input_refs,
            "input_fingerprint": input_fingerprint,
            "preprocessing_version": preprocessing,
            "egress_mode": "blocked",
            "policy_decision": decision,
            "token_compute_cost": None,
            "output_hash": _fingerprint({"candidates": [], "abstentions": []}),
            "parse_result": "not_applicable",
            "errors": [],
            "abstentions": [],
            "validity": "current",
            "review_state": "pending",
            "derived_artifacts": [],
            "synthetic": True,
            "disclaimer": DISCLAIMER,
            "denial_reason": reason,
        }

    capability_decision = check_capability(
        capability, task_type=task_type,
        modality=checked["modality"], execution_mode=mode)
    if capability_decision["outcome"] != "allowed":
        return {"status": "blocked_by_policy",
                "receipt": denial_receipt(capability_decision["reason"], {
                    "outcome": "denied", "gate": "capability",
                    **capability_decision}),
                "candidates": [], "abstentions": [],
                "synthetic": True, "disclaimer": DISCLAIMER}
    rights_decision = check_rights(checked)
    if rights_decision["outcome"] != "allowed":
        return {"status": "blocked_by_policy",
                "receipt": denial_receipt(rights_decision["reason"], {
                    "outcome": "denied", "gate": "rights", **rights_decision}),
                "candidates": [], "abstentions": [],
                "synthetic": True, "disclaimer": DISCLAIMER}

    provider = capability.get("model_provider")
    if provider not in LOCAL_PROVIDERS or mode != "local_only":
        if provider not in LOCAL_PROVIDERS:
            reason = ("mock harness executes local providers only; "
                      "non-local execution needs a separately qualified path")
        else:
            reason = ("mock harness executes local_only runs only; "
                      "authorized_remote execution needs a separately qualified path")
        return {"status": "blocked_by_policy",
                "receipt": denial_receipt(reason, {
                    "outcome": "denied", "gate": "execution", "reason": reason}),
                "candidates": [], "abstentions": [],
                "synthetic": True, "disclaimer": DISCLAIMER}

    required_context = capability.get("required_context") or []
    conflicted = _conflicted_specimens(inputs)
    candidates: list[dict] = []
    abstentions: list[dict] = []
    for item in inputs:
        missing = [key for key in required_context if item.get(key) is None]
        if missing:
            abstentions.append({
                "topic": f"document:{item['document_id']}@{item['version']}",
                "reason": "insufficient_evidence",
                "detail": f"missing required context: {', '.join(sorted(missing))}",
                "source_ref": {"source_version_id": item["source_version_id"],
                               "document_id": item["document_id"],
                               "version": item["version"]},
            })
            continue
        if not _is_full_date(item["event_date"]):
            abstentions.append({
                "topic": f"document:{item['document_id']}@{item['version']}",
                "reason": "insufficient_evidence",
                "detail": (f"non-full occurred date {item['event_date']!r} is "
                           "unrepresentable (G-4); abstaining rather than guessing"),
                "source_ref": {"source_version_id": item["source_version_id"],
                               "document_id": item["document_id"],
                               "version": item["version"]},
            })
            continue
        specimen = item.get("specimen_id")
        if specimen is not None and specimen in conflicted:
            abstentions.append({
                "topic": f"specimen:{specimen}",
                "reason": "conflicting_evidence",
                "detail": f"asserted occurred dates {conflicted[specimen]}; no winner selected",
                "source_ref": {"source_version_id": item["source_version_id"],
                               "document_id": item["document_id"],
                               "version": item["version"]},
            })
            continue
        for finding in item["findings"]:
            candidate_id = f"candidate:{run_id}:{len(candidates)}"
            candidates.append({
                "candidate_id": candidate_id,
                "run_id": run_id,
                "epistemic_level": "extracted_candidate",
                "source_ref": {
                    "source_version_id": item["source_version_id"],
                    "document_id": item["document_id"],
                    "version": item["version"],
                    "source_line": finding["source_line"],
                },
                "episode_context": {
                    "episode_id": item.get("episode_id") or "unknown",
                    "lesion_id": item.get("lesion_id") or "unknown",
                    "specimen_id": item.get("specimen_id") or "unknown",
                    "assay_ref": item.get("assay_ref") or "unknown",
                },
                "polarity": finding["certainty"],
                # The mock states minimal confidence in its own proposal.
                "certainty": "low",
                "occurred": item["event_date"],
                "documented": item["issued_at"],
                "received": item["received_at"],
                "units_reference": "unknown",
                "alternatives": [],
                "validity": "current",
                "review_state": "pending",
                "synthetic": True,
                "disclaimer": ("Fictional synthetic demonstration data only. "
                               "Unreviewed mock proposal, not a finding."),
            })
    # Closed-world invariant: every candidate cites only inputs from this
    # request. Verified here, not trusted from the construction above.
    # Every candidate is then re-scanned as a whole (canonical JSON), so no
    # caller-supplied string that reaches an output escapes the guard.
    allowed_refs = {(r["source_version_id"], r["document_id"], r["version"])
                    for r in input_refs}
    for candidate in candidates:
        ref = candidate["source_ref"]
        if (ref["source_version_id"], ref["document_id"], ref["version"]) not in allowed_refs:
            raise AdapterError("Candidate cites a source outside this run's inputs")
        if contains_clinical_language(_canonical(candidate)):
            raise AdapterError("Candidate carries prohibited clinical language")

    receipt = {
        "run_id": run_id,
        "case_scope": checked["case_scope"],
        "investigation_id": checked.get("investigation_id"),
        "task_type": task_type,
        "modality": checked["modality"],
        "purpose": checked["purpose"],
        "task_interface_version": TASK_INTERFACE_VERSION,
        "model_provider": capability.get("model_provider"),
        "model_ref": MODEL_REF,
        "capability_ref": capability.get("capability_id"),
        "runtime_location": mode,
        "deterministic_config": {"reproducible": True, "seed": "n/a-deterministic-rules"},
        "input_refs": input_refs,
        "input_fingerprint": input_fingerprint,
        "preprocessing_version": preprocessing,
        "egress_mode": "local_only",
        "policy_decision": {"outcome": "allowed", "gate": "capability+rights+execution",
                            "capability": capability_decision,
                            "rights": rights_decision},
        "token_compute_cost": None,
        "output_hash": _fingerprint({"candidates": candidates, "abstentions": abstentions}),
        "parse_result": "parsed",
        "errors": [],
        "abstentions": abstentions,
        "validity": "current",
        "review_state": "pending",
        "derived_artifacts": [c["candidate_id"] for c in candidates],
        "synthetic": True,
        "disclaimer": DISCLAIMER,
        "denial_reason": None,
    }
    status = "completed" if candidates else "abstained"
    return {"status": status, "receipt": receipt, "candidates": candidates,
            "abstentions": abstentions,
            "synthetic": True, "disclaimer": DISCLAIMER}
