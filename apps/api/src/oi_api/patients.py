"""HTTP composition of the existing canonical patient registry, synthetic only."""

from contextlib import contextmanager
from datetime import datetime
from typing import Literal

from fastapi import APIRouter, Body, Depends, HTTPException, Request, Response
from fastapi.responses import JSONResponse
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import Field, StrictBool, field_validator

from open_intelligence.patient_registry import (
    PatientRegistryConflict, PatientRegistryDenied, PatientRegistryError, _key,
)
from open_intelligence.postgres_registry import PostgresPatientRegistry

from .access import Authentication, Principal, authenticate_request
from .contracts import Contract
from .database import Database
from .record_requests import PostgresRecordRequests
from .case_bindings import CanonicalCaseBindings
from .sources import PostgresSourceVersions
from .source_world_model import project_source_world_model
from .composer_preflight import PostgresSourceComposerPreflight
from .source_questions import PostgresSourceQuestions
from .question_review_returns import PostgresQuestionReviewReturns

from .images import PostgresSourceImages


class CreatePatient(Contract):
    synthetic: StrictBool
    request_key: str = Field(min_length=3, max_length=128)

    @field_validator("synthetic")
    @classmethod
    def synthetic_acknowledgement(cls, value):
        if value is not True:
            raise ValueError("Only independently fictional patient identities are accepted")
        return value

    @field_validator("request_key")
    @classmethod
    def opaque_request(cls, value):
        return _key(value, "request_key")


class CreatedPatient(Contract):
    patient_id: str
    duplicate: bool


class Patient(Contract):
    patient_id: str
    origin_org: str
    created_at: datetime
    status: Literal["active", "suspended"]
    revision: int = Field(ge=1)


class Error(Contract):
    detail: str


class CreateRecordRequest(Contract):
    synthetic: StrictBool
    request_key: str = Field(min_length=3, max_length=128)
    kind: Literal["clinical", "pathology", "laboratory", "imaging", "molecular", "other"]
    record_label: str = Field(min_length=1, max_length=140)
    source_organization: str = Field(min_length=1, max_length=100)

    @field_validator("synthetic")
    @classmethod
    def synthetic_only(cls, value):
        if value is not True:
            raise ValueError("Only fictional record requests are allowed")
        return value


class CancelRecordRequest(Contract):
    synthetic: StrictBool
    reason: str = Field(min_length=1, max_length=200)

    @field_validator("synthetic")
    @classmethod
    def synthetic_only(cls, value):
        if value is not True:
            raise ValueError("Only fictional record requests are allowed")
        return value


class RecordRequestReceipt(Contract):
    request_id: str
    duplicate: bool


class ReceiveRecordRequest(Contract):
    synthetic: StrictBool
    case_id: str = Field(min_length=6, max_length=40,
                         pattern=r"^CASE-[A-Z0-9-]{1,35}$")
    source_id: str = Field(pattern=r"^SRC-[0-9A-F]{32}$")

    @field_validator("synthetic")
    @classmethod
    def fictional_only(cls, value):
        if value is not True:
            raise ValueError("Only fictional original-source receipts are allowed")
        return value


class ReceivedRecordRequest(Contract):
    request_id: str
    source_id: str
    version: int = Field(ge=1)
    duplicate: bool


class ReceivedSourceReference(Contract):
    case_id: str
    source_id: str
    version: int = Field(ge=1)
    sha256: str


class RecordRequest(Contract):
    request_id: str
    patient_id: str
    kind: str
    record_label: str
    source_organization: str
    status: Literal["requested", "received", "cancelled"]
    revision: int = Field(ge=1)
    created_at: datetime
    updated_at: datetime
    receipt_status: Literal["not_received", "source_current_unreviewed",
                            "source_superseded_reconciliation_required",
                            "binding_revoked_not_usable"]
    source_reference: ReceivedSourceReference | None
    external_request_sent: Literal[False]


class RecordRequests(Contract):
    patient_id: str
    requests: list[RecordRequest]
    synthetic: Literal[True] = True
    external_request_sent: Literal[False] = False
    source_receipts_enabled: Literal[True] = True



class CreateCaseBinding(Contract):
    synthetic: StrictBool
    case_id: str = Field(min_length=6, max_length=40, pattern=r"^CASE-[A-Z0-9-]{1,35}$")
    source_organization: str = Field(min_length=3, max_length=128)
    source_system: str = Field(min_length=3, max_length=128)
    source_subject_ref: str = Field(min_length=3, max_length=128)
    review_ref: str = Field(min_length=3, max_length=128)

    @field_validator("synthetic")
    @classmethod
    def fictional_only(cls, value):
        if value is not True:
            raise ValueError("Only independently fictional case mappings are allowed")
        return value


class RevokeCaseBinding(Contract):
    synthetic: StrictBool
    reason: str = Field(min_length=10, max_length=200)

    @field_validator("synthetic")
    @classmethod
    def fictional_only(cls, value):
        if value is not True:
            raise ValueError("Only fictional case mappings are allowed")
        return value


class CaseBindingReceipt(Contract):
    case_id: str
    patient_id: str
    duplicate: bool
    source_identity_verified: Literal[False]


class CaseBinding(Contract):
    case_id: str
    patient_id: str
    source_organization: str
    source_system: str
    source_subject_ref: str
    review_ref: str
    status: Literal["active", "revoked"]
    revision: int
    created_at: datetime
    revoked_at: datetime | None
    source_identity_verified: Literal[False]
    clinical_sources_linked: Literal[False]
    clinical_conclusions: Literal[False]


class CaseBindingList(Contract):
    patient_id: str
    mappings: list[CaseBinding]
    synthetic: Literal[True] = True
    source_identity_verified: Literal[False] = False
    clinical_sources_linked: Literal[False] = False



class ImportOriginalSource(Contract):
    synthetic: StrictBool
    original_text: str = Field(min_length=1, max_length=65_536)

    @field_validator("synthetic")
    @classmethod
    def fictional_only(cls, value):
        if value is not True:
            raise ValueError("Only independently authored fictional reports are allowed")
        return value


class OriginalSourceReceipt(Contract):
    result: Literal["imported", "duplicate", "quarantined"]
    duplicate: bool
    source_id: str | None
    version: int | None


class SourceVersion(Contract):
    source_id: str
    document_id: str
    version: int
    sha256: str
    kind: Literal["clinical", "pathology", "laboratory", "imaging", "molecular", "other"]
    event_date: str
    issued_at: str
    received_at: datetime
    specimen_id: str | None
    state: Literal["current", "superseded"]
    supersedes_id: str | None


class SourceFinding(Contract):
    source_id: str
    finding_key: str
    reported_state: str
    source_statement: str
    source_line: int
    clinical_review_state: Literal["not_established"] = "not_established"


class OriginalSourceIndex(Contract):
    contract: Literal["oi.synthetic-original-sources/1"]
    patient_id: str
    case_id: str
    access_receipt_id: str
    sources: list[SourceVersion]
    source_reported_assertions: list[SourceFinding]
    synthetic: Literal[True]
    clinical_interpretation: Literal[False]
    research_review_invalidation_integrated: Literal[False]


class OriginalSource(Contract):
    source_id: str
    case_id: str
    access_receipt_id: str
    document_id: str
    version: int
    state: Literal["current", "superseded"]
    sha256: str
    original_text: str
    synthetic: Literal[True]
    clinical_review_state: Literal["not_established"]



class WorldSourceRef(Contract):
    source_id: str
    source_line: int = Field(ge=1)


class WorldObservation(Contract):
    source_id: str
    document_id: str
    document_version: int = Field(ge=1)
    source_sha256: str
    source_kind: Literal["clinical", "pathology", "laboratory", "imaging", "molecular", "other"]
    finding_key: str
    reported_state: str
    source_statement: str
    source_line: int = Field(ge=1)
    specimen_id: str | None
    event_date: str
    issued_at: str
    review_state: Literal["not_established"]
    clinical_meaning: None


class WorldConflict(Contract):
    specimen_id: str
    event_date: str
    finding_key: str
    status: Literal["unresolved_source_disagreement"]
    reported_states: list[str]
    source_refs: list[WorldSourceRef]
    clinical_interpretation: Literal["not_performed"]


class WorldSummary(Contract):
    current_sources: int = Field(ge=0)
    historical_sources: int = Field(ge=0)
    current_observations: int = Field(ge=0)
    unresolved_observations: int = Field(ge=0)
    source_disagreements: int = Field(ge=0)


class SourceWorldModel(Contract):
    contract: Literal["oi.pg-source-world-model/1"]
    patient_id: str
    case_id: str
    access_receipt_id: str
    synthetic: Literal[True]
    authority: Literal["source_report_only_unreviewed"]
    clinical_interpretation: Literal[False]
    research_review_invalidation_integrated: Literal[False]
    composer_execution_authorized: Literal[False]
    snapshot_fingerprint: str
    as_of_received_at: datetime | None
    summary: WorldSummary
    current_sources: list[SourceVersion]
    history: list[SourceVersion]
    observations: list[WorldObservation]
    unresolved_refs: list[WorldSourceRef]
    conflicts: list[WorldConflict]
    limitations: list[str]


class PrepareSourceComposer(Contract):
    synthetic: StrictBool
    expected_source_snapshot_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    source_id: str = Field(pattern=r"^SRC-[0-9A-F]{32}$")
    source_line: int = Field(ge=1, le=10_000)
    question: str = Field(min_length=8, max_length=500)

    @field_validator("synthetic")
    @classmethod
    def synthetic_only(cls, value):
        if value is not True:
            raise ValueError("Only fictional Composer preflights are allowed")
        return value


class SelectedComposerSource(Contract):
    source_id: str
    document_id: str
    version: int = Field(ge=1)
    sha256: str
    line: int = Field(ge=1)
    finding_key: str
    reported_state: str
    statement: str
    kind: str
    event_date: str
    issued_at: str
    specimen_id: str | None


class PreparedSourceComposer(Contract):
    contract: Literal["oi.synthetic-source-composer-preflight/2"]
    patient_id: str
    case_id: str
    question: str
    source_snapshot_contract: Literal["oi.pg-source-world-model/1"]
    source_snapshot_sha256: str
    access_receipt_id: str
    selected_source: SelectedComposerSource
    source_context_only: Literal[True]
    biomedical_evidence_rights_verified: Literal[False]
    model_execution_authorized: Literal[False]
    durable_question_created: Literal[False]
    durable_review_connected: Literal[False]
    clinical_approval: Literal[False]
    clinical_interpretation: Literal["not_performed"]
    reassessment_policy: Literal["revalidate_source_and_authority_before_any_future_write"]
    limitations: str
    preflight_sha256: str


class SaveSourceQuestion(Contract):
    synthetic: StrictBool
    request_key: str = Field(min_length=3, max_length=128)
    source_id: str = Field(pattern=r"^SRC-[0-9A-F]{32}$")
    source_line: int = Field(ge=1, le=10_000)
    question: str = Field(min_length=8, max_length=500)
    expected_source_snapshot_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    expected_preflight_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")

    @field_validator("synthetic")
    @classmethod
    def synthetic_only(cls, value):
        if value is not True:
            raise ValueError("Only fictional source-anchored questions are allowed")
        return value


class SavedSourceQuestion(Contract):
    question_id: str
    duplicate: bool


class QuestionSourceState(Contract):
    question_id: str
    patient_id: str
    case_id: str
    question: str
    source_id: str
    source_line: int = Field(ge=1)
    source_sha256: str
    source_version: int = Field(ge=1)
    source_snapshot_contract: Literal["oi.pg-source-world-model/1",
                                      "oi.synthetic-postgres-world-model-sources/1"]
    source_snapshot_sha256: str
    preflight_sha256: str
    created_at: datetime
    source_context_state: Literal["current_unreviewed_question", "source_reassessment_required"]
    human_review_state: Literal["not_submitted"]
    clinical_approval: Literal[False]
    model_executed: Literal[False]


class SourceQuestionsList(Contract):
    contract: Literal["oi.synthetic-source-questions/2"]
    patient_id: str
    case_id: str
    access_receipt_id: str
    questions: list[QuestionSourceState]
    synthetic: Literal[True] = True
    clinical_review_connected: Literal[False] = False
    clinical_approval: Literal[False] = False

class SourceImage(Contract):
    image_id: str
    source_id: str
    case_id: str
    sha256: str
    byte_count: int = Field(ge=132, le=2_097_152)
    study_uid: str
    series_uid: str
    sop_uid: str
    modality: Literal["CT"]
    study_date: str


class SourceImageReceipt(SourceImage):
    result: Literal["imported", "linked", "duplicate"]
    synthetic: Literal[True]
    source_identity_verified: Literal[False]
    clinical_interpretation: Literal[False]


class SourceImageIndex(Contract):
    patient_id: str
    case_id: str
    source_id: str
    images: list[SourceImage]
    access_receipt_id: str
    synthetic: Literal[True]
    source_identity_verified: Literal[False]


class ReturnForVerification(Contract):
    synthetic: StrictBool
    request_key: str = Field(min_length=3, max_length=128)
    expected_queue_fingerprint: str = Field(pattern=r"^[0-9a-f]{64}$")
    reason: str = Field(min_length=10, max_length=600)

    @field_validator("synthetic")
    @classmethod
    def fictional_only(cls, value):
        if value is not True:
            raise ValueError("Only fictional review return receipts are enabled")
        return value


class ReturnForVerificationReceipt(Contract):
    receipt_id: str
    question_id: str
    duplicate: bool


class QuestionReviewItem(Contract):
    question_id: str
    patient_id: str
    case_id: str
    question: str
    source_id: str
    source_line: int = Field(ge=1)
    source_sha256: str
    source_version: int = Field(ge=1)
    source_snapshot_sha256: str
    source_snapshot_contract: Literal["oi.pg-source-world-model/1",
                                      "oi.synthetic-postgres-world-model-sources/1"]
    preflight_sha256: str
    created_at: datetime
    kind: Literal["source-question"]
    queue_fingerprint: str | None
    queue_fingerprint_contract: Literal["oi.synthetic-source-review-return/2"]
    source_context_state: Literal["current_unreviewed_question", "source_reassessment_required"]
    review_state: Literal["awaiting_independent_verification",
                          "returned_for_independent_verification", "source_reassessment_required"]
    current_return_receipt_id: str | None
    return_count: int = Field(ge=0)
    prior_return_count: int = Field(ge=0)
    clinical_approval: Literal[False]
    reviewer_identity_verified: Literal[False]


class QuestionReturnHistory(Contract):
    receipt_id: str
    question_id: str
    queue_fingerprint: str
    source_snapshot_sha256: str
    source_snapshot_contract: Literal["oi.pg-source-world-model/1",
                                      "oi.synthetic-postgres-world-model-sources/1"]
    queue_fingerprint_contract: Literal["oi.synthetic-source-review-return/1",
                                       "oi.synthetic-source-review-return/2"]
    actor_label: str
    action: Literal["returned"]
    reason: str
    created_at: datetime
    reviewer_identity_verified: Literal[False]
    external_notification_sent: Literal[False]
    clinical_approval: Literal[False]


class QuestionReviewQueue(Contract):
    contract: Literal["oi.synthetic-question-review-return-queue/2"]
    patient_id: str
    case_id: str
    access_receipt_id: str
    synthetic: Literal[True]
    items: list[QuestionReviewItem]
    receipts: list[QuestionReturnHistory]
    external_notification_sent: Literal[False]
    reviewer_identity_verified: Literal[False]
    clinical_approval: Literal[False]
    review_completion_supported: Literal[False]


def patient_router(database: Database, authentication: Authentication, *, image_archive=None) -> APIRouter:
    router = APIRouter(prefix="/v1/patients", tags=["Synthetic patient registry"])
    bearer = HTTPBearer(auto_error=False, scheme_name="SyntheticFixture",
                        description="Local synthetic fixture credential. Not a patient account or clinical consent.")

    def principal(request: Request, credentials: HTTPAuthorizationCredentials | None = Depends(bearer)) -> Principal:
        return authenticate_request(request, authentication)

    @contextmanager
    def registry(context: Principal):
        try:
            with database.registry_connection() as connection:
                def authorize(actor, subject, action, purpose):
                    if actor != context.actor or purpose != context.purpose or action not in context.actions:
                        return False
                    if action == "patient_create":
                        return subject == context.organization
                    if action not in {"patient_read", "record_request_create", "record_request_read", "record_request_cancel", "record_request_receive", "case_binding_create", "case_binding_read", "case_binding_revoke", "source_import", "source_read", "source_original_read", "composer_context_read", "question_create", "question_read", "image_import", "image_read", "image_original_read", "review_queue_read", "review_return"} or subject not in context.patient_ids:
                        return False
                    cursor = connection.cursor()
                    try:
                        cursor.execute("SELECT origin_org FROM identity.identity_patients WHERE patient_id=%s", (subject,))
                        row = cursor.fetchone()
                        return row is not None and row[0] == context.organization
                    finally:
                        cursor.close()

                yield PostgresPatientRegistry(connection, authorize)
        except PatientRegistryDenied:
            raise
        except PatientRegistryConflict:
            raise HTTPException(409, "Request intent conflict") from None
        except PatientRegistryError:
            raise HTTPException(422, "Invalid request") from None
        except HTTPException:
            raise
        except Exception:
            # DB-API errors, schema failures and provider details stay private.
            raise HTTPException(503, "Patient registry unavailable") from None

    errors = {code: {"model": Error} for code in (401, 403, 404, 408, 409, 413, 415, 422, 503)}

    @router.post("", response_model=CreatedPatient, status_code=201,
                 responses={200: {"model": CreatedPatient}, **errors}, operation_id="create_patient_v1")
    def create_patient(payload: CreatePatient, response: Response, context: Principal = Depends(principal)):
        if "patient_create" not in context.actions:
            raise HTTPException(403, "Patient creation unavailable")
        try:
            with registry(context) as patients:
                receipt = patients.create_patient(organization=context.organization,
                                                   actor=context.actor, purpose=context.purpose,
                                                   request_key=payload.request_key)
        except PatientRegistryDenied:
            raise HTTPException(403, "Patient creation unavailable") from None
        response.status_code = 200 if receipt["duplicate"] else 201
        return CreatedPatient(**receipt)

    @router.get("/{patient_id}", response_model=Patient, responses=errors, operation_id="read_patient_v1")
    def get_patient(patient_id: str, context: Principal = Depends(principal)):
        if "patient_read" not in context.actions or patient_id not in context.patient_ids:
            raise HTTPException(404, "Patient unavailable")
        try:
            with registry(context) as patients:
                value = patients.get_patient(patient_id, actor=context.actor, purpose=context.purpose)
        except PatientRegistryDenied:
            raise HTTPException(404, "Patient unavailable") from None
        return Patient(**value)

    def records_authorized(patients: PostgresPatientRegistry, context: Principal,
                           patient_id: str, action: str) -> None:
        # An acquisition grant never grants patient access implicitly.
        if ("patient_read" not in context.actions or action not in context.actions
                or patient_id not in context.patient_ids):
            raise HTTPException(404, "Patient unavailable")
        try:
            patients._allow(context.actor, patient_id, "patient_read", context.purpose)
            patients._allow(context.actor, patient_id, action, context.purpose)
        except PatientRegistryDenied:
            raise HTTPException(404, "Patient unavailable") from None

    @router.get("/{patient_id}/record-requests", response_model=RecordRequests,
                responses=errors, operation_id="list_record_requests_v1")
    def list_records(patient_id: str, context: Principal = Depends(principal)):
        try:
            with registry(context) as patients:
                records_authorized(patients, context, patient_id, "record_request_read")
                # Request-read permission alone exposes receipt state, not
                # source identifiers. Original source metadata requires its
                # independent source_read action; original bytes have a third.
                source_grant = "source_read" in context.actions
                if source_grant:
                    patients._allow(context.actor, patient_id,
                                    "source_read", context.purpose)
                records = PostgresRecordRequests(patients).list(
                    patient_id, organization=context.organization,
                    disclose_source=source_grant)
                return RecordRequests(patient_id=patient_id, requests=records)
        except PatientRegistryDenied:
            raise HTTPException(404, "Patient unavailable") from None

    @router.post("/{patient_id}/record-requests", response_model=RecordRequestReceipt,
                 status_code=201, responses={200: {"model": RecordRequestReceipt}, **errors},
                 operation_id="create_record_request_v1")
    def create_record(patient_id: str, payload: CreateRecordRequest, response: Response,
                      context: Principal = Depends(principal)):
        try:
            with registry(context) as patients:
                records_authorized(patients, context, patient_id, "record_request_create")
                result = PostgresRecordRequests(patients).create(
                    patient_id, organization=context.organization, actor=context.actor,
                    purpose=context.purpose, request_key=payload.request_key, kind=payload.kind,
                    record_label=payload.record_label,
                    source_organization=payload.source_organization)
        except PatientRegistryDenied:
            raise HTTPException(404, "Patient unavailable") from None
        response.status_code = 200 if result["duplicate"] else 201
        return RecordRequestReceipt(**result)

    @router.post("/{patient_id}/record-requests/{request_id}/cancel",
                 response_model=RecordRequestReceipt, responses=errors,
                 operation_id="cancel_record_request_v1")
    def cancel_record(patient_id: str, request_id: str, payload: CancelRecordRequest,
                      context: Principal = Depends(principal)):
        try:
            with registry(context) as patients:
                records_authorized(patients, context, patient_id, "record_request_cancel")
                result = PostgresRecordRequests(patients).cancel(
                    patient_id, request_id, organization=context.organization,
                    actor=context.actor, reason=payload.reason)
        except PatientRegistryDenied:
            raise HTTPException(404, "Patient unavailable") from None
        return RecordRequestReceipt(**result)


    @router.post("/{patient_id}/record-requests/{request_id}/receive",
                 response_model=ReceivedRecordRequest, status_code=201,
                 responses={200: {"model": ReceivedRecordRequest}, **errors},
                 operation_id="receive_original_record_request_v1")
    def receive_record(patient_id: str, request_id: str,
                       payload: ReceiveRecordRequest, response: Response,
                       context: Principal = Depends(principal)):
        try:
            with registry(context) as patients:
                records_authorized(patients, context, patient_id, "record_request_receive")
                records_authorized(patients, context, patient_id, "source_read")
                result = PostgresRecordRequests(patients).receive(
                    patient_id, request_id, payload.case_id, payload.source_id,
                    organization=context.organization, actor=context.actor,
                    purpose=context.purpose)
        except PatientRegistryDenied:
            raise HTTPException(404, "Record request or source unavailable") from None
        response.status_code = 200 if result["duplicate"] else 201
        return ReceivedRecordRequest(**result)


    @router.get("/{patient_id}/case-bindings", response_model=CaseBindingList,
                responses=errors, operation_id="list_case_bindings_v1")
    def list_case_bindings(patient_id: str, context: Principal = Depends(principal)):
        try:
            with registry(context) as patients:
                records_authorized(patients, context, patient_id, "case_binding_read")
                rows = CanonicalCaseBindings(patients).list(
                    patient_id, organization=context.organization)
                return CaseBindingList(patient_id=patient_id, mappings=rows)
        except PatientRegistryDenied:
            raise HTTPException(404, "Patient unavailable") from None

    @router.post("/{patient_id}/case-bindings", response_model=CaseBindingReceipt,
                 status_code=201, responses={200: {"model": CaseBindingReceipt}, **errors},
                 operation_id="create_case_binding_v1")
    def create_case_binding(patient_id: str, payload: CreateCaseBinding,
                            response: Response, context: Principal = Depends(principal)):
        try:
            with registry(context) as patients:
                records_authorized(patients, context, patient_id, "case_binding_create")
                result = CanonicalCaseBindings(patients).bind(
                    patient_id, organization=context.organization,
                    actor=context.actor, purpose=context.purpose,
                    case_id=payload.case_id, source_organization=payload.source_organization,
                    source_system=payload.source_system,
                    source_subject_ref=payload.source_subject_ref,
                    review_ref=payload.review_ref)
        except PatientRegistryDenied:
            raise HTTPException(404, "Patient unavailable") from None
        response.status_code = 200 if result["duplicate"] else 201
        return CaseBindingReceipt(**result)

    @router.post("/{patient_id}/case-bindings/{case_id}/revoke",
                 response_model=CaseBindingReceipt, responses=errors,
                 operation_id="revoke_case_binding_v1")
    def revoke_case_binding(patient_id: str, case_id: str,
                            payload: RevokeCaseBinding, context: Principal = Depends(principal)):
        try:
            with registry(context) as patients:
                records_authorized(patients, context, patient_id, "case_binding_revoke")
                result = CanonicalCaseBindings(patients).revoke(
                    patient_id, case_id, organization=context.organization,
                    actor=context.actor, reason=payload.reason)
        except PatientRegistryDenied:
            raise HTTPException(404, "Patient unavailable") from None
        return CaseBindingReceipt(**result)


    def refresh_source_authority(request: Request, initial: Principal,
                                 patients: PostgresPatientRegistry,
                                 patient_id: str, action: str) -> None:
        current = authenticate_request(request, authentication)
        if (current.actor, current.organization, current.purpose) != (
                initial.actor, initial.organization, initial.purpose):
            raise PatientRegistryDenied("Source authority changed")
        # Both patient grant and operation grant are independently enforced.
        records_authorized(patients, current, patient_id, action)

    def final_question_authority(request: Request, initial: Principal,
                                 patients: PostgresPatientRegistry,
                                 patient_id: str, actions: tuple[str, ...]) -> None:
        """Preserve the upstream fresh actor/context/grant check under owner locks."""
        current = authenticate_request(request, authentication)
        if (current.actor, current.organization, current.purpose) != (
                initial.actor, initial.organization, initial.purpose):
            raise PatientRegistryDenied("Source-question authority changed")
        for action in actions:
            records_authorized(patients, current, patient_id, action)

    @router.get("/{patient_id}/cases/{case_id}/review-queue",
                response_model=QuestionReviewQueue, responses=errors,
                operation_id="list_source_question_review_queue_v1")
    def list_source_question_review_queue(request: Request, patient_id: str, case_id: str,
                                         context: Principal = Depends(principal)):
        if context.purpose != "operations":
            raise HTTPException(404, "Question review queue unavailable")
        try:
            with registry(context) as patients:
                actions = ("question_read", "source_read", "review_queue_read")
                for action in actions:
                    records_authorized(patients, context, patient_id, action)
                return PostgresQuestionReviewReturns(patients).queue(
                    patient_id, case_id, organization=context.organization,
                    actor=context.actor, purpose=context.purpose,
                    # Complete the actual JSON body under the source owner's
                    # locks, before final authority, access audit and commit.
                    prepare_response=lambda result: JSONResponse(
                        QuestionReviewQueue(**result).model_dump(mode="json"),
                        headers={"Cache-Control": "no-store"}),
                    recheck_authority=lambda: final_question_authority(
                        request, context, patients, patient_id, actions),
                )
        except PatientRegistryDenied:
            raise HTTPException(404, "Question review queue unavailable") from None

    @router.post(
        "/{patient_id}/cases/{case_id}/questions/{question_id}/return-for-verification",
        response_model=ReturnForVerificationReceipt, status_code=201,
        responses={200: {"model": ReturnForVerificationReceipt}, **errors},
        operation_id="return_source_question_for_verification_v1")
    def return_source_question_for_verification(
            request: Request, patient_id: str, case_id: str, question_id: str,
            payload: ReturnForVerification,
            context: Principal = Depends(principal)):
        if context.purpose != "operations":
            raise HTTPException(404, "Review return unavailable")
        try:
            with registry(context) as patients:
                actions = ("question_read", "source_read", "review_return")
                for action in actions:
                    records_authorized(patients, context, patient_id, action)
                return PostgresQuestionReviewReturns(patients).return_for_verification(
                    patient_id, case_id, question_id, organization=context.organization,
                    actor=context.actor, purpose=context.purpose,
                    request_key=payload.request_key,
                    expected_queue_fingerprint=payload.expected_queue_fingerprint,
                    reason=payload.reason,
                    prepare_response=lambda result: JSONResponse(
                        ReturnForVerificationReceipt(**result).model_dump(mode="json"),
                        status_code=200 if result["duplicate"] else 201,
                        headers={"Cache-Control": "no-store"}),
                    recheck_authority=lambda: final_question_authority(
                        request, context, patients, patient_id, actions),
                )
        except PatientRegistryDenied:
            raise HTTPException(404, "Review return unavailable") from None

    @router.get("/{patient_id}/cases/{case_id}/questions",
                response_model=SourceQuestionsList, responses=errors,
                operation_id="list_source_questions_v1")
    def list_source_questions(request: Request, patient_id: str, case_id: str,
                              context: Principal = Depends(principal)):
        if context.purpose != "operations":
            raise HTTPException(404, "Question intake unavailable")
        try:
            with registry(context) as patients:
                actions = ("question_read", "source_read")
                for action in actions:
                    records_authorized(patients, context, patient_id, action)
                return PostgresSourceQuestions(patients).list(
                    patient_id, case_id, organization=context.organization,
                    actor=context.actor, purpose=context.purpose,
                    prepare_response=lambda result: SourceQuestionsList(**result),
                    recheck_authority=lambda: final_question_authority(
                        request, context, patients, patient_id, actions),
                )
        except PatientRegistryDenied:
            raise HTTPException(404, "Question intake unavailable") from None

    @router.post("/{patient_id}/cases/{case_id}/questions",
                 response_model=SavedSourceQuestion, status_code=201,
                 responses={200: {"model": SavedSourceQuestion}, **errors},
                 operation_id="save_source_question_v1")
    def save_source_question(request: Request, patient_id: str, case_id: str,
                             payload: SaveSourceQuestion, response: Response,
                             context: Principal = Depends(principal)):
        if context.purpose != "operations":
            raise HTTPException(404, "Question intake unavailable")
        try:
            with registry(context) as patients:
                actions = ("question_create", "composer_context_read", "source_read")
                for action in actions:
                    records_authorized(patients, context, patient_id, action)
                receipt = PostgresSourceQuestions(patients).create(
                    patient_id, case_id, organization=context.organization,
                    actor=context.actor, purpose=context.purpose,
                    request_key=payload.request_key, question=payload.question,
                    source_id=payload.source_id, source_line=payload.source_line,
                    expected_source_snapshot_sha256=payload.expected_source_snapshot_sha256,
                    expected_preflight_sha256=payload.expected_preflight_sha256,
                    prepare_response=lambda result: SavedSourceQuestion(**result),
                    recheck_authority=lambda: final_question_authority(
                        request, context, patients, patient_id, actions),
                )
        except PatientRegistryDenied:
            raise HTTPException(404, "Question intake unavailable") from None
        response.status_code = 200 if receipt.duplicate else 201
        return receipt

    @router.post("/{patient_id}/cases/{case_id}/composer/source-preflight",
                 response_model=PreparedSourceComposer, responses=errors,
                 operation_id="prepare_source_composer_v1")
    def prepare_source_composer(request: Request, patient_id: str, case_id: str,
                                payload: PrepareSourceComposer,
                                context: Principal = Depends(principal)):
        if context.purpose != "operations":
            raise HTTPException(404, "Source context unavailable")
        try:
            with registry(context) as patients:
                actions = ("source_read", "composer_context_read")
                for action in actions:
                    records_authorized(patients, context, patient_id, action)
                return PostgresSourceComposerPreflight(patients).preview(
                    patient_id, case_id, organization=context.organization,
                    actor=context.actor, purpose=context.purpose,
                    expected_source_snapshot_sha256=payload.expected_source_snapshot_sha256,
                    source_id=payload.source_id, source_line=payload.source_line,
                    question=payload.question,
                    prepare_response=lambda result: PreparedSourceComposer(**result),
                    recheck_authority=lambda: final_question_authority(
                        request, context, patients, patient_id, actions),
                )
        except PatientRegistryDenied:
            raise HTTPException(404, "Source context unavailable") from None

    @router.get("/{patient_id}/cases/{case_id}/sources", response_model=OriginalSourceIndex,
                responses=errors, operation_id="list_original_sources_v1")
    def list_original_sources(request: Request, patient_id: str, case_id: str,
                              context: Principal = Depends(principal)):
        try:
            with registry(context) as patients:
                records_authorized(patients, context, patient_id, "source_read")
                return PostgresSourceVersions(patients).list(
                    patient_id, case_id, organization=context.organization,
                    actor=context.actor, purpose=context.purpose,
                    prepare_response=lambda index: OriginalSourceIndex(**index),
                    recheck_authority=lambda: refresh_source_authority(
                        request, context, patients, patient_id, "source_read"))
        except PatientRegistryDenied:
            raise HTTPException(404, "Source unavailable") from None

    @router.get("/{patient_id}/cases/{case_id}/world-model",
                response_model=SourceWorldModel, responses=errors,
                operation_id="read_source_world_model_v1")
    def source_world_model(request: Request, patient_id: str, case_id: str,
                           context: Principal = Depends(principal)):
        """Derived from the one existing source owner, no new write authority.

        Deliberately only source-reported observations; not the full original
        SQLite clinical World Model, literature/AI, or review workflow.
        """
        try:
            with registry(context) as patients:
                records_authorized(patients, context, patient_id, "source_read")
                return PostgresSourceVersions(patients).list(
                    patient_id, case_id, organization=context.organization,
                    actor=context.actor, purpose=context.purpose,
                    prepare_response=lambda index: SourceWorldModel(**project_source_world_model(index)),
                    recheck_authority=lambda: refresh_source_authority(
                        request, context, patients, patient_id, "source_read"))
        except PatientRegistryDenied:
            raise HTTPException(404, "Source unavailable") from None

    @router.post("/{patient_id}/cases/{case_id}/sources",
                 response_model=OriginalSourceReceipt, status_code=201,
                 responses={200: {"model": OriginalSourceReceipt}, **errors},
                 operation_id="import_original_source_v1")
    def import_original_source(patient_id: str, case_id: str,
                               payload: ImportOriginalSource, response: Response,
                               context: Principal = Depends(principal)):
        try:
            with registry(context) as patients:
                records_authorized(patients, context, patient_id, "source_import")
                result = PostgresSourceVersions(patients).import_original(
                    patient_id, case_id, payload.original_text.encode("utf-8"),
                    organization=context.organization, actor=context.actor,
                    purpose=context.purpose)
        except PatientRegistryDenied:
            raise HTTPException(404, "Source unavailable") from None
        response.status_code = 201 if result["result"] == "imported" else 200
        return OriginalSourceReceipt(**result)

    @router.get("/{patient_id}/cases/{case_id}/sources/{source_id}",
                response_model=OriginalSource, responses=errors,
                operation_id="read_exact_original_source_v1")
    def original_source(request: Request, patient_id: str, case_id: str, source_id: str,
                        context: Principal = Depends(principal)):
        try:
            with registry(context) as patients:
                records_authorized(patients, context, patient_id, "source_original_read")
                result = PostgresSourceVersions(patients).original(
                    patient_id, case_id, source_id, organization=context.organization,
                    actor=context.actor, purpose=context.purpose,
                    recheck_authority=lambda: refresh_source_authority(
                        request, context, patients, patient_id, "source_original_read"))
                return OriginalSource(**result)
        except PatientRegistryDenied:
            raise HTTPException(404, "Source unavailable") from None

    @router.post("/{patient_id}/cases/{case_id}/sources/{source_id}/images",
                 response_model=SourceImageReceipt, status_code=201,
                 responses={200: {"model": SourceImageReceipt}, **errors},
                 operation_id="import_source_image_v1")
    def import_source_image(request: Request, patient_id: str, case_id: str, source_id: str,
                            original: bytes = Body(media_type="application/dicom"),
                            context: Principal = Depends(principal)):
        if request.query_params:
            raise HTTPException(422, "Invalid request")
        if (request.headers.getlist("content-type") != ["application/dicom"]
                or request.headers.getlist("content-encoding")):
            raise HTTPException(415, "Unsupported image transport")
        try:
            with registry(context) as patients:
                records_authorized(patients, context, patient_id, "image_import")
                return PostgresSourceImages(patients).import_original(
                    patient_id, case_id, source_id, original, organization=context.organization,
                    actor=context.actor, purpose=context.purpose,
                    # Validate and encode the actual body before the image
                    # owner's final authority check, event and commit. Returning
                    # a DTO would let FastAPI encode it after those boundaries.
                    prepare_response=lambda result: JSONResponse(
                        SourceImageReceipt(**result).model_dump(mode="json"),
                        status_code=200 if result["result"] == "duplicate" else 201,
                        headers={"Cache-Control": "no-store"}),
                    recheck_authority=lambda: refresh_source_authority(
                        request, context, patients, patient_id, "image_import"))
        except PatientRegistryDenied:
            raise HTTPException(404, "Image unavailable") from None

    @router.get("/{patient_id}/cases/{case_id}/sources/{source_id}/images",
                response_model=SourceImageIndex, responses=errors,
                operation_id="list_source_images_v1")
    def list_source_images(request: Request, patient_id: str, case_id: str, source_id: str,
                           context: Principal = Depends(principal)):
        if request.query_params:
            raise HTTPException(422, "Invalid request")
        try:
            with registry(context) as patients:
                records_authorized(patients, context, patient_id, "image_read")
                return PostgresSourceImages(patients).list(
                    patient_id, case_id, source_id, organization=context.organization,
                    actor=context.actor, purpose=context.purpose,
                    prepare_response=lambda result: JSONResponse(
                        SourceImageIndex(**result).model_dump(mode="json"),
                        headers={"Cache-Control": "no-store"}),
                    recheck_authority=lambda: refresh_source_authority(
                        request, context, patients, patient_id, "image_read"))
        except PatientRegistryDenied:
            raise HTTPException(404, "Image unavailable") from None

    @router.get("/{patient_id}/cases/{case_id}/sources/{source_id}/images/{image_id}",
                response_class=Response,
                responses={200: {"content": {"application/dicom": {"schema": {"type": "string", "format": "binary"}}}}, **errors},
                operation_id="read_original_source_image_v1")
    def original_source_image(request: Request, patient_id: str, case_id: str, source_id: str,
                               image_id: str, context: Principal = Depends(principal)):
        if request.query_params:
            raise HTTPException(422, "Invalid request")
        try:
            with registry(context) as patients:
                records_authorized(patients, context, patient_id, "image_original_read")
                return PostgresSourceImages(patients, archive=image_archive).original(
                    patient_id, case_id, source_id, image_id, organization=context.organization,
                    actor=context.actor, purpose=context.purpose,
                    prepare_response=lambda raw, receipt: Response(
                        raw, media_type="application/dicom", headers={
                            "Content-Disposition": 'attachment; filename="original.dcm"',
                            "X-OI-Access-Receipt": receipt, "X-Content-Type-Options": "nosniff",
                            "Content-Security-Policy": "default-src 'none'", "Cache-Control": "no-store",
                        }),
                    recheck_authority=lambda: refresh_source_authority(
                        request, context, patients, patient_id, "image_original_read"))
        except PatientRegistryDenied:
            raise HTTPException(404, "Image unavailable") from None
    return router
