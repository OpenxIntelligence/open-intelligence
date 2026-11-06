"""DICOM report-only surface (program plan slice D2).

Imaging reports without pixels: this module records and serves the
*report* of an imaging study — study identifier, modality, accession,
narrative text, and the source version it reports on — and nothing
else. It is report-only by construction:

* The ``dicom_reports`` table has no pixel column and no column that
  could hold pixel bytes; there is no code path that accepts, stores,
  or serves them.
* Any payload containing a pixel field (``PixelData`` and its
  spellings, bulk-data URIs, image arrays) is rejected with the typed
  reason ``dicom_pixels_rejected`` before any record is written.
* A report is a record about a study, not the study itself: no SOP
  instance, no pixel reference, no endpoint is ever emitted.

Modality codes are the standard two-letter DICOM modality codes.
Study identifiers are synthetic (``OI-SYNTHETIC-STUDY-...``); a real
Study Instance UID is never expected here, and no real imaging system
is connected.
"""
from __future__ import annotations

import re

from .store import InvalidInput

# Standard two-letter DICOM modality codes accepted here.
DICOM_MODALITIES = frozenset(
    {"CT", "MR", "US", "XR", "PT", "NM", "MG", "DX", "CR", "OT", "SR", "SC"}
)

STUDY_UID_RE = re.compile(r"OI-SYNTHETIC-STUDY-[A-Z0-9-]{1,32}\Z")
ACCESSION_RE = re.compile(r"[A-Z0-9][A-Z0-9-]{0,31}\Z")

# Field names that mean pixel data, in any spelling this surface might
# meet. Matched case-insensitively against every key of an inbound
# payload, at any depth.
PIXEL_FIELD_NAMES = frozenset({
    "pixeldata", "pixel_data", "pixelarray", "pixel_array",
    "bulkdatauri", "bulk_data_uri", "bulkdata", "bulk_data",
    "image", "imagedata", "image_data", "pixeldata provider",
})


def _reject_pixel_fields(value, path: str = "$") -> None:
    """Recursively reject any pixel field in an inbound payload."""
    if isinstance(value, dict):
        for key, item in value.items():
            if isinstance(key, str) \
                    and key.strip().lower().replace(" ", "") in PIXEL_FIELD_NAMES:
                raise InvalidInput(
                    "dicom_pixels_rejected: the DICOM surface is report-only; "
                    f"pixel data is not accepted (field {path}.{key})")
            _reject_pixel_fields(item, f"{path}.{key}")
    elif isinstance(value, list):
        for index, item in enumerate(value):
            _reject_pixel_fields(item, f"{path}[{index}]")


def validate_dicom_report(payload) -> dict:
    """Validate a DICOM report record; return its normalized fields.

    Raises ``InvalidInput`` with a typed reason for anything outside
    the report-only contract, including any pixel field at any depth.
    """
    if not isinstance(payload, dict):
        raise InvalidInput("dicom_report_must_be_an_object")
    _reject_pixel_fields(payload)
    study_uid = payload.get("study_uid")
    if not isinstance(study_uid, str) or not STUDY_UID_RE.fullmatch(study_uid):
        raise InvalidInput(
            "dicom_invalid_study_uid: expected OI-SYNTHETIC-STUDY-<id>")
    modality = payload.get("modality")
    if modality not in DICOM_MODALITIES:
        raise InvalidInput(f"dicom_unknown_modality: {modality!r}")
    accession = payload.get("accession")
    if not isinstance(accession, str) or not ACCESSION_RE.fullmatch(accession):
        raise InvalidInput("dicom_invalid_accession")
    report_text = payload.get("report_text")
    if not isinstance(report_text, str) or not report_text.strip() \
            or len(report_text) > 4000:
        raise InvalidInput(
            "dicom_report_text_required: nonempty, at most 4000 characters")
    source_version_id = payload.get("source_version_id")
    if source_version_id is not None \
            and (type(source_version_id) is not int or source_version_id < 1):
        raise InvalidInput("dicom_invalid_source_version_id")
    extra = sorted(set(payload) - {
        "study_uid", "modality", "accession", "report_text",
        "source_version_id"})
    if extra:
        raise InvalidInput(f"dicom_unknown_fields: {', '.join(extra)}")
    return {
        "study_uid": study_uid,
        "modality": modality,
        "accession": accession,
        "report_text": report_text.strip(),
        "source_version_id": source_version_id,
    }
