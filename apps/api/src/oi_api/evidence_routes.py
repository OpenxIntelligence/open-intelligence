"""Question-scoped metadata routes reuse the existing trusted authority port."""
from fastapi import Depends, HTTPException, Request
from fastapi.responses import JSONResponse

from open_intelligence.patient_registry import PatientRegistryDenied
from .access import Principal
from .evidence_contracts import (
    EvidenceSearch, EvidenceSearchResult, EvidenceLinkCreate, EvidenceLinkReceipt, EvidenceLinks,
    LaboratoryEvidenceLinks, LaboratoryEvidenceSearchResult,
)
from .question_evidence import PostgresLaboratoryQuestionEvidence, PostgresQuestionEvidence


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
    # Both routes use the same scoped grants, serialization and receipt boundary.
    def register(prefix, owner, kind, search_model, links_model, *, reject_query):
        def scoped_actions(request, context, patients, patient_id, write=False):
            if context.purpose != "operations" or (reject_query and request.query_params):
                raise PatientRegistryDenied("Question evidence unavailable")
            actions = ("question_read", "source_read", "evidence_read") + (("evidence_link",) if write else ())
            for action in actions:
                records_authorized(patients, context, patient_id, action)
            return actions

        @router.post(prefix + "/evidence-search",
                     response_model=search_model, responses=errors,
                     operation_id=f"search_{kind}_evidence_metadata_v1")
        def search(request: Request, patient_id: str, case_id: str, question_id: str,
                   payload: EvidenceSearch, context: Principal = Depends(principal)):
            try:
                with registry(context) as patients:
                    actions = scoped_actions(request, context, patients, patient_id)
                    return owner(patients).search(
                        patient_id, case_id, question_id, organization=context.organization,
                        actor=context.actor, purpose=context.purpose, query=payload.query,
                        prepare_response=lambda result: _prepare(search_model, result),
                        recheck_authority=lambda: final_question_authority(
                            request, context, patients, patient_id, actions),
                    )
            except PatientRegistryDenied:
                raise HTTPException(404, "Question evidence unavailable") from None

        @router.get(prefix + "/evidence-links",
                    response_model=links_model, responses=errors,
                    operation_id=f"list_{kind}_evidence_links_v1")
        def links(request: Request, patient_id: str, case_id: str, question_id: str,
                  context: Principal = Depends(principal)):
            try:
                with registry(context) as patients:
                    actions = scoped_actions(request, context, patients, patient_id)
                    return owner(patients).links(
                        patient_id, case_id, question_id, organization=context.organization,
                        actor=context.actor, purpose=context.purpose,
                        prepare_response=lambda result: _prepare(links_model, result),
                        recheck_authority=lambda: final_question_authority(
                            request, context, patients, patient_id, actions),
                    )
            except PatientRegistryDenied:
                raise HTTPException(404, "Question evidence unavailable") from None

        @router.post(prefix + "/evidence-links",
                     response_model=EvidenceLinkReceipt, status_code=201,
                     responses={200: {"model": EvidenceLinkReceipt}, **errors},
                     operation_id=f"link_{kind}_evidence_metadata_v1")
        def create(request: Request, patient_id: str, case_id: str, question_id: str,
                   payload: EvidenceLinkCreate, context: Principal = Depends(principal)):
            try:
                with registry(context) as patients:
                    actions = scoped_actions(request, context, patients, patient_id, write=True)
                    return owner(patients).create_link(
                        patient_id, case_id, question_id, organization=context.organization,
                        actor=context.actor, purpose=context.purpose,
                        **payload.model_dump(exclude={"synthetic"}),
                        prepare_response=lambda result: _prepare(EvidenceLinkReceipt, result, command=True),
                        recheck_authority=lambda: final_question_authority(
                            request, context, patients, patient_id, actions),
                    )
            except PatientRegistryDenied:
                raise HTTPException(404, "Question evidence unavailable") from None

    case = "/{patient_id}/cases/{case_id}"
    register(case + "/questions/{question_id}", PostgresQuestionEvidence, "question",
             EvidenceSearchResult, EvidenceLinks, reject_query=False)
    register(case + "/composer/laboratory-questions/{question_id}", PostgresLaboratoryQuestionEvidence,
             "laboratory_question", LaboratoryEvidenceSearchResult, LaboratoryEvidenceLinks, reject_query=True)
