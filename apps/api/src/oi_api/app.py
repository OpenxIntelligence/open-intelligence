"""Local synthetic composition root; no domain migration or authority implied."""

import ipaddress
from contextlib import asynccontextmanager
from urllib.parse import urlsplit

from fastapi import FastAPI, Request, Response
from fastapi.responses import JSONResponse

from . import __version__
from .config import Settings
from .contracts import Liveness, Readiness, VersionManifest
from .database import Database


def _loopback_host(host: str) -> bool:
    try:
        parsed = urlsplit("//" + host)
        if parsed.username or parsed.password or parsed.path or parsed.query or parsed.fragment:
            return False
        parsed.port  # Validate an optional numeric port.
        if parsed.hostname == "localhost":
            return True
        return ipaddress.ip_address(parsed.hostname or "").is_loopback
    except ValueError:
        return False


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings if settings is not None else Settings.from_env()
    database = Database(settings)

    @asynccontextmanager
    async def lifespan(app):
        yield
        database.close()

    app = FastAPI(
        title="Open Intelligence H1 API",
        version=__version__,
        description="Local synthetic infrastructure shell. No authentication or patient operations are implemented.",
        lifespan=lifespan,
        openapi_url="/v1/openapi.json",
        docs_url=None,
        redoc_url=None,
    )

    @app.middleware("http")
    async def local_boundary(request: Request, call_next):
        hosts = request.headers.getlist("host")
        if len(hosts) != 1 or not _loopback_host(hosts[0]):
            return JSONResponse(
                status_code=400, content={"detail": "Loopback Host required"},
                headers={"Cache-Control": "no-store"},
            )
        response = await call_next(request)
        response.headers["Cache-Control"] = "no-store"
        return response

    @app.get("/health", response_model=Liveness, operation_id="liveness_v1")
    def health():
        return Liveness()

    @app.get("/health/ready", response_model=Readiness, operation_id="readiness_v1",
             responses={503: {"model": Readiness, "description": "Database dependency is not ready"}})
    def ready(response: Response):
        state = database.check()
        is_ready = state.status == "ready"
        response.status_code = 200 if is_ready else 503
        return Readiness(status="ready" if is_ready else "not_ready", database=state)

    @app.get("/v1", response_model=VersionManifest, operation_id="version_v1")
    def version():
        return VersionManifest()

    return app
