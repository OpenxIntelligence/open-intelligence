import json
import subprocess
import sys
import unittest
from datetime import datetime, timezone
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

    def test_retrieval_time_rejects_invalid_or_ambiguous_provenance(self):
        invalid = [
            "", False, 0, [], "not-a-date", "2026-11-03", "2026-11-03T10:00:00",
            "2026-02-30T10:00:00Z", "2025-02-29T10:00:00Z",
            "2026-11-03T10:00:00+01:99", "2026-11-03T10:00:00+24:00",
            "2026-11-03T10:00:00-00:00", "2026-11-03T10:00:00Z\n",
            "2026-11-03\n10:00:00+00:00", "2026-11-03T10:00:00\x00+00:00",
            "2026-11-03T10:00:00.1234567Z", "2026-11-03T10:00Z",
        ]
        for timestamp in invalid:
            with self.subTest(timestamp=timestamp):
                with self.assertRaisesRegex(MetadataInputError, "retrieval timestamp"):
                    project_work(fixture(), DOI, retrieved_at=timestamp)

    def test_retrieval_time_preserves_valid_explicit_time_and_offset(self):
        for timestamp in ("2024-02-29T23:59:59Z", "2026-11-03T10:00:00+05:45",
                          "2026-11-03T10:00:00.123456-04:00", "2026-11-03T10:00:00+00:00"):
            with self.subTest(timestamp=timestamp):
                record = project_work(fixture(), DOI, retrieved_at=timestamp)
                self.assertEqual(record["source"]["retrieved_at"], timestamp)

    def test_omitted_retrieval_time_is_aware_current_utc(self):
        before = datetime.now(timezone.utc).replace(microsecond=0)
        record = project_work(fixture(), DOI)
        actual = datetime.fromisoformat(record["source"]["retrieved_at"])
        self.assertEqual(actual.utcoffset().total_seconds(), 0)
        self.assertLessEqual(before, actual)
        self.assertLessEqual(actual, datetime.now(timezone.utc))

    def test_live_duplicate_keys_do_not_silently_choose_one_identity(self):
        raw = json.dumps(fixture()).replace(
            '"DOI":', '"DOI": "10.5555/CONFLICTING-IDENTITY", "DOI":', 1)
        with self.assertRaisesRegex(MetadataInputError, "Malformed Crossref JSON") as error:
            fetch_public_doi(DOI, opener=_CaptureTransport(raw.encode()))
        self.assertNotIn("CONFLICTING-IDENTITY", str(error.exception))

    def test_live_nonstandard_json_constants_fail_closed(self):
        for constant in ("NaN", "Infinity", "-Infinity"):
            with self.subTest(constant=constant):
                raw = json.dumps(fixture())[:-1] + ', "untrusted": ' + constant + '}'
                with self.assertRaisesRegex(MetadataInputError, "Malformed Crossref JSON"):
                    fetch_public_doi(DOI, opener=_CaptureTransport(raw.encode()))

    def test_media_type_is_exact_not_a_substring(self):
        class Transport:
            def __init__(self, content_type):
                self.content_type = content_type
            def open(self, *args, **kwargs):
                return _FakeResponse(json.dumps(fixture()).encode(), self.content_type)
        for content_type in ("text/html; hint=application/json", "application/jsonp", "x-application/json"):
            with self.subTest(content_type=content_type):
                with self.assertRaisesRegex(MetadataInputError, "did not return JSON"):
                    fetch_public_doi(DOI, opener=Transport(content_type))
        result = fetch_public_doi(DOI, opener=Transport("Application/JSON; charset=utf-8"))
        self.assertEqual(result["doi"], DOI)

    def test_cli_fixture_rejects_ambiguous_json_without_printing_payload(self):
        import tempfile
        raw = json.dumps(fixture()).replace('"title":', '"title": ["UNTRUSTED-PAYLOAD"], "title":', 1)
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "ambiguous.json"
            path.write_text(raw)
            process = subprocess.run([sys.executable, "-m", "tools.crossref_metadata", DOI,
                                      "--fixture", str(path)], capture_output=True, text=True)
        self.assertNotEqual(process.returncode, 0)
        self.assertEqual(process.stdout, "")
        self.assertIn("Malformed Crossref JSON", process.stderr)
        self.assertNotIn("UNTRUSTED-PAYLOAD", process.stderr)


if __name__ == "__main__":
    unittest.main()
