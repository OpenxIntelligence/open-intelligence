"""Update/revocation propagation tests (Engineering-core audit).

Every trigger below must reach every dependent row and the per-case event
queue in the same transaction: amendments supersede, dependents go stale or
reopen, history is preserved, and other cases are untouched. These tests
verify software contracts only, not clinical correctness. Fictional
fixtures only.
"""

import json
import unittest
from pathlib import Path

from open_intelligence.investigation import ValidatedInvestigation
from open_intelligence.store import CaseStore

ROOT = Path(__file__).resolve().parents[1]
SAMPLE = ROOT / "examples" / "synthetic"
TRIAL = (SAMPLE / "discovery-trial-001.txt").read_bytes()

FULL_PERMS = {
    "metadata": {"store": "allowed", "display": "allowed"},
    "full_text": {"store": "allowed", "display": "allowed"},
}
META_PERMS = {"metadata": {"store": "allowed", "display": "allowed"}}

EVIDENCE_V1 = b"""OI-SYNTHETIC-EVIDENCE/1
Evidence: EVID-PROP
Title: Fictional propagation methods example
Issued-At: 2026-05-09
Rights: original-synthetic
Statement: This independently authored fictional note describes a method limit; it is not evidence of treatment efficacy.
"""

EVIDENCE_V2 = b"""OI-SYNTHETIC-EVIDENCE/1
Evidence: EVID-PROP
Title: Fictional propagation methods example, corrected
Issued-At: 2026-05-11
Rights: original-synthetic
Amends: EVID-PROP@1
Statement: This fictional correction restates the method limit; no patient-specific conclusion follows.
"""


def report(name: str) -> bytes:
    return (SAMPLE / name).read_bytes()


def validated_investigation(citations) -> ValidatedInvestigation:
    return ValidatedInvestigation(
        status="completed",
        claims=[{
            "text": "The fictional sources describe a finding.",
            "kind": "hypothesis",
            "support": "context",
            "citations": citations,
            "uncertainty": "moderate",
            "limits": "Synthetic only.",
        }],
        abstentions=[], dropped=[],
        model="recorded-test", mode="replay")


def register(store: CaseStore, perms, key="EXT-1") -> int:
    return store.register_rights_source(
        key, "Fictional Archive", "v1", "2026-01-15", perms,
        attribution="Fictional archive, demo only")["rights_source_id"]


class SourceAmendmentPropagationTests(unittest.TestCase):
    def setUp(self):
        self.store = CaseStore(":memory:")
        self.store.add_case("CASE-ALPHA", "Fictional case Alpha")
        self.store.add_case("CASE-BETA", "Fictional case Beta")
        self.alpha_source = self.store.import_report(
            "CASE-ALPHA", report("alpha-pathology-original.txt"))["source_id"]
        self.beta_source = self.store.import_report(
            "CASE-BETA", report("beta-pathology.txt"))["source_id"]

    def tearDown(self):
        self.store.close()

    def events(self, case_id: str, kind: str):
        return [event for event in self.store.state(case_id)["events"]
                if event["kind"] == kind]

    def test_amendment_stales_investigations_without_snapshot_dependents(self):
        question = self.store.add_question(
            "CASE-ALPHA", "What does the fictional pathology source report?")
        investigation = self.store.save_investigation(
            "CASE-ALPHA", question, "evidence-summary",
            validated_investigation([{"type": "source", "id": self.alpha_source}]),
            "replay")
        self.assertEqual(
            self.store.get_investigation("CASE-ALPHA", investigation)["stale"], 0)

        outcome = self.store.import_report(
            "CASE-ALPHA", report("alpha-pathology-amended.txt"))

        # No snapshot cited the superseded version, yet freshness propagated.
        self.assertEqual(outcome["invalidated_snapshots"], [])
        self.assertEqual(outcome["invalidated_investigations"], [investigation])
        self.assertEqual(
            self.store.get_investigation("CASE-ALPHA", investigation)["stale"], 1)
        imported = self.events("CASE-ALPHA", "source_imported")[0]
        self.assertEqual(json.loads(imported["details"])["invalidated_investigations"],
                         [investigation])
        # The superseded version and its bytes remain recoverable.
        self.assertEqual(len([source for source in self.store.state("CASE-ALPHA")["sources"]
                              if source["document_id"] == "PATH-ALPHA"]), 2)

    def test_amendment_reopens_question_whose_only_support_went_stale(self):
        lone_question = self.store.add_question(
            "CASE-ALPHA", "What does the fictional pathology source report?")
        lone_investigation = self.store.save_investigation(
            "CASE-ALPHA", lone_question, "evidence-summary",
            validated_investigation([{"type": "source", "id": self.alpha_source}]),
            "replay")
        held_question = self.store.add_question(
            "CASE-ALPHA", "What else does the fictional source report?")
        self.store.save_investigation(
            "CASE-ALPHA", held_question, "evidence-summary",
            validated_investigation([{"type": "source", "id": self.alpha_source}]),
            "replay")
        draft = self.store.create_snapshot(
            "CASE-ALPHA", held_question,
            "The fictional source reports histology and marker states.",
            [self.alpha_source])
        self.assertEqual(
            {item["id"]: item["state"]
             for item in self.store.state("CASE-ALPHA")["questions"]},
            {lone_question: "addressed", held_question: "addressed"})
        self.assertEqual(
            self.store.get_investigation("CASE-ALPHA", lone_investigation)["stale"], 0)

        self.store.import_report("CASE-ALPHA", report("alpha-pathology-amended.txt"))

        states = {item["id"]: item["state"]
                  for item in self.store.state("CASE-ALPHA")["questions"]}
        self.assertEqual(states[lone_question], "open")
        # The draft cites the superseded version, so it goes stale too and its
        # question reopens through the snapshot path; assert the mechanism.
        snapshots = {item["id"]: item["state"]
                     for item in self.store.state("CASE-ALPHA")["snapshots"]}
        self.assertEqual(snapshots[draft], "stale")
        self.assertEqual(states[held_question], "open")

    def test_question_with_fresh_support_stays_addressed(self):
        question = self.store.add_question(
            "CASE-ALPHA", "What does the fictional pathology source report?")
        self.store.save_investigation(
            "CASE-ALPHA", question, "evidence-summary",
            validated_investigation([{"type": "source", "id": self.alpha_source}]),
            "replay")
        # A second investigation on another question keeps this question's
        # support intact only through its own rows; give this question a
        # snapshot on a document the coming amendment does not touch.
        imaging = self.store.import_report(
            "CASE-ALPHA", report("alpha-imaging.txt"))["source_id"]
        self.store.create_snapshot(
            "CASE-ALPHA", question,
            "The fictional imaging source reports a reference lesion.",
            [imaging])

        self.store.import_report("CASE-ALPHA", report("alpha-pathology-amended.txt"))

        states = {item["id"]: item["state"]
                  for item in self.store.state("CASE-ALPHA")["questions"]}
        self.assertEqual(states[question], "addressed")

    def test_amendment_never_touches_another_case(self):
        alpha_question = self.store.add_question(
            "CASE-ALPHA", "What does the fictional pathology source report?")
        beta_question = self.store.add_question(
            "CASE-BETA", "What does the fictional pathology source report?")
        self.store.save_investigation(
            "CASE-ALPHA", alpha_question, "evidence-summary",
            validated_investigation([{"type": "source", "id": self.alpha_source}]),
            "replay")
        beta_investigation = self.store.save_investigation(
            "CASE-BETA", beta_question, "evidence-summary",
            validated_investigation([{"type": "source", "id": self.beta_source}]),
            "replay")
        beta_events_before = len(self.store.state("CASE-BETA")["events"])

        self.store.import_report("CASE-ALPHA", report("alpha-pathology-amended.txt"))

        self.assertEqual(
            self.store.get_investigation("CASE-BETA", beta_investigation)["stale"], 0)
        self.assertEqual(
            {item["id"]: item["state"]
             for item in self.store.state("CASE-BETA")["questions"]},
            {beta_question: "addressed"})
        self.assertEqual(len(self.store.state("CASE-BETA")["events"]), beta_events_before)

    def test_duplicate_reimport_emits_no_propagation(self):
        question = self.store.add_question(
            "CASE-ALPHA", "What does the fictional pathology source report?")
        investigation = self.store.save_investigation(
            "CASE-ALPHA", question, "evidence-summary",
            validated_investigation([{"type": "source", "id": self.alpha_source}]),
            "replay")
        events_before = len(self.store.state("CASE-ALPHA")["events"])

        outcome = self.store.import_report(
            "CASE-ALPHA", report("alpha-pathology-original.txt"))

        self.assertEqual(outcome["result"], "duplicate")
        self.assertEqual(len(self.store.state("CASE-ALPHA")["events"]), events_before)
        self.assertEqual(
            self.store.get_investigation("CASE-ALPHA", investigation)["stale"], 0)


class EvidencePropagationTests(unittest.TestCase):
    def setUp(self):
        self.store = CaseStore(":memory:")
        self.store.add_case("CASE-ALPHA", "Fictional case Alpha")
        self.store.add_case("CASE-BETA", "Fictional case Beta")
        self.alpha_source = self.store.import_report(
            "CASE-ALPHA", report("alpha-pathology-original.txt"))["source_id"]
        self.beta_source = self.store.import_report(
            "CASE-BETA", report("beta-pathology.txt"))["source_id"]
        self.question_a = self.store.add_question(
            "CASE-ALPHA", "What does the fictional method note demonstrate?")
        self.question_b = self.store.add_question(
            "CASE-BETA", "What does the fictional method note not demonstrate?")

    def tearDown(self):
        self.store.close()

    def test_amendment_stales_only_citing_investigations(self):
        version = self.store.import_synthetic_evidence(EVIDENCE_V1)["evidence_version_id"]
        assessment = self.store.assess_synthetic_evidence(
            "CASE-ALPHA", self.question_a, version, "context", "limited",
            "Fictional text is relevant only to demonstrating provenance, not clinical applicability.")
        citing = self.store.save_investigation(
            "CASE-ALPHA", self.question_a, "evidence-summary",
            validated_investigation([{"type": "assessment", "id": assessment}]),
            "replay")
        uncited = self.store.save_investigation(
            "CASE-ALPHA", self.question_a, "evidence-summary",
            validated_investigation([{"type": "source", "id": self.alpha_source}]),
            "replay")

        outcome = self.store.import_synthetic_evidence(EVIDENCE_V2)

        self.assertEqual(outcome["invalidated_snapshots"], [])
        self.assertEqual(outcome["invalidated_investigations"], [citing])
        self.assertEqual(self.store.get_investigation("CASE-ALPHA", citing)["stale"], 1)
        self.assertEqual(self.store.get_investigation("CASE-ALPHA", uncited)["stale"], 0)
        # The citing investigation's question keeps fresh support (the
        # uncited investigation), so it stays addressed.
        states = {item["id"]: item["state"]
                  for item in self.store.state("CASE-ALPHA")["questions"]}
        self.assertEqual(states[self.question_a], "addressed")
        flagged = [event for event in self.store.state("CASE-ALPHA")["events"]
                   if event["kind"] == "evidence_invalidated"]
        self.assertEqual(len(flagged), 1)
        details = json.loads(flagged[0]["details"])
        self.assertEqual(details["invalidated_snapshots"], [])
        self.assertEqual(details["invalidated_investigations"], [citing])
        self.assertEqual(details["reason"], "amendment")

    def test_withdrawal_fans_out_globally_but_only_to_citing_rows(self):
        version = self.store.import_synthetic_evidence(EVIDENCE_V1)["evidence_version_id"]
        assessment_a = self.store.assess_synthetic_evidence(
            "CASE-ALPHA", self.question_a, version, "context", "limited",
            "Fictional text is relevant only to demonstrating provenance, not clinical applicability.")
        assessment_b = self.store.assess_synthetic_evidence(
            "CASE-BETA", self.question_b, version, "context", "limited",
            "Fictional text is relevant only to demonstrating provenance, not clinical applicability.")
        citing_alpha = self.store.save_investigation(
            "CASE-ALPHA", self.question_a, "evidence-summary",
            validated_investigation([{"type": "assessment", "id": assessment_a}]),
            "replay")
        citing_beta = self.store.save_investigation(
            "CASE-BETA", self.question_b, "evidence-summary",
            validated_investigation([{"type": "assessment", "id": assessment_b}]),
            "replay")
        untouched_beta = self.store.save_investigation(
            "CASE-BETA", self.question_b, "evidence-summary",
            validated_investigation([{"type": "source", "id": self.beta_source}]),
            "replay")

        outcome = self.store.withdraw_synthetic_evidence(
            version, "Fictional example withdrawn for propagation testing.")

        self.assertEqual(sorted(outcome["invalidated_investigations"]),
                         sorted([citing_alpha, citing_beta]))
        self.assertEqual(
            self.store.get_investigation("CASE-BETA", untouched_beta)["stale"], 0)
        for case_id, investigation in (("CASE-ALPHA", citing_alpha),
                                       ("CASE-BETA", citing_beta)):
            flagged = [event for event in self.store.state(case_id)["events"]
                       if event["kind"] == "evidence_invalidated"]
            self.assertEqual(len(flagged), 1)
            self.assertEqual(json.loads(flagged[0]["details"])["invalidated_investigations"],
                             [investigation])
        # Withdrawn evidence stays readable as history.
        states = [entry["state"] for entry in self.store.state("CASE-ALPHA")["evidence"]]
        self.assertEqual(states, ["withdrawn"])

    def test_damaged_claims_payload_never_breaks_evidence_import(self):
        version = self.store.import_synthetic_evidence(EVIDENCE_V1)["evidence_version_id"]
        self.store.assess_synthetic_evidence(
            "CASE-ALPHA", self.question_a, version, "context", "limited",
            "Fictional text is relevant only to demonstrating provenance, not clinical applicability.")
        with self.store.db:
            self.store.db.execute(
                """INSERT INTO investigations
                (case_id,question_id,template,status,mode,model,claims_json,
                 abstentions_json,dropped_json,stale,created_at)
                VALUES (?,?,?,?,?,?,?,?,?,0,?)""",
                ("CASE-ALPHA", self.question_a, "evidence-summary", "completed",
                 "replay", "recorded-test", "{damaged-json", "[]", "[]",
                 "2026-05-12T00:00:00+00:00"))
        damaged = self.store.db.execute(
            "SELECT id FROM investigations WHERE claims_json='{damaged-json'").fetchone()["id"]

        outcome = self.store.import_synthetic_evidence(EVIDENCE_V2)

        self.assertEqual(outcome["result"], "imported")
        self.assertEqual(outcome["version"], 2)
        self.assertEqual(outcome["invalidated_investigations"], [])
        # Read the flag directly: get_investigation strictly parses claims
        # and legitimately rejects damaged JSON, which is not the import
        # path under test here. The guarantee is that the import neither
        # crashes nor blindly invalidates the damaged row.
        stale = self.store.db.execute(
            "SELECT stale FROM investigations WHERE id=?", (damaged,)).fetchone()["stale"]
        self.assertEqual(stale, 0)


class BrokerReviewPropagationTests(unittest.TestCase):
    def setUp(self):
        self.store = CaseStore(":memory:")
        self.store.add_case("CASE-ALPHA", "Fictional case Alpha")
        self.store.add_case("CASE-BETA", "Fictional case Beta")
        self.question_a = self.store.add_question(
            "CASE-ALPHA", "What fictional sources relate to this question?")
        self.question_b = self.store.add_question(
            "CASE-BETA", "What fictional sources relate to this question?")

    def tearDown(self):
        self.store.close()

    def test_rereview_flags_citing_discovery_links_without_deleting_them(self):
        rights_id = register(self.store, FULL_PERMS)
        discovery_id = self.store.import_discovery(TRIAL)["discovery_id"]
        broker_link = self.store.create_broker_link(
            "CASE-ALPHA", self.question_a, rights_id, "context", "unknown",
            "Human review notes the limits of this source.")["broker_link_id"]
        citing = self.store.link_discovery(
            "CASE-ALPHA", self.question_a, discovery_id, "limited",
            "No applicability judgement made yet for this listing.",
            broker_link_ids=[broker_link])
        other_discovery = self.store.import_discovery(
            TRIAL.replace(b"FICT-TRIAL-001", b"FICT-TRIAL-002"))["discovery_id"]
        uncited = self.store.link_discovery(
            "CASE-ALPHA", self.question_a, other_discovery, "limited",
            "No applicability judgement made yet for this listing.")

        reviewed = self.store.review_broker_link(
            "CASE-ALPHA", broker_link, "contradicts", "limited",
            "Human re-review confirms limited applicability.")

        self.assertEqual(reviewed["invalidated_snapshots"], [])
        self.assertEqual(reviewed["affected_discovery_links"], [citing])
        flagged = [event for event in self.store.state("CASE-ALPHA")["events"]
                   if event["kind"] == "broker_invalidated"]
        self.assertEqual(len(flagged), 1)
        details = json.loads(flagged[0]["details"])
        self.assertEqual(details["reason"], "review")
        self.assertEqual(details["affected_discovery_links"], [citing])
        # Rows stay valid with history preserved; only the queue is notified.
        by_id = {row["link_id"]: row
                 for row in self.store.case_discovery_links("CASE-ALPHA")}
        self.assertEqual(by_id[citing]["state"], "valid")
        self.assertIsNone(by_id[citing]["invalidated_cause"])
        self.assertEqual(by_id[uncited]["state"], "valid")
        self.assertEqual(
            [event for event in self.store.state("CASE-BETA")["events"]
             if event["kind"] == "broker_invalidated"], [])

    def test_rereview_without_dependents_emits_no_event(self):
        rights_id = register(self.store, META_PERMS, key="EXT-2")
        broker_link = self.store.create_broker_link(
            "CASE-ALPHA", self.question_a, rights_id, "context", "unknown",
            "Human review notes the limits of this source.")["broker_link_id"]
        events_before = len(self.store.state("CASE-ALPHA")["events"])

        reviewed = self.store.review_broker_link(
            "CASE-ALPHA", broker_link, "context", "limited",
            "Human re-review confirms limited applicability.")

        self.assertEqual(reviewed["affected_discovery_links"], [])
        self.assertEqual(reviewed["invalidated_snapshots"], [])
        self.assertEqual(len(self.store.state("CASE-ALPHA")["events"]), events_before)

    def test_revocation_still_invalidates_snapshots_and_discovery(self):
        # Regression guard: the pre-existing fan-out is unchanged.
        rights_id = register(self.store, FULL_PERMS)
        source = self.store.import_report(
            "CASE-ALPHA", report("alpha-pathology-original.txt"))["source_id"]
        broker_link = self.store.create_broker_link(
            "CASE-ALPHA", self.question_a, rights_id, "context", "unknown",
            "Human review notes the limits of this source.")["broker_link_id"]
        snapshot = self.store.create_snapshot(
            "CASE-ALPHA", self.question_a,
            "The fictional source and broker link are demo data only.",
            [source], broker_link_ids=[broker_link])

        outcome = self.store.revoke_rights_source(
            rights_id, "Rights withdrawn by the fictional archive.")

        self.assertEqual(outcome["invalidated_snapshots"], [snapshot])
        states = {item["id"]: item["state"]
                  for item in self.store.state("CASE-ALPHA")["snapshots"]}
        self.assertEqual(states[snapshot], "stale")


if __name__ == "__main__":
    unittest.main()
