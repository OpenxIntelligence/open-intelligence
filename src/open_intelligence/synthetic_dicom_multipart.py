"""Bounded one-part DICOMweb multipart encoder/decoder for fictional tests.

Wire-format subset only. Not a conformant PACS, general multipart parser,
authentication layer, PHI processing library, or clinical image validator.
"""
from __future__ import annotations

import re
from .store import InvalidInput

MAX_BODY = 300_000
BOUNDARY = "oi-synthetic-dicom-test-1"
BOUNDARY_RE = re.compile(r"[A-Za-z0-9_-]{8,64}\Z")


def encode_dicom_part(data: bytes, boundary: str = BOUNDARY) -> tuple[str, bytes]:
    if not BOUNDARY_RE.fullmatch(boundary):
        raise InvalidInput("Bad test boundary")
    if not isinstance(data, bytes) or not 132 <= len(data) <= 256_000:
        raise InvalidInput("Only bounded fictional DICOM files")
    marker=boundary.encode("ascii")
    body=(b"--"+marker+b"\r\n"
          b"Content-Type: application/dicom\r\n"
          b"\r\n"+data+b"\r\n--"+marker+b"--\r\n")
    return "multipart/related; type=\"application/dicom\"; boundary="+boundary,body


def decode_dicom_part(content_type: str, body: bytes) -> bytes:
    if not isinstance(content_type,str) or not isinstance(body,bytes) or len(body)>MAX_BODY:
        raise InvalidInput("Unsupported multipart input")
    # Deliberately refuse duplicated/unknown parameters and multi-parts.
    match=re.fullmatch(
        r'multipart/related;\s*type="?application/dicom"?;\s*boundary="?([A-Za-z0-9_-]{8,64})"?',
        content_type,re.I)
    if not match:
        raise InvalidInput("Unsupported multipart media type")
    marker=match.group(1).encode("ascii")
    prefix=b"--"+marker+b"\r\nContent-Type: application/dicom\r\n\r\n"
    suffix=b"\r\n--"+marker+b"--\r\n"
    if not body.startswith(prefix) or not body.endswith(suffix):
        raise InvalidInput("Malformed or multiple-part DICOM multipart body")
    payload=body[len(prefix):-len(suffix)]
    if not 132 <= len(payload) <= 256_000 or payload[128:132] != b"DICM":
        raise InvalidInput("Missing valid fictional Part 10 DICOM payload")
    if b"\r\n--"+marker+b"\r\n" in payload:
        raise InvalidInput("Multiple objects unsupported")
    return payload
