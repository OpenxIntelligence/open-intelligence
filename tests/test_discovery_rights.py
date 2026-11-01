"""Discovery-to-rights linkage tests.

Every test uses independently authored fictional fixture text only. No
external content is fetched, and no rights record here asserts legal
truth — the tests prove revocation/correction invalidates dependent
discovery links while preserving history, failing closed.
"""

import json
import sqlite3
import tempfile
import threading
import unittest
from http.server import ThreadingHTTPServer
from pathlib import Path
from urllib.error import HTTPError
from urllib.request import Request, urlopen

from open_intelligence.__main__ import Handler, seed
from open_intelligence.store import CaseStore, InvalidInput

ROOT = Path(__file__).resolve().parents[1]
TRIAL = (ROOT / "examples" / "synthetic" / "discovery-trial-001.txt").read_bytes()
LITERATURE = (ROOT / "examples" / "synthetic" / "discovery-literature-001.txt").read_bytes()

FULL_PERMS = {
    "metadata": {"store": "allowed", "display": "allowed"},
    "full_text": {"store": "allowed", "display": "allowed"},
}
META_PERMS = {"metadata": {"store": "allowed", "display": "allowed"}}

RATIONALE = "No applicability judgement made yet for this listing."
BROKER_RATIONALE = "Human review notes the limits of this source."
QUESTION = "What fictional sources relate to this question?"


def key_variant(raw, new_key):
    lines = raw.decode().splitlines()
    assert lines[1].startswith("Discovery: "), lines[1]
    old_key = lines[1].split(": ", 1)[1]
    return raw.decode().replace(f"Discovery: {old_key}", f"Discovery: {new_key}", 1).encode()


def register(store, perms, key="EXT-1"):
    return store.register_rights_source(
        key, "Fictional Archive", "v1", "2026-01-15", perms,
        attribution="Fictional archive, demo only")["rights_source_id"]


class DiscoveryRightsStoreTests(unittest.TestCase):
    def setUp(self):
        self.store = CaseStore(":memory:")
        self.store.add_case("CASE-ALPHA", "Fictional case Alpha")
        self.question = self.store.add_question("CASE-ALPHA", QUESTION)

    def tearDown(self):
        self.store.close()

    def test_import_binding_requires_active_row(self):
        rid = register(self.store, FULL_PERMS)
        out = self.store.import_discovery(TRIAL, rights_source_id=rid)
        self.assertEqual((out["result"], out["rights_source_id"]), ("imported", rid))
        items = self.store.list_discovery()
        self.assertEqual(
            (items[0]["rights_source_id"], items[0]["rights_state"]), (rid, "active"))
        with self.assertRaises(InvalidInput):
            self.store.import_discovery(LITERATURE, rights_source_id=9999)
        with self.assertRaises(InvalidInput):
            self.store.import_discovery(LITERATURE, rights_source_id="1")
        self.store.revoke_rights_source(rid, "Rights withdrawn by the fictional archive.")
        with self.assertRaises(InvalidInput):
            self.store.import_discovery(LITERATURE, rights_source_id=rid)

    def test_import_binding_is_immutable(self):
        rid = register(self.store, FULL_PERMS)
        other = register(self.store, FULL_PERMS, key="EXT-2")
        self.store.import_discovery(TRIAL, rights_source_id=rid)
        dup = self.store.import_discovery(TRIAL, rights_source_id=rid)
        self.assertEqual((dup["result"], dup["rights_source_id"]), ("duplicate", rid))
        with self.assertRaises(InvalidInput):
            self.store.import_discovery(TRIAL, rights_source_id=other)
        self.store.import_discovery(LITERATURE)
        with self.assertRaises(InvalidInput):
            self.store.import_discovery(LITERATURE, rights_source_id=rid)

    def test_revocation_invalidates_dependent_links_and_preserves_history(self):
        rid = register(self.store, FULL_PERMS)
        disc = self.store.import_discovery(TRIAL, rights_source_id=rid)["discovery_id"]
        link = self.store.link_discovery("CASE-ALPHA", self.question, disc,
                                         "limited", RATIONALE)
        out = self.store.revoke_rights_source(rid, "Rights withdrawn by the fictional archive.")
        self.assertEqual(out["invalidated_discovery_links"], [link])
        links = self.store.case_discovery_links("CASE-ALPHA")
        self.assertEqual(len(links), 1)
        row = links[0]
        self.assertEqual(row["state"], "invalid")
        self.assertEqual(row["invalidated_cause"], "revocation")
        self.assertEqual(row["invalidated_rights_source_id"], rid)
        self.assertIsNotNone(row["invalidated_at"])
        # History preserved: assessment and item stay readable.
        self.assertEqual((row["applicability"], row["rationale"]), ("limited", RATIONALE))
        self.assertEqual(row["item"]["discovery_key"], "FICT-TRIAL-001")
        self.assertTrue(row["item"]["fictional"])
        items = self.store.list_discovery()
        self.assertEqual(len(items), 1)
        self.assertEqual(items[0]["rights_state"], "revoked")

    def test_correction_invalidates_with_cause(self):
        rid = register(self.store, FULL_PERMS)
        disc = self.store.import_discovery(TRIAL, rights_source_id=rid)["discovery_id"]
        link = self.store.link_discovery("CASE-ALPHA", self.question, disc,
                                         "unknown", RATIONALE)
        out = self.store.correct_rights_source(
            rid, "v2", META_PERMS, "Terms narrowed to metadata-only use.")
        self.assertEqual(out["invalidated_discovery_links"], [link])
        row = self.store.case_discovery_links("CASE-ALPHA")[0]
        self.assertEqual(row["state"], "invalid")
        self.assertEqual(row["invalidated_cause"], "correction")
        self.assertEqual(row["invalidated_rights_source_id"], rid)
        by_id = {r["id"]: r for r in self.store.rights_sources()}
        self.assertEqual(by_id[rid]["state"], "superseded")
        self.assertEqual(by_id[out["rights_source_id"]]["state"], "active")
        # The item's binding still points at the superseded row, so new
        # links fail closed rather than silently carrying forward.
        other_question = self.store.add_question("CASE-ALPHA", QUESTION)
        with self.assertRaises(InvalidInput):
            self.store.link_discovery("CASE-ALPHA", other_question, disc,
                                      "unknown", RATIONALE)

    def test_unrelated_links_untouched(self):
        rid_one = register(self.store, FULL_PERMS, key="EXT-1")
        rid_two = register(self.store, FULL_PERMS, key="EXT-2")
        bound = self.store.import_discovery(TRIAL, rights_source_id=rid_one)["discovery_id"]
        other = self.store.import_discovery(
            key_variant(LITERATURE, "FICT-LIT-002"), rights_source_id=rid_two)["discovery_id"]
        unlinked = self.store.import_discovery(
            key_variant(TRIAL, "FICT-TRIAL-002"))["discovery_id"]
        link_bound = self.store.link_discovery("CASE-ALPHA", self.question, bound,
                                               "unknown", RATIONALE)
        link_other = self.store.link_discovery("CASE-ALPHA", self.question, other,
                                               "unknown", RATIONALE)
        link_unlinked = self.store.link_discovery("CASE-ALPHA", self.question, unlinked,
                                                  "unknown", RATIONALE)
        out = self.store.revoke_rights_source(
            rid_one, "Rights withdrawn by the fictional archive.")
        self.assertEqual(out["invalidated_discovery_links"], [link_bound])
        by_id = {row["link_id"]: row for row in self.store.case_discovery_links("CASE-ALPHA")}
        self.assertEqual(by_id[link_bound]["state"], "invalid")
        self.assertEqual(by_id[link_other]["state"], "valid")
        self.assertIsNone(by_id[link_other]["invalidated_cause"])
        self.assertEqual(by_id[link_unlinked]["state"], "valid")
        self.assertIsNone(by_id[link_unlinked]["invalidated_cause"])

    def test_unlinked_items_stay_listable_and_linkable(self):
        disc = self.store.import_discovery(TRIAL)["discovery_id"]
        items = self.store.list_discovery()
        self.assertEqual(items[0]["rights_source_id"], None)
        self.assertEqual(items[0]["rights_state"], "unlinked")
        link = self.store.link_discovery("CASE-ALPHA", self.question, disc,
                                         "unknown", RATIONALE)
        # An unrelated revocation touches nothing unlinked.
        rid = register(self.store, FULL_PERMS)
        out = self.store.revoke_rights_source(rid, "Rights withdrawn by the fictional archive.")
        self.assertEqual(out["invalidated_discovery_links"], [])
        row = self.store.case_discovery_links("CASE-ALPHA")[0]
        self.assertEqual((row["link_id"], row["state"]), (link, "valid"))

    def test_broker_link_ids_bind_and_invalidate(self):
        rid = register(self.store, FULL_PERMS)
        broker = self.store.create_broker_link(
            "CASE-ALPHA", self.question, rid, "context", "unknown", BROKER_RATIONALE)
        broker_id = broker["broker_link_id"]
        disc = self.store.import_discovery(TRIAL)["discovery_id"]
        link = self.store.link_discovery("CASE-ALPHA", self.question, disc,
                                         "unknown", RATIONALE, [broker_id])
        row = self.store.case_discovery_links("CASE-ALPHA")[0]
        self.assertEqual(row["broker_link_ids"], [broker_id])
        self.assertEqual(row["state"], "valid")
        out = self.store.revoke_rights_source(rid, "Rights withdrawn by the fictional archive.")
        self.assertEqual(out["invalidated_discovery_links"], [link])
        row = self.store.case_discovery_links("CASE-ALPHA")[0]
        self.assertEqual(
            (row["state"], row["invalidated_cause"]), ("invalid", "revocation"))
        self.assertEqual(row["broker_link_ids"], [broker_id])

    def test_broker_link_ids_reject_revoked_wrong_case_and_wrong_question(self):
        rid = register(self.store, FULL_PERMS)
        broker_id = self.store.create_broker_link(
            "CASE-ALPHA", self.question, rid, "context", "unknown",
            BROKER_RATIONALE)["broker_link_id"]
        disc = self.store.import_discovery(TRIAL)["discovery_id"]
        with self.assertRaises(InvalidInput):
            self.store.link_discovery("CASE-ALPHA", self.question, disc,
                                      "unknown", RATIONALE, [9999])
        with self.assertRaises(InvalidInput):
            self.store.link_discovery("CASE-ALPHA", self.question, disc,
                                      "unknown", RATIONALE, [broker_id, broker_id])
        other_question = self.store.add_question("CASE-ALPHA", QUESTION)
        with self.assertRaises(InvalidInput):
            self.store.link_discovery("CASE-ALPHA", other_question, disc,
                                      "unknown", RATIONALE, [broker_id])
        self.store.add_case("CASE-BETA", "Fictional case Beta")
        beta_question = self.store.add_question("CASE-BETA", QUESTION)
        with self.assertRaises(InvalidInput):
            self.store.link_discovery("CASE-BETA", beta_question, disc,
                                      "unknown", RATIONALE, [broker_id])
        self.store.revoke_rights_source(rid, "Rights withdrawn by the fictional archive.")
        with self.assertRaises(InvalidInput):
            self.store.link_discovery("CASE-ALPHA", other_question, disc,
                                      "unknown", RATIONALE, [broker_id])

    def test_new_links_fail_closed_after_revocation(self):
        rid = register(self.store, FULL_PERMS)
        disc = self.store.import_discovery(TRIAL, rights_source_id=rid)["discovery_id"]
        self.store.link_discovery("CASE-ALPHA", self.question, disc, "unknown", RATIONALE)
        self.store.revoke_rights_source(rid, "Rights withdrawn by the fictional archive.")
        other_question = self.store.add_question("CASE-ALPHA", QUESTION)
        with self.assertRaises(InvalidInput):
            self.store.link_discovery("CASE-ALPHA", other_question, disc,
                                      "unknown", RATIONALE)

    def test_legacy_database_migrates_without_losing_rows(self):
        tmp = tempfile.TemporaryDirectory()
        try:
            path = str(Path(tmp.name) / "legacy.sqlite")
            db = sqlite3.connect(path)
            db.execute("""CREATE TABLE discovery_items (
                id INTEGER PRIMARY KEY, discovery_key TEXT NOT NULL UNIQUE,
                kind TEXT NOT NULL, title TEXT NOT NULL, registry_id TEXT, doi TEXT,
                issued_at TEXT NOT NULL, summary TEXT NOT NULL, status TEXT,
                rights TEXT NOT NULL, raw BLOB NOT NULL, created_at TEXT NOT NULL)""")
            db.execute("""CREATE TABLE discovery_links (
                id INTEGER PRIMARY KEY, case_id TEXT NOT NULL, question_id INTEGER NOT NULL,
                discovery_id INTEGER NOT NULL, applicability TEXT NOT NULL,
                rationale TEXT NOT NULL, created_at TEXT NOT NULL,
                UNIQUE(case_id,question_id,discovery_id))""")
            db.execute("""INSERT INTO discovery_items
                (id,discovery_key,kind,title,registry_id,doi,issued_at,summary,status,rights,raw,created_at)
                VALUES (1,'FICT-TRIAL-001','trial','Fictional study listing for demonstration only',
                'FICT-NCT-000001',NULL,'2026-01-15',
                'Fictional registry listing for demonstration only.','not-verified',
                'original-synthetic',?,'2026-01-15T00:00:00+00:00')""", (TRIAL,))
            db.execute("""INSERT INTO discovery_links
                (id,case_id,question_id,discovery_id,applicability,rationale,created_at)
                VALUES (1,'CASE-ALPHA',1,1,'unknown',
                'Legacy linkage kept readable after migration.',
                '2026-02-01T00:00:00+00:00')""")
            db.commit()
            db.close()
            store = CaseStore(path)
            try:
                store.add_case("CASE-ALPHA", "Fictional case Alpha")
                qid = store.add_question("CASE-ALPHA", QUESTION)
                links = store.case_discovery_links("CASE-ALPHA")
                self.assertEqual(len(links), 1)
                self.assertEqual(links[0]["state"], "valid")
                self.assertEqual(links[0]["item"]["rights_state"], "unlinked")
                self.assertEqual(links[0]["created_at"], "2026-02-01T00:00:00+00:00")
                rid = register(store, FULL_PERMS)
                disc = store.import_discovery(LITERATURE, rights_source_id=rid)["discovery_id"]
                store.link_discovery("CASE-ALPHA", qid, disc, "unknown", RATIONALE)
                self.assertEqual(len(store.case_discovery_links("CASE-ALPHA")), 2)
            finally:
                store.close()
        finally:
            tmp.cleanup()


class DiscoveryRightsHttpTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        cls.path = str(Path(cls.tmp.name) / "api.sqlite")
        seed(cls.path)
        bound = type("DiscoveryRightsTestHandler", (Handler,), {"db_path": cls.path})
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
        if data is not None:
            headers["Content-Type"] = "application/json"
            headers["Origin"] = f"http://127.0.0.1:{self.port}"
        request = Request(f"http://127.0.0.1:{self.port}{path}",
                          data=None if data is None else json.dumps(data).encode(),
                          headers=headers)
        try:
            with urlopen(request, timeout=5) as response:
                return response.status, json.loads(response.read())
        except HTTPError as error:
            return error.code, json.loads(error.read())

    def test_http_rights_linkage_flow(self):
        status, rights = self.call("/api/rights/sources", {
            "source_key": "EXT-HTTP-DISC", "owner": "Fictional Archive",
            "version_label": "v1", "retrieved_at": "2026-01-15",
            "permissions": FULL_PERMS})
        self.assertEqual(status, 201)
        rid = rights["rights_source_id"]
        status, imported = self.call("/api/discovery/imports", {
            "text": TRIAL.decode(), "rights_source_id": rid})
        self.assertEqual(status, 200)
        self.assertEqual(imported["rights_source_id"], rid)
        status, items = self.call("/api/discovery")
        self.assertEqual(items[0]["rights_state"], "active")
        status, q = self.call("/api/cases/CASE-ALPHA/questions", {"question": QUESTION})
        self.assertEqual(status, 201)
        status, broker = self.call("/api/cases/CASE-ALPHA/broker-links", {
            "question_id": q["question_id"], "rights_source_id": rid,
            "relation": "context", "applicability": "unknown",
            "rationale": BROKER_RATIONALE})
        self.assertEqual(status, 201)
        status, link = self.call("/api/cases/CASE-ALPHA/discovery-links", {
            "question_id": q["question_id"], "discovery_id": imported["discovery_id"],
            "applicability": "unknown", "rationale": RATIONALE,
            "broker_link_ids": [broker["broker_link_id"]]})
        self.assertEqual(status, 201)
        status, links = self.call("/api/cases/CASE-ALPHA/discovery")
        self.assertEqual(links[0]["state"], "valid")
        self.assertEqual(links[0]["broker_link_ids"], [broker["broker_link_id"]])
        status, revoked = self.call(f"/api/rights/sources/{rid}/revoke", {
            "reason": "Rights withdrawn by the fictional archive."})
        self.assertEqual(status, 200)
        self.assertEqual(revoked["invalidated_discovery_links"], [link["link_id"]])
        status, links = self.call("/api/cases/CASE-ALPHA/discovery")
        self.assertEqual(links[0]["state"], "invalid")
        self.assertEqual(links[0]["invalidated_cause"], "revocation")
        self.assertEqual(links[0]["rationale"], RATIONALE)
        self.assertTrue(links[0]["item"]["fictional"])
        status, q2 = self.call("/api/cases/CASE-ALPHA/questions", {"question": QUESTION})
        status, rejected = self.call("/api/cases/CASE-ALPHA/discovery-links", {
            "question_id": q2["question_id"], "discovery_id": imported["discovery_id"],
            "applicability": "unknown", "rationale": RATIONALE})
        self.assertEqual(status, 422)


if __name__ == "__main__":
    unittest.main()
