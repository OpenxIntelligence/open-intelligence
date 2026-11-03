"""Versioned shell responses. These are not patient-domain contracts."""

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

SCHEMA_REVISION = "0002_patient_registry"
POSTGRES_MAJOR = 16


class Contract(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class Liveness(Contract):
    status: Literal["ok"] = "ok"


class DatabaseStatus(Contract):
    status: Literal["unconfigured", "unavailable", "unsupported_version", "schema_mismatch", "ready"]
    required_postgres_major: Literal[16] = POSTGRES_MAJOR
    required_revision: Literal["0002_patient_registry"] = SCHEMA_REVISION


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
    capabilities: list[Literal["synthetic_patient_create", "synthetic_patient_read"]] = Field(
        default_factory=lambda: ["synthetic_patient_create", "synthetic_patient_read"])
    openapi: Literal["/v1/openapi.json"] = "/v1/openapi.json"
