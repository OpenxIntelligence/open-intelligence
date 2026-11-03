"""Original source-bound synthetic WADO reads: no external network or medical data."""
from __future__ import annotations

from dataclasses import replace
from hashlib import sha256
from pathlib import Path
from unittest.mock import Mock, patch
import unittest

from open_intelligence.store import CaseStore, InvalidInput
from open_intelligence.synthetic_dicom_roundtrip import synthetic_dicom_bytes
from tools.imaging import pacsnode_live_probe as pacs
from tools.imaging.source_bound_wado import (
    SyntheticWadoBinding, read_source_bound_wado,
)

REPORT = (Path(__file__).resolve().parents[1]
          / "examples" / "synthetic" / "alpha-imaging.txt")


class SourceBoundWadoTests(unittest.TestCase):
    def setUp(self):
        self.store = CaseStore(":memory:")
        self.store.add_case("CASE-ALPHA", "Independent fictional imaging case")
        self.store.add_case("CASE-BETA", "Unrelated fictional case")
        self.source_id = self.store.import_report(
            "CASE-ALPHA", REPORT.read_bytes()
        )["source_id"]
        source = next(s for s in self.store.state("CASE-ALPHA")["sources"]
                      if s["id"] == self.source_id)
        self.original = synthetic_dicom_bytes(
            study_uid=pacs.IMAGE_STUDY_UID,
            series_uid=pacs.IMAGE_SERIES_UID,
            sop_uid=pacs.SOP_UIDS[0],
        )
        self.binding = SyntheticWadoBinding(
            case_id="CASE-ALPHA",
            source_version_id=self.source_id,
            source_sha256=source["sha256"],
            study_uid=pacs.IMAGE_STUDY_UID,
            series_uid=pacs.IMAGE_SERIES_UID,
            sop_uid=pacs.SOP_UIDS[0],
            original_dicom_sha256=sha256(self.original).hexdigest(),
        )
        self.media, self.wire = pacs.multipart_body([self.original])

    def tearDown(self):
        self.store.close()

    def fetch(self):
        return Mock(return_value=(200, self.media, self.wire))

    def read(self, binding=None, fetch=None):
        return read_source_bound_wado(
            self.store, binding or self.binding, "http://127.0.0.1:18042",
            fetch=fetch or self.fetch()
        )

    def _amend(self):
        corrected = (
            "OI-SYNTHETIC-REPORT/1\n"
            "Patient: CASE-ALPHA\n"
            "Document: IMG-ALPHA\n"
            "Type: imaging\n"
            "Event-Date: 2026-05-17\n"
            "Issued-At: 2026-05-19\n"
            "Amends: IMG-ALPHA@1\n"
            "Finding: change|reported|Independent fictional amended imaging report.\n"
        ).encode()
        return self.store.import_report("CASE-ALPHA", corrected)

    def test_read_returns_original_source_and_digest_without_dicom_bytes(self):
        before = self.store.state("CASE-ALPHA")
        fetch = self.fetch()
        result = self.read(fetch=fetch)
        self.assertEqual(result["case_id"], "CASE-ALPHA")
        self.assertEqual(result["source_version_id"], self.source_id)
        self.assertEqual(result["source_sha256"], self.binding.source_sha256)
        self.assertTrue(result["original_bytes_verified"])
        self.assertEqual(result["retrieved_original_dicom_sha256"],
                         self.binding.original_dicom_sha256)
        self.assertFalse(result["caller_authenticated"])
        self.assertFalse(result["case_authorization_verified"])
        self.assertFalse(result["upstream_object_access_revoked"])
        self.assertFalse(result["pacs_adoption_approved"])
        self.assertEqual(result["clinical_review_state"], "not_performed")
        self.assertEqual(self.store.state("CASE-ALPHA"), before)
        self.assertNotIn("PixelData", str(result))
        self.assertNotIn("DICM", str(result))
        args = fetch.call_args.args
        self.assertEqual(args[0], "http://127.0.0.1:18042/wado/studies/"
                         + pacs.IMAGE_STUDY_UID + "/series/" + pacs.IMAGE_SERIES_UID
                         + "/instances/" + pacs.SOP_UIDS[0])
        self.assertEqual(args[1], pacs.WADO_ACCEPT)

    def test_wrong_case_and_invalid_sha_fail_before_http(self):
        fetch = self.fetch()
        with self.assertRaises(InvalidInput):
            self.read(replace(self.binding, case_id="CASE-BETA"), fetch)
        with self.assertRaises(InvalidInput):
            self.read(replace(self.binding, source_sha256="a"*64), fetch)
        with self.assertRaises(InvalidInput):
            self.read(replace(self.binding, source_version_id=999), fetch)
        fetch.assert_not_called()

    def test_incompatible_object_digest_and_multipart_fail_closed(self):
        fetch = self.fetch()
        with self.assertRaises(InvalidInput):
            self.read(replace(self.binding, original_dicom_sha256="0"*64), fetch)
        with self.assertRaises(InvalidInput):
            self.read(fetch=Mock(return_value=(200, "application/json", b"[]")))
        with self.assertRaises(InvalidInput):
            self.read(fetch=Mock(return_value=(403, self.media, self.wire)))
        with self.assertRaises(InvalidInput):
            self.read(fetch=Mock(return_value=(200, self.media, self.wire+b"wrong")))

    def test_source_amendment_between_preflight_and_response_does_not_publish(self):
        def amend_during_retrieval(url, accept):
            self._amend()
            return 200, self.media, self.wire

        with self.assertRaises(InvalidInput):
            self.read(fetch=amend_during_retrieval)
        source = next(s for s in self.store.state("CASE-ALPHA")["sources"]
                      if s["id"] == self.source_id)
        self.assertEqual(source["state"], "superseded")
        # Even though the upstream still has the byte-identical DICOM object,
        # an old report cannot authorize a *new* OI result.
        with self.assertRaises(InvalidInput):
            self.read(fetch=self.fetch())

    def test_bad_uid_and_nonloopback_destination_rejected(self):
        for bad in ("1..2", "1."+"2"*65, "../1.2.3", "0001.2"):
            with self.subTest(uid=bad), self.assertRaises(InvalidInput):
                self.read(replace(self.binding, sop_uid=bad))
        for url in ("http://localhost:18042", "https://127.0.0.1:18042",
                    "http://127.0.0.2:18042", "http://example.org:18042"):
            with self.subTest(url=url), self.assertRaises(InvalidInput):
                read_source_bound_wado(self.store, self.binding, url,
                                       fetch=self.fetch())

    def test_default_uses_no_proxy_no_redirect_restricted_transport(self):
        with patch.object(
            pacs, "_request", return_value=(200, self.media, self.wire)
        ) as request:
            result = read_source_bound_wado(
                self.store, self.binding, "http://127.0.0.1:18042"
            )
        self.assertTrue(result["original_bytes_verified"])
        self.assertEqual(request.call_args.kwargs["accept"], pacs.WADO_ACCEPT)


if __name__ == "__main__":
    unittest.main()
