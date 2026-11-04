"""Converge existing evidence owners without changing their authority or meaning.

Tests use only the published metadata base's fixtures. Missing authored routes
fail as missing behavior, before any new grant or optional owner is imported.
All text is independently fictional engineering material, not medical evidence.
"""
from pathlib import Path
import unittest

from alembic.config import Config
from alembic.script import ScriptDirectory
from sqlalchemy import text

from http_support import running_server
from oi_api.app import create_app
from oi_api.config import Settings
from oi_api.database import Database
from oi_api.evidence_catalog import fictional_records, seed_fictional_records
from open_intelligence.postgres_registry import PostgresPatientRegistry
from test_canonical_review_flow import create_question
from test_patients import TOKEN_A, request
from test_source_versions import AMENDED, SourceVersionFixture


PREFIX = "/v1/patients/{patient_id}/cases/{case_id}/questions/{question_id}"
MERGED_REVISION = "0011_evidence_convergence"
AUTHORED_ACTIONS = (
    "authored_evidence_read", "authored_evidence_import", "authored_evidence_assess",
    "authored_evidence_original_read", "authored_evidence_withdraw", "evidence_report_export",
)
QUOTE = "fictional continuity workflow can preserve its source anchors"
ORIGINAL_EVIDENCE = (
    "OI-SYNTHETIC-EVIDENCE/1\nEvidence: FICTION-CONTINUITY-COMPARISON\n"
    "Title: Independently authored continuity comparison\nIssued-At: 2026-11-03\n"
    "Rights: original-synthetic\n"
    "Statement: A fictional continuity workflow can preserve its source anchors; "
    "this authored example does not establish a clinical conclusion.\n"
)


class EvidenceConvergenceContractTests(unittest.TestCase):
    def test_one_api_exposes_metadata_authored_reports_and_followthrough(self):
        schema = create_app(Settings.from_env({})).openapi()
        for suffix, method in (
            ("/evidence-search", "post"), ("/evidence-links", "get"),
            ("/followthrough", "post"), ("/evidence", "get"),
            ("/evidence", "post"), ("/evidence-assessments", "post"),
            ("/evidence-reports", "post"), ("/evidence-reports/{report_id}", "get"),
        ):
            with self.subTest(suffix=suffix, method=method):
                self.assertIn(PREFIX + suffix, tuple(schema["paths"]),
                              "The combined patient-question API lost an existing owner")
                self.assertEqual(schema["paths"][PREFIX + suffix][method]["security"],
                                 [{"SyntheticFixture": []}])

    def test_single_head_preserves_both_published_migration_lineages(self):
        config = Config()
        config.set_main_option("script_location", str(Path(__file__).resolve().parents[1] / "migrations"))
        script = ScriptDirectory.from_config(config)
        self.assertEqual(script.get_heads(), ["0012_reviewed_documents"],
                         "The converged app needs one explicit head, not one abandoned owner")
        self.assertEqual(script.get_revision("0012_reviewed_documents").down_revision, MERGED_REVISION)
        self.assertEqual(set(script.get_revision(MERGED_REVISION).down_revision),
                         {"0010_question_evidence", "0010_authored_evidence_origin"})
        self.assertEqual(script.get_revision("0010_question_evidence").down_revision,
                         "0009_question_followthrough")
        self.assertEqual(script.get_revision("0010_authored_evidence_origin").down_revision,
                         "0009_question_evidence")


class EvidenceConvergenceHTTPTests(SourceVersionFixture):
    def test_one_question_retains_both_evidence_meanings_and_task_after_source_amendment(self):
        # This guard exposes the missing combined route on the unmodified base;
        # it must not fail because a future module or grant cannot be loaded.
        self.assertIn(PREFIX + "/evidence", tuple(create_app(self.settings).openapi()["paths"]),
                      "The canonical question has no authored evidence owner")
        self.creds[0]["actions"].extend((
            "composer_context_read", "question_create", "question_read",
            "evidence_read", "evidence_link", "followthrough_read", "followthrough_create",
            *AUTHORED_ACTIONS,
        ))
        self.write()
        with Database(self.settings).registry_connection() as connection:
            seed_fictional_records(PostgresPatientRegistry(connection, lambda *args: False),
                                   fictional_records(), recorded_by="FIXTURE-AUTHOR")
        with running_server(create_app(self.settings)) as base:
            patient = self.setup_case(base)
            code, source, _ = self.ingest(base, patient)
            self.assertEqual(code, 201, source)
            question, snapshot = create_question(self, base, patient, source["source_id"])
            case_path = f"/v1/patients/{patient}/cases/CASE-ALPHA"
            question_path = case_path + "/questions/" + question
            code, saved, _ = request(base, case_path + "/questions", token=TOKEN_A)
            self.assertEqual(code, 200, saved)
            selected, = saved["questions"]
            context = {
                "source_snapshot_contract": "oi.pg-source-world-model/1",
                "expected_source_snapshot_sha256": snapshot,
                "expected_preflight_sha256": selected["preflight_sha256"],
            }
            code, search, _ = request(base, question_path + "/evidence-search", token=TOKEN_A,
                                      body={"synthetic": True, "query": "continuity"})
            self.assertEqual(code, 200, search)
            record, = search["records"]
            link_intent = {"synthetic": True, "request_key": "CONVERGED-CITATION", **context,
                           "citation": record["citation"],
                           "expected_metadata_sha256": record["metadata_sha256"]}
            code, link, _ = request(base, question_path + "/evidence-links", token=TOKEN_A,
                                    body=link_intent)
            self.assertEqual(code, 201, link)
            self.assertFalse(search["content_appraised"])
            task_intent = {"synthetic": True, "request_key": "CONVERGED-TASK", **context,
                           "title": "Inspect the authored comparison", "detail": "",
                           "owner_label": "", "due_date": None,
                           "review_trigger": "When the source record changes",
                           "reason": "Keep the fictional preparation work visible."}
            code, task, _ = request(base, question_path + "/followthrough", token=TOKEN_A,
                                    body=task_intent)
            self.assertEqual(code, 201, task)
            # Catalog identity is not an authored passage or an assessed finding.
            code, empty, _ = request(base, question_path + "/evidence", token=TOKEN_A)
            self.assertEqual(code, 200, empty)
            self.assertEqual((empty["evidence"], empty["assessments"], empty["reports"]), ([], [], []))
            rights = {item: {use: "unknown" for use in ("store", "display", "redistribute", "ml_use")}
                      for item in ("metadata", "abstract", "full_text", "figures", "terminology", "api_output")}
            for item in ("metadata", "api_output"):
                rights[item].update(store="allowed", display="allowed", redistribute="allowed")
            code, imported, _ = request(base, question_path + "/evidence", token=TOKEN_A,
                body={"synthetic": True, "request_key": "CONVERGED-ORIGINAL",
                      "original_text": ORIGINAL_EVIDENCE, "content_item": "api_output", "permissions": rights})
            self.assertEqual(code, 201, imported)
            code, packet, _ = request(base, question_path + "/evidence", token=TOKEN_A)
            self.assertEqual(code, 200, packet)
            evidence, = packet["evidence"]
            self.assertEqual(packet["question"]["question_id"], question)
            self.assertEqual(packet["question"]["source_id"], source["source_id"])
            assessment_intent = {
                "synthetic": True, "request_key": "CONVERGED-ASSESSMENT",
                "evidence_id": imported["evidence_id"], "evidence_sha256": evidence["sha256"],
                "rights_sha256": evidence["rights_sha256"],
                "expected_source_snapshot_sha256": snapshot,
                "expected_preflight_sha256": selected["preflight_sha256"],
                "quote": QUOTE, "relation": "context", "applicability": "limited",
                "rationale": "Human-authored continuity example only; clinical review has not been performed.",
            }
            code, assessment, _ = request(base, question_path + "/evidence-assessments", token=TOKEN_A,
                                          body=assessment_intent)
            self.assertEqual(code, 201, assessment)
            packet = request(base, question_path + "/evidence", token=TOKEN_A)[1]
            report_intent = {"synthetic": True, "request_key": "CONVERGED-REPORT",
                             "expected_packet_sha256": packet["packet_sha256"],
                             "assessment_ids": [assessment["assessment_id"]]}
            code, prepared, _ = request(base, question_path + "/evidence-reports", token=TOKEN_A,
                                        body=report_intent)
            self.assertEqual(code, 201, prepared)
            report_path = question_path + "/evidence-reports/" + prepared["report_id"]
            code, report, _ = request(base, report_path, token=TOKEN_A)
            self.assertEqual(code, 200, report)
            self.assertEqual(report["state"], "current_unreviewed")
            self.assertIn(QUOTE, report["body"])
            self.assertNotIn(record["citation"], report["body"])
            self.assertFalse(report["clinical_approval"])
            self.assertFalse(report["model_executed"])
            # Convergence must not turn one owner's grant into another's.
            for missing, expected in (
                ("evidence_read", (404, 200, 200, 200)),
                ("authored_evidence_read", (200, 404, 404, 200)),
                ("evidence_report_export", (200, 200, 404, 200)),
                ("followthrough_read", (200, 200, 200, 404)),
            ):
                with self.subTest(independent_grant=missing):
                    self.creds[0]["actions"].remove(missing)
                    self.write()
                    try:
                        observed = (
                            request(base, question_path + "/evidence-links", token=TOKEN_A)[0],
                            request(base, question_path + "/evidence", token=TOKEN_A)[0],
                            request(base, report_path, token=TOKEN_A)[0],
                            request(base, case_path + "/followthrough", token=TOKEN_A)[0],
                        )
                        self.assertEqual(observed, expected)
                    finally:
                        self.creds[0]["actions"].append(missing)
                        self.write()
            self.assertEqual(self.ingest(base, patient, AMENDED)[0], 201)
            code, historical, _ = request(base, report_path, token=TOKEN_A)
            self.assertEqual(code, 200, historical)
            self.assertEqual(historical["state"], "historical_reassessment_required")
            self.assertEqual(historical["body"], report["body"])
            code, links, _ = request(base, question_path + "/evidence-links", token=TOKEN_A)
            self.assertEqual(code, 200, links)
            self.assertEqual(links["source_context_state"], "source_reassessment_required")
            self.assertEqual(links["links"][0]["link_id"], link["link_id"])
            code, tasks, _ = request(base, case_path + "/followthrough", token=TOKEN_A)
            self.assertEqual(code, 200, tasks)
            self.assertEqual(tasks["tasks"][0]["task_id"], task["task_id"])
            self.assertTrue(tasks["tasks"][0]["needs_recheck"])
            for suffix, intent, receipt in (
                ("/evidence-links", link_intent, link),
                ("/evidence-assessments", assessment_intent, assessment),
                ("/evidence-reports", report_intent, prepared),
                ("/followthrough", task_intent, task),
            ):
                with self.subTest(retry=suffix):
                    code, duplicate, _ = request(base, question_path + suffix, token=TOKEN_A, body=intent)
                    self.assertEqual(code, 200, duplicate)
                    self.assertEqual(duplicate, {**receipt, "duplicate": True})
            with self.engine.connect() as connection:
                self.assertEqual(connection.execute(text(
                    "SELECT count(*) FROM investigation.source_questions WHERE patient_id=:patient"
                ), {"patient": patient}).scalar_one(), 1)
        with running_server(create_app(self.settings)) as restarted:
            code, restored, _ = request(restarted, report_path, token=TOKEN_A)
            self.assertEqual(code, 200, restored)
            self.assertEqual((restored["body"], restored["body_sha256"]),
                             (report["body"], report["body_sha256"]))
            self.assertEqual(restored["state"], "historical_reassessment_required")


if __name__ == "__main__":
    unittest.main()
