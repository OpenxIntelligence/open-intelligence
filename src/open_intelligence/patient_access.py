"""Patient-directed access adapter contract (complementary research, OI issue #17).

This module is a deterministic, synthetic-only gate in front of the EXISTING
``CaseStore`` source ledger. It creates NO second source ledger, NO canonical
state, NO authorization system, and NO live EHR integration:

* Source bytes live only in ``source_versions`` (or, on rejection, in the
  existing ``quarantine`` table). This module never stores a normalized
  projection as a source.
* Authorization receipts, loss receipts, bindings checks and revocation are
  recorded only as rows in the existing ``events`` ledger (via
  ``CaseStore.record_adapter_event``) plus, for quarantined deliveries, the
  existing ``quarantine`` table.
* No vendor is selected. ``purpose`` must be ``individual-access`` for this
  patient-directed adapter; a Treatment-purpose receipt is rejected here
  because it belongs to a different pathway with different eligibility and
  obligations (see the OI-017 research document). That rejection is a
  contract boundary, not a judgement about any vendor's Treatment access.

All inputs are independently authored synthetic fixtures. No real patient
data, no live network call, no clinical claim is involved.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass, field

from .store import CaseStore, InvalidInput, parse_report, valid_date

ADAPTER_EVENT_KINDS = frozenset({
    "adapter_delivery_accepted",
    "adapter_delivery_rejected",
    "adapter_delivery_quarantined",
    "adapter_loss_receipt",
    "adapter_authorization_revoked",
})
COVERAGE_STATUSES = frozenset({"present", "negative", "known_missing", "unknown"})


@dataclass(frozen=True)
class AuthorizationReceipt:
    """A synthetic authorization receipt presented by an adapter delivery.

    Dates are YYYY-MM-DD. ``revoked_at`` is None while the receipt is live.
    A receipt is not proof of real-world access rights; it is the envelope
    field the adapter contract requires before any bytes reach the ledger.
    """

    receipt_id: str
    purpose: str  # only "individual-access" is accepted by this adapter
    scope: tuple[str, ...]
    granted_at: str
    expires_at: str
    revoked_at: str | None = None

    def validate(self) -> None:
        if not isinstance(self.receipt_id, str) or not self.receipt_id.strip():
            raise InvalidInput("Authorization receipt id is required")
        if self.purpose != "individual-access":
            raise InvalidInput(
                "Patient-directed adapter accepts only individual-access purpose; "
                "Treatment-purpose receipts belong to a different pathway")
        if not self.scope:
            raise InvalidInput("Authorization receipt scope must be nonempty")
        valid_date(self.granted_at)
        valid_date(self.expires_at)
        if self.revoked_at is not None:
            valid_date(self.revoked_at)
        if self.expires_at < self.granted_at:
            raise InvalidInput("Authorization expiry precedes grant")


@dataclass(frozen=True)
class TransformationReceipt:
    """Field-level record of what a lossy transform dropped or changed.

    ``dropped_fields`` must name every source field absent from the
    normalized output. An empty receipt for a lossy transform is invalid:
    loss must be declared, never silent. The receipt does NOT authorise
    replacing the original bytes; the adapter always imports the original.
    """

    dropped_fields: tuple[str, ...] = ()
    truncated_fields: tuple[str, ...] = ()
    cardinality_changes: tuple[str, ...] = ()
    notes: str = ""

    @property
    def is_lossy(self) -> bool:
        return bool(self.dropped_fields or self.truncated_fields or self.cardinality_changes)


def assess_transformation(original_fields: set[str], transformed_fields: set[str],
                          truncated: tuple[str, ...] = (),
                          cardinality_changes: tuple[str, ...] = ()) -> TransformationReceipt:
    """Compute a loss receipt from two field sets (pure, deterministic)."""
    if not isinstance(original_fields, set) or not isinstance(transformed_fields, set):
        raise InvalidInput("Transformation field sets must be sets")
    dropped = tuple(sorted(original_fields - transformed_fields))
    return TransformationReceipt(dropped_fields=dropped, truncated_fields=tuple(truncated),
                                 cardinality_changes=tuple(cardinality_changes))


@dataclass
class AdapterEnvelope:
    """Everything an adapter delivery must declare, besides the raw bytes."""

    adapter_id: str
    source_organization: str
    source_system: str
    case_id: str
    source_subject_ref: str
    authorization: AuthorizationReceipt
    retrieved_at: str
    transformation: TransformationReceipt | None = None
    # Field sets for the loss check; None means "verbatim, no transform claimed".
    original_fields: set[str] | None = None
    transformed_fields: set[str] | None = None

    def validate_time_semantics(self, event_date: str, issued_at: str) -> None:
        """event_date <= issued_at <= retrieved_at, inside the auth window."""
        valid_date(event_date)
        valid_date(issued_at)
        valid_date(self.retrieved_at)
        if not (event_date <= issued_at <= self.retrieved_at):
            raise InvalidInput(
                "Time semantics violated: expected event_date <= issued_at <= retrieved_at")
        auth = self.authorization
        if not (auth.granted_at <= self.retrieved_at <= auth.expires_at):
            raise InvalidInput("Retrieval outside the authorization window")
        if auth.revoked_at is not None and self.retrieved_at >= auth.revoked_at:
            raise InvalidInput("Authorization receipt is revoked")


def classify_coverage(manifest: list[dict]) -> dict:
    """Classify an artifact inventory without conflating missing and negative.

    Statuses:
    * ``present`` -- an artifact was delivered for this class.
    * ``negative`` -- a delivered source explicitly reports the finding as
      negative / not present. Requires ``source_document``: a negative is
      evidence, not an absence.
    * ``known_missing`` -- the class is known not to be exposed by the source
      (e.g. report-only imaging without DICOM pixels, payer events without
      administration confirmation). Requires ``reason``.
    * ``unknown`` -- availability is not established either way.

    Returns counts plus the per-artifact classification. Raises InvalidInput
    on an unknown status or a missing required field, so a manifest cannot
    silently relabel a gap as a negative.
    """
    if not isinstance(manifest, list) or not manifest:
        raise InvalidInput("Coverage manifest must be a nonempty list")
    classified: list[dict] = []
    counts = {status: 0 for status in sorted(COVERAGE_STATUSES)}
    for entry in manifest:
        if not isinstance(entry, dict):
            raise InvalidInput("Coverage manifest entries must be objects")
        artifact = entry.get("artifact")
        status = entry.get("status")
        if not isinstance(artifact, str) or not artifact.strip():
            raise InvalidInput("Coverage manifest entry requires an artifact name")
        if status not in COVERAGE_STATUSES:
            raise InvalidInput(f"Unknown coverage status for {artifact}")
        if status == "negative" and not entry.get("source_document"):
            raise InvalidInput(f"Negative classification for {artifact} requires a source_document")
        if status == "known_missing" and not entry.get("reason"):
            raise InvalidInput(f"Known-missing classification for {artifact} requires a reason")
        counts[status] += 1
        classified.append({"artifact": artifact, "status": status})
    return {"counts": counts, "artifacts": classified}


class PatientAccessAdapter:
    """Stateful (in-memory) binding/revocation gate over an existing CaseStore.

    Bindings and revocations live only for the life of this adapter object in
    tests and in the recorded event ledger; they are not a second source
    ledger. A production deployment would need a separately authorized,
    durable authorization store -- this module deliberately does not build
    one (see the OI-017 document, "what is NOT proved").
    """

    def __init__(self, store: CaseStore):
        self.store = store
        # (source_organization) -> source_subject_ref, first binding wins.
        self._org_bindings: dict[str, str] = {}
        # source_subject_ref -> case_id, first binding wins.
        self._subject_cases: dict[str, str] = {}
        self._revoked_receipts: set[str] = set()

    def revoke(self, case_id: str, receipt_id: str, reason: str) -> dict:
        """Record a revocation in the existing event ledger.

        Revocation blocks future deliveries. It does NOT delete history:
        already-imported source versions remain recoverable, exactly as an
        amendment supersedes rather than erases.
        """
        if not isinstance(reason, str) or not 10 <= len(reason.strip()) <= 600:
            raise InvalidInput("Revocation requires a 10–600 character reason")
        self._revoked_receipts.add(receipt_id)
        self.store.record_adapter_event(
            case_id, "adapter_authorization_revoked",
            receipt_id=receipt_id, reason=reason.strip())
        return {"result": "revoked", "receipt_id": receipt_id}

    def deliver(self, envelope: AdapterEnvelope, raw: bytes) -> dict:
        """Validate an adapter delivery and, only if valid, import it.

        Returns the underlying ``import_report`` result on success, or a
        ``{"result": "rejected", "reason": ...}`` dict (with an event and, for
        identity collisions, a quarantine row) on contract rejection. Bytes
        that fail contract checks are never imported as sources.
        """
        auth = envelope.authorization
        auth.validate()
        if envelope.adapter_id.strip() == "" or envelope.source_organization.strip() == "":
            raise InvalidInput("Adapter id and source organization are required")
        if not envelope.source_subject_ref.strip():
            raise InvalidInput("Source subject reference is required")
        if auth.receipt_id in self._revoked_receipts:
            self.store.record_adapter_event(
                envelope.case_id, "adapter_delivery_rejected",
                reason="revoked_authorization", receipt_id=auth.receipt_id)
            return {"result": "rejected", "reason": "revoked_authorization"}
        # Parse first so time semantics are checked against the real report.
        report = parse_report(raw)
        envelope.validate_time_semantics(report.event_date, report.issued_at)
        # Loss contract: a claimed transform must carry its receipt, and a
        # lossy receipt never substitutes normalized bytes for the original.
        if envelope.transformed_fields is not None or envelope.original_fields is not None:
            if envelope.original_fields is None or envelope.transformed_fields is None:
                raise InvalidInput("Transform claim requires both field sets")
            computed = assess_transformation(envelope.original_fields, envelope.transformed_fields)
            declared = envelope.transformation
            if computed.is_lossy and declared is None:
                self.store.record_adapter_event(
                    envelope.case_id, "adapter_delivery_rejected",
                    reason="transformation_loss_undocumented",
                    document_id=report.document_id)
                return {"result": "rejected", "reason": "transformation_loss_undocumented"}
            if declared is not None and set(declared.dropped_fields) != set(computed.dropped_fields):
                raise InvalidInput("Declared loss receipt does not match computed dropped fields")
        # Identity binding: first binding wins per organization and per
        # subject reference. A conflict is quarantined/rejected, never merged.
        org_bound = self._org_bindings.get(envelope.source_organization)
        subject_case = self._subject_cases.get(envelope.source_subject_ref)
        if (org_bound is not None and org_bound != envelope.source_subject_ref) or \
                (subject_case is not None and subject_case != envelope.case_id):
            digest = hashlib.sha256(raw).hexdigest()
            outcome = self.store.quarantine_adapter_delivery(
                envelope.case_id, raw, report.patient_id, "identity_collision")
            self.store.record_adapter_event(
                envelope.case_id, "adapter_delivery_quarantined",
                reason="identity_collision", quarantine_id=outcome["quarantine_id"],
                sha256=digest)
            return {"result": "rejected", "reason": "identity_collision",
                    "quarantine_id": outcome["quarantine_id"]}
        # Bind on first successful contract pass (before import, so a later
        # duplicate delivery from the same binding is not a collision).
        self._org_bindings.setdefault(envelope.source_organization, envelope.source_subject_ref)
        self._subject_cases.setdefault(envelope.source_subject_ref, envelope.case_id)
        outcome = self.store.import_report(envelope.case_id, raw)
        if outcome["result"] == "imported":
            self.store.record_adapter_event(
                envelope.case_id, "adapter_delivery_accepted",
                document_id=report.document_id, version=outcome["version"],
                source_id=outcome["source_id"], adapter_id=envelope.adapter_id,
                source_organization=envelope.source_organization,
                receipt_id=auth.receipt_id, retrieved_at=envelope.retrieved_at,
                sha256=hashlib.sha256(raw).hexdigest())
            if envelope.transformation is not None and envelope.transformation.is_lossy:
                # The original bytes were imported; the loss receipt rides
                # alongside as an event, never as a replacement source.
                self.store.record_adapter_event(
                    envelope.case_id, "adapter_loss_receipt",
                    document_id=report.document_id,
                    dropped_fields=list(envelope.transformation.dropped_fields),
                    truncated_fields=list(envelope.transformation.truncated_fields),
                    cardinality_changes=list(envelope.transformation.cardinality_changes))
        return outcome
