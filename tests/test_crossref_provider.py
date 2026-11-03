"""Shared provider boundary; invented fixtures and in-process transports only."""
import copy
import io
import json
from email.message import Message
from threading import Event, Lock, Thread
import unittest
from unittest.mock import patch
from urllib.error import HTTPError
from urllib.request import BaseHandler, build_opener
from urllib.response import addinfourl

from open_intelligence import crossref_metadata as provider
from test_crossref_metadata import DOI, fixture, _CaptureTransport, _FakeResponse


class CrossrefProviderBoundaryTests(unittest.TestCase):
    def setUp(self):
        self.now = 1000.0
        self.clock = patch.object(provider, "monotonic", side_effect=lambda: self.now, create=True)
        self.deadline = patch.object(provider, "_next_request_at", 0.0, create=True)
        self.lock = patch.object(provider, "_request_lock", Lock(), create=True)
        for patcher in (self.clock, self.deadline, self.lock):
            patcher.start()
            self.addCleanup(patcher.stop)

    def test_projection_validator_rejects_forged_provenance_and_unknown_content(self):
        validator = getattr(provider, "validate_projected_work", None)
        self.assertTrue(callable(validator), "Shared projection validation is absent")
        base = provider.project_work(fixture(), DOI, retrieved_at="2026-11-03T10:00:00Z")
        accepted = validator(base, DOI)
        self.assertEqual(accepted, base)
        accepted["authors"].append("Independent caller")
        self.assertEqual(base["authors"], ["Ari Example", "Rin Invented"])
        mutations = [
            ("unknown", lambda r: r.update(abstract="do not retain")),
            ("doi", lambda r: r.update(doi="10.5555/other")),
            ("url", lambda r: r.update(canonical_url="https://untrusted.invalid/")),
            ("flag", lambda r: r.update(clinical_evidence_appraised=0)),
            ("year", lambda r: r.update(year=True)),
            ("author", lambda r: r.update(authors=["Bad\ud800name"])),
            ("provider", lambda r: r["source"].update(provider="untrusted")),
            ("rights", lambda r: r["source"].update(rights_basis="https://untrusted.invalid/")),
            ("record_url", lambda r: r["source"].update(record_url="https://api.crossref.org/works/other")),
            ("timestamp", lambda r: r["source"].update(retrieved_at="not-a-date")),
            ("source_extra", lambda r: r["source"].update(raw_abstract="do not retain")),
            ("missing", lambda r: r.pop("publication_type")),
        ]
        for label, mutate in mutations:
            record = copy.deepcopy(base)
            mutate(record)
            with self.subTest(label=label):
                with self.assertRaises(provider.MetadataInputError):
                    validator(record, DOI)

    def test_provider_rejects_author_controls_before_trimming(self):
        for part in ("\nAri", "Ari\x85", "\ud800", "\n"):
            raw = fixture()
            raw["message"]["author"] = [{"given": part, "family": "Example"}]
            with self.subTest(part=ascii(part)):
                with self.assertRaises(provider.MetadataInputError):
                    provider.project_work(raw, DOI)

    def test_malformed_large_integer_and_nested_json_are_typed_failures(self):
        for raw in (b'{"number":' + b'9' * 5000 + b'}', b'[' * 2000 + b']' * 2000):
            self.now += 100
            with self.subTest(size=len(raw)):
                with self.assertRaises(provider.MetadataInputError):
                    provider.fetch_public_doi(DOI, opener=_CaptureTransport(raw))

    def test_concurrent_request_is_denied_before_provider_egress(self):
        entered, release = Event(), Event()
        first_results, first_errors = [], []
        class HeldTransport:
            def open(self, request, timeout):
                entered.set()
                if not release.wait(3):
                    raise TimeoutError("test transport not released")
                return _FakeResponse(json.dumps(fixture()).encode())
        def run():
            try:
                first_results.append(provider.fetch_public_doi(DOI, opener=HeldTransport()))
            except Exception as exc:
                first_errors.append(exc)
        worker = Thread(target=run)
        worker.start()
        self.assertTrue(entered.wait(3))
        second = _CaptureTransport(json.dumps(fixture()).encode())
        try:
            with self.assertRaisesRegex(provider.MetadataInputError, "busy"):
                provider.fetch_public_doi(DOI, opener=second)
            self.assertEqual(second.requests, [])
        finally:
            release.set()
            worker.join(3)
        self.assertFalse(worker.is_alive())
        self.assertEqual(first_errors, [])
        self.assertEqual(first_results[0]["doi"], DOI)

    def test_completed_response_releases_single_flight_and_cools_down(self):
        transport = _CaptureTransport(json.dumps(fixture()).encode())
        first = provider.fetch_public_doi(DOI, opener=transport)
        self.assertEqual(first["doi"], DOI)
        self.assertFalse(provider._request_lock.locked())
        with self.assertRaisesRegex(provider.MetadataInputError, "rate limited"):
            provider.fetch_public_doi(DOI, opener=transport)
        self.assertEqual(len(transport.requests), 1)
        self.now += 1
        self.assertEqual(provider.fetch_public_doi(DOI, opener=transport)["doi"], DOI)
        self.assertEqual(len(transport.requests), 2)

    def test_rate_response_is_redacted_not_retried_and_cools_down(self):
        class RateLimited:
            calls = 0
            def open(self, request, timeout):
                self.calls += 1
                raise HTTPError("https://private.invalid/secret", 429,
                                "sensitive provider body", {}, io.BytesIO(b"private"))
        transport = RateLimited()
        with self.assertRaises(provider.MetadataInputError) as failure:
            provider.fetch_public_doi(DOI, opener=transport)
        self.assertNotIn("private", str(failure.exception))
        self.assertNotIn("sensitive", str(failure.exception))
        self.now += 59
        with self.assertRaisesRegex(provider.MetadataInputError, "rate limited"):
            provider.fetch_public_doi(DOI, opener=transport)
        self.assertEqual(transport.calls, 1)
        self.assertFalse(provider._request_lock.locked())

    def test_real_redirect_handler_never_opens_redirect_target(self):
        class RedirectResponse(BaseHandler):
            handler_order = 100
            requests = []
            def https_open(self, request):
                self.requests.append(request.full_url)
                headers = Message()
                headers["Location"] = "https://untrusted.invalid/redirect-target"
                response = addinfourl(io.BytesIO(b"redirect"), headers, request.full_url, 302)
                response.msg = "Found"
                return response
        handler = RedirectResponse()
        opener = build_opener(provider._NoRedirect(), handler)
        with self.assertRaises(provider.MetadataInputError):
            provider.fetch_public_doi(DOI, opener=opener)
        self.assertEqual(handler.requests, ["https://api.crossref.org/works/10.5555%2Foi-synthetic-001"])


if __name__ == "__main__":
    unittest.main()
