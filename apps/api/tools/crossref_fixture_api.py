"""Disposable acceptance factory with a fictional Crossref protocol transport.

The patient API, authorization, source/evidence stores and PostgreSQL are real.
Only the external provider is replaced. This verification utility is not copied
into the application image and has no fallback to a network provider.
"""
from dataclasses import replace
import json
import os
from pathlib import Path

from open_intelligence.crossref_metadata import MAX_BYTES, project_work
from oi_api.app import create_app
from oi_api.config import Settings


def create_fixture_app():
    if os.environ.get("OI_CROSSREF_FIXTURE_VERIFICATION") != "1":
        raise RuntimeError("Explicit disposable protocol verification required")
    source = Path(os.environ["OI_CROSSREF_PROTOCOL_FIXTURE_PATH"])
    if not source.is_absolute():
        raise RuntimeError("Absolute independently authored fixture path required")
    settings = Settings.from_env()

    def fixture_lookup(doi):
        raw = source.read_bytes()
        if len(raw) > MAX_BYTES:
            raise ValueError("Protocol fixture exceeds the provider boundary")
        return project_work(json.loads(raw), doi)

    return create_app(
        replace(settings, crossref_enabled=True),
        crossref_fetcher=fixture_lookup,
        crossref_acquisition_mode="protocol_fixture",
    )
