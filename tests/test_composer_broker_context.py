"""Original fictional broker text only; no network or real patient material."""
import json
import tempfile
import unittest
from pathlib import Path

from open_intelligence.__main__ import seed
from open_intelligence.composer import build_composer_context, composer_context_fingerprint
from open_intelligence.investigation import build_prompt, validate_output
from open_intelligence.store import CaseStore, InvalidInput


PERMS = {item: {use: "allowed" for use in ("store", "display", "ml_use")}
         for item in ("full_text", "metadata")}


def link(store, q, key="BROKER-ONE", permissions=None, case="CASE-ALPHA", **kwargs):
    rid = store.register_rights_source(key, "Fictional author", "v1", "2026-01-01",
        PERMS if permissions is None else permissions)["rights_source_id"]
    lid = store.create_broker_link(case, q, rid, kwargs.pop("relation", "contradicts"),
        "limited", "Independent fictional assessment has important limits.",
        **kwargs)["broker_link_id"]
    return rid, lid


def payload(lid):
    return {"claims": [{"text": "Fictional broker material is inconclusive.",
        "support": "contradicts", "citations": [{"type": "broker", "id": lid}],
        "uncertainty": "high", "limits": "Only independently fictional text."}],
        "abstentions": [{"topic": "Derived sensitive marker", "reason": "no_evidence"}]}


class BrokerContextTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.path = Path(self.temp.name) / "ledger.sqlite"
        seed(str(self.path))
        self.store = CaseStore(self.path)
        self.q = self.store.add_question("CASE-ALPHA", "What does this fictional evidence support?")
        self.other = self.store.add_question("CASE-ALPHA", "What remains unknown about other evidence?")

    def tearDown(self):
        self.store.close()
        self.temp.cleanup()

    def test_preview_requires_separate_model_rights_and_preserves_counterevidence(self):
        _, eligible = link(self.store, self.q, excerpt="Fictional counterevidence passage.", citation_title="Fictional title")
        _, metadata = link(self.store, self.q, "META-ONLY", permissions={"metadata": PERMS["metadata"]}, citation_title="Bibliography only")
        link(self.store, self.other, "OTHER-QUESTION", excerpt="Other question must stay isolated.")
        ctx = build_composer_context(self.store, "CASE-ALPHA", self.q)
        self.assertEqual(ctx.get("external_evidence_count"), 2)
        rows = {r["id"]: r for r in ctx["external_evidence"]}
        self.assertTrue(rows[eligible]["model_eligible"])
        self.assertEqual(rows[eligible]["relation"], "contradicts")
        self.assertEqual(rows[eligible]["applicability"], "limited")
        self.assertFalse(rows[metadata]["model_eligible"])
        self.assertIsNone(rows[metadata]["excerpt"])
        self.assertTrue(rows[metadata]["withheld_reason"])

    def test_permission_cells_fail_closed_and_denied_title_does_not_reach_prompt(self):
        perms = {"full_text": dict(PERMS["full_text"]), "metadata": {"store": "allowed", "display": "denied", "ml_use": "allowed"}}
        _, lid = link(self.store, self.q, permissions=perms,
            citation_title="RESTRICTED-TITLE", excerpt="Independent fictional excerpt without metadata.")
        facts = self.store.investigation_facts("CASE-ALPHA", self.q)
        self.assertIn(lid, facts.get("valid_brokers", set()))
        prompt = build_prompt("evidence-summary", facts["question"]["question"], facts["assertions"], facts["assessments"], facts["external_evidence"])
        self.assertNotIn("RESTRICTED-TITLE", prompt)
        public = self.store.state("CASE-ALPHA")
        self.assertIsNone(next(r for r in public["broker_links"] if r["id"] == lid)["citation_title"])
        for item in ("full_text",):
            for use in ("store", "display", "ml_use"):
                self.store.db.execute("UPDATE rights_permissions SET permission='unknown' WHERE item=? AND use=?", (item, use))
                self.store.db.commit()
                self.assertNotIn(lid, self.store.investigation_facts("CASE-ALPHA", self.q)["valid_brokers"])
                self.store.db.execute("UPDATE rights_permissions SET permission='allowed' WHERE item=? AND use=?", (item, use))
                self.store.db.commit()

    def test_snapshot_changes_for_link_review_content_and_rights_but_not_other_question(self):
        rid, lid = link(self.store, self.q, excerpt="Original fictional external excerpt.")
        before = composer_context_fingerprint(self.store, "CASE-ALPHA", self.q)
        link(self.store, self.other, "UNRELATED", excerpt="Unrelated fictional external excerpt.")
        self.assertEqual(before, composer_context_fingerprint(self.store, "CASE-ALPHA", self.q))
        self.store.review_broker_link("CASE-ALPHA", lid, "context", "unknown", "Review now identifies additional uncertainty.")
        reviewed = composer_context_fingerprint(self.store, "CASE-ALPHA", self.q)
        self.assertNotEqual(before, reviewed)
        self.store.db.execute("UPDATE broker_links SET excerpt=? WHERE id=?", ("Corrected independently fictional text.", lid))
        self.store.db.commit()
        self.assertNotEqual(reviewed, composer_context_fingerprint(self.store, "CASE-ALPHA", self.q))
        before = composer_context_fingerprint(self.store, "CASE-ALPHA", self.q)
        self.store.revoke_rights_source(rid, "Fictional rights declaration revoked.")
        self.assertNotEqual(before, composer_context_fingerprint(self.store, "CASE-ALPHA", self.q))

    def test_saved_receipts_survive_restart_and_revocation_withholds_all_derived_text(self):
        rid, lid = link(self.store, self.q, excerpt="Independently fictional source passage.")
        facts = self.store.investigation_facts("CASE-ALPHA", self.q)
        validated = validate_output(payload(lid), facts["valid_sources"], facts["valid_assessments"], facts.get("valid_brokers", set()))
        validated.dropped = [{"claim": "Derived sensitive marker", "reason": "language_guard"}]
        iid = self.store.save_investigation("CASE-ALPHA", self.q, "evidence-summary", validated, "replay",
            context_fingerprint=facts.get("context_fingerprint"), input_receipts=facts.get("input_receipts"))
        self.store.close()
        self.store = CaseStore(self.path)
        saved = self.store.get_investigation("CASE-ALPHA", iid)
        self.assertEqual(saved["input_receipts"][0]["broker_link_id"], lid)
        self.assertEqual(saved["input_receipts"][0].get("relation"), "contradicts")
        self.assertEqual(saved["input_receipts"][0].get("applicability"), "limited")
        self.assertEqual(saved["kind"], "hypothesis")
        self.assertEqual(saved["review_state"], "pending")
        self.store.revoke_rights_source(rid, "Fictional declaration withdrawn after execution.")
        redacted = self.store.get_investigation("CASE-ALPHA", iid)
        self.assertTrue(redacted["stale"])
        self.assertTrue(redacted["output_withheld"])
        self.assertEqual(redacted["claims"], [])
        self.assertEqual(redacted["abstentions"], [])
        self.assertEqual(redacted["dropped"], [])
        self.assertNotIn("Derived sensitive marker", json.dumps(redacted))

    def test_broker_citations_require_captured_inputs_and_metadata_is_not_support(self):
        _, lid = link(self.store, self.q, excerpt="Independently fictional source passage.")
        valid = validate_output(payload(lid), set(), set(), {lid})
        self.assertEqual(len(valid.claims), 1)
        with self.assertRaises(InvalidInput):
            self.store.save_investigation("CASE-ALPHA", self.q, "evidence-summary", valid, "replay")
        self.assertEqual(validate_output(payload(lid), set(), set()).claims, [])
        self.assertEqual(validate_output(payload(True), set(), set(), {1}).claims, [])

    def test_prompt_budget_citations_are_exactly_the_broker_text_actually_present(self):
        _, first = link(self.store, self.q, excerpt="First fictional source is available.")
        for number in range(55):
            link(self.store, self.q, f"BOUND-{number}", excerpt=f"Fictional passage {number} " + "z" * 1100)
        facts = self.store.investigation_facts("CASE-ALPHA", self.q)
        prompt = build_prompt("evidence-summary", facts["question"]["question"], facts["assertions"], facts["assessments"], facts["external_evidence"])
        self.assertLessEqual(len(prompt), 64000)
        self.assertIn(first, facts["valid_brokers"])
        self.assertLess(len(facts["valid_brokers"]), 56)
        for row in facts["external_evidence"]:
            self.assertEqual(f"broker_id={row['id']} " in prompt, row["id"] in facts["valid_brokers"])
            valid = validate_output(payload(row["id"]), facts["valid_sources"], facts["valid_assessments"], facts["valid_brokers"])
            self.assertEqual(bool(valid.claims), row["id"] in facts["valid_brokers"])

    def test_denied_metadata_cannot_be_laundered_through_excerpt(self):
        perms = {"full_text": dict(PERMS["full_text"]), "metadata": {"store": "allowed", "display": "allowed", "ml_use": "denied"}}
        _, lid = link(self.store, self.q, permissions=perms, citation_title="RESTRICTED TITLE",
                      excerpt="RESTRICTED TITLE appears in this independently fictional excerpt.")
        facts = self.store.investigation_facts("CASE-ALPHA", self.q)
        prompt = build_prompt("evidence-summary", facts["question"]["question"], facts["assertions"], facts["assessments"], facts["external_evidence"])
        self.assertNotIn(lid, facts["valid_brokers"])
        self.assertNotIn("RESTRICTED TITLE", prompt)

    def test_review_and_correction_hold_only_dependent_model_output(self):
        rid, lid = link(self.store, self.q, excerpt="Independently fictional source passage.")
        def save(q):
            facts = self.store.investigation_facts("CASE-ALPHA", q)
            valid = validate_output(payload(lid), facts["valid_sources"], facts["valid_assessments"], facts["valid_brokers"])
            return self.store.save_investigation("CASE-ALPHA", q, "evidence-summary", valid, "replay",
                context_fingerprint=facts["context_fingerprint"], input_receipts=facts["input_receipts"])
        affected, unrelated = save(self.q), save(self.other)
        self.store.review_broker_link("CASE-ALPHA", lid, "context", "unknown", "Reassessment creates new uncertainty for review.")
        self.assertTrue(self.store.get_investigation("CASE-ALPHA", affected)["output_withheld"])
        self.assertFalse(self.store.get_investigation("CASE-ALPHA", unrelated)["stale"])
        new_run = save(self.q)
        self.store.correct_rights_source(rid, "v2", {}, "Fictional permission declaration corrected.")
        self.assertTrue(self.store.get_investigation("CASE-ALPHA", new_run)["output_withheld"])
        self.assertFalse(self.store.get_investigation("CASE-ALPHA", unrelated)["stale"])

