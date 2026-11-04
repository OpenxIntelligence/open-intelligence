"""Bound the small identity command before JSON parsing, including chunked HTTP."""

import asyncio

from starlette.responses import JSONResponse


class PatientRequestLimit:
    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        route = scope.get("path", "")
        bounded = route == "/v1/patients" or (
            route.startswith("/v1/patients/") and (
                route.endswith("/record-requests") or route.endswith("/case-bindings") or route.endswith("/sources") or
                route.endswith("/questions") or route.endswith("/composer/source-preflight") or
                route.endswith("/documents") or "/documents/" in route or
                ("/questions/" in route and route.endswith("/return-for-verification")) or
                ("/questions/" in route and route.endswith("/brief")) or
                ("/questions/" in route and route.endswith("/followthrough")) or
                ("/questions/" in route and route.endswith(("/evidence-search", "/evidence-links"))) or
                ("/followthrough/" in route and route.endswith("/transitions")) or
                ("/questions/" in route and route.endswith(("/evidence", "/evidence-assessments", "/evidence-reports"))) or
                ("/questions/" in route and "/evidence/" in route and route.endswith("/withdraw")) or
                ("/record-requests/" in route and route.endswith("/cancel")) or
                ("/case-bindings/" in route and route.endswith("/revoke"))
            )
        )
        if scope["type"] != "http" or scope["method"] != "POST" or not bounded:
            await self.app(scope, receive, send)
            return

        async def reject(code, detail):
            response = JSONResponse({"detail": detail}, status_code=code,
                                    headers={"Cache-Control": "no-store", "Connection": "close"})
            await response(scope, receive, send)

        headers = dict(scope["headers"])
        length = headers.get(b"content-length")
        if length is not None:
            try:
                if int(length) < 0:
                    raise ValueError()
                if int(length) > (210_000 if route.endswith('/evidence') else 262_144 if '/documents' in route else 72_000 if route.endswith('/sources') else 16_384):
                    await reject(413, "Request body too large")
                    return
            except ValueError:
                await reject(400, "Invalid request")
                return
        content = bytearray()
        try:
            async with asyncio.timeout(5):
                while True:
                    message = await receive()
                    if message["type"] == "http.disconnect":
                        return
                    chunk = message.get("body", b"")
                    if len(content) + len(chunk) > (210_000 if route.endswith('/evidence') else 262_144 if '/documents' in route else 72_000 if route.endswith('/sources') else 16_384):
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
