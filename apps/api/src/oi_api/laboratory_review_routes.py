"""Human verification returns over an exactly reopened saved laboratory inspection."""
from typing import Literal

from fastapi import Depends, HTTPException, Request
from pydantic import Field, StrictBool, StrictInt, StrictStr

from open_intelligence.patient_registry import PatientRegistryDenied

from .access import Principal
from .contracts import Contract
from .evidence_routes import _prepare
from .laboratory_citation_report import REPORT_ACTIONS
from .question_review_returns import PostgresQuestionReviewReturns


class ReturnLaboratoryInspection(Contract):
    synthetic: StrictBool
    request_key: StrictStr = Field(min_length=3, max_length=128)
    expected_queue_fingerprint: StrictStr = Field(pattern=r"^[a-f0-9]{64}$")
    expected_captured_report_sha256: StrictStr = Field(pattern=r"^[a-f0-9]{64}$")
    expected_report_sha256: StrictStr = Field(pattern=r"^[a-f0-9]{64}$")
    reason: StrictStr = Field(min_length=10, max_length=600)


class LaboratoryReturnReceipt(Contract):
    receipt_id: StrictStr = Field(pattern=r"^REVIEW-[0-9A-F]{32}$")
    question_id: StrictStr = Field(pattern=r"^QUESTION-[0-9A-F]{32}$")
    snapshot_id: StrictStr = Field(pattern=r"^LAB-SNAPSHOT-[0-9A-F]{32}$")
    duplicate: StrictBool


class LaboratoryReturnHistory(Contract):
    receipt_id: StrictStr = Field(pattern=r"^REVIEW-[0-9A-F]{32}$")
    question_id: StrictStr = Field(pattern=r"^QUESTION-[0-9A-F]{32}$")
    snapshot_id: StrictStr = Field(pattern=r"^LAB-SNAPSHOT-[0-9A-F]{32}$")
    captured_report_sha256: StrictStr = Field(pattern=r"^[a-f0-9]{64}$")
    report_sha256: StrictStr = Field(pattern=r"^[a-f0-9]{64}$")
    source_context_state: Literal["current_unreviewed_question", "source_reassessment_required"]
    queue_fingerprint: StrictStr = Field(pattern=r"^[a-f0-9]{64}$")
    actor_label: StrictStr
    action: Literal["returned"]
    reason: StrictStr = Field(min_length=10, max_length=600)
    created_at: StrictStr
    clinical_approval: Literal[False]
    reviewer_identity_verified: Literal[False]
    external_notification_sent: Literal[False]


class LaboratoryReviewHistory(Contract):
    contract: Literal["oi.laboratory-inspection-review-returns/1"]
    patient_id: StrictStr
    case_id: StrictStr
    question_id: StrictStr = Field(pattern=r"^QUESTION-[0-9A-F]{32}$")
    snapshot_id: StrictStr = Field(pattern=r"^LAB-SNAPSHOT-[0-9A-F]{32}$")
    captured_report_sha256: StrictStr = Field(pattern=r"^[a-f0-9]{64}$")
    current_report_sha256: StrictStr = Field(pattern=r"^[a-f0-9]{64}$")
    source_context_state: Literal["current_unreviewed_question", "source_reassessment_required"]
    queue_fingerprint: StrictStr = Field(pattern=r"^[a-f0-9]{64}$")
    source_access_receipt_id: StrictStr = Field(pattern=r"^ACCESS-[0-9A-F]{32}$")
    review_state: Literal["awaiting_independent_verification", "returned_for_independent_verification", "source_reassessment_required"]
    current_return_receipt_id: StrictStr | None = Field(pattern=r"^REVIEW-[0-9A-F]{32}$")
    return_count: StrictInt = Field(ge=0, le=100)
    prior_return_count: StrictInt = Field(ge=0, le=100)
    receipts: list[LaboratoryReturnHistory] = Field(max_length=100)
    synthetic: Literal[True]
    clinical_approval: Literal[False]
    reviewer_identity_verified: Literal[False]
    external_notification_sent: Literal[False]


def register_laboratory_review_returns(router, *, principal, registry, records_authorized,
                                       final_question_authority, errors):
    path = ("/{patient_id}/cases/{case_id}/composer/laboratory-questions/{question_id}"
            "/source-citation-report/snapshots/{snapshot_id}/review-returns")

    def perform(patient_id, case_id, question_id, snapshot_id, request, context, command=None):
        if context.purpose != "operations" or request.query_params or (command is not None and not command.synthetic):
            raise HTTPException(404, "Laboratory review unavailable")
        actions = (*REPORT_ACTIONS, "review_return" if command is not None else "review_queue_read")
        try:
            with registry(context) as patients:
                for action in actions:
                    records_authorized(patients, context, patient_id, action)
                owner = PostgresQuestionReviewReturns(patients)
                options = dict(organization=context.organization, actor=context.actor, purpose=context.purpose,
                    recheck_authority=lambda: final_question_authority(request, context, patients, patient_id, actions),
                    prepare_response=lambda value: _prepare(
                        LaboratoryReturnReceipt if command is not None else LaboratoryReviewHistory,
                        value, command=command is not None))
                if command is not None:
                    return owner.return_laboratory_inspection(patient_id, case_id, question_id, snapshot_id,
                        **options, **command.model_dump(exclude={"synthetic"}))
                return owner.laboratory_inspection_queue(patient_id, case_id, question_id, snapshot_id, **options)
        except PatientRegistryDenied:
            raise HTTPException(404, "Laboratory review unavailable") from None

    @router.get(path, response_model=LaboratoryReviewHistory, responses=errors,
                operation_id="read_laboratory_inspection_review_returns_v1")
    def history(patient_id: str, case_id: str, question_id: str, snapshot_id: str, request: Request,
                context: Principal = Depends(principal)):
        return perform(patient_id, case_id, question_id, snapshot_id, request, context)

    @router.post(path, status_code=201, response_model=LaboratoryReturnReceipt,
                 responses={200: {"model": LaboratoryReturnReceipt}, **errors},
                 operation_id="return_laboratory_inspection_for_verification_v1")
    def returning(patient_id: str, case_id: str, question_id: str, snapshot_id: str, request: Request,
                  payload: ReturnLaboratoryInspection, context: Principal = Depends(principal)):
        return perform(patient_id, case_id, question_id, snapshot_id, request, context, payload)
