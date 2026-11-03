"""Explicit test-only Unix-socket archive for existing restored HTTP acceptance.

The bounded file fixture and exact two-object manifest remain the backing source.
The same-process/same-UID socket peer exercises #351's actual transport, not a
production gateway, independent identity isolation or external-archive backup.
Only verify_images_compose.py mounts this module; the runtime image excludes it.
"""
from contextlib import asynccontextmanager, contextmanager
import json
import os
from pathlib import Path
import re
import socket
import socketserver
import struct
import tempfile
import threading
import time


MAX_IMAGE_BYTES = 2_097_152
ARCHIVE_DIRECTORY = Path("/run/oi-acceptance-archive")
ARCHIVE_CALLS = Path("/run/oi-acceptance-archive-calls.jsonl")


class AcceptanceArchive:
    def __init__(self, directory: Path, calls: Path):
        self.directory = directory
        self.calls = calls
        manifest = json.loads((directory / "manifest.json").read_text())
        if (manifest.get("contract") != "oi.synthetic-archive-acceptance/1"
                or manifest.get("independently_authored") is not True
                or len(manifest.get("objects", [])) != 2):
            raise ValueError("Invalid fictional archive manifest")
        self.objects = {}
        for item in manifest["objects"]:
            identifiers = tuple(item[key] for key in ("study_uid", "series_uid", "sop_uid"))
            filename = item["filename"]
            if (any(type(value) is not str or re.fullmatch(r"[0-9.]{1,64}", value) is None
                    for value in identifiers)
                    or type(filename) is not str
                    or re.fullmatch(r"[0-9]{2}\.dcm", filename) is None
                    or identifiers in self.objects):
                raise ValueError("Invalid fictional archive entry")
            self.objects[identifiers] = filename

    def read(self, study_uid, series_uid, sop_uid):
        identifiers = (study_uid, series_uid, sop_uid)
        filename = self.objects[identifiers]
        # Only synthetic server-owned identifiers enter this bounded trace.
        # Never record credentials, application request URLs or original bytes.
        with self.calls.open("a", encoding="utf-8") as stream:
            stream.write(json.dumps(dict(zip(
                ("study_uid", "series_uid", "sop_uid"), identifiers)), sort_keys=True) + "\n")
        with (self.directory / filename).open("rb") as stream:
            raw = stream.read(MAX_IMAGE_BYTES + 1)
        if not raw or len(raw) > MAX_IMAGE_BYTES:
            raise ValueError("Fictional archive object exceeds its bound")
        # Deliberately do not repair or substitute damaged fixture bytes. The
        # application's existing custody owner must reject any discrepancy.
        return raw


_MAX_REQUEST = 1024
_UID = rb"(?:0|[1-9][0-9]*)(?:\.(?:0|[1-9][0-9]*))+"
_REQUEST = re.compile(
    rb"GET /studies/(" + _UID + rb")/series/(" + _UID + rb")/instances/(" + _UID + rb") HTTP/1.1\r\n"
    rb"Host: oi-archive\r\n"
    rb'Accept: multipart/related; type="application/dicom", application/dicom\r\n'
    rb"Accept-Encoding: identity\r\nConnection: close\r\n\r\n"
)
_FAILURE = b"HTTP/1.1 503 Unavailable\r\nContent-Length: 0\r\nConnection: close\r\n\r\n"


@contextmanager
def socket_archive_service(reader, socket_path: str):
    """Serve one bounded exact-profile request at a time; close before return."""
    expected_uid = os.getuid()

    class Handler(socketserver.BaseRequestHandler):
        def handle(self):
            conn = self.request
            try:
                size = struct.calcsize("=iII")
                _, uid, _ = struct.unpack("=iII", conn.getsockopt(socket.SOL_SOCKET, socket.SO_PEERCRED, size))
                if uid != expected_uid:
                    return
                deadline = time.monotonic() + 2.0
                request = bytearray()
                while b"\r\n\r\n" not in request:
                    remaining = deadline - time.monotonic()
                    if remaining <= 0 or len(request) >= _MAX_REQUEST:
                        raise ValueError()
                    conn.settimeout(remaining)
                    chunk = conn.recv(_MAX_REQUEST + 1 - len(request))
                    if not chunk:
                        raise ValueError()
                    request.extend(chunk)
                if len(request) > _MAX_REQUEST:
                    raise ValueError()
                match = _REQUEST.fullmatch(request)
                if match is None or any(not 3 <= len(uid) <= 64 for uid in match.groups()):
                    raise ValueError()
                # The original file fixture records only these canonical IDs.
                # It deliberately returns changed bytes unchanged so custody
                # remains responsible for rejecting a corrupt replica.
                raw = reader.read(*(value.decode("ascii") for value in match.groups()))
                if type(raw) is not bytes or not 0 < len(raw) <= MAX_IMAGE_BYTES:
                    raise ValueError()
                conn.settimeout(2.0)
                conn.sendall(b"HTTP/1.1 200 OK\r\nContent-Type: application/dicom\r\n"
                             b"Content-Length: " + str(len(raw)).encode("ascii")
                             + b"\r\nConnection: close\r\n\r\n" + raw)
            except Exception:
                # Do not echo filenames, identifiers, request bodies or errors.
                try:
                    conn.settimeout(0.2)
                    conn.sendall(_FAILURE)
                except OSError:
                    pass

    class Server(socketserver.UnixStreamServer):
        request_queue_size = 4

        def handle_error(self, request, client_address):
            # Handler failures cannot put private values in CI/container logs.
            pass

    # A private TemporaryDirectory belongs to the factory/calling test. Refuse
    # an occupied path instead of deleting another listener before bind.
    server = Server(socket_path, Handler)
    thread = threading.Thread(target=server.serve_forever, kwargs={"poll_interval": 0.05})
    started = False
    try:
        thread.start()
        started = True
        yield
    finally:
        if started:
            server.shutdown()
            thread.join(3)
        server.server_close()
        Path(socket_path).unlink(missing_ok=True)
        if started and thread.is_alive():
            raise RuntimeError("Synthetic archive listener did not stop")


def create_acceptance_app():
    """Explicit acceptance factory; no application setting activates this."""
    # Defer application imports so the protocol fixture has stdlib-only tests.
    from oi_api.app import create_app
    from oi_api.archive_socket import UnixSocketImageArchive

    directory = tempfile.TemporaryDirectory(prefix="oi-recovery-socket-")
    try:
        backing = AcceptanceArchive(ARCHIVE_DIRECTORY, ARCHIVE_CALLS)
        socket_path = str(Path(directory.name) / "archive.sock")
        archive = UnixSocketImageArchive(socket_path, expected_peer_uid=os.getuid())
        app = create_app(image_archive=archive)
    except BaseException:
        directory.cleanup()
        raise
    previous_lifespan = app.router.lifespan_context

    @asynccontextmanager
    async def lifespan(application):
        try:
            with socket_archive_service(backing, socket_path):
                async with previous_lifespan(application) as state:
                    yield state
        finally:
            directory.cleanup()

    app.router.lifespan_context = lifespan
    return app
