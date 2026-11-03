"""Question-scoped metadata routes reuse the existing trusted authority port."""
from fastapi import Depends, HTTPException, Request
from fastapi.responses import JSONResponse

from open_intelligence.patient_registry import PatientRegistryDenied
from .access import Principal
from .evidence_contracts import (
    EvidenceSearch, EvidenceSearchResult, EvidenceLinkCreate, EvidenceLinkReceipt, EvidenceLinks, EvidenceDoiLookup,
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
                             final_question_authority, errors, crossref_enabled=False,
                             crossref_fetcher=None, crossref_acquisition_mode="provider_lookup"):
    def scoped_actions(context, patients, patient_id, write=False):
        if context.purpose != "operations":
            raise PatientRegistryDenied("Question evidence unavailable")
        actions = ("question_read", "source_read", "evidence_read") + (("evidence_link",) if write else ())
        for action in actions:
            records_authorized(patients, context, patient_id, action)
        return actions

    @router.post("/{patient_id}/cases/{case_id}/questions/{question_id}/evidence-doi",
                 response_model=EvidenceSearchResult, responses={502: {"description": "Metadata provider unavailable"}, **errors},
                 operation_id="lookup_question_evidence_doi_v1")
    def lookup(request: Request, patient_id: str, case_id: str, question_id: str,
               payload: EvidenceDoiLookup, context: Principal = Depends(principal)):
        from .crossref_evidence import CrossrefQuestionLookup
        from open_intelligence.crossref_metadata import validate_projected_work
        if "evidence_lookup" not in context.actions:
            raise HTTPException(404, "Question evidence unavailable")
        if not crossref_enabled:
            raise HTTPException(403, "Public DOI lookup is disabled")
        try:
            with registry(context) as patients:
                actions = (*scoped_actions(context, patients, patient_id), "evidence_lookup")
                captured = CrossrefQuestionLookup(patients).preflight(
                    patient_id, case_id, question_id, organization=context.organization,
                    actor=context.actor, purpose=context.purpose, doi=payload.doi,
                    recheck_authority=lambda: final_question_authority(request, context, patients, patient_id, actions))
            # The connection, transaction and patient locks have ended. Only the
            # normalized DOI crosses this boundary; never question or source text.
            try:
                projected = validate_projected_work(crossref_fetcher(payload.doi), payload.doi)
            except Exception:
                # Refresh authority even for a provider failure; do not echo
                # transport errors or present an unavailable provider as zero hits.
                with registry(context) as patients:
                    CrossrefQuestionLookup(patients).preflight(
                        patient_id, case_id, question_id, organization=context.organization,
                        actor=context.actor, purpose=context.purpose, doi=payload.doi,
                        recheck_authority=lambda: final_question_authority(request, context, patients, patient_id, actions))
                raise HTTPException(502, "Public DOI metadata unavailable") from None
            with registry(context) as patients:
                return CrossrefQuestionLookup(patients).retain(
                    patient_id, case_id, question_id, organization=context.organization,
                    actor=context.actor, purpose=context.purpose, doi=payload.doi,
                    projected=projected, captured=captured, acquisition_mode=crossref_acquisition_mode,
                    prepare_response=lambda result: _prepare(EvidenceSearchResult, result),
                    recheck_authority=lambda: final_question_authority(request, context, patients, patient_id, actions))
        except PatientRegistryDenied:
            raise HTTPException(404, "Question evidence unavailable") from None

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
