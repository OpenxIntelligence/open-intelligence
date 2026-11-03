"""Independent local Unix-socket responder; no external service or patient data."""
from contextlib import contextmanager
from pathlib import Path
import socket
import tempfile
import threading


def http_response(body: bytes, *, content_type: bytes = b"application/dicom",
                  status: bytes = b"200 OK", extra: bytes = b"") -> bytes:
    return (b"HTTP/1.1 " + status + b"\r\nContent-Type: " + content_type
            + b"\r\nContent-Length: " + str(len(body)).encode("ascii")
            + b"\r\n" + extra + b"\r\n" + body)


def multipart_body(body: bytes, *, boundary: bytes = b"oi-boundary",
                   extra: bytes = b"") -> bytes:
    return (b"--" + boundary + b"\r\nContent-Type: application/dicom\r\n"
            + extra + b"\r\n" + body + b"\r\n--" + boundary + b"--\r\n")


@contextmanager
def archive_server(response=None, *, handler=None):
    """Each accepted connection has bounded lifetime and is reaped on exit.

    The handler receives the real connected socket and full recorded request.
    Ordinary server termination supplies EOF; fault handlers may deliberately
    delay, truncate or disconnect. Peer-UID refusal sends no request at all.
    """
    with tempfile.TemporaryDirectory(prefix="oi-arc-") as directory:
        path = str(Path(directory) / "archive.sock")
        listener = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        listener.bind(path)
        listener.listen(32)
        listener.settimeout(0.05)
        stop = threading.Event()
        requests, errors, workers = [], [], []

        def serve(conn):
            try:
                with conn:
                    conn.settimeout(1.0)
                    request = bytearray()
                    while b"\r\n\r\n" not in request:
                        part = conn.recv(1024)
                        if not part:
                            return
                        request.extend(part)
                        if len(request) > 16384:
                            raise AssertionError("unbounded test request")
                    requests.append(bytes(request))
                    if handler is not None:
                        handler(conn, bytes(request))
                    else:
                        conn.sendall(response)
            except (BrokenPipeError, ConnectionResetError):
                # Expected when a bounded client rejects/truncates a response.
                pass
            except Exception as error:
                errors.append(error)

        def accept():
            while not stop.is_set():
                try:
                    conn, _ = listener.accept()
                except socket.timeout:
                    continue
                except OSError:
                    if stop.is_set():
                        return
                    raise
                worker = threading.Thread(target=serve, args=(conn,))
                workers.append(worker)
                worker.start()

        thread = threading.Thread(target=accept)
        thread.start()
        try:
            yield path, requests
        finally:
            stop.set()
            thread.join(2)
            listener.close()
            for worker in workers:
                worker.join(2)
            if thread.is_alive() or any(w.is_alive() for w in workers):
                raise AssertionError("archive responder did not stop")
            if errors:
                raise AssertionError("archive responder failed") from errors[0]
