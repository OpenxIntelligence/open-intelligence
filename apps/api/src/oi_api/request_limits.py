"""Bound patient command bodies before JSON parsing, including chunked HTTP."""

import asyncio
import math
import re
from threading import Lock
from time import monotonic

from starlette.responses import JSONResponse


COMMAND_METHODS = frozenset({"POST", "PUT", "PATCH", "DELETE"})
DEFAULT_COMMANDS_PER_MINUTE = 240
_CASE = r"/v1/patients/[^/]+/cases/[^/]+/"
# Larger envelopes apply only to existing POST transports. New commands inherit
# 16 KiB until their wire payload and boundary tests justify an exception.
_UPLOAD_LIMITS = (
    (re.compile(_CASE + r"sources/[^/]+/images"), 2_097_152),
    # A non-BMP character can occupy twelve bytes in an escaped JSON string.
    (re.compile(_CASE + r"laboratory/fhir-r4/(?:preview|sources)"), 800_000),
    (re.compile(_CASE + r"documents(?:/preview|/[^/]+/annotations)?"), 262_144),
    (re.compile(_CASE + r"questions/[^/]+/evidence"), 210_000),
    (re.compile(_CASE + r"sources"), 72_000),
)


class PatientRequestLimit:
    def __init__(self, app, *, commands_per_minute=DEFAULT_COMMANDS_PER_MINUTE):
        self.app = app
        self._capacity = commands_per_minute
        self._tokens = float(commands_per_minute)
        self._updated = None
        self._lock = Lock()

    def _retry_after(self):
        # One bucket per app process; no caller-controlled keys or stored identities.
        with self._lock:
            now = monotonic()
            if self._updated is not None:
                refill = (now - self._updated) * self._capacity / 60
                self._tokens = min(self._capacity, self._tokens + refill)
            self._updated = now
            if self._tokens < 1:
                return max(1, math.ceil((1 - self._tokens) * 60 / self._capacity))
            self._tokens -= 1
            return 0

    async def __call__(self, scope, receive, send):
        route = scope.get("path", "")
        if (scope["type"] != "http" or scope["method"] not in COMMAND_METHODS
                or not (route == "/v1/patients" or route.startswith("/v1/patients/"))):
            await self.app(scope, receive, send)
            return

        async def reject(code, detail, extra_headers=None):
            headers = {"Cache-Control": "no-store", **(extra_headers or {})}
            if scope.get("http_version", "1.1") in {"1.0", "1.1"}:
                headers["Connection"] = "close"
            await JSONResponse({"detail": detail}, status_code=code, headers=headers)(scope, receive, send)

        retry_after = self._retry_after()
        if retry_after:
            await reject(429, "Patient command rate limit reached", {"Retry-After": str(retry_after)})
            return

        limit = 16_384
        if scope["method"] == "POST":
            for pattern, upload_limit in _UPLOAD_LIMITS:
                if pattern.fullmatch(route):
                    limit = upload_limit
                    break
        lengths = [value for name, value in scope["headers"] if name.lower() == b"content-length"]
        if lengths:
            if len(lengths) != 1 or not lengths[0].isdigit():
                await reject(400, "Invalid request")
                return
            # Compare decimal bytes so even adversarially long headers have a bounded conversion.
            digits = lengths[0].lstrip(b"0")
            if len(digits) > len(str(limit)) or int(digits or b"0") > limit:
                await reject(413, "Request body too large")
                return
        content = bytearray()
        try:
            async with asyncio.timeout(5):
                while True:
                    message = await receive()
                    if message["type"] == "http.disconnect":
                        return
                    chunk = message.get("body", b"")
                    if len(content) + len(chunk) > limit:
                        await reject(413, "Request body too large")
                        return
                    content.extend(chunk)
                    if not message.get("more_body", False):
                        break
        except TimeoutError:
            await reject(408, "Request body timed out")
            return

        delivered = False

        async def bounded_receive():
            nonlocal delivered
            if not delivered:
                delivered = True
                return {"type": "http.request", "body": bytes(content), "more_body": False}
            return await receive()

        await self.app(scope, bounded_receive, send)
