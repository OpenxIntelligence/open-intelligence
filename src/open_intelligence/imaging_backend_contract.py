"""DICOMweb metadata acceptance contract against the existing fictional source ledger.

This is a vendor-neutral *test boundary*, not a PACS, DICOM decoder, viewer,
live QIDO/WADO/STOW service, medical image analyzer, or patient authentication.
No external network, storage or source changes are performed.

Input rows imitate the DICOMweb metadata JSON structure, with an explicit,
out-of-band fictional report-source binding supplied by the test adapter.
A DICOM PatientName/PatientID field is never treated as case authorization.
"""
from __future__ import annotations

from datetime import date
import re

from .store import CaseStore, InvalidInput

_UID = re.compile(r"(?:0|[1-9][0-9]*)(?:\.(?:0|[1-9][0-9]*))*\Z")
_MAX_ROWS = 256
# Each tag is validated independently, including DICOM VR and one value.
_TAGS = {
    "0020000D": "UI",  # StudyInstanceUID
    "0020000E": "UI",  # SeriesInstanceUID
    "00080018": "UI",  # SOPInstanceUID
    "00080020": "DA",  # StudyDate
    "00080060": "CS",  # Modality
}
_MODALITIES = frozenset({"CT", "MR", "PT", "US", "DX", "CR", "NM"})


def _field(metadata: dict, key: str) -> str:
    row = metadata.get(key)
    if not isinstance(row, dict) or row.get("vr") != _TAGS[key]:
        raise InvalidInput("Required typed DICOMweb metadata field missing")
    values = row.get("Value")
    if (not isinstance(values, list) or len(values) != 1
            or not isinstance(values[0], str) or not values[0]):
        raise InvalidInput("DICOMweb field must contain one nonempty string")
    return values[0]


def _uid(value: str) -> str:
    if len(value) > 64 or _UID.fullmatch(value) is None:
        raise InvalidInput("Invalid DICOM UID")
    return value


def _date(value: str) -> str:
    if not re.fullmatch(r"[0-9]{8}", value):
        raise InvalidInput("Invalid DICOM StudyDate")
    try:
        date(int(value[:4]), int(value[4:6]), int(value[6:8]))
    except ValueError:
        raise InvalidInput("Invalid DICOM StudyDate") from None
    return value


def check_dicomweb_metadata(store: CaseStore, case_id: str,
                            rows: list[dict]) -> dict:
    """Return a deterministic evidence-bound candidate-backend test receipt.

    The adapter must supply an explicit synthetic case and report-source
    binding. This deliberately refuses mismatched dates for manual
    reconciliation; it does not claim acquisition and report dates are
    necessarily identical in real clinical workflows.
    """
    state = store.state(case_id)
    if not isinstance(rows, list) or len(rows) > _MAX_ROWS:
        raise InvalidInput("Bounded list of synthetic DICOMweb metadata required")
    current = {s["id"]: s for s in state["sources"]
               if s["kind"] == "imaging" and s["state"] == "current"}
    seen = set()
    study_metadata = {}
    series_metadata = {}
    instances = []
    for row in rows:
        if not isinstance(row, dict):
            raise InvalidInput("DICOMweb metadata row must be an object")
        if row.get("oi_test_case_id") != case_id:
            raise InvalidInput("DICOM metadata is not bound to selected case")
        source_id = row.get("oi_test_source_version_id")
        if type(source_id) is not int or source_id not in current:
            raise InvalidInput("Missing or superseded same-case imaging report")
        source = current[source_id]

        uid_study = _uid(_field(row, "0020000D"))
        uid_series = _uid(_field(row, "0020000E"))
        uid_instance = _uid(_field(row, "00080018"))
        acquired = _date(_field(row, "00080020"))
        modality = _field(row, "00080060")
        if modality not in _MODALITIES:
            raise InvalidInput("Unsupported modality requires review")
        if acquired != source["event_date"].replace("-", ""):
            raise InvalidInput("StudyDate and source event date need reconciliation")

        identity = (uid_study, uid_series, uid_instance)
        if identity in seen:
            raise InvalidInput("Duplicate SOPInstanceUID not silently collapsed")
        seen.add(identity)
        if uid_series in series_metadata and series_metadata[uid_series] != uid_study:
            raise InvalidInput("SeriesInstanceUID reused under different studies")
        series_metadata[uid_series] = uid_study
        descriptor = (acquired, source_id, case_id)
        if uid_study in study_metadata and study_metadata[uid_study] != descriptor:
            raise InvalidInput("Study identity disagrees on date or source binding")
        study_metadata[uid_study] = descriptor

        instances.append({
            "study_uid": uid_study,
            "series_uid": uid_series,
            "sop_uid": uid_instance,
            "modality": modality,
            "study_date": acquired,
            "source_version_id": source_id,
            "source_document": source["document_id"],
            "source_version": source["version"],
            "source_sha256": source["sha256"],
            "source_event_date": source["event_date"],
            "source_issued_at": source["issued_at"],
            "source_received_at": source["received_at"],
            "source_specimen_id": source["specimen_id"],
            "patient_case_id": case_id,
        })

    instances.sort(key=lambda r: (r["study_uid"], r["series_uid"], r["sop_uid"]))
    return {
        "case_id": case_id,
        "status": "synthetic_metadata_contract_checked",
        "instances": instances,
        "study_count": len(study_metadata),
        "series_count": len(series_metadata),
        "instance_count": len(instances),
        "empty_input_state": "not_provided" if not rows else None,
        "qido_rs_network_executed": False,
        "wado_rs_object_retrieved": False,
        "stow_rs_object_stored": False,
        "pixel_data_processed": False,
        "clinical_review_state": "not_performed",
        "disclaimer": (
            "Only fictional source-bound DICOMweb-style metadata was validated. "
            "No real imaging files, PACS, clinical interpretation, authorization, "
            "or DICOMweb network operation is established."
        ),
    }
