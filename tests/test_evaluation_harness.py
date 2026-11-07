"""Tests for the deterministic evaluation harness (program plan
slice C5, Notion OI-09 section 9).

No live model call is made here: every probe runs offline against
the real K-checks, the Skeptic wiring (stub verdicts), T6 grouping,
and the replay check. The sensitivity tests deliberately weaken a
K-check (or a D5 compose rule) and prove the harness fails — a
harness that cannot fail measures nothing.
"""

import unittest

from open_intelligence.evaluation import (
    check_prose_attribution,
    fixture_context,
    probe_appointments,
    probe_care_team,
    probe_contradiction,
    probe_hypothesis,
    probe_hypothesis_composition,
    probe_notifications,
    probe_prose_attribution,
    probe_referrals,
    probe_route_replay,
    probe_scope,
    probe_skeptic_wiring,
    probe_staleness,
    probe_temporal,
    record_spot_check_set,
    run_evaluation_suite,
)
from open_intelligence.hypothesis import compose_hypothesis
from open_intelligence.investigation import validate_output


def _weakened(check):
    """A validate_fn that simulates a K-check failing to catch: any
    drop (and any run-level finding) from that check is undone, the
    claim kept instead."""

    def weakened(payload, valid_sources, valid_assessments, context=None):
        result = validate_output(payload, valid_sources, valid_assessments, context)
        rescued = [entry for entry in result.dropped
                   if entry.get("check") == check]
        result.dropped = [entry for entry in result.dropped
                          if entry.get("check") != check]
        result.claims = list(result.claims) + [entry["claim"] for entry in rescued]
        result.findings = [entry for entry in result.findings
                           if entry.get("check") != check]
        return result

    return weakened


class MetricValueTests(unittest.TestCase):
    def test_m5_temporal_recall_is_complete(self):
        metric = probe_temporal()["metric"]
        self.assertEqual(metric["caught"], 5)
        self.assertEqual(metric["planted"], 5)
        self.assertEqual(metric["false_positives"], 0)
        self.assertEqual(metric["value"], 1.0)
        self.assertTrue(metric["pass"])

    def test_m6_contradiction_recall_and_precision(self):
        metric = probe_contradiction()["metric"]
        self.assertEqual(metric["caught"], 2)
        self.assertEqual(metric["planted"], 2)
        self.assertEqual(metric["false_positives"], 0)
        self.assertEqual(metric["value"], 1.0)
        self.assertTrue(metric["pass"])

    def test_m7_staleness_recall_is_complete(self):
        metric = probe_staleness()["metric"]
        self.assertEqual(metric["caught"], 4)
        self.assertEqual(metric["planted"], 4)
        self.assertEqual(metric["false_positives"], 0)
        self.assertEqual(metric["value"], 1.0)
        self.assertTrue(metric["pass"])

    def test_m8_scope_leakage_is_zero(self):
        metric = probe_scope()["metric"]
        self.assertEqual(metric["planted"], 8)
        self.assertEqual(metric["caught"], 8)
        self.assertEqual(metric["leaked"], 0)
        self.assertEqual(metric["false_positives"], 0)
        self.assertTrue(metric["pass"])

    def test_m10_hypothesis_support_is_complete(self):
        metric = probe_hypothesis()["metric"]
        self.assertEqual(metric["correct"], 6)
        self.assertEqual(metric["total"], 6)
        self.assertEqual(metric["value"], 1.0)
        self.assertTrue(metric["pass"])

    def test_m16_replay_is_deterministic(self):
        outcome = probe_route_replay()
        self.assertEqual(outcome["m16"]["identical"], 3)
        self.assertEqual(outcome["m16"]["replays"], 3)
        self.assertEqual(outcome["m16"]["value"], 1.0)
        self.assertTrue(outcome["m16"]["pass"])
        # Every tamper probe must fail replay with its typed reason.
        by_name = {item["name"]: item for item in outcome["probes"]}
        self.assertTrue(by_name["missing-route-fails-replay"]["pass"])
        self.assertTrue(by_name["amended-source-fails-replay"]["pass"])
        self.assertTrue(by_name["tampered-input-fails-replay"]["pass"])

    def test_m27_routing_record_is_complete(self):
        outcome = probe_route_replay()
        self.assertEqual(outcome["m27"]["complete"], 1)
        self.assertEqual(outcome["m27"]["runs"], 1)
        self.assertEqual(outcome["m27"]["value"], 1.0)
        self.assertTrue(outcome["m27"]["pass"])

    def test_m28_prose_attribution_is_complete(self):
        metric = probe_prose_attribution()["metric"]
        self.assertEqual(metric["correct"], 6)
        self.assertEqual(metric["total"], 6)
        self.assertEqual(metric["value"], 1.0)
        self.assertEqual(metric["response_level"], 1.0)
        self.assertTrue(metric["pass"])


class ProseAttributionTests(unittest.TestCase):
    def test_relation_verb_k7_misses_is_caught(self):
        # "31" is in the evidence, so K7 keeps the claim; M28 must
        # still fail it on the unsupported relation verb "increased".
        context = fixture_context()
        validated = validate_output(
            {"claims": [{"text": "The lesion increased to 31 mm.",
                         "support": "context",
                         "citations": [{"type": "source", "id": 2}],
                         "uncertainty": "moderate", "limits": "Synthetic only."}],
             "abstentions": []},
            {1, 2, 3, 4, 5}, {1}, context)
        self.assertEqual(len(validated.claims), 1)
        checked = check_prose_attribution(
            "The lesion increased to 31 mm.", context, cited_sources={2})
        self.assertFalse(checked["pass"])
        self.assertIn({"kind": "relation", "unit": "increased"}, checked["missing"])

    def test_temporal_word_k7_misses_is_caught(self):
        context = fixture_context()
        checked = check_prose_attribution(
            "The lesion was measured as 31 mm after treatment.",
            context, cited_sources={2})
        self.assertFalse(checked["pass"])
        self.assertIn({"kind": "temporal", "unit": "after"}, checked["missing"])

    def test_unknown_entity_is_caught(self):
        context = fixture_context()
        checked = check_prose_attribution(
            "The marker-b value was reported.", context, cited_sources={1})
        self.assertFalse(checked["pass"])
        self.assertIn({"kind": "entity", "unit": "marker-b"}, checked["missing"])

    def test_supported_sentence_passes(self):
        context = fixture_context()
        checked = check_prose_attribution(
            "The lesion was measured as 31 mm.", context, cited_sources={2})
        self.assertTrue(checked["pass"])
        self.assertEqual(checked["missing"], [])

    def test_unit_free_sentence_passes_without_false_positive(self):
        context = fixture_context()
        checked = check_prose_attribution(
            "The examination identified a finding.", context, cited_sources={1})
        self.assertTrue(checked["pass"])
        self.assertEqual(checked["units"], [])


class SkepticWiringTests(unittest.TestCase):
    def test_skeptic_wiring_probes_pass(self):
        probes = probe_skeptic_wiring()["probes"]
        self.assertEqual(len(probes), 3)
        for item in probes:
            self.assertTrue(item["pass"], item)


def _weakened_compose(sentences, kept_claims, *, tiers=None, substance_names=()):
    """A compose_fn that ignores the over-length rule: an over-long
    composition is kept instead of rejected."""
    result = compose_hypothesis(
        sentences, kept_claims, tiers=tiers, substance_names=substance_names)
    if not any(v.get("reason") == "over_length"
               for v in result.get("violations", [])):
        return result
    result = dict(result)
    result["violations"] = [v for v in result["violations"]
                            if v.get("reason") != "over_length"]
    if not result["violations"]:
        result["status"] = "composed"
        result["text"] = " ".join(s["text"] for s in sentences)
        result["claim_ids"] = sorted(
            {claim for s in sentences for claim in s.get("claim_ids", [])})
        result["char_count"] = len(result["text"])
    return result


class CompositionAndCareLoopTests(unittest.TestCase):
    """Wave slice W3: the D5–D9 probe families. These are probe
    families, not M-metrics: they measure composition/report assembly
    and the care loop, and a failing family fails the suite."""

    def test_d5_composition_probes_pass(self):
        outcome = probe_hypothesis_composition()
        by_family = {}
        for item in outcome["probes"]:
            by_family.setdefault(item["family"], []).append(item)
        self.assertEqual(
            {item["name"] for item in by_family["D5-composition"]},
            {"over-length", "missing-citation", "unknown-claim",
             "unsupported-number", "unsupported-identifier",
             "unsupported-substance", "scope-language",
             "malformed-identifier", "low-tier-without-phrase",
             "low-tier-with-phrase", "valid-composition"})
        self.assertEqual(
            {item["name"] for item in by_family["D5-report"]},
            {"fixed-section-order", "trial-label-present",
             "literature-metadata-only", "counts-match",
             "stored-hypothesis-in-report", "not-composed-without-stored",
             "invalidated-hypothesis-not-in-report"})
        self.assertEqual(len(outcome["probes"]), 18)
        for item in outcome["probes"]:
            self.assertTrue(item["pass"], item)

    def test_d6_appointment_probes_pass(self):
        outcome = probe_appointments()
        self.assertEqual(
            {item["name"] for item in outcome["probes"]},
            {"record-plan", "reschedule-changes-date-time",
             "reschedule-noop-rejected", "cancel-terminal",
             "complete-terminal", "history-append-only",
             "invalid-date-rejected"})
        self.assertEqual(len(outcome["probes"]), 7)
        for item in outcome["probes"]:
            self.assertTrue(item["pass"], item)

    def test_d7_notification_probes_pass(self):
        outcome = probe_notifications()
        self.assertEqual(
            {item["name"] for item in outcome["probes"]},
            {"overdue-exactly-once", "due-soon-not-overdue",
             "exclusive-transition", "recheck-on-amendment",
             "rereview-and-stale-on-amendment", "appointment-due",
             "patient-clear-carve-out", "counts-match"})
        self.assertEqual(len(outcome["probes"]), 8)
        for item in outcome["probes"]:
            self.assertTrue(item["pass"], item)

    def test_d8_referral_probes_pass(self):
        outcome = probe_referrals()
        self.assertEqual(
            {item["name"] for item in outcome["probes"]},
            {"lifecycle", "exactly-one-outcome", "pinned-kinds",
             "outcome-requires-acknowledgement",
             "acknowledge-requires-requested", "anchor-must-be-current",
             "materials-pinned", "sends-nothing", "review-acknowledges"})
        self.assertEqual(len(outcome["probes"]), 9)
        for item in outcome["probes"]:
            self.assertTrue(item["pass"], item)

    def test_d9_care_team_probes_pass(self):
        outcome = probe_care_team()
        self.assertEqual(
            {item["name"] for item in outcome["probes"]},
            {"shared-update-same-record", "author-role-boundary",
             "handoff-lifecycle", "close-requires-acknowledged",
             "amendment-reopens-handoff", "update-review",
             "handoff-review"})
        self.assertEqual(len(outcome["probes"]), 7)
        for item in outcome["probes"]:
            self.assertTrue(item["pass"], item)

    def test_new_families_add_no_metric(self):
        report = run_evaluation_suite()
        self.assertEqual(
            set(report["metrics"]),
            {"M5", "M6", "M7", "M8", "M10", "M16", "M27", "M28"})
        families = {item["family"] for item in report["probes"]}
        for family in ("D5-composition", "D5-report", "D6-appointments",
                       "D7-notifications", "D8-referrals", "D9-care-team"):
            self.assertIn(family, families)


class SensitivityTests(unittest.TestCase):
    def test_weakened_k3_fails_m5_and_the_suite(self):
        report = run_evaluation_suite(validate_fn=_weakened("K3"))
        self.assertLess(report["metrics"]["M5"]["value"], 1.0)
        self.assertFalse(report["metrics"]["M5"]["pass"])
        self.assertFalse(report["passed"])
        self.assertIn("M5", [entry["metric"] for entry in report["failures"]])

    def test_weakened_k4_fails_m6_and_the_suite(self):
        report = run_evaluation_suite(validate_fn=_weakened("K4"))
        self.assertLess(report["metrics"]["M6"]["value"], 1.0)
        self.assertFalse(report["metrics"]["M6"]["pass"])
        self.assertFalse(report["passed"])
        self.assertIn("M6", [entry["metric"] for entry in report["failures"]])

    def test_weakened_k7_fails_m10(self):
        report = run_evaluation_suite(validate_fn=_weakened("K7"))
        self.assertLess(report["metrics"]["M10"]["value"], 1.0)
        self.assertFalse(report["metrics"]["M10"]["pass"])
        self.assertFalse(report["passed"])

    def test_weakened_compose_fails_d5_and_the_suite(self):
        # The over-length rule is ignored, so the over-length probe
        # fails; the K-check metrics are untouched, so the failure
        # comes only from the D5-composition family entry.
        report = run_evaluation_suite(compose_fn=_weakened_compose)
        for metric in report["metrics"].values():
            self.assertTrue(metric["pass"], metric)
        self.assertFalse(report["passed"])
        self.assertIn("D5-composition",
                      [entry["metric"] for entry in report["failures"]])
        failed = [item for item in report["probes"]
                  if item["family"] == "D5-composition" and not item["pass"]]
        self.assertEqual([item["name"] for item in failed], ["over-length"])


class SpotCheckSetTests(unittest.TestCase):
    def test_thirty_items_is_complete(self):
        recorded = record_spot_check_set(
            [{"id": f"item-{index}"} for index in range(30)])
        self.assertEqual(recorded["count"], 30)
        self.assertTrue(recorded["complete"])
        self.assertEqual(recorded["labels_pending"], 30)

    def test_twenty_nine_items_is_incomplete(self):
        recorded = record_spot_check_set(
            [{"id": f"item-{index}"} for index in range(29)])
        self.assertFalse(recorded["complete"])

    def test_labels_are_recorded_not_performed(self):
        recorded = record_spot_check_set([
            {"id": "a", "label": "confirmed"},
            {"id": "b"},
        ])
        self.assertEqual(recorded["labelled"], 1)
        self.assertEqual(recorded["labels_pending"], 1)


class SuiteReportTests(unittest.TestCase):
    def test_suite_passes_on_healthy_code(self):
        report = run_evaluation_suite()
        self.assertTrue(report["passed"], report["failures"])
        self.assertEqual(report["failures"], [])
        self.assertEqual(report["model_calls"], 0)
        self.assertEqual(report["mode"], "offline-deterministic")

    def test_report_carries_every_metric(self):
        report = run_evaluation_suite()
        self.assertEqual(
            set(report["metrics"]),
            {"M5", "M6", "M7", "M8", "M10", "M16", "M27", "M28"})
        for metric_id, metric in report["metrics"].items():
            self.assertIn("value", metric, metric_id)
            self.assertIn("target", metric, metric_id)
            self.assertIn("pass", metric, metric_id)

    def test_model_dependent_metrics_are_listed_not_measured(self):
        report = run_evaluation_suite()
        not_measured = {entry["metric"] for entry in report["not_measured"]}
        self.assertIn("M25", not_measured)
        self.assertIn("M26", not_measured)
        self.assertIn("M29", not_measured)

    def test_spot_check_set_is_recorded_and_complete(self):
        report = run_evaluation_suite()
        self.assertGreaterEqual(report["spot_check"]["count"], 30)
        self.assertTrue(report["spot_check"]["complete"])
        self.assertEqual(report["spot_check"]["labelled"], 0)

    def test_live_model_gap_is_recorded_as_a_note(self):
        report = run_evaluation_suite()
        self.assertTrue(any("402" in note for note in report["notes"]))


if __name__ == "__main__":
    unittest.main()
