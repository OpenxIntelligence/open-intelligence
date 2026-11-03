"""Offline, fictional contract tests for post-amendment direct-PACS URL reads."""
from __future__ import annotations

from hashlib import sha256
from io import StringIO
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import Mock, patch
from contextlib import redirect_stderr, redirect_stdout

from open_intelligence.store import InvalidInput
from tools.imaging import pacsnode_direct_access_gate as gate
from tools.imaging import pacsnode_live_probe as pacs


class DirectAccessAfterAmendmentTests(unittest.TestCase):
    def setUp(self):
        # No actual patient/clinical pixels. The header permits strict
        # multipart framing validation; the remainder is fictional.
        self.objects = {
            sop: b"\0" * 128 + b"DICM" + bytes([i]) * 20
            for i, sop in enumerate(pacs.SOP_UIDS, 1)
        }
        digests = {uid: sha256(value).hexdigest()
                   for uid, value in self.objects.items()}
        self.prior = {
            "synthetic_only": True,
            "technical_evaluation_passed": True,
            "first_party_wado_wrong_case_refused": True,
            "first_party_wado_amendment_refused": True,
            "source_and_retrieved_objects_byte_identical": True,
            "clinical_or_full_dicomweb_approval": False,
            "real_patient_data_used": False,
            "candidate": "knopkem/pacsnode standalone",
            "source_commit": "e9b4334477a66967d290add9e0b9afa068f59dc0",
            "sop_original_sha256": digests,
            "sop_returned_sha256": digests.copy(),
        }

    def response(self, sop):
        media, body = pacs.multipart_body([self.objects[sop]])
        return (200, media, body)

    def read_mock(self, *, deny=False, changed=False):
        def read(url, accept):
            self.assertTrue(url.startswith("http://127.0.0.1:18042/wado/studies/"))
            self.assertEqual(accept, pacs.WADO_ACCEPT)
            sop = url.rsplit("/", 1)[-1]
            self.assertIn(sop, self.objects)
            if deny:
                return (403, "", b"")
            if changed:
                data = self.objects[sop] + b"x"
                media, body = pacs.multipart_body([data])
                return (200, media, body)
            return self.response(sop)
        return Mock(side_effect=read)

    def test_stale_original_still_directly_available_records_security_hold(self):
        get = self.read_mock()
        result = gate.inspect_direct_access(
            self.prior, "http://127.0.0.1:18042", fetch=get
        )
        self.assertEqual(get.call_count, 2)
        self.assertTrue(result["direct_access_test_completed"])
        self.assertTrue(result["anonymous_original_access_observed"])
        self.assertTrue(result["anonymous_original_access_observed_for_all_sops"])
        self.assertFalse(result["backend_adoption_approved"])
        self.assertFalse(result["upstream_revocation_verified"])
        self.assertFalse(result["upstream_patient_authorization_verified"])
        self.assertFalse(result["upstream_tenant_isolation_verified"])
        self.assertFalse(result["credential_header_sent"])
        self.assertNotIn("DICM", json.dumps(result))
        for sop in pacs.SOP_UIDS:
            self.assertEqual(
                result["sop_observations"][sop]["observed_original_sha256"],
                self.prior["sop_original_sha256"][sop],
            )

    def test_403_is_a_denial_not_tenant_authorization_clearance(self):
        result = gate.inspect_direct_access(
            self.prior, "http://127.0.0.1:18042", fetch=self.read_mock(deny=True)
        )
        self.assertTrue(result["direct_access_test_completed"])
        self.assertFalse(result["anonymous_original_access_observed"])
        self.assertFalse(result["upstream_revocation_verified"])
        self.assertFalse(result["upstream_patient_authorization_verified"])
        self.assertTrue(all(
            item["outcome"] == "anonymous_request_denied"
            for item in result["sop_observations"].values()
        ))

    def test_404_and_changed_original_are_inconclusive_not_denied(self):
        for response in (
            lambda url, accept: (404, "", b""),
            self.read_mock(changed=True),
            lambda url, accept: (200, "application/json", b"{}"),
        ):
            with self.subTest(response=response):
                result = gate.inspect_direct_access(
                    self.prior, "http://127.0.0.1:18042", fetch=response
                )
                self.assertFalse(result["direct_access_test_completed"])
                self.assertFalse(result["upstream_revocation_verified"])
                self.assertFalse(result["backend_adoption_approved"])

    def test_malformed_prior_proof_fails_before_any_http_request(self):
        for change in (
            {"first_party_wado_amendment_refused": False},
            {"clinical_or_full_dicomweb_approval": True},
            {"real_patient_data_used": True},
            {"source_commit": "unexpected"},
            {"sop_original_sha256": {"unexpected": "0" * 64}},
            {"sop_returned_sha256": {uid: "0"*64 for uid in pacs.SOP_UIDS}},
        ):
            with self.subTest(change=change):
                get = self.read_mock()
                with self.assertRaises(InvalidInput):
                    gate.inspect_direct_access(
                        {**self.prior, **change},
                        "http://127.0.0.1:18042", fetch=get
                    )
                get.assert_not_called()

    def test_nonloopback_url_rejected_before_network(self):
        for origin in ("http://localhost:18042", "http://127.0.0.2:18042",
                       "https://127.0.0.1:18042", "http://127.0.0.1:18042@host"):
            with self.subTest(origin=origin):
                get = self.read_mock()
                with self.assertRaises(InvalidInput):
                    gate.inspect_direct_access(self.prior, origin, fetch=get)
                get.assert_not_called()

    def test_cli_persists_only_bounded_observations(self):
        with tempfile.TemporaryDirectory() as tmp:
            before = Path(tmp) / "before.json"
            after = Path(tmp) / "after.json"
            before.write_text(json.dumps(self.prior))
            good = gate.inspect_direct_access(
                self.prior, "http://127.0.0.1:18042", fetch=self.read_mock()
            )
            argv = ["probe", "--base-url", "http://127.0.0.1:18042",
                    "--prior-receipt", str(before), "--output", str(after)]
            with patch.object(gate.sys, "argv", argv), patch.object(
                gate, "inspect_direct_access", return_value=good
            ), redirect_stdout(StringIO()):
                self.assertEqual(gate.main(), 0)
            saved = json.loads(after.read_text())
            self.assertTrue(saved["anonymous_original_access_observed"])
            self.assertFalse(saved["backend_adoption_approved"])
            self.assertNotIn("DICM", after.read_text())

    def test_cli_exception_does_not_echo_untrusted_contents(self):
        with tempfile.TemporaryDirectory() as tmp:
            before = Path(tmp) / "before.json"
            after = Path(tmp) / "after.json"
            before.write_text(json.dumps(self.prior))
            argv = ["probe", "--base-url", "http://127.0.0.1:18042",
                    "--prior-receipt", str(before), "--output", str(after)]
            unsafe = "UNTRUSTED_SYNTHETIC_BODY_NEVER_ECHO"
            stderr = StringIO()
            with patch.object(gate.sys, "argv", argv), patch.object(
                gate, "inspect_direct_access", side_effect=InvalidInput(unsafe)
            ), redirect_stderr(stderr):
                self.assertEqual(gate.main(), 1)
            result = json.loads(after.read_text())
            self.assertFalse(result["backend_adoption_approved"])
            self.assertEqual(result["failure_type"], "InvalidInput")
            self.assertNotIn(unsafe, after.read_text() + stderr.getvalue())


if __name__ == "__main__":
    unittest.main()
