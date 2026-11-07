"""Slice D5 — hypothesis generation dimension: A4 Literature, A5 Trials,
T5 report assembly, HYPOTHESIS composition per REQ-09-10.

Fixtures are written from the plan (§D5) and Notion REQ-09-10, not
from the implementation: a composition that invents a number, an
identifier, or a substance, that cites nothing, that exceeds 280
characters, or that states eligibility must be rejected; a trial
listing must never be presentable as eligibility.

W2 persistence: composed hypotheses are stored (store table + write-contract treatment) and go stale via the import cascade.
"""

import ast
import json
import tempfile
import threading
import unittest
from http.server import ThreadingHTTPServer
from pathlib import Path
from urllib.error import HTTPError
from urllib.request import Request, urlopen

from open_intelligence.__main__ import Handler, seed
from open_intelligence.agent_writes import (
    CONTRACT_FIELDS,
    WriteContractRejected,
    build_investigation_contract,
    build_route_id,
    build_write_contract,
)
from session_auth import signin_demo
from open_intelligence.hypothesis import (
    DATA_LABEL,
    HYPOTHESIS_LABEL,
    LITERATURE_LABEL,
    MAX_HYPOTHESIS_CHARS,
    TRIALS_LABEL,
    assemble_hypothesis_report,
    claim_id,
    compose_hypothesis,
)
from open_intelligence.kchecks import TIER_LIMITS_PHRASE
from open_intelligence.literature import (
    PINNED_RECORDS,
    get_record,
    list_records,
    validate_literature_record,
)
from open_intelligence.trials import (
    LISTING_LABEL,
    PINNED_LISTINGS,
    check_eligibility_claim,
    get_listing,
    list_listings,
    render_listing,
    validate_trial_listing,
)
from open_intelligence.investigation import validate_output
from open_intelligence.orchestrator import decide_route
from open_intelligence.store import CaseStore, InvalidInput, now_utc


def _kept_claims():
    return [
        {"id": "inv1:c1", "text": "The lesion was measured as 31 mm.",
         "uncertainty": "low",
         "citations": [{"type": "source", "id": 2}]},
        {"id": "inv1:c2", "text": "Marker A was not tested.",
         "uncertainty": "moderate",
         "citations": [{"type": "source", "id": 1}]},
        {"id": "inv2:c1", "text": "See NCT12345678 for the registry entry.",
         "uncertainty": "low",
         "citations": [{"type": "source", "id": 1}]},
        {"id": "inv2:c2", "text": "The note mentions fictional-substance-x.",
         "uncertainty": "moderate",
         "citations": [{"type": "source", "id": 1}]},
    ]


def _reasons(result):
    return [item["reason"] for item in result["violations"]]


class LiteratureTest(unittest.TestCase):
    def test_pinned_records_validate_clean(self):
        for record in PINNED_RECORDS:
            self.assertEqual(validate_literature_record(record), [], record["record_id"])

    def test_pinned_records_are_metadata_only(self):
        for record in PINNED_RECORDS:
            self.assertTrue(record["synthetic"])
            self.assertTrue(record["doi"].startswith("10.0000/oi-synth-lit-"))
            for key in ("findings", "efficacy", "conclusion", "results", "abstract"):
                self.assertNotIn(key, record)

    def test_missing_field_rejected(self):
        record = dict(PINNED_RECORDS[0])
        del record["title"]
        reasons = [item["reason"] for item in validate_literature_record(record)]
        self.assertIn("missing_field", reasons)

    def test_not_synthetic_rejected(self):
        record = dict(PINNED_RECORDS[0], synthetic=False)
        reasons = [item["reason"] for item in validate_literature_record(record)]
        self.assertIn("not_synthetic", reasons)

    def test_unknown_source_rejected(self):
        record = dict(PINNED_RECORDS[0], source="pubmed-central")
        reasons = [item["reason"] for item in validate_literature_record(record)]
        self.assertIn("unknown_source", reasons)

    def test_malformed_doi_rejected(self):
        record = dict(PINNED_RECORDS[0], doi="doi:10.1234/not-a-doi")
        reasons = [item["reason"] for item in validate_literature_record(record)]
        self.assertIn("malformed_doi", reasons)

    def test_bad_year_rejected(self):
        record = dict(PINNED_RECORDS[0], year="2025")
        reasons = [item["reason"] for item in validate_literature_record(record)]
        self.assertIn("bad_year", reasons)

    def test_record_carrying_findings_rejected(self):
        record = dict(PINNED_RECORDS[0], findings="The treatment worked.")
        reasons = [item["reason"] for item in validate_literature_record(record)]
        self.assertIn("carries_findings", reasons)

    def test_topic_filter_matches_title_and_topics(self):
        found = list_records("cardiology")
        self.assertEqual([item["record_id"] for item in found], ["LIT-0003"])
        found = list_records("SPECIMEN")
        self.assertEqual([item["record_id"] for item in found], ["LIT-0002"])
        self.assertEqual(len(list_records()), len(PINNED_RECORDS))
        self.assertEqual(list_records("no-such-topic"), [])

    def test_list_returns_copies(self):
        first = list_records()[0]
        first["title"] = "mutated"
        self.assertNotEqual(list_records()[0]["title"], "mutated")

    def test_get_record(self):
        self.assertEqual(get_record("LIT-0004")["doi"], "10.0000/oi-synth-lit-0004")
        self.assertIsNone(get_record("LIT-9999"))


class TrialsTest(unittest.TestCase):
    def test_pinned_listings_validate_clean(self):
        for listing in PINNED_LISTINGS:
            self.assertEqual(validate_trial_listing(listing), [], listing["listing_id"])

    def test_pinned_listings_are_synthetic_nct9(self):
        for listing in PINNED_LISTINGS:
            self.assertTrue(listing["synthetic"])
            self.assertTrue(listing["registry_id"].startswith("NCT9"))

    def test_missing_field_rejected(self):
        listing = dict(PINNED_LISTINGS[0])
        del listing["phase"]
        reasons = [item["reason"] for item in validate_trial_listing(listing)]
        self.assertIn("missing_field", reasons)

    def test_not_synthetic_rejected(self):
        listing = dict(PINNED_LISTINGS[0], synthetic=False)
        reasons = [item["reason"] for item in validate_trial_listing(listing)]
        self.assertIn("not_synthetic", reasons)

    def test_malformed_registry_id_rejected(self):
        listing = dict(PINNED_LISTINGS[0], registry_id="NCT123")
        reasons = [item["reason"] for item in validate_trial_listing(listing)]
        self.assertIn("malformed_registry_id", reasons)

    def test_listing_stating_eligibility_rejected(self):
        listing = dict(PINNED_LISTINGS[0],
                       title="Synthetic study — patients are eligible to join")
        problems = validate_trial_listing(listing)
        self.assertIn("states_eligibility", [item["reason"] for item in problems])
        self.assertEqual(
            next(item for item in problems if item["reason"] == "states_eligibility")["predicate"],
            "eligible")

    def test_eligibility_claim_detection(self):
        self.assertEqual(check_eligibility_claim("You are eligible for this trial."), "eligible")
        self.assertEqual(check_eligibility_claim("She qualifies for enrollment."), "qualifies_for")
        self.assertEqual(check_eligibility_claim("You can enroll today."), "can_enroll")
        self.assertEqual(check_eligibility_claim("The patient meets the criteria."), "meets_criteria")
        self.assertEqual(check_eligibility_claim("Inclusion criteria met."), "criteria_met")
        self.assertEqual(check_eligibility_claim("Enroll in this trial now."), "enroll_in_this")
        # Registry status language is listing metadata, not an eligibility claim.
        self.assertIsNone(check_eligibility_claim("Status: recruiting. Enrollment is open."))
        self.assertIsNone(check_eligibility_claim("Phase 2 study of longitudinal review."))

    def test_render_listing_always_carries_label(self):
        rendered = render_listing(PINNED_LISTINGS[0])
        self.assertEqual(rendered["label"], LISTING_LABEL)
        self.assertEqual(rendered["listing"]["registry_id"], "NCT90000001")

    def test_render_invalid_listing_raises(self):
        listing = dict(PINNED_LISTINGS[0], registry_id="NCT123")
        with self.assertRaises(ValueError):
            render_listing(listing)

    def test_condition_filter(self):
        found = list_listings("cardiology")
        self.assertEqual([item["listing_id"] for item in found], ["TRL-0002"])
        self.assertEqual(len(list_listings()), len(PINNED_LISTINGS))

    def test_get_listing(self):
        self.assertEqual(get_listing("TRL-0003")["registry_id"], "NCT90000003")
        self.assertIsNone(get_listing("TRL-9999"))


class ClaimIdTest(unittest.TestCase):
    def test_claim_id_shape(self):
        self.assertEqual(claim_id(12, 3), "inv12:c3")


class ComposeHypothesisTest(unittest.TestCase):
    def test_valid_composition(self):
        result = compose_hypothesis(
            [{"text": "The lesion was measured as 31 mm.",
              "claim_ids": ["inv1:c1"]}],
            _kept_claims())
        self.assertEqual(result["status"], "composed")
        self.assertEqual(result["text"], "The lesion was measured as 31 mm.")
        self.assertEqual(result["claim_ids"], ["inv1:c1"])
        self.assertEqual(result["violations"], [])
        self.assertLessEqual(result["char_count"], MAX_HYPOTHESIS_CHARS)

    def test_number_must_match_cited_claims(self):
        # 31.0 is the same number as 31 by value.
        result = compose_hypothesis(
            [{"text": "The lesion was measured as 31.0 mm.",
              "claim_ids": ["inv1:c1"]}],
            _kept_claims())
        self.assertEqual(result["status"], "composed")

    def test_sentence_without_citation_rejected(self):
        result = compose_hypothesis(
            [{"text": "The lesion was measured as 31 mm.", "claim_ids": []}],
            _kept_claims())
        self.assertEqual(result["status"], "rejected")
        self.assertIn("missing_citation", _reasons(result))
        self.assertIsNone(result["text"])

    def test_unknown_claim_id_rejected(self):
        result = compose_hypothesis(
            [{"text": "The lesion was measured as 31 mm.",
              "claim_ids": ["inv9:c9"]}],
            _kept_claims())
        self.assertEqual(result["status"], "rejected")
        self.assertIn("unknown_claim", _reasons(result))

    def test_invented_number_rejected(self):
        result = compose_hypothesis(
            [{"text": "The lesion was measured as 45 mm.",
              "claim_ids": ["inv1:c1"]}],
            _kept_claims())
        self.assertEqual(result["status"], "rejected")
        self.assertIn("unsupported_number", _reasons(result))

    def test_invented_registry_id_rejected(self):
        result = compose_hypothesis(
            [{"text": "See NCT87654321 for the registry entry.",
              "claim_ids": ["inv2:c1"]}],
            _kept_claims())
        self.assertEqual(result["status"], "rejected")
        self.assertIn("unsupported_identifier", _reasons(result))

    def test_supported_registry_id_passes(self):
        result = compose_hypothesis(
            [{"text": "See NCT12345678 for the registry entry.",
              "claim_ids": ["inv2:c1"]}],
            _kept_claims())
        self.assertEqual(result["status"], "composed")

    def test_malformed_identifier_rejected(self):
        result = compose_hypothesis(
            [{"text": "See NCT123 for the registry entry.",
              "claim_ids": ["inv2:c1"]}],
            _kept_claims())
        self.assertEqual(result["status"], "rejected")
        self.assertIn("malformed_identifier", _reasons(result))

    def test_invented_substance_rejected(self):
        result = compose_hypothesis(
            [{"text": "The note mentions fictional-substance-y.",
              "claim_ids": ["inv2:c2"]}],
            _kept_claims(),
            substance_names=["fictional-substance-x", "fictional-substance-y"])
        self.assertEqual(result["status"], "rejected")
        self.assertIn("unsupported_substance", _reasons(result))

    def test_supported_substance_passes_and_arm_reports(self):
        result = compose_hypothesis(
            [{"text": "The note mentions fictional-substance-x.",
              "claim_ids": ["inv2:c2"]}],
            _kept_claims(),
            substance_names=["fictional-substance-x"])
        self.assertEqual(result["status"], "composed")
        self.assertEqual(result["substance_check"], "checked")

    def test_substance_arm_skipped_without_vocabulary(self):
        result = compose_hypothesis(
            [{"text": "The note mentions fictional-substance-x.",
              "claim_ids": ["inv2:c2"]}],
            _kept_claims())
        self.assertEqual(result["status"], "composed")
        self.assertEqual(result["substance_check"], "skipped")

    def test_over_length_rejected(self):
        long_text = "The lesion was measured as 31 mm. " * 10
        result = compose_hypothesis(
            [{"text": long_text.strip(), "claim_ids": ["inv1:c1"]}],
            _kept_claims())
        self.assertEqual(result["status"], "rejected")
        self.assertIn("over_length", _reasons(result))

    def test_exactly_280_chars_passes(self):
        base = "The lesion was measured as 31 mm."
        padding = "x" * (MAX_HYPOTHESIS_CHARS - len(base) - 1)
        text = base + " " + padding
        self.assertEqual(len(text), MAX_HYPOTHESIS_CHARS)
        result = compose_hypothesis(
            [{"text": text, "claim_ids": ["inv1:c1"]}], _kept_claims())
        self.assertEqual(result["status"], "composed")

    def test_empty_hypothesis_rejected(self):
        result = compose_hypothesis([], _kept_claims())
        self.assertEqual(result["status"], "rejected")
        self.assertIn("empty_hypothesis", _reasons(result))

    def test_scope_language_rejected(self):
        for text in (
            "We recommend starting treatment now.",
            "The best treatment is the new drug.",
            "You should take the new drug.",
            "The patient is eligible for this trial.",
            "She qualifies for enrollment.",
        ):
            result = compose_hypothesis(
                [{"text": text, "claim_ids": ["inv1:c1"]}], _kept_claims())
            self.assertEqual(result["status"], "rejected", text)
            self.assertIn("scope_language", _reasons(result), text)

    def test_low_tier_without_limits_phrase_rejected(self):
        result = compose_hypothesis(
            [{"text": "Marker A was not tested.", "claim_ids": ["inv1:c2"]}],
            _kept_claims(),
            tiers={"inv1:c2": "D"})
        self.assertEqual(result["status"], "rejected")
        self.assertIn("missing_limits_phrase", _reasons(result))
        self.assertEqual(result["tier_check"], "checked")

    def test_low_tier_with_limits_phrase_passes(self):
        text = "Marker A was not tested. " + TIER_LIMITS_PHRASE
        self.assertLessEqual(len(text), MAX_HYPOTHESIS_CHARS)
        result = compose_hypothesis(
            [{"text": text, "claim_ids": ["inv1:c2"]}],
            _kept_claims(),
            tiers={"inv1:c2": "D"})
        self.assertEqual(result["status"], "composed")

    def test_tier_arm_skipped_without_tiers(self):
        result = compose_hypothesis(
            [{"text": "Marker A was not tested.", "claim_ids": ["inv1:c2"]}],
            _kept_claims())
        self.assertEqual(result["status"], "composed")
        self.assertEqual(result["tier_check"], "skipped")

    def test_tier_arm_skipped_when_a_cited_claim_is_not_low_tier(self):
        result = compose_hypothesis(
            [{"text": "The lesion was measured as 31 mm.",
              "claim_ids": ["inv1:c1"]}],
            _kept_claims(),
            tiers={"inv1:c1": "A"})
        self.assertEqual(result["status"], "composed")
        self.assertEqual(result["tier_check"], "skipped")

    def test_multi_sentence_composition_cites_each_sentence(self):
        result = compose_hypothesis(
            [{"text": "The lesion was measured as 31 mm.", "claim_ids": ["inv1:c1"]},
             {"text": "Marker A was not tested.", "claim_ids": ["inv1:c2"]}],
            _kept_claims())
        self.assertEqual(result["status"], "composed")
        self.assertEqual(result["claim_ids"], ["inv1:c1", "inv1:c2"])

    def test_hypothesis_and_trials_agree_on_eligibility_probes(self):
        # The eligibility predicates are mirrored in trials.py and
        # hypothesis.py; a probe the trials check flags must also fail
        # composition, and one it clears must not fail on scope.
        probes = [
            "You are eligible for this trial.",
            "She qualifies for enrollment.",
            "You can enroll today.",
            "The patient meets the criteria.",
            "Inclusion criteria met.",
            "Enroll in this trial now.",
        ]
        for text in probes:
            self.assertIsNotNone(check_eligibility_claim(text), text)
            result = compose_hypothesis(
                [{"text": text, "claim_ids": ["inv1:c1"]}], _kept_claims())
            self.assertIn("scope_language", _reasons(result), text)
        self.assertIsNone(check_eligibility_claim("Status: recruiting."))
        result = compose_hypothesis(
            [{"text": "Status: recruiting.", "claim_ids": ["inv1:c1"]}],
            _kept_claims())
        self.assertNotIn("scope_language", _reasons(result))


class ReportAssemblyTest(unittest.TestCase):
    def test_deterministic_and_ordered(self):
        first = assemble_hypothesis_report(
            "CASE-ALPHA", _kept_claims(), list_records(), list_listings())
        second = assemble_hypothesis_report(
            "CASE-ALPHA", list(reversed(_kept_claims())), list_records(), list_listings())
        self.assertEqual(first, second)
        self.assertEqual([item["id"] for item in first["kept_claims"]],
                         ["inv1:c1", "inv1:c2", "inv2:c1", "inv2:c2"])
        self.assertEqual(list(first.keys()),
                         ["case_id", "generated_as_of", "labels", "kept_claims",
                          "hypothesis", "literature", "trials", "abstentions", "counts"])

    def test_labels_present(self):
        report = assemble_hypothesis_report("CASE-ALPHA", [], [], [])
        self.assertEqual(report["labels"]["hypothesis"], HYPOTHESIS_LABEL)
        self.assertEqual(report["labels"]["trials"], TRIALS_LABEL)
        self.assertEqual(report["labels"]["literature"], LITERATURE_LABEL)
        self.assertEqual(report["labels"]["data"], DATA_LABEL)

    def test_not_composed_without_a_hypothesis(self):
        report = assemble_hypothesis_report("CASE-ALPHA", _kept_claims(), [], [])
        self.assertEqual(report["hypothesis"]["status"], "not_composed")
        self.assertIsNone(report["hypothesis"]["text"])
        self.assertIn("No composed hypothesis", report["hypothesis"]["reason"])

    def test_composed_hypothesis_carried(self):
        composed = compose_hypothesis(
            [{"text": "The lesion was measured as 31 mm.", "claim_ids": ["inv1:c1"]}],
            _kept_claims())
        report = assemble_hypothesis_report(
            "CASE-ALPHA", _kept_claims(), [], [], hypothesis=composed)
        self.assertEqual(report["hypothesis"]["status"], "composed")
        self.assertEqual(report["hypothesis"]["text"], "The lesion was measured as 31 mm.")

    def test_listings_carry_the_fixed_label(self):
        report = assemble_hypothesis_report("CASE-ALPHA", [], [], list_listings())
        for item in report["trials"]["listings"]:
            self.assertEqual(item["label"], LISTING_LABEL)
        rendered = assemble_hypothesis_report(
            "CASE-ALPHA", [], [], [render_listing(item) for item in list_listings()])
        for item in rendered["trials"]["listings"]:
            self.assertEqual(item["label"], LISTING_LABEL)

    def test_empty_inputs_produce_empty_sections(self):
        report = assemble_hypothesis_report("CASE-ALPHA", [], [], [])
        self.assertEqual(report["counts"], {
            "kept_claims": 0, "literature_records": 0,
            "trial_listings": 0, "abstentions": 0})
        self.assertEqual(report["kept_claims"], [])
        self.assertEqual(report["literature"]["records"], [])

    def test_abstentions_carried(self):
        report = assemble_hypothesis_report(
            "CASE-ALPHA", [], [], [],
            abstentions=[{"topic": "dose", "reason": "out_of_scope"}])
        self.assertEqual(report["abstentions"],
                         [{"topic": "dose", "reason": "out_of_scope"}])

    def test_as_of_recorded(self):
        report = assemble_hypothesis_report("CASE-ALPHA", [], [], [], as_of="2026-11-06")
        self.assertEqual(report["generated_as_of"], "2026-11-06")


class HypothesisReportHttpTests(unittest.TestCase):
    """The read-only hypothesis-report route, served live like test_http.py."""

    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        cls.path = str(Path(cls.tmp.name) / "server.sqlite")
        seed(cls.path)
        bound = type("BoundHandlerForTest", (Handler,), {"db_path": cls.path})
        cls.server = ThreadingHTTPServer(("127.0.0.1", 0), bound)
        cls.port = cls.server.server_address[1]
        cls.thread = threading.Thread(target=cls.server.serve_forever,
                                      daemon=True)
        cls.thread.start()
        cls._cookie = signin_demo(cls.port, cls.path)

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.server.server_close()
        cls.thread.join(timeout=5)
        cls.tmp.cleanup()

    def request(self, path, headers=None):
        values = {"Cookie": self._cookie}
        values.update(headers or {})
        req = Request(f"http://127.0.0.1:{self.port}{path}", headers=values)
        try:
            with urlopen(req, timeout=5) as resp:
                return resp.status, json.loads(resp.read())
        except HTTPError as err:
            return err.code, json.loads(err.read())

    def test_hypothesis_report_route_returns_sections(self):
        status, data = self.request("/api/cases/CASE-ALPHA/hypothesis-report")
        self.assertEqual(status, 200)
        self.assertEqual(data["case_id"], "CASE-ALPHA")
        self.assertIn("kept_claims", data)
        self.assertIn("hypothesis", data)
        self.assertIn("literature", data)
        self.assertIn("trials", data)
        # Seeded CASE-ALPHA has no stored investigations, so no kept
        # claims and no composed hypothesis — reported, never invented.
        self.assertEqual(data["kept_claims"], [])
        self.assertEqual(data["hypothesis"]["status"], "not_composed")
        self.assertEqual(len(data["literature"]["records"]), len(PINNED_RECORDS))
        self.assertEqual(len(data["trials"]["listings"]), len(PINNED_LISTINGS))
        for item in data["trials"]["listings"]:
            self.assertEqual(item["label"], LISTING_LABEL)
        self.assertEqual(data["labels"]["hypothesis"], HYPOTHESIS_LABEL)

    def test_hypothesis_report_route_requires_a_grant(self):
        # W1: the header is ignored — a header-only request is denied.
        req = Request(
            f"http://127.0.0.1:{self.port}/api/cases/CASE-ALPHA/hypothesis-report",
            headers={"X-Fictional-Actor": "FICTIONAL-NOBODY"})
        try:
            with urlopen(req, timeout=5) as resp:
                status = resp.status
        except HTTPError as err:
            status = err.code
        self.assertEqual(status, 403)


class NoModelCallTests(unittest.TestCase):
    def test_modules_have_no_model_call_and_no_dimension_import(self):
        # D5 is deterministic code over the ledger and pinned fixtures:
        # it never calls a model and never imports another dimension
        # module — not even the other D5 modules. The K-checks import
        # in hypothesis.py is core verification, not a dimension module.
        src = Path(__file__).resolve().parents[1] / "src" / "open_intelligence"
        dimension_modules = {
            "extraction", "specimen_chain", "terminology", "fhir_exchange",
            "dicom", "longitudinal", "lab_series", "imaging", "molecular",
            "therapy", "patient_analytics",
            "literature", "trials", "hypothesis",
        }
        for module in ("literature", "trials", "hypothesis"):
            tree = ast.parse((src / f"{module}.py").read_text())
            imports = set()
            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    imports.update(a.name for a in node.names)
                elif isinstance(node, ast.ImportFrom):
                    if node.module:
                        imports.add(node.module)
            self.assertFalse({"investigation", "skeptic", "__main__"} & imports, module)
            imported = {name.split(".")[-1] for name in imports}
            self.assertFalse(dimension_modules & imported, module)


def seed_case(store, case_id="CASE-ALPHA"):
    """A fictional case with one imported source and one question."""
    store.add_case(case_id, f"Fictional case {case_id}")
    synthetic = Path(__file__).resolve().parents[1] / "examples" / "synthetic"
    source_id = store.import_report(
        case_id, (synthetic / "alpha-pathology-original.txt").read_bytes()
    )["source_id"]
    question_id = store.add_question(case_id, "What does the source report?")
    return source_id, question_id


def save_run(store, case_id, question_id, source_id, *, model="recorded-replay",
             route=True):
    """Save one completed replay investigation with its contract."""
    if route:
        decide_route(store, case_id, "evidence-summary", question_id, "clinician")
    facts = store.investigation_facts(case_id, question_id)
    validated = validate_output(
        {"claims": [{"text": "The sources report a finding.",
                     "support": "context",
                     "citations": [{"type": "source", "id": source_id}],
                     "uncertainty": "moderate", "limits": "Synthetic only."}],
         "abstentions": []},
        facts["valid_sources"], facts["valid_assessments"])
    validated.model = model
    validated.mode = "replay"
    contract = build_investigation_contract(
        store, case_id, question_id, "evidence-summary", model, facts=facts)
    run_id = store.save_investigation(
        case_id, question_id, "evidence-summary", validated, "replay",
        write_contract=contract)
    return run_id, contract


class ComposedHypothesisPersistenceTests(unittest.TestCase):
    """W2: stored composed hypotheses — write contract and staleness."""

    TEXT = "The sources report a finding."

    def setUp(self):
        self.store = CaseStore(":memory:")
        self.source_id, self.question_id = seed_case(self.store)

    def tearDown(self):
        self.store.close()

    def contract(self, case_id="CASE-ALPHA"):
        return build_write_contract(
            agent_role="A4", model_id="recorded-replay",
            route_id=build_route_id(case_id, "evidence-summary",
                                    self.question_id),
            snapshot_at={"as_of": now_utc(), "event_id": None},
            inputs=[], prompt_version="hypothesis:1")

    def run_once(self):
        inv_id, _ = save_run(self.store, "CASE-ALPHA", self.question_id,
                             self.source_id)
        return inv_id

    def compose(self, inv_id, text=None):
        kept = [{"id": claim_id(inv_id, 1), "text": self.TEXT,
                 "uncertainty": "moderate",
                 "citations": [{"type": "source", "id": self.source_id}]}]
        return compose_hypothesis(
            [{"text": text or self.TEXT, "claim_ids": [claim_id(inv_id, 1)]}],
            kept)

    def amend(self):
        amended = (Path(__file__).resolve().parents[1] / "examples"
                   / "synthetic" / "alpha-pathology-amended.txt")
        self.store.import_report("CASE-ALPHA", amended.read_bytes())

    def store_hypothesis(self, composed, contract=None):
        return self.store.save_composed_hypothesis(
            "CASE-ALPHA", composed,
            write_contract=self.contract() if contract is None else contract)

    def test_round_trip_stores_text_claim_ids_and_contract(self):
        inv_id = self.run_once()
        composed = self.compose(inv_id)
        self.assertEqual(composed["status"], "composed")
        row_id = self.store_hypothesis(composed)
        stored = self.store.get_composed_hypothesis("CASE-ALPHA")
        self.assertEqual(stored["id"], row_id)
        self.assertEqual(stored["status"], "composed")
        self.assertEqual(stored["text"], self.TEXT)
        self.assertEqual(stored["claim_ids"], [claim_id(inv_id, 1)])
        self.assertTrue(stored["write_id"])
        self.assertIsInstance(stored["write_contract"], dict)
        self.assertEqual(stored["write_contract"]["agentRole"], "A4")
        self.assertEqual(stored["review_state"], "pending")
        self.assertIs(stored["stale"], False)
        self.assertEqual(len(self.store.list_composed_hypotheses("CASE-ALPHA")), 1)

    def test_missing_contract_rejected(self):
        composed = self.compose(self.run_once())
        with self.assertRaises(WriteContractRejected) as ctx:
            self.store.save_composed_hypothesis(
                "CASE-ALPHA", composed, write_contract=None)
        self.assertEqual(ctx.exception.reason, "missing_write_contract")

    def test_incomplete_contract_rejected(self):
        composed = self.compose(self.run_once())
        contract = self.contract()
        field = next(name for name in CONTRACT_FIELDS if name in contract)
        del contract[field]
        with self.assertRaises(WriteContractRejected) as ctx:
            self.store_hypothesis(composed, contract)
        self.assertEqual(ctx.exception.reason, "missing_field")
        self.assertEqual(ctx.exception.field, field)

    def test_rejected_composition_not_stored(self):
        composed = self.compose(self.run_once(),
                                text="The sources report 42 findings.")
        self.assertEqual(composed["status"], "rejected")
        with self.assertRaises(InvalidInput):
            self.store_hypothesis(composed)
        self.assertEqual(self.store.list_composed_hypotheses("CASE-ALPHA"), [])

    def test_wrong_role_rejected(self):
        composed = self.compose(self.run_once())
        contract = dict(self.contract(), agentRole="A1")
        with self.assertRaises(WriteContractRejected) as ctx:
            self.store_hypothesis(composed, contract)
        self.assertEqual(ctx.exception.reason, "invalid_role")

    def test_unknown_claim_id_rejected(self):
        self.run_once()
        composed = {
            "status": "composed", "text": self.TEXT,
            "claim_ids": ["inv99:c1"],
            "sentences": [{"text": self.TEXT, "claim_ids": ["inv99:c1"]}],
            "char_count": 29, "violations": [],
        }
        with self.assertRaises(InvalidInput):
            self.store_hypothesis(composed)

    def test_claim_from_stale_investigation_rejected(self):
        inv_id = self.run_once()
        self.amend()
        self.assertEqual(self.store.get_investigation("CASE-ALPHA", inv_id)["stale"], 1)
        composed = self.compose(inv_id)
        self.assertEqual(composed["status"], "composed")
        with self.assertRaises(InvalidInput):
            self.store_hypothesis(composed)

    def test_amendment_invalidates_stored_hypothesis(self):
        row_id = self.store_hypothesis(self.compose(self.run_once()))
        self.assertEqual(self.store.get_composed_hypothesis("CASE-ALPHA")["id"], row_id)
        self.amend()
        self.assertIsNone(self.store.get_composed_hypothesis("CASE-ALPHA"))
        rows = self.store.list_composed_hypotheses("CASE-ALPHA")
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["id"], row_id)
        self.assertIs(rows[0]["stale"], True)
        self.assertEqual(rows[0]["stale_reason"], "source_changed")

    def test_amendment_before_write_lock_rejects_hypothesis(self):
        # A second connection commits an amendment at the save boundary.
        # The cited investigation must be checked after taking the lock.
        self.store.close()
        with tempfile.TemporaryDirectory() as directory:
            path = str(Path(directory) / "race.sqlite")
            self.store = CaseStore(path)
            self.source_id, self.question_id = seed_case(self.store)
            inv_id = self.run_once()
            composed = self.compose(inv_id)
            peer = CaseStore(path)
            amended = (Path(__file__).resolve().parents[1] / "examples"
                       / "synthetic" / "alpha-pathology-amended.txt").read_bytes()
            fired = []
            def before_lock(sql):
                if sql == "BEGIN IMMEDIATE" and not fired:
                    fired.append(True)
                    peer.import_report("CASE-ALPHA", amended)
            self.store.db.set_trace_callback(before_lock)
            try:
                with self.assertRaises(InvalidInput):
                    self.store_hypothesis(composed)
                self.assertEqual(fired, [True])
                self.assertTrue(self.store.get_investigation(
                    "CASE-ALPHA", inv_id)["stale"])
                self.assertEqual(self.store.list_composed_hypotheses("CASE-ALPHA"), [])
            finally:
                self.store.db.set_trace_callback(None)
                peer.close()

    def test_inconsistent_composition_envelope_is_rejected(self):
        import copy
        composed = self.compose(self.run_once())
        variants = []
        for mutation in ("empty", "citation", "text", "count"):
            changed = copy.deepcopy(composed)
            if mutation == "empty":
                changed["sentences"] = []
            elif mutation == "citation":
                changed["sentences"][0]["claim_ids"] = ["inv999:c1"]
            elif mutation == "text":
                changed["text"] = "Different unsupported text."
            else:
                changed["char_count"] = 0
            variants.append((mutation, changed))
        for mutation, changed in variants:
            with self.subTest(mutation=mutation):
                before = self.store.db.execute("SELECT COUNT(*) FROM events").fetchone()[0]
                with self.assertRaises(InvalidInput):
                    self.store_hypothesis(changed)
                self.assertEqual(self.store.list_composed_hypotheses("CASE-ALPHA"), [])
                self.assertEqual(self.store.db.execute(
                    "SELECT COUNT(*) FROM events").fetchone()[0], before)

    def test_latest_stored_hypothesis_is_current(self):
        inv_id = self.run_once()
        second_text = "The sources report a finding again."
        first_id = self.store_hypothesis(self.compose(inv_id))
        second_id = self.store_hypothesis(self.compose(inv_id, text=second_text))
        self.assertEqual(self.store.get_composed_hypothesis("CASE-ALPHA")["text"],
                         second_text)
        rows = self.store.list_composed_hypotheses("CASE-ALPHA")
        self.assertEqual([row["id"] for row in rows], [second_id, first_id])
        self.assertEqual([row["text"] for row in rows], [second_text, self.TEXT])

    def test_route_case_mismatch_rejected(self):
        composed = self.compose(self.run_once())
        with self.assertRaises(WriteContractRejected) as ctx:
            self.store_hypothesis(composed, self.contract(case_id="CASE-BETA"))
        self.assertEqual(ctx.exception.reason, "route_mismatch")

    def test_assignment_not_enforced_at_save_time(self):
        """Deliberate W2 decision: the route assigns A1 only (policy v1), yet
        an A4 hypothesis stores. Assignment enforcement arrives with W4's
        route policy v2, not here."""
        inv_id = self.run_once()
        row_id = self.store_hypothesis(self.compose(inv_id))
        stored = self.store.get_composed_hypothesis("CASE-ALPHA")
        self.assertEqual(stored["id"], row_id)
        self.assertEqual(stored["write_contract"]["agentRole"], "A4")


class StoredHypothesisHttpTests(unittest.TestCase):
    """W2: the stored composed hypothesis, served live over HTTP."""

    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        cls.path = str(Path(cls.tmp.name) / "stored.sqlite")
        seed(cls.path)
        store = CaseStore(cls.path)
        try:
            question_id = store.add_question(
                "CASE-ALPHA", "What does the source report?")
            facts = store.investigation_facts("CASE-ALPHA", question_id)
            source_id = sorted(facts["valid_sources"])[0]
            run_id, _ = save_run(store, "CASE-ALPHA", question_id, source_id)
            cls.run_id = run_id
            composed = compose_hypothesis(
                [{"text": "The sources report a finding.",
                  "claim_ids": [claim_id(run_id, 1)]}],
                [{"id": claim_id(run_id, 1),
                  "text": "The sources report a finding.",
                  "uncertainty": "moderate",
                  "citations": [{"type": "source", "id": source_id}]}])
            write_contract = build_write_contract(
                agent_role="A4",
                model_id="recorded-replay",
                route_id=build_route_id(
                    "CASE-ALPHA", "evidence-summary", question_id),
                snapshot_at={"as_of": now_utc(), "event_id": None},
                inputs=[],
                prompt_version="hypothesis:1")
            store.save_composed_hypothesis(
                "CASE-ALPHA", composed, write_contract=write_contract)
        finally:
            store.close()
        bound = type("BoundHandlerForTest", (Handler,), {"db_path": cls.path})
        cls.server = ThreadingHTTPServer(("127.0.0.1", 0), bound)
        cls.port = cls.server.server_address[1]
        cls.thread = threading.Thread(target=cls.server.serve_forever,
                                      daemon=True)
        cls.thread.start()
        cls._cookie = signin_demo(cls.port, cls.path)

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.server.server_close()
        cls.thread.join(timeout=5)
        cls.tmp.cleanup()

    def request(self, path, headers=None):
        values = {"Cookie": self._cookie}
        values.update(headers or {})
        req = Request(f"http://127.0.0.1:{self.port}{path}", headers=values)
        try:
            with urlopen(req, timeout=5) as resp:
                return resp.status, json.loads(resp.read())
        except HTTPError as err:
            return err.code, json.loads(err.read())

    def test_report_route_shows_stored_hypothesis(self):
        status, data = self.request("/api/cases/CASE-ALPHA/hypothesis-report")
        self.assertEqual(status, 200)
        expected = claim_id(self.run_id, 1)
        self.assertEqual(data["hypothesis"]["status"], "composed")
        self.assertEqual(data["hypothesis"]["text"],
                         "The sources report a finding.")
        self.assertEqual(data["hypothesis"]["claim_ids"], [expected])
        self.assertTrue(data["kept_claims"])
        self.assertIn(expected, [c["id"] for c in data["kept_claims"]])

    def test_hypothesis_route_returns_stored_hypothesis(self):
        status, data = self.request("/api/cases/CASE-ALPHA/hypothesis")
        self.assertEqual(status, 200)
        self.assertEqual(data["case_id"], "CASE-ALPHA")
        hyp = data["hypothesis"]
        self.assertIsInstance(hyp, dict)
        self.assertEqual(hyp["status"], "composed")
        self.assertEqual(hyp["text"], "The sources report a finding.")
        self.assertEqual(hyp["write_contract"]["agentRole"], "A4")

    def test_hypothesis_route_returns_null_when_none_stored(self):
        status, data = self.request("/api/cases/CASE-BETA/hypothesis")
        self.assertEqual(status, 200)
        self.assertIsNone(data["hypothesis"])

    def test_hypothesis_route_requires_a_grant(self):
        req = Request(
            f"http://127.0.0.1:{self.port}/api/cases/CASE-ALPHA/hypothesis",
            headers={"X-Fictional-Actor": "FICTIONAL-NOBODY"})
        try:
            with urlopen(req, timeout=5) as resp:
                status = resp.status
        except HTTPError as err:
            status = err.code
        self.assertEqual(status, 403)


if __name__ == "__main__":
    unittest.main()
