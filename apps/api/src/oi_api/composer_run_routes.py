"""Composer controls composed through the existing patient authority callbacks."""
from fastapi import Depends, HTTPException, Request
from fastapi.responses import JSONResponse

from open_intelligence.patient_registry import PatientRegistryDenied

from .access import Principal
from .composer_run_contracts import (
    CancelComposerRun, ComposerRunReceipt, ComposerRunResult, ComposerRunStatus, EnqueueComposerRun,
)
from .composer_runs import ACTIONS, PostgresComposerRuns


def _prepare(model, value, *, enqueue=False):
    validated = model(**value)
    response = JSONResponse(content=validated.model_dump(mode="json"),
                            status_code=(200 if validated.duplicate else 201) if enqueue else 200,
                            headers={"Cache-Control": "no-store", "X-Content-Type-Options": "nosniff"})
    if len(response.body) > 73_728:
        raise ValueError("Execution response exceeds bounded size")
    return response


def register_composer_run_routes(router, *, principal, registry, records_authorized,
                                 final_question_authority, errors):
    prefix = "/{patient_id}/cases/{case_id}/questions/{question_id}/runs"

    def scope(request, context, patients, patient_id):
        if context.purpose != "operations":
            raise PatientRegistryDenied("Composer run unavailable")
        for action in ACTIONS:
            records_authorized(patients, context, patient_id, action)
        return dict(organization=context.organization, actor=context.actor, purpose=context.purpose,
                    recheck_authority=lambda: final_question_authority(
                        request, context, patients, patient_id, ACTIONS))

    @router.post(prefix, response_model=ComposerRunReceipt, status_code=201,
                 responses={200: {"model": ComposerRunReceipt}, **errors},
                 operation_id="enqueue_source_brief_run_v1")
    def enqueue(request: Request, patient_id: str, case_id: str, question_id: str,
                payload: EnqueueComposerRun, context: Principal = Depends(principal)):
        try:
            with registry(context) as patients:
                return PostgresComposerRuns(patients).enqueue(
                    patient_id, case_id, question_id, **scope(request, context, patients, patient_id),
                    **payload.model_dump(exclude={"synthetic"}),
                    prepare_response=lambda value: _prepare(ComposerRunReceipt, value, enqueue=True))
        except PatientRegistryDenied:
            raise HTTPException(404, "Composer run unavailable") from None

    @router.get(prefix + "/{run_id}", response_model=ComposerRunStatus, responses=errors,
                operation_id="read_source_brief_run_v1")
    def get(request: Request, patient_id: str, case_id: str, question_id: str, run_id: str,
            context: Principal = Depends(principal)):
        try:
            with registry(context) as patients:
                return PostgresComposerRuns(patients).get(
                    patient_id, case_id, question_id, run_id, **scope(request, context, patients, patient_id),
                    prepare_response=lambda value: _prepare(ComposerRunStatus, value))
        except PatientRegistryDenied:
            raise HTTPException(404, "Composer run unavailable") from None

    @router.post(prefix + "/{run_id}/cancel", response_model=ComposerRunStatus, responses=errors,
                 operation_id="cancel_source_brief_run_v1")
    def cancel(request: Request, patient_id: str, case_id: str, question_id: str, run_id: str,
               payload: CancelComposerRun, context: Principal = Depends(principal)):
        try:
            with registry(context) as patients:
                return PostgresComposerRuns(patients).cancel(
                    patient_id, case_id, question_id, run_id, **scope(request, context, patients, patient_id),
                    prepare_response=lambda value: _prepare(ComposerRunStatus, value))
        except PatientRegistryDenied:
            raise HTTPException(404, "Composer run unavailable") from None

    @router.get(prefix + "/{run_id}/result", response_model=ComposerRunResult, responses=errors,
                operation_id="read_source_brief_run_result_v1")
    def result(request: Request, patient_id: str, case_id: str, question_id: str, run_id: str,
               context: Principal = Depends(principal)):
        try:
            with registry(context) as patients:
                return PostgresComposerRuns(patients).result(
                    patient_id, case_id, question_id, run_id, **scope(request, context, patients, patient_id),
                    prepare_response=lambda value: _prepare(ComposerRunResult, value))
        except PatientRegistryDenied:
            raise HTTPException(404, "Composer run unavailable") from None
