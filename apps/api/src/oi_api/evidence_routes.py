"""Question-scoped metadata routes reuse the existing trusted authority port."""
from fastapi import Depends, HTTPException, Request
from fastapi.responses import JSONResponse

from open_intelligence.patient_registry import PatientRegistryDenied
from .access import Principal
from .evidence_contracts import (
    EvidenceSearch, EvidenceSearchResult, EvidenceLinkCreate, EvidenceLinkReceipt, EvidenceLinks,
)
from .question_evidence import PostgresQuestionEvidence


def _prepare(model, value, *, command=False):
    result = model(**value)
    response = JSONResponse(
        content=result.model_dump(mode="json"),
        status_code=(200 if result.duplicate else 201) if command else 200,
        headers={"Cache-Control": "no-store", "X-Content-Type-Options": "nosniff"},
    )
    if len(response.body) > 512_000:
        raise ValueError("Evidence response exceeds bounded size")
    return response


def register_evidence_routes(router, *, principal, registry, records_authorized,
                             final_question_authority, errors):
    def scoped_actions(context, patients, patient_id, write=False):
        if context.purpose != "operations":
            raise PatientRegistryDenied("Question evidence unavailable")
        actions = ("question_read", "source_read", "evidence_read") + (("evidence_link",) if write else ())
        for action in actions:
            records_authorized(patients, context, patient_id, action)
        return actions

    @router.post("/{patient_id}/cases/{case_id}/questions/{question_id}/evidence-search",
                 response_model=EvidenceSearchResult, responses=errors,
                 operation_id="search_question_evidence_metadata_v1")
    def search(request: Request, patient_id: str, case_id: str, question_id: str,
               payload: EvidenceSearch, context: Principal = Depends(principal)):
        try:
            with registry(context) as patients:
                actions = scoped_actions(context, patients, patient_id)
                return PostgresQuestionEvidence(patients).search(
                    patient_id, case_id, question_id, organization=context.organization,
                    actor=context.actor, purpose=context.purpose, query=payload.query,
                    prepare_response=lambda result: _prepare(EvidenceSearchResult, result),
                    recheck_authority=lambda: final_question_authority(
                        request, context, patients, patient_id, actions),
                )
        except PatientRegistryDenied:
            raise HTTPException(404, "Question evidence unavailable") from None

    @router.get("/{patient_id}/cases/{case_id}/questions/{question_id}/evidence-links",
                response_model=EvidenceLinks, responses=errors,
                operation_id="list_question_evidence_links_v1")
    def links(request: Request, patient_id: str, case_id: str, question_id: str,
              context: Principal = Depends(principal)):
        try:
            with registry(context) as patients:
                actions = scoped_actions(context, patients, patient_id)
                return PostgresQuestionEvidence(patients).links(
                    patient_id, case_id, question_id, organization=context.organization,
                    actor=context.actor, purpose=context.purpose,
                    prepare_response=lambda result: _prepare(EvidenceLinks, result),
                    recheck_authority=lambda: final_question_authority(
                        request, context, patients, patient_id, actions),
                )
        except PatientRegistryDenied:
            raise HTTPException(404, "Question evidence unavailable") from None

    @router.post("/{patient_id}/cases/{case_id}/questions/{question_id}/evidence-links",
                 response_model=EvidenceLinkReceipt, status_code=201,
                 responses={200: {"model": EvidenceLinkReceipt}, **errors},
                 operation_id="link_question_evidence_metadata_v1")
    def create(request: Request, patient_id: str, case_id: str, question_id: str,
               payload: EvidenceLinkCreate, context: Principal = Depends(principal)):
        try:
            with registry(context) as patients:
                actions = scoped_actions(context, patients, patient_id, write=True)
                return PostgresQuestionEvidence(patients).create_link(
                    patient_id, case_id, question_id, organization=context.organization,
                    actor=context.actor, purpose=context.purpose,
                    **payload.model_dump(exclude={"synthetic"}),
                    prepare_response=lambda result: _prepare(EvidenceLinkReceipt, result, command=True),
                    recheck_authority=lambda: final_question_authority(
                        request, context, patients, patient_id, actions),
                )
        except PatientRegistryDenied:
            raise HTTPException(404, "Question evidence unavailable") from None
