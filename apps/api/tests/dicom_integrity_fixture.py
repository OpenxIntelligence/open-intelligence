"""Independently authored, stdlib-only CT and MR bytes for synthetic custody tests.

No scans, package datasets, patient records or pydicom data/example helpers.
This is a fixture encoder, not an image parser or an application authority.
"""

import struct


CT_CLASS = "1.2.840.10008.5.1.4.1.1.2"
MR_CLASS = "1.2.840.10008.5.1.4.1.1.4"
EXPLICIT_LE = "1.2.840.10008.1.2.1"
LONG_VRS = {"OB", "OD", "OF", "OL", "OV", "OW", "SQ", "SV", "UC", "UN", "UR", "UT", "UV"}


def element(tag: int, vr: str, value: bytes) -> bytes:
    """Encode one explicit-VR little-endian fixture element."""
    if len(value) % 2:
        value += b"\0" if vr in {"UI", "OB", "OW", "UN"} else b" "
    group, number = tag >> 16, tag & 0xFFFF
    if vr in LONG_VRS:
        return struct.pack("<HH2s2sI", group, number, vr.encode("ascii"), b"\0\0", len(value)) + value
    return struct.pack("<HH2sH", group, number, vr.encode("ascii"), len(value)) + value


def file_bytes(meta: list[tuple[int, str, bytes]], dataset: list[tuple[int, str, bytes]]) -> bytes:
    """Keep supplied element order so tests can author malformed files too."""
    encoded_meta = b"".join(element(*item) for item in meta)
    return (b"\0" * 128 + b"DICM"
            + element(0x00020000, "UL", struct.pack("<I", len(encoded_meta)))
            + encoded_meta + b"".join(element(*item) for item in dataset))


def fixture_elements(*, patient_id="SYNTHETIC-ALPHA", issuer="SYNTHETIC-PACS",
                     study_uid="2.25.11001", series_uid="2.25.11002", sop_uid="2.25.11003",
                     study_date="20260517", modality="CT", rows=2, columns=2, pixels=None):
    """Return editable fixture elements; values originate entirely here."""
    sop_class = {"CT": CT_CLASS, "MR": MR_CLASS}[modality].encode("ascii")
    if pixels is None:
        # A repeated four-value pattern remains 16-bit for larger authored frames.
        count = rows * columns
        pixels = (struct.pack("<4H", 0, 1, 2, 3) * ((count + 3) // 4))[:count * 2]
    meta = [
        (0x00020001, "OB", b"\0\1"),
        (0x00020002, "UI", sop_class),
        (0x00020003, "UI", sop_uid.encode("ascii")),
        (0x00020010, "UI", EXPLICIT_LE.encode("ascii")),
        (0x00020012, "UI", b"2.25.110099"),
    ]
    dataset = [
        (0x00080016, "UI", sop_class),
        (0x00080018, "UI", sop_uid.encode("ascii")),
        (0x00080020, "DA", study_date.encode("ascii")),
        (0x00080060, "CS", modality.encode("ascii")),
        (0x00100010, "PN", b"FICTIONAL^INDEPENDENT"),
        (0x00100020, "LO", patient_id.encode("ascii")),
        (0x00100021, "LO", issuer.encode("ascii")),
        (0x0020000D, "UI", study_uid.encode("ascii")),
        (0x0020000E, "UI", series_uid.encode("ascii")),
        (0x00280002, "US", struct.pack("<H", 1)),
        (0x00280004, "CS", b"MONOCHROME2"),
        (0x00280008, "IS", b"1"),
        (0x00280010, "US", struct.pack("<H", rows)),
        (0x00280011, "US", struct.pack("<H", columns)),
        (0x00280100, "US", struct.pack("<H", 16)),
        (0x00280101, "US", struct.pack("<H", 16)),
        (0x00280102, "US", struct.pack("<H", 15)),
        (0x00280103, "US", struct.pack("<H", 0)),
        (0x7FE00010, "OW", pixels),
    ]
    return meta, dataset


def dicom_bytes(*, patient_id="SYNTHETIC-ALPHA", issuer="SYNTHETIC-PACS",
                study_uid="2.25.11001", series_uid="2.25.11002", sop_uid="2.25.11003",
                study_date="20260517", modality="CT", rows=2, columns=2, pixels=None) -> bytes:
    return file_bytes(*fixture_elements(
        patient_id=patient_id, issuer=issuer, study_uid=study_uid, series_uid=series_uid,
        sop_uid=sop_uid, study_date=study_date, modality=modality, rows=rows, columns=columns, pixels=pixels,
    ))
