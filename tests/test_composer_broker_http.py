"""HTTP integration over fictional local ledger and a stub provider boundary."""
from unittest.mock import patch
import unittest

import test_composer_http as http_helpers
from test_composer_broker_context import link, payload
from open_intelligence.store import CaseStore


class BrokerHttpTest(unittest.TestCase):
    setUp = http_helpers.NativeComposerHttpTest.setUp
    tearDown = http_helpers.NativeComposerHttpTest.tearDown
    request = http_helpers.NativeComposerHttpTest.request
    question = http_helpers.NativeComposerHttpTest.question
    preview = http_helpers.NativeComposerHttpTest.preview

    def test_no_client_fingerprint_cannot_save_after_mid_call_revocation(self):
        q = self.question()
        store = CaseStore(self.db)
        rid, lid = link(store, q, excerpt="Fictional allowed input before revocation.")
        store.close()
        def response(prompt, key):
            current = CaseStore(self.db)
            current.revoke_rights_source(rid, "Rights changed during fictional provider call.")
            current.close()
            return payload(lid)
        with patch("open_intelligence.__main__.call_meta_api", side_effect=response), patch("open_intelligence.__main__.meta_api_key", return_value="fake"):
            status, body = self.request("/api/cases/CASE-ALPHA/investigations", {"question_id": q, "template": "evidence-summary", "mode": "live"})
        self.assertEqual(status, 422)
        self.assertIn("stale", body["error"])
        check = CaseStore(self.db)
        self.assertEqual(check.list_investigations("CASE-ALPHA"), [])
        check.close()

    def test_eligible_broker_text_reaches_model_and_saved_claim_has_receipt(self):
        q = self.question()
        store = CaseStore(self.db)
        _, lid = link(store, q, excerpt="Only this fictional counterevidence reaches provider.")
        store.close()
        def response(prompt, key):
            self.assertIn("Only this fictional counterevidence", prompt)
            self.assertIn("relation=contradicts", prompt)
            return payload(lid)
        with patch("open_intelligence.__main__.call_meta_api", side_effect=response), patch("open_intelligence.__main__.meta_api_key", return_value="fake"):
            status, body = self.request("/api/cases/CASE-ALPHA/investigations", {"question_id": q, "template": "evidence-summary", "mode": "live"})
        self.assertEqual(status, 201)
        self.assertEqual(body["claims"][0]["citations"], [{"type": "broker", "id": lid}])
        self.assertEqual(body["input_receipts"][0]["broker_link_id"], lid)
