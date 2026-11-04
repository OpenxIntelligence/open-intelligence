"""Supervisor for bounded, separately executed PDF text extraction.

The existing CaseStore owns originals and reviewed assertions. This adapter
returns a derived rendition only and never creates facts or clinical approval.
"""
from __future__ import annotations

import json
import os
from pathlib import Path
import selectors
import signal
import subprocess
import sys
import threading
import time

from .store import InvalidInput
from .pdf_worker import (MAX_OUTPUT_BYTES, WALL_SECONDS, PdfRejected,
                         canonical_json, make_rendition, validate_input)

_WORKER_SLOT = threading.BoundedSemaphore(1)
_ERRORS = {
    "input": "PDF must be nonempty bytes, at most 64 KiB",
    "invalid": "PDF is malformed or could not be safely extracted",
    "encrypted": "This intake does not support encrypted PDFs",
    "unsupported": "PDF requires unsupported features or optional dependencies",
    "unextractable": "Every nonblank page must have extractable text; image-only or unreadable pages are unsupported",
    "limits": "PDF exceeds the page, text, line, or resource limits",
    "version": "PDF extraction requires the exact pinned pypdf 6.21.4 installation",
    "unavailable": "PDF worker resource isolation is unavailable on this platform",
    "time": "PDF extraction exceeded its time limit",
    "output": "PDF extraction exceeded its bounded output limit",
    "busy": "PDF extraction is busy; try again",
}


def _worker_command() -> list[str]:
    return [sys.executable, "-I", "-B", "-u", str(Path(__file__).with_name("pdf_worker.py").resolve())]


def _run_worker(raw: bytes) -> tuple[int, bytes]:
    """Bound stdin, stdout, time and process lifetime without communicate buffers."""
    if os.name != "posix":
        raise PdfRejected("unavailable")
    process = None
    selector = selectors.DefaultSelector()
    completed = False
    output = bytearray()
    try:
        process = subprocess.Popen(
            _worker_command(), stdin=subprocess.PIPE, stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL, start_new_session=True, close_fds=True,
            env={"LANG": "C.UTF-8", "LC_ALL": "C.UTF-8"},
        )
        deadline = time.monotonic() + WALL_SECONDS
        os.set_blocking(process.stdin.fileno(), False)
        os.set_blocking(process.stdout.fileno(), False)
        selector.register(process.stdin, selectors.EVENT_WRITE, "stdin")
        selector.register(process.stdout, selectors.EVENT_READ, "stdout")
        offset = 0
        while selector.get_map():
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                raise PdfRejected("time")
            for key, _ in selector.select(min(remaining, 0.2)):
                if key.data == "stdin":
                    try:
                        offset += os.write(key.fd, raw[offset:offset + 16384])
                    except BrokenPipeError:
                        offset = len(raw)
                    except BlockingIOError:
                        continue
                    if offset == len(raw):
                        selector.unregister(key.fileobj)
                        key.fileobj.close()
                else:
                    try:
                        chunk = os.read(key.fd, min(16384, MAX_OUTPUT_BYTES + 1 - len(output)))
                    except BlockingIOError:
                        continue
                    if not chunk:
                        selector.unregister(key.fileobj)
                        key.fileobj.close()
                    else:
                        output.extend(chunk)
                        if len(output) > MAX_OUTPUT_BYTES:
                            raise PdfRejected("output")
        try:
            returncode = process.wait(timeout=max(0.001, deadline - time.monotonic()))
        except subprocess.TimeoutExpired:
            raise PdfRejected("time") from None
        completed = True
        return returncode, bytes(output)
    except OSError:
        raise PdfRejected("unavailable") from None
    finally:
        selector.close()
        if process is not None:
            if not completed:
                try:
                    os.killpg(process.pid, signal.SIGKILL)
                except ProcessLookupError:
                    pass
                process.wait()
            for stream in (process.stdin, process.stdout):
                if stream is not None:
                    stream.close()


def extract_pdf(raw: bytes) -> dict:
    """Extract with a fresh, exact-version worker; reject incomplete results."""
    acquired = False
    try:
        validate_input(raw)
        acquired = _WORKER_SLOT.acquire(timeout=1)
        if not acquired:
            raise PdfRejected("busy")
        returncode, output = _run_worker(raw)
        try:
            value = json.loads(output)
        except (UnicodeError, ValueError, RecursionError):
            raise PdfRejected("invalid") from None
        if isinstance(value, dict) and set(value) == {"error"}:
            code = value["error"]
            raise PdfRejected(code if isinstance(code, str) and code in _ERRORS else "invalid")
        if returncode != 0 or not isinstance(value, dict):
            raise PdfRejected("limits" if returncode < 0 else "invalid")
        pages = value.get("pages")
        if (not isinstance(pages, list) or
                any(not isinstance(page, dict) or not isinstance(page.get("text"), str) for page in pages)):
            raise PdfRejected("invalid")
        # Re-derive all page hashes, global indices, descriptor and fingerprint.
        # This also rejects additional fields or worker-side partial/protocol data.
        expected = make_rendition([page["text"] for page in pages])
        try:
            matches = canonical_json(value) == canonical_json(expected)
        except (UnicodeError, ValueError, RecursionError):
            raise PdfRejected("invalid") from None
        if not matches:
            raise PdfRejected("invalid")
        return expected
    except PdfRejected as error:
        raise InvalidInput(_ERRORS.get(str(error), _ERRORS["invalid"])) from None
    finally:
        if acquired:
            _WORKER_SLOT.release()
