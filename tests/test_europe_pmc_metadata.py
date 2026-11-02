"""Offline contracts for bounded Europe PMC discovery; all records are authored."""

from http.client import IncompleteRead
import json
from pathlib import Path
import subprocess
import sys
import unittest
from unittest.mock import patch
from urllib.error import HTTPError, URLError
from urllib.parse import parse_qs, urlsplit

from tools import europe_pmc_metadata


ROOT = Path(__file__).resolve().parents[1]
SEARCH = {"topic": "melanoma", "page_size": 2}


def provider_fixture():
    # Independently authored protocol fixture, not a real publication or patient.
    return {
        "version": "6.9", "hitCount": 3, "nextCursorMark": "DO-NOT-FOLLOW",
        "request": {"queryString": "DO-NOT-STORE-RAW-QUERY"},
        "resultList": {"result": [{
            "source": "MED", "id": "999000001", "pmid": "999000001",
            "pmcid": "PMC999000001", "doi": "10.5555/oi-test-citation",
            "title": "Authored test citation about melanoma",
            "authorString": "Example A, Invented B.", "journalTitle": "Fictional Test Journal",
            "pubYear": "2025", "firstPublicationDate": "2025-01-01",
            "abstractText": "ABSTRACT-MUST-NOT-PASS", "brSummary": "BOOK-MUST-NOT-PASS",
            "bookOrReportDetails": {"text": "REPORT-MUST-NOT-PASS"},
            "fullTextUrlList": {"fullTextUrl": [{"url": "https://untrusted.example/text"}]},
            "isOpenAccess": "Y", "license": "DO-NOT-INFER-RIGHTS",
            "unknown": "UNKNOWN-MUST-NOT-PASS",
        }]},
    }


class Response:
    def __init__(self, body, content_type="application/json", status=200):
        self.body = body
        self.headers = {"Content-Type": content_type}
        self.status = status
        self.read_sizes = []

    def read(self, size):
        self.read_sizes.append(size)
        return self.body[:size]

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False


class Transport:
    def __init__(self, response):
        self.response = response
        self.requests = []

    def open(self, request, timeout):
        self.requests.append((request, timeout))
        if isinstance(self.response, Exception):
            raise self.response
        return self.response


class EuropePMCMetadataTests(unittest.TestCase):
    def setUp(self):
        self.module = europe_pmc_metadata
        patcher = patch.object(self.module, "_last_request_at", None)
        patcher.start()
        self.addCleanup(patcher.stop)

    def test_projection_excludes_article_content_and_does_not_infer_rights(self):
        result = self.module.project_search(provider_fixture(), SEARCH,
                                            retrieved_at="2026-11-02T12:00:00+00:00")
        self.assertEqual(result["mode"], "live")
        self.assertEqual(result["kind"], "bibliographic_discovery")
        self.assertEqual(result["hit_count"], 3)
        self.assertEqual(result["returned_count"], 1)
        self.assertTrue(result["has_more"])
        item = result["results"][0]
        self.assertEqual(item["id"], "999000001")
        self.assertEqual(item["source"], "MED")
        self.assertEqual(item["title"], "Authored test citation about melanoma")
        self.assertEqual(item["year"], 2025)
        self.assertEqual(item["canonical_url"], "https://europepmc.org/article/MED/999000001")
        self.assertEqual(result["provenance"]["rights_status"], "unassessed")
        self.assertEqual(result["provenance"]["retrieved_at"], "2026-11-02T12:00:00+00:00")
        self.assertFalse(result["clinical_evidence_appraised"])
        self.assertFalse(result["saved_to_ledger"])
        rendered = json.dumps(result)
        for unwanted in ("ABSTRACT-MUST-NOT-PASS", "BOOK-MUST-NOT-PASS", "REPORT-MUST-NOT-PASS",
                         "untrusted.example", "UNKNOWN-MUST-NOT-PASS", "DO-NOT-FOLLOW",
                         "DO-NOT-STORE-RAW-QUERY", "DO-NOT-INFER-RIGHTS", "isOpenAccess"):
            self.assertNotIn(unwanted, rendered)

    def test_metadata_hash_changes_only_with_selected_content(self):
        first = self.module.project_search(provider_fixture(), SEARCH)
        changed = provider_fixture()
        changed["resultList"]["result"][0]["abstractText"] = "OTHER-EXCLUDED-TEXT"
        second = self.module.project_search(changed, SEARCH)
        self.assertEqual(first["results"][0]["metadata_sha256"], second["results"][0]["metadata_sha256"])
        changed["resultList"]["result"][0]["title"] = "A corrected authored title"
        third = self.module.project_search(changed, SEARCH)
        self.assertNotEqual(first["results"][0]["metadata_sha256"], third["results"][0]["metadata_sha256"])
        other = self.module.project_search(provider_fixture(), {"topic": "lymphoma", "page_size": 2})
        self.assertNotEqual(first["provenance"]["query_fingerprint"], other["provenance"]["query_fingerprint"])
        self.assertRegex(first["provenance"]["query_fingerprint"], r"^[0-9a-f]{64}$")

    def test_only_zero_hit_valid_envelope_means_no_results(self):
        empty = {"version": "6.9", "hitCount": 0, "resultList": {"result": []}}
        result = self.module.project_search(empty, SEARCH)
        self.assertEqual(result["results"], [])
        self.assertFalse(result["has_more"])
        for malformed in ({"version": "6.9"}, {"hitCount": True, "resultList": {"result": []}},
                          {"hitCount": 2, "resultList": {"result": []}},
                          {"hitCount": 0, "resultList": {"result": [{}]}},
                          {"hitCount": 0, "resultList": {}}):
            with self.subTest(payload=malformed):
                with self.assertRaises(self.module.EuropePMCUnavailable):
                    self.module.project_search(malformed, SEARCH)

    def test_provider_identity_and_page_caps_fail_closed(self):
        for field, value in (("source", "PPR"), ("id", "../../evil"), ("id", 123),
                             ("pmid", "999000002"), ("pmcid", "https://evil.example"),
                             ("doi", "https://evil.example")):
            changed = provider_fixture()
            changed["resultList"]["result"][0][field] = value
            with self.subTest(field=field, value=value):
                with self.assertRaises(self.module.EuropePMCUnavailable):
                    self.module.project_search(changed, SEARCH)
        changed = provider_fixture()
        changed["resultList"]["result"] *= 3
        with self.assertRaises(self.module.EuropePMCUnavailable):
            self.module.project_search(changed, SEARCH)
        changed["resultList"]["result"] = changed["resultList"]["result"][:2]
        with self.assertRaises(self.module.EuropePMCUnavailable):
            self.module.project_search(changed, SEARCH)  # Duplicate provider identity.

    def test_missing_optional_metadata_is_not_filled_with_invented_values(self):
        sparse = {"hitCount": 1, "resultList": {"result": [
            {"source": "MED", "id": "999000001", "title": "Authored sparse citation"}]}}
        item = self.module.project_search(sparse, SEARCH)["results"][0]
        self.assertIsNone(item["doi"])
        self.assertIsNone(item["year"])
        self.assertIsNone(item["first_publication_date"])
        self.assertIsNone(item["authors"])
        for field, value in (("title", "x" * 1001), ("title", "bad\x00text"),
                             ("authorString", ["invalid"]), ("pubYear", "202x"),
                             ("firstPublicationDate", "2025-02-29")):
            changed = provider_fixture()
            changed["resultList"]["result"][0][field] = value
            with self.subTest(field=field):
                with self.assertRaises(self.module.EuropePMCUnavailable):
                    self.module.project_search(changed, SEARCH)

    def test_literal_query_cannot_supply_source_or_provider_syntax(self):
        request = self.module.validate_search_request({"topic": "  BRAF positive  melanoma ",
            "start_date": "2024-01-01", "end_date": "2025-12-31", "page_size": 2})
        self.assertEqual(self.module.build_query(request),
                         'SRC:MED AND TITLE:"BRAF positive melanoma" AND FIRST_PDATE:[2024-01-01 TO 2025-12-31]')
        invalid = [None, [], {}, {"topic": 12}, {"topic": ""}, {"topic": "x" * 121},
                   {"topic": "melanoma\nname"}, {"topic": 'melanoma" OR SRC:PPR'},
                   {"topic": "melanoma", "patient_id": "DO-NOT-SEND"},
                   {"topic": "melanoma", "url": "https://untrusted.example"},
                   {"topic": "melanoma", "page_size": True},
                   {"topic": "melanoma", "page_size": 0},
                   {"topic": "melanoma", "page_size": 26},
                   {"topic": "melanoma", "page_size": "2"},
                   {"topic": "melanoma", "start_date": "2024-01-01"},
                   {"topic": "melanoma", "start_date": "2025-02-29", "end_date": "2025-03-01"},
                   {"topic": "melanoma", "start_date": "2025-03-02", "end_date": "2025-03-01"}]
        for request in invalid:
            with self.subTest(request=request):
                with self.assertRaises(self.module.EuropePMCInputError):
                    self.module.validate_search_request(request)

    def test_live_fetch_uses_one_fixed_lite_endpoint_with_time_and_byte_bounds(self):
        response = Response(json.dumps(provider_fixture()).encode())
        transport = Transport(response)
        result = self.module.fetch_public_topic(SEARCH, opener=transport)
        self.assertEqual(result["results"][0]["id"], "999000001")
        self.assertEqual(len(transport.requests), 1)
        request, timeout = transport.requests[0]
        url = urlsplit(request.full_url)
        self.assertEqual(url.scheme, "https")
        self.assertEqual(url.netloc, "www.ebi.ac.uk")
        self.assertEqual(url.path, "/europepmc/webservices/rest/search")
        self.assertEqual(parse_qs(url.query), {"query": ['SRC:MED AND TITLE:"melanoma"'],
            "format": ["json"], "resultType": ["lite"], "pageSize": ["2"], "cursorMark": ["*"]})
        self.assertEqual(timeout, 8)
        self.assertEqual(response.read_sizes, [256 * 1024 + 1])

    def test_live_requests_are_throttled_before_another_outbound_attempt(self):
        transport = Transport(Response(json.dumps(provider_fixture()).encode()))
        with patch.object(self.module, "monotonic", return_value=100.0):
            self.module.fetch_public_topic(SEARCH, opener=transport)
            with self.assertRaises(self.module.EuropePMCRateLimited):
                self.module.fetch_public_topic(SEARCH, opener=transport)
        self.assertEqual(len(transport.requests), 1)

    def test_content_type_and_size_limits_fail_closed(self):
        for response in (Response(b"{}", "text/html"), Response(b"{}", "application/jsonp"),
                         Response(b"x" * (256 * 1024 + 1)), Response(b"not-json"),
                         Response(b"{}", status=302)):
            with self.subTest(kind=response.headers, status=response.status):
                with patch.object(self.module, "_last_request_at", None):
                    with self.assertRaises(self.module.EuropePMCUnavailable):
                        self.module.fetch_public_topic(SEARCH, opener=Transport(response))

    def test_network_errors_are_bounded_and_do_not_echo_untrusted_payloads(self):
        for error in (HTTPError("https://untrusted.example/private", 302, "SECRET", {}, None),
                      URLError("SECRET"), TimeoutError("SECRET")):
            with self.subTest(error=type(error).__name__):
                with patch.object(self.module, "_last_request_at", None):
                    with self.assertRaises(self.module.EuropePMCUnavailable) as caught:
                        self.module.fetch_public_topic(SEARCH, opener=Transport(error))
                self.assertNotIn("SECRET", str(caught.exception))
                self.assertNotIn("untrusted", str(caught.exception))

    def test_truncated_transport_and_oversized_json_integer_are_provider_failures(self):
        scenarios = (
            Transport(IncompleteRead(b"SECRET")),
            Transport(Response(b'{"hitCount":' + b"9" * 5000 + b'}')),
        )
        for transport in scenarios:
            with self.subTest(transport=type(transport.response).__name__):
                caught = None
                with patch.object(self.module, "_last_request_at", None):
                    try:
                        self.module.fetch_public_topic(SEARCH, opener=transport)
                    except Exception as error:
                        caught = error
                self.assertIsInstance(caught, self.module.EuropePMCUnavailable)
                self.assertNotIn("SECRET", str(caught))

    def test_provider_quota_and_an_active_request_never_succeed_silently(self):
        transport = Transport(HTTPError("https://www.ebi.ac.uk", 429, "quota", {}, None))
        with self.assertRaises(self.module.EuropePMCRateLimited):
            self.module.fetch_public_topic(SEARCH, opener=transport)
        transport = Transport(Response(json.dumps(provider_fixture()).encode()))
        self.module._live_lock.acquire()
        try:
            with self.assertRaises(self.module.EuropePMCRateLimited):
                self.module.fetch_public_topic(SEARCH, opener=transport)
        finally:
            self.module._live_lock.release()
        self.assertEqual(transport.requests, [])

    def test_redirect_handler_refuses_an_arbitrary_destination(self):
        handler = self.module._NoRedirect()
        self.assertIsNone(handler.redirect_request(None, None, 302, "Found", {}, "https://untrusted.example"))

    def test_demo_has_no_live_identifiers_or_pretended_provider_retrieval(self):
        result = self.module.demo_search()
        self.assertEqual(result["mode"], "offline_demo")
        self.assertEqual(result["provenance"]["provider"], "Open Intelligence authored demonstration")
        for item in result["results"]:
            self.assertEqual(item["source"], "DEMO")
            self.assertIsNone(item["canonical_url"])
            self.assertIsNone(item["doi"])
            self.assertIsNone(item["pmid"])
        self.assertFalse(result["saved_to_ledger"])

    def test_cli_defaults_to_demo_and_requires_opt_in_for_a_topic(self):
        process = subprocess.run([sys.executable, "-m", "tools.europe_pmc_metadata"],
                                 cwd=ROOT, capture_output=True, text=True, check=False)
        self.assertEqual(process.returncode, 0, process.stderr)
        self.assertEqual(json.loads(process.stdout)["mode"], "offline_demo")
        process = subprocess.run([sys.executable, "-m", "tools.europe_pmc_metadata", "melanoma"],
                                 cwd=ROOT, capture_output=True, text=True, check=False)
        self.assertNotEqual(process.returncode, 0)
        self.assertIn("--live", process.stderr)


if __name__ == "__main__":
    unittest.main()
