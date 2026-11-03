"""Source-owned image custody through the existing canonical registry boundary.

The small development profile stores originals in PostgreSQL, not a public
PACS. Every operation shares the source owner's patient/case locks and event
journal. No source, patient, identity, permission or review ledger is added.
"""
from __future__ import annotations

from collections.abc import Callable
from dataclasses import asdict
import hashlib
import json
import re
import uuid

from open_intelligence.patient_registry import (
    PatientRegistryConflict, PatientRegistryDenied, PatientRegistryError, _key,
)

from .case_bindings import _case_id
from .dicom_integrity import DicomIntegrityError, parse_dicom
from .sources import PostgresSourceVersions, PreparedResponse, _source_id


MAX_CASE_IMAGES = 256
MAX_CASE_IMAGE_BYTES = 67_108_864
_FIELDS = ("image_id", "case_id", "raw", "sha256", "byte_count", "patient_id", "issuer",
           "study_uid", "series_uid", "sop_uid", "sop_class_uid", "transfer_syntax_uid",
           "study_date", "modality", "rows", "columns")
_PUBLIC = ("image_id", "case_id", "sha256", "byte_count", "study_uid", "series_uid", "sop_uid", "modality")


class ImageIntegrityError(RuntimeError):
    """Stored custody corruption: never expose raw input or parser diagnostics."""


def _image_id(value: object) -> str:
    if type(value) is not str or re.fullmatch(r"IMG-[0-9A-F]{32}", value) is None:
        raise PatientRegistryError("Invalid image identifier")
    return value


class PostgresSourceImages:
    def __init__(self, registry, *, archive=None):
        self.archive = archive
        self.sources = PostgresSourceVersions(registry)
        self.registry = registry

    def _scope(self, patient_id, case_id, source_id, organization, purpose):
        _key(patient_id, "patient_id")
        _case_id(case_id)
        _source_id(source_id)
        _key(organization, "organization")
        revision = self.sources._binding(patient_id, case_id, organization, purpose)
        # A manually reviewed document is a different source owner, even when
        # its kind says imaging or a legacy image link names this source ID.
        if self.sources._is_reviewed(source_id):
            raise PatientRegistryDenied("Current imaging source unavailable")
        source, _ = self.sources._validated_original(case_id, source_id)
        if source["kind"] != "imaging" or source["state"] != "current":
            raise PatientRegistryDenied("Current imaging source unavailable")
        # The qualified mapping is immutable and was locked above. This narrow
        # profile maps IssuerOfPatientID to source_organization/source_system.
        # Both stored keys forbid '/', so this preserves the qualified namespace
        # without collisions. PatientID is the exact source_subject_ref.
        binding = self.registry._fetchone(
            "SELECT source_organization,source_system,source_subject_ref "
            "FROM coordination.patient_case_bindings WHERE case_id=%s", (case_id,))
        if binding is None:
            raise PatientRegistryDenied("Image mapping unavailable")
        return revision, source, binding

    @staticmethod
    def _issuer(binding):
        return binding[0] + "/" + binding[1]

    @staticmethod
    def _matches_context(identity, source, binding):
        return (identity.patient_id, identity.issuer, identity.study_date) == (
            binding[2], PostgresSourceImages._issuer(binding), source["event_date"].isoformat())

    @staticmethod
    def _metadata(row, source_id):
        return {**{name: row[name] for name in _PUBLIC}, "source_id": source_id,
                "study_date": row["study_date"].isoformat()}

    def _validated_object(self, row, source, binding, *, require_source_date=True):
        try:
            raw = bytes(row["raw"])
            identity = parse_dicom(raw)
            actual = asdict(identity)
            stored = {name: row[name] for name in actual}
            stored["study_date"] = stored["study_date"].isoformat()
            if (actual != stored or row["case_id"] != source["case_id"]
                    or (identity.patient_id, identity.issuer) != (binding[2], self._issuer(binding))
                    or (require_source_date and identity.study_date != source["event_date"].isoformat())):
                raise ValueError()
            return raw
        except Exception:
            raise ImageIntegrityError("Stored image integrity failure") from None

    def import_original(self, patient_id: str, case_id: str, source_id: str, original: bytes, *,
                        organization: str, actor: str, purpose: str,
                        recheck_authority: Callable[[], None],
                        prepare_response: Callable[[dict], PreparedResponse] | None = None) -> dict | PreparedResponse:
        with self.registry.transaction():
            revision, source, binding = self._scope(patient_id, case_id, source_id, organization, purpose)
            try:
                identity = parse_dicom(original)
            except DicomIntegrityError:
                raise PatientRegistryError("Unsupported image input") from None
            if not self._matches_context(identity, source, binding):
                raise PatientRegistryError("Image context mismatch")
            stored = self.registry._fetchone(
                "SELECT " + ",".join(_FIELDS) + " FROM clinical_source.dicom_objects "
                "WHERE case_id=%s AND sop_uid=%s", (case_id, identity.sop_uid))
            result = "imported"
            if stored is not None:
                row = dict(zip(_FIELDS, stored))
                # A prior object can belong to a different report date. First
                # validate its own immutable custody, then classify a changed
                # same-SOP upload as conflict. The incoming object has already
                # been checked against the new parent date above.
                old_raw = self._validated_object(row, source, binding, require_source_date=False)
                if old_raw != original:
                    raise PatientRegistryConflict("Image identity already has different original bytes")
                link = self.registry._fetchone(
                    "SELECT image_id FROM clinical_source.source_image_links "
                    "WHERE source_id=%s AND image_id=%s", (source_id, row["image_id"]))
                result = "duplicate" if link else "linked"
            else:
                count, size = self.registry._fetchone(
                    "SELECT count(*),coalesce(sum(byte_count),0) FROM clinical_source.dicom_objects WHERE case_id=%s",
                    (case_id,))
                if count >= MAX_CASE_IMAGES or size + identity.byte_count > MAX_CASE_IMAGE_BYTES:
                    raise PatientRegistryConflict("Development image custody limit reached")
                row = {"image_id": "IMG-" + uuid.uuid4().hex.upper(), "case_id": case_id,
                       "raw": original, **asdict(identity)}
                self.registry._execute(
                    "INSERT INTO clinical_source.dicom_objects (" + ",".join(_FIELDS) + ") VALUES ("
                    + ",".join("%s::date" if name == "study_date" else "%s" for name in _FIELDS) + ")",
                    tuple(row[name] for name in _FIELDS))
                # Metadata serialization uses the same date type as PostgreSQL.
                from datetime import date
                row["study_date"] = date.fromisoformat(identity.study_date)
            if result != "duplicate":
                self.registry._execute(
                    "INSERT INTO clinical_source.source_image_links(source_id,image_id) VALUES (%s,%s)",
                    (source_id, row["image_id"]))
            response = {**self._metadata(row, source_id), "result": result, "synthetic": True,
                        "source_identity_verified": False, "clinical_interpretation": False}
            prepared = prepare_response(response) if prepare_response is not None else response
            # Includes retries: an old successful import is no ongoing grant.
            recheck_authority()
            if result != "duplicate":
                self.registry.append_event(
                    patient_id, "image.original_imported" if result == "imported" else "image.source_linked",
                    actor=_key(actor, "actor"), purpose=purpose, binding_revision=revision,
                    case_id=case_id, source_id=source_id, source_version=source["version"],
                    source_sha256=source["sha256"], image_id=row["image_id"],
                    sha256=row["sha256"], byte_count=row["byte_count"])
                # Event persistence is I/O: changed authority must also roll
                # back the original/link and its event, not release the body.
                recheck_authority()
            return prepared

    def list(self, patient_id: str, case_id: str, source_id: str, *, organization: str,
             actor: str, purpose: str, recheck_authority: Callable[[], None],
             prepare_response: Callable[[dict], PreparedResponse] | None = None) -> dict | PreparedResponse:
        with self.registry.transaction():
            revision, source, binding = self._scope(patient_id, case_id, source_id, organization, purpose)
            fields = tuple(name for name in _FIELDS if name != "raw")
            rows = self.registry._fetchall(
                "SELECT " + ",".join("o." + name for name in fields)
                + " FROM clinical_source.dicom_objects o JOIN clinical_source.source_image_links l "
                "ON l.image_id=o.image_id WHERE o.case_id=%s AND l.source_id=%s ORDER BY o.image_id LIMIT %s",
                (case_id, source_id, MAX_CASE_IMAGES + 1))
            if len(rows) > MAX_CASE_IMAGES:
                raise ImageIntegrityError("Image index exceeds custody profile")
            images = []
            for values in rows:
                row = dict(zip(fields, values))
                if (row["patient_id"], row["issuer"], row["study_date"]) != (
                        binding[2], self._issuer(binding), source["event_date"]):
                    raise ImageIntegrityError("Stored image context failure")
                images.append(self._metadata(row, source_id))
            result = {"patient_id": patient_id, "case_id": case_id, "source_id": source_id,
                      "images": images, "synthetic": True, "source_identity_verified": False}
            snapshot = hashlib.sha256(json.dumps(result, sort_keys=True, ensure_ascii=False,
                                                 separators=(",", ":")).encode()).hexdigest()
            receipt = "ACCESS-" + uuid.uuid4().hex.upper()
            result["access_receipt_id"] = receipt
            prepared = prepare_response(result) if prepare_response is not None else result
            self.sources._read_receipt(
                patient_id, case_id, actor=actor, purpose=purpose, binding_revision=revision,
                event="image.read_authorized", receipt_id=receipt,
                recheck_authority=recheck_authority,
                source_id=source_id, source_version=source["version"], source_sha256=source["sha256"],
                snapshot_sha256=snapshot, image_count=len(images))
            recheck_authority()
            return prepared

    def original(self, patient_id: str, case_id: str, source_id: str, image_id: str, *,
                 organization: str, actor: str, purpose: str,
                 recheck_authority: Callable[[], None],
                 prepare_response: Callable[[bytes, str], PreparedResponse] | None = None
                 ) -> tuple[bytes, str] | PreparedResponse:
        """Validate and prepare bounded original bytes before final authority.

        Archive I/O never holds patient/case locks. After retrieval, a fresh
        transaction revalidates custody and covers complete response preparation,
        final authority and receipt commit. Preparation never streams.
        """
        _image_id(image_id)
        remote = None
        if self.archive is not None:
            # Preflight uses canonical custody and server-stored identifiers;
            # callers cannot supply an upstream URL, credential or expected hash.
            with self.registry.transaction():
                revision, source, binding = self._scope(patient_id, case_id, source_id, organization, purpose)
                values = self.registry._fetchone(
                    "SELECT " + ",".join("o." + name for name in _FIELDS)
                    + " FROM clinical_source.dicom_objects o JOIN clinical_source.source_image_links l "
                    "ON l.image_id=o.image_id WHERE o.case_id=%s AND l.source_id=%s AND o.image_id=%s",
                    (case_id, source_id, image_id))
                if values is None:
                    raise PatientRegistryDenied("Image unavailable")
                row = dict(zip(_FIELDS, values))
                expected = self._validated_object(row, source, binding)
                preflight = (revision, source["sha256"], tuple(binding))
                recheck_authority()
            # Release all source-owner locks before any external network call.
            # A configured archive failure is never a silent local fallback.
            try:
                remote = self.archive.read(row["study_uid"], row["series_uid"], row["sop_uid"])
                if type(remote) is not bytes or remote != expected:
                    raise ValueError()
            except Exception:
                raise ImageIntegrityError("Remote original unavailable") from None
        with self.registry.transaction():
            revision, source, binding = self._scope(patient_id, case_id, source_id, organization, purpose)
            if self.archive is not None and preflight != (revision, source["sha256"], tuple(binding)):
                raise PatientRegistryDenied("Image authority changed")
            values = self.registry._fetchone(
                "SELECT " + ",".join("o." + name for name in _FIELDS)
                + " FROM clinical_source.dicom_objects o JOIN clinical_source.source_image_links l "
                "ON l.image_id=o.image_id WHERE o.case_id=%s AND l.source_id=%s AND o.image_id=%s",
                (case_id, source_id, image_id))
            if values is None:
                raise PatientRegistryDenied("Image unavailable")
            row = dict(zip(_FIELDS, values))
            raw = self._validated_object(row, source, binding)
            if remote is not None:
                if remote != raw:
                    raise ImageIntegrityError("Original changed during remote retrieval")
                raw = remote
            receipt_id = "ACCESS-" + uuid.uuid4().hex.upper()
            prepared = (prepare_response(raw, receipt_id) if prepare_response is not None
                        else (raw, receipt_id))
            self.sources._read_receipt(
                patient_id, case_id, actor=actor, purpose=purpose, binding_revision=revision,
                event="image.original_read_authorized", receipt_id=receipt_id,
                recheck_authority=recheck_authority,
                source_id=source_id, source_version=source["version"], source_sha256=source["sha256"],
                image_id=image_id, sha256=row["sha256"], byte_count=len(raw))
            recheck_authority()
            return prepared
