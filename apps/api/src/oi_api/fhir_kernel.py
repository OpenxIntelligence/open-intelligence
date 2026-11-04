"""Bounded FHIR source admission kernel; interoperability, not a second patient master.

This first slice validates only the transport shape needed to preserve an
external resource as an unreviewed source. It does not perform profile,
terminology or clinical validation and does not create clinical assertions.
"""
from __future__ import annotations

import hashlib
import json
import re
from typing import Final

FHIR_R4: Final = "4.0.1"
MAX_RESOURCE_BYTES: Final = 65_536
MAX_DEPTH: Final = 64
MAX_PROFILES: Final = 16
_SUPPORTED = frozenset(("Patient", "Observation", "DiagnosticReport", "Provenance", "AuditEvent"))
_ID = re.compile(r"^[A-Za-z0-9\-.]{1,64}$")

_US_CORE_BASELINE = {
    "package_id": "hl7.fhir.us.core",
    "version": "9.0.0",
    "fhir_version": FHIR_R4,
    "state": "declared_not_loaded",
    "artifact_sha256": None,
    "profile_validation_available": False,
}


class FhirRejected(ValueError):
    """The source cannot enter the bounded FHIR admission surface."""


def declared_package_baselines() -> list[dict]:
    """Return descriptive baselines without implying package acquisition or validation."""
    return [dict(_US_CORE_BASELINE)]


def capability_statement() -> dict:
    """Describe only behavior actually implemented by this first kernel slice."""
    return {
        "resourceType": "CapabilityStatement",
        "id": "open-intelligence-h1-fhir",
        "name": "OpenIntelligenceH1FhirCapability",
        "title": "Open Intelligence H1 FHIR interoperability boundary",
        "status": "active",
        "experimental": True,
        "date": "2026-11-04",
        "kind": "instance",
        "software": {"name": "Open Intelligence H1"},
        "implementation": {
            "description": (
                "Metadata and bounded source admission only; no FHIR resource REST "
                "interactions are implemented or advertised by this slice."
            )
        },
        "fhirVersion": FHIR_R4,
        "format": ["json"],
        "rest": [{
            "mode": "server",
            "documentation": (
                "Metadata only: no FHIR resource REST interactions are advertised. "
                "FHIR JSON may be admitted internally as an unreviewed versioned source "
                "after current Open Intelligence authorization in a later patient-scoped adapter."
            ),
            "resource": [],
        }],
    }


def _pairs(pairs):
    value = {}
    for key, item in pairs:
        if key in value:
            raise FhirRejected("duplicate JSON member")
        value[key] = item
    return value


def _bounded_tree(value, depth: int = 0, nodes: list[int] | None = None) -> None:
    if depth > MAX_DEPTH:
        raise FhirRejected("FHIR JSON depth exceeds bound")
    if nodes is None:
        nodes = [0]
    nodes[0] += 1
    if nodes[0] > 8192:
        raise FhirRejected("FHIR JSON structure exceeds bound")
    if type(value) is dict:
        for key, item in value.items():
            if type(key) is not str:
                raise FhirRejected("FHIR JSON object key must be text")
            _bounded_tree(item, depth + 1, nodes)
    elif type(value) is list:
        for item in value:
            _bounded_tree(item, depth + 1, nodes)
    elif value is not None and type(value) not in (str, int, float, bool):
        raise FhirRejected("Unsupported FHIR JSON value")


def _visible(value: object, name: str, *, maximum: int = 512) -> str:
    if type(value) is not str or not value or len(value) > maximum:
        raise FhirRejected(f"Invalid {name}")
    if any(ord(char) < 0x20 or ord(char) == 0x7F for char in value):
        raise FhirRejected(f"Invalid {name}")
    return value


def _profiles(resource: dict) -> list[str]:
    meta = resource.get("meta")
    if meta is None:
        return []
    if type(meta) is not dict:
        raise FhirRejected("Invalid FHIR profiles")
    values = meta.get("profile", [])
    if type(values) is not list or len(values) > MAX_PROFILES:
        raise FhirRejected("Invalid FHIR profiles")
    result = []
    for value in values:
        result.append(_visible(value, "FHIR profiles", maximum=512))
    if len(set(result)) != len(result):
        raise FhirRejected("Duplicate FHIR profiles")
    return result


def _classification(resource_type: str) -> str:
    if resource_type == "Patient":
        return "administrative_source"
    if resource_type in ("Observation", "DiagnosticReport"):
        return "clinical_source"
    if resource_type == "Provenance":
        return "provenance"
    return "security_audit"


def admit_fhir_json(
    raw: bytes,
    *,
    source_system: str,
    issuer: str,
    package_id: str | None = None,
    package_version: str | None = None,
    fhir_version: str = FHIR_R4,
) -> dict:
    """Validate bounded JSON transport and return a source-only admission envelope.

    The caller remains responsible for current authorization, patient/case binding,
    durable original-byte storage and profile/terminology validation. This function
    deliberately returns no canonical patient identifier or clinical assertion.
    """
    if type(raw) is not bytes or not 1 <= len(raw) <= MAX_RESOURCE_BYTES:
        raise FhirRejected("FHIR JSON source exceeds byte bound")
    if raw.startswith(b"\xef\xbb\xbf"):
        raise FhirRejected("FHIR JSON must be UTF-8 without BOM")
    try:
        text = raw.decode("utf-8", errors="strict")
    except UnicodeDecodeError:
        raise FhirRejected("FHIR JSON must be valid UTF-8") from None
    try:
        resource = json.loads(text, object_pairs_hook=_pairs)
    except FhirRejected:
        raise
    except (json.JSONDecodeError, RecursionError, ValueError, TypeError):
        raise FhirRejected("Invalid FHIR JSON") from None
    if type(resource) is not dict:
        raise FhirRejected("FHIR JSON root must be an object")
    _bounded_tree(resource)

    resource_type = resource.get("resourceType")
    if type(resource_type) is not str or resource_type not in _SUPPORTED:
        raise FhirRejected("Unsupported FHIR resource type")
    logical_id = resource.get("id")
    if logical_id is not None and (type(logical_id) is not str or _ID.fullmatch(logical_id) is None):
        raise FhirRejected("Invalid FHIR logical id")
    profiles = _profiles(resource)

    source_system = _visible(source_system, "source system", maximum=256)
    issuer = _visible(issuer, "issuer", maximum=512)
    if fhir_version != FHIR_R4:
        raise FhirRejected("Unsupported FHIR version")
    if (package_id is None) != (package_version is None):
        raise FhirRejected("Incomplete FHIR package identity")

    package = None
    if package_id is not None:
        package_id = _visible(package_id, "package id", maximum=128)
        package_version = _visible(package_version, "package version", maximum=64)
        exact_baseline = (
            package_id == _US_CORE_BASELINE["package_id"]
            and package_version == _US_CORE_BASELINE["version"]
            and fhir_version == _US_CORE_BASELINE["fhir_version"]
        )
        package = {
            "package_id": package_id,
            "version": package_version,
            "fhir_version": fhir_version,
            "state": "declared_not_loaded" if exact_baseline else "unresolved",
        }

    return {
        "contract": "oi.fhir-source-envelope/1",
        "fhir_version": fhir_version,
        "resource_type": resource_type,
        "logical_id": logical_id,
        "classification": _classification(resource_type),
        "source_identity": {"source_system": source_system, "issuer": issuer},
        "profiles": profiles,
        "package": package,
        "profile_validation": "not_performed",
        "terminology_validation": "not_performed",
        "original_sha256": hashlib.sha256(raw).hexdigest(),
        "original_size": len(raw),
        "original_json": text,
        "normalized_resource": resource,
        "interpretation_state": "source_only_unreviewed",
        "clinical_interpretation": False,
    }
