"""Tests for the Skeptic (A6), one repair round, and reconciliation
(program plan slice C4, Notion OI-09 sections 4.6 and 5.4).

Fixtures are written from the Notion spec, not from the implementation:
the planted misstatement passes K1-K7 by construction (verified
against run_kchecks here), the repair fixtures are K-drops a
restatement can fix, and the contradiction fixtures are the same
source-vs-source disagreement the K4 rule already describes.

No live model call is made here: the Skeptic and repair model calls
are injectable, and every test drives them with stubs. The live prompt
is verified separately against the Meta Model API on synthetic data.
"""

import json
import unittest
from pathlib import Path

from open_intelligence.agent_writes import build_investigation_contract
from open_intelligence.investigation import validate_output
from open_intelligence.vertical import get_vertical

# The oncology wiring, resolved through the vertical interface (slice
# V1) instead of imported from the vertical module.
_ONCOLOGY = get_vertical("oncology")
ONCOLOGY_SYNONYMS = _ONCOLOGY.synonyms
K6_SCOPE_PATTERNS = _ONCOLOGY.scope_patterns
CONDITION_TERMS = _ONCOLOGY.condition_terms
from open_intelligence.kchecks import (
    KCheckContext,
    Slot,
    SourceVersionInfo,
    build_kcheck_context,
    run_kchecks,
)
from open_intelligence.orchestrator import decide_route
from open_intelligence.skeptic import (
    ABSTENTION_CODES,
    REPAIRABLE_REASONS,
    SKEPTIC_AGENT_ROLE,
    SKEPTIC_MODEL,
    SKEPTIC_PROMPT_VERSION,
    SkepticError,
    build_skeptic_prompt,
    cited_evidence,
    compute_abstention_codes,
    parse_skeptic_output,
    run_skeptic,
    run_verification,
)
from open_intelligence.store import CaseStore, now_utc
from open_intelligence.synthesis import (
    group_run_contradictions,
    group_source_contradictions,
    group_timeline_conflicts,
    group_timeline_gaps,
)


def claim(text, source_id=1, assessment_id=None, limits="Synthetic only."):
    citations = [{"type": "source", "id": source_id}]
    if assessment_id is not None:
        citations.append({"type": "assessment", "id": assessment_id})
    return {"text": text, "kind": "hypothesis", "support": "context",
            "citations": citations, "uncertainty": "moderate", "limits": limits}


def _version(version_id, *, state="current", specimen="SPEC-A",
             specimen_date="2026-05-03", report_date="2026-05-05",
             received_date="2026-05-06T10:00:00Z", supersedes_id=None):
    return SourceVersionInfo(
        id=version_id, specimen_date=specimen_date, report_date=report_date,
        received_date=received_date, state=state, supersedes_id=supersedes_id,
        sha256=f"digest-{version_id}", specimen_id=specimen)


def make_context(**overrides):
    """A small synthetic case: v1 pathology (SPEC-A) says marker-a was
    not tested; v4 is a second current SPEC-A document that disagrees
    with v1 on marker-a; v3 is the superseded reading v1 replaces; v5
    is a SPEC-B document that agrees with v4. Mirrors the K-check
    fixture, trimmed to the versions this slice's tests need."""
    versions = {
        1: _version(1, supersedes_id=3),
        2: _version(2, specimen="SPEC-B", specimen_date="2026-05-17",
                    report_date="2026-05-18", received_date="2026-05-19T10:00:00Z"),
        3: _version(3, state="superseded", specimen_date="2026-05-01",
                    report_date="2026-05-02", received_date="2026-05-03T10:00:00Z"),
        4: _version(4),
        5: _version(5, specimen="SPEC-B", specimen_date="2026-05-17",
                    report_date="2026-05-18", received_date="2026-05-19T10:00:00Z"),
    }
    slots = [
        Slot(subject="CASE-X", field="marker-a", value="not-reported",
             source_version_id=1, specimen="SPEC-A",
             quote="Marker A was not tested in this specimen."),
        Slot(subject="CASE-X", field="histology", value="reported",
             source_version_id=1, specimen="SPEC-A",
             quote="The examination identified a finding."),
        Slot(subject="CASE-X", field="lesion-size", value="reported",
             source_version_id=2, specimen="SPEC-B",
             quote="The lesion was measured as 31 mm."),
        Slot(subject="CASE-X", field="marker-a", value="reported",
             source_version_id=3, specimen="SPEC-A",
             quote="Marker A was reported."),
        Slot(subject="CASE-X", field="marker-a", value="reported",
             source_version_id=4, specimen="SPEC-A",
             quote="Marker A was reported."),
        Slot(subject="CASE-X", field="marker-a", value="reported",
             source_version_id=5, specimen="SPEC-B",
             quote="Marker A was reported."),
    ]
    context = KCheckContext(
        subject="CASE-X", source_versions=versions, derived_slots=slots,
        assessment_statements={
            1: "This independently authored note describes an assay limitation; "
               "it is not evidence of efficacy.",
        },
        snapshot_as_of="2026-06-01T00:00:00Z",
        snapshot_source_ids={1, 2, 4, 5},
        synonyms=ONCOLOGY_SYNONYMS, scope_patterns=K6_SCOPE_PATTERNS,
        condition_terms=CONDITION_TERMS,
        substance_names=["fictional-substance-x", "fictional-substance-y"],
    )
    for key, value in overrides.items():
        setattr(context, key, value)
    return context


VALID_SOURCES = {1, 2, 3, 4, 5}
VALID_ASSESSMENTS = {1}
FACTS = {"valid_sources": VALID_SOURCES, "valid_assessments": VALID_ASSESSMENTS}


def validated_claims(texts, context=None):
    """Validate raw claim texts through validate_output + K-checks."""
    context = context or make_context()
    payload = {"claims": [claim(text) if isinstance(text, str) else text
                          for text in texts], "abstentions": []}
    return validate_output(payload, VALID_SOURCES, VALID_ASSESSMENTS, context)


class CountingStub:
    """A stub model call that records prompts and returns canned JSON."""

    def __init__(self, payload):
        self.payload = payload
        self.calls = 0
        self.prompts = []

    def __call__(self, prompt):
        self.calls += 1
        self.prompts.append(prompt)
        if isinstance(self.payload, Exception):
            raise self.payload
        return self.payload


def skeptic_stub(verdicts):
    """A Skeptic stub returning one verdict per claim, in order."""
    reviews = [
        {"claim_index": index, "verdict": verdict,
         "reason": f"stub review {index}: {verdict}"}
        for index, verdict in enumerate(verdicts)
    ]
    return CountingStub({"reviews": reviews})


def repair_stub(repairs):
    """A repair stub returning one repair per attempted claim."""
    entries = [
        {"claim_index": index, "repaired_text": text,
         "cannot_repair": text is None,
         "reason": f"stub repair {index}"}
        for index, text in enumerate(repairs)
    ]
    return CountingStub({"repairs": entries})


class SkepticPromptTests(unittest.TestCase):
    def test_prompt_contains_only_claim_and_cited_evidence(self):
        # Independence is the point: each claim's block lists only its
        # own cited quotes, never the template, the question, or another
        # claim's evidence.
        context = make_context()
        first = claim("The lesion was measured as 31 cm.", source_id=2)
        second = claim("Marker A was not tested.", source_id=1)
        entries = [
            {"claim_index": 0, "text": first["text"],
             "evidence": cited_evidence(first, context)},
            {"claim_index": 1, "text": second["text"],
             "evidence": cited_evidence(second, context)},
        ]
        prompt = build_skeptic_prompt(entries)
        self.assertIn("The lesion was measured as 31 cm.", prompt)
        self.assertIn("The lesion was measured as 31 mm.", prompt)
        self.assertIn("Marker A was not tested.", prompt)
        self.assertNotIn("evidence-summary", prompt)
        self.assertNotIn("What does the source report?", prompt)
        first_block = prompt.split("Claim 0:")[1].split("Claim 1:")[0]
        self.assertIn("31 mm", first_block)
        self.assertNotIn("Marker A was not tested in this specimen.", first_block)

    def test_prompt_version_model_and_role_constants(self):
        self.assertEqual(SKEPTIC_PROMPT_VERSION, "skeptic:1")
        self.assertEqual(SKEPTIC_MODEL, "muse-spark-1.3")
        self.assertEqual(SKEPTIC_AGENT_ROLE, "A6")
        self.assertIn("AB-CONFLICT", ABSTENTION_CODES)
        self.assertIn("AB-STALE", ABSTENTION_CODES)
        self.assertIn("AB-BUDGET", ABSTENTION_CODES)
        self.assertIn("AB-MODEL", ABSTENTION_CODES)
        self.assertIn("AB-ALL-DROPPED", ABSTENTION_CODES)

    def test_cited_evidence_uses_only_the_claims_citations(self):
        context = make_context()
        evidence = cited_evidence(
            claim("The lesion was measured as 31 cm.", source_id=2), context)
        self.assertEqual([item["label"] for item in evidence], ["source 2"])
        self.assertEqual(evidence[0]["quote"], "The lesion was measured as 31 mm.")
        assessment = cited_evidence(
            claim("A note applies.", source_id=1, assessment_id=1), context)
        self.assertEqual(
            [item["label"] for item in assessment],
            ["source 1", "source 1", "assessment 1"])
        self.assertEqual(
            {item["quote"] for item in assessment},
            {"Marker A was not tested in this specimen.",
             "The examination identified a finding.",
             "This independently authored note describes an assay limitation; "
             "it is not evidence of efficacy."})


class SkepticParseTests(unittest.TestCase):
    def test_unknown_verdict_is_schema_invalid(self):
        with self.assertRaises(SkepticError):
            parse_skeptic_output(
                {"reviews": [{"claim_index": 0, "verdict": "maybe",
                              "reason": "unsure"}]}, 1)

    def test_missing_review_becomes_uncertain_not_dropped(self):
        reviews = parse_skeptic_output(
            {"reviews": [{"claim_index": 0, "verdict": "supported",
                          "reason": "matches the quote"}]}, 2)
        self.assertEqual(reviews[0]["verdict"], "supported")
        self.assertEqual(reviews[1]["verdict"], "uncertain")
        self.assertIn("no review returned", reviews[1]["reason"])

    def test_run_skeptic_returns_typed_record(self):
        stub = skeptic_stub(["supported"])
        record = run_skeptic(
            [{"claim_index": 0, "text": "The lesion was measured as 31 mm.",
              "evidence": [{"label": "source 2",
                            "quote": "The lesion was measured as 31 mm."}]}],
            call_model=stub)
        self.assertEqual(record["status"], "completed")
        self.assertEqual(record["model"], "muse-spark-1.3")
        self.assertEqual(record["prompt_version"], "skeptic:1")
        self.assertEqual(record["reviews"][0]["verdict"], "supported")


class SkepticVerificationTests(unittest.TestCase):
    def test_skeptic_catches_planted_misstatement_kchecks_miss(self):
        # The premise, proved here: 31 mm restated as 31 cm passes
        # K1-K7 (K7 sees "31" in the evidence; the unit change is
        # invisible to the deterministic checks).
        context = make_context()
        validated = validated_claims(
            [claim("The lesion was measured as 31 cm.", source_id=2)], context)
        self.assertEqual(len(validated.claims), 1)
        self.assertEqual(validated.dropped, [])
        record = run_verification(
            validated, context, FACTS, mode="live",
            skeptic_call=skeptic_stub(["challenged"]),
            repair_call=repair_stub([]))
        self.assertEqual(validated.claims, [])
        self.assertEqual(validated.status, "abstained")
        self.assertEqual(len(validated.dropped), 1)
        held = validated.dropped[0]
        self.assertEqual(held["reason"], "skeptic_challenged")
        self.assertEqual(held["check"], "skeptic")
        # Never deletes: the original claim text and the challenge are
        # preserved in the record.
        self.assertEqual(held["claim"]["text"], "The lesion was measured as 31 cm.")
        self.assertIn("challenged", held["detail"]["verdict"])
        codes = [code for code in record["abstention_codes"]
                 if code["code"] == "AB-CONFLICT"]
        self.assertEqual([code["origin"] for code in codes], ["skeptic_challenge"])
        self.assertEqual(record["skeptic"]["status"], "completed")
        self.assertEqual(record["skeptic"]["reviews"][0]["verdict"], "challenged")

    def test_skeptic_supported_keeps_claim(self):
        context = make_context()
        validated = validated_claims(
            [claim("The lesion was measured as 31 mm.", source_id=2)], context)
        record = run_verification(
            validated, context, FACTS, mode="live",
            skeptic_call=skeptic_stub(["supported"]),
            repair_call=repair_stub([]))
        self.assertEqual(len(validated.claims), 1)
        self.assertEqual(validated.status, "completed")
        self.assertEqual(record["abstention_codes"], [])

    def test_skeptic_uncertain_raises_uncertainty_and_notes_limits(self):
        context = make_context()
        validated = validated_claims(
            [claim("The lesion was measured as 31 mm.", source_id=2)], context)
        record = run_verification(
            validated, context, FACTS, mode="live",
            skeptic_call=skeptic_stub(["uncertain"]),
            repair_call=repair_stub([]))
        self.assertEqual(len(validated.claims), 1)
        self.assertEqual(validated.claims[0]["uncertainty"], "high")
        self.assertIn("Skeptic could not verify", validated.claims[0]["limits"])
        self.assertEqual(record["abstention_codes"], [])

    def test_skeptic_failure_records_ab_model_and_keeps_claims(self):
        context = make_context()
        validated = validated_claims(
            [claim("The lesion was measured as 31 mm.", source_id=2)], context)
        record = run_verification(
            validated, context, FACTS, mode="live",
            skeptic_call=CountingStub(RuntimeError("network down")),
            repair_call=repair_stub([]))
        # A failed Skeptic does not fail the run: the K-checked claim
        # is still stored, with AB-MODEL making the gap visible.
        self.assertEqual(len(validated.claims), 1)
        self.assertEqual(validated.status, "completed")
        self.assertEqual(record["skeptic"]["status"], "failed")
        self.assertEqual(
            [code["code"] for code in record["abstention_codes"]], ["AB-MODEL"])

    def test_skeptic_budget_exceeded_records_ab_budget(self):
        context = make_context()
        validated = validated_claims(
            [claim("The lesion was measured as 31 mm.", source_id=2)], context)
        record = run_verification(
            validated, context, FACTS, mode="live",
            skeptic_call=skeptic_stub(["supported"]),
            repair_call=repair_stub([]),
            call_budget={"skeptic_calls": 1, "repair_calls": 0})
        self.assertEqual(len(validated.claims), 1)
        self.assertEqual(record["skeptic"]["status"], "skipped")
        self.assertEqual(
            [code["code"] for code in record["abstention_codes"]], ["AB-BUDGET"])


class RepairRoundTests(unittest.TestCase):
    def test_repair_fixes_fixable_claim(self):
        context = make_context()
        validated = validated_claims(
            [claim("The lesion was measured as 42 mm.", source_id=2)], context)
        self.assertEqual(validated.claims, [])
        self.assertEqual(validated.dropped[0]["reason"], "k7_unsupported_token")
        record = run_verification(
            validated, context, FACTS, mode="live",
            skeptic_call=skeptic_stub(["supported"]),
            repair_call=repair_stub(["The lesion was measured as 31 mm."]))
        self.assertEqual(len(validated.claims), 1)
        self.assertEqual(validated.claims[0]["text"], "The lesion was measured as 31 mm.")
        self.assertEqual(validated.status, "completed")
        repair = record["repair"]
        self.assertEqual(repair["status"], "completed")
        self.assertEqual(repair["rounds"], 1)
        self.assertEqual(repair["attempts"][0]["original_text"],
                         "The lesion was measured as 42 mm.")
        self.assertEqual(repair["attempts"][0]["reason"], "k7_unsupported_token")
        self.assertEqual(repair["repaired"][0]["recheck"], "kept")
        self.assertEqual(repair["unrepaired"], [])

    def test_repair_never_runs_twice(self):
        # Two repairable drops, one repair call: the round is one call
        # for all repairable claims, and it never runs a second time.
        # (The second fixture is a K2 slot mismatch: "reported" against
        # a source that says not tested; the repair restates it from
        # the cited quote. An NCT repair would fail K7 instead, because
        # the identifier is not in the cited evidence.)
        context = make_context()
        validated = validated_claims(
            [claim("The lesion was measured as 42 mm.", source_id=2),
             "Marker A was reported."], context)
        self.assertEqual(len(validated.dropped), 2)
        self.assertEqual(
            {entry["reason"] for entry in validated.dropped},
            {"k7_unsupported_token", "k2_slot_mismatch"})
        self.assertTrue(all(entry["reason"] in REPAIRABLE_REASONS
                            for entry in validated.dropped))
        stub = repair_stub(["The lesion was measured as 31 mm.",
                            "Marker A was not tested."])
        record = run_verification(
            validated, context, FACTS, mode="live",
            skeptic_call=skeptic_stub(["supported", "supported"]),
            repair_call=stub)
        self.assertEqual(stub.calls, 1)
        self.assertEqual(record["repair"]["rounds"], 1)
        self.assertEqual(len(validated.claims), 2)

    def test_repair_drops_unfixable_claim(self):
        context = make_context()
        validated = validated_claims(
            [claim("The lesion was measured as 42 mm.", source_id=2)], context)
        record = run_verification(
            validated, context, FACTS, mode="live",
            skeptic_call=skeptic_stub([]),
            repair_call=repair_stub([None]))
        self.assertEqual(validated.claims, [])
        self.assertEqual(validated.status, "abstained")
        self.assertEqual(record["repair"]["unrepaired"][0]["reason"],
                         "k7_unsupported_token")
        self.assertEqual(
            [code["code"] for code in record["abstention_codes"]],
            ["AB-ALL-DROPPED"])

    def test_repair_restatement_still_failing_stays_dropped(self):
        context = make_context()
        validated = validated_claims(
            [claim("The lesion was measured as 42 mm.", source_id=2)], context)
        record = run_verification(
            validated, context, FACTS, mode="live",
            skeptic_call=skeptic_stub([]),
            repair_call=repair_stub(["The lesion was measured as 99 mm."]))
        self.assertEqual(validated.claims, [])
        self.assertEqual(validated.dropped[0]["reason"], "k7_unsupported_token")
        self.assertEqual(validated.dropped[0]["detail"]["repaired_text"],
                         "The lesion was measured as 99 mm.")
        self.assertEqual(record["repair"]["unrepaired"][0]["detail"],
                         "re-check dropped: k7_unsupported_token")

    def test_k4_contradiction_is_not_repaired(self):
        # Restating one side to match the other would be merging by
        # rewrite, which the reconciliation rule forbids: the repair
        # round is never attempted for a K4 drop.
        context = make_context()
        validated = validated_claims(
            ["Marker A was not tested.",
             claim("Marker A was reported.", source_id=4)], context)
        self.assertEqual(len(validated.claims), 1)
        self.assertEqual(validated.dropped[0]["reason"], "k4_contradiction")
        stub = repair_stub([])
        record = run_verification(
            validated, context, FACTS, mode="live",
            skeptic_call=skeptic_stub(["supported"]),
            repair_call=stub)
        self.assertEqual(stub.calls, 0)
        self.assertEqual(record["repair"]["rounds"], 0)
        self.assertEqual(len(validated.dropped), 1)
        self.assertEqual(validated.dropped[0]["reason"], "k4_contradiction")
        # The run's own claims disagree (agent_divergence) and the
        # underlying sources disagree too (source_disagreement): both
        # origins are visible, never merged into one code.
        origins = [code["origin"] for code in record["abstention_codes"]
                   if code["code"] == "AB-CONFLICT"]
        self.assertIn("agent_divergence", origins)
        self.assertIn("source_disagreement", origins)

    def test_k6_scope_and_k5_stale_are_not_repaired(self):
        context = make_context()
        validated = validated_claims(
            ["The first-line choice should be discussed.",
             claim("Marker A was reported.", source_id=3)], context)
        self.assertEqual(
            {entry["reason"] for entry in validated.dropped},
            {"k6_scope", "k5_stale"})
        stub = repair_stub([])
        record = run_verification(
            validated, context, FACTS, mode="live",
            skeptic_call=skeptic_stub([]),
            repair_call=stub)
        self.assertEqual(stub.calls, 0)
        self.assertEqual(record["repair"]["rounds"], 0)
        self.assertEqual(
            {entry["reason"] for entry in validated.dropped},
            {"k6_scope", "k5_stale"})
        codes = {code["code"] for code in record["abstention_codes"]}
        self.assertIn("AB-STALE", codes)
        self.assertIn("AB-ALL-DROPPED", codes)


class AbstentionCodeTests(unittest.TestCase):
    def test_ab_all_dropped_when_every_claim_fails(self):
        codes = compute_abstention_codes(
            kept_count=0, attempted_count=2, k4_present=False,
            source_disagreement=False, skeptic_challenged=False, stale=False,
            budget_exceeded=False, model_failed=False)
        self.assertEqual([code["code"] for code in codes], ["AB-ALL-DROPPED"])

    def test_no_ab_all_dropped_when_nothing_was_attempted(self):
        codes = compute_abstention_codes(
            kept_count=0, attempted_count=0, k4_present=False,
            source_disagreement=False, skeptic_challenged=False, stale=False,
            budget_exceeded=False, model_failed=False)
        self.assertEqual(codes, [])

    def test_ab_stale_from_k5_finding(self):
        context = make_context(
            expected_snapshot_hash="digest-old", current_snapshot_hash="digest-new")
        validated = validated_claims(
            [claim("The lesion was measured as 31 mm.", source_id=2)], context)
        self.assertTrue(any(
            finding.get("reason") == "k5_snapshot_changed"
            for finding in validated.findings))
        record = run_verification(
            validated, context, FACTS, mode="live",
            skeptic_call=skeptic_stub(["supported"]),
            repair_call=repair_stub([]))
        codes = {code["code"] for code in record["abstention_codes"]}
        self.assertIn("AB-STALE", codes)
        self.assertEqual(validated.status, "completed")

    def test_ab_conflict_source_disagreement(self):
        # The run cites source 1; v1 and v4 (both current, same
        # specimen) disagree on marker-a, so the run's answer rests on
        # a disputed source.
        context = make_context()
        validated = validated_claims(["Marker A was not tested."], context)
        self.assertEqual(len(validated.claims), 1)
        record = run_verification(
            validated, context, FACTS, mode="live",
            skeptic_call=skeptic_stub(["supported"]),
            repair_call=repair_stub([]))
        codes = [code for code in record["abstention_codes"]
                 if code["code"] == "AB-CONFLICT"]
        self.assertEqual([code["origin"] for code in codes], ["source_disagreement"])
        groups = record["t6"]["contradictions"]
        self.assertEqual(len(groups), 1)
        group = groups[0]
        self.assertEqual(group["origin"], "source_disagreement")
        self.assertEqual(group["field"], "marker-a")
        self.assertEqual(sorted(group["values"]), ["not reported", "reported"])
        self.assertEqual(group["source_version_ids"], [1, 4])
        self.assertIn("evidence_needed", group)
        self.assertNotIn("winner", group)
        self.assertNotIn("merged", group)


class ReplayModeTests(unittest.TestCase):
    def test_replay_skips_model_passes_but_still_reconciles(self):
        # In replay there is no model call: a stub that raises proves
        # no call is attempted, while T6 grouping and codes still run.
        def _exploding_stub(prompt):
            raise AssertionError("no model call may run in replay mode")

        context = make_context()
        validated = validated_claims(
            ["Marker A was not tested.",
             claim("Marker A was reported.", source_id=4)], context)
        record = run_verification(
            validated, context, FACTS, mode="replay",
            skeptic_call=_exploding_stub, repair_call=_exploding_stub)
        self.assertEqual(record["skeptic"]["status"], "skipped")
        self.assertEqual(record["skeptic"]["reason"], "replay")
        self.assertEqual(record["repair"]["status"], "skipped")
        self.assertEqual(record["repair"]["reason"], "replay")
        origins = [code["origin"] for code in record["abstention_codes"]
                   if code["code"] == "AB-CONFLICT"]
        self.assertIn("agent_divergence", origins)
        self.assertEqual(len(validated.claims), 1)


class T6GroupingTests(unittest.TestCase):
    def test_source_group_lists_both_sides_never_merges(self):
        groups = group_source_contradictions(make_context())
        self.assertEqual(len(groups), 1)
        group = groups[0]
        self.assertEqual(group["kind"], "contradiction")
        self.assertEqual(group["origin"], "source_disagreement")
        self.assertEqual(sorted(group["values"]), ["not reported", "reported"])
        self.assertIn("Marker A was not tested in this specimen.", group["quotes"])
        self.assertIn("Marker A was reported.", group["quotes"])
        # No merged verdict, no winner, no vote: dissent stays listed.
        for forbidden in ("winner", "merged", "verdict", "consensus"):
            self.assertNotIn(forbidden, group)

    def test_superseded_version_never_joins_group(self):
        # v3 is superseded by v1: its disagreement is resolved by
        # supersession, not a live conflict.
        groups = group_source_contradictions(make_context())
        self.assertEqual(groups[0]["source_version_ids"], [1, 4])

    def test_different_specimen_never_joins_group(self):
        # v5 (SPEC-B) agrees with v4 but disagrees with v1 on a
        # different specimen: that is a specimen difference, not a
        # contradiction, so no group may name source 5.
        groups = group_source_contradictions(make_context())
        self.assertTrue(all(5 not in group["source_version_ids"] for group in groups))

    def test_run_contradiction_groups_carry_both_claims(self):
        context = make_context()
        validated = validated_claims(
            ["Marker A was not tested.",
             claim("Marker A was reported.", source_id=4)], context)
        groups = group_run_contradictions(validated.dropped)
        self.assertEqual(len(groups), 1)
        self.assertEqual(groups[0]["origin"], "agent_divergence")
        self.assertEqual(groups[0]["claim_indices"], [0, 1])
        self.assertEqual(groups[0]["source_version_ids"], [1, 4])
        self.assertEqual(sorted(groups[0]["values"]), ["not reported", "reported"])

    def test_timeline_gaps_and_conflicts_grouped(self):
        timeline = {
            "gaps": [{
                "start_date": "2026-05-07", "end_date": "2026-05-16",
                "before": {"occurred": "2026-05-06", "document_ids": ["DOC-A"]},
                "after": {"occurred": "2026-05-17", "document_ids": ["DOC-B"]},
            }],
            "entries": [
                {"source_id": 1, "document_id": "DOC-A", "occurred": "2026-05-06"},
                {"source_id": 2, "document_id": "DOC-B", "occurred": None},
            ],
            "conflicts": [{
                "conflict_key": "specimen:SPEC-A",
                "kind": "specimen_occurred_conflict",
                "status": "unknown",
                "asserted_occurred_dates": ["2026-05-03", "2026-05-04"],
                "sources": [{"source_id": 1}, {"source_id": 4}],
            }],
        }
        gaps = group_timeline_gaps(timeline)
        self.assertEqual(len(gaps), 2)
        self.assertEqual(gaps[0]["start_date"], "2026-05-07")
        self.assertIn("a source covering 2026-05-07 to 2026-05-16",
                      gaps[0]["evidence_needed"])
        self.assertIn("no occurred date", gaps[1]["what"])
        conflicts = group_timeline_conflicts(timeline)
        self.assertEqual(len(conflicts), 1)
        self.assertEqual(conflicts[0]["origin"], "source_disagreement")
        self.assertEqual(conflicts[0]["conflict_key"], "specimen:SPEC-A")
        self.assertIn("evidence_needed", conflicts[0])


def seed_case(store, case_id="CASE-ALPHA"):
    """A fictional case with one imported source and one question."""
    store.add_case(case_id, f"Fictional case {case_id}")
    synthetic = Path(__file__).resolve().parents[1] / "examples" / "synthetic"
    source_id = store.import_report(
        case_id, (synthetic / "alpha-pathology-original.txt").read_bytes()
    )["source_id"]
    question_id = store.add_question(case_id, "What does the source report?")
    return source_id, question_id


def save_run_with_verification(store, case_id, question_id, source_id,
                               verification):
    """Save one replay investigation with its contract and record."""
    decide_route(store, case_id, "evidence-summary", question_id, "clinician")
    facts = store.investigation_facts(case_id, question_id)
    validated = validate_output(
        {"claims": [claim("The sources report a finding.", source_id=source_id)],
         "abstentions": []},
        facts["valid_sources"], facts["valid_assessments"])
    validated.model = "recorded-replay"
    validated.mode = "replay"
    contract = build_investigation_contract(
        store, case_id, question_id, "evidence-summary", "recorded-replay",
        facts=facts)
    run_id = store.save_investigation(
        case_id, question_id, "evidence-summary", validated, "replay",
        write_contract=contract, verification_record=verification)
    return run_id


class PersistenceTests(unittest.TestCase):
    def setUp(self):
        self.store = CaseStore(":memory:")
        self.source_id, self.question_id = seed_case(self.store)

    def tearDown(self):
        self.store.close()

    def _verification(self):
        """Run C4 in replay mode over the seeded case's facts."""
        facts = self.store.investigation_facts("CASE-ALPHA", self.question_id)
        context = build_kcheck_context(
            facts, self.store.source_version_facts("CASE-ALPHA"),
            case_id="CASE-ALPHA", snapshot_as_of=now_utc(),
            synonyms=ONCOLOGY_SYNONYMS, scope_patterns=K6_SCOPE_PATTERNS,
            condition_terms=CONDITION_TERMS, substance_names=[],
            evidence_tiers={})
        validated = validate_output(
            {"claims": [claim("The sources report a finding.",
                              source_id=self.source_id)], "abstentions": []},
            facts["valid_sources"], facts["valid_assessments"], context)
        record = run_verification(
            validated, context, facts, mode="replay",
            store=self.store, case_id="CASE-ALPHA")
        return validated, record

    def test_verification_record_persists_and_reads_back(self):
        validated, record = self._verification()
        self.assertEqual(len(validated.claims), 1)
        run_id = save_run_with_verification(
            self.store, "CASE-ALPHA", self.question_id, self.source_id, record)
        stored = self.store.get_investigation("CASE-ALPHA", run_id)
        self.assertEqual(stored["verification"], record)
        self.assertEqual(stored["verification"]["skeptic"]["status"], "skipped")

    def test_pre_c4_row_reads_with_null_verification(self):
        decide_route(self.store, "CASE-ALPHA", "evidence-summary",
                     self.question_id, "clinician")
        facts = self.store.investigation_facts("CASE-ALPHA", self.question_id)
        validated = validate_output(
            {"claims": [claim("The sources report a finding.",
                              source_id=self.source_id)], "abstentions": []},
            facts["valid_sources"], facts["valid_assessments"])
        validated.model = "recorded-replay"
        validated.mode = "replay"
        contract = build_investigation_contract(
            self.store, "CASE-ALPHA", self.question_id, "evidence-summary",
            "recorded-replay", facts=facts)
        run_id = self.store.save_investigation(
            "CASE-ALPHA", self.question_id, "evidence-summary", validated,
            "replay", write_contract=contract)
        stored = self.store.get_investigation("CASE-ALPHA", run_id)
        self.assertIsNone(stored["verification"])

    def test_ab_stale_keeps_question_open(self):
        _validated, record = self._verification()
        record = dict(record)
        record["abstention_codes"] = [
            {"code": "AB-STALE", "detail": "inputs superseded during the run"}]
        save_run_with_verification(
            self.store, "CASE-ALPHA", self.question_id, self.source_id, record)
        state = self.store.db.execute(
            "SELECT state FROM questions WHERE id=? AND case_id=?",
            (self.question_id, "CASE-ALPHA")).fetchone()[0]
        self.assertEqual(state, "open")

    def test_completed_run_without_ab_stale_addresses_question(self):
        _validated, record = self._verification()
        self.assertEqual(record["abstention_codes"], [])
        save_run_with_verification(
            self.store, "CASE-ALPHA", self.question_id, self.source_id, record)
        state = self.store.db.execute(
            "SELECT state FROM questions WHERE id=? AND case_id=?",
            (self.question_id, "CASE-ALPHA")).fetchone()[0]
        self.assertEqual(state, "addressed")


if __name__ == "__main__":
    unittest.main()
