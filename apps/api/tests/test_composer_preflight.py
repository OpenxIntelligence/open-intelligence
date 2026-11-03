"""Actual PG16 acceptance of version-pinned, no-execution Composer source preflight."""
import hashlib
import json
import unittest

from sqlalchemy import text
from http_support import running_server

from oi_api.app import create_app
from test_patients import TOKEN_A, TOKEN_B, request
from test_source_versions import SourceVersionHTTPTests as SourceFixture, AMENDED


QUESTION = "What is independently verifiable about this fictional source statement?"


class SourceComposerPreflightHTTPTests(SourceFixture):
    def setUp(self):
        super().setUp()
        self.creds[0]["actions"].append("composer_context_read")
        self.write()

    def source_world(self, base, patient, *, case="CASE-ALPHA", token=TOKEN_A):
        return request(base,
            f"/v1/patients/{patient}/cases/{case}/world-model",
            token=token)

    def preflight(self, base, patient, source, fingerprint, *, line=8,
                  case="CASE-ALPHA", token=TOKEN_A, question=QUESTION, **changes):
        data = {
            "synthetic": True,
            "expected_source_snapshot_sha256": fingerprint,
            "source_id": source, "source_line": line,
            "question": question,
        }
        data.update(changes)
        return request(base,
            f"/v1/patients/{patient}/cases/{case}/composer/source-preflight",
            token=token, body=data)

    def test_source_preflight_is_exact_and_read_only(self):
        with running_server(create_app(self.settings)) as base:
            pid = self.setup_case(base)
            source = self.ingest(base, pid)[1]["source_id"]
            world = self.source_world(base, pid)[1]
            fingerprint = world["source_snapshot_sha256"]
            with self.engine.connect() as db:
                before = db.execute(text(
                    "SELECT count(*) FROM identity.identity_domain_events"
                )).scalar_one()
            status, packet, _ = self.preflight(base, pid, source, fingerprint)
            self.assertEqual(status, 200)
            self.assertEqual(packet["contract"], "oi.synthetic-source-composer-preflight/1")
            self.assertEqual(packet["patient_id"], pid)
            self.assertEqual(packet["case_id"], "CASE-ALPHA")
            self.assertEqual(packet["source_snapshot_sha256"], fingerprint)
            self.assertEqual(packet["selected_source"]["source_id"], source)
            self.assertEqual(packet["selected_source"]["line"], 8)
            self.assertEqual(packet["selected_source"]["reported_state"], "not-reported")
            self.assertEqual(packet["selected_source"]["statement"],
                             world["observations"][0]["source_statement"])
            self.assertEqual(packet["question"], QUESTION)
            for name in ("clinical_approval", "durable_review_connected",
                         "durable_question_created", "model_execution_authorized",
                         "biomedical_evidence_rights_verified"):
                self.assertIs(packet[name], False)
            self.assertTrue(packet["source_context_only"])
            self.assertEqual(packet["clinical_interpretation"], "not_performed")
            self.assertEqual(packet["reassessment_policy"],
                             "revalidate_source_and_authority_before_any_future_write")
            digest = packet.pop("preflight_sha256")
            raw = json.dumps(packet, ensure_ascii=False, sort_keys=True,
                             separators=(",", ":"), allow_nan=False).encode("utf-8")
            self.assertEqual(digest, hashlib.sha256(raw).hexdigest())
            packet["preflight_sha256"] = digest
            same = self.preflight(base, pid, source, fingerprint)[1]
            self.assertEqual(same, packet)
            changed = self.preflight(base, pid, source, fingerprint,
                      question="Which uncertainty is explicitly reported in this fictional original?")[1]
            self.assertNotEqual(changed["preflight_sha256"], digest)
            with self.engine.connect() as db:
                after = db.execute(text(
                    "SELECT count(*) FROM identity.identity_domain_events"
                )).scalar_one()
            self.assertEqual(before, after)

    def test_amendment_demands_updated_world_fingerprint_and_new_exact_line(self):
        with running_server(create_app(self.settings)) as base:
            pid = self.setup_case(base)
            original = self.ingest(base, pid)[1]["source_id"]
            first = self.source_world(base, pid)[1]["source_snapshot_sha256"]
            self.assertEqual(self.preflight(base, pid, original, first)[0], 200)
            amended = self.ingest(base, pid, AMENDED)
            self.assertEqual(amended[0], 201)
            current = amended[1]["source_id"]
            self.assertEqual(self.preflight(base, pid, original, first)[0], 409)
            newer = self.source_world(base, pid)[1]["source_snapshot_sha256"]
            self.assertNotEqual(first, newer)
            self.assertEqual(self.preflight(base, pid, original, newer)[0], 409)
            self.assertEqual(self.preflight(base, pid, current, newer, line=8)[0], 409)
            status, packet, _ = self.preflight(base, pid, current, newer, line=9)
            self.assertEqual(status, 200)
            self.assertEqual(packet["selected_source"]["version"], 2)
            self.assertEqual(packet["selected_source"]["reported_state"], "negative")
            self.assertEqual(packet["selected_source"]["line"], 9)
            self.assertFalse(packet["durable_question_created"])
        with running_server(create_app(self.settings)) as restart:
            status, packet, _ = self.preflight(restart, pid, current, newer, line=9)
            self.assertEqual(status, 200)

    def test_composer_permission_is_separate_from_patient_and_source_read(self):
        with running_server(create_app(self.settings)) as base:
            pid = self.setup_case(base)
            original = self.ingest(base, pid)[1]["source_id"]
            fingerprint = self.source_world(base, pid)[1]["source_snapshot_sha256"]
            self.creds[0]["actions"].remove("composer_context_read")
            self.write()
            self.assertEqual(self.source_world(base, pid)[0], 200)
            self.assertEqual(self.preflight(base, pid, original, fingerprint)[0], 404)
            self.creds[0]["actions"].append("composer_context_read")
            self.creds[0]["actions"].remove("source_read")
            self.write()
            self.assertEqual(self.preflight(base, pid, original, fingerprint)[0], 404)
            self.creds[0]["actions"].append("source_read")
            self.write()
            self.assertEqual(self.preflight(base, pid, original, fingerprint)[0], 200)
            self.creds[0]["patient_ids"] = []
            self.write()
            self.assertEqual(self.preflight(base, pid, original, fingerprint)[0], 404)

    def test_wrong_patient_case_purpose_and_malformed_request_do_not_preflight(self):
        with running_server(create_app(self.settings)) as base:
            pid = self.setup_case(base)
            other = self.setup_case(base, token=TOKEN_B, case="CASE-BETA",
                                    key="CREATE-BETA", source_subject="SUBJECT-BETA")
            source = self.ingest(base, pid)[1]["source_id"]
            fp = self.source_world(base, pid)[1]["source_snapshot_sha256"]
            self.assertEqual(self.preflight(base, other, source, fp,
                                            case="CASE-BETA", token=TOKEN_B)[0], 404)
            self.assertEqual(self.preflight(base, pid, source, fp,
                                            case="CASE-BETA")[0], 404)
            self.assertEqual(self.preflight(base, pid, source, fp,
                                            token=TOKEN_B)[0], 404)
            self.creds[0]["purpose"] = "research"
            self.write()
            self.assertEqual(self.preflight(base, pid, source, fp)[0], 404)
            self.creds[0]["purpose"] = "operations"
            self.write()
            self.assertEqual(self.preflight(base, pid, source, fp, synthetic=False)[0], 422)
            self.assertEqual(self.preflight(base, pid, source, fp, question="x")[0], 422)
            self.assertEqual(self.preflight(base, pid, source, fp,
                                             question="Invalid\nquestion")[0], 422)
            self.assertEqual(self.preflight(base, pid, source, "0"*64)[0], 409)
            self.assertEqual(self.preflight(base, pid, source, fp, line=0)[0], 422)
            self.assertEqual(self.preflight(base, pid, source, fp,
                                            source_id="SRC-" + "F"*32)[0], 409)

    def test_case_binding_revocation_denies_preflight_but_preserves_original_history(self):
        with running_server(create_app(self.settings)) as base:
            pid = self.setup_case(base)
            source = self.ingest(base, pid)[1]["source_id"]
            fp = self.source_world(base, pid)[1]["source_snapshot_sha256"]
            self.assertEqual(self.preflight(base, pid, source, fp)[0], 200)
            revoked = request(base,
                f"/v1/patients/{pid}/case-bindings/CASE-ALPHA/revoke",
                token=TOKEN_A, body={"synthetic": True,
                                      "reason": "Fictional case mapping explicitly revoked"})
            self.assertEqual(revoked[0], 200)
            self.assertEqual(self.preflight(base, pid, source, fp)[0], 404)
            with self.engine.connect() as db:
                self.assertEqual(db.execute(text(
                    "SELECT count(*) FROM clinical_source.source_versions"
                )).scalar_one(), 1)


if __name__ == "__main__":
    unittest.main()
