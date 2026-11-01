"""Rights-qualified evidence broker tests (issue #2).

Every test uses independently authored fixture text only. No external
content is fetched, and no rights record here asserts legal truth — the
tests prove the gate enforces what the record says, failing closed.
"""

import json
import tempfile
import threading
import unittest
from http.client import HTTPConnection
from http.server import ThreadingHTTPServer
from pathlib import Path
from urllib.error import HTTPError
from urllib.request import Request, urlopen

from open_intelligence.__main__ import Handler, seed
from open_intelligence.rights import (
    RightsError, check_link_content, excerpt_mode, normalize_permissions,
)
from open_intelligence.store import CaseStore, InvalidInput

FULL_PERMS = {
    "metadata": {"store": "allowed", "display": "allowed"},
    "full_text": {"store": "allowed", "display": "allowed"},
}
META_PERMS = {"metadata": {"store": "allowed", "display": "allowed"}}
DENIED_PERMS = {"full_text": {"store": "denied", "display": "denied"}}


def make_store() -> CaseStore:
    store = CaseStore(":memory:")
    store.add_case("CASE-ALPHA", "Fictional case Alpha")
    store.add_case("CASE-BETA", "Fictional case Beta")
    return store


def register(store: CaseStore, perms, key="EXT-1") -> int:
    return store.register_rights_source(
        key, "Fictional Archive", "v1", "2026-01-15", perms,
        attribution="Fictional archive, demo only")["rights_source_id"]


class GateTests(unittest.TestCase):
    def test_unknown_permission_fails_closed(self):
        perms = normalize_permissions({})
        self.assertEqual(excerpt_mode(perms), "citation_only")
        self.assertFalse(perms["full_text"]["store"] == "allowed")
        with self.assertRaises(RightsError):
            check_link_content(perms, citation_title="A title", excerpt=None)
        with self.assertRaises(RightsError):
            check_link_content(perms, citation_title=None, excerpt="Some excerpt text")

    def test_unknown_item_or_use_rejected(self):
        with self.assertRaises(RightsError):
            normalize_permissions({"telepathy": {"store": "allowed"}})
        with self.assertRaises(RightsError):
            normalize_permissions({"metadata": {"teleport": "allowed"}})
        with self.assertRaises(RightsError):
            normalize_permissions({"metadata": {"store": "maybe"}})

    def test_modes_follow_permissions(self):
        self.assertEqual(excerpt_mode(normalize_permissions(FULL_PERMS)), "full")
        self.assertEqual(excerpt_mode(normalize_permissions(META_PERMS)), "metadata_only")
        self.assertEqual(excerpt_mode(normalize_permissions(DENIED_PERMS)), "citation_only")
        # Partial grant is not full: display without store stays metadata_only.
        partial = normalize_permissions(
            {"metadata": {"store": "allowed"}, "full_text": {"display": "allowed"}})
        self.assertEqual(excerpt_mode(partial), "metadata_only")


class BrokerStoreTests(unittest.TestCase):
    def setUp(self):
        self.store = make_store()
        self.q_alpha = self.store.add_question("CASE-ALPHA", "What do the sources report?")
        self.q_beta = self.store.add_question("CASE-BETA", "What do the sources report?")

    def tearDown(self):
        self.store.close()

    def link(self, rights_id, **over):
        args = dict(case_id="CASE-ALPHA", question_id=self.q_alpha,
                    rights_source_id=rights_id, relation="context",
                    applicability="unknown",
                    rationale="Human review notes the limits of this source.")
        args.update(over)
        return self.store.create_broker_link(**args)

    def test_full_mode_excerpt_allowed_and_title_allowed(self):
        rid = register(self.store, FULL_PERMS)
        out = self.link(rid, citation_title="Fictional study title",
                        excerpt="A fictional excerpt passage for demo use.")
        self.assertEqual(out["mode"], "full")

    def test_metadata_only_blocks_excerpt_allows_title(self):
        rid = register(self.store, META_PERMS)
        out = self.link(rid, citation_title="Fictional study title")
        self.assertEqual(out["mode"], "metadata_only")
        with self.assertRaises(InvalidInput):
            self.link(rid, citation_title="Fictional study title",
                      excerpt="A fictional excerpt passage for demo use.")

    def test_citation_only_blocks_title_and_excerpt(self):
        rid = register(self.store, {})
        out = self.link(rid)
        self.assertEqual(out["mode"], "citation_only")
        with self.assertRaises(InvalidInput):
            self.link(rid, citation_title="Fictional study title")
        with self.assertRaises(InvalidInput):
            self.link(rid, excerpt="A fictional excerpt passage for demo use.")

    def test_wrong_case_linkage_rejected(self):
        rid = register(self.store, FULL_PERMS)
        with self.assertRaises(InvalidInput):
            self.store.create_broker_link(
                "CASE-ALPHA", self.q_beta, rid, "context", "unknown",
                "Human review notes the limits of this source.")
        with self.assertRaises(InvalidInput):
            self.store.create_broker_link(
                "CASE-BETA", self.q_alpha, rid, "context", "unknown",
                "Human review notes the limits of this source.")

    def test_promotion_of_unsupported_claims_rejected(self):
        rid = register(self.store, FULL_PERMS)
        with self.assertRaises(InvalidInput):
            self.link(rid, relation="supports", applicability="not_applicable")

    def test_negative_and_unknown_review_are_first_class(self):
        rid = register(self.store, FULL_PERMS)
        link_id = self.link(rid, relation="contradicts",
                            applicability="unknown")["broker_link_id"]
        reviewed = self.store.review_broker_link(
            "CASE-ALPHA", link_id, "contradicts", "limited",
            "Human re-review confirms limited applicability.")
        self.assertEqual(reviewed["result"], "reviewed")
        self.assertEqual(reviewed["invalidated_snapshots"], [])

    def test_review_is_case_scoped_and_stales_attached_drafts(self):
        rid = register(self.store, FULL_PERMS)
        link_id = self.link(rid)["broker_link_id"]
        with self.assertRaises(InvalidInput):
            self.store.review_broker_link(
                "CASE-BETA", link_id, "context", "unknown",
                "Human review notes the limits of this source.")
        sid = self._seed_source()
        snap = self.store.create_snapshot(
            "CASE-ALPHA", self.q_alpha, "Draft summary for review test.",
            [sid], broker_link_ids=[link_id])
        reviewed = self.store.review_broker_link(
            "CASE-ALPHA", link_id, "contradicts", "limited",
            "Human re-review confirms limited applicability.")
        self.assertEqual(reviewed["invalidated_snapshots"], [snap])
        state = self.store.state("CASE-ALPHA")
        self.assertEqual(
            [s for s in state["snapshots"] if s["id"] == snap][0]["state"], "stale")

    def test_title_needs_its_own_metadata_permission(self):
        rid = register(self.store, {"full_text": {"store": "allowed", "display": "allowed"}})
        out = self.link(rid, excerpt="A fictional excerpt passage for demo use.")
        self.assertEqual(out["mode"], "full")
        with self.assertRaises(InvalidInput):
            self.link(rid, citation_title="Fictional study title",
                      excerpt="A fictional excerpt passage for demo use.")

    def test_revoked_content_redacted_from_state_but_provenance_kept(self):
        rid = register(self.store, FULL_PERMS)
        link_id = self.link(rid, citation_title="Fictional study title",
                            excerpt="A fictional excerpt passage for demo use.")["broker_link_id"]
        self.store.revoke_rights_source(rid, "Rights withdrawn by the fictional archive.")
        state = self.store.state("CASE-ALPHA")
        row = [bl for bl in state["broker_links"] if bl["id"] == link_id][0]
        self.assertTrue(row["content_redacted"])
        self.assertIsNone(row["citation_title"])
        self.assertIsNone(row["excerpt"])
        self.assertEqual(row["mode"], "full")

    def test_revocation_stales_drafts_and_keeps_history(self):
        rid = register(self.store, FULL_PERMS)
        link_id = self.link(rid)["broker_link_id"]
        # Drafts need at least one current source version; seed one via report.
        from open_intelligence.store import parse_report  # noqa: F401 (doc anchor)
        sid = self._seed_source()
        snap = self.store.create_snapshot(
            "CASE-ALPHA", self.q_alpha, "Draft summary for stale test.",
            [sid], broker_link_ids=[link_id])
        self.assertEqual(
            [s for s in self.store.state("CASE-ALPHA")["snapshots"] if s["id"] == snap][0]["state"],
            "draft")
        out = self.store.revoke_rights_source(rid, "Rights withdrawn by the fictional archive.")
        self.assertEqual(out["invalidated_snapshots"], [snap])
        state = self.store.state("CASE-ALPHA")
        self.assertEqual(
            [s for s in state["snapshots"] if s["id"] == snap][0]["state"], "stale")
        self.assertEqual(
            [q for q in state["questions"] if q["id"] == self.q_alpha][0]["state"], "open")
        rights = [r for r in state["rights_sources"] if r["id"] == rid][0]
        self.assertEqual(rights["state"], "revoked")
        self.assertTrue(any(bl["id"] == link_id for bl in state["broker_links"]))
        # Revoked evidence cannot be attached to a new draft or re-blessed.
        with self.assertRaises(InvalidInput):
            self.store.review_broker_link("CASE-ALPHA", link_id, "context", "unknown",
                                          "Human review notes the limits of this source.")
        with self.assertRaises(InvalidInput):
            self.store.create_snapshot(
                "CASE-ALPHA", self.q_alpha, "Another draft summary here.",
                [sid], broker_link_ids=[link_id])

    def test_correction_supersedes_and_stales_old_drafts(self):
        rid = register(self.store, FULL_PERMS)
        link_id = self.link(rid)["broker_link_id"]
        sid = self._seed_source()
        snap = self.store.create_snapshot(
            "CASE-ALPHA", self.q_alpha, "Draft summary for correction test.",
            [sid], broker_link_ids=[link_id])
        out = self.store.correct_rights_source(
            rid, "v2", META_PERMS, "Terms narrowed to metadata-only use.")
        self.assertEqual(out["invalidated_snapshots"], [snap])
        state = self.store.state("CASE-ALPHA")
        by_id = {r["id"]: r for r in state["rights_sources"]}
        self.assertEqual(by_id[rid]["state"], "superseded")
        self.assertEqual(by_id[out["rights_source_id"]]["state"], "active")
        self.assertEqual(by_id[out["rights_source_id"]]["previous_id"], rid)
        # New drafts use the new row, under its narrower terms.
        new_link = self.store.create_broker_link(
            "CASE-ALPHA", self.q_alpha, out["rights_source_id"], "context", "unknown",
            "Human review notes the limits of this source.",
            citation_title="Fictional study title")
        self.assertEqual(new_link["mode"], "metadata_only")

    def test_duplicate_version_and_bad_payloads_rejected(self):
        register(self.store, FULL_PERMS)
        with self.assertRaises(InvalidInput):
            register(self.store, FULL_PERMS)
        with self.assertRaises(InvalidInput):
            self.store.register_rights_source(
                "EXT-2", "Owner", "v1", "15/01/2026", FULL_PERMS)
        with self.assertRaises(InvalidInput):
            self.store.revoke_rights_source(9999, "A sufficiently long reason here.")

    def _seed_source(self) -> int:
        text = (Path(__file__).resolve().parents[1] / "examples" / "synthetic"
                / "alpha-pathology-original.txt").read_bytes()
        result = self.store.import_report("CASE-ALPHA", text)
        state = self.store.state("CASE-ALPHA")
        return state["sources"][0]["id"]


class BrokerHttpTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        cls.path = str(Path(cls.tmp.name) / "server.sqlite")
        seed(cls.path)
        bound = type("BoundHandlerForBroker", (Handler,), {"db_path": cls.path})
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

    def request(self, path, data=None):
        headers = {"Content-Type": "application/json"} if data is not None else {}
        req = Request(f"http://127.0.0.1:{self.port}{path}",
                      data=None if data is None else json.dumps(data).encode(),
                      headers=headers)
        try:
            with urlopen(req, timeout=5) as resp:
                return resp.status, json.loads(resp.read())
        except HTTPError as err:
            return err.code, json.loads(err.read())

    def test_http_register_link_revoke_flow(self):
        status, data = self.request("/api/rights/sources", {
            "source_key": "EXT-HTTP-1", "owner": "Fictional Archive",
            "version_label": "v1", "retrieved_at": "2026-01-15",
            "permissions": FULL_PERMS})
        self.assertEqual(status, 201)
        rid = data["rights_source_id"]
        status, data = self.request("/api/cases/CASE-ALPHA/questions",
                                    {"question": "What do the sources report?"})
        qid = data["question_id"]
        status, data = self.request("/api/cases/CASE-ALPHA/broker-links", {
            "question_id": qid, "rights_source_id": rid, "relation": "context",
            "applicability": "unknown",
            "rationale": "Human review notes the limits of this source."})
        self.assertEqual(status, 201)
        self.assertEqual(data["mode"], "full")
        status, data = self.request("/api/rights/sources")
        self.assertEqual(status, 200)
        self.assertTrue(any(r["id"] == rid for r in data))
        status, data = self.request(f"/api/rights/sources/{rid}/revoke",
                                    {"reason": "Rights withdrawn by the fictional archive."})
        self.assertEqual(status, 200)
        status, data = self.request("/api/cases/CASE-ALPHA/broker-links", {
            "question_id": qid, "rights_source_id": rid, "relation": "context",
            "applicability": "unknown",
            "rationale": "Human review notes the limits of this source."})
        self.assertEqual(status, 422)


if __name__ == "__main__":
    unittest.main()
