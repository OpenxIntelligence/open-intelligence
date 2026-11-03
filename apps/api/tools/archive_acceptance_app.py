"""Explicit test-only archive injection for the existing Compose acceptance.

This module is mounted only by verify_images_compose.py; it is not copied into
the runtime image or enabled by application settings. The two fictional objects
live outside PostgreSQL so restored HTTP can prove that the archive port ran.
It is a bounded file fixture, not a PACS, network adapter or backup mechanism.
"""

import json
from pathlib import Path
import re

from oi_api.app import create_app


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


def create_acceptance_app():
    return create_app(image_archive=AcceptanceArchive(ARCHIVE_DIRECTORY, ARCHIVE_CALLS))
