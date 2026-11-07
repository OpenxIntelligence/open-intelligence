"""Pure integrity checks for a bounded original CT and MR custody profile.

This accepts Part 10, Explicit VR Little Endian, one 16-bit MONOCHROME2 frame
from classic CT or MR Image Storage, with ASCII patient/issuer identity and
dimensions at most 1024 each.
It is neither a general DICOM validator nor identity/consent/clinical authority.
The custody owner must compare the returned identity to its locked source and
case binding. No original bytes, pixel arrays or diagnostics are returned.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from hashlib import sha256
from io import BytesIO
import re
import struct
import zlib

from pydicom import config as dicom_config
from pydicom.datadict import dictionary_VR
from pydicom.filereader import dcmread


MAX_DICOM_BYTES = 2_097_152
_MAX_ELEMENTS = 1024
_MAX_META_BYTES = 65_536
_STORAGE_MODALITY = {
    "1.2.840.10008.5.1.4.1.1.2": "CT",
    "1.2.840.10008.5.1.4.1.1.4": "MR",
}
_EXPLICIT_LE = "1.2.840.10008.1.2.1"
_UID = re.compile(r"(?:0|[1-9][0-9]*)(?:\.(?:0|[1-9][0-9]*))+\Z")
_LONG_VRS = frozenset({"OB", "OD", "OF", "OL", "OV", "OW", "SV", "UC", "UN", "UR", "UT", "UV"})
_SHORT_VRS = frozenset({"AE", "AS", "AT", "CS", "DA", "DS", "DT", "FD", "FL", "IS", "LO",
                        "LT", "PN", "SH", "SL", "SS", "ST", "TM", "UI", "UL", "US"})
_WIDTHS = {"AT": 4, "FD": 8, "FL": 4, "OD": 8, "OF": 4, "OL": 4, "OV": 8,
           "OW": 2, "SL": 4, "SS": 2, "SV": 8, "UL": 4, "US": 2, "UV": 8}


class DicomIntegrityError(RuntimeError):
    """Unsupported or inconsistent original; no original identifiers in errors."""


@dataclass(frozen=True, repr=False)
class DicomIdentity:
    patient_id: str
    issuer: str
    study_uid: str
    series_uid: str
    sop_uid: str
    sop_class_uid: str
    transfer_syntax_uid: str
    study_date: str
    modality: str
    rows: int
    columns: int
    byte_count: int
    sha256: str


def _elements(raw: bytes) -> dict[int, tuple[str, bytes]]:
    """Check complete framing before pydicom can collapse duplicates or recover.

    This is a framing pass, not an alternative pixel decoder. The bounded
    dictionary contains at most 1024 elements and at most the input's bytes.
    """
    if type(raw) is not bytes or not 144 <= len(raw) <= MAX_DICOM_BYTES or raw[128:132] != b"DICM":
        raise ValueError()
    offset, previous, meta_end = 132, -1, None
    found = {}
    while offset < len(raw):
        start = offset
        if len(found) >= _MAX_ELEMENTS or start + 8 > len(raw):
            raise ValueError()
        group, number, encoded_vr = struct.unpack_from("<HH2s", raw, start)
        tag = group << 16 | number
        vr = encoded_vr.decode("ascii")
        if tag <= previous or group == 0xFFFE:
            raise ValueError()
        try:
            declared_vr = dictionary_VR(tag)
        except KeyError:
            declared_vr = None
        if declared_vr == "SQ":
            # A known sequence cannot evade this profile by declaring OB/UN.
            raise ValueError()
        if vr in _LONG_VRS:
            if start + 12 > len(raw) or raw[start + 6:start + 8] != b"\0\0":
                raise ValueError()
            length = struct.unpack_from("<I", raw, start + 8)[0]
            offset += 12
        elif vr in _SHORT_VRS:
            length = struct.unpack_from("<H", raw, start + 6)[0]
            offset += 8
        else:
            # SQ (including empty/defined-length sequences) is out of profile.
            raise ValueError()
        end = offset + length
        if length == 0xFFFFFFFF or length % 2 or end > len(raw) or length % _WIDTHS.get(vr, 1):
            raise ValueError()
        if not found:
            if tag != 0x00020000 or vr != "UL" or length != 4:
                raise ValueError()
            meta_length = struct.unpack_from("<I", raw, offset)[0]
            if not 1 <= meta_length <= _MAX_META_BYTES:
                raise ValueError()
            meta_end = end + meta_length
            if meta_end > len(raw):
                raise ValueError()
        elif start < meta_end:
            if group != 2 or end > meta_end:
                raise ValueError()
        elif group < 8:
            raise ValueError()
        if tag == 0x7FE00010 and end != len(raw):
            # No appended datasets, fragments, or trailing padding in this profile.
            raise ValueError()
        found[tag] = vr, raw[offset:end]
        previous, offset = tag, end
    if meta_end is None or meta_end >= len(raw) or previous != 0x7FE00010:
        raise ValueError()
    return found


def _value(elements: dict, tag: int, vr: str) -> bytes:
    actual_vr, value = elements[tag]
    if actual_vr != vr:
        raise ValueError()
    return value


def _uid(elements: dict, tag: int) -> str:
    value = _value(elements, tag, "UI")
    if not 1 <= len(value) <= 64:
        raise ValueError()
    unpadded = value[:-1] if value.endswith(b"\0") else value
    text = unpadded.decode("ascii")
    if _UID.fullmatch(text) is None:
        raise ValueError()
    return text


def _text(elements: dict, tag: int, vr: str, maximum: int) -> str:
    value = _value(elements, tag, vr)
    if not 1 <= len(value) <= maximum:
        raise ValueError()
    text = value.rstrip(b" ").decode("ascii")
    if (not text or text.startswith(" ") or "\\" in text
            or any(ord(character) < 32 or ord(character) > 126 for character in text)):
        raise ValueError()
    return text


def _unsigned(elements: dict, tag: int) -> int:
    value = _value(elements, tag, "US")
    if len(value) != 2:
        raise ValueError()
    return struct.unpack("<H", value)[0]


def parse_dicom(raw: bytes) -> DicomIdentity:
    """Return identity derived from one supported exact original, or fail closed.

    pydicom receives only fully framed, unambiguous explicit-VR input and reads
    selected metadata. No pixel decoding, I/O, data/example helper, or global
    pydicom configuration change is performed. Errors suppress parser causes.
    """
    try:
        if dicom_config.debugging or dicom_config.data_element_callback is not None:
            # Diagnostic reads can emit raw tag values; callbacks can perform
            # arbitrary work. Refuse these modes without changing global state.
            raise ValueError()
        elements = _elements(raw)
        if _value(elements, 0x00020001, "OB") != b"\0\1":
            raise ValueError()
        meta_class, meta_sop = _uid(elements, 0x00020002), _uid(elements, 0x00020003)
        transfer_syntax = _uid(elements, 0x00020010)
        _uid(elements, 0x00020012)
        sop_class, sop = _uid(elements, 0x00080016), _uid(elements, 0x00080018)
        if (meta_class != sop_class or meta_sop != sop
                or sop_class not in _STORAGE_MODALITY or transfer_syntax != _EXPLICIT_LE):
            raise ValueError()
        if 0x00080005 in elements and _value(elements, 0x00080005, "CS").rstrip(b" ") not in (b"", b"ISO_IR 6"):
            raise ValueError()
        patient = _text(elements, 0x00100020, "LO", 64)
        issuer = _text(elements, 0x00100021, "LO", 64)
        study, series = _uid(elements, 0x0020000D), _uid(elements, 0x0020000E)
        study_date = _text(elements, 0x00080020, "DA", 8)
        if re.fullmatch(r"[0-9]{8}", study_date) is None:
            raise ValueError()
        actual_date = date(int(study_date[:4]), int(study_date[4:6]), int(study_date[6:]))
        modality = _text(elements, 0x00080060, "CS", 16)
        rows, columns = _unsigned(elements, 0x00280010), _unsigned(elements, 0x00280011)
        if modality != _STORAGE_MODALITY[sop_class] or not 1 <= rows <= 1024 or not 1 <= columns <= 1024:
            raise ValueError()
        if (_unsigned(elements, 0x00280002) != 1
                or _text(elements, 0x00280004, "CS", 16) != "MONOCHROME2"
                or _unsigned(elements, 0x00280100) != 16
                or _unsigned(elements, 0x00280101) != 16
                or _unsigned(elements, 0x00280102) != 15
                or _unsigned(elements, 0x00280103) not in (0, 1)):
            raise ValueError()
        if 0x00280008 in elements and _text(elements, 0x00280008, "IS", 12) != "1":
            raise ValueError()
        if len(_value(elements, 0x7FE00010, "OW")) != rows * columns * 2:
            raise ValueError()

        expected = {
            0x00080016: ("UI", sop_class), 0x00080018: ("UI", sop),
            0x00080020: ("DA", study_date), 0x00080060: ("CS", modality),
            0x00100020: ("LO", patient), 0x00100021: ("LO", issuer),
            0x0020000D: ("UI", study), 0x0020000E: ("UI", series),
            0x00280002: ("US", "1"), 0x00280004: ("CS", "MONOCHROME2"),
            0x00280010: ("US", str(rows)), 0x00280011: ("US", str(columns)),
            0x00280100: ("US", "16"), 0x00280101: ("US", "16"),
            0x00280102: ("US", "15"), 0x00280103: ("US", str(_unsigned(elements, 0x00280103))),
        }
        if 0x00280008 in elements:
            expected[0x00280008] = "IS", "1"
        dataset = dcmread(BytesIO(raw), force=False, stop_before_pixels=False,
                          specific_tags=list(expected))
        for tag, (vr, value) in expected.items():
            parsed = dataset[tag]
            if parsed.VR != vr or parsed.VM != 1 or str(parsed.value) != value:
                raise ValueError()
        if (str(dataset.file_meta.MediaStorageSOPClassUID) != sop_class
                or str(dataset.file_meta.MediaStorageSOPInstanceUID) != sop
                or str(dataset.file_meta.TransferSyntaxUID) != transfer_syntax):
            raise ValueError()
        return DicomIdentity(
            patient_id=patient, issuer=issuer, study_uid=study, series_uid=series,
            sop_uid=sop, sop_class_uid=sop_class, transfer_syntax_uid=transfer_syntax,
            study_date=actual_date.isoformat(), modality=modality, rows=rows, columns=columns,
            byte_count=len(raw), sha256=sha256(raw).hexdigest(),
        )
    except Exception:
        raise DicomIntegrityError("DICOM original integrity check failed") from None


_PNG_SIGNATURE = b"\x89PNG\r\n\x1a\n"
MAX_PREVIEW_BYTES = 1_200_000


def _png_chunk(kind: bytes, payload: bytes) -> bytes:
    if len(kind) != 4:
        raise ValueError()
    body = kind + payload
    return struct.pack(">I", len(payload)) + body + struct.pack(">I", zlib.crc32(body) & 0xFFFFFFFF)


def render_dicom_preview(raw: bytes) -> bytes:
    """Render a bounded, non-diagnostic 8-bit grayscale PNG from the qualified CT profile.

    The original is first revalidated by parse_dicom. Pixel values are mapped by
    per-frame min/max only; no modality LUT, rescale slope/intercept, VOI/window,
    spatial calibration, overlays, annotations or clinical interpretation is
    applied. This preview exists only to make the already-authorized synthetic
    custody object visible in the development workspace.
    """
    try:
        identity = parse_dicom(raw)
        if identity.modality != "CT":
            raise DicomIntegrityError("Preview requires the qualified CT profile")
        elements = _elements(raw)
        pixels = _value(elements, 0x7FE00010, "OW")
        signed = _unsigned(elements, 0x00280103) == 1
        sample = "<h" if signed else "<H"
        low = high = None
        for (value,) in struct.iter_unpack(sample, pixels):
            low = value if low is None or value < low else low
            high = value if high is None or value > high else high
        if low is None or high is None:
            raise ValueError()

        count = identity.rows * identity.columns
        grayscale = bytearray(count)
        if high == low:
            grayscale[:] = b"\x7f" * count
        else:
            span = high - low
            for index, (value,) in enumerate(struct.iter_unpack(sample, pixels)):
                grayscale[index] = (value - low) * 255 // span

        stride = identity.columns
        scanlines = b"".join(
            b"\x00" + bytes(grayscale[offset:offset + stride])
            for offset in range(0, count, stride)
        )
        header = struct.pack(">IIBBBBB", identity.columns, identity.rows, 8, 0, 0, 0, 0)
        png = (_PNG_SIGNATURE + _png_chunk(b"IHDR", header)
               + _png_chunk(b"IDAT", zlib.compress(scanlines, level=6))
               + _png_chunk(b"IEND", b""))
        if len(png) > MAX_PREVIEW_BYTES:
            raise ValueError()
        return png
    except DicomIntegrityError:
        raise
    except Exception:
        raise DicomIntegrityError("DICOM preview generation failed") from None
