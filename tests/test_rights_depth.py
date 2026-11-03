"""Rights-retrieval depth tests (B-03, closes G-03).

Three linked behaviors: broker-link re-review propagates to citing
discovery links with cause 're-review'; an explicit human re-attachment
migrates a discovery item to a successor rights row; every broker
attachment carries a retrieval receipt beside the excerpt-or-redaction.

Every test uses independently authored fictional fixture text only. No
external content is fetched, and no receipt or rights record here asserts
legal truth — the tests prove the records describe what was recorded at
retrieval, failing closed.
"""

import copy
import json
import unittest
from pathlib import Path

from open_intelligence.store import CaseStore, InvalidInput

ROOT = Path(__file__).resolve().parents[1]
TRIAL = (ROOT / "examples" / "synthetic" / "discovery-trial-001.txt").read_bytes()
LITERATURE = (ROOT / "examples" / "synthetic" / "discovery-literature-001.txt").read_bytes()

FULL_PERMS = {
    "metadata": {"store": "allowed", "display": "allowed"},
    "full_text": {"store": "allowed", "display": "allowed"},
}
META_PERMS = {"metadata": {"store": "allowed", "display": "allowed"}}
CITATION_PERMS = {}

RATIONALE = "No applicability judgement made yet for this listing."
BROKER_RATIONALE = "Human review notes the limits of this source."
REREVIEW_RATIONALE = "Human re-review records a narrower reading of this source."
REATTACH_REASON = "Migrate listing to corrected terms after archive update."
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


class RightsDepthTests(unittest.TestCase):
    def setUp(self):
        self.store = CaseStore(":memory:")
        self.store.add_case("CASE-FIG-01", "Fictional case Fig 01")
        self.question = self.store.add_question("CASE-FIG-01", QUESTION)

    def tearDown(self):
        self.store.close()

    def broker(self, rights_id, question=None, **over):
        args = dict(case_id="CASE-FIG-01", question_id=question or self.question,
                    rights_source_id=rights_id, relation="context",
                    applicability="unknown", rationale=BROKER_RATIONALE)
        args.update(over)
        return self.store.create_broker_link(**args)["broker_link_id"]

    def test_broker_rereview_invalidates_citing_discovery_links_with_cause(self):
        rid = register(self.store, FULL_PERMS)
        broker_id = self.broker(rid)
        disc = self.store.import_discovery(TRIAL)["discovery_id"]
        link = self.store.link_discovery("CASE-FIG-01", self.question, disc,
                                         "unknown", RATIONALE, [broker_id])
        reviewed = self.store.review_broker_link(
            "CASE-FIG-01", broker_id, "contradicts", "limited", REREVIEW_RATIONALE)
        self.assertEqual(reviewed["invalidated_discovery_links"], [link])
        row = self.store.case_discovery_links("CASE-FIG-01")[0]
        self.assertEqual(row["link_id"], link)
        self.assertEqual(row["state"], "invalid")
        self.assertEqual(row["invalidated_cause"], "re-review")
        self.assertEqual(row["invalidated_broker_link_id"], broker_id)
        self.assertEqual(row["invalidated_rights_source_id"], rid)
        self.assertIsNotNone(row["invalidated_at"])
        # History preserved: assessment, bindings, and item stay readable.
        self.assertEqual((row["applicability"], row["rationale"]), ("unknown", RATIONALE))
        self.assertEqual(row["broker_link_ids"], [broker_id])
        self.assertEqual(row["item"]["discovery_key"], "FICT-TRIAL-001")
        self.assertTrue(row["item"]["fictional"])
        # A per-case event row records the invalidation.
        events = self.store.state("CASE-FIG-01")["events"]
        kinds = [event["kind"] for event in events]
        self.assertIn("discovery_invalidated", kinds)
        details = json.loads(next(
            event["details"] for event in events
            if event["kind"] == "discovery_invalidated"))
        self.assertEqual(details["reason"], "re-review")
        self.assertEqual(details["broker_link_id"], broker_id)
        self.assertEqual(details["invalidated_discovery_links"], [link])

    def test_broker_rereview_leaves_non_citing_links_valid(self):
        rid = register(self.store, FULL_PERMS)
        cited = self.broker(rid)
        other_broker = self.broker(rid)
        disc_cited = self.store.import_discovery(TRIAL)["discovery_id"]
        disc_other = self.store.import_discovery(
            key_variant(LITERATURE, "FICT-LIT-002"))["discovery_id"]
        disc_plain = self.store.import_discovery(
            key_variant(TRIAL, "FICT-TRIAL-002"))["discovery_id"]
        self.store.link_discovery("CASE-FIG-01", self.question, disc_cited,
                                  "unknown", RATIONALE, [cited])
        link_other = self.store.link_discovery("CASE-FIG-01", self.question, disc_other,
                                               "limited", RATIONALE, [other_broker])
        link_plain = self.store.link_discovery("CASE-FIG-01", self.question, disc_plain,
                                               "unknown", RATIONALE)
        before = {row["link_id"]: copy.deepcopy(row)
                  for row in self.store.case_discovery_links("CASE-FIG-01")}
        self.store.review_broker_link(
            "CASE-FIG-01", cited, "contradicts", "limited", REREVIEW_RATIONALE)
        after = {row["link_id"]: row for row in self.store.case_discovery_links("CASE-FIG-01")}
        self.assertEqual(after[link_other]["state"], "valid")
        self.assertEqual(after[link_plain]["state"], "valid")
        self.assertEqual(after[link_other], before[link_other])
        self.assertEqual(after[link_plain], before[link_plain])

    def test_correction_without_reattachment_keeps_new_links_failing_closed(self):
        rid = register(self.store, FULL_PERMS)
        disc = self.store.import_discovery(TRIAL, rights_source_id=rid)["discovery_id"]
        self.store.link_discovery("CASE-FIG-01", self.question, disc,
                                  "unknown", RATIONALE)
        corrected = self.store.correct_rights_source(
            rid, "v2", META_PERMS, "Terms narrowed to metadata-only use.")
        new_id = corrected["rights_source_id"]
        self.assertNotEqual(new_id, rid)
        # The binding still points at the superseded row as provenance.
        items = self.store.list_discovery()
        self.assertEqual(items[0]["rights_source_id"], rid)
        self.assertEqual(items[0]["rights_state"], "superseded")
        self.assertIsNone(items[0]["previous_rights_source_id"])
        self.assertEqual(self.store.discovery_reattachment_history(disc), [])
        # New links fail closed with the existing message.
        other_question = self.store.add_question("CASE-FIG-01", QUESTION)
        with self.assertRaisesRegex(InvalidInput, "not active"):
            self.store.link_discovery("CASE-FIG-01", other_question, disc,
                                      "unknown", RATIONALE)

    def test_reattachment_binds_new_row_and_permits_under_new_terms_only(self):
        rid = register(self.store, FULL_PERMS)
        disc = self.store.import_discovery(TRIAL, rights_source_id=rid)["discovery_id"]
        old_link = self.store.link_discovery("CASE-FIG-01", self.question, disc,
                                             "unknown", RATIONALE)
        corrected = self.store.correct_rights_source(
            rid, "v2", CITATION_PERMS, "Terms narrowed to citation-only use.")
        new_id = corrected["rights_source_id"]
        out = self.store.reattach_discovery_item(
            "CASE-FIG-01", disc, new_id, REATTACH_REASON)
        self.assertEqual(out["result"], "reattached")
        self.assertEqual((out["from_rights_source_id"], out["to_rights_source_id"]),
                         (rid, new_id))
        # Current binding migrated; prior binding stays visible as provenance.
        items = self.store.list_discovery()
        self.assertEqual(items[0]["rights_source_id"], new_id)
        self.assertEqual(items[0]["rights_state"], "active")
        self.assertEqual(items[0]["previous_rights_source_id"], rid)
        history = self.store.discovery_reattachment_history(disc)
        self.assertEqual(len(history), 1)
        self.assertEqual((history[0]["from_rights_source_id"],
                          history[0]["to_rights_source_id"]), (rid, new_id))
        # The old invalid link stays invalid history; it is not revived.
        by_id = {row["link_id"]: row
                 for row in self.store.case_discovery_links("CASE-FIG-01")}
        self.assertEqual(by_id[old_link]["state"], "invalid")
        # New discovery links are permitted again on a fresh question.
        other_question = self.store.add_question("CASE-FIG-01", QUESTION)
        new_link = self.store.link_discovery("CASE-FIG-01", other_question, disc,
                                             "unknown", RATIONALE)
        by_id = {row["link_id"]: row
                 for row in self.store.case_discovery_links("CASE-FIG-01")}
        self.assertEqual(by_id[new_link]["state"], "valid")
        # Broker attachments on the new row use only the new row's terms:
        # citation-only permits identity alone, not title or excerpt.
        broker_question = self.store.add_question("CASE-FIG-01", QUESTION)
        with self.assertRaises(InvalidInput):
            self.store.create_broker_link(
                "CASE-FIG-01", broker_question, new_id, "context", "unknown",
                BROKER_RATIONALE, citation_title="Fictional study title")
        with self.assertRaises(InvalidInput):
            self.store.create_broker_link(
                "CASE-FIG-01", broker_question, new_id, "context", "unknown",
                BROKER_RATIONALE, excerpt="A fictional excerpt passage for demo use.")
        allowed = self.store.create_broker_link(
            "CASE-FIG-01", broker_question, new_id, "context", "unknown",
            BROKER_RATIONALE)
        self.assertEqual(allowed["mode"], "citation_only")
        # Migration logged in both the case ledger and rights_events.
        events = self.store.state("CASE-FIG-01")["events"]
        self.assertTrue(any(event["kind"] == "discovery_reattached" for event in events))
        kinds = [row["kind"] for row in self.store.db.execute(
            "SELECT kind FROM rights_events WHERE rights_source_id=?", (new_id,)).fetchall()]
        self.assertIn("reattached", kinds)

    def test_reattachment_rejected_across_source_key_lineages(self):
        rid = register(self.store, FULL_PERMS, key="EXT-1")
        foreign = register(self.store, FULL_PERMS, key="EXT-2")
        disc = self.store.import_discovery(TRIAL, rights_source_id=rid)["discovery_id"]
        self.store.link_discovery("CASE-FIG-01", self.question, disc,
                                  "unknown", RATIONALE)
        self.store.correct_rights_source(
            rid, "v2", META_PERMS, "Terms narrowed to metadata-only use.")
        with self.assertRaisesRegex(InvalidInput, "lineage"):
            self.store.reattach_discovery_item(
                "CASE-FIG-01", disc, foreign, REATTACH_REASON)
        items = self.store.list_discovery()
        self.assertEqual(items[0]["rights_source_id"], rid)
        self.assertEqual(self.store.discovery_reattachment_history(disc), [])

    def test_no_automatic_reattachment_on_correction_import_or_read(self):
        rid = register(self.store, FULL_PERMS)
        disc = self.store.import_discovery(TRIAL, rights_source_id=rid)["discovery_id"]
        self.store.link_discovery("CASE-FIG-01", self.question, disc,
                                  "unknown", RATIONALE)
        corrected = self.store.correct_rights_source(
            rid, "v2", META_PERMS, "Terms narrowed to metadata-only use.")
        self.assertEqual(
            self.store.list_discovery()[0]["rights_source_id"], rid)
        # A later import of an unrelated item changes nothing on this binding.
        self.store.import_discovery(LITERATURE, rights_source_id=corrected["rights_source_id"])
        # Reads never migrate: list, link, state, and rights projections.
        self.store.list_discovery()
        self.store.case_discovery_links("CASE-FIG-01")
        self.store.state("CASE-FIG-01")
        self.store.rights_sources()
        by_key = {item["discovery_key"]: item for item in self.store.list_discovery()}
        self.assertEqual(by_key["FICT-TRIAL-001"]["rights_source_id"], rid)
        self.assertEqual(by_key["FICT-TRIAL-001"]["rights_state"], "superseded")
        self.assertEqual(self.store.discovery_reattachment_history(disc), [])

    def test_receipt_present_on_every_broker_attachment(self):
        full_id = register(self.store, FULL_PERMS, key="EXT-FULL")
        meta_id = register(self.store, META_PERMS, key="EXT-META")
        cite_id = register(self.store, CITATION_PERMS, key="EXT-CITE")
        full_link = self.store.create_broker_link(
            "CASE-FIG-01", self.question, full_id, "context", "unknown",
            BROKER_RATIONALE, citation_title="Fictional study title",
            excerpt="A fictional excerpt passage for demo use.")["broker_link_id"]
        meta_link = self.store.create_broker_link(
            "CASE-FIG-01", self.question, meta_id, "context", "unknown",
            BROKER_RATIONALE, citation_title="Fictional study title")["broker_link_id"]
        cite_link = self.store.create_broker_link(
            "CASE-FIG-01", self.question, cite_id, "context", "unknown",
            BROKER_RATIONALE)["broker_link_id"]
        by_id = {row["id"]: row for row in self.store.state("CASE-FIG-01")["broker_links"]}
        self.assertEqual(
            {row["receipt"]["mode"] for row in by_id.values()},
            {"full", "metadata_only", "citation_only"})
        full_receipt = by_id[full_link]["receipt"]
        self.assertEqual(full_receipt["source_key"], "EXT-FULL")
        self.assertEqual(full_receipt["version_label"], "v1")
        self.assertEqual(full_receipt["rights_source_id"], full_id)
        self.assertEqual(full_receipt["mode"], "full")
        self.assertEqual(full_receipt["permissions_relied_upon"], {
            "full_text/store": "allowed", "full_text/display": "allowed",
            "metadata/store": "allowed"})
        self.assertTrue(full_receipt["retrieved_at"])
        self.assertIn("retrieval", full_receipt["disclaimer"].lower())
        self.assertIn("not verification", full_receipt["disclaimer"].lower())
        meta_receipt = by_id[meta_link]["receipt"]
        self.assertEqual(meta_receipt["mode"], "metadata_only")
        self.assertEqual(meta_receipt["permissions_relied_upon"]["metadata/store"], "allowed")
        cite_receipt = by_id[cite_link]["receipt"]
        self.assertEqual(cite_receipt["mode"], "citation_only")
        self.assertEqual(cite_receipt["permissions_relied_upon"], {
            "full_text/store": "unknown", "full_text/display": "unknown",
            "metadata/store": "unknown"})

    def test_receipt_provenance_kept_but_content_redacted_after_revocation(self):
        rid = register(self.store, FULL_PERMS)
        broker_id = self.store.create_broker_link(
            "CASE-FIG-01", self.question, rid, "context", "unknown",
            BROKER_RATIONALE, citation_title="Fictional study title",
            excerpt="A fictional excerpt passage for demo use.")["broker_link_id"]
        before = {row["id"]: copy.deepcopy(row)
                  for row in self.store.state("CASE-FIG-01")["broker_links"]}
        self.store.revoke_rights_source(rid, "Rights withdrawn by the fictional archive.")
        after = {row["id"]: row for row in self.store.state("CASE-FIG-01")["broker_links"]}
        row = after[broker_id]
        self.assertTrue(row["content_redacted"])
        self.assertIsNone(row["citation_title"])
        self.assertIsNone(row["excerpt"])
        self.assertEqual(row["mode"], "full")
        # Receipt provenance survives redaction byte-identically.
        self.assertEqual(row["receipt"], before[broker_id]["receipt"])
        self.assertEqual(row["receipt"]["source_key"], "EXT-1")
        self.assertEqual(row["receipt"]["version_label"], "v1")
        self.assertEqual(row["receipt"]["mode"], "full")
        # Receipts never restore content access: revoked rows stay unusable.
        other_question = self.store.add_question("CASE-FIG-01", QUESTION)
        with self.assertRaises(InvalidInput):
            self.store.create_broker_link(
                "CASE-FIG-01", other_question, rid, "context", "unknown",
                BROKER_RATIONALE)
        disc = self.store.import_discovery(TRIAL)["discovery_id"]
        with self.assertRaises(InvalidInput):
            self.store.link_discovery("CASE-FIG-01", other_question, disc,
                                      "unknown", RATIONALE, [broker_id])

    def test_permission_downgrade_redacts_excerpts_on_next_read(self):
        rid = register(self.store, FULL_PERMS)
        broker_id = self.store.create_broker_link(
            "CASE-FIG-01", self.question, rid, "context", "unknown",
            BROKER_RATIONALE, citation_title="Fictional study title",
            excerpt="A fictional excerpt passage for demo use.")["broker_link_id"]
        visible = {row["id"]: row for row in self.store.state("CASE-FIG-01")["broker_links"]}
        self.assertEqual(visible[broker_id]["excerpt"],
                         "A fictional excerpt passage for demo use.")
        self.assertFalse(visible[broker_id]["content_redacted"])
        corrected = self.store.correct_rights_source(
            rid, "v2", CITATION_PERMS, "Terms narrowed to citation-only use.")
        redacted = {row["id"]: row for row in self.store.state("CASE-FIG-01")["broker_links"]}
        self.assertTrue(redacted[broker_id]["content_redacted"])
        self.assertIsNone(redacted[broker_id]["citation_title"])
        self.assertIsNone(redacted[broker_id]["excerpt"])
        # The successor row gates its own attachments under the narrower terms.
        new_question = self.store.add_question("CASE-FIG-01", QUESTION)
        with self.assertRaises(InvalidInput):
            self.store.create_broker_link(
                "CASE-FIG-01", new_question, corrected["rights_source_id"],
                "context", "unknown", BROKER_RATIONALE,
                excerpt="A fictional excerpt passage for demo use.")
        narrowed = self.store.create_broker_link(
            "CASE-FIG-01", new_question, corrected["rights_source_id"],
            "context", "unknown", BROKER_RATIONALE)
        self.assertEqual(narrowed["mode"], "citation_only")


if __name__ == "__main__":
    unittest.main()
