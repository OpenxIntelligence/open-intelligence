"""Offline tests with invented bibliographic records; no patient fixtures."""
import copy
import hashlib
import json
import unittest
from datetime import datetime, timezone
from email.message import Message
from io import BytesIO
from unittest.mock import patch
from urllib.error import HTTPError, URLError
from urllib.parse import parse_qs, urlsplit
from urllib.response import addinfourl

from open_intelligence import literature


NOW = datetime(2026, 11, 2, 12, 34, 56, tzinfo=timezone.utc)
RECORD = {
    "id": "12345678", "source": "MED", "pmid": "12345678",
    "pmcid": "PMC1234567", "doi": "10.5555/Invented-Metadata.1",
    "title": "Invented bibliographic test title",
    "authorString": "Example A, Invented B.", "journalTitle": "Example Journal",
    "pubYear": "2026", "firstPublicationDate": "2026-01-02",
    "pubType": "Journal Article; Review",
}


def payload(records=None, **changes):
    records = [copy.deepcopy(RECORD)] if records is None else records
    data = {"version": "6.9", "hitCount": len(records), "resultList": {"result": records}}
    data.update(changes)
    return json.dumps(data).encode("utf-8")


class Response:
    def __init__(self, body, *, status=200, content_type="application/json", url=None, headers=None):
        self.body, self.status, self.url = body, status, url
        self.headers = {"Content-Type": content_type, **(headers or {})}
        self.read_sizes = []
        self.closed = False

    def geturl(self):
        return self.url

    def read(self, size):
        self.read_sizes.append(size)
        return self.body[:size]

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.closed = True


class Transport:
    def __init__(self, response=None, error=None):
        self.response = response if response is not None else Response(payload())
        self.error = error
        self.requests = []

    def open(self, request, timeout):
        self.requests.append((request, timeout))
        if self.error:
            raise self.error
        if self.response.url is None:
            self.response.url = request.full_url
        return self.response


class LiteratureTests(unittest.TestCase):
    def search(self, transport=None, terms="HER2-positive breast cancer", **kwargs):
        return literature.search_europe_pmc(
            terms, human_authored=True, public_terms_only=True,
            opener=transport if transport is not None else Transport(),
            clock=lambda: NOW, **kwargs,
        )

    def test_fixed_encoded_first_page_request_and_metadata_contract(self):
        transport = Transport()
        result = self.search(transport, terms="ERBB2 + breast cancer", page_size=3)
        request, timeout = transport.requests[0]
        parts = urlsplit(request.full_url)
        self.assertEqual((parts.scheme, parts.netloc, parts.path),
                         ("https", "www.ebi.ac.uk", "/europepmc/webservices/rest/search"))
        self.assertEqual(parse_qs(parts.query), {
            "query": ["ERBB2 + breast cancer"], "format": ["json"],
            "resultType": ["lite"], "pageSize": ["3"], "cursorMark": ["*"], "synonym": ["false"],
        })
        self.assertIn("%2B", parts.query)
        self.assertEqual(timeout, 8)
        self.assertEqual(request.get_method(), "GET")
        self.assertEqual(request.get_header("Accept-encoding"), "identity")
        self.assertEqual(len(transport.requests), 1)
        self.assertEqual(result["metadata_only"], True)
        self.assertEqual(result["clinical_use"], "not evidence for a clinical conclusion")
        self.assertFalse(result["clinical_evidence_appraised"])
        self.assertEqual(result["retrieved_at"], "2026-11-02T12:34:56Z")
        self.assertEqual(result["provider_api_version"], "6.9")
        self.assertEqual(result["response_sha256"], hashlib.sha256(transport.response.body).hexdigest())
        citation = result["citations"][0]
        self.assertEqual(citation["citation_id"], "europepmc:MED:12345678")
        self.assertEqual(citation["identifiers"], {
            "pmid": "12345678", "pmcid": "PMC1234567", "doi": "10.5555/invented-metadata.1"})
        self.assertEqual(citation["record_url"], "https://europepmc.org/article/MED/12345678")
        self.assertEqual(citation["publication_year"], 2026)
        self.assertEqual(citation["first_publication_date"], "2026-01-02")
        self.assertEqual(citation["publication_types"], ["Journal Article", "Review"])
        self.assertEqual(citation["integrity"]["status"], "unknown")
        self.assertEqual(result["rights_status"], "not_assessed")
        self.assertTrue(transport.response.closed)

    def test_explicit_public_human_terms_required_before_transport(self):
        for attestations in ({}, {"human_authored": True}, {"public_terms_only": True},
                             {"human_authored": 1, "public_terms_only": True},
                             {"human_authored": True, "public_terms_only": "yes"}):
            with self.subTest(attestations=attestations):
                transport = Transport()
                with self.assertRaises(literature.LiteratureError):
                    literature.search_europe_pmc("breast cancer", opener=transport, **attestations)
                self.assertEqual(transport.requests, [])

    def test_malformed_or_excessive_terms_and_page_size_never_leave_process(self):
        for terms in (None, {}, "", " ", "a", "x" * 241, "breast\ncancer", "cancer\x00",
                      "https://example.org/private", "www.example.org", "person@example.org",
                      "cancer&format=xml", "TITLE:cancer", "cancer\\secret", "cancer\ttrial",
                      "<script>", "12345"):
            with self.subTest(terms=terms):
                transport = Transport()
                with self.assertRaises(literature.LiteratureError):
                    self.search(transport, terms=terms)
                self.assertEqual(transport.requests, [])
        for page_size in (0, -1, 11, True, 2.5, "2"):
            with self.subTest(page_size=page_size):
                transport = Transport()
                with self.assertRaises(literature.LiteratureError):
                    self.search(transport, page_size=page_size)
                self.assertEqual(transport.requests, [])

    def test_untrusted_content_links_licenses_and_echoed_query_are_discarded(self):
        record = copy.deepcopy(RECORD)
        record.update({"abstractText": "ABSTRACT SENTINEL", "fullText": "BODY SENTINEL",
                       "fullTextUrlList": {"url": "https://attacker.invalid/FULLTEXT"},
                       "figure": "FIGURE SENTINEL", "supplement": "SUPPLEMENT SENTINEL",
                       "license": "LICENSE SENTINEL", "isOpenAccess": "Y"})
        result = self.search(Transport(Response(payload([record], request={"queryString": "QUERY SENTINEL"},
                               nextPageUrl="https://attacker.invalid/NEXT", nextCursorMark="CURSOR SENTINEL"))))
        serialized = json.dumps(result)
        for value in ("SENTINEL", "attacker.invalid", "abstractText", "fullText", "isOpenAccess", "license"):
            self.assertNotIn(value, serialized)
        self.assertNotIn("HER2-positive breast cancer", serialized)
        self.assertNotIn("evidence_text", serialized)
        self.assertNotIn("permission_receipt", serialized)

    def test_missing_invalid_conflicting_and_unsupported_ids_are_counted_not_invented(self):
        changed = []
        for changes in ({"id": None}, {"id": "../bad"}, {"pmid": "87654321"},
                        {"pmcid": "PMC../bad"}, {"doi": "https://attacker.invalid/x"},
                        {"source": "PAT", "id": "WO123"}, {"source": "PPR", "id": "PPR1"}):
            changed.append({**RECORD, **changes})
        result = self.search(Transport(Response(payload(changed))), page_size=10)
        self.assertEqual(result["citations"], [])
        self.assertEqual(sum(result["excluded_counts"].values()), 7)
        self.assertEqual(result["excluded_counts"]["unsupported_source"], 2)
        self.assertEqual(result["provider_hit_count"], 7)

    def test_pmc_identity_and_missing_optional_metadata_remain_unknown(self):
        record = {"source": "PMC", "id": "PMC1234567", "title": "Invented PMC title"}
        result = self.search(Transport(Response(payload([record]))))
        citation = result["citations"][0]
        self.assertEqual(citation["identifiers"], {"pmid": None, "pmcid": "PMC1234567", "doi": None})
        self.assertEqual(citation["record_url"], "https://europepmc.org/article/PMC/PMC1234567")
        self.assertIsNone(citation["publication_year"])
        self.assertIsNone(citation["first_publication_date"])
        self.assertEqual(citation["date_precision"], "unknown")
        self.assertEqual(citation["integrity"], {"status": "unknown", "markers": []})

    def test_metadata_dates_and_lengths_are_validated_and_bad_records_are_reported(self):
        for changes in ({"firstPublicationDate": "2026-02-30"}, {"firstPublicationDate": "20260102"},
                        {"firstPublicationDate": "2026-1-2"}, {"pubYear": True},
                        {"pubYear": "26"}, {"pubYear": "2026-01"}, {"title": ""},
                        {"title": "x" * 1001}, {"title": "bad\x00title"},
                        {"authorString": ["unexpected list"]}, {"pubType": ["Review"]}):
            with self.subTest(changes=changes):
                result = self.search(Transport(Response(payload([{**RECORD, **changes}]))))
                self.assertEqual(result["citations"], [])
                self.assertEqual(result["excluded_counts"], {"invalid_metadata": 1})

    def test_provider_correction_and_retraction_markers_survive_without_inference(self):
        record = {**RECORD, "pubType": "Journal Article; Retracted Publication",
                  "commentCorrectionList": {"commentCorrection": [
                      {"type": "Retraction in", "source": "MED", "id": "87654321",
                       "note": "NOTE SENTINEL", "reference": "REFERENCE SENTINEL"}]}}
        citation = self.search(Transport(Response(payload([record]))))["citations"][0]
        self.assertEqual(citation["integrity"]["status"], "provider_markers_present")
        markers = citation["integrity"]["markers"]
        self.assertIn({"field": "pubType", "value": "Retracted Publication"}, markers)
        self.assertIn({"field": "commentCorrectionList.type", "value": "Retraction in",
                       "related_source": "MED", "related_id": "87654321"}, markers)
        self.assertNotIn("SENTINEL", json.dumps(citation))
        titled = {**RECORD, "title": "Retraction discussion in an invented title"}
        self.assertEqual(self.search(Transport(Response(payload([titled]))))["citations"][0]
                         ["integrity"]["status"], "unknown")

    def test_unexpected_core_type_markers_are_preserved_but_core_text_is_discarded(self):
        record = {**RECORD, "pubTypeList": {"pubType": ["Published Erratum", "Expression of Concern"]},
                  "abstractText": "ABSTRACT SENTINEL"}
        citation = self.search(Transport(Response(payload([record]))))["citations"][0]
        self.assertEqual(citation["publication_types"],
                         ["Journal Article", "Review", "Published Erratum", "Expression of Concern"])
        self.assertIn({"field": "pubTypeList.pubType", "value": "Published Erratum"},
                      citation["integrity"]["markers"])
        self.assertNotIn("SENTINEL", json.dumps(citation))
        for bad in ({"pubTypeList": {"pubType": [None]}},
                    {"commentCorrectionList": {"commentCorrection": [{"type": None}]}}):
            result = self.search(Transport(Response(payload([{**RECORD, **bad}]))))
            self.assertEqual(result["citations"], [])
            self.assertEqual(result["excluded_counts"], {"invalid_metadata": 1})

    def test_hash_tracks_projected_metadata_but_not_retrieval_or_discarded_content(self):
        first = self.search()["citations"][0]
        changed = {**RECORD, "abstractText": "DIFFERENT ABSTRACT"}
        second = self.search(Transport(Response(payload([changed]))))["citations"][0]
        self.assertEqual(first["metadata_sha256"], second["metadata_sha256"])
        changed["title"] = "Changed invented title"
        third = self.search(Transport(Response(payload([changed]))))["citations"][0]
        self.assertNotEqual(first["metadata_sha256"], third["metadata_sha256"])
        self.assertEqual(len(first["metadata_sha256"]), 64)

    def test_duplicate_identity_cannot_create_two_citations(self):
        result = self.search(Transport(Response(payload([RECORD, {**RECORD, "title": "Conflicting title"}]))))
        self.assertEqual(len(result["citations"]), 1)
        self.assertEqual(result["excluded_counts"], {"duplicate_identifier": 1})

    def test_empty_results_are_valid_but_malformed_envelopes_are_not(self):
        self.assertEqual(self.search(Transport(Response(payload([]))))["citations"], [])
        for data in ([], {}, {"resultList": {"result": []}},
                     {"hitCount": True, "resultList": {"result": []}},
                     {"hitCount": 1, "resultList": {"result": {}}},
                     {"hitCount": 0, "resultList": {"result": [RECORD]}},
                     {"hitCount": 1, "resultList": {"result": [None]}},
                     {"hitCount": 1, "resultList": {"result": [RECORD]}, "version": "https://bad"}):
            with self.subTest(data=data):
                with self.assertRaises(literature.LiteratureError):
                    self.search(Transport(Response(json.dumps(data).encode())))
        with self.assertRaises(literature.LiteratureError):
            self.search(Transport(Response(payload([RECORD] * 3))), page_size=2)

    def test_non_success_and_redirect_statuses_fail_before_body_read(self):
        for status in (201, 204, 301, 302, 307, 400, 429, 500):
            with self.subTest(status=status):
                response = Response(payload(), status=status)
                with self.assertRaises(literature.LiteratureError):
                    self.search(Transport(response))
                self.assertEqual(response.read_sizes, [])
                self.assertTrue(response.closed)
        with self.assertRaises(literature.LiteratureError):
            self.search(Transport(Response(payload(), url="https://attacker.invalid/redirect")))

    def test_default_transport_does_not_follow_real_urllib_redirects(self):
        calls = []

        def fake_https_open(handler, request):
            calls.append(request.full_url)
            headers = Message()
            headers["Location"] = "https://attacker.invalid/redirect"
            response = addinfourl(BytesIO(b""), headers, request.full_url, code=302)
            response.msg = "Found"
            return response

        with patch("urllib.request.HTTPSHandler.https_open", fake_https_open):
            with self.assertRaises(literature.LiteratureError):
                literature.search_europe_pmc("breast cancer", human_authored=True, public_terms_only=True)
        self.assertEqual(len(calls), 1)
        self.assertEqual(urlsplit(calls[0]).netloc, "www.ebi.ac.uk")

    def test_non_json_bad_json_duplicate_keys_and_oversize_responses_fail(self):
        for body in (b"<html>not json</html>", b"{", b"\xff", b'{"hitCount":0,"hitCount":1}',
                     b'{"hitCount":NaN,"resultList":{"result":[]}}'):
            with self.subTest(body=body):
                with self.assertRaises(literature.LiteratureError):
                    self.search(Transport(Response(body)))
        for response in (Response(payload(), content_type="text/html"),
                         Response(payload(), headers={"Content-Encoding": "gzip"}),
                         Response(payload(), headers={"Content-Length": "-1"}),
                         Response(payload(), headers={"Content-Length": str(256 * 1024 + 1)})):
            with self.assertRaises(literature.LiteratureError):
                self.search(Transport(response))
            self.assertEqual(response.read_sizes, [])
        response = Response(b"x" * (256 * 1024 + 1))
        with self.assertRaises(literature.LiteratureError):
            self.search(Transport(response))
        self.assertEqual(response.read_sizes, [256 * 1024 + 1])

    def test_network_and_provider_errors_do_not_leak_terms_urls_or_response_body(self):
        secret = "PRIVATE SENTINEL"
        for error in (URLError(secret), TimeoutError(secret),
                      HTTPError("https://example.invalid/?" + secret, 500, secret, {}, None)):
            with self.subTest(error=type(error).__name__):
                with self.assertRaises(literature.LiteratureError) as caught:
                    self.search(Transport(error=error), terms=secret)
                self.assertNotIn(secret, str(caught.exception))
                self.assertNotIn("example.invalid", str(caught.exception))
                self.assertTrue(caught.exception.__suppress_context__)
        with self.assertRaises(literature.LiteratureError) as caught:
            self.search(Transport(Response(payload([], errMsg=secret))), terms=secret)
        self.assertNotIn(secret, str(caught.exception))


if __name__ == "__main__":
    unittest.main()
