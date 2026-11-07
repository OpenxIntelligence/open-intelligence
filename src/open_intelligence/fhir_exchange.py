"""FHIR R4 exchange for the data-integration dimension (program plan slice D2).

Synthetic exchange endpoints with pinned fixtures — no live-system
connection, no real patient data, no clinical claim. A bundle round-trips
through the routes: the export builds a FHIR R4 Bundle from the case's
current assertions and source versions (with terminology codings attached
where the pinned table binds them), and the import validates an inbound
bundle, translates its Observations and Conditions into anchored findings,
and stores the original bundle bytes as a source version through the one
import path (``CaseStore.import_fhir_bundle``), so the A1 anchor checker,
the amendment rules, and the snapshot-invalidation cascade all apply
exactly as they do to report imports.

The synthetic bundle contract (pinned; anything outside it is rejected
with a typed reason, never silently accepted):

* ``Bundle`` of ``type`` ``collection``; ``id`` is the document id
  (``valid_id``); ``meta.lastUpdated`` is the issue date; ``meta.versionId``
  is the bundle version — ``"1"`` (or absent) for a first import, ``N``
  for an amendment of version ``N - 1`` (genuine FHIR version semantics,
  mapped onto the ledger's ``Amends`` rule). ``meta.profile`` is never
  accepted: a profile is a conformance claim this slice cannot verify.
* Exactly one ``Patient``; every ``subject`` reference is
  ``Patient/<that id>``. The patient id is the case id; a bundle for
  another case is quarantined as ``patient_mismatch`` by the import path.
* ``Observation`` and ``Condition`` are the finding carriers. Each
  carries ``text.div`` — the verbatim narrative the assertion quotes —
  and ``code.text`` (a human label). The ledger finding key is derived
  from the resource id (``fhir-observation-<slug>`` /
  ``fhir-condition-<slug>``), so keys are unique per resource and the
  translation is explicit about re-keying: the exchange does not
  preserve the ledger's finding keys, and the delivery's loss receipt
  records that. Certainty travels in the synthetic extension
  ``https://example.invalid/oi-synthetic/certainty`` (``valueCode`` in
  the ledger's STATES); without it, the resource status maps
  deterministically (final -> reported, preliminary -> pending,
  unknown -> indeterminate, cancelled -> not-reported).
* ``DiagnosticReport`` is structural: it must reference only
  Observations present in the same bundle and carries no finding.
* Codings are validated through an injected ``validate_coding``
  callable (the terminology module's, passed by the store — the
  dimension modules must not import each other, per the orthogonality
  rule; injection is the seam). Unknown codes, unknown systems, and
  SNOMED CT codings are all rejected.
* ``source_line`` for an assertion is the line number of the
  resource's ``"id"`` line in the canonical bundle bytes (the route
  canonicalizes with ``json.dumps(..., indent=2, sort_keys=True)``),
  so the anchor is exact. A resource whose id line cannot be found is
  rejected, never guessed.
* Field-level loss is computed, not assumed: every field outside the
  consumed-field allowlist below is reported as dropped (dotted path),
  and the adapter delivery must declare exactly that set in its
  transformation receipt.

mCODE: the exchange machinery is FHIR R4; mCODE conformance is NOT
claimed in this slice. The mCODE profiles bind condition codes to
SNOMED CT, which is license-blocked here, and this slice validates no
IG. ``MCODE_PROFILES`` records the profiles and their status; the
export never sets ``meta.profile`` to one, and the import rejects any
bundle that claims one (``mcode_profile_unverified``). Claiming mCODE
conformance is future work, pending terminology licensing and IG
validation — not a line to fake now.
"""
from __future__ import annotations

import html
import json
import re
from xml.sax.saxutils import escape as xml_escape

from .store import (
    MAX_SOURCE_BYTES,
    STATES,
    Finding,
    InvalidInput,
    ParsedReport,
    today_utc,
    valid_date,
    valid_id,
)
from .vertical import default_vertical

CERTAINTY_EXTENSION_URL = "https://example.invalid/oi-synthetic/certainty"

# mCODE 4.0 profiles relevant to this exchange. Status is "not_claimed"
# for every one: no mCODE conformance is claimed or verified in D2.
MCODE_PROFILES = {
    "http://hl7.org/fhir/us/mcode/StructureDefinition/mcode-cancer-condition": {
        "name": "mCODE Cancer Condition",
        "status": "not_claimed",
        "reason": "Binds condition codes to SNOMED CT (license-blocked here); no IG validation in this slice.",
    },
    "http://hl7.org/fhir/us/mcode/StructureDefinition/mcode-cancer-disease-status": {
        "name": "mCODE Cancer Disease Status",
        "status": "not_claimed",
        "reason": "Binds condition codes to SNOMED CT (license-blocked here); no IG validation in this slice.",
    },
    "http://hl7.org/fhir/us/mcode/StructureDefinition/mcode-tumor-marker": {
        "name": "mCODE Tumor Marker",
        "status": "not_claimed",
        "reason": "Binds observation codes to LOINC/SNOMED CT; no IG validation in this slice.",
    },
}

# FHIR Observation.status -> ledger certainty, used only when the
# synthetic certainty extension is absent.
OBSERVATION_STATUS_CERTAINTY = {
    "final": "reported",
    "amended": "reported",
    "corrected": "reported",
    "preliminary": "pending",
    "registered": "pending",
    "unknown": "indeterminate",
    "cancelled": "not-reported",
}

# FHIR Condition.verificationStatus -> ledger certainty.
CONDITION_VERIFICATION_CERTAINTY = {
    "confirmed": "reported",
    "unconfirmed": "indeterminate",
    "refuted": "negative",
    "provisional": "pending",
    "differential": "pending",
}

# Ledger certainty -> FHIR Observation.status on export. The certainty
# extension always carries the exact value as well, so the round-trip
# is exact even where the status map is lossy.
CERTAINTY_OBSERVATION_STATUS = {
    "reported": "final",
    "negative": "final",
    "pending": "preliminary",
    "indeterminate": "unknown",
    "not-reported": "cancelled",
    "not-assessed": "unknown",
    "conflicting": "unknown",
}

_BUNDLE_ID_RE = re.compile(r"[A-Z][A-Z0-9-]{1,39}\Z")
_RESOURCE_ID_RE = re.compile(r"[A-Za-z0-9][A-Za-z0-9\-]{0,63}\Z")
_SLUG_RE = re.compile(r"[^a-z0-9]+")


def mcode_status() -> dict:
    """The mCODE position for the exchange response envelope: not claimed."""
    return {
        "status": "not_claimed",
        "reason": (
            "mCODE profiles bind condition codes to SNOMED CT, which is "
            "license-blocked in this slice, and no implementation-guide "
            "validation exists here; no mCODE conformance is claimed."
        ),
        "profiles": {
            url: {"name": info["name"], "status": info["status"],
                  "reason": info["reason"]}
            for url, info in MCODE_PROFILES.items()
        },
    }


def _is_mcode_profile(url: str) -> bool:
    return "/mcode/" in url or url in MCODE_PROFILES


def _check_no_profile(meta, where: str) -> None:
    """Any meta.profile is a conformance claim this slice cannot verify."""
    if not isinstance(meta, dict):
        return
    profiles = meta.get("profile")
    if profiles is None:
        return
    if not isinstance(profiles, list) or not profiles:
        raise InvalidInput(f"fhir_invalid_profile at {where}")
    for url in profiles:
        if not isinstance(url, str):
            raise InvalidInput(f"fhir_invalid_profile at {where}")
        if _is_mcode_profile(url):
            raise InvalidInput(
                "mcode_profile_unverified: this slice claims no mCODE conformance")
        raise InvalidInput(
            f"fhir_profile_claim_unverified: {url} at {where}")


def _bundle_date(value, where: str) -> str:
    """A FHIR date or dateTime, reduced to its YYYY-MM-DD date part."""
    if not isinstance(value, str) or not value:
        raise InvalidInput(f"fhir_invalid_date at {where}")
    date_part = value.split("T", 1)[0]
    try:
        return valid_date(date_part)
    except InvalidInput:
        raise InvalidInput(f"fhir_invalid_date at {where}") from None


def _narrative(resource: dict, where: str) -> str:
    """The verbatim narrative text of a resource: the assertion's quote."""
    text = resource.get("text")
    if not isinstance(text, dict) or not isinstance(text.get("div"), str):
        raise InvalidInput(f"fhir_missing_narrative at {where}")
    div = text["div"]
    start = div.find(">")
    end = div.rfind("</div>")
    if start < 0 or end < 0 or end <= start:
        raise InvalidInput(f"fhir_malformed_narrative at {where}")
    quote = html.unescape(div[start + 1:end]).strip()
    if not quote:
        raise InvalidInput(f"fhir_empty_narrative at {where}")
    if len(quote) > 1200:
        raise InvalidInput(f"fhir_quote_too_long at {where}")
    return quote


def _div(quote: str) -> dict:
    return {"status": "generated",
            "div": '<div xmlns="http://www.w3.org/1999/xhtml">'
                   + xml_escape(quote) + "</div>"}


def _slug(resource_id: str) -> str:
    slug = _SLUG_RE.sub("-", resource_id.lower()).strip("-")
    if not slug:
        raise InvalidInput(f"fhir_invalid_resource_id: {resource_id!r}")
    return slug


def _finding_key(resource_type: str, resource_id: str) -> str:
    key = f"fhir-{resource_type.lower()}-{_slug(resource_id)}"
    if len(key) > 59:
        raise InvalidInput(f"fhir_finding_key_too_long: {key}")
    return key


def _certainty_extension(resource: dict, where: str) -> str | None:
    """The synthetic certainty extension, if present (at most one)."""
    found = None
    for entry in resource.get("extension") or []:
        if not isinstance(entry, dict):
            raise InvalidInput(f"fhir_malformed_extension at {where}")
        if entry.get("url") == CERTAINTY_EXTENSION_URL:
            if found is not None:
                raise InvalidInput(f"fhir_duplicate_certainty at {where}")
            value = entry.get("valueCode")
            if value not in STATES:
                raise InvalidInput(f"fhir_invalid_certainty at {where}")
            found = value
    return found


# Consumed-field allowlist, as nested specs keyed by dotted path. Any
# field outside the allowlist is reported as dropped (never silently
# ignored), and the adapter delivery must declare exactly that set.
_CONSUMED = {
    "Bundle": {"resourceType", "id", "meta", "type", "entry"},
    "Bundle.meta": {"versionId", "lastUpdated"},
    "entry": {"resource", "fullUrl"},
    "Patient": {"resourceType", "id", "text"},
    "Observation": {"resourceType", "id", "status", "code", "subject",
                    "effectiveDateTime", "valueString", "text", "specimen",
                    "extension"},
    "Observation.code": {"coding", "text"},
    "Observation.coding": {"system", "code", "display"},
    "Observation.subject": {"reference"},
    "Observation.specimen": {"reference"},
    "Observation.extension": {"url", "valueCode"},
    "DiagnosticReport": {"resourceType", "id", "status", "code", "subject",
                         "effectiveDateTime", "issued", "result", "text"},
    "DiagnosticReport.code": {"coding", "text"},
    "DiagnosticReport.coding": {"system", "code", "display"},
    "DiagnosticReport.subject": {"reference"},
    "DiagnosticReport.result": {"reference"},
    "Condition": {"resourceType", "id", "clinicalStatus",
                  "verificationStatus", "code", "subject", "onsetDateTime",
                  "text", "note", "extension"},
    "Condition.code": {"coding", "text"},
    "Condition.coding": {"system", "code", "display"},
    "Condition.subject": {"reference"},
    "Condition.clinicalStatus": {"coding"},
    "Condition.clinicalStatus.coding": {"system", "code", "display"},
    "Condition.verificationStatus": {"coding"},
    "Condition.verificationStatus.coding": {"system", "code", "display"},
    "Condition.note": {"text"},
    "Condition.extension": {"url", "valueCode"},
}


def _dropped_fields(obj, spec_path: str, out: set[str]) -> None:
    """Collect dotted paths of fields outside the consumed allowlist.

    ``entry`` and ``resource`` are structural pivots, not dotted paths:
    an entry is walked under the ``entry`` spec and its resource under
    the resource type's spec, so ``entry.request`` and
    ``Observation.performer`` are both reported.
    """
    if isinstance(obj, dict):
        allowed = _CONSUMED.get(spec_path)
        if allowed is None:
            return
        for key, value in obj.items():
            if key not in allowed:
                out.add(f"{spec_path}.{key}")
                continue
            if key == "entry" and isinstance(value, list):
                for item in value:
                    _dropped_fields(item, "entry", out)
                continue
            if key == "resource" and isinstance(value, dict) \
                    and isinstance(value.get("resourceType"), str):
                _dropped_fields(value, value["resourceType"], out)
                continue
            child_path = f"{spec_path}.{key}"
            if child_path in _CONSUMED:
                _dropped_fields(value, child_path, out)
            elif isinstance(value, list):
                for item in value:
                    _dropped_fields(item, child_path, out)
    elif isinstance(obj, list):
        for item in obj:
            _dropped_fields(item, spec_path, out)


def _resource_line(lines: list[str], resource_id: str, where: str) -> int:
    """1-based line number of the resource's own `"id"` line.

    IDs may repeat between resource types. A line belongs to this
    specific entry.resource object only when its own resourceType also
    matches. Do not take the first matching id in the entire bundle.
    """
    needle = f'"id": "{resource_id}"'
    expected_type = where.split("/", 1)[0]
    for index, line in enumerate(lines, start=1):
        if not line.strip().startswith(needle):
            continue
        indentation = len(line) - len(line.lstrip(" "))
        # Locate the containing entry.resource object, not another resource
        # type with the same id or an unrelated nested `id` field.
        parent_index = None
        for prior in range(index - 2, -1, -1):
            candidate = lines[prior]
            margin = len(candidate) - len(candidate.lstrip(" "))
            if margin < indentation:
                if candidate.strip() == '"resource": {':
                    parent_index = prior
                break
        if parent_index is None:
            continue
        margin = len(lines[parent_index]) - len(lines[parent_index].lstrip(" "))
        for candidate in lines[parent_index + 1:]:
            depth = len(candidate) - len(candidate.lstrip(" "))
            if depth <= margin:
                break
            if (depth == indentation and
                    candidate.strip().startswith(
                        f'"resourceType": "{expected_type}"')):
                return index
    raise InvalidInput(f"fhir_unanchored_resource at {where}")


def fhir_bundle_to_report(raw: bytes, *, validate_coding,
                          vertical=None) -> tuple[ParsedReport, tuple[str, ...]]:
    """Validate a synthetic FHIR bundle and translate it into a ledger report.

    Returns ``(ParsedReport, dropped_fields)``. ``validate_coding`` is
    the terminology validator (injected by the caller — dimension
    modules must not import each other). ``vertical`` is the case's
    vertical (the pre-V2 default when omitted); its terminology
    bindings are part of the validation. Raises ``InvalidInput`` with a
    typed reason for anything outside the pinned contract.
    """
    if validate_coding is None:
        raise InvalidInput("a terminology validator is required for FHIR import")
    if vertical is None:
        vertical = default_vertical()
    if not isinstance(raw, bytes) or not raw or len(raw) > MAX_SOURCE_BYTES:
        raise InvalidInput("FHIR bundle must be nonempty UTF-8, at most 64 KiB")
    try:
        text = raw.decode("utf-8", errors="strict")
    except UnicodeDecodeError:
        raise InvalidInput("FHIR bundle must be UTF-8") from None
    if "\x00" in text:
        raise InvalidInput("FHIR bundle must not contain NUL characters")
    try:
        bundle = json.loads(text)
    except json.JSONDecodeError:
        raise InvalidInput("fhir_invalid_json") from None
    if not isinstance(bundle, dict):
        raise InvalidInput("fhir_bundle_must_be_an_object")
    if bundle.get("resourceType") != "Bundle":
        raise InvalidInput("fhir_not_a_bundle")
    if bundle.get("type") != "collection":
        raise InvalidInput("fhir_unsupported_bundle_type")
    document_id = bundle.get("id")
    if not isinstance(document_id, str) or not _BUNDLE_ID_RE.fullmatch(document_id):
        raise InvalidInput("fhir_invalid_bundle_id")
    meta = bundle.get("meta")
    if not isinstance(meta, dict):
        raise InvalidInput("fhir_missing_meta")
    _check_no_profile(meta, "Bundle.meta")
    issued_at = _bundle_date(meta.get("lastUpdated"), "Bundle.meta.lastUpdated")
    version_raw = meta.get("versionId", "1")
    if not isinstance(version_raw, str) or not version_raw.isdigit() \
            or int(version_raw) < 1:
        raise InvalidInput("fhir_invalid_version")
    version = int(version_raw)
    amends = (document_id, version - 1) if version > 1 else None
    entries = bundle.get("entry")
    if not isinstance(entries, list) or not entries:
        raise InvalidInput("fhir_bundle_requires_entries")

    lines = text.splitlines()
    patients: list[dict] = []
    observations: list[dict] = []
    reports: list[dict] = []
    conditions: list[dict] = []
    seen_ids: dict[str, str] = {}
    for position, entry in enumerate(entries):
        where = f"entry[{position}]"
        if not isinstance(entry, dict):
            raise InvalidInput(f"fhir_malformed_entry at {where}")
        resource = entry.get("resource")
        if not isinstance(resource, dict):
            raise InvalidInput(f"fhir_malformed_entry at {where}")
        full_url = entry.get("fullUrl")
        resource_type = resource.get("resourceType")
        if not isinstance(resource_type, str) \
                or resource_type not in ("Patient", "Observation",
                                        "DiagnosticReport", "Condition"):
            raise InvalidInput(f"fhir_unsupported_resource at {where}")
        resource_id = resource.get("id")
        if not isinstance(resource_id, str) \
                or not _RESOURCE_ID_RE.fullmatch(resource_id):
            raise InvalidInput(f"fhir_invalid_resource_id at {where}")
        if full_url != f"{resource_type}/{resource_id}":
            raise InvalidInput(f"fhir_fullurl_mismatch at {where}")
        key = f"{resource_type}/{resource_id}"
        if key in seen_ids:
            raise InvalidInput(f"fhir_duplicate_resource_id at {where}")
        seen_ids[key] = resource_type
        _check_no_profile(resource.get("meta"), f"{where}.meta")
        if resource_type == "Patient":
            patients.append(resource)
        elif resource_type == "Observation":
            observations.append(resource)
        elif resource_type == "DiagnosticReport":
            reports.append(resource)
        else:
            conditions.append(resource)
    if len(patients) != 1:
        raise InvalidInput("fhir_bundle_requires_exactly_one_patient")
    patient = patients[0]
    try:
        patient_id = valid_id(patient.get("id"))
    except InvalidInput:
        raise InvalidInput("fhir_invalid_patient_id") from None
    if not observations and not conditions:
        raise InvalidInput("fhir_no_exchangeable_resources")

    dropped: set[str] = set()
    _dropped_fields(bundle, "Bundle", dropped)

    findings: list[Finding] = []
    event_dates: list[str] = []
    specimen_ids: set[str] = set()
    used_keys: set[str] = set()

    def check_subject(resource: dict, where: str) -> None:
        subject = resource.get("subject")
        if not isinstance(subject, dict) \
                or subject.get("reference") != f"Patient/{patient_id}":
            raise InvalidInput(f"fhir_subject_mismatch at {where}")

    def check_codings(resource: dict, where: str) -> None:
        # A CodeableConcept may carry text only (FHIR allows a coding
        # list of zero); the export emits exactly that for unbound
        # findings. Every coding present is validated against the
        # pinned table — unknown, unlicensed, or blocked systems fail.
        code = resource.get("code")
        if not isinstance(code, dict) or not isinstance(code.get("text"), str) \
                or not code["text"].strip():
            raise InvalidInput(f"fhir_missing_code at {where}")
        codings = code.get("coding") or []
        if not isinstance(codings, list):
            raise InvalidInput(f"fhir_malformed_coding at {where}")
        for coding in codings:
            if not isinstance(coding, dict):
                raise InvalidInput(f"fhir_malformed_coding at {where}")
            validate_coding(coding.get("system"), coding.get("code"), vertical)

    for resource in observations:
        where = f"Observation/{resource['id']}"
        check_subject(resource, where)
        check_codings(resource, where)
        status = resource.get("status")
        if status == "entered-in-error":
            raise InvalidInput(f"fhir_entered_in_error at {where}")
        certainty = _certainty_extension(resource, where)
        if certainty is None:
            if status not in OBSERVATION_STATUS_CERTAINTY:
                raise InvalidInput(f"fhir_unknown_status at {where}")
            certainty = OBSERVATION_STATUS_CERTAINTY[status]
        quote = _narrative(resource, where)
        key = _finding_key("Observation", resource["id"])
        if key in used_keys:
            raise InvalidInput(f"fhir_duplicate_finding_key at {where}")
        used_keys.add(key)
        line = _resource_line(lines, resource["id"], where)
        findings.append(Finding(key, certainty, quote, line))
        effective = resource.get("effectiveDateTime")
        if effective is not None:
            event_dates.append(_bundle_date(effective, f"{where}.effectiveDateTime"))
        specimen = resource.get("specimen")
        if specimen is not None:
            if not isinstance(specimen, dict):
                raise InvalidInput(f"fhir_malformed_specimen at {where}")
            reference = specimen.get("reference")
            if not isinstance(reference, str) or not reference.startswith("Specimen/"):
                raise InvalidInput(f"fhir_malformed_specimen at {where}")
            specimen_ids.add(reference[len("Specimen/"):])
        if resource.get("valueString") is not None:
            if not isinstance(resource["valueString"], str) \
                    or resource["valueString"].strip() != quote:
                raise InvalidInput(f"fhir_value_narrative_mismatch at {where}")

    for resource in conditions:
        where = f"Condition/{resource['id']}"
        check_subject(resource, where)
        check_codings(resource, where)
        # A Condition is only exchanged when it carries a coding: it is
        # the coded clinical statement, not a bare label.
        if not resource["code"].get("coding"):
            raise InvalidInput(f"fhir_missing_code at {where}")
        verification = resource.get("verificationStatus")
        if not isinstance(verification, dict):
            raise InvalidInput(f"fhir_missing_verification_status at {where}")
        codings = verification.get("coding")
        if not isinstance(codings, list) or not codings \
                or not isinstance(codings[0], dict):
            raise InvalidInput(f"fhir_missing_verification_status at {where}")
        status_code = codings[0].get("code")
        if status_code == "entered-in-error":
            raise InvalidInput(f"fhir_entered_in_error at {where}")
        certainty = _certainty_extension(resource, where)
        if certainty is None:
            if status_code not in CONDITION_VERIFICATION_CERTAINTY:
                raise InvalidInput(f"fhir_unknown_verification_status at {where}")
            certainty = CONDITION_VERIFICATION_CERTAINTY[status_code]
        quote = _narrative(resource, where)
        key = _finding_key("Condition", resource["id"])
        if key in used_keys:
            raise InvalidInput(f"fhir_duplicate_finding_key at {where}")
        used_keys.add(key)
        line = _resource_line(lines, resource["id"], where)
        findings.append(Finding(key, certainty, quote, line))
        onset = resource.get("onsetDateTime")
        if onset is not None:
            event_dates.append(_bundle_date(onset, f"{where}.onsetDateTime"))

    for resource in reports:
        where = f"DiagnosticReport/{resource['id']}"
        check_subject(resource, where)
        code = resource.get("code")
        if not isinstance(code, dict) \
                or (not code.get("coding") and not code.get("text")):
            raise InvalidInput(f"fhir_missing_code at {where}")
        for coding in code.get("coding") or []:
            if not isinstance(coding, dict):
                raise InvalidInput(f"fhir_malformed_coding at {where}")
            validate_coding(coding.get("system"), coding.get("code"), vertical)
        for reference in resource.get("result") or []:
            if not isinstance(reference, dict) \
                    or not isinstance(reference.get("reference"), str) \
                    or reference["reference"] not in seen_ids \
                    or not reference["reference"].startswith("Observation/"):
                raise InvalidInput(f"fhir_dangling_reference at {where}")
        effective = resource.get("effectiveDateTime")
        if effective is not None:
            event_dates.append(_bundle_date(effective, f"{where}.effectiveDateTime"))

    if not event_dates:
        raise InvalidInput("fhir_missing_dates")
    event_date = min(event_dates)
    if event_date > issued_at:
        raise InvalidInput("fhir_date_order: event date after issue date")
    if len(specimen_ids) > 1:
        raise InvalidInput("fhir_mixed_specimens")
    specimen_id = next(iter(specimen_ids)) if specimen_ids else None
    if specimen_id is not None:
        try:
            valid_id(specimen_id)
        except InvalidInput:
            raise InvalidInput("fhir_invalid_specimen_id") from None

    report = ParsedReport(
        patient_id=patient_id, document_id=document_id, kind="fhir-bundle",
        event_date=event_date, issued_at=issued_at, specimen_id=specimen_id,
        amends=amends, findings=tuple(findings), raw=raw)
    return report, tuple(sorted(dropped))


def build_fhir_bundle(state: dict, vertical, *, codings_for) -> dict:
    """Build a FHIR R4 Bundle from a case's current assertions and sources.

    Pure over ``CaseStore.state(case_id)``. One Observation per current
    assertion (status + certainty extension + codings from the
    terminology table), one DiagnosticReport per source that has current
    assertions, one Condition per assertion whose codings include an
    ICD-10 code (verificationStatus unconfirmed — the bundle asserts
    nothing clinically). Findings with no pinned coding are exported
    without a coding and listed under ``unbound_findings``: unbound,
    never fabricated. No ``meta.profile`` is set anywhere — no mCODE
    conformance is claimed.
    """
    if codings_for is None:
        raise InvalidInput("a terminology lookup is required for FHIR export")
    case = state["case"]
    case_id = valid_id(case["case_id"])
    sources = [s for s in state["sources"] if s["state"] == "current"]
    assertions = list(state["assertions"])
    by_source: dict[int, list[dict]] = {}
    for assertion in assertions:
        by_source.setdefault(assertion["source_version_id"], []).append(assertion)
    sources = [s for s in sources if by_source.get(s["id"])]
    if not assertions or not sources:
        raise InvalidInput("fhir_export_requires_current_assertions")

    entries: list[dict] = [{
        "fullUrl": f"Patient/{case_id}",
        "resource": {
            "resourceType": "Patient",
            "id": case_id,
            "text": _div(
                f"Fictional case {case_id} — synthetic demonstration only, "
                "not a real patient."),
        },
    }]
    unbound: list[str] = []
    observation_ids: dict[int, list[str]] = {}
    for assertion in assertions:
        resource_id = f"OBS-{assertion['id']}"
        observation_ids.setdefault(assertion["source_version_id"], []).append(resource_id)
        codings = codings_for(assertion["finding_key"], vertical)
        if not codings:
            unbound.append(assertion["finding_key"])
        source = next(s for s in sources if s["id"] == assertion["source_version_id"])
        observation: dict = {
            "resourceType": "Observation",
            "id": resource_id,
            "status": CERTAINTY_OBSERVATION_STATUS[assertion["certainty"]],
            "code": {
                "coding": [dict(coding) for coding in codings],
                "text": assertion["finding_key"],
            },
            "subject": {"reference": f"Patient/{case_id}"},
            "effectiveDateTime": source["event_date"],
            "valueString": assertion["quote"],
            "text": _div(assertion["quote"]),
            "extension": [{
                "url": CERTAINTY_EXTENSION_URL,
                "valueCode": assertion["certainty"],
            }],
        }
        if source.get("specimen_id"):
            observation["specimen"] = {"reference": f"Specimen/{source['specimen_id']}"}
        entries.append({"fullUrl": f"Observation/{resource_id}",
                        "resource": observation})
        icd10 = [c for c in codings
                 if c["system"] == "http://hl7.org/fhir/sid/icd-10"]
        if icd10:
            condition_id = f"COND-{assertion['id']}"
            entries.append({
                "fullUrl": f"Condition/{condition_id}",
                "resource": {
                    "resourceType": "Condition",
                    "id": condition_id,
                    "clinicalStatus": {"coding": [{
                        "system": "http://terminology.hl7.org/CodeSystem/condition-clinical",
                        "code": "active", "display": "Active"}]},
                    "verificationStatus": {"coding": [{
                        "system": "http://terminology.hl7.org/CodeSystem/condition-ver-status",
                        "code": "unconfirmed", "display": "Unconfirmed"}]},
                    "code": {"coding": [dict(c) for c in icd10],
                             "text": assertion["finding_key"]},
                    "subject": {"reference": f"Patient/{case_id}"},
                    "onsetDateTime": source["event_date"],
                    "text": _div(assertion["quote"]),
                    "note": [{"text": "Synthetic demonstration data — "
                                      "unconfirmed, not a diagnosis."}],
                },
            })
    for source in sources:
        report_id = f"REP-{source['document_id']}"
        entries.append({
            "fullUrl": f"DiagnosticReport/{report_id}",
            "resource": {
                "resourceType": "DiagnosticReport",
                "id": report_id,
                "status": "final",
                "code": {"text": f"{source['kind']} report {source['document_id']}"},
                "subject": {"reference": f"Patient/{case_id}"},
                "effectiveDateTime": source["event_date"],
                "issued": source["issued_at"],
                "result": [{"reference": f"Observation/{oid}"}
                           for oid in observation_ids[source["id"]]],
                "text": _div(
                    f"Source document {source['document_id']}, version "
                    f"{source['version']}, kind {source['kind']}."),
            },
        })
    last_updated = max(s["issued_at"] for s in sources)
    bundle = {
        "resourceType": "Bundle",
        "id": f"OI-BUNDLE-{case_id}-1",
        "meta": {"lastUpdated": last_updated, "versionId": "1"},
        "type": "collection",
        "entry": entries,
    }
    return {
        "bundle": bundle,
        "mcode": mcode_status(),
        "unbound_findings": sorted(set(unbound)),
        "exported_at": today_utc(),
    }
