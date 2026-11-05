"""Authorized FHIR-R4 laboratory preview and canonical source custody.

Preview remains nonpersisting. Explicit imports use the existing source owner,
active case binding and source-import authority; neither establishes clinical review.
"""
from __future__ import annotations

from typing import Literal

from fastapi import Depends, HTTPException, Request
from fastapi.responses import JSONResponse
from pydantic import Field, StrictBool, StrictInt, StrictStr

from open_intelligence.patient_registry import PatientRegistryDenied, PatientRegistryError

from .contracts import Contract
from .composer_preflight import PostgresSourceComposerPreflight
from .laboratory_fhir_r4 import LaboratoryBundleRejected, prepare_laboratory_bundle
from .laboratory_fhir_store import PostgresLaboratoryFHIR
from .sources import PostgresSourceVersions
from .laboratory_questions import PostgresLaboratoryQuestions


class LabFHIRPreviewRequest(Contract):
    synthetic: StrictBool
    bundle_json: str = Field(min_length=1, max_length=65_536)


class LabObservationPreview(Contract):
    reference: str
    loinc_code: str
    effective_at: str
    issued_at: str
    source_reported: bool
    clinical_review: str
    status: str
    value_text: str | None
    unit_code: str | None
    absent_reason: str | None


class LabFHIRImportRequest(Contract):
    synthetic: StrictBool
    request_key: str = Field(min_length=3, max_length=128)
    expected_previous_source_id: str | None = Field(
        default=None, pattern=r"^SRC-[0-9A-F]{32}$")
    bundle_json: str = Field(min_length=1, max_length=65_536)


class LabFHIRImportReceipt(Contract):
    source_id: str = Field(pattern=r"^SRC-[0-9A-F]{32}$")
    version: int = Field(ge=1)
    duplicate: bool
    original_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    observation_count: int = Field(ge=1, le=16)


class LabFHIRPreviewResponse(Contract):
    contract: str = "oi.fhir-r4-laboratory-preview/1"
    patient_id: str
    case_id: str
    source_organization: str
    source_system: str
    mapped_subject_reference: str
    original_sha256: str
    original_byte_count: int
    specimen_reference: str
    specimen_type_text: str
    specimen_collected_at: str
    report_reference: str | None
    observations: tuple[LabObservationPreview, ...]
    synthetic: bool = True
    persisted: bool = False
    clinical_review: str = "not_performed"
    verified_identity: bool = False
    source_version_created: bool = False


class PrepareLaboratoryQuestion(Contract):
    synthetic: StrictBool
    source_id: StrictStr = Field(pattern=r"^SRC-[0-9A-F]{32}$")
    observation_reference: StrictStr = Field(pattern=r"^Observation/[A-Za-z0-9.-]{1,64}$")
    expected_source_snapshot_sha256: StrictStr = Field(pattern=r"^[0-9a-f]{64}$")
    question: StrictStr = Field(min_length=8, max_length=500)


class PreparedLaboratorySource(Contract):
    anchor_kind: Literal["fhir_observation"]
    source_id: StrictStr = Field(pattern=r"^SRC-[0-9A-F]{32}$")
    document_id: StrictStr
    version: StrictInt = Field(ge=1)
    sha256: StrictStr = Field(pattern=r"^[0-9a-f]{64}$")
    kind: Literal["laboratory"]
    resource_reference: StrictStr
    specimen_reference: StrictStr
    specimen_type_text: StrictStr
    specimen_collected_at: StrictStr
    report_reference: StrictStr
    loinc_code: StrictStr
    effective_at: StrictStr
    issued_at: StrictStr
    status: Literal["reported_value", "reported_absent"]
    value_text: StrictStr | None
    unit_code: StrictStr | None
    absent_reason: Literal["unknown", "not-performed", "error", "masked"] | None
    source_reported: Literal[True]
    review_state: Literal["not_established"]
    clinical_review: Literal["not_performed"]


class PreparedLaboratoryQuestion(Contract):
    contract: Literal["oi.synthetic-laboratory-question-preflight/1"]
    patient_id: StrictStr
    case_id: StrictStr
    question: StrictStr
    source_snapshot_contract: Literal["oi.pg-source-world-model/1"]
    source_snapshot_sha256: StrictStr = Field(pattern=r"^[0-9a-f]{64}$")
    selected_source: PreparedLaboratorySource
    synthetic: Literal[True]
    source_context_only: Literal[True]
    durable_question_created: Literal[False]
    durable_review_connected: Literal[False]
    biomedical_evidence_rights_verified: Literal[False]
    model_execution_authorized: Literal[False]
    clinical_approval: Literal[False]
    clinical_interpretation: Literal["not_performed"]
    terminology_validation: Literal["not_performed"]
    reassessment_policy: Literal["revalidate_source_and_authority_before_any_future_write"]
    preflight_sha256: StrictStr = Field(pattern=r"^[0-9a-f]{64}$")
    access_receipt_id: StrictStr = Field(pattern=r"^ACCESS-[0-9A-F]{32}$")


class SaveLaboratoryQuestion(PrepareLaboratoryQuestion):
    request_key: StrictStr = Field(min_length=3, max_length=128)
    expected_preflight_sha256: StrictStr = Field(pattern=r"^[0-9a-f]{64}$")


class LaboratorySaveReceipt(Contract):
    question_id: StrictStr = Field(pattern=r"^QUESTION-[0-9A-F]{32}$")
    duplicate: StrictBool


class LaboratoryQuestionEntry(Contract):
    question_id: StrictStr = Field(pattern=r"^QUESTION-[0-9A-F]{32}$")
    question: StrictStr = Field(min_length=8, max_length=500)
    source_id: StrictStr = Field(pattern=r"^SRC-[0-9A-F]{32}$")
    source_version: StrictInt = Field(ge=1)
    source_sha256: StrictStr = Field(pattern=r"^[0-9a-f]{64}$")
    observation_reference: StrictStr = Field(pattern=r"^Observation/[A-Za-z0-9.-]{1,64}$")
    source_snapshot_sha256: StrictStr = Field(pattern=r"^[0-9a-f]{64}$")
    preflight_sha256: StrictStr = Field(pattern=r"^[0-9a-f]{64}$")
    source_context_state: Literal["current_unreviewed_question", "source_reassessment_required"]


class LaboratoryQuestionHistory(Contract):
    patient_id: StrictStr
    case_id: StrictStr
    access_receipt_id: StrictStr = Field(pattern=r"^ACCESS-[0-9A-F]{32}$")
    questions: list[LaboratoryQuestionEntry]


def _laboratory_question_response(body: Contract, status: int = 200) -> JSONResponse:
    response = JSONResponse(
        content=body.model_dump(mode="json"), status_code=status,
        headers={"Cache-Control": "no-store", "X-Content-Type-Options": "nosniff"},
    )
    if len(response.body) > 1_048_576:
        raise PatientRegistryError("Laboratory question response exceeds the supported size")
    return response


def register_laboratory_fhir_routes(router, *, principal, registry,
                                    records_authorized, final_authority, errors):
    question_path = "/{patient_id}/cases/{case_id}/composer/laboratory-questions"

    @router.post(question_path, response_model=LaboratorySaveReceipt, status_code=201,
                 responses={200: {"model": LaboratorySaveReceipt}, **errors},
                 operation_id="save_fictional_laboratory_question_v1")
    def save_laboratory_question(request: Request, patient_id: str, case_id: str,
                                 payload: SaveLaboratoryQuestion, context=Depends(principal)):
        if payload.synthetic is not True or context.purpose != "operations" or request.query_params:
            raise HTTPException(404, "Laboratory question unavailable")
        actions = ("question_create", "composer_context_read", "source_read")
        try:
            with registry(context) as patients:
                for action in actions:
                    records_authorized(patients, context, patient_id, action)

                def encode(result):
                    receipt = LaboratorySaveReceipt(**result)
                    return _laboratory_question_response(receipt, 200 if receipt.duplicate else 201)

                return PostgresLaboratoryQuestions(patients).save(
                    patient_id, case_id, actor=context.actor, organization=context.organization,
                    purpose=context.purpose, **payload.model_dump(exclude={"synthetic"}),
                    prepare_response=encode,
                    recheck_authority=lambda: final_authority(request, context, patients, patient_id, actions),
                )
        except PatientRegistryDenied:
            raise HTTPException(404, "Laboratory question unavailable") from None

    @router.get(question_path, response_model=LaboratoryQuestionHistory, responses=errors,
                operation_id="list_fictional_laboratory_questions_v1")
    def list_laboratory_questions(request: Request, patient_id: str, case_id: str,
                                  context=Depends(principal)):
        if context.purpose != "operations" or request.query_params:
            raise HTTPException(404, "Laboratory questions unavailable")
        actions = ("question_read", "source_read")
        try:
            with registry(context) as patients:
                for action in actions:
                    records_authorized(patients, context, patient_id, action)
                return PostgresLaboratoryQuestions(patients).list(
                    patient_id, case_id, actor=context.actor, organization=context.organization,
                    purpose=context.purpose,
                    prepare_response=lambda result: _laboratory_question_response(LaboratoryQuestionHistory(**result)),
                    recheck_authority=lambda: final_authority(request, context, patients, patient_id, actions),
                )
        except PatientRegistryDenied:
            raise HTTPException(404, "Laboratory questions unavailable") from None

    @router.post("/{patient_id}/cases/{case_id}/composer/laboratory-preflight",
                 response_model=PreparedLaboratoryQuestion, responses=errors,
                 operation_id="prepare_fictional_laboratory_question_v1")
    def prepare_laboratory_question(request: Request, patient_id: str, case_id: str,
                                    payload: PrepareLaboratoryQuestion,
                                    context=Depends(principal)):
        if payload.synthetic is not True or context.purpose != "operations" or request.query_params:
            raise HTTPException(404, "Laboratory question context unavailable")
        try:
            with registry(context) as patients:
                actions = ("source_read", "composer_context_read")
                for action in actions:
                    records_authorized(patients, context, patient_id, action)

                def prepare_response(result):
                    # Materialize actual wire bytes under canonical source locks,
                    # before final reauthentication, the read receipt and commit.
                    response = JSONResponse(
                        content=PreparedLaboratoryQuestion(**result).model_dump(mode="json"),
                        headers={"Cache-Control": "no-store",
                                 "X-Content-Type-Options": "nosniff"},
                    )
                    if len(response.body) > 65_536:
                        raise PatientRegistryError("Laboratory question context exceeds response bound")
                    return response

                return PostgresSourceComposerPreflight(patients).preview_laboratory(
                    patient_id, case_id, organization=context.organization,
                    actor=context.actor, purpose=context.purpose,
                    source_id=payload.source_id,
                    observation_reference=payload.observation_reference,
                    question=payload.question,
                    expected_source_snapshot_sha256=payload.expected_source_snapshot_sha256,
                    prepare_response=prepare_response,
                    recheck_authority=lambda: final_authority(
                        request, context, patients, patient_id, actions),
                )
        except PatientRegistryDenied:
            raise HTTPException(404, "Laboratory question context unavailable") from None

    @router.post("/{patient_id}/cases/{case_id}/laboratory/fhir-r4/sources",
                 response_model=LabFHIRImportReceipt, status_code=201,
                 responses={200: {"model": LabFHIRImportReceipt}, **errors},
                 operation_id="import_fictional_fhir_r4_lab_v1")
    def import_laboratory_bundle(request: Request, patient_id: str, case_id: str,
                                 payload: LabFHIRImportRequest,
                                 context=Depends(principal)):
        if payload.synthetic is not True or context.purpose != "operations" or request.query_params:
            raise HTTPException(404, "Laboratory import unavailable")
        try:
            with registry(context) as patients:
                records_authorized(patients, context, patient_id, "source_import")
                # Resolve the active qualified external subject only to validate
                # the incoming bundle. The write owner locks and rechecks this
                # same binding again before any persistence.
                with patients.transaction():
                    PostgresSourceVersions(patients)._binding(
                        patient_id, case_id, context.organization, context.purpose)
                    binding = patients._fetchone(
                        "SELECT source_subject_ref FROM coordination.patient_case_bindings "
                        "WHERE case_id=%s AND patient_id=%s AND status='active'",
                        (case_id, patient_id),
                    )
                    if binding is None:
                        raise PatientRegistryDenied("Source mapping unavailable")
                try:
                    parsed = prepare_laboratory_bundle(
                        payload.bundle_json.encode("utf-8"),
                        expected_subject_reference="Patient/" + binding[0])
                except LaboratoryBundleRejected:
                    raise HTTPException(422, "Unsupported fictional laboratory bundle") from None
                return PostgresLaboratoryFHIR(patients).import_bundle(
                    patient_id, case_id, parsed,
                    organization=context.organization, actor=context.actor,
                    purpose=context.purpose, request_key=payload.request_key,
                    expected_previous_source_id=payload.expected_previous_source_id,
                    prepare_response=lambda result: JSONResponse(
                        content=LabFHIRImportReceipt(**result).model_dump(mode="json"),
                        status_code=200 if result["duplicate"] else 201,
                        headers={"Cache-Control": "no-store",
                                 "X-Content-Type-Options": "nosniff"}),
                    recheck_authority=lambda: final_authority(
                        request, context, patients, patient_id, ("source_import",)),
                )
        except PatientRegistryDenied:
            raise HTTPException(404, "Laboratory import unavailable") from None

    @router.post("/{patient_id}/cases/{case_id}/laboratory/fhir-r4/preview",
                 response_model=LabFHIRPreviewResponse, responses=errors,
                 operation_id="preview_fictional_fhir_r4_lab_v1")
    def preview_laboratory_bundle(request: Request, patient_id: str, case_id: str,
                                  payload: LabFHIRPreviewRequest,
                                  context=Depends(principal)):
        if payload.synthetic is not True or context.purpose != "operations" or request.query_params:
            raise HTTPException(404, "Laboratory preview unavailable")
        try:
            with registry(context) as patients:
                records_authorized(patients, context, patient_id, "source_import")
                # The same owner transaction locks active patient and case
                # binding. Never trust the FHIR Patient resource or a caller
                # submitted mapping to choose the destination case.
                with patients.transaction():
                    PostgresSourceVersions(patients)._binding(
                        patient_id, case_id, context.organization, context.purpose)
                    binding = patients._fetchone(
                        "SELECT source_organization,source_system,source_subject_ref "
                        "FROM coordination.patient_case_bindings "
                        "WHERE case_id=%s AND patient_id=%s AND status='active'",
                        (case_id, patient_id),
                    )
                    if binding is None:
                        raise PatientRegistryDenied("Source mapping unavailable")
                    external_org, external_system, source_subject = binding
                    try:
                        parsed = prepare_laboratory_bundle(
                            payload.bundle_json.encode("utf-8"),
                            expected_subject_reference="Patient/" + source_subject)
                    except LaboratoryBundleRejected:
                        raise HTTPException(422, "Unsupported fictional laboratory bundle") from None
                    result = LabFHIRPreviewResponse(
                        patient_id=patient_id, case_id=case_id,
                        source_organization=external_org, source_system=external_system,
                        mapped_subject_reference=parsed.subject_reference,
                        original_sha256=parsed.source_sha256,
                        original_byte_count=len(parsed.original_bytes),
                        specimen_reference=parsed.specimen_reference,
                        specimen_type_text=parsed.specimen_type_text,
                        specimen_collected_at=parsed.specimen_collected_at,
                        report_reference=parsed.report_reference,
                        observations=tuple(LabObservationPreview(**row) for row in parsed.observations),
                    )
                    # Serialize before the final fresh authentication/grant
                    # check. A failure cannot expose partially prepared data.
                    response = JSONResponse(
                        content=result.model_dump(mode="json"),
                        headers={"Cache-Control": "no-store",
                                 "X-Content-Type-Options": "nosniff"},
                    )
                    final_authority(request, context, patients, patient_id,
                                    ("source_import",))
                    # A preview is not a source receipt or proof of delivery.
                    # No event, row, source version or clinical opinion is saved.
                    return response
        except PatientRegistryDenied:
            raise HTTPException(404, "Laboratory preview unavailable") from None
