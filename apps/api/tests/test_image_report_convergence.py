"""One canonical question across images, citations, authored reports and tasks.

The baseline imports only existing evidence-owner fixtures. Image-specific
fixtures are loaded after a behavioral route assertion, so the tests-first
failure is missing application behavior, not an unavailable future import.
All records and image bytes are independently fictional engineering material.
"""
from pathlib import Path
import unittest

from alembic.config import Config
from alembic.script import ScriptDirectory
from sqlalchemy import text

from http_support import running_server
from oi_api.app import create_app
from oi_api.config import Settings
from oi_api.contracts import SCHEMA_REVISION
from oi_api.database import Database
from oi_api.evidence_catalog import append_rights_decision, fictional_records, seed_fictional_records
from open_intelligence.postgres_registry import PostgresPatientRegistry
from test_canonical_review_flow import create_question
import test_evidence_convergence_migrations as existing_upgrades
from test_evidence_owner_convergence import AUTHORED_ACTIONS, ORIGINAL_EVIDENCE, QUOTE
from test_patients import TOKEN_A, TOKEN_B, request
from test_source_versions import AMENDED, ORIGINAL, SourceVersionFixture


MERGED_REVISION = "0012_image_report_convergence"
REPORT_REVISION = "0011_evidence_convergence"
IMAGE_REVISION = "0011_image_evidence_merge"
QUESTION_PATH = "/v1/patients/{patient_id}/cases/{case_id}/questions/{question_id}"
IMAGE_PATH = "/v1/patients/{patient_id}/cases/{case_id}/sources/{source_id}/images"
IMAGE_ACTIONS = ("image_import", "image_read", "image_original_read")
IMAGING_ORIGINAL = ORIGINAL.replace("Type: pathology", "Type: imaging")
IMAGING_AMENDED = AMENDED.replace("Type: pathology", "Type: imaging")


def declared_rights():
    rights = {item: {use: "unknown" for use in ("store", "display", "redistribute", "ml_use")}
              for item in ("metadata", "abstract", "full_text", "figures", "terminology", "api_output")}
    for item in ("metadata", "api_output"):
        rights[item].update(store="allowed", display="allowed", redistribute="allowed")
    return rights


class ImageReportConvergenceContractTests(unittest.TestCase):
    def test_one_api_retains_the_image_and_all_existing_question_owners(self):
        paths = create_app(Settings.from_env({})).openapi()["paths"]
        for path, method in (
            (IMAGE_PATH, "post"), (IMAGE_PATH, "get"), (IMAGE_PATH + "/{image_id}", "get"),
            (QUESTION_PATH + "/evidence-links", "get"),
            (QUESTION_PATH + "/evidence", "get"),
            (QUESTION_PATH + "/evidence-reports/{report_id}", "get"),
            (QUESTION_PATH + "/followthrough", "post"),
        ):
            with self.subTest(path=path, method=method):
                self.assertIn(path, tuple(paths), "The connected API is missing a published owner")
                self.assertEqual(paths[path][method]["security"], [{"SyntheticFixture": []}])

    def test_single_new_head_keeps_both_published_0011_histories(self):
        config = Config()
        config.set_main_option("script_location", str(Path(__file__).resolve().parents[1] / "migrations"))
        script = ScriptDirectory.from_config(config)
        self.assertEqual(script.get_heads(), [MERGED_REVISION],
                         "Image and authored-report histories need one explicit joining head")
        self.assertEqual(SCHEMA_REVISION, MERGED_REVISION)
        self.assertEqual(set(script.get_revision(MERGED_REVISION).down_revision),
                         {REPORT_REVISION, IMAGE_REVISION})
        self.assertEqual(script.get_revision(REPORT_REVISION).down_revision,
                         ("0010_question_evidence", "0010_authored_evidence_origin"))
        self.assertEqual(script.get_revision(IMAGE_REVISION).down_revision,
                         ("0009_image_review_merge", "0010_question_evidence"))


class ImageReportConvergenceHTTPTests(SourceVersionFixture):
    snapshot = existing_upgrades.EvidenceConvergenceMigrationTests.snapshot

    def require_images(self):
        self.assertIn(IMAGE_PATH, tuple(create_app(self.settings).openapi()["paths"]),
                      "The canonical patient/source API has no original-image owner")
        # The guard above intentionally precedes donor-only fixture imports and
        # adding image actions to the current credential contract.
        from test_image_custody import image_bytes, image_request
        self.image_bytes, self.image_request = image_bytes, image_request
        self.creds[0]["actions"].extend((
            "composer_context_read", "question_create", "question_read",
            "evidence_read", "evidence_link", "followthrough_read", "followthrough_create",
            *AUTHORED_ACTIONS, *IMAGE_ACTIONS,
        ))
        self.write()
        database = Database(self.settings)
        try:
            with database.registry_connection() as connection:
                seed_fictional_records(PostgresPatientRegistry(connection, lambda *args: False),
                                       fictional_records(), recorded_by="INDEPENDENT-FIXTURE")
        finally:
            database.close()

    def read_json(self, base, path):
        code, value, _ = request(base, path, token=TOKEN_A)
        self.assertEqual(code, 200, value)
        return value

    def save(self, base, path, body):
        code, value, _ = request(base, path, token=TOKEN_A, body=body)
        self.assertEqual(code, 201, value)
        self.assertFalse(value["duplicate"])
        return path, body, value

    def populate(self, base):
        patient = self.setup_case(base)
        code, source, _ = self.ingest(base, patient, IMAGING_ORIGINAL)
        self.assertEqual(code, 201, source)
        sid = source["source_id"]
        question, fingerprint = create_question(self, base, patient, sid)
        case = f"/v1/patients/{patient}/cases/CASE-ALPHA"
        prefix = case + "/questions/" + question
        selected, = self.read_json(base, case + "/questions")["questions"]
        context = {"source_snapshot_contract": "oi.pg-source-world-model/1",
                   "expected_source_snapshot_sha256": fingerprint,
                   "expected_preflight_sha256": selected["preflight_sha256"]}
        image_path = case + "/sources/" + sid + "/images"
        raw = self.image_bytes(study_date="20260110")
        code, image, _ = self.image_request(base, image_path, raw=raw)
        self.assertEqual((code, image["result"]), (201, "imported"))

        code, search, _ = request(base, prefix + "/evidence-search", token=TOKEN_A,
                                  body={"synthetic": True, "query": "continuity"})
        self.assertEqual(code, 200, search)
        self.assertFalse(search["content_appraised"])
        catalog, = search["records"]
        citation = self.save(base, prefix + "/evidence-links", {
            "synthetic": True, "request_key": "IMAGE-REPORT-CITATION", **context,
            "citation": catalog["citation"], "expected_metadata_sha256": catalog["metadata_sha256"],
        })
        task = self.save(base, prefix + "/followthrough", {
            "synthetic": True, "request_key": "IMAGE-REPORT-TASK", **context,
            "title": "Inspect the fictional report and original image", "detail": "",
            "owner_label": "", "due_date": None, "review_trigger": "When the source report changes",
            "reason": "Preserve the independently authored follow-up question.",
        })
        packet = self.read_json(base, prefix + "/evidence")
        self.assertEqual((packet["evidence"], packet["assessments"], packet["reports"]), ([], [], []),
                         "A metadata citation must not silently create an assessed passage")
        original = self.save(base, prefix + "/evidence", {
            "synthetic": True, "request_key": "IMAGE-REPORT-EVIDENCE", "original_text": ORIGINAL_EVIDENCE,
            "content_item": "api_output", "permissions": declared_rights(),
        })
        evidence, = self.read_json(base, prefix + "/evidence")["evidence"]
        comparison = self.save(base, prefix + "/evidence-assessments", {
            "synthetic": True, "request_key": "IMAGE-REPORT-COMPARISON",
            "evidence_id": evidence["evidence_id"], "evidence_sha256": evidence["sha256"],
            "rights_sha256": evidence["rights_sha256"],
            "expected_source_snapshot_sha256": fingerprint,
            "expected_preflight_sha256": selected["preflight_sha256"],
            "quote": QUOTE, "relation": "context", "applicability": "limited",
            "rationale": "Fictional image custody provides no independent scientific or clinical validation.",
        })
        packet = self.read_json(base, prefix + "/evidence")
        preparation = self.save(base, prefix + "/evidence-reports", {
            "synthetic": True, "request_key": "IMAGE-REPORT-PREPARATION",
            "expected_packet_sha256": packet["packet_sha256"],
            "assessment_ids": [comparison[2]["assessment_id"]],
        })
        report_path = prefix + "/evidence-reports/" + preparation[2]["report_id"]
        report = self.read_json(base, report_path)
        self.assertEqual(report["state"], "current_unreviewed")
        self.assertEqual(report["question_id"], question)
        self.assertFalse(report["clinical_approval"])
        self.assertFalse(report["model_executed"])
        self.assertNotIn(catalog["citation"], report["body"])
        return dict(patient=patient, source=sid, question=question, case=case, prefix=prefix,
                    fingerprint=fingerprint, preflight=selected["preflight_sha256"], image_path=image_path,
                    raw=raw, image=image, catalog=catalog, citation=citation, task=task, evidence=evidence,
                    report_path=report_path, report=report,
                    writes=[citation, task, original, comparison, preparation])

    def assert_preserved_report(self, base, flow, state):
        current = self.read_json(base, flow["report_path"])
        self.assertEqual(current["state"], state)
        for name in ("report_id", "question_id", "body", "body_sha256", "snapshot", "snapshot_sha256", "prepared_at"):
            self.assertEqual(current[name], flow["report"][name], name)
        return current

    def retry(self, base, flow):
        before = self.snapshot()[0]
        for path, body, receipt in flow["writes"]:
            self.assertEqual(request(base, path, token=TOKEN_A, body=body)[:2],
                             (200, {**receipt, "duplicate": True}))
        after = self.snapshot()[0]
        for table in before.keys() - {"identity.identity_domain_events"}:
            self.assertEqual(after[table], before[table], table)

    def test_same_question_images_reports_citations_and_tasks_survive_amendment_and_restart(self):
        self.require_images()
        with running_server(create_app(self.settings)) as base:
            flow = self.populate(base)
            before = self.snapshot()[0]
            another = self.image_bytes(study_date="20260110", sop_uid="2.25.104", pixels=b"\x01\x00" * 4)
            code, imported, _ = self.image_request(base, flow["image_path"], raw=another)
            self.assertEqual((code, imported["result"]), (201, "imported"))
            self.assertEqual(self.image_request(base, flow["image_path"], raw=flow["raw"])[:2],
                             (200, {**flow["image"], "result": "duplicate"}))
            self.assertEqual(self.read_json(base, flow["case"] + "/world-model")["snapshot_fingerprint"],
                             flow["fingerprint"])
            selected, = self.read_json(base, flow["case"] + "/questions")["questions"]
            self.assertEqual((selected["question_id"], selected["preflight_sha256"]),
                             (flow["question"], flow["preflight"]))
            self.assert_preserved_report(base, flow, "current_unreviewed")
            after = self.snapshot()[0]
            for table in before.keys() - {"identity.identity_domain_events", "clinical_source.dicom_objects",
                                         "clinical_source.source_image_links"}:
                self.assertEqual(after[table], before[table], table)

            code, amended, _ = self.ingest(base, flow["patient"], IMAGING_AMENDED)
            self.assertEqual(code, 201, amended)
            self.assert_preserved_report(base, flow, "historical_reassessment_required")
            links = self.read_json(base, flow["prefix"] + "/evidence-links")
            self.assertEqual(links["source_context_state"], "source_reassessment_required")
            self.assertEqual(links["links"][0]["link_id"], flow["citation"][2]["link_id"])
            task, = self.read_json(base, flow["case"] + "/followthrough")["tasks"]
            self.assertEqual(task["task_id"], flow["task"][2]["task_id"])
            self.assertTrue(task["needs_recheck"])
            current_path = flow["case"] + "/sources/" + amended["source_id"] + "/images"
            for path in (flow["image_path"], current_path):
                self.assertEqual(self.image_request(base, path + "/" + flow["image"]["image_id"])[0], 404)
            code, relinked, _ = self.image_request(base, current_path, raw=flow["raw"])
            self.assertEqual((code, relinked["result"], relinked["image_id"]),
                             (201, "linked", flow["image"]["image_id"]))
            self.assert_preserved_report(base, flow, "historical_reassessment_required")
            self.retry(base, flow)
            # Relinking an image cannot authorize a fresh comparison or task
            # from the old source question's captured context.
            for path, body, _ in (flow["writes"][0], flow["writes"][1], flow["writes"][3]):
                self.assertEqual(request(base, path, token=TOKEN_A,
                    body={**body, "request_key": body["request_key"] + "-NEW"})[0], 409)
            self.assertEqual(self.read_json(base, flow["case"] + "/sources/" + flow["source"])["original_text"],
                             IMAGING_ORIGINAL)
        with running_server(create_app(self.settings)) as restarted:
            self.assert_preserved_report(restarted, flow, "historical_reassessment_required")
            self.assertEqual(self.image_request(restarted, current_path + "/" + flow["image"]["image_id"])[:2],
                             (200, flow["raw"]))
            self.assertEqual(self.read_json(restarted, flow["case"] + "/followthrough")["tasks"], [task])
            self.retry(restarted, flow)

    def test_independent_image_and_content_rights_do_not_bypass_shared_case_authority(self):
        self.require_images()
        with running_server(create_app(self.settings)) as base:
            flow = self.populate(base)
            image_path = flow["image_path"] + "/" + flow["image"]["image_id"]
            paths = (image_path, flow["prefix"] + "/evidence-links", flow["prefix"] + "/evidence",
                     flow["report_path"], flow["case"] + "/followthrough")
            for missing, expected in (
                ("image_original_read", (404, 200, 200, 200, 200)),
                ("evidence_read", (200, 404, 200, 200, 200)),
                ("authored_evidence_read", (200, 200, 404, 404, 200)),
                ("evidence_report_export", (200, 200, 200, 404, 200)),
                ("followthrough_read", (200, 200, 200, 200, 404)),
            ):
                with self.subTest(missing=missing):
                    self.creds[0]["actions"].remove(missing)
                    self.write()
                    try:
                        for path, status in zip(paths, expected):
                            before = self.snapshot() if status == 404 else None
                            actual = self.image_request(base, path) if path == image_path else request(base, path, token=TOKEN_A)
                            self.assertEqual(actual[0], status)
                            if before is not None:
                                self.assertEqual(self.snapshot(), before, "Denied read changed durable state")
                    finally:
                        self.creds[0]["actions"].append(missing)
                        self.write()
            for path in paths:
                self.assertEqual(request(base, path, token=TOKEN_B)[0], 404)

            database = Database(self.settings)
            try:
                with database.registry_connection() as connection:
                    append_rights_decision(PostgresPatientRegistry(connection, lambda *args: False),
                        "FICT-RECORD-CONTINUITY", "1", permissions={"metadata": {"store": "allowed", "display": "allowed"}},
                        revoked=True, superseded=False, recorded_by="FICTIONAL-REVIEWER",
                        reason="Withdraw fictional metadata display permission independently of image custody.")
            finally:
                database.close()
            redacted = self.read_json(base, paths[1])["links"][0]
            self.assertEqual((redacted["link_id"], redacted["status"], redacted["record"]),
                             (flow["citation"][2]["link_id"], "rights_restricted", None))
            self.assert_preserved_report(base, flow, "current_unreviewed")
            self.assertEqual(self.image_request(base, image_path)[:2], (200, flow["raw"]))
            self.save(base, flow["prefix"] + "/evidence/" + flow["evidence"]["evidence_id"] + "/withdraw", {
                "synthetic": True, "request_key": "IMAGE-REPORT-WITHDRAWAL",
                "reason": "Withdraw this fictional comparison family pending independent review.",
            })
            withheld = self.read_json(base, flow["report_path"])
            self.assertEqual((withheld["state"], withheld["body"], withheld["snapshot"]),
                             ("content_withheld", None, None))
            self.assertEqual(self.image_request(base, image_path)[:2], (200, flow["raw"]))
            self.assertEqual(self.read_json(base, flow["case"] + "/followthrough")["tasks"][0]["task_id"],
                             flow["task"][2]["task_id"])
            code, revoked, _ = request(base, f"/v1/patients/{flow['patient']}/case-bindings/CASE-ALPHA/revoke",
                token=TOKEN_A, body={"synthetic": True, "reason": "Withdraw the fictional joined case authority."})
            self.assertEqual((code, revoked["duplicate"]), (200, False))
            before = self.snapshot()
            for path in paths:
                self.assertEqual(request(base, path, token=TOKEN_A)[0], 404)
            for path, body, _ in flow["writes"]:
                self.assertEqual(request(base, path, token=TOKEN_A, body=body)[0], 404)
            self.assertEqual(self.image_request(base, flow["image_path"], raw=flow["raw"])[0], 404)
            self.assertEqual(self.snapshot(), before)


if __name__ == "__main__":
    unittest.main()
