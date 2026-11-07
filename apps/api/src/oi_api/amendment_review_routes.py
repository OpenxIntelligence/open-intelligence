"""Patient routes for scoped laboratory amendment comparisons and independent verification."""
from fastapi import Depends, HTTPException, Request
from fastapi.responses import JSONResponse

from open_intelligence.patient_registry import PatientRegistryDenied
from .access import Principal
from .amendment_review_contracts import AmendmentCommand, AmendmentComparison, AmendmentInbox, AmendmentReceipt
from .laboratory_amendment_reviews import LaboratoryAmendmentReviews


def _prepare(model, result):
    validated = model(**result)
    status = 201 if isinstance(validated, AmendmentReceipt) and not validated.duplicate else 200
    response = JSONResponse(validated.model_dump(mode="json"), status_code=status,
                            headers={"Cache-Control": "no-store", "X-Content-Type-Options": "nosniff"})
    if len(response.body) > 4 * 1024 * 1024:
        raise ValueError("Amendment review response exceeds bounded size")
    return response


def register_amendment_review_routes(router, *, principal, registry, final_question_authority, errors):
    case = "/{patient_id}/cases/{case_id}"
    detail = case + "/followthrough/{task_id}/laboratory-amendment-review"

    def run(request, context, patient_id, case_id, model, *, task_id=None, command=None):
        if request.query_params:
            raise HTTPException(404, "Amendment verification unavailable")
        try:
            with registry(context) as patients:
                return LaboratoryAmendmentReviews(patients).run(
                    patient_id, case_id, organization=context.organization, actor=context.actor,
                    purpose=context.purpose, task_id=task_id, command=command,
                    prepare_response=lambda result: _prepare(model, result),
                    recheck_authority=lambda actions: final_question_authority(
                        request, context, patients, patient_id, actions))
        except PatientRegistryDenied:
            raise HTTPException(404, "Amendment verification unavailable") from None

    @router.get(detail, response_model=AmendmentComparison, responses=errors,
                operation_id="read_laboratory_amendment_review_v1")
    def comparison(patient_id: str, case_id: str, task_id: str, request: Request,
                   context: Principal = Depends(principal)):
        return run(request, context, patient_id, case_id, AmendmentComparison, task_id=task_id)

    @router.post(detail, response_model=AmendmentReceipt, status_code=201,
                 responses={200: {"model": AmendmentReceipt}, **errors},
                 operation_id="record_laboratory_amendment_verification_v1")
    def record(patient_id: str, case_id: str, task_id: str, payload: AmendmentCommand,
               request: Request, context: Principal = Depends(principal)):
        return run(request, context, patient_id, case_id, AmendmentReceipt, task_id=task_id, command=payload)

    @router.get(case + "/laboratory-amendment-requests", response_model=AmendmentInbox,
                responses=errors, operation_id="list_laboratory_amendment_requests_v1")
    def inbox(patient_id: str, case_id: str, request: Request, context: Principal = Depends(principal)):
        return run(request, context, patient_id, case_id, AmendmentInbox)
