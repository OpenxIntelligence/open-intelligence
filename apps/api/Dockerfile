# Synthetic H1 development image. Python/OS/container layers have separate
# provenance and licensing obligations; the application lock does not clear them.
# Patch tag verified against docker-library/official-images on 2026-11-02.
# This tag is not a digest pin. CI records the resolved image identity.
FROM python:3.12.16-slim-bookworm

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PYTHONPATH=/app/src:/app/domain

WORKDIR /app
COPY apps/api/requirements.lock apps/api/dependency-license-inventory.json apps/api/THIRD_PARTY_NOTICES.md ./
COPY apps/api/tools/check_dependencies.py ./tools/check_dependencies.py
COPY apps/api/tools/prepare_dependencies.py apps/api/tools/pydicom_runtime.py apps/api/tools/pydicom-runtime.json apps/api/tools/pydicom-upstream.lock ./tools/

# The optional BuildKit secret supports managed development proxies without
# copying their CA into an image layer or disabling certificate verification.
RUN --mount=type=secret,id=proxy_ca \
    if [ -f /run/secrets/proxy_ca ]; then export PIP_CERT=/run/secrets/proxy_ca; fi; \
    python tools/prepare_dependencies.py --wheel-dir /tmp/oi-h1-wheels \
    && python tools/check_dependencies.py --wheel-dir /tmp/oi-h1-wheels --sbom /app/dependency-sbom.json \
    && python -m pip install --no-cache-dir --force-reinstall --no-deps --require-hashes --no-index --find-links /tmp/oi-h1-wheels -r requirements.lock \
    && python -m pip check \
    && rm -rf /tmp/oi-h1-wheels

COPY apps/api/alembic.ini ./alembic.ini
COPY apps/api/migrations ./migrations
COPY apps/api/src ./src
COPY src/open_intelligence ./domain/open_intelligence
USER 10001:10001

EXPOSE 8000

# Migrations are an explicit, separate command. Serving never creates schemas.
# Compose publishes this container listener on host 127.0.0.1 only.
CMD ["python", "-m", "uvicorn", "oi_api.app:create_app", "--factory", "--host", "0.0.0.0", "--port", "8000", "--no-access-log", "--no-proxy-headers"]
