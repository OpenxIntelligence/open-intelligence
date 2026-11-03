"""Versioned shell responses. These are not patient-domain contracts."""

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

SCHEMA_REVISION = "0006_image_custody"
POSTGRES_MAJOR = 16


class Contract(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class Liveness(Contract):
    status: Literal["ok"] = "ok"


class DatabaseStatus(Contract):
    status: Literal["unconfigured", "unavailable", "unsupported_version", "schema_mismatch", "ready"]
    required_postgres_major: Literal[16] = POSTGRES_MAJOR
    required_revision: Literal["0006_image_custody"] = SCHEMA_REVISION


class Readiness(Contract):
    status: Literal["ready", "not_ready"]
    database: DatabaseStatus


class VersionManifest(Contract):
    product: Literal["Open Intelligence"] = "Open Intelligence"
    api_version: Literal["v1"] = "v1"
    stage: Literal["synthetic_patient_registry"] = "synthetic_patient_registry"
    authentication: Literal["deny_all", "synthetic_fixture", "trusted_provider"] = "deny_all"
    patient_data_enabled: Literal[False] = False
    synthetic_registry_enabled: Literal[True] = True
    capabilities: list[Literal["synthetic_patient_create", "synthetic_patient_read", "synthetic_record_request_create", "synthetic_record_request_list", "synthetic_record_request_cancel", "synthetic_record_request_receive", "synthetic_case_binding_create", "synthetic_case_binding_list", "synthetic_case_binding_revoke", "synthetic_source_import", "synthetic_source_list", "synthetic_source_original_read", "synthetic_source_world_model_read", "synthetic_image_import", "synthetic_image_list", "synthetic_image_original_read"]] = Field(
        default_factory=lambda: ["synthetic_patient_create", "synthetic_patient_read", "synthetic_record_request_create", "synthetic_record_request_list", "synthetic_record_request_cancel", "synthetic_record_request_receive", "synthetic_case_binding_create", "synthetic_case_binding_list", "synthetic_case_binding_revoke", "synthetic_source_import", "synthetic_source_list", "synthetic_source_original_read", "synthetic_source_world_model_read", "synthetic_image_import", "synthetic_image_list", "synthetic_image_original_read"])
    openapi: Literal["/v1/openapi.json"] = "/v1/openapi.json"
