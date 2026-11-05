"""Authorized FHIR-R4 laboratory preview and canonical source custody.

Preview remains nonpersisting. Explicit imports use the existing source owner,
active case binding and source-import authority; neither establishes clinical review.
"""
from __future__ import annotations

from fastapi import Depends, HTTPException, Request
from fastapi.responses import JSONResponse
from pydantic import Field, StrictBool

from open_intelligence.patient_registry import PatientRegistryDenied

from .contracts import Contract
from .laboratory_fhir_r4 import LaboratoryBundleRejected, prepare_laboratory_bundle
from .laboratory_fhir_store import PostgresLaboratoryFHIR
from .sources import PostgresSourceVersions


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


def register_laboratory_fhir_routes(router, *, principal, registry,
                                    records_authorized, final_authority, errors):
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
