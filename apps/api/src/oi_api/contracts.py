"""Versioned shell responses. These are not patient-domain contracts."""

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

SCHEMA_REVISION = "0030_lab_amendment_reviews"
POSTGRES_MAJOR = 16


class Contract(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class Liveness(Contract):
    status: Literal["ok"] = "ok"


class DatabaseStatus(Contract):
    status: Literal["unconfigured", "unavailable", "unsupported_version", "schema_mismatch", "ready"]
    required_postgres_major: Literal[16] = POSTGRES_MAJOR
    required_revision: Literal[SCHEMA_REVISION] = SCHEMA_REVISION


class Readiness(Contract):
    status: Literal["ready", "not_ready"]
    database: DatabaseStatus


class VersionManifest(Contract):
    product: Literal["Open Intelligence"] = "Open Intelligence"
    api_version: Literal["v1"] = "v1"
    stage: Literal["synthetic_patient_registry"] = "synthetic_patient_registry"
    authentication: Literal["deny_all", "synthetic_fixture", "trusted_provider"] = "deny_all"
    patient_access_policy: Literal["synthetic_fixture", "persisted_grants"] = "synthetic_fixture"
    patient_data_enabled: Literal[False] = False
    synthetic_registry_enabled: Literal[True] = True
    capabilities: list[Literal["synthetic_patient_create", "synthetic_patient_read", "synthetic_record_request_create", "synthetic_record_request_list", "synthetic_record_request_cancel", "synthetic_record_request_receive", "synthetic_case_binding_create", "synthetic_case_binding_list", "synthetic_case_binding_revoke", "synthetic_source_import", "synthetic_source_list", "synthetic_source_original_read", "synthetic_source_world_model_read", "synthetic_source_composer_preflight", "synthetic_source_question_create", "synthetic_source_question_list", "synthetic_image_import", "synthetic_image_list", "synthetic_image_original_read", "synthetic_source_review_queue_read", "synthetic_source_review_return", "synthetic_source_question_brief", "synthetic_source_review_packet_read", "synthetic_question_followthrough_read", "synthetic_question_followthrough_create", "synthetic_question_followthrough_update", "synthetic_question_evidence_search", "synthetic_question_evidence_link", "synthetic_question_evidence_list", "synthetic_question_evidence_read", "synthetic_question_evidence_import", "synthetic_question_evidence_assess", "synthetic_question_evidence_withdraw", "synthetic_question_evidence_original_read", "synthetic_question_evidence_report", "synthetic_laboratory_question_preflight", "synthetic_laboratory_question_save", "synthetic_laboratory_question_history", "synthetic_laboratory_question_evidence_metadata", "synthetic_laboratory_source_citation_report", "synthetic_ehr_encounters", "synthetic_ehr_note_drafts", "synthetic_ehr_encounter_source_links", "synthetic_source_brief_run_enqueue", "synthetic_source_brief_run_read", "synthetic_source_brief_run_cancel", "synthetic_source_brief_run_result"]] = Field(
        default_factory=lambda: ["synthetic_patient_create", "synthetic_patient_read", "synthetic_record_request_create", "synthetic_record_request_list", "synthetic_record_request_cancel", "synthetic_record_request_receive", "synthetic_case_binding_create", "synthetic_case_binding_list", "synthetic_case_binding_revoke", "synthetic_source_import", "synthetic_source_list", "synthetic_source_original_read", "synthetic_source_world_model_read", "synthetic_source_composer_preflight", "synthetic_source_question_create", "synthetic_source_question_list", "synthetic_image_import", "synthetic_image_list", "synthetic_image_original_read", "synthetic_source_review_queue_read", "synthetic_source_review_return", "synthetic_source_question_brief", "synthetic_source_review_packet_read", "synthetic_question_followthrough_read", "synthetic_question_followthrough_create", "synthetic_question_followthrough_update", "synthetic_question_evidence_search", "synthetic_question_evidence_link", "synthetic_question_evidence_list", "synthetic_question_evidence_read", "synthetic_question_evidence_import", "synthetic_question_evidence_assess", "synthetic_question_evidence_withdraw", "synthetic_question_evidence_original_read", "synthetic_question_evidence_report", "synthetic_laboratory_question_preflight", "synthetic_laboratory_question_save", "synthetic_laboratory_question_history", "synthetic_laboratory_question_evidence_metadata", "synthetic_laboratory_source_citation_report", "synthetic_ehr_encounters", "synthetic_ehr_note_drafts", "synthetic_ehr_encounter_source_links", "synthetic_source_brief_run_enqueue", "synthetic_source_brief_run_read", "synthetic_source_brief_run_cancel", "synthetic_source_brief_run_result"])
    openapi: Literal["/v1/openapi.json"] = "/v1/openapi.json"
