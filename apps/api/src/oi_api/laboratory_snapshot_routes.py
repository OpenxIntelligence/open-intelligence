"""Capture and reopen reference-only snapshots of authorized laboratory inspections."""
from typing import Literal

from fastapi import Depends, HTTPException, Request
from pydantic import Field, StrictBool, StrictInt, StrictStr

from open_intelligence.patient_registry import PatientRegistryDenied

from .access import Principal
from .contracts import Contract
from .evidence_routes import _prepare
from .laboratory_citation_report import REPORT_ACTIONS
from .laboratory_citation_report_routes import VersionedLaboratoryCitationInspection
from .laboratory_inspection_snapshots import CAPTURE, LaboratoryInspectionSnapshots


class CaptureInspection(Contract):
    synthetic: StrictBool
    request_key: StrictStr = Field(min_length=3, max_length=128)
    expected_report_sha256: StrictStr = Field(pattern=r"^[a-f0-9]{64}$")


class SnapshotReceipt(Contract):
    snapshot_id: StrictStr = Field(pattern=r"^LAB-SNAPSHOT-[A-F0-9]{32}$")
    captured_report_sha256: StrictStr = Field(pattern=r"^[a-f0-9]{64}$")
    duplicate: StrictBool


class SnapshotSummary(Contract):
    snapshot_id: StrictStr = Field(pattern=r"^LAB-SNAPSHOT-[A-F0-9]{32}$")
    captured_report_sha256: StrictStr = Field(pattern=r"^[a-f0-9]{64}$")
    captured_at: StrictStr
    citation_count: StrictInt = Field(ge=0, le=100)
    captured_source_context_state: Literal["current_unreviewed_question", "source_reassessment_required"]


class SnapshotHistory(Contract):
    patient_id: StrictStr
    case_id: StrictStr
    question_id: StrictStr
    source_access_receipt_id: StrictStr = Field(pattern=r"^ACCESS-[0-9A-F]{32}$")
    snapshots: list[SnapshotSummary] = Field(max_length=100)


class ReopenedInspection(Contract):
    snapshot: SnapshotSummary
    inspection: VersionedLaboratoryCitationInspection


def register_laboratory_snapshots(router, *, principal, registry, records_authorized, final_question_authority, errors):
    path = "/{patient_id}/cases/{case_id}/composer/laboratory-questions/{question_id}/source-citation-report/snapshots"

    def perform(patient_id, case_id, question_id, request, context, model, *, command=None, snapshot_id=None):
        if context.purpose != "operations" or request.query_params or (command is not None and not command.synthetic):
            raise HTTPException(404, "Laboratory snapshot unavailable")
        actions = (*REPORT_ACTIONS, CAPTURE) if command is not None else REPORT_ACTIONS
        try:
            with registry(context) as patients:
                for action in actions:
                    records_authorized(patients, context, patient_id, action)
                owner = LaboratoryInspectionSnapshots(patients)
                options = dict(
                    organization=context.organization, actor=context.actor, purpose=context.purpose,
                    recheck_authority=lambda: final_question_authority(request, context, patients, patient_id, actions),
                    prepare_response=lambda value: _prepare(model, value, command=command is not None))
                if command is not None:
                    return owner.capture(patient_id, case_id, question_id, **options, request_key=command.request_key,
                                         expected_report_sha256=command.expected_report_sha256)
                return owner.read(patient_id, case_id, question_id, **options, snapshot_id=snapshot_id)
        except PatientRegistryDenied:
            raise HTTPException(404, "Laboratory snapshot unavailable") from None

    @router.post(path, status_code=201, response_model=SnapshotReceipt, responses={200: {"model": SnapshotReceipt}, **errors},
                 operation_id="capture_laboratory_inspection_snapshot_v1")
    def capture(patient_id: str, case_id: str, question_id: str, request: Request, payload: CaptureInspection,
                context: Principal = Depends(principal)):
        return perform(patient_id, case_id, question_id, request, context, SnapshotReceipt, command=payload)

    @router.get(path, response_model=SnapshotHistory, responses=errors, operation_id="list_laboratory_inspection_snapshots_v1")
    def history(patient_id: str, case_id: str, question_id: str, request: Request, context: Principal = Depends(principal)):
        return perform(patient_id, case_id, question_id, request, context, SnapshotHistory)

    @router.get(path + "/{snapshot_id}", response_model=ReopenedInspection, responses=errors,
                operation_id="reopen_laboratory_inspection_snapshot_v1")
    def reopen(patient_id: str, case_id: str, question_id: str, snapshot_id: str, request: Request,
               context: Principal = Depends(principal)):
        return perform(patient_id, case_id, question_id, request, context, ReopenedInspection, snapshot_id=snapshot_id)
