"""Tests for the branch-only mock specialist adapter (issue #15).

All fixtures are independently authored fictional synthetic reports, labeled
as such. These tests prove the harness contract shapes (receipt, candidates,
capability gate, fail-closed denials) — not any model behavior. No network,
no model, no Nano involvement anywhere in this file.
"""

import ast
import json
import re
import unittest
from pathlib import Path

from open_intelligence.store import CaseStore
from tools.mock_specialist_adapter import (
    AdapterError,
    check_capability,
    contains_clinical_language,
    run_mock_specialist,
)


def _report(patient, document, event_date, issued_at, findings, specimen=None):
    lines = ["OI-SYNTHETIC-REPORT/1", f"Patient: {patient}",
             f"Document: {document}", "Type: pathology",
             f"Event-Date: {event_date}", f"Issued-At: {issued_at}"]
    if specimen is not None:
        lines.append(f"Specimen: {specimen}")
    for key, state, quote in findings:
        lines.append(f"Finding: {key}|{state}|{quote}")
    return ("\n".join(lines) + "\n").encode()


REPORT_A = _report(
    "CASE-MOCK", "PATH-MOCKA", "2026-05-03", "2026-05-04",
    [("marker-b", "reported", "Fictional note records Marker B as present."),
     ("marker-c", "negative", "Fictional note records Marker C as absent.")],
    specimen="SPECIMEN-MOCKA")

REPORT_B = _report(
    "CASE-MOCK", "PATH-MOCKB", "2026-06-10", "2026-06-11",
    [("marker-d", "pending", "Fictional note records Marker D as pending.")],
    specimen="SPECIMEN-MOCKB")


def _capability(**overrides):
    record = {
        "capability_id": "mock-chronology/1",
        "model_provider": "local-mock",
        "provider_approval_ref": None,
        "task_type": "chronology_extraction",
        "modality": "text-report",
        "owner_label": "Fictional issue-15 harness (branch only)",
        "record_state": "cleared",
        "input_schema": "issue15-task-input/1",
        "output_schema": "issue15-task-output/1",
        "required_context": ["specimen_id"],
        "qc_rules": ["anchor-resolves", "no-clinical-vocabulary", "uncertainty-present"],
        "abstention_conditions": ["missing-required-context", "conflicting-input-dates"],
        "execution_modes": ["local_only"],
        "allowed_data_classes": ["fictional-synthetic"],
        "forbidden_data_classes": ["real-patient-data"],
        "retention_terms": "none-stored-pure-function (mock design statement)",
        "training_use_terms": "no-training-use (mock design statement)",
        "dependency_licenses": "stdlib-only, no weights, no data (mock design statement)",
        "per_use_rights": "explicit mock allow-list in request (mock design statement)",
        "cost_latency": {"cost": "0", "latency": "negligible-local"},
        "evaluation_ref": "none",
        "evaluation_date": "none",
        "failure_thresholds": "none",
        "known_limitations": ["Mock harness only; proves contract shapes, not model behavior."],
        "synthetic": True,
    }
    record.update(overrides)
    return record


PERMISSIONS_OK = {"full_text": {"ml_use": "allowed"}}


def _adapter_inputs(store, case_id="CASE-MOCK"):
    """Build adapter inputs from real ledger rows (references only)."""
    inputs = []
    rows = store.db.execute(
        """SELECT id,document_id,version,sha256,event_date,issued_at,
                  received_at,specimen_id FROM source_versions
           WHERE case_id=? ORDER BY id""", (case_id,)).fetchall()
    for row in rows:
        findings = [dict(f) for f in store.db.execute(
            """SELECT finding_key,certainty,source_line FROM assertions
               WHERE source_version_id=? ORDER BY finding_key""",
            (row["id"],)).fetchall()]
        inputs.append({
            "source_version_id": row["id"],
            "document_id": row["document_id"],
            "version": row["version"],
            "sha256": row["sha256"],
            "event_date": row["event_date"],
            "issued_at": row["issued_at"],
            "received_at": row["received_at"],
            "state": "current",
            "specimen_id": row["specimen_id"],
            "episode_id": "EPISODE-MOCK-1",
            "lesion_id": None,
            "assay_ref": None,
            "findings": findings,
        })
    return inputs


def _store_with_reports():
    store = CaseStore(":memory:")
    store.add_case("CASE-MOCK", "Fictional mock-adapter case")
    store.import_report("CASE-MOCK", REPORT_A)
    store.import_report("CASE-MOCK", REPORT_B)
    return store


def _request(store, **overrides):
    request = {
        "task_type": "chronology_extraction",
        "modality": "text-report",
        "case_scope": "CASE-MOCK",
        "purpose": "Fictional demo: order two synthetic reports by occurred date.",
        "capability": _capability(),
        "permissions": dict(PERMISSIONS_OK),
        "rights_flags": {"revoked": False, "superseded": False},
        "execution_mode": "local_only",
        "inputs": _adapter_inputs(store),
    }
    request.update(overrides)
    return request


class MockSpecialistAdapterTests(unittest.TestCase):
    def test_happy_path_candidates_reference_exact_anchors(self):
        store = _store_with_reports()
        try:
            result = run_mock_specialist(_request(store))
        finally:
            store.close()
        self.assertEqual(result["status"], "completed")
        self.assertEqual(len(result["candidates"]), 3)
        first = result["candidates"][0]
        self.assertEqual(first["epistemic_level"], "extracted_candidate")
        self.assertEqual(first["source_ref"]["document_id"], "PATH-MOCKA")
        self.assertEqual(first["source_ref"]["version"], 1)
        self.assertEqual(first["source_ref"]["source_line"], 8)
        self.assertEqual(first["polarity"], "reported")
        self.assertEqual(first["occurred"], "2026-05-03")
        self.assertEqual(first["documented"], "2026-05-04")
        self.assertEqual(first["review_state"], "pending")
        self.assertEqual(first["validity"], "current")
        self.assertTrue(first["synthetic"])
        receipt = result["receipt"]
        self.assertEqual(receipt["case_scope"], "CASE-MOCK")
        self.assertIsNone(receipt["investigation_id"])
        self.assertEqual(receipt["model_provider"], "local-mock")
        self.assertIn("Fictional demo", receipt["purpose"])
        self.assertEqual(receipt["egress_mode"], "local_only")
        self.assertEqual(receipt["review_state"], "pending")
        self.assertEqual(receipt["policy_decision"]["outcome"], "allowed")
        self.assertEqual(receipt["derived_artifacts"],
                         [c["candidate_id"] for c in result["candidates"]])
        self.assertTrue(result["synthetic"])
        self.assertIn("Fictional", result["disclaimer"])

    def test_unknown_license_terms_block_with_inspectable_denial(self):
        store = _store_with_reports()
        try:
            capability = _capability(dependency_licenses="unknown")
            result = run_mock_specialist(_request(store, capability=capability))
        finally:
            store.close()
        self.assertEqual(result["status"], "blocked_by_policy")
        self.assertEqual(result["candidates"], [])
        receipt = result["receipt"]
        self.assertEqual(receipt["egress_mode"], "blocked")
        self.assertEqual(receipt["review_state"], "pending")
        self.assertEqual(receipt["policy_decision"]["gate"], "capability")
        self.assertIn("dependency_licenses", receipt["denial_reason"])
        self.assertTrue(receipt["synthetic"])

    def test_denied_ml_use_blocks(self):
        store = _store_with_reports()
        try:
            perms = {"full_text": {"ml_use": "denied"}}
            result = run_mock_specialist(_request(store, permissions=perms))
        finally:
            store.close()
        self.assertEqual(result["status"], "blocked_by_policy")
        self.assertEqual(result["candidates"], [])
        self.assertEqual(result["receipt"]["policy_decision"]["gate"], "rights")
        self.assertEqual(result["receipt"]["egress_mode"], "blocked")

    def test_missing_permission_blocks_fail_closed(self):
        store = _store_with_reports()
        try:
            result = run_mock_specialist(_request(store, permissions={}))
        finally:
            store.close()
        self.assertEqual(result["status"], "blocked_by_policy")
        self.assertEqual(result["candidates"], [])

    def test_revoked_rights_block(self):
        store = _store_with_reports()
        try:
            flags = {"revoked": True, "superseded": False}
            result = run_mock_specialist(_request(store, rights_flags=flags))
        finally:
            store.close()
        self.assertEqual(result["status"], "blocked_by_policy")
        self.assertEqual(result["candidates"], [])

    def test_malformed_rights_flags_block(self):
        store = _store_with_reports()
        try:
            result = run_mock_specialist(_request(store, rights_flags="active"))
        finally:
            store.close()
        self.assertEqual(result["status"], "blocked_by_policy")
        self.assertEqual(result["candidates"], [])

    def test_uncleared_capability_blocks(self):
        store = _store_with_reports()
        try:
            capability = _capability(record_state="proposed")
            result = run_mock_specialist(_request(store, capability=capability))
        finally:
            store.close()
        self.assertEqual(result["status"], "blocked_by_policy")
        self.assertIn("not cleared", result["receipt"]["denial_reason"])

    def test_modality_mismatch_blocks(self):
        store = _store_with_reports()
        try:
            capability = _capability(modality="pathology-wsi")
            result = run_mock_specialist(_request(store, capability=capability))
        finally:
            store.close()
        self.assertEqual(result["status"], "blocked_by_policy")
        self.assertIn("modality", result["receipt"]["denial_reason"])

    def test_unlisted_execution_mode_blocks(self):
        store = _store_with_reports()
        try:
            result = run_mock_specialist(_request(store, execution_mode="authorized_remote"))
        finally:
            store.close()
        self.assertEqual(result["status"], "blocked_by_policy")
        self.assertIn("execution mode", result["receipt"]["denial_reason"])

    def test_nonlocal_provider_without_approval_blocks(self):
        store = _store_with_reports()
        try:
            capability = _capability(model_provider="external-x")
            result = run_mock_specialist(_request(store, capability=capability))
        finally:
            store.close()
        self.assertEqual(result["status"], "blocked_by_policy")
        self.assertIn("provider approval", result["receipt"]["denial_reason"])

    def test_nonlocal_provider_with_approval_refuses_execution(self):
        # The registry gate passes, but the mock still refuses to execute:
        # minting a mock-built receipt under a non-local provider would be
        # a hollow receipt. Gate and execution are two separate layers.
        store = _store_with_reports()
        try:
            capability = _capability(model_provider="external-x",
                                     provider_approval_ref="approval/fictional/1")
            gate = check_capability(capability, task_type="chronology_extraction",
                                    modality="text-report", execution_mode="local_only")
            self.assertEqual(gate["outcome"], "allowed")
            result = run_mock_specialist(_request(store, capability=capability))
        finally:
            store.close()
        self.assertEqual(result["status"], "blocked_by_policy")
        self.assertEqual(result["candidates"], [])
        receipt = result["receipt"]
        self.assertEqual(receipt["policy_decision"]["gate"], "execution")
        self.assertEqual(receipt["egress_mode"], "blocked")
        self.assertIn("local providers only", receipt["denial_reason"])
        self.assertEqual(receipt["model_provider"], "external-x")
        self.assertTrue(receipt["synthetic"])

    def test_authorized_remote_listed_still_refused(self):
        # Even a capability record listing authorized_remote cannot make the
        # mock claim a remote run: the harness has no remote machinery.
        store = _store_with_reports()
        try:
            capability = _capability(execution_modes=["local_only", "authorized_remote"])
            result = run_mock_specialist(_request(
                store, capability=capability, execution_mode="authorized_remote"))
        finally:
            store.close()
        self.assertEqual(result["status"], "blocked_by_policy")
        self.assertEqual(result["candidates"], [])
        receipt = result["receipt"]
        self.assertEqual(receipt["policy_decision"]["gate"], "execution")
        self.assertEqual(receipt["egress_mode"], "blocked")
        self.assertIn("local_only", receipt["denial_reason"])

    def test_missing_schema_declaration_blocks(self):
        store = _store_with_reports()
        try:
            capability = _capability(input_schema="")
            result = run_mock_specialist(_request(store, capability=capability))
        finally:
            store.close()
        self.assertEqual(result["status"], "blocked_by_policy")
        self.assertIn("input_schema", result["receipt"]["denial_reason"])

    def test_unknown_task_type_raises(self):
        store = _store_with_reports()
        try:
            with self.assertRaises(AdapterError):
                run_mock_specialist(_request(store, task_type="treatment_planning"))
        finally:
            store.close()

    def test_invalid_case_scope_raises(self):
        store = _store_with_reports()
        try:
            with self.assertRaises(AdapterError):
                run_mock_specialist(_request(store, case_scope="lowercase-bad"))
        finally:
            store.close()

    def test_clinical_language_in_purpose_raises(self):
        store = _store_with_reports()
        try:
            with self.assertRaises(AdapterError):
                run_mock_specialist(_request(
                    store, purpose="Recommend treatment for this fictional case."))
        finally:
            store.close()

    def test_clinical_language_in_modality_raises(self):
        store = _store_with_reports()
        try:
            with self.assertRaises(AdapterError):
                run_mock_specialist(_request(store, modality="treatment-planning"))
        finally:
            store.close()

    def test_clinical_language_in_case_scope_raises(self):
        store = _store_with_reports()
        try:
            with self.assertRaises(AdapterError):
                run_mock_specialist(_request(store, case_scope="TREATMENT-1"))
        finally:
            store.close()

    def test_clinical_language_in_input_reference_raises(self):
        store = _store_with_reports()
        try:
            request = _request(store)
            request["inputs"][0]["received_at"] = "treatment o'clock"
            with self.assertRaises(AdapterError):
                run_mock_specialist(request)
        finally:
            store.close()

    def test_clinical_language_in_required_context_raises(self):
        store = _store_with_reports()
        try:
            capability = _capability(required_context=["treatment"])
            with self.assertRaises(AdapterError):
                run_mock_specialist(_request(store, capability=capability))
        finally:
            store.close()

    def test_missing_required_context_abstains_without_guessing(self):
        store = CaseStore(":memory:")
        try:
            store.add_case("CASE-MOCK", "Fictional mock-adapter case")
            store.import_report("CASE-MOCK", REPORT_A)
            no_specimen = _report(
                "CASE-MOCK", "PATH-MOCKC", "2026-07-01", "2026-07-02",
                [("marker-e", "reported", "Fictional note records Marker E.")])
            store.import_report("CASE-MOCK", no_specimen)
            result = run_mock_specialist(_request(store))
        finally:
            store.close()
        self.assertEqual(result["status"], "completed")
        self.assertEqual(len(result["candidates"]), 2)
        self.assertEqual(len(result["abstentions"]), 1)
        abstention = result["abstentions"][0]
        self.assertEqual(abstention["reason"], "insufficient_evidence")
        self.assertIn("specimen_id", abstention["detail"])
        self.assertEqual({c["source_ref"]["document_id"] for c in result["candidates"]},
                         {"PATH-MOCKA"})

    def test_conflicting_specimen_dates_abstain_with_no_winner(self):
        store = CaseStore(":memory:")
        try:
            store.add_case("CASE-MOCK", "Fictional mock-adapter case")
            store.import_report("CASE-MOCK", REPORT_A)
            other_date = _report(
                "CASE-MOCK", "PATH-MOCKD", "2026-05-24", "2026-05-25",
                [("marker-f", "reported", "Fictional note records Marker F.")],
                specimen="SPECIMEN-MOCKA")
            store.import_report("CASE-MOCK", other_date)
            result = run_mock_specialist(_request(store))
        finally:
            store.close()
        self.assertEqual(result["status"], "abstained")
        self.assertEqual(result["candidates"], [])
        self.assertEqual(len(result["abstentions"]), 2)
        for abstention in result["abstentions"]:
            self.assertEqual(abstention["reason"], "conflicting_evidence")

    def test_partial_occurred_date_abstains_without_poisoning_sibling(self):
        # G-4: a non-full occurred date abstains (never guessed into a
        # candidate), and must not drag a sibling input into a conflict.
        store = _store_with_reports()
        try:
            request = _request(store)
            request["inputs"][0]["event_date"] = "2026-05"
            request["inputs"][1]["specimen_id"] = "SPECIMEN-MOCKA"
            result = run_mock_specialist(request)
        finally:
            store.close()
        self.assertEqual(result["status"], "completed")
        self.assertEqual(len(result["candidates"]), 1)
        self.assertEqual(result["candidates"][0]["occurred"], "2026-06-10")
        self.assertEqual(len(result["abstentions"]), 1)
        self.assertEqual(result["abstentions"][0]["reason"], "insufficient_evidence")
        self.assertIn("G-4", result["abstentions"][0]["detail"])

    def test_superseded_input_fails_creation(self):
        store = _store_with_reports()
        try:
            request = _request(store)
            request["inputs"][0]["state"] = "superseded"
            with self.assertRaises(AdapterError):
                run_mock_specialist(request)
        finally:
            store.close()

    def test_receipt_records_modality_cost_and_denial_fields(self):
        store = _store_with_reports()
        try:
            completed = run_mock_specialist(_request(store))
            perms = {"full_text": {"ml_use": "denied"}}
            denied = run_mock_specialist(_request(store, permissions=perms))
        finally:
            store.close()
        receipt = completed["receipt"]
        self.assertEqual(receipt["modality"], "text-report")
        self.assertIsNone(receipt["token_compute_cost"])
        self.assertIsNone(receipt["denial_reason"])
        self.assertEqual(receipt["policy_decision"]["gate"],
                         "capability+rights+execution")
        denial = denied["receipt"]
        self.assertEqual(denial["modality"], "text-report")
        self.assertIsNone(denial["token_compute_cost"])
        self.assertTrue(denial["denial_reason"])

    def test_run_id_ignores_purpose_but_separates_execution_target(self):
        store = _store_with_reports()
        try:
            base = run_mock_specialist(_request(store))
            reworded = run_mock_specialist(_request(
                store, purpose="Fictional demo: reworded purpose, same run."))
            remote_cap = _capability(execution_modes=["local_only", "authorized_remote"])
            remote = run_mock_specialist(_request(
                store, capability=remote_cap, execution_mode="authorized_remote"))
            ext_cap = _capability(model_provider="external-x",
                                  provider_approval_ref="approval/fictional/1")
            external = run_mock_specialist(_request(store, capability=ext_cap))
        finally:
            store.close()
        self.assertEqual(base["receipt"]["run_id"], reworded["receipt"]["run_id"])
        self.assertNotEqual(base["receipt"]["run_id"], remote["receipt"]["run_id"])
        self.assertNotEqual(base["receipt"]["run_id"], external["receipt"]["run_id"])
        self.assertEqual(remote["status"], "blocked_by_policy")
        self.assertEqual(external["status"], "blocked_by_policy")

    def test_runs_are_deterministic(self):
        store = _store_with_reports()
        try:
            first = run_mock_specialist(_request(store))
            second = run_mock_specialist(_request(store))
        finally:
            store.close()
        self.assertEqual(first, second)
        self.assertEqual(first["receipt"]["run_id"], second["receipt"]["run_id"])

    def test_receipt_hashes_are_well_formed(self):
        store = _store_with_reports()
        try:
            result = run_mock_specialist(_request(store))
        finally:
            store.close()
        pattern = re.compile(r"\Asha256:[0-9a-f]{64}\Z")
        for field in ("run_id", "input_fingerprint", "output_hash"):
            self.assertRegex(result["receipt"][field], pattern)

    def test_candidates_cite_only_run_inputs(self):
        store = _store_with_reports()
        try:
            request = _request(store)
            result = run_mock_specialist(request)
        finally:
            store.close()
        allowed = {(i["source_version_id"], i["document_id"], i["version"])
                   for i in request["inputs"]}
        for candidate in result["candidates"]:
            ref = candidate["source_ref"]
            self.assertIn((ref["source_version_id"], ref["document_id"], ref["version"]),
                          allowed)

    def test_outputs_carry_no_clinical_vocabulary(self):
        store = _store_with_reports()
        try:
            result = run_mock_specialist(_request(store))
        finally:
            store.close()
        text = json.dumps(result, sort_keys=True)
        self.assertFalse(contains_clinical_language(text))

    def test_adapter_module_uses_no_network(self):
        path = Path(__file__).resolve().parents[1] / "tools" / "mock_specialist_adapter.py"
        source = path.read_text(encoding="utf-8")
        for token in ("import urllib", "from urllib", "import socket",
                      "import requests", "from requests", "http.client", "urlopen(",
                      "import os", "from os", "import sys", "import subprocess",
                      "import pathlib", "import shutil", "import http"):
            self.assertNotIn(token, source)
        roots = set()
        for node in ast.walk(ast.parse(source)):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    roots.add(alias.name.split(".")[0])
            elif isinstance(node, ast.ImportFrom):
                if node.module:
                    roots.add(node.module.split(".")[0])
        self.assertLessEqual(
            roots, {"__future__", "hashlib", "json", "re", "datetime"})
        self.assertIn("Fictional", source)


if __name__ == "__main__":
    unittest.main()
