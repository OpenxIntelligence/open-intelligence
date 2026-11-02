"""Fictional DICOM Part 10 byte roundtrip and loopback DICOMweb protocol *subset*.

Only the original synthetic source ledger is authoritative. This does NOT
implement an externally deployable PACS, clinical DICOM validation, de-id,
authentication, production DICOMweb conformance or image interpretation.
"""
from __future__ import annotations

from hashlib import sha256
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import struct
from threading import Thread
from urllib.parse import urlsplit
from urllib.request import Request, urlopen

from .imaging_backend_contract import check_dicomweb_metadata
from .store import CaseStore, InvalidInput

BOUNDARY = "oi-synthetic-dicom"
INSTANCE_LIMIT = 256_000
IMPLICIT_VR_LE = "1.2.840.10008.1.2"
EXPLICIT_VR_LE = "1.2.840.10008.1.2.1"
CT_STORAGE = "1.2.840.10008.5.1.4.1.1.2"
META_IMPLEMENTATION_UID = "2.25.3703618943028452510039519805649999999"


def _element(group: int, number: int, vr: str, value: bytes) -> bytes:
    if len(value) % 2:
        value += b"\0" if vr in {"UI", "OB", "OW"} else b" "
    if vr in {"OB", "OW"}:
        return struct.pack("<HH2s2sI", group, number, vr.encode(), b"\0\0", len(value)) + value
    if len(value) > 0xFFFF:
        raise InvalidInput("Fictional DICOM element too large")
    return struct.pack("<HH2sH", group, number, vr.encode(), len(value)) + value


def _str(group: int, number: int, vr: str, value: str) -> bytes:
    return _element(group, number, vr, value.encode("ascii"))


def synthetic_dicom_bytes(study_uid="1.2.3", series_uid="1.2.3.1",
                          sop_uid="1.2.3.1.1") -> bytes:
    """One independently authored 2x2 uncompressed fictional CT image."""
    meta = b"".join([
        _element(2, 1, "OB", b"\0\1"),
        _str(2, 2, "UI", CT_STORAGE),
        _str(2, 3, "UI", sop_uid),
        _str(2, 16, "UI", EXPLICIT_VR_LE),
        _str(2, 18, "UI", META_IMPLEMENTATION_UID),
    ])
    ds = b"".join([
        _str(8, 16, "UI", CT_STORAGE),
        _str(8, 0x0018, "UI", sop_uid),
        _str(8, 0x0020, "DA", "20260517"),
        _str(8, 96, "CS", "CT"),
        _str(16, 32, "LO", "FICTIONAL-NOT-A-PATIENT"),
        _str(32, 13, "UI", study_uid),
        _str(32, 14, "UI", series_uid),
        _element(40, 2, "US", struct.pack("<H", 1)),
        _str(40, 4, "CS", "MONOCHROME2"),
        _element(40, 16, "US", struct.pack("<H", 2)),
        _element(40, 17, "US", struct.pack("<H", 2)),
        _element(40, 256, "US", struct.pack("<H", 16)),
        _element(40, 257, "US", struct.pack("<H", 16)),
        _element(40, 258, "US", struct.pack("<H", 15)),
        _element(40, 259, "US", struct.pack("<H", 0)),
        _element(0x7FE0, 0x0010, "OW", struct.pack("<4H", 0, 1, 2, 3)),
    ])
    return b"\0"*128 + b"DICM" + _element(2, 0, "UL", struct.pack("<I", len(meta))) + meta + ds


def _unpack(data: bytes) -> dict:
    """Deliberately strict, small explicit-VR LE test decoder; not general DICOM."""
    if not isinstance(data, bytes) or len(data) > INSTANCE_LIMIT or data[128:132] != b"DICM":
        raise InvalidInput("Unsupported DICOM Part 10 file or size")
    offset = 132
    result = {}
    while offset < len(data):
        if offset+8 > len(data):
            raise InvalidInput("Truncated DICOM element")
        group, element, vrbytes = struct.unpack_from("<HH2s", data, offset)
        vr = vrbytes.decode("ascii", errors="replace")
        if vr in {"OB", "OW", "SQ", "UN", "UT"}:
            if offset+12 > len(data):
                raise InvalidInput("Truncated long-VR DICOM header")
            length = struct.unpack_from("<I", data, offset+8)[0]
            offset += 12
        else:
            length = struct.unpack_from("<H", data, offset+6)[0]
            offset += 8
        if length > INSTANCE_LIMIT or offset+length > len(data):
            raise InvalidInput("Truncated DICOM element payload")
        key = f"{group:04X}{element:04X}"
        if key in result:
            raise InvalidInput("Duplicate DICOM element")
        result[key] = (vr, data[offset:offset+length])
        offset += length
    def text(key, vr):
        found = result.get(key)
        if found is None or found[0] != vr:
            raise InvalidInput("Required DICOM tag missing")
        return found[1].rstrip(b"\0 ").decode("ascii")
    if text("00020010","UI") != EXPLICIT_VR_LE:
        raise InvalidInput("Unsupported transfer syntax")
    if text("00020003","UI") != text("00080018","UI"):
        raise InvalidInput("File meta SOP mismatch")
    if text("00020002","UI") != text("00080016","UI"):
        raise InvalidInput("File meta storage-class mismatch")
    pixel = result.get("7FE00010")
    if pixel is None or pixel[0] != "OW" or len(pixel[1]) != 8:
        raise InvalidInput("Fictional 2x2 pixel payload missing")
    return {
        "study":text("0020000D","UI"),
        "series":text("0020000E","UI"),
        "sop":text("00080018","UI"),
        "date":text("00080020","DA"),
        "modality":text("00080060","CS"),
        "pixel_sha256":sha256(pixel[1]).hexdigest(),
    }


def _qido(ref: dict, parsed: dict) -> dict:
    def tag(vr, val):
        return {"vr":vr,"Value":[val]}
    return {
        "oi_test_case_id":ref["case_id"],
        "oi_test_source_version_id":ref["source_version_id"],
        "0020000D":tag("UI", parsed["study"]),
        "0020000E":tag("UI", parsed["series"]),
        "00080018":tag("UI", parsed["sop"]),
        "00080020":tag("DA", parsed["date"]),
        "00080060":tag("CS", parsed["modality"]),
    }


class SyntheticObjectServer:
    """In-memory one-object STOW/QIDO/WADO-like test transport, loopback only."""

    def __init__(self, store: CaseStore, case_id: str, source_version_id: int):
        self.store = store
        self.ref = {"case_id":case_id, "source_version_id":source_version_id}
        self.object = None
        self.parsed = None

    def validate(self, parsed):
        # HTTP handlers use their own connection; Python SQLite connections
        # cannot be shared across ThreadingHTTPServer request threads.
        if self.store.path == ":memory:":
            raise InvalidInput("Use a local fictional file-backed CaseStore for HTTP")
        local = CaseStore(self.store.path)
        try:
            check_dicomweb_metadata(local,self.ref["case_id"],
                                    [_qido(self.ref,parsed)])
        finally:
            local.close()

    def start(self):
        parent = self
        class Handler(BaseHTTPRequestHandler):
            def log_message(self, *args):
                pass
            def reply(self, status, data, mime):
                self.send_response(status)
                self.send_header("Content-Type", mime)
                self.send_header("Content-Length", str(len(data)))
                self.send_header("Cache-Control", "no-store")
                self.end_headers()
                self.wfile.write(data)
            def do_POST(self):
                if urlsplit(self.path).path != "/studies" or self.headers.get("Content-Type") != "application/dicom":
                    return self.reply(415,b"unsupported content","text/plain")
                try:
                    count = int(self.headers.get("Content-Length", "0"))
                    if count < 132 or count > INSTANCE_LIMIT:
                        raise InvalidInput("Invalid bounded byte count")
                    data = self.rfile.read(count)
                    parsed = _unpack(data)
                    parent.validate(parsed)
                    parent.object, parent.parsed = data,parsed
                    receipt = {"status":"stored_fictional_test_object",
                               "sha256":sha256(data).hexdigest()}
                    self.reply(200,json.dumps(receipt).encode(),"application/json")
                except (InvalidInput, ValueError):
                    self.reply(422,b"invalid fictional DICOM object or binding","text/plain")
            def do_GET(self):
                path = urlsplit(self.path).path
                if parent.object is None:
                    return self.reply(404,b"no object","text/plain")
                # Recheck current source version on every query/retrieval.
                try:
                    parent.validate(parent.parsed)
                except InvalidInput:
                    return self.reply(409,b"source context changed","text/plain")
                if path == "/studies":
                    return self.reply(200,json.dumps([_qido(parent.ref,parent.parsed)]).encode(),
                                      "application/dicom+json")
                if path == "/studies/"+parent.parsed["study"]+"/series/"+parent.parsed["series"]+"/instances/"+parent.parsed["sop"]:
                    return self.reply(200,parent.object,"application/dicom")
                return self.reply(404,b"unknown study","text/plain")
        # Server is bound to loopback; still not an authentication boundary.
        self.server = ThreadingHTTPServer(("127.0.0.1",0),Handler)
        self.thread = Thread(target=self.server.serve_forever,daemon=True)
        self.thread.start()
        return "http://127.0.0.1:"+str(self.server.server_port)

    def close(self):
        self.server.shutdown()
        self.server.server_close()
        self.thread.join(timeout=5)


def local_roundtrip(base_url: str, data: bytes) -> dict:
    """Real local HTTP transfer; simplified single-part endpoints, not full STOW."""
    request = Request(base_url+"/studies",data=data,method="POST",
                      headers={"Content-Type":"application/dicom"})
    with urlopen(request,timeout=5) as response:
        stored = json.loads(response.read())
    with urlopen(base_url+"/studies",timeout=5) as response:
        rows = json.loads(response.read())
    if len(rows) != 1:
        raise InvalidInput("Expected exactly one fictional study inventory entry")
    parsed = _unpack(data)
    with urlopen(base_url+"/studies/"+parsed["study"]+"/series/"+parsed["series"]+
                 "/instances/"+parsed["sop"],timeout=5) as response:
        returned = response.read()
    if returned != data:
        raise InvalidInput("DICOM object changed during retrieval")
    return {"store_receipt":stored,"qido_metadata":rows,
            "original_sha256":sha256(data).hexdigest(),
            "retrieved_sha256":sha256(returned).hexdigest(),
            "actual_http_roundtrip":True,
            "full_dicomweb_conformance":False,
            "clinical_validation":False}
