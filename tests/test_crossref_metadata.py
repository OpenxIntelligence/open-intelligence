import json
import subprocess
import sys
import unittest
from pathlib import Path
from urllib.error import HTTPError

from tools.crossref_metadata import (
    MAX_BYTES, MetadataInputError, fetch_public_doi, normalize_doi, project_work,
)

FIXTURE = Path(__file__).resolve().parents[1] / "examples" / "synthetic" / "crossref-metadata-fixture.json"
DOI = "10.5555/oi-synthetic-001"


def fixture():
    return json.loads(FIXTURE.read_text(encoding="utf-8"))


class _FakeResponse:
    def __init__(self, body, content_type="application/json"):
        self.headers = {"Content-Type": content_type}
        self.body = body
        self.pos = 0
    def read(self, size):
        return self.body[:size]
    def __enter__(self):
        return self
    def __exit__(self, *args):
        return False


class _CaptureTransport:
    def __init__(self, raw):
        self.raw = raw
        self.requests = []
    def open(self, request, timeout):
        self.requests.append((request, timeout))
        return _FakeResponse(self.raw)


class CrossrefMetadataTests(unittest.TestCase):
    def test_fixture_keeps_only_auditable_bibliographic_fields(self):
        record = project_work(fixture(), DOI, retrieved_at="2026-10-31T16:00:00+00:00")
        self.assertEqual(record["kind"], "bibliographic_metadata_only")
        self.assertEqual(record["doi"], DOI)
        self.assertEqual(record["year"], 2026)
        self.assertEqual(record["authors"], ["Ari Example", "Rin Invented"])
        self.assertFalse(record["clinical_evidence_appraised"])
        serialized = json.dumps(record)
        for private in ("COPYRIGHTED ABSTRACT", "untrusted-link", "paywalled", "full-text-unlicensed", "article-license"):
            self.assertNotIn(private, serialized)
        self.assertEqual(record["canonical_url"], "https://doi.org/10.5555%2Foi-synthetic-001")
        self.assertEqual(record["source"]["record_url"], "https://api.crossref.org/works/10.5555%2Foi-synthetic-001")

    def test_rejects_identity_mismatch_and_invalid_doi(self):
        changed = fixture()
        changed["message"]["DOI"] = "10.5555/another-item"
        with self.assertRaisesRegex(MetadataInputError, "does not match"):
            project_work(changed, DOI)
        for doi in ("Alpha lung cancer", "../10.1000/x", "10.5555/x?patient=abc", "10.5555/ü",
                    "10.55/x", "", "10.5555/x#fragment"):
            with self.subTest(doi=doi):
                with self.assertRaises(MetadataInputError):
                    normalize_doi(doi)

    def test_rejects_malformed_envelopes_and_unbounded_content(self):
        for data in ({}, {"status":"ok","message":[]}, {"status":"error","message":{}}):
            with self.assertRaises(MetadataInputError):
                project_work(data, DOI)
        changed = fixture()
        changed["message"]["title"] = []
        with self.assertRaisesRegex(MetadataInputError, "title"):
            project_work(changed, DOI)
        changed = fixture()
        changed["message"]["author"] = [{}] * 101
        with self.assertRaisesRegex(MetadataInputError, "Too many authors"):
            project_work(changed, DOI)

    def test_explicit_live_fetch_uses_fixed_endpoint_only(self):
        transport = _CaptureTransport(json.dumps(fixture()).encode())
        result = fetch_public_doi(DOI, opener=transport)
        self.assertEqual(result["doi"], DOI)
        self.assertEqual(len(transport.requests), 1)
        request, timeout = transport.requests[0]
        self.assertEqual(request.full_url, "https://api.crossref.org/works/10.5555%2Foi-synthetic-001")
        self.assertEqual(timeout, 8)
        self.assertIn("OpenIntelligenceMetadataPrototype", request.get_header("User-agent"))
        transport = _CaptureTransport(json.dumps(fixture()).encode())
        fetch_public_doi(DOI, contact="operator@example.org", opener=transport)
        self.assertIn("mailto=operator%40example.org", transport.requests[0][0].full_url)
        with self.assertRaises(MetadataInputError):
            fetch_public_doi(DOI, contact="invalid@@example", opener=transport)

    def test_bad_response_type_and_size_fail_closed(self):
        class WrongType:
            def open(self, *args, **kwargs):
                return _FakeResponse(b"<html>wrong</html>", "text/html")
        with self.assertRaisesRegex(MetadataInputError, "did not return JSON"):
            fetch_public_doi(DOI, opener=WrongType())
        too_big = _CaptureTransport(b"x" * (MAX_BYTES + 1))
        with self.assertRaisesRegex(MetadataInputError, "exceeds"):
            fetch_public_doi(DOI, opener=too_big)

    def test_cli_fixture_never_needs_network(self):
        process = subprocess.run([sys.executable, "-m", "tools.crossref_metadata", DOI,
                                  "--fixture", str(FIXTURE)], capture_output=True, text=True, check=True)
        output = json.loads(process.stdout)
        self.assertEqual(output["doi"], DOI)
        self.assertNotIn("COPYRIGHTED ABSTRACT", process.stdout)


if __name__ == "__main__":
    unittest.main()
