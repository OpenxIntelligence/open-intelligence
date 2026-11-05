"""Question-scoped metadata routes reuse the existing trusted authority port."""
from fastapi import Depends, HTTPException, Request
from fastapi.responses import JSONResponse

from open_intelligence.patient_registry import PatientRegistryConflict, PatientRegistryDenied
from .access import Principal
from .authored_evidence import PostgresQuestionEvidence as AuthoredEvidence
from .composer_runs import ACTIONS, PostgresComposerRuns
from .question_review_returns import PostgresQuestionReviewReturns
from .evidence_contracts import (
    EvidenceSearch, EvidenceSearchResult, EvidenceLinkCreate, EvidenceLinkReceipt, EvidenceLinks,
    LaboratoryEvidenceLinks, LaboratoryEvidenceSearchResult, RunEvidenceReview, RunEvidenceReviewReceipt,
    RunQuoteReview, RunQuoteReviewReceipt,
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

    @router.post(case + "/questions/{question_id}/runs/{run_id}/verification-return",
                 response_model=RunEvidenceReviewReceipt | RunQuoteReviewReceipt, status_code=201,
                 responses={200: {"model": RunEvidenceReviewReceipt | RunQuoteReviewReceipt}, **errors},
                 operation_id="return_completed_brief_and_link_for_verification_v1")
    def return_run(request: Request, patient_id: str, case_id: str, question_id: str, run_id: str,
                   payload: RunEvidenceReview | RunQuoteReview, context: Principal = Depends(principal)):
        try:
            if context.purpose != "operations" or request.query_params:
                raise PatientRegistryDenied("Verification handoff unavailable")
            with registry(context) as patients:
                quoted = isinstance(payload, RunQuoteReview)
                actions = (*ACTIONS, "authored_evidence_read" if quoted else "evidence_read", "review_return")
                for action in actions:
                    records_authorized(patients, context, patient_id, action)
                scope = dict(organization=context.organization, actor=context.actor, purpose=context.purpose)
                rights_check = None
                proof = {}

                def authority():
                    final_question_authority(request, context, patients, patient_id, actions)
                    if rights_check is not None:
                        rights_check()

                def verify(item, source_index):
                    nonlocal rights_check, proof
                    PostgresComposerRuns(patients).verify_review_input_locked(
                        item, run_id, payload.expected_result_sha256, **scope, recheck_authority=authority)
                    if quoted:
                        proof, rights_check = AuthoredEvidence(patients).verify_review_assessment_locked(
                            item, payload.assessment_id, source_index=source_index, **scope)
                        if (proof["assessment_id"] != payload.assessment_id
                                or proof["evidence_sha256"] != payload.expected_evidence_sha256
                                or proof["quote_sha256"] != payload.expected_quote_sha256):
                            raise PatientRegistryConflict("Evidence passage differs from the selected version")
                        return {**proof, "verification_type": payload.verification,
                                "run_id": run_id, "result_sha256": payload.expected_result_sha256}
                    rights_check = PostgresQuestionEvidence(patients).permitted_review_link_locked(
                        item, payload.link_id, payload.citation, payload.expected_metadata_sha256, **scope)
                    # The canonical intent and its audit bind both exact inputs. Queue-only
                    # readers need neither the citation nor the content of the completed run.
                    record_id, version = payload.citation.rsplit("@", 1)
                    return {"verification_type": "exact_version_metadata_only", "run_id": run_id,
                            "result_sha256": payload.expected_result_sha256, "evidence_link_id": payload.link_id,
                            "citation_record_id": record_id, "citation_version": version,
                            "metadata_sha256": payload.expected_metadata_sha256}

                def receipt(value):
                    selected = proof if quoted else {
                        "link_id": payload.link_id, "citation": payload.citation,
                        "metadata_sha256": payload.expected_metadata_sha256}
                    return _prepare(RunQuoteReviewReceipt if quoted else RunEvidenceReviewReceipt, {
                        **value, **selected, "contract": "oi.synthetic-run-evidence-review-return/1",
                        "run_id": run_id, "result_sha256": payload.expected_result_sha256,
                        "verification": payload.verification,
                        "review_state": "returned_for_independent_verification",
                        "clinical_approval": False, "model_executed": False,
                    }, command=True)

                return PostgresQuestionReviewReturns(patients).return_for_verification(
                    patient_id, case_id, question_id, **scope,
                    request_key="run-review-" + run_id + "-" + (payload.assessment_id if quoted else payload.link_id),
                    expected_queue_fingerprint=None,
                    reason=("Independently verify the question after checking the brief and exact authored passage." if quoted
                            else "Independently verify the source question after checking the brief and linked citation metadata."),
                    verify_handoff=verify, recheck_authority=authority, prepare_response=receipt)
        except PatientRegistryDenied:
            raise HTTPException(404, "Verification handoff unavailable") from None
