"""Tests for the synthetic-fixture metrics projection (B-10, closes G-10).

Fictional fixtures only. No model is called here: investigations are
validated locally with validate_output and stored in replay-labeled form,
and the no-model-call test patches the network path to fail loudly.

Every test builds freshly authored fictional bytes (never pre-seeded
metric states) and asserts exact counts against the underlying ledger.
"""

import hashlib
import json
import tempfile
import threading
import unittest
from datetime import datetime
from http.server import ThreadingHTTPServer
from pathlib import Path
from unittest.mock import patch
from urllib.error import HTTPError
from urllib.request import Request, urlopen

from open_intelligence.__main__ import Handler, seed
from open_intelligence.investigation import ABSTAIN_REASONS, validate_output
from open_intelligence.store import CaseStore, InvalidInput
from open_intelligence.synthetic_metrics import (
    NON_TRANSFERABLE_LABEL,
    SYNTHETIC_ONLY_LABEL,
    case_metrics,
    fixture_run,
)

MANIFEST = json.loads((Path(__file__).resolve().parent / "synthetic_metrics_manifest.json").read_text())


def _report(patient, document, event_date="2026-05-20", issued="2026-05-21",
            amends=None, findings=(("fig-marker", "reported", "Fictional note records the marker as present."),)):
    lines = ["OI-SYNTHETIC-REPORT/1", f"Patient: {patient}", f"Document: {document}",
             "Type: laboratory", f"Event-Date: {event_date}", f"Issued-At: {issued}"]
    if amends is not None:
        lines.append(f"Amends: {amends}")
    for key, state, quote in findings:
        lines.append(f"Finding: {key}|{state}|{quote}")
    return ("\n".join(lines) + "\n").encode("utf-8")


def _evidence(key, title="Fictional example study summary", issued="2026-05-10",
              statement="A fictional example statement used only for metrics fixtures.",
              amends=None):
    lines = ["OI-SYNTHETIC-EVIDENCE/1", f"Evidence: {key}", f"Title: {title}",
             f"Issued-At: {issued}", "Rights: original-synthetic"]
    if amends is not None:
        lines.append(f"Amends: {amends}")
    lines.append(f"Statement: {statement}")
    return ("\n".join(lines) + "\n").encode("utf-8")


def _add_case_with_source(store, case_id, document="DOC-FIG"):
    store.add_case(case_id, f"Fictional case {case_id}")
    result = store.import_report(case_id, _report(case_id, document))
    return result["source_id"]


def _save_replay(store, case_id, question_id, payload):
    facts = store.investigation_facts(case_id, question_id)
    validated = validate_output(payload, facts["valid_sources"], facts["valid_assessments"])
    validated.model = "recorded-replay"
    validated.mode = "replay"
    return store.save_investigation(case_id, question_id, "evidence-summary", validated, "replay")


def _ledger_fingerprint(store):
    tables = [row[0] for row in store.db.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%' ORDER BY name").fetchall()]
    fingerprint = {}
    for table in tables:
        rows = store.db.execute(f'SELECT * FROM "{table}" ORDER BY rowid').fetchall()
        fingerprint[table] = hashlib.sha256(repr([tuple(row) for row in rows]).encode("utf-8")).hexdigest()
    return fingerprint


def _event_occurred(store, case_id, event_id):
    row = store.db.execute("SELECT occurred_at FROM events WHERE case_id=? AND id=?",
                           (case_id, event_id)).fetchone()
    return row["occurred_at"]


def _build_rich_case(store, case_id):
    """One source amendment with a completed rereview; callers add evidence/investigations."""
    _add_case_with_source(store, case_id)
    question_id = store.add_question(case_id, "What does the fictional record show so far?")
    state = store.state(case_id)
    source_ids = [item["id"] for item in state["sources"] if item["state"] == "current"]
    snapshot_id = store.create_snapshot(case_id, question_id, "Human draft summary for metrics.", source_ids)
    store.acknowledge_demo_review(case_id, snapshot_id, "FICTIONAL-REVIEWER-B")
    store.import_report(case_id, _report(case_id, "DOC-FIG", amends="DOC-FIG@1"))
    followup_id = store.add_question(case_id, "What fictional follow-up is recorded after review?")
    state = store.state(case_id)
    fresh_ids = [item["id"] for item in state["sources"] if item["state"] == "current"]
    fresh_snapshot = store.create_snapshot(case_id, followup_id, "Second human draft after amendment.", fresh_ids)
    store.acknowledge_demo_review(case_id, fresh_snapshot, "FICTIONAL-REVIEWER-B")
    return {"question_id": question_id, "snapshot_id": snapshot_id}


class SyntheticMetricsTests(unittest.TestCase):
    def test_metrics_computed_deterministically_two_runs_identical(self):
        store = CaseStore(":memory:")
        _build_rich_case(store, "CASE-FIG-01")
        _build_rich_case(store, "CASE-FIG-02")
        _build_rich_case(store, "CASE-FIG-09")
        first = fixture_run(store, ["CASE-FIG-01", "CASE-FIG-02"], ["CASE-FIG-09"])
        second = fixture_run(store, ["CASE-FIG-02", "CASE-FIG-01"], ["CASE-FIG-09"])
        self.assertEqual(json.dumps(first, sort_keys=True), json.dumps(second, sort_keys=True))
        self.assertEqual(first["run"]["run_id"], second["run"]["run_id"])

    def test_metrics_leave_ledger_unchanged(self):
        store = CaseStore(":memory:")
        built = _build_rich_case(store, "CASE-FIG-01")
        _save_replay(store, "CASE-FIG-01", built["question_id"],
                     {"claims": [], "abstentions": [{"topic": "scope", "reason": "out_of_scope"}]})
        before = _ledger_fingerprint(store)
        case_metrics(store, "CASE-FIG-01")
        fixture_run(store, ["CASE-FIG-01"], [])
        after = _ledger_fingerprint(store)
        self.assertEqual(before, after)

    def test_correction_count_matches_amendment_events(self):
        store = CaseStore(":memory:")
        _add_case_with_source(store, "CASE-FIG-01")
        store.import_report("CASE-FIG-01", _report("CASE-FIG-01", "DOC-FIG", amends="DOC-FIG@1"))
        imported = store.import_synthetic_evidence(_evidence("EVID-FIG"))
        question_id = store.add_question("CASE-FIG-01", "What does the fictional record show so far?")
        assessment_id = store.assess_synthetic_evidence(
            "CASE-FIG-01", question_id, imported["evidence_version_id"],
            "supports", "applicable", "Human rationale linking the fictional item to the question.")
        state = store.state("CASE-FIG-01")
        source_ids = [item["id"] for item in state["sources"] if item["state"] == "current"]
        store.create_snapshot("CASE-FIG-01", question_id, "Human draft bound to evidence.", source_ids,
                              evidence_assessment_ids=[assessment_id])
        store.import_synthetic_evidence(_evidence("EVID-FIG", amends="EVID-FIG@1"))
        result = case_metrics(store, "CASE-FIG-01")
        self.assertEqual(result["corrections"]["source_amendments"], 1)
        self.assertEqual(result["corrections"]["evidence_invalidations"], 1)
        self.assertEqual(result["corrections"]["total"], 2)
        self.assertEqual(len(result["corrections"]["correction_event_ids"]), 2)
        kinds = [row["kind"] for row in result["invalidated_vs_untouched"]]
        self.assertEqual(sorted(kinds), ["evidence_invalidated", "source_imported"])

    def test_stale_lag_distribution_matches_ledger_timestamps(self):
        store = CaseStore(":memory:")
        _build_rich_case(store, "CASE-FIG-01")
        result = case_metrics(store, "CASE-FIG-01")
        lag = result["stale_lag"]
        self.assertEqual(lag["invalidations"], 1)
        self.assertEqual(lag["pending"], 0)
        self.assertEqual(len(lag["samples"]), 1)
        sample = lag["samples"][0]
        expected = int((datetime.fromisoformat(
            _event_occurred(store, "CASE-FIG-01", sample["rereview_event_id"])) -
            datetime.fromisoformat(_event_occurred(store, "CASE-FIG-01", sample["invalidation_event_id"]))
        ).total_seconds())
        self.assertEqual(sample["lag_seconds"], expected)
        self.assertEqual(lag["summary"]["resolved"], 1)
        self.assertEqual(lag["summary"]["min_seconds"], expected)
        self.assertEqual(lag["summary"]["max_seconds"], expected)
        self.assertEqual(lag["summary"]["median_seconds"], expected)
        # An amendment with no later acknowledgment stays pending, never zero-lag.
        _add_case_with_source(store, "CASE-FIG-02")
        store.import_report("CASE-FIG-02", _report("CASE-FIG-02", "DOC-FIG", amends="DOC-FIG@1"))
        pending = case_metrics(store, "CASE-FIG-02")["stale_lag"]
        self.assertEqual(pending["pending"], 1)
        self.assertEqual(pending["samples"], [])
        self.assertEqual(len(pending["pending_invalidation_event_ids"]), 1)

    def test_abstention_counts_by_reason_match_investigations(self):
        store = CaseStore(":memory:")
        _add_case_with_source(store, "CASE-FIG-01")
        question_id = store.add_question("CASE-FIG-01", "What does the fictional record show so far?")
        _save_replay(store, "CASE-FIG-01", question_id, {"claims": [], "abstentions": [
            {"topic": "one", "reason": "no_evidence"},
            {"topic": "two", "reason": "no_evidence"},
            {"topic": "three", "reason": "conflicting_evidence"},
        ]})
        _save_replay(store, "CASE-FIG-01", question_id, {"claims": [], "abstentions": [
            {"topic": "four", "reason": "out_of_scope"},
        ]})
        result = case_metrics(store, "CASE-FIG-01")
        expected = {reason: 0 for reason in ABSTAIN_REASONS}
        expected.update({"no_evidence": 2, "conflicting_evidence": 1, "out_of_scope": 1})
        for reason, count in expected.items():
            self.assertEqual(result["abstentions_by_reason"][reason], count, reason)
        self.assertEqual(result["abstention_entries"], 4)
        self.assertEqual(result["unrecognized_abstention_entries"], 0)
        # Independent check straight from the investigations table.
        rows = store.db.execute("SELECT abstentions_json FROM investigations WHERE case_id=?",
                                ("CASE-FIG-01",)).fetchall()
        direct = sum(len(json.loads(row["abstentions_json"])) for row in rows)
        self.assertEqual(result["abstention_entries"], direct)

    def test_guard_drop_counts_by_reason_match_dropped_json(self):
        store = CaseStore(":memory:")
        source_id = _add_case_with_source(store, "CASE-FIG-01")
        question_id = store.add_question("CASE-FIG-01", "What does the fictional record show so far?")
        _save_replay(store, "CASE-FIG-01", question_id, {"claims": [
            {"text": "We recommend starting treatment now.", "support": "context",
             "citations": [{"type": "source", "id": source_id}], "uncertainty": "moderate"},
            {"text": "A claim citing nothing known.", "support": "context",
             "citations": [{"type": "source", "id": 9999}], "uncertainty": "moderate"},
            {"support": "context", "citations": [{"type": "source", "id": source_id}],
             "uncertainty": "moderate"},
        ], "abstentions": []})
        result = case_metrics(store, "CASE-FIG-01")
        self.assertEqual(result["guard_drops_by_reason"]["language_guard"], 1)
        self.assertEqual(result["guard_drops_by_reason"]["unresolved_citation"], 1)
        self.assertEqual(result["guard_drops_by_reason"]["missing_text"], 1)
        self.assertEqual(result["guard_drop_entries"], 3)
        rows = store.db.execute("SELECT dropped_json FROM investigations WHERE case_id=?",
                                ("CASE-FIG-01",)).fetchall()
        direct = sum(len(json.loads(row["dropped_json"])) for row in rows)
        self.assertEqual(result["guard_drop_entries"], direct)

    def test_invalidated_vs_untouched_counts_per_event(self):
        store = CaseStore(":memory:")
        _add_case_with_source(store, "CASE-FIG-01", document="DOC-ONE")
        store.import_report("CASE-FIG-01", _report("CASE-FIG-01", "DOC-TWO"))
        state = store.state("CASE-FIG-01")
        by_document = {}
        for item in state["sources"]:
            if item["state"] == "current":
                by_document[item["document_id"]] = item["id"]
        first_question = store.add_question("CASE-FIG-01", "What does the first fictional source show?")
        second_question = store.add_question("CASE-FIG-01", "What does the second fictional source show?")
        store.create_snapshot("CASE-FIG-01", first_question, "Draft bound to the first source only.",
                              [by_document["DOC-ONE"]])
        store.create_snapshot("CASE-FIG-01", second_question, "Draft bound to the second source only.",
                              [by_document["DOC-TWO"]])
        store.import_report("CASE-FIG-01", _report("CASE-FIG-01", "DOC-ONE", amends="DOC-ONE@1"))
        result = case_metrics(store, "CASE-FIG-01")
        self.assertEqual(len(result["invalidated_vs_untouched"]), 1)
        row = result["invalidated_vs_untouched"][0]
        self.assertEqual(row["kind"], "source_imported")
        self.assertEqual(row["invalidated"], 1)
        self.assertEqual(row["untouched"], 1)

    def test_held_out_fixtures_excluded_from_dev_aggregates(self):
        manifest_dev = list(MANIFEST["dev_cases"])
        manifest_held_out = list(MANIFEST["held_out_cases"])
        self.assertTrue(manifest_dev and manifest_held_out)
        self.assertEqual(set(manifest_dev) & set(manifest_held_out), set())
        store = CaseStore(":memory:")
        for case_id in manifest_dev:
            _add_case_with_source(store, case_id)
        for case_id in manifest_held_out:
            _add_case_with_source(store, case_id)
            store.import_report(case_id, _report(case_id, "DOC-FIG", amends="DOC-FIG@1"))
        run = fixture_run(store, manifest_dev, manifest_held_out)
        self.assertEqual(run["dev"]["aggregate"]["corrections"]["total"], 0)
        self.assertEqual(run["held_out"]["aggregate"]["corrections"]["total"], len(manifest_held_out))
        self.assertEqual(set(run["dev"]["cases"]), set(manifest_dev))
        self.assertEqual(set(run["held_out"]["cases"]), set(manifest_held_out))
        # No shared counts: the run block carries identity only, never totals.
        for forbidden in ("aggregate", "total", "corrections", "abstentions_by_reason",
                          "guard_drops_by_reason", "stale_lag", "samples"):
            self.assertNotIn(forbidden, run["run"])
        with self.assertRaises(InvalidInput):
            fixture_run(store, manifest_dev, manifest_dev)
        with self.assertRaises(InvalidInput):
            fixture_run(store, ["CASE-NOPE"], manifest_held_out)

    def test_scripted_amendment_moves_counts_by_exact_deltas(self):
        store = CaseStore(":memory:")
        _add_case_with_source(store, "CASE-FIG-01")
        question_id = store.add_question("CASE-FIG-01", "What does the fictional record show so far?")
        state = store.state("CASE-FIG-01")
        source_ids = [item["id"] for item in state["sources"] if item["state"] == "current"]
        snapshot_id = store.create_snapshot("CASE-FIG-01", question_id, "Human draft summary for deltas.", source_ids)
        store.acknowledge_demo_review("CASE-FIG-01", snapshot_id, "FICTIONAL-REVIEWER-B")
        baseline = case_metrics(store, "CASE-FIG-01")
        self.assertEqual(baseline["corrections"]["total"], 0)
        self.assertEqual(baseline["stale_lag"]["invalidations"], 0)
        store.import_report("CASE-FIG-01", _report("CASE-FIG-01", "DOC-FIG", amends="DOC-FIG@1"))
        amended = case_metrics(store, "CASE-FIG-01")
        self.assertEqual(amended["corrections"]["total"] - baseline["corrections"]["total"], 1)
        self.assertEqual(amended["stale_lag"]["invalidations"] - baseline["stale_lag"]["invalidations"], 1)
        self.assertEqual(amended["stale_lag"]["pending"], 1)
        self.assertEqual(len(amended["invalidated_vs_untouched"]), 1)
        self.assertEqual(amended["invalidated_vs_untouched"][0]["invalidated"], 1)
        self.assertEqual(amended["invalidated_vs_untouched"][0]["untouched"], 0)
        followup_id = store.add_question("CASE-FIG-01", "What fictional follow-up closes the loop?")
        state = store.state("CASE-FIG-01")
        fresh_ids = [item["id"] for item in state["sources"] if item["state"] == "current"]
        fresh_snapshot = store.create_snapshot("CASE-FIG-01", followup_id, "Rereview draft on the new version.", fresh_ids)
        store.acknowledge_demo_review("CASE-FIG-01", fresh_snapshot, "FICTIONAL-REVIEWER-B")
        rereviewed = case_metrics(store, "CASE-FIG-01")
        self.assertEqual(rereviewed["stale_lag"]["pending"], 0)
        self.assertEqual(len(rereviewed["stale_lag"]["samples"]), 1)
        self.assertEqual(rereviewed["stale_lag"]["summary"]["resolved"], 1)

    def test_metric_payload_has_no_source_text_or_identifiers(self):
        store = CaseStore(":memory:")
        store.add_case("CASE-FIG-01", "Fictional case ZEBRA")
        store.import_report("CASE-FIG-01", _report(
            "CASE-FIG-01", "DOC-ZEBRA",
            findings=(("zebra-marker", "reported", "Zebra quotation text for hygiene checks."),)))
        question_id = store.add_question("CASE-FIG-01", "Zebra question text for hygiene checks?")
        state = store.state("CASE-FIG-01")
        source_ids = [item["id"] for item in state["sources"] if item["state"] == "current"]
        snapshot_id = store.create_snapshot("CASE-FIG-01", question_id, "Zebra draft summary text.", source_ids)
        store.acknowledge_demo_review("CASE-FIG-01", snapshot_id, "Zebra Reviewer Label")
        store.add_case("CASE-FIG-09", "Fictional held-out ZEBRA")
        store.import_report("CASE-FIG-09", _report(
            "CASE-FIG-09", "DOC-ZEBRA",
            findings=(("zebra-marker", "reported", "Zebra quotation text for hygiene checks."),)))
        run = fixture_run(store, ["CASE-FIG-01"], ["CASE-FIG-09"])
        body = json.dumps(run, sort_keys=True)
        self.assertNotIn("zebra", body.lower())
        for distinctive in ("DOC-ZEBRA", "zebra-marker", "Zebra quotation text",
                            "Zebra question text", "Zebra draft summary", "Zebra Reviewer Label"):
            self.assertNotIn(distinctive, body)

        def _keys(value, found):
            if isinstance(value, dict):
                for key, item in value.items():
                    found.add(key)
                    _keys(item, found)
            elif isinstance(value, list):
                for item in value:
                    _keys(item, found)

        keys = set()
        _keys(run, keys)
        for forbidden in ("quote", "finding_key", "finding_keys", "document_id", "evidence_key",
                          "question", "reviewer_label", "owner_label", "statement", "excerpt",
                          "title", "raw", "sha256", "text", "topic"):
            self.assertNotIn(forbidden, keys)
        self.assertIn("CASE-FIG-01", body)
        self.assertIn("CASE-FIG-09", body)

    def test_dashboard_labels_synthetic_only_and_non_transferable(self):
        store = CaseStore(":memory:")
        _build_rich_case(store, "CASE-FIG-01")
        _build_rich_case(store, "CASE-FIG-09")
        run = fixture_run(store, ["CASE-FIG-01"], ["CASE-FIG-09"])
        for block in (run["run"], run["dev"], run["held_out"],
                      run["dev"]["cases"]["CASE-FIG-01"], run["held_out"]["cases"]["CASE-FIG-09"]):
            self.assertTrue(block["synthetic_only"])
            self.assertTrue(block["non_transferable"])
            self.assertIn(SYNTHETIC_ONLY_LABEL, block["labels"])
            self.assertIn(NON_TRANSFERABLE_LABEL, block["labels"])
            self.assertIn("synthetic", block["disclaimer"].lower())
            self.assertIn("non-transferable", block["disclaimer"].lower())
        body = json.dumps(run, sort_keys=True).lower()
        # The disclaimer negates clinical meaning ("states no clinical
        # accuracy ... or recommendation"); nothing here may affirm it.
        for forbidden in ("prescrib", "treatment benefit", "clinically validated",
                          "diagnos", "dosage", "treatment recommendation"):
            self.assertNotIn(forbidden, body)

    def test_metrics_trigger_no_model_call_and_no_proposal_write(self):
        store = CaseStore(":memory:")
        built = _build_rich_case(store, "CASE-FIG-01")
        _save_replay(store, "CASE-FIG-01", built["question_id"],
                     {"claims": [], "abstentions": [{"topic": "scope", "reason": "no_evidence"}]})
        before = _ledger_fingerprint(store)
        event_count = store.db.execute("SELECT COUNT(*) AS n FROM events").fetchone()["n"]
        investigation_count = store.db.execute("SELECT COUNT(*) AS n FROM investigations").fetchone()["n"]
        with patch("open_intelligence.investigation.call_meta_api",
                   side_effect=AssertionError("metrics must not call the model")):
            with patch("urllib.request.urlopen",
                       side_effect=AssertionError("metrics must not touch the network")):
                run = fixture_run(store, ["CASE-FIG-01"], [])
        self.assertEqual(run["dev"]["aggregate"]["case_count"], 1)
        self.assertEqual(_ledger_fingerprint(store), before)
        self.assertEqual(store.db.execute("SELECT COUNT(*) AS n FROM events").fetchone()["n"], event_count)
        self.assertEqual(store.db.execute("SELECT COUNT(*) AS n FROM investigations").fetchone()["n"],
                         investigation_count)


class SyntheticMetricsHttpTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        cls.path = str(Path(cls.tmp.name) / "server.sqlite")
        seed(cls.path)
        bound = type("BoundHandlerForMetrics", (Handler,), {"db_path": cls.path})
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
        values = {"Content-Type": "application/json"} if data is not None else {}
        request = Request(f"http://127.0.0.1:{self.port}{path}",
                          data=None if data is None else json.dumps(data).encode(),
                          headers=values)
        try:
            with urlopen(request, timeout=10) as response:
                raw = response.read()
                try:
                    return response.status, json.loads(raw)
                except ValueError:
                    return response.status, raw.decode()
        except HTTPError as err:
            return err.code, json.loads(err.read())

    def test_metrics_route_reports_sets_separately_with_labels(self):
        status, data = self.request("/api/metrics/synthetic?dev=CASE-ALPHA&held_out=CASE-BETA")
        self.assertEqual(status, 200)
        self.assertTrue(data["run"]["synthetic_only"])
        self.assertTrue(data["run"]["non_transferable"])
        self.assertIn(SYNTHETIC_ONLY_LABEL, data["run"]["labels"])
        self.assertIn(NON_TRANSFERABLE_LABEL, data["run"]["labels"])
        self.assertEqual(data["run"]["manifest"]["dev_cases"], ["CASE-ALPHA"])
        self.assertEqual(data["run"]["manifest"]["held_out_cases"], ["CASE-BETA"])
        self.assertEqual(set(data["dev"]["cases"]), {"CASE-ALPHA"})
        self.assertEqual(set(data["held_out"]["cases"]), {"CASE-BETA"})
        self.assertTrue(data["run"]["run_id"].startswith("METRICS-"))
        self.assertIsNotNone(data["run"]["as_of_ledger_time"])

    def test_metrics_route_rejects_overlap_and_unknown_cases(self):
        status, _ = self.request("/api/metrics/synthetic?dev=CASE-ALPHA&held_out=CASE-ALPHA")
        self.assertEqual(status, 422)
        status, _ = self.request("/api/metrics/synthetic?dev=CASE-NOPE&held_out=")
        self.assertEqual(status, 422)
        status, _ = self.request("/api/metrics/synthetic")
        self.assertEqual(status, 422)

    def test_metrics_panel_markup_carries_labels_and_manifest_form(self):
        status, html = self.request("/")
        self.assertEqual(status, 200)
        for element_id in ("synthetic-metrics", "metrics-form", "metrics-dev-input",
                           "metrics-heldout-input", "metrics-status", "metrics-dev",
                           "metrics-heldout", "metrics-run", "metrics-disclaimer"):
            self.assertIn(f'id="{element_id}"', html)
        self.assertIn("SYNTHETIC FIXTURES ONLY", html)
        self.assertIn("NON-TRANSFERABLE", html)
        self.assertIn("no shared counts", html)


if __name__ == "__main__":
    unittest.main()
