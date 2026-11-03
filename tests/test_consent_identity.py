import json
import tempfile
import threading
import unittest
from http.server import ThreadingHTTPServer
from pathlib import Path
from urllib.error import HTTPError
from urllib.request import Request, urlopen

from open_intelligence import CaseStore, InvalidInput
from open_intelligence.__main__ import Handler, seed

ROOT = Path(__file__).resolve().parents[1]
SAMPLE = ROOT / "examples" / "synthetic"


def report(name):
    return (SAMPLE / name).read_bytes()


class ConsentIdentityStoreTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.store = CaseStore(Path(self.tmp.name) / "consent.sqlite")
        self.store.add_case("CASE-ALPHA", "Fictional Alpha")
        self.store.add_case("CASE-BETA", "Fictional Beta")
        self.alpha = self.store.import_report("CASE-ALPHA", report("alpha-pathology-original.txt"))
        self.beta = self.store.import_report("CASE-BETA", report("beta-pathology.txt"))

    def tearDown(self):
        self.store.close()
        self.tmp.cleanup()

    def test_record_withdraw_history_shows_both_versions_in_order(self):
        consent_id = self.store.record_consent(
            "CASE-ALPHA", "Fictional permission to use notes for teaching.", "2026-05-10")
        current = self.store.list_consents("CASE-ALPHA")
        self.assertEqual(len(current), 1)
        self.assertEqual(current[0]["status"], "active")
        self.assertEqual(current[0]["review_state"], "display_only")
        self.assertTrue(current[0]["fictional"])
        self.assertEqual(len(current[0]["versions"]), 1)
        self.assertEqual(current[0]["versions"][0]["status"], "active")

        version = self.store.withdraw_consent(
            "CASE-ALPHA", consent_id,
            "Fictional reason: the person changed their mind.", "2026-06-01")
        self.assertEqual(version, 2)

        current = self.store.list_consents("CASE-ALPHA")
        self.assertEqual(current[0]["status"], "withdrawn")
        history = current[0]["versions"]
        self.assertEqual([v["version"] for v in history], [1, 2])
        self.assertEqual([v["status"] for v in history], ["active", "withdrawn"])
        # Prior active version stays in history, never deleted.
        self.assertIsNone(history[0]["reason"])
        self.assertEqual(history[1]["reason"],
                         "Fictional reason: the person changed their mind.")
        self.assertEqual(history[1]["date_recorded"], "2026-06-01")

    def test_statuses_restricted_and_inputs_validated(self):
        with self.assertRaisesRegex(InvalidInput, "Consent scope"):
            self.store.record_consent("CASE-ALPHA", "bad", "2026-05-10")
        with self.assertRaisesRegex(InvalidInput, "YYYY-MM-DD"):
            self.store.record_consent("CASE-ALPHA", "Fictional permission scope text.", "05/10/2026")
        consent_id = self.store.record_consent(
            "CASE-ALPHA", "Fictional permission to use notes for teaching.", "2026-05-10")
        with self.assertRaisesRegex(InvalidInput, "10–600"):
            self.store.withdraw_consent("CASE-ALPHA", consent_id, "short")
        with self.assertRaisesRegex(InvalidInput, "Consent not in this case"):
            self.store.withdraw_consent("CASE-ALPHA", 9999, "Fictional reason that is long enough.")
        with self.assertRaisesRegex(InvalidInput, "Invalid consent ID"):
            self.store.withdraw_consent("CASE-ALPHA", 0, "Fictional reason that is long enough.")
        self.store.withdraw_consent(
            "CASE-ALPHA", consent_id, "Fictional reason that is long enough.", "2026-06-01")
        with self.assertRaisesRegex(InvalidInput, "already withdrawn"):
            self.store.withdraw_consent(
                "CASE-ALPHA", consent_id, "A second fictional reason that is long.")
        # Only active/withdrawn exist; no other status can be stored.
        rows = self.store.list_consents("CASE-ALPHA")
        self.assertEqual({r["status"] for r in rows}, {"withdrawn"})
        self.assertEqual({v["status"] for v in rows[0]["versions"]}, {"active", "withdrawn"})

    def test_qualifier_attaches_only_to_existing_same_case_anchor(self):
        anchor = self.alpha["source_id"]
        qualifier_id = self.store.add_identity_qualifier(
            "CASE-ALPHA", "Fictional note: spelling differs; both kept.", anchor, "2026-05-11")
        rows = self.store.list_identity_qualifiers("CASE-ALPHA")
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["id"], qualifier_id)
        self.assertEqual(rows[0]["review_state"], "display_only")
        self.assertTrue(rows[0]["fictional"])
        self.assertIn("PATH-ALPHA@1", rows[0]["anchor_label"])
        self.assertIn("# %d" % anchor, rows[0]["anchor_label"])
        # Cross-case anchor is rejected, never linked.
        with self.assertRaisesRegex(InvalidInput, "Anchor source not in this case"):
            self.store.add_identity_qualifier(
                "CASE-ALPHA", "Fictional cross-case attempt note.", self.beta["source_id"], "2026-05-11")
        with self.assertRaisesRegex(InvalidInput, "Anchor source not in this case"):
            self.store.add_identity_qualifier(
                "CASE-ALPHA", "Fictional missing anchor note text.", 9999, "2026-05-11")
        with self.assertRaisesRegex(InvalidInput, "Anchor line"):
            self.store.add_identity_qualifier(
                "CASE-ALPHA", "Fictional note with bad line anchor.", anchor, "2026-05-11",
                anchor_line=9999)
        with self.assertRaisesRegex(InvalidInput, "Identity note"):
            self.store.add_identity_qualifier("CASE-ALPHA", "bad", anchor, "2026-05-11")
        self.assertEqual(len(self.store.list_identity_qualifiers("CASE-ALPHA")), 1)

    def test_qualifier_never_alters_existing_identity_fields(self):
        before_cases = self.store.cases()
        before_sources = self.store.state("CASE-ALPHA")["sources"]
        anchor = self.alpha["source_id"]
        self.store.add_identity_qualifier(
            "CASE-ALPHA", "Fictional note: check spelling against prior report.", anchor, "2026-05-11")
        self.assertEqual(self.store.cases(), before_cases)
        after_sources = self.store.state("CASE-ALPHA")["sources"]
        self.assertEqual(after_sources, before_sources)
        # No new case, source, or patient linkage was created.
        self.assertEqual(len(self.store.cases()), 2)
        self.assertEqual(len(after_sources), len(before_sources))

    def test_withdrawing_consent_changes_no_other_record(self):
        first = self.store.record_consent(
            "CASE-ALPHA", "Fictional permission scope one for teaching.", "2026-05-10")
        second = self.store.record_consent(
            "CASE-ALPHA", "Fictional permission scope two for review.", "2026-05-10")
        qualifier = self.store.add_identity_qualifier(
            "CASE-ALPHA", "Fictional note that must not change.", self.alpha["source_id"], "2026-05-11")
        question = self.store.add_question("CASE-ALPHA", "What did the fictional report actually say?")
        snapshot = self.store.create_snapshot(
            "CASE-ALPHA", question, "Fictional draft that must stay draft.", [self.alpha["source_id"]])
        before_second = [c for c in self.store.list_consents("CASE-ALPHA") if c["id"] == second][0]
        before_qualifier = [q for q in self.store.list_identity_qualifiers("CASE-ALPHA") if q["id"] == qualifier][0]

        self.store.withdraw_consent(
            "CASE-ALPHA", first, "Fictional reason that is long enough.", "2026-06-01")

        after = {c["id"]: c for c in self.store.list_consents("CASE-ALPHA")}
        self.assertEqual(after[first]["status"], "withdrawn")
        self.assertEqual(after[second], before_second)
        after_qualifier = [q for q in self.store.list_identity_qualifiers("CASE-ALPHA") if q["id"] == qualifier][0]
        self.assertEqual(after_qualifier, before_qualifier)
        state = self.store.state("CASE-ALPHA")
        self.assertEqual(next(q["state"] for q in state["questions"] if q["id"] == question), "open")
        self.assertEqual(next(s["state"] for s in state["snapshots"] if s["id"] == snapshot), "draft")

    def test_case_isolation_holds_for_both_lists(self):
        self.store.record_consent(
            "CASE-ALPHA", "Fictional Alpha-only permission scope.", "2026-05-10")
        self.store.add_identity_qualifier(
            "CASE-ALPHA", "Fictional Alpha-only identity note.", self.alpha["source_id"], "2026-05-11")
        self.assertEqual(self.store.list_consents("CASE-BETA"), [])
        self.assertEqual(self.store.list_identity_qualifiers("CASE-BETA"), [])
        alpha_consent = self.store.list_consents("CASE-ALPHA")[0]["id"]
        with self.assertRaisesRegex(InvalidInput, "Consent not in this case"):
            self.store.withdraw_consent("CASE-BETA", alpha_consent, "Fictional cross-case reason text.")
        self.assertEqual(self.store.list_consents("CASE-ALPHA")[0]["status"], "active")

    def test_state_includes_case_scoped_consent_slice(self):
        self.store.record_consent(
            "CASE-ALPHA", "Fictional Alpha permission for state view.", "2026-05-10")
        self.store.add_identity_qualifier(
            "CASE-ALPHA", "Fictional Alpha note for state view.", self.alpha["source_id"], "2026-05-11")
        alpha = self.store.state("CASE-ALPHA")
        beta = self.store.state("CASE-BETA")
        self.assertIn("consents", alpha)
        self.assertIn("identity_qualifiers", alpha)
        self.assertEqual(len(alpha["consents"]), 1)
        self.assertEqual(len(alpha["identity_qualifiers"]), 1)
        self.assertEqual(beta["consents"], [])
        self.assertEqual(beta["identity_qualifiers"], [])

    def test_unknown_case_rejected_at_store_boundary(self):
        with self.assertRaisesRegex(InvalidInput, "Unknown case"):
            self.store.list_consents("CASE-NOPE")
        with self.assertRaisesRegex(InvalidInput, "Unknown case"):
            self.store.list_identity_qualifiers("CASE-NOPE")

    def test_consent_optional_anchor_and_default_withdraw_date(self):
        anchor = self.alpha["source_id"]
        consent_id = self.store.record_consent(
            "CASE-ALPHA", "Fictional anchored permission scope.", "2026-05-10", anchor)
        listed = next(c for c in self.store.list_consents("CASE-ALPHA") if c["id"] == consent_id)
        self.assertIn("PATH-ALPHA@1", listed["anchor_label"])
        with self.assertRaisesRegex(InvalidInput, "Anchor source not in this case"):
            self.store.record_consent(
                "CASE-ALPHA", "Fictional bad-anchor permission scope.", "2026-05-10",
                self.beta["source_id"])
        # Withdraw without an explicit date still appends history in order.
        version = self.store.withdraw_consent(
            "CASE-ALPHA", consent_id, "Fictional default-date reason text.")
        self.assertEqual(version, 2)
        listed = next(c for c in self.store.list_consents("CASE-ALPHA") if c["id"] == consent_id)
        self.assertEqual([v["version"] for v in listed["versions"]], [1, 2])
        self.assertRegex(listed["versions"][1]["date_recorded"], r"^\d{4}-\d{2}-\d{2}$")

    def test_qualifier_anchor_line_must_exist_in_source(self):
        anchor = self.alpha["source_id"]
        qualifier_id = self.store.add_identity_qualifier(
            "CASE-ALPHA", "Fictional note with a real line anchor.", anchor, "2026-05-11",
            anchor_line=8)
        listed = next(q for q in self.store.list_identity_qualifiers("CASE-ALPHA")
                      if q["id"] == qualifier_id)
        self.assertIn("line 8", listed["anchor_label"])


class ConsentIdentityHttpTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        cls.path = str(Path(cls.tmp.name) / "consent-http.sqlite")
        seed(cls.path)
        bound = type("ConsentHttpHandler", (Handler,), {"db_path": cls.path})
        cls.server = ThreadingHTTPServer(("127.0.0.1", 0), bound)
        cls.port = cls.server.server_address[1]
        cls.thread = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.thread.start()

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.server.server_close()
        cls.thread.join(timeout=5)
        cls.tmp.cleanup()

    def call(self, path, data=None):
        headers = {}
        body = None
        if data is not None:
            headers["Content-Type"] = "application/json"
            headers["Origin"] = f"http://127.0.0.1:{self.port}"
            body = json.dumps(data).encode()
        request = Request(f"http://127.0.0.1:{self.port}{path}", data=body, headers=headers,
                          method="POST" if data is not None else "GET")
        try:
            with urlopen(request, timeout=5) as response:
                return response.status, json.loads(response.read())
        except HTTPError as error:
            return error.code, json.loads(error.read())

    def test_http_record_withdraw_list_flow(self):
        status, created = self.call("/api/cases/CASE-ALPHA/consents", {
            "scope_text": "Fictional HTTP permission for teaching.", "date_recorded": "2026-05-10"})
        self.assertEqual(status, 201)
        consent_id = created["consent_id"]
        status, listed = self.call("/api/cases/CASE-ALPHA/consents")
        self.assertEqual(status, 200)
        mine = next(c for c in listed["consents"] if c["id"] == consent_id)
        self.assertEqual(mine["status"], "active")
        status, withdrawn = self.call(f"/api/cases/CASE-ALPHA/consents/{consent_id}/withdraw", {
            "reason": "Fictional HTTP reason that is long enough.", "date_recorded": "2026-06-01"})
        self.assertEqual(status, 200)
        self.assertEqual(withdrawn["status"], "withdrawn")
        self.assertEqual(withdrawn["version"], 2)
        status, listed = self.call("/api/cases/CASE-ALPHA/consents")
        mine = next(c for c in listed["consents"] if c["id"] == consent_id)
        self.assertEqual(mine["status"], "withdrawn")
        self.assertEqual([v["status"] for v in mine["versions"]], ["active", "withdrawn"])

    def test_http_qualifier_flow_and_isolation(self):
        status, state = self.call("/api/cases/CASE-ALPHA/state")
        self.assertEqual(status, 200)
        anchor = next(s["id"] for s in state["sources"] if s["state"] == "current")
        status, created = self.call("/api/cases/CASE-ALPHA/identity-qualifiers", {
            "qualifier_text": "Fictional HTTP identity note.", "anchor_source_version_id": anchor,
            "date_recorded": "2026-05-11"})
        self.assertEqual(status, 201)
        status, listed = self.call("/api/cases/CASE-ALPHA/identity-qualifiers")
        self.assertEqual(status, 200)
        self.assertTrue(any(q["id"] == created["qualifier_id"] for q in listed["identity_qualifiers"]))
        status, beta = self.call("/api/cases/CASE-BETA/identity-qualifiers")
        self.assertEqual(status, 200)
        self.assertFalse(any(q["qualifier_text"] == "Fictional HTTP identity note."
                             for q in beta["identity_qualifiers"]))
        # Cross-case anchor fails with the existing 422 contract.
        status, beta_state = self.call("/api/cases/CASE-BETA/state")
        beta_anchor = next(s["id"] for s in beta_state["sources"] if s["state"] == "current")
        status, error = self.call("/api/cases/CASE-ALPHA/identity-qualifiers", {
            "qualifier_text": "Fictional cross-case HTTP note.", "anchor_source_version_id": beta_anchor,
            "date_recorded": "2026-05-11"})
        self.assertEqual(status, 422)

    def test_http_unknown_case_uses_existing_422_boundary(self):
        for path, data in [
            ("/api/cases/CASE-NOPE/consents", None),
            ("/api/cases/CASE-NOPE/identity-qualifiers", None),
            ("/api/cases/CASE-NOPE/consents", {"scope_text": "Fictional scope text here.", "date_recorded": "2026-05-10"}),
            ("/api/cases/CASE-NOPE/consents/1/withdraw", {"reason": "Fictional reason that is long enough."}),
            ("/api/cases/CASE-NOPE/identity-qualifiers", {
                "qualifier_text": "Fictional note text here.", "anchor_source_version_id": 1,
                "date_recorded": "2026-05-11"}),
        ]:
            with self.subTest(path=path):
                status, error = self.call(path, data)
                self.assertEqual(status, 422)
                self.assertEqual(error["error"], "Unknown case")

    def test_http_validation_rejects_bad_input_and_double_withdraw(self):
        status, error = self.call("/api/cases/CASE-ALPHA/consents", {
            "scope_text": "bad", "date_recorded": "2026-05-10"})
        self.assertEqual(status, 422)
        status, created = self.call("/api/cases/CASE-ALPHA/consents", {
            "scope_text": "Fictional HTTP validation permission scope.", "date_recorded": "2026-05-10"})
        self.assertEqual(status, 201)
        consent_id = created["consent_id"]
        status, error = self.call(f"/api/cases/CASE-ALPHA/consents/{consent_id}/withdraw", {
            "reason": "short"})
        self.assertEqual(status, 422)
        status, first = self.call(f"/api/cases/CASE-ALPHA/consents/{consent_id}/withdraw", {
            "reason": "Fictional first HTTP withdrawal reason."})
        self.assertEqual(status, 200)
        status, error = self.call(f"/api/cases/CASE-ALPHA/consents/{consent_id}/withdraw", {
            "reason": "Fictional second HTTP withdrawal reason."})
        self.assertEqual(status, 422)
        status, error = self.call("/api/cases/CASE-ALPHA/identity-qualifiers", {
            "qualifier_text": "bad", "anchor_source_version_id": 1, "date_recorded": "2026-05-11"})
        self.assertEqual(status, 422)


class ConsentIdentityUiContractTests(unittest.TestCase):
    def test_portal_contains_consent_identity_surface(self):
        html = (ROOT / "web" / "index.html").read_text()
        self.assertIn('href="#consent-identity"', html)
        self.assertIn('id="consent-identity"', html)
        self.assertIn('id="consent-form"', html)
        self.assertIn('id="consent-scope"', html)
        self.assertIn('id="consent-date"', html)
        self.assertIn('id="consent-list"', html)
        self.assertIn('id="consent-withdraw-form"', html)
        self.assertIn('id="consent-withdraw-choice"', html)
        self.assertIn('id="consent-withdraw-reason"', html)
        self.assertIn('id="consent-withdraw-date"', html)
        self.assertIn('id="qualifier-form"', html)
        self.assertIn('id="qualifier-text"', html)
        self.assertIn('id="qualifier-anchor-choice"', html)
        self.assertIn('id="qualifier-date"', html)
        self.assertIn('id="qualifier-list"', html)
        self.assertIn('<script src="/consent.js" defer></script>', html)
        self.assertIn("FICTIONAL", html)
        self.assertIn("Consent &amp; identity", html)

    def test_renderer_is_case_scoped_source_safe_and_refreshable(self):
        javascript = (ROOT / "web" / "consent.js").read_text()
        self.assertIn("/api/cases/${encodeURIComponent(caseId)}/consents", javascript)
        self.assertIn("/api/cases/${encodeURIComponent(caseId)}/identity-qualifiers", javascript)
        self.assertIn("requestSequence", javascript)
        self.assertIn("picker.value !== caseId", javascript)
        self.assertIn("MutationObserver", javascript)
        self.assertIn("textContent", javascript)
        self.assertIn("FICTIONAL", javascript)
        self.assertNotIn("innerHTML", javascript)

    def test_server_serves_renderer_and_consent_routes(self):
        server = (ROOT / "src" / "open_intelligence" / "__main__.py").read_text()
        self.assertIn('if path == "/consent.js":', server)
        self.assertIn('self._static("consent.js", "text/javascript; charset=utf-8")', server)
        self.assertIn("/consents", server)
        self.assertIn("/identity-qualifiers", server)
        self.assertIn("record_consent", server)
        self.assertIn("withdraw_consent", server)
        self.assertIn("add_identity_qualifier", server)

    def test_case_switch_guards_cover_new_fields(self):
        app = (ROOT / "web" / "app.js").read_text()
        for field in ("consent-scope", "consent-withdraw-reason", "qualifier-text",
                      "consent-date", "consent-withdraw-date", "qualifier-date"):
            self.assertIn(field, app)


if __name__ == "__main__":
    unittest.main()
