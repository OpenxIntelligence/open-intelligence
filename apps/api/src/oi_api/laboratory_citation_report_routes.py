"""Authorized, freshly rendered laboratory source/citation inspection. No export or write."""
from typing import Literal

from fastapi import Depends, HTTPException, Request
from pydantic import Field, StrictStr

from open_intelligence.patient_registry import PatientRegistryDenied
from .access import Principal
from .contracts import Contract
from .evidence_contracts import LaboratoryEvidenceLinks
from .evidence_routes import _prepare
from .laboratory_citation_report import LaboratoryCitationReport, REPORT_ACTIONS
from .laboratory_fhir_routes import PreparedLaboratorySource


class LaboratoryCitationInspection(Contract):
    contract: Literal["oi.laboratory-source-citation-inspection/1"]
    question: StrictStr = Field(min_length=8, max_length=500)
    reported_result: PreparedLaboratorySource
    citations: LaboratoryEvidenceLinks
    clinical_review: Literal["not_performed"]
    claim_appraisal: Literal["not_performed"]


def register_laboratory_citation_report(router, *, principal, registry, records_authorized,
                                        final_question_authority, errors):
    @router.get("/{patient_id}/cases/{case_id}/composer/laboratory-questions/{question_id}/source-citation-report",
                response_model=LaboratoryCitationInspection, operation_id="read_laboratory_source_citation_report_v1",
                responses=errors)
    def read_report(patient_id: str, case_id: str, question_id: str, request: Request,
                    context: Principal = Depends(principal)):
        if context.purpose != "operations" or request.query_params:
            raise HTTPException(404, "Laboratory report unavailable")
        try:
            with registry(context) as patients:
                for action in REPORT_ACTIONS:
                    records_authorized(patients, context, patient_id, action)
                return LaboratoryCitationReport(patients).read(
                    patient_id, case_id, question_id, organization=context.organization,
                    actor=context.actor, purpose=context.purpose,
                    prepare_response=lambda result: _prepare(LaboratoryCitationInspection, result),
                    recheck_authority=lambda: final_question_authority(
                        request, context, patients, patient_id, REPORT_ACTIONS),
                )
        except PatientRegistryDenied:
            raise HTTPException(404, "Laboratory report unavailable") from None
