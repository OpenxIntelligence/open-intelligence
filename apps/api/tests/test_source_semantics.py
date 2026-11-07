"""Synthetic contract and real-PostgreSQL source semantics acceptance."""
import copy
import unittest
from unittest.mock import patch
from pathlib import Path
import json

from oi_api.source_semantics import project_source_semantics
from oi_api.source_world_model import project_source_world_model
from oi_api.app import create_app
from http_support import running_server
from test_patients import request, TOKEN_A, TOKEN_B
from test_source_versions import SourceVersionFixture, AMENDED


def fixture():
    source_id = "SRC-" + "A" * 32
    states = ["reported", "negative", "pending", "indeterminate", "not-reported", "not-assessed", "conflicting"]
    index = dict(contract="oi.synthetic-original-sources/1", patient_id="PAT-SYNTH",
        case_id="CASE-ALPHA", access_receipt_id="ACCESS-"+"A"*32, synthetic=True,
        clinical_interpretation=False, research_review_invalidation_integrated=False,
        sources=[dict(source_id=source_id, document_id="DOC-SYNTH", version=1, sha256="a"*64,
            kind="pathology", event_date="2026-01-01", issued_at="2026-01-02",
            received_at="2026-01-02T00:00:00Z", specimen_id="SPECIMEN-SYNTH",
            state="current", supersedes_id=None)],
        source_reported_assertions=[dict(source_id=source_id, source_line=n+8, finding_key=f"item-{n}",
            reported_state=state, source_statement="Independently authored synthetic statement.",
            clinical_review_state="not_established") for n,state in enumerate(states)])
    return project_source_world_model(index)


class SourceSemanticContractTests(unittest.TestCase):
    def test_classifies_without_losing_original_state_or_changing_source_snapshot(self):
        world = fixture()
        before = copy.deepcopy(world)
        packet = project_source_semantics(world).model_dump(mode="json")
        self.assertEqual(world, before)
        self.assertEqual(packet["source_snapshot_sha256"], world["snapshot_fingerprint"])
        self.assertEqual([r["evidence_status"] for r in packet["records"]],
                         ["present", "negative", "pending", "indeterminate", "missing", "missing", "conflicting"])
        self.assertEqual([r["original_state"] for r in packet["records"]],
                         [o["reported_state"] for o in world["observations"]])
        self.assertTrue(all(r["knowledge_kind"] == "reported" for r in packet["records"]))

    def test_laboratory_absence_is_never_negative_and_unknown_states_fail(self):
        world = fixture()
        world["laboratory_observations"] = [dict(source_id="SRC-"+"B"*32, source_sha256="b"*64,
            observation_reference=f"Observation/{reason}", status="reported_absent", absent_reason=reason)
            for reason in ("unknown", "not-performed", "error", "masked")]
        refs = project_source_semantics(world).records[-4:]
        self.assertEqual([r.evidence_status for r in refs], ["indeterminate", "missing", "indeterminate", "missing"])
        self.assertEqual([r.original_state for r in refs], ["unknown", "not-performed", "error", "masked"])
        world["laboratory_observations"][0]["absent_reason"] = "unsupported"
        with self.assertRaises(KeyError):
            project_source_semantics(world)

    def test_browser_fixture_matches_python_contract(self):
        fixture_path = Path(__file__).resolve().parents[2] / "web/tests/fixtures/source-semantics.json"
        data = json.loads(fixture_path.read_text())
        self.assertEqual(data["world"], fixture())
        self.assertEqual(data["semantics"], project_source_semantics(data["world"]).model_dump(mode="json"))


class SourceSemanticHTTPTests(SourceVersionFixture):
    def test_authorized_read_amendment_restart_and_revocation(self):
        with running_server(create_app(self.settings)) as base:
            patient = self.setup_case(base)
            self.assertEqual(self.ingest(base, patient)[0], 201)
            path = f"/v1/patients/{patient}/cases/CASE-ALPHA/world-model/semantics"
            status, first, headers = request(base, path, token=TOKEN_A)
            self.assertEqual(status, 200)
            self.assertEqual(headers["Cache-Control"], "no-store")
            self.assertEqual(first["records"][0]["evidence_status"], "missing")
            self.assertEqual(request(base, path, token=TOKEN_B)[0], 404)
            self.assertEqual(request(base, path.replace("CASE-ALPHA", "CASE-OTHER"), token=TOKEN_A)[0], 404)
            self.assertEqual(self.ingest(base, patient, AMENDED)[0], 201)
            amended = request(base, path, token=TOKEN_A)[1]
            self.assertEqual(amended["records"][0]["evidence_status"], "negative")
            self.assertNotEqual(amended["source_snapshot_sha256"], first["source_snapshot_sha256"])
            self.assertNotEqual(amended["records"][0]["record_id"], first["records"][0]["record_id"])
        with running_server(create_app(self.settings)) as restarted:
            self.assertEqual(request(restarted, path, token=TOKEN_A)[1]["records"], amended["records"])
            self.creds[0]["actions"].remove("source_read")
            self.write()
            self.assertEqual(request(restarted, path, token=TOKEN_A)[0], 404)

    def test_final_authority_recheck_withholds_prepared_semantics(self):
        with running_server(create_app(self.settings)) as base:
            patient = self.setup_case(base)
            self.assertEqual(self.ingest(base, patient)[0], 201)
            path = f"/v1/patients/{patient}/cases/CASE-ALPHA/world-model/semantics"
            original = project_source_semantics
            def revoke_after_projection(world):
                packet = original(world)
                self.creds[0]["actions"].remove("source_read")
                self.write()
                return packet
            with patch("oi_api.patients.project_source_semantics", side_effect=revoke_after_projection):
                status, body, _ = request(base, path, token=TOKEN_A)
            self.assertEqual((status, body), (404, {"detail":"Source unavailable"}))
