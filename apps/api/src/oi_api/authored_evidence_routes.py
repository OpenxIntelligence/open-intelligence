"""Human-only case-evidence routes using the existing authenticated registry port."""
from fastapi import Depends, HTTPException, Request
from fastapi.responses import JSONResponse

from open_intelligence.patient_registry import PatientRegistryDenied, PatientRegistryError
from .access import Principal
from .authored_evidence_contracts import (
    AssessEvidence, EvidenceAssessmentReceipt, EvidenceImportReceipt, EvidenceOriginal,
    EvidencePacket, EvidenceReport, EvidenceReportReceipt, EvidenceWithdrawReceipt,
    ImportEvidence, PrepareEvidenceReport, WithdrawEvidence,
)
from .evidence_report import MAX_RESPONSE_BYTES
from .authored_evidence import PostgresQuestionEvidence

BASE_ACTIONS = ("source_read", "question_read", "authored_evidence_read")


def prepare_json(model, result, *, write=False):
    """The entire wire body exists before authority refresh, audit and commit."""
    value = model(**result).model_dump(mode="json")
    response = JSONResponse(content=value, status_code=(200 if result["duplicate"] else 201) if write else 200)
    if len(response.body) > MAX_RESPONSE_BYTES:
        raise PatientRegistryError("Evidence response exceeds bounded size")
    return response


def register_evidence_routes(router, *, principal, registry, records_authorized,
                             final_question_authority, errors):
    path = "/{patient_id}/cases/{case_id}/questions/{question_id}"

    def perform(request, context, patient_id, case_id, question_id, action, method,
                model, *, write=False, payload=None, reference=None):
        if context.purpose != "operations":
            raise HTTPException(404, "Evidence unavailable")
        try:
            with registry(context) as patients:
                actions = tuple(dict.fromkeys((*BASE_ACTIONS, action)))
                for required in actions:
                    records_authorized(patients, context, patient_id, required)
                owner = PostgresQuestionEvidence(patients)
                options = {"organization": context.organization, "actor": context.actor, "purpose": context.purpose,
                           "prepare_response": lambda result: prepare_json(model, result, write=write),
                           "recheck_authority": lambda: final_question_authority(
                               request, context, patients, patient_id, actions),
                           "recheck_original_authority": lambda: final_question_authority(
                               request, context, patients, patient_id, (*actions, 'source_original_read'))}
                if payload is not None:
                    options["payload"] = payload.model_dump(mode="json", exclude_none=True)
                positional = (patient_id, case_id, question_id) + ((reference,) if reference is not None else ())
                return getattr(owner, method)(*positional, **options)
        except PatientRegistryDenied:
            raise HTTPException(404, "Evidence unavailable") from None

    @router.get(path + "/evidence", response_model=EvidencePacket, responses=errors,
                operation_id="inspect_question_evidence_v1")
    def inspect_evidence(request: Request, patient_id: str, case_id: str, question_id: str,
                         context: Principal = Depends(principal)):
        return perform(request, context, patient_id, case_id, question_id, "authored_evidence_read", "packet", EvidencePacket)

    @router.post(path + "/evidence", response_model=EvidenceImportReceipt, status_code=201,
                 responses={200: {"model": EvidenceImportReceipt}, **errors}, operation_id="import_question_evidence_v1")
    def import_evidence(request: Request, patient_id: str, case_id: str, question_id: str, payload: ImportEvidence,
                        context: Principal = Depends(principal)):
        return perform(request, context, patient_id, case_id, question_id, "authored_evidence_import", "import_evidence",
                       EvidenceImportReceipt, write=True, payload=payload)

    @router.post(path + "/evidence/{evidence_id}/withdraw", response_model=EvidenceWithdrawReceipt, status_code=201,
                 responses={200: {"model": EvidenceWithdrawReceipt}, **errors}, operation_id="withdraw_question_evidence_v1")
    def withdraw_evidence(request: Request, patient_id: str, case_id: str, question_id: str, evidence_id: str,
                          payload: WithdrawEvidence, context: Principal = Depends(principal)):
        return perform(request, context, patient_id, case_id, question_id, "authored_evidence_withdraw", "withdraw",
                       EvidenceWithdrawReceipt, write=True, payload=payload, reference=evidence_id)

    @router.get(path + "/evidence/{evidence_id}/original", response_model=EvidenceOriginal,
                responses=errors, operation_id="read_question_evidence_original_v1")
    def original_evidence(request: Request, patient_id: str, case_id: str, question_id: str, evidence_id: str,
                          context: Principal = Depends(principal)):
        return perform(request, context, patient_id, case_id, question_id, "authored_evidence_original_read", "original",
                       EvidenceOriginal, reference=evidence_id)

    @router.post(path + "/evidence-assessments", response_model=EvidenceAssessmentReceipt, status_code=201,
                 responses={200: {"model": EvidenceAssessmentReceipt}, **errors}, operation_id="assess_question_evidence_v1")
    def assess_evidence(request: Request, patient_id: str, case_id: str, question_id: str, payload: AssessEvidence,
                        context: Principal = Depends(principal)):
        return perform(request, context, patient_id, case_id, question_id, "authored_evidence_assess", "assess",
                       EvidenceAssessmentReceipt, write=True, payload=payload)

    @router.post(path + "/evidence-reports", response_model=EvidenceReportReceipt, status_code=201,
                 responses={200: {"model": EvidenceReportReceipt}, **errors}, operation_id="prepare_question_evidence_report_v1")
    def prepare_report(request: Request, patient_id: str, case_id: str, question_id: str, payload: PrepareEvidenceReport,
                       context: Principal = Depends(principal)):
        return perform(request, context, patient_id, case_id, question_id, "evidence_report_export", "create_report",
                       EvidenceReportReceipt, write=True, payload=payload)

    @router.get(path + "/evidence-reports/{report_id}", response_model=EvidenceReport, responses=errors,
                operation_id="read_question_evidence_report_v1")
    def read_report(request: Request, patient_id: str, case_id: str, question_id: str, report_id: str,
                    context: Principal = Depends(principal)):
        return perform(request, context, patient_id, case_id, question_id, "evidence_report_export", "report",
                       EvidenceReport, reference=report_id)
