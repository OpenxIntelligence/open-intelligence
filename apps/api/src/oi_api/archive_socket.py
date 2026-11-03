"""Bounded Linux private-socket replica reads, injected into existing custody.

This is a deliberately small HTTP profile, not a general DICOMweb client or
patient authorization service. The caller must still validate exact original
bytes and current patient/source authority. Nothing enables this adapter by
default; no endpoint or credentials are accepted from an HTTP request.
"""
from __future__ import annotations

from dataclasses import dataclass, field
import math
import re
import socket
import struct
from threading import BoundedSemaphore
import time


# A separate transport ceiling, equal to the current original-custody ceiling.
# Raising the clinical parser's limit does not implicitly widen this transport.
MAX_ARCHIVE_INSTANCE_BYTES = 2_097_152
_MAX_HEADERS = 16_384
_MAX_HEADER_COUNT = 64
_MAX_HEADER_LINE = 4096
_MAX_ENVELOPE = 16_384
_UID = re.compile(r"(?:0|[1-9][0-9]*)(?:\.(?:0|[1-9][0-9]*))+\Z")
_TOKEN = re.compile(rb"[!#$%&'*+.^_`|~0-9A-Za-z-]+\Z")
_BOUNDARY = re.compile(r"[0-9A-Za-z'()+_,./:=? -]{1,70}\Z")


class ArchiveTransportError(RuntimeError):
    """Generic failure; no private path, identifiers or upstream diagnostics."""


@dataclass(frozen=True, slots=True, repr=False, eq=False)
class ArchiveReadCapacity:
    """Non-waiting transport slots shared explicitly within one process.

    Instantiate after worker startup/fork. This limits socket/receive/parse work,
    not canonical custody queries, caller-owned returned bytes or other workers.
    """
    max_in_flight: int = 4
    _slots: BoundedSemaphore = field(init=False, repr=False)

    def __post_init__(self) -> None:
        if type(self.max_in_flight) is not int or not 1 <= self.max_in_flight <= 16:
            raise ValueError("Invalid archive read capacity")
        object.__setattr__(self, "_slots", BoundedSemaphore(self.max_in_flight))


def _remaining(deadline: float) -> float:
    remaining = deadline - time.monotonic()
    if remaining <= 0:
        raise TimeoutError()
    return remaining


def _headers(block: bytes) -> dict[bytes, bytes]:
    """Parse only bounded, unfolded ASCII headers; reject all duplicate names."""
    if len(block) > _MAX_HEADERS:
        raise ValueError()
    lines = block.split(b"\r\n")
    if not 1 <= len(lines) <= _MAX_HEADER_COUNT:
        raise ValueError()
    result: dict[bytes, bytes] = {}
    for line in lines:
        if not line or len(line) > _MAX_HEADER_LINE or b":" not in line:
            raise ValueError()
        name, value = line.split(b":", 1)
        name = name.lower()
        if _TOKEN.fullmatch(name) is None or name in result:
            raise ValueError()
        if any(byte < 32 and byte != 9 or byte > 126 for byte in value):
            raise ValueError()
        result[name] = value.strip(b" \t")
    return result


def _length(value: bytes | None, ceiling: int) -> int:
    # Bound the integer before parsing; reject signs, lists and leading zeros.
    if value is None or not 1 <= len(value) <= 10 or re.fullmatch(rb"[1-9][0-9]*", value) is None:
        raise ValueError()
    size = int(value)
    if size > ceiling:
        raise ValueError()
    return size


def _media_type(value: bytes | None) -> bytes | None:
    """Return a multipart boundary, or None for raw application/dicom."""
    if value is None:
        raise ValueError()
    sections = value.decode("ascii").split(";")
    media = sections.pop(0).strip().lower()
    if media == "application/dicom" and not sections:
        return None
    if media != "multipart/related":
        raise ValueError()
    params: dict[str, str] = {}
    for section in sections:
        name, separator, parameter = section.strip().partition("=")
        name, parameter = name.strip().lower(), parameter.strip()
        if not separator or name not in {"type", "boundary"} or name in params:
            raise ValueError()
        if parameter.startswith('"') and parameter.endswith('"') and len(parameter) >= 2:
            parameter = parameter[1:-1]
            if '"' in parameter or "\\" in parameter:
                raise ValueError()
        elif not parameter or _TOKEN.fullmatch(parameter.encode("ascii")) is None:
            # The media type has a slash; it must be quoted in this small profile.
            raise ValueError()
        params[name] = parameter
    boundary = params.get("boundary", "")
    if (set(params) != {"type", "boundary"}
            or params["type"].lower() != "application/dicom"
            or _BOUNDARY.fullmatch(boundary) is None or boundary.endswith(" ")):
        raise ValueError()
    return boundary.encode("ascii")


def _instance(body: bytes, boundary: bytes | None, path: bytes) -> bytes:
    if boundary is None:
        raw = body
    else:
        opening = b"--" + boundary + b"\r\n"
        closing = b"\r\n--" + boundary + b"--\r\n"
        if not body.startswith(opening) or not body.endswith(closing):
            raise ValueError()
        end = body.find(b"\r\n\r\n", len(opening))
        if end < 0 or end + 4 > _MAX_HEADERS:
            raise ValueError()
        headers = _headers(body[len(opening):end])
        if (headers.get(b"content-type", b"").lower() != b"application/dicom"
                or set(headers) - {b"content-type", b"content-length", b"content-location"}):
            raise ValueError()
        if b"content-location" in headers and headers[b"content-location"] != path:
            raise ValueError()
        raw = body[end + 4:-len(closing)]
        if (b"\r\n--" + boundary in raw or len(body) - len(raw) > _MAX_ENVELOPE):
            raise ValueError()
        if b"content-length" in headers and _length(headers[b"content-length"],
                                                     MAX_ARCHIVE_INSTANCE_BYTES) != len(raw):
            raise ValueError()
    if not 1 <= len(raw) <= MAX_ARCHIVE_INSTANCE_BYTES:
        raise ValueError()
    return raw


def _receive(sock: socket.socket, deadline: float, path: bytes) -> bytes:
    data = bytearray()
    while b"\r\n\r\n" not in data:
        if len(data) >= _MAX_HEADERS:
            raise ValueError()
        sock.settimeout(_remaining(deadline))
        block = sock.recv(min(4096, _MAX_HEADERS - len(data)))
        if not block:
            raise ValueError()
        data.extend(block)
    header, body = bytes(data).split(b"\r\n\r\n", 1)
    status, separator, fields = header.partition(b"\r\n")
    if not separator or re.fullmatch(rb"HTTP/1\.1 200 [\x20-\x7e]*", status) is None:
        raise ValueError()
    headers = _headers(fields)
    if b"transfer-encoding" in headers or b"content-encoding" in headers:
        raise ValueError()
    boundary = _media_type(headers.get(b"content-type"))
    ceiling = MAX_ARCHIVE_INSTANCE_BYTES + (_MAX_ENVELOPE if boundary is not None else 0)
    size = _length(headers.get(b"content-length"), ceiling)
    if len(body) > size:
        raise ValueError()
    payload = bytearray(body)
    while len(payload) < size:
        sock.settimeout(_remaining(deadline))
        block = sock.recv(min(65_536, size - len(payload)))
        if not block:
            raise ValueError()
        payload.extend(block)
    # Connection: close is mandatory for this profile. Detect late surplus
    # bytes too, not only a surplus delivered in the first recv(). No pooling.
    sock.settimeout(_remaining(deadline))
    if sock.recv(1):
        raise ValueError()
    raw = _instance(bytes(payload), boundary, path)
    _remaining(deadline)
    return raw


@dataclass(frozen=True, slots=True, repr=False)
class UnixSocketImageArchive:
    """Operator-selected pathname and expected UID; one connection per read.

    Linux peer credentials identify the service process, not a patient. Deploy
    only behind separately verified socket permissions and network isolation.
    """
    socket_path: str
    expected_peer_uid: int
    timeout_seconds: float = 5.0
    capacity: ArchiveReadCapacity = field(default_factory=ArchiveReadCapacity, kw_only=True)

    def __post_init__(self) -> None:
        path = self.socket_path
        timeout = self.timeout_seconds
        valid = (
            type(path) is str and path.startswith("/") and 1 < len(path) <= 107
            and all(32 <= ord(char) <= 126 for char in path)
            and type(self.expected_peer_uid) is int and 0 <= self.expected_peer_uid < 2**32 - 1
            and type(timeout) in (int, float) and 0.05 <= timeout <= 30 and math.isfinite(timeout)
            and type(getattr(socket, "SO_PEERCRED", None)) is int
            and hasattr(socket, "AF_UNIX")
            and type(self.capacity) is ArchiveReadCapacity
        )
        if not valid:
            raise ValueError("Invalid archive transport configuration")

    def read(self, study_uid: str, series_uid: str, sop_uid: str) -> bytes:
        """Retrieve one bounded replica; custody/clinical validation is caller-owned."""
        admitted = False
        try:
            for uid in (study_uid, series_uid, sop_uid):
                if type(uid) is not str or not 3 <= len(uid) <= 64 or _UID.fullmatch(uid) is None:
                    raise ValueError()
            # No queue: excess callers leave before opening an upstream socket.
            admitted = self.capacity._slots.acquire(blocking=False)
            if not admitted:
                raise ValueError()
            path = f"/studies/{study_uid}/series/{series_uid}/instances/{sop_uid}".encode("ascii")
            request = (b"GET " + path + b" HTTP/1.1\r\nHost: oi-archive\r\n"
                       b'Accept: multipart/related; type="application/dicom", application/dicom\r\n'
                       b"Accept-Encoding: identity\r\nConnection: close\r\n\r\n")
            deadline = time.monotonic() + self.timeout_seconds
            with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as sock:
                sock.settimeout(_remaining(deadline))
                sock.connect(self.socket_path)
                credential_size = struct.calcsize("=iII")
                _, peer_uid, _ = struct.unpack("=iII", sock.getsockopt(
                    socket.SOL_SOCKET, socket.SO_PEERCRED, credential_size))
                if peer_uid != self.expected_peer_uid:
                    raise ValueError()
                sock.settimeout(_remaining(deadline))
                sock.sendall(request)
                return _receive(sock, deadline, path)
        except (OSError, ValueError, OverflowError, struct.error):
            pass
        finally:
            # The socket context has exited, including on timeout or cancellation.
            # Rejected callers must never release another read's capacity.
            if admitted:
                self.capacity._slots.release()
        # Outside the except block: no retained upstream exception context.
        raise ArchiveTransportError("Archive transport unavailable")
