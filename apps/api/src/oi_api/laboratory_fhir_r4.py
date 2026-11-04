"""Bounded, deterministic FHIR R4 lab *preparation*, not clinical import.

One independent fictional Patient + Specimen + 1..16 final Observations and
an optional final DiagnosticReport may be inspected without mutating any H1
patient/source/PWM ledger. The calling owner supplies a pre-verified, qualified
patient-to-provider subject mapping; this parser never establishes that mapping.

This is a deliberately constrained FHIR R4 subset, not a general FHIR validator.
Unknown clinically meaningful fields are rejected rather than silently dropped.
No network, terminology expansion, unit conversion, model execution, or PHI.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
import hashlib
import json
import re
from typing import Any
from uuid import UUID

MAX_BUNDLE_BYTES = 65_536
MAX_OBSERVATIONS = 16
_ID = re.compile(r"[A-Za-z0-9.-]{1,64}\Z")
_LOINC = re.compile(r"[0-9]{1,6}-[0-9]\Z")
_CONTROL = re.compile(r"[\x00-\x1f\x7f]")
_ALLOWED_ABSENT = frozenset(("unknown", "not-performed", "error", "masked"))
_LAB_CATEGORY = "http://terminology.hl7.org/CodeSystem/observation-category"


class LaboratoryBundleRejected(ValueError):
    """Refuse unsupported or ambiguous source data before any record write."""


def _reject(message: str):
    raise LaboratoryBundleRejected(message)


def _object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            _reject("Duplicate JSON member")
        result[key] = value
    return result


def _finite_constant(_):
    _reject("Nonfinite JSON number")


def _shape(value: Any, required: set[str], optional: set[str] = frozenset()):
    if type(value) is not dict or not required <= value.keys() or value.keys() - required - optional:
        _reject("Missing or unsupported FHIR fields")
    return value


def _identifier(value: Any) -> str:
    if type(value) is not str or not _ID.fullmatch(value):
        _reject("Invalid local FHIR identifier")
    return value


def _reference(value: Any, kind: str) -> str:
    _shape(value, {"reference"})
    reference = value["reference"]
    if type(reference) is not str or not reference.startswith(kind + "/"):
        _reject("External, ambiguous or incorrect FHIR reference")
    _identifier(reference[len(kind) + 1:])
    return reference


def _instant(value: Any) -> str:
    if type(value) is not str or not re.fullmatch(
            r"\d{4}-\d\d-\d\dT\d\d:\d\d:\d\d(?:\.\d{1,6})?(?:Z|[+-]\d\d:\d\d)", value):
        _reject("An explicit offset and second-precision date-time are required")
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        _reject("Invalid FHIR date-time")
    if parsed.utcoffset() is None or abs(parsed.utcoffset().total_seconds()) > 14 * 3600:
        _reject("Invalid date-time offset")
    return value


def _concept(value: Any, system: str | None = None) -> dict:
    _shape(value, {"coding"})
    coding = value["coding"]
    if type(coding) is not list or len(coding) != 1:
        _reject("Exactly one nonambiguous code required")
    code = _shape(coding[0], {"system", "code"})
    if type(code["system"]) is not str or not code["system"]:
        _reject("Missing coding system")
    if type(code["code"]) is not str or not 0 < len(code["code"]) <= 64 or _CONTROL.search(code["code"]):
        _reject("Invalid code")
    if system is not None and code["system"] != system:
        _reject("Unsupported coding system")
    return code


def _lab_category(value: Any) -> None:
    if type(value) is not list or len(value) != 1:
        _reject("A single laboratory category is required")
    code = _concept(value[0], _LAB_CATEGORY)
    if code["code"] != "laboratory":
        _reject("Only laboratory category is supported")


def _full_url(value: Any) -> str:
    if type(value) is not str or not value.startswith("urn:uuid:"):
        _reject("Only local bundle identities are supported")
    try:
        token = UUID(value[len("urn:uuid:"):])
    except (ValueError, AttributeError):
        _reject("Invalid local bundle UUID")
    if str(token) != value[len("urn:uuid:"):]:
        _reject("Noncanonical bundle UUID")
    return value


@dataclass(frozen=True)
class PreparedLaboratoryBundle:
    """Immutable, explicitly *unpersisted* intake candidate."""
    source_sha256: str
    original_bytes: bytes
    subject_reference: str
    specimen_reference: str
    specimen_type_text: str
    specimen_collected_at: str
    observations: tuple[dict, ...]
    report_reference: str | None
    authority: str = "synthetic_source_unreviewed"
    clinical_review: str = "not_performed"
    persisted: bool = False


def prepare_laboratory_bundle(raw: bytes, *, expected_subject_reference: str) -> PreparedLaboratoryBundle:
    """Validate source structure/relations after an independently proven binding.

    The caller must compare expected_subject_reference with its qualified,
    authorized case-binding source subject. Passing a string here is NOT an
    authorization check; the preview is deliberately disconnected from writes.
    """
    if type(raw) is not bytes or not 0 < len(raw) <= MAX_BUNDLE_BYTES:
        _reject("FHIR bundle must be bounded original bytes")
    subject = _reference({"reference": expected_subject_reference}, "Patient")
    try:
        data = json.loads(raw.decode("utf-8", "strict"), parse_float=Decimal,
                          object_pairs_hook=_object, parse_constant=_finite_constant)
    except (UnicodeError, json.JSONDecodeError, RecursionError, OverflowError, ValueError) as exc:
        if isinstance(exc, LaboratoryBundleRejected):
            raise
        _reject("Invalid UTF-8 FHIR JSON")
    _shape(data, {"resourceType", "type", "entry"})
    if data["resourceType"] != "Bundle" or data["type"] != "collection":
        _reject("Only bounded FHIR R4 collection bundles are supported")
    entries = data["entry"]
    if type(entries) is not list or not 3 <= len(entries) <= MAX_OBSERVATIONS + 3:
        _reject("Invalid bundle entry count")
    resources = {}
    full_urls = set()
    for entry in entries:
        _shape(entry, {"fullUrl", "resource"})
        url = _full_url(entry["fullUrl"])
        if url in full_urls:
            _reject("Duplicate bundle identity")
        full_urls.add(url)
        resource = entry["resource"]
        if type(resource) is not dict:
            _reject("Invalid resource")
        kind = resource.get("resourceType")
        if kind not in {"Patient", "Specimen", "Observation", "DiagnosticReport"}:
            _reject("Unsupported FHIR resource")
        identity = kind + "/" + _identifier(resource.get("id"))
        if identity in resources:
            _reject("Conflicting resource identity")
        resources[identity] = resource
    patients = {k: v for k, v in resources.items() if k.startswith("Patient/")}
    specimens = {k: v for k, v in resources.items() if k.startswith("Specimen/")}
    observations = {k: v for k, v in resources.items() if k.startswith("Observation/")}
    reports = {k: v for k, v in resources.items() if k.startswith("DiagnosticReport/")}
    if (len(patients) != 1 or subject not in patients or len(specimens) != 1
            or not 1 <= len(observations) <= MAX_OBSERVATIONS or len(reports) > 1):
        _reject("Bundle patient/specimen/observation scope mismatch")
    _shape(patients[subject], {"resourceType", "id"})
    specimen_ref, specimen = next(iter(specimens.items()))
    _shape(specimen, {"resourceType", "id", "subject", "type", "collection"})
    if _reference(specimen["subject"], "Patient") != subject:
        _reject("Specimen belongs to another patient")
    _shape(specimen["type"], {"text"})
    spec_type = specimen["type"]["text"]
    if type(spec_type) is not str or not 0 < len(spec_type) <= 100 or _CONTROL.search(spec_type):
        _reject("Invalid specimen description")
    _shape(specimen["collection"], {"collectedDateTime"})
    collected = _instant(specimen["collection"]["collectedDateTime"])
    result_rows = []
    for ref, observation in sorted(observations.items()):
        _shape(observation, {"resourceType", "id", "status", "category", "code",
                             "subject", "specimen", "effectiveDateTime", "issued"},
               {"valueQuantity", "dataAbsentReason"})
        if observation["status"] != "final":
            _reject("Non-final or corrected results require separate source review")
        _lab_category(observation["category"])
        code = _concept(observation["code"], "http://loinc.org")
        if not _LOINC.fullmatch(code["code"]):
            _reject("Invalid LOINC code syntax")
        if (_reference(observation["subject"], "Patient") != subject
                or _reference(observation["specimen"], "Specimen") != specimen_ref):
            _reject("Observation patient or specimen mismatch")
        effective = _instant(observation["effectiveDateTime"])
        issued = _instant(observation["issued"])
        has_value = "valueQuantity" in observation
        has_absent = "dataAbsentReason" in observation
        if has_value == has_absent:
            _reject("Result must be a value or an explicit absent reason, never both")
        row = {"reference": ref, "loinc_code": code["code"],
               "effective_at": effective, "issued_at": issued,
               "source_reported": True, "clinical_review": "not_performed"}
        if has_value:
            quantity = _shape(observation["valueQuantity"], {"value", "system", "code"})
            if quantity["system"] != "http://unitsofmeasure.org":
                _reject("Only declared UCUM units supported; no conversion")
            if type(quantity["code"]) is not str or not 0 < len(quantity["code"]) <= 32 or _CONTROL.search(quantity["code"]):
                _reject("Invalid UCUM code")
            number = quantity["value"]
            if type(number) not in (int, Decimal):
                _reject("Result value must be numeric, never a Boolean or text")
            number = Decimal(number)
            if not number.is_finite() or len(number.as_tuple().digits) > 20 or abs(number.as_tuple().exponent) > 12:
                _reject("Result quantity is nonfinite or outside profile bounds")
            row.update(status="reported_value", value_text=format(number, "f"),
                       unit_code=quantity["code"], absent_reason=None)
        else:
            absent = _concept(observation["dataAbsentReason"],
                              "http://terminology.hl7.org/CodeSystem/data-absent-reason")
            if absent["code"] not in _ALLOWED_ABSENT:
                _reject("Unrecognized result-absence reason")
            row.update(status="reported_absent", value_text=None, unit_code=None,
                       absent_reason=absent["code"])
        result_rows.append(row)
    report_ref = None
    if reports:
        report_ref, report = next(iter(reports.items()))
        _shape(report, {"resourceType", "id", "status", "category", "code",
                        "subject", "specimen", "result", "effectiveDateTime", "issued"})
        if report["status"] != "final":
            _reject("Non-final diagnostic report requires review")
        _lab_category(report["category"])
        _concept(report["code"], "http://loinc.org")
        if _reference(report["subject"], "Patient") != subject:
            _reject("Report patient mismatch")
        if (type(report["specimen"]) is not list or len(report["specimen"]) != 1
                or _reference(report["specimen"][0], "Specimen") != specimen_ref):
            _reject("Report specimen mismatch")
        if (type(report["result"]) is not list or len(report["result"]) != len(observations)
                or {_reference(x, "Observation") for x in report["result"]} != set(observations)):
            _reject("Report result references incomplete, duplicated or external")
        _instant(report["effectiveDateTime"])
        _instant(report["issued"])
    return PreparedLaboratoryBundle(
        source_sha256=hashlib.sha256(raw).hexdigest(), original_bytes=raw,
        subject_reference=subject, specimen_reference=specimen_ref,
        specimen_type_text=spec_type, specimen_collected_at=collected,
        observations=tuple(result_rows), report_reference=report_ref,
    )
