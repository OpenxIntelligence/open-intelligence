"""Synthetic contract and real-PostgreSQL source semantics acceptance."""
import copy
from dataclasses import replace
from datetime import datetime, timedelta, timezone
from urllib.parse import quote
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
            self.assertEqual((status, body), (404, {"detail":"Patient unavailable"}))

    def test_historical_semantics_replay_original_after_amendment_and_restart(self):
        with running_server(create_app(self.settings)) as base:
            patient = self.setup_case(base)
            self.assertEqual(self.ingest(base, patient)[0], 201)
            root = f"/v1/patients/{patient}/cases/CASE-ALPHA/world-model"
            cutoff = request(base, root, token=TOKEN_A)[1]["as_of_received_at"]
            before = request(base, root+"/semantics", token=TOKEN_A)[1]
            self.assertEqual(self.ingest(base, patient, AMENDED)[0], 201)
            current = request(base, root+"/semantics", token=TOKEN_A)[1]
            path = root+"/history/semantics?received_through="+quote(cutoff,safe="")
            status, past, _ = request(base, path, token=TOKEN_A)
            self.assertEqual(status, 200, past)
            self.assertTrue(past["historical_only"])
            self.assertTrue(past["current_authority_required"])
            self.assertEqual(past["semantics"]["records"], before["records"])
            self.assertEqual(past["semantics"]["source_snapshot_sha256"], before["source_snapshot_sha256"])
            self.assertNotEqual(past["semantics"]["records"], current["records"])
            self.assertEqual(request(base, root+"/semantics", token=TOKEN_A)[1]["records"], current["records"])
            self.assertEqual(request(base,path,token=TOKEN_B)[0],404)
            self.assertEqual(request(base,path.replace('CASE-ALPHA','CASE-OTHER'),token=TOKEN_A)[0],404)
        with running_server(create_app(self.settings)) as base:
            self.assertEqual(request(base,path,token=TOKEN_A)[1]["semantics"]["records"],before["records"])
            self.creds[0]["actions"].remove("source_read"); self.write()
            self.assertEqual(request(base,path,token=TOKEN_A)[0],404)

    def test_persisted_grants_control_both_current_and_historical_semantics(self):
        self.creds[0]["actions"].extend(["patient_permissions_read","patient_permissions_manage"])
        self.write()
        with running_server(create_app(self.settings)) as base:
            patient=self.setup_case(base)
            self.assertEqual(self.ingest(base,patient)[0],201)
            root=f"/v1/patients/{patient}/cases/CASE-ALPHA/world-model"
            cutoff=request(base,root,token=TOKEN_A)[1]["as_of_received_at"]
        routes=[root+"/semantics",root+"/history/semantics?received_through="+quote(cutoff,safe="")]
        governed=replace(self.settings,require_persisted_grants=True)
        with running_server(create_app(governed)) as base:
            for route in routes:
                self.assertEqual(request(base,route,token=TOKEN_A)[0],404)
            status, grant, _=request(base,f"/v1/patients/{patient}/permissions",token=TOKEN_A,body=dict(
                synthetic=True,request_key="SEMANTIC-GRANT",authority_ref="AUTHORITY-FICTIONAL",
                actor="ACTOR-ALPHA",purpose="operations",actions=["patient_read","source_read"],
                relationship="care_team",expires_at=(datetime.now(timezone.utc)+timedelta(minutes=20)).isoformat()))
            self.assertEqual(status,200,grant)
            for route in routes:
                self.assertEqual(request(base,route,token=TOKEN_A)[0],200)
            status, body, _=request(base,f"/v1/patients/{patient}/permissions/{grant['grant_id']}/revocations",
                token=TOKEN_A,body=dict(synthetic=True,request_key="SEMANTIC-REVOKE",
                    authority_ref="AUTHORITY-REVOKED",expected_revision=1))
            self.assertEqual(status,200,body)
            for route in routes:
                self.assertEqual(request(base,route,token=TOKEN_A)[0],404)
        with running_server(create_app(governed)) as base:
            for route in routes:
                self.assertEqual(request(base,route,token=TOKEN_A)[0],404)

    def test_historical_semantics_final_recheck_rolls_back_prepared_audit(self):
        from sqlalchemy import text
        with running_server(create_app(self.settings)) as base:
            patient=self.setup_case(base)
            self.assertEqual(self.ingest(base,patient)[0],201)
            root=f"/v1/patients/{patient}/cases/CASE-ALPHA/world-model"
            cutoff=request(base,root,token=TOKEN_A)[1]["as_of_received_at"]
            path=root+"/history/semantics?received_through="+quote(cutoff,safe="")
            def count():
                with self.engine.connect() as c:
                    return c.execute(text('SELECT count(*) FROM identity.identity_domain_events')).scalar_one()
            before=count()
            def revoke(world):
                packet=project_source_semantics(world)
                self.creds[0]["actions"].remove("source_read");self.write()
                return packet
            with patch('oi_api.patients.project_source_semantics',side_effect=revoke):
                self.assertEqual(request(base,path,token=TOKEN_A)[0],404)
            self.assertEqual(count(),before)

    def test_semantic_source_references_survive_actual_database_dump_restore(self):
        import os
        from pathlib import Path
        import subprocess
        import tempfile
        import uuid
        from sqlalchemy.engine import make_url
        from sqlalchemy import text

        with running_server(create_app(self.settings)) as base:
            patient=self.setup_case(base)
            self.assertEqual(self.ingest(base,patient)[0],201)
            root=f"/v1/patients/{patient}/cases/CASE-ALPHA/world-model"
            cutoff=request(base,root,token=TOKEN_A)[1]['as_of_received_at']
            self.assertEqual(self.ingest(base,patient,AMENDED)[0],201)
            history=root+'/history/semantics?received_through='+quote(cutoff,safe='')
            before_current=request(base,root+'/semantics',token=TOKEN_A)[1]
            before_history=request(base,history,token=TOKEN_A)[1]['semantics']
        url=make_url(self.settings.database_url)
        self.assertTrue(url.database.startswith('oi_api_test_'))
        restored='oi_api_test_semantic_restore_'+uuid.uuid4().hex
        command_scope=['--host',url.host or '127.0.0.1','--port',str(url.port or 5432),'--username',url.username]
        environment=dict(os.environ,PGPASSWORD=url.password or '')
        restored_settings=replace(self.settings,database_url=url.set(database=restored).render_as_string(hide_password=False))
        with tempfile.TemporaryDirectory() as directory:
            dump=str(Path(directory)/'synthetic.dump')
            subprocess.run(['pg_dump',*command_scope,'--dbname',url.database,'--format=custom','--file',dump],
                           env=environment,check=True,capture_output=True)
            with self.engine.connect().execution_options(isolation_level='AUTOCOMMIT') as c:
                c.execute(text('CREATE DATABASE '+restored))
            try:
                subprocess.run(['pg_restore',*command_scope,'--dbname',restored,'--exit-on-error',dump],
                               env=environment,check=True,capture_output=True)
                with running_server(create_app(restored_settings)) as base:
                    for path, before, historical in ((root+'/semantics',before_current,False),(history,before_history,True)):
                        status,value,_=request(base,path,token=TOKEN_A)
                        self.assertEqual(status,200,value)
                        packet=value['semantics'] if historical else value
                        self.assertNotEqual(packet['access_receipt_id'],before['access_receipt_id'])
                        self.assertEqual({k:v for k,v in packet.items() if k!='access_receipt_id'},
                                         {k:v for k,v in before.items() if k!='access_receipt_id'})
                    self.creds[0]['actions'].remove('source_read');self.write()
                    for path in (root+'/semantics',history):
                        self.assertEqual(request(base,path,token=TOKEN_A)[0],404)
            finally:
                with self.engine.connect().execution_options(isolation_level='AUTOCOMMIT') as c:
                    c.execute(text('DROP DATABASE '+restored+' WITH (FORCE)'))
