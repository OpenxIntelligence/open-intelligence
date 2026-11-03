"""Real-upstream DICOMweb smoke evaluation against an isolated local PACS.

Synthetic data only. This script does NOT grant patient/tenant authorization
to the upstream server, establish clinical suitability, or install a backend.
Only explicit 127.0.0.1 endpoints are supported; redirects are forbidden.
"""
from __future__ import annotations

import argparse
from email import policy
from email.parser import BytesParser
from hashlib import sha256
from io import BytesIO
import json
from pathlib import Path
import struct
import sys
import tempfile
from urllib.error import HTTPError
from urllib.parse import urlsplit, urlencode
from urllib.request import HTTPRedirectHandler, ProxyHandler, Request, build_opener

from open_intelligence.imaging_backend_contract import check_dicomweb_metadata
from open_intelligence.store import CaseStore, InvalidInput

BASE_PATH = Path(__file__).resolve().parents[2]
IMAGING_REPORT = BASE_PATH / "examples" / "synthetic" / "alpha-imaging.txt"
# Not a DICOM UIDs registry. These are fictional identifiers for local tests.
IMAGE_STUDY_UID = "2.25.110026110201000000000000000001"
IMAGE_SERIES_UID = "2.25.110026110201000000000000000002"
SOP_UIDS = (
    "2.25.110026110201000000000000000003",
    "2.25.110026110201000000000000000004",
)
MAX_DICOM_SIZE = 500_000
MAX_WIRE_SIZE = 1_250_000
BOUNDARY = "OI20261102SyntheticImageOnly"
# This experiment explicitly disables the vendor's default HTJ2K lossless
# archival transcoding, so both original file and raw pixel bytes can be
# tested independently. The vendor's default codec needs a separate
# decoded-pixel comparison; encoded byte inequality does not prove corruption.
EXPECTED_RETRIEVAL_TRANSFER_SYNTAX = "1.2.840.10008.1.2.1"
WADO_ACCEPT = ('multipart/related; type="application/dicom"; transfer-syntax='
               + EXPECTED_RETRIEVAL_TRANSFER_SYNTAX)


class RejectRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        raise InvalidInput("Redirect refused during synthetic backend evaluation")


OPENER = build_opener(RejectRedirect(), ProxyHandler({}))


def loopback_origin(base_url: str) -> str:
    """Require a single non-credentialed HTTP loopback origin."""
    if not isinstance(base_url, str):
        raise InvalidInput("Backend URL must be a string")
    parsed = urlsplit(base_url)
    try:
        port = parsed.port
    except ValueError:
        raise InvalidInput("Invalid HTTP port") from None
    if (parsed.scheme != "http" or parsed.hostname != "127.0.0.1"
            or not port or parsed.username or parsed.password
            or parsed.path not in ("", "/") or parsed.query or parsed.fragment):
        raise InvalidInput("Evaluation requires an HTTP 127.0.0.1 origin, no credentials")
    return f"http://127.0.0.1:{port}"


def synthetic_part10(sop: str, index: int) -> tuple[bytes, str]:
    """Create independent, fully fictional two-by-two CT SOP with pydicom.

    Only the pinned standalone pydicom dependency is used by this function.
    No patient data, bundled test scans or restricted compression codecs.
    """
    if sop not in SOP_UIDS or type(index) is not int or index not in (1, 2):
        raise InvalidInput("Unexpected fictional SOP identity")
    from pydicom.dataset import FileDataset, FileMetaDataset
    from pydicom.filewriter import dcmwrite
    from pydicom.uid import CTImageStorage, ExplicitVRLittleEndian, PYDICOM_IMPLEMENTATION_UID

    meta = FileMetaDataset()
    meta.MediaStorageSOPClassUID = CTImageStorage
    meta.MediaStorageSOPInstanceUID = sop
    meta.TransferSyntaxUID = ExplicitVRLittleEndian
    meta.ImplementationClassUID = PYDICOM_IMPLEMENTATION_UID
    ds = FileDataset(None, {}, file_meta=meta, preamble=b"\x00" * 128)
    ds.SOPClassUID = CTImageStorage
    ds.SOPInstanceUID = sop
    ds.PatientName = "FICTIONAL^NOT-A-REAL-PATIENT"
    ds.PatientID = "FICTIONAL-CASE-ALPHA"
    ds.PatientBirthDate = ""
    ds.PatientSex = "O"
    ds.StudyInstanceUID = IMAGE_STUDY_UID
    ds.SeriesInstanceUID = IMAGE_SERIES_UID
    ds.StudyDate = "20260517"
    ds.SeriesDate = "20260517"
    ds.ContentDate = "20260517"
    ds.StudyTime = "120000"
    ds.SeriesTime = "120000"
    ds.ContentTime = "120000"
    ds.AccessionNumber = "OI-SYNTH-ACC-001"
    ds.StudyID = "FICTIONAL-01"
    ds.Modality = "CT"
    ds.SeriesNumber = 1
    ds.InstanceNumber = index
    ds.ImageType = ["ORIGINAL", "PRIMARY", "AXIAL"]
    ds.FrameOfReferenceUID = "2.25.110026110201000000000000000005"
    ds.PatientPosition = "HFS"
    ds.ImagePositionPatient = ["0", "0", str(index)]
    ds.ImageOrientationPatient = ["1", "0", "0", "0", "1", "0"]
    ds.PixelSpacing = ["1", "1"]
    ds.SliceThickness = "1"
    ds.KVP = "120"
    ds.SamplesPerPixel = 1
    ds.PhotometricInterpretation = "MONOCHROME2"
    ds.Rows = 2
    ds.Columns = 2
    ds.BitsAllocated = 16
    ds.BitsStored = 16
    ds.HighBit = 15
    ds.PixelRepresentation = 0
    ds.RescaleIntercept = "0"
    ds.RescaleSlope = "1"
    ds.PixelData = struct.pack("<4H", index, index + 1, index + 2, index + 3)
    out = BytesIO()
    dcmwrite(out, ds, enforce_file_format=True)
    data = out.getvalue()
    if len(data) > MAX_DICOM_SIZE or data[128:132] != b"DICM":
        raise InvalidInput("Generated fictional Part 10 object is invalid")
    return data, sha256(ds.PixelData).hexdigest()


def multipart_body(parts: list[bytes]) -> tuple[str, bytes]:
    if not isinstance(parts, list) or len(parts) not in (1, 2):
        raise InvalidInput("Only one or two fictional DICOM parts are permitted")
    marker = BOUNDARY.encode("ascii")
    result = b"".join(
        b"--" + marker + b"\r\nContent-Type: application/dicom\r\n\r\n"
        + data + b"\r\n"
        for data in parts
        if isinstance(data, bytes) and 132 <= len(data) <= MAX_DICOM_SIZE
    ) + b"--" + marker + b"--\r\n"
    if len(result) > MAX_WIRE_SIZE or result.count(b"\r\nContent-Type: application/dicom\r\n") != len(parts):
        raise InvalidInput("Bounded multipart payload is invalid")
    return f'multipart/related; type="application/dicom"; boundary={BOUNDARY}', result


def multipart_dicom_parts(media_type: str, body: bytes) -> list[bytes]:
    if not isinstance(media_type, str) or not isinstance(body, bytes) or len(body) > MAX_WIRE_SIZE:
        raise InvalidInput("Unsupported DICOMweb response")
    headers = (f"Content-Type: {media_type}\r\nMIME-Version: 1.0\r\n\r\n").encode("ascii")
    message = BytesParser(policy=policy.default).parsebytes(headers + body)
    if message.get_content_type() != "multipart/related" or not message.is_multipart():
        raise InvalidInput("WADO response was not multipart/related")
    items = list(message.iter_parts())
    if len(items) not in (1, 2):
        raise InvalidInput("WADO response has unexpected object count")
    decoded = []
    for item in items:
        data = item.get_payload(decode=True)
        if (item.get_content_type() != "application/dicom" or not isinstance(data, bytes)
                or not 132 <= len(data) <= MAX_DICOM_SIZE or data[128:132] != b"DICM"):
            raise InvalidInput("WADO did not return bounded original DICOM Part 10")
        decoded.append(data)
    return decoded


def _request(url: str, *, method="GET", content=None, accept=None, content_type=None):
    headers = {}
    if accept:
        headers["Accept"] = accept
    if content_type:
        headers["Content-Type"] = content_type
    try:
        response = OPENER.open(
            Request(url, data=content, headers=headers, method=method), timeout=15
        )
        with response:
            data = response.read(MAX_WIRE_SIZE + 1)
            if len(data) > MAX_WIRE_SIZE:
                raise InvalidInput("Response exceeds bounded synthetic limit")
            return response.status, response.headers.get("Content-Type", ""), data
    except HTTPError as exc:
        data = exc.read(500)
        raise InvalidInput(f"Backend returned HTTP {exc.code}: {data[:120]!r}") from None


def _uid_value(row: dict, tag: str) -> str:
    value = row.get(tag)
    if not isinstance(value, dict) or value.get("vr") != "UI":
        raise InvalidInput(f"Missing {tag} typed DICOM QIDO field")
    ids = value.get("Value")
    if not isinstance(ids, list) or len(ids) != 1 or not isinstance(ids[0], str):
        raise InvalidInput("Ambiguous DICOM UID field")
    return ids[0]


def _qido_list(url: str) -> tuple[list[dict], str]:
    """Keep syntactic QIDO data checks distinct from media-type conformance.

    pacsnode currently uses axum::Json (application/json), which is a
    material deviation from PS3.18 application/dicom+json; the receipt MUST
    retain that fact. We still inspect its claimed DICOM JSON values to
    learn whether the open-source backend actually stores/retrieves them.
    """
    status, content_type, body = _request(url, accept="application/dicom+json")
    media_type = content_type.split(";", 1)[0].strip().lower()
    if status != 200 or media_type not in ("application/dicom+json", "application/json"):
        raise InvalidInput("QIDO response status/media incompatible: "
                           + str(status) + " " + media_type[:80])
    data = json.loads(body)
    if not isinstance(data, list):
        raise InvalidInput("QIDO results must be a list")
    return data, media_type


def run_evaluation(base_url: str) -> dict:
    base = loopback_origin(base_url)
    # All record material is authored independently within this test.
    with tempfile.TemporaryDirectory(prefix="oi-fictional-pacs-") as temporary:
        ledger = CaseStore(Path(temporary) / "fictional.sqlite")
        try:
            ledger.add_case("CASE-ALPHA", "Fictional oncology case")
            ledger.add_case("CASE-BETA", "Unrelated fictional case")
            source_id = ledger.import_report("CASE-ALPHA", IMAGING_REPORT.read_bytes())["source_id"]
            original_state = ledger.state("CASE-ALPHA")
            sources = [synthetic_part10(uid, idx) for idx, uid in enumerate(SOP_UIDS, 1)]
            payloads = [p[0] for p in sources]
            expected_pixel = {uid: p[1] for uid, p in zip(SOP_UIDS, sources)}
            expected_digests = {uid: sha256(data).hexdigest()
                                for uid, data in zip(SOP_UIDS, payloads)}
            mime, wire = multipart_body(payloads)

            status, stow_type, stow_body = _request(
                base + "/wado/studies", method="POST", content=wire,
                content_type=mime, accept="application/dicom+json"
            )
            if status not in (200, 201, 202):
                raise InvalidInput("STOW did not acknowledge objects")
            study_rows, study_mime = _qido_list(base + "/wado/studies?" + urlencode({
                "StudyInstanceUID": IMAGE_STUDY_UID
            }))
            if not any(_uid_value(row, "0020000D") == IMAGE_STUDY_UID
                       for row in study_rows):
                raise InvalidInput("Stored study not discoverable by QIDO")
            instance_rows, instance_mime = _qido_list(
                base + "/wado/studies/" + IMAGE_STUDY_UID
                + "/series/" + IMAGE_SERIES_UID + "/instances"
            )
            returned_ids = {_uid_value(row, "00080018") for row in instance_rows}
            if returned_ids != set(SOP_UIDS):
                raise InvalidInput("QIDO instance inventory differs from the stored SOP set")

            # Original stored metadata is checked against first-party source.
            # The PACS itself has no right to infer patient grant from PatientID.
            backend_qido = []
            for row in instance_rows:
                sop = _uid_value(row, "00080018")
                # QIDO may omit optional StudyDate/Modality at instance level.
                # Use independently authored original metadata only as
                # *declared* adapter input and explicitly compare returned UIDs.
                backend_qido.append({
                    "oi_test_case_id": "CASE-ALPHA",
                    "oi_test_source_version_id": source_id,
                    "0020000D": {"vr": "UI", "Value": [IMAGE_STUDY_UID]},
                    "0020000E": {"vr": "UI", "Value": [IMAGE_SERIES_UID]},
                    "00080018": {"vr": "UI", "Value": [sop]},
                    "00080020": {"vr": "DA", "Value": ["20260517"]},
                    "00080060": {"vr": "CS", "Value": ["CT"]},
                })
            checked = check_dicomweb_metadata(ledger, "CASE-ALPHA", backend_qido)
            try:
                check_dicomweb_metadata(ledger, "CASE-BETA", backend_qido)
            except InvalidInput:
                case_isolated_at_adapter = True
            else:
                raise InvalidInput("Case source binding leaked between synthetic patients")

            returned_digests = {}
            returned_pixel_digests = {}
            exact_byte_match = {}
            pixel_diagnostics = {}
            from pydicom import dcmread
            for sop in SOP_UIDS:
                _, wado_type, wado_body = _request(
                    base + "/wado/studies/" + IMAGE_STUDY_UID + "/series/"
                    + IMAGE_SERIES_UID + "/instances/" + sop,
                    accept=WADO_ACCEPT
                )
                objects = multipart_dicom_parts(wado_type, wado_body)
                if len(objects) != 1:
                    raise InvalidInput("WADO instance endpoint returned multiple SOPs")
                returned = objects[0]
                parsed = dcmread(BytesIO(returned))
                if (str(parsed.SOPInstanceUID) != sop
                        or str(parsed.StudyInstanceUID) != IMAGE_STUDY_UID
                        or str(parsed.SeriesInstanceUID) != IMAGE_SERIES_UID
                        or parsed.PatientID != "FICTIONAL-CASE-ALPHA"):
                    raise InvalidInput("Retrieved DICOM identities did not match uploaded SOP")
                original = dcmread(BytesIO(payloads[SOP_UIDS.index(sop)]))
                returned_ts = str(parsed.file_meta.TransferSyntaxUID)
                source_ts = str(original.file_meta.TransferSyntaxUID)
                pixel_matches = sha256(parsed.PixelData).hexdigest() == expected_pixel[sop]
                # The only pixel claim made here is equality of the
                # *encoded* bytes in the explicitly uncompressed test mode.
                # If a codec transcodes, this comparison is inconclusive
                # about the decoded numerical pixel array.
                pixel_diagnostics[sop] = {
                    "source_transfer_syntax": source_ts,
                    "retrieved_transfer_syntax": returned_ts,
                    "requested_uncompressed_transfer_syntax":
                        EXPECTED_RETRIEVAL_TRANSFER_SYNTAX,
                    "source_pixel_length": len(original.PixelData),
                    "retrieved_pixel_length": len(parsed.PixelData),
                    "source_pixel_sha256": expected_pixel[sop],
                    "retrieved_pixel_sha256": sha256(parsed.PixelData).hexdigest(),
                    "encoded_pixel_bytes_equal": pixel_matches,
                    "retrieval_is_expected_uncompressed_encoding":
                        returned_ts == EXPECTED_RETRIEVAL_TRANSFER_SYNTAX,
                }
                returned_digests[sop] = sha256(returned).hexdigest()
                returned_pixel_digests[sop] = sha256(parsed.PixelData).hexdigest()
                exact_byte_match[sop] = returned_digests[sop] == expected_digests[sop]

            if ledger.state("CASE-ALPHA") != original_state:
                raise InvalidInput("Backend evaluation mutated first-party case ledger")
            amendment = (
                "OI-SYNTHETIC-REPORT/1\nPatient: CASE-ALPHA\n"
                "Document: IMG-ALPHA\nType: imaging\n"
                "Event-Date: 2026-05-17\nIssued-At: 2026-05-19\n"
                "Amends: IMG-ALPHA@1\n"
                "Finding: comparison|reported|Corrected fictional imaging report.\n"
            ).encode()
            ledger.import_report("CASE-ALPHA", amendment)
            try:
                check_dicomweb_metadata(ledger, "CASE-ALPHA", backend_qido)
            except InvalidInput:
                amendment_blocks_first_party_binding = True
            else:
                raise InvalidInput("Source amendment did not invalidate adapter binding")

            encoding_verified = all(
                p["encoded_pixel_bytes_equal"]
                and p["retrieval_is_expected_uncompressed_encoding"]
                for p in pixel_diagnostics.values()
            )
            originals_verified = all(exact_byte_match.values())
            return {
                "evaluation_status": (
                    "technical_roundtrip_observed_with_standards_hold"
                    if encoding_verified and originals_verified else
                    "HOLD_original_object_bytes_changed"
                    if encoding_verified else
                    "HOLD_uncompressed_pixel_or_transfer_syntax_mismatch"
                ),
                "technical_evaluation_passed": encoding_verified and originals_verified,
                "clinical_or_full_dicomweb_approval": False,
                "candidate": "knopkem/pacsnode standalone",
                "source_commit": "e9b4334477a66967d290add9e0b9afa068f59dc0",
                "backend_url": "127.0.0.1 client destination only",
                "backend_listener_isolation_verified": False,
                "synthetic_only": True,
                "dicom_count": len(SOP_UIDS),
                "study_count": checked["study_count"],
                "series_count": checked["series_count"],
                "stow_http_status": status,
                "stow_content_type": stow_type,
                "wado_accept": WADO_ACCEPT,
                "qido_media_types": {
                    "study": study_mime,
                    "instance": instance_mime,
                },
                "qido_media_type_conformant": (
                    study_mime == instance_mime == "application/dicom+json"
                ),
                "standards_conformance_verified": False,
                "stow_response_sha256": sha256(stow_body).hexdigest(),
                "sop_original_sha256": expected_digests,
                "sop_returned_sha256": returned_digests,
                "sop_pixel_sha256": returned_pixel_digests,
                "pixel_diagnostics": pixel_diagnostics,
                "uncompressed_pixel_integrity_passed": encoding_verified,
                "source_and_retrieved_objects_byte_identical":
                    originals_verified,
                "compressed_pixel_equivalence_verified": False,
                "default_storage_codec_evaluated": False,
                "exact_original_object_preserved": exact_byte_match,
                "first_party_wrong_case_rejected": case_isolated_at_adapter,
                "first_party_amendment_rejected": amendment_blocks_first_party_binding,
                "pacs_authentication_verified": False,
                "pacs_tenant_isolation_verified": False,
                "clinical_validation": False,
                "upstream_license_approved": False,
                "real_patient_data_used": False,
                "limitations": [
                    "Standalone test server is unauthenticated and NOT clinical software",
                    "Loopback client restriction does not confine the server's 0.0.0.0 listener",
                    "Default HTJ2K storage and default transfer-syntax negotiation remain unverified",
                    "The PACS does not enforce Open Intelligence's canonical case grants",
                    "The source is an evaluation candidate, not an adopted dependency",
                    "Source-level MIT declarations do not clear all crates and embedded assets",
                    "The default Docker stack uses a separately license-gated storage service",
                ],
            }
        finally:
            ledger.close()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--base-url", required=True)
    parser.add_argument("--output", default="verification-artifacts/pacsnode-roundtrip.json")
    args = parser.parse_args()
    try:
        evidence = run_evaluation(args.base_url)
    except Exception as error:
        # Persist a bounded failure even when parsing/transport stopped before
        # per-SOP diagnostics existed. Never log an untrusted response or URL.
        evidence = {
            "evaluation_status": "HOLD_evaluation_error",
            "technical_evaluation_passed": False,
            "failure_type": type(error).__name__,
            "clinical_or_full_dicomweb_approval": False,
            "real_patient_data_used": False,
        }
    # The CLI independently enforces the original-preservation contract. A
    # transport/pixel success must never hide changed complete file bytes.
    evidence["technical_evaluation_passed"] = (
        evidence.get("technical_evaluation_passed") is True
        and evidence.get("uncompressed_pixel_integrity_passed") is True
        and evidence.get("source_and_retrieved_objects_byte_identical") is True
    )
    output = Path(args.output)
    try:
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(json.dumps(evidence, indent=2, sort_keys=True) + "\n",
                          encoding="utf-8")
    except OSError:
        print("HOLD: could not persist the evaluation receipt", file=sys.stderr)
        return 1
    if evidence["technical_evaluation_passed"]:
        print("TECHNICAL TEST COMPLETE: original files and uncompressed pixel bytes match.")
        if not evidence["qido_media_type_conformant"]:
            print("STANDARDS HOLD: QIDO response used application/json "
                  "rather than application/dicom+json")
        print("No backend adoption, patient access control or clinical clearance.")
        print("Evidence file:", output)
        return 0
    print("HOLD: original-object, pixel, transfer-syntax or evaluation failure; "
          "inspect the bounded JSON diagnostics", file=sys.stderr)
    print("Evidence file:", output)
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
