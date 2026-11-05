"""Synthetic-only full recovery proof for native FHIR R4 laboratory custody.

Exercises the existing H1 Docker/PostgreSQL/FastAPI stack. No external FHIR
server, patient data, model, terminology service or clinical interpretation.
"""
from datetime import datetime, timedelta, timezone
import hashlib
import json
import os
from pathlib import Path
import secrets
import subprocess
import tempfile
import time
from urllib.error import HTTPError, URLError
from urllib.request import ProxyHandler, Request, build_opener
import uuid

from oi_api.contracts import SCHEMA_REVISION

ROOT = Path(__file__).resolve().parents[3]
BASE = "http://127.0.0.1:8000"
CASE = "CASE-FHIR-LAB"
RESTORED = "oi_api_test_fhir_lab_restore"

FHIR_V1 = (
    '{"resourceType":"Bundle","type":"collection","entry":['
    '{"fullUrl":"urn:uuid:00000000-0000-4000-8000-000000000001","resource":'
    '{"resourceType":"Patient","id":"FICTIONAL-PATIENT-A"}},'
    '{"fullUrl":"urn:uuid:00000000-0000-4000-8000-000000000002","resource":'
    '{"resourceType":"Specimen","id":"FICTIONAL-SPECIMEN-A",'
    '"subject":{"reference":"Patient/FICTIONAL-PATIENT-A"},'
    '"type":{"text":"Fictional plasma sample"},'
    '"collection":{"collectedDateTime":"2026-04-03T09:05:00-04:00"}}},'
    '{"fullUrl":"urn:uuid:00000000-0000-4000-8000-000000000003","resource":'
    '{"resourceType":"Observation","id":"FICTIONAL-OBS-A","status":"final",'
    '"category":[{"coding":[{"system":"http://terminology.hl7.org/CodeSystem/observation-category","code":"laboratory"}]}],'
    '"code":{"coding":[{"system":"http://loinc.org","code":"777-3"}]},'
    '"subject":{"reference":"Patient/FICTIONAL-PATIENT-A"},'
    '"specimen":{"reference":"Specimen/FICTIONAL-SPECIMEN-A"},'
    '"effectiveDateTime":"2026-04-03T09:05:00-04:00",'
    '"issued":"2026-04-04T12:00:00Z",'
    '"valueQuantity":{"value":4.20,"system":"http://unitsofmeasure.org","code":"10*9/L"}}},'
    '{"fullUrl":"urn:uuid:00000000-0000-4000-8000-000000000004","resource":'
    '{"resourceType":"DiagnosticReport","id":"FICTIONAL-REPORT-A","status":"final",'
    '"category":[{"coding":[{"system":"http://terminology.hl7.org/CodeSystem/observation-category","code":"laboratory"}]}],'
    '"code":{"coding":[{"system":"http://loinc.org","code":"58410-2"}]},'
    '"subject":{"reference":"Patient/FICTIONAL-PATIENT-A"},'
    '"specimen":[{"reference":"Specimen/FICTIONAL-SPECIMEN-A"}],'
    '"result":[{"reference":"Observation/FICTIONAL-OBS-A"}],'
    '"effectiveDateTime":"2026-04-03T09:05:00-04:00",'
    '"issued":"2026-04-04T12:00:00Z"}}]}'
)
FHIR_V2 = FHIR_V1.replace('"value":4.20', '"value":5.00').replace(
    '"issued":"2026-04-04T12:00:00Z"', '"issued":"2026-04-05T12:00:00Z"')


def main():
    project = "oi-h1-fhir-lab-proof-" + uuid.uuid4().hex[:12]
    compose = ["docker", "compose", "--project-name", project,
               "--file", str(ROOT / "apps/api/compose.yaml"),
               "--file", str(ROOT / "apps/api/compose.synthetic-access.yaml")]
    with tempfile.TemporaryDirectory(prefix="oi-synthetic-fhir-lab-access-") as directory:
        access = Path(directory); access.chmod(0o755)
        env = dict(os.environ, OI_API_ACCESS_DIRECTORY=directory)
        token = secrets.token_urlsafe(32)
        actions = ["patient_create", "patient_read", "case_binding_create", "case_binding_read",
                   "case_binding_revoke", "source_import", "source_read", "source_original_read",
                   "composer_context_read", "question_create", "question_read"]
        credential = {
            "token_sha256": hashlib.sha256(token.encode()).hexdigest(),
            "actor": "ACTOR-FHIR-LAB-PROOF", "organization": "ORG-FHIR-LAB-PROOF",
            "purpose": "operations", "actions": list(actions), "patient_ids": [],
            "expires_at": (datetime.now(timezone.utc) + timedelta(hours=1)).isoformat(),
        }

        def save_access():
            pending = access / "access.new"
            pending.write_text(json.dumps({"version":"oi.synthetic-access/1",
                                           "credentials":[credential]}), encoding="utf-8")
            pending.chmod(0o644); pending.replace(access / "access.json")

        def command(args, *, check=True, **kwargs):
            return subprocess.run(compose + args, cwd=ROOT, env=env, check=check,
                                  timeout=240, **kwargs)

        def request(path, body=None, *, authenticated=True):
            headers = {"Authorization":"Bearer " + token} if authenticated else {}
            if body is not None: headers["Content-Type"] = "application/json"
            req = Request(BASE + path, headers=headers,
                          data=None if body is None else json.dumps(body).encode())
            try:
                response = build_opener(ProxyHandler({})).open(req, timeout=8)
            except HTTPError as exc:
                response = exc
            with response:
                assert response.headers.get("Cache-Control") == "no-store"
                return response.status, json.load(response)

        def ready():
            deadline = time.monotonic() + 60
            while True:
                try:
                    status, body = request("/health/ready", authenticated=False)
                    if status == 200 and body["status"] == "ready":
                        assert body["database"]["required_revision"] == SCHEMA_REVISION
                        return
                except (OSError, URLError, TimeoutError):
                    pass
                if time.monotonic() >= deadline:
                    raise RuntimeError("FHIR laboratory API did not become ready")
                time.sleep(0.25)

        def query(sql, database="oi_api_synthetic"):
            result = command(["exec","-T","db","psql","-X","-U","oi_api","-d",database,
                              "-v","ON_ERROR_STOP=1","-At","-c",sql],
                             capture_output=True,text=True)
            return json.loads(result.stdout)

        def snapshot(database="oi_api_synthetic"):
            return query("""SELECT json_build_object(
              'revision',(SELECT version_num FROM public.alembic_version),
              'sources',(SELECT COALESCE(json_agg(x ORDER BY x.version),'[]'::json) FROM (
                SELECT source_id,case_id,document_id,version,sha256,encode(sha256(raw),'hex') raw_sha256,
                       octet_length(raw) byte_count,kind,event_date,issued_at,specimen_id,state,supersedes_id
                  FROM clinical_source.source_versions WHERE case_id='CASE-FHIR-LAB') x),
              'fhir_sources',(SELECT COALESCE(json_agg(x ORDER BY x.source_id),'[]'::json)
                FROM (SELECT * FROM clinical_source.fhir_laboratory_sources) x),
              'observations',(SELECT COALESCE(json_agg(x ORDER BY x.source_id,x.position),'[]'::json)
                FROM (SELECT * FROM clinical_source.fhir_laboratory_observations) x),
              'commands',(SELECT COALESCE(json_agg(x ORDER BY x.request_key),'[]'::json)
                FROM (SELECT * FROM clinical_source.fhir_laboratory_commands) x),
              'questions',(SELECT COALESCE(json_agg(x ORDER BY x.question_id),'[]'::json)
                FROM (SELECT question_id,patient_id,case_id,request_key,question,source_id,source_line,
                             source_sha256,source_version,source_snapshot_sha256,preflight_sha256,
                             source_snapshot_contract,anchor_kind,observation_reference
                        FROM investigation.source_questions WHERE case_id='CASE-FHIR-LAB') x)
            )""", database)

        def body(raw, key, previous=None):
            value = {"synthetic":True,"request_key":key,"bundle_json":raw}
            if previous is not None: value["expected_previous_source_id"] = previous
            return value

        def verify_world(patient_path, source_id, value, history):
            status, world = request(patient_path + "/cases/" + CASE + "/world-model")
            assert status == 200 and world["observations"] == []
            assert world["summary"]["current_laboratory_observations"] == 1
            assert world["summary"]["current_observations"] == 1
            assert world["summary"]["historical_sources"] == history
            lab, = world["laboratory_observations"]
            assert (lab["source_id"],lab["loinc_code"],lab["value_text"],lab["unit_code"]) == (
                source_id,"777-3",value,"10*9/L")
            assert lab["clinical_review"] == "not_performed" and lab["clinical_meaning"] is None
            timeline, = world["laboratory_timeline"]
            assert timeline["source_id"] == source_id
            assert timeline["clinical_interpretation"] == "not_performed"

        def verify_original(patient_path, source_id, raw, version, state):
            status, original = request(patient_path + "/cases/" + CASE + "/sources/" + source_id)
            assert status == 200
            assert (original["source_id"],original["version"],original["state"]) == (
                source_id,version,state)
            assert original["original_text"] == raw
            assert original["sha256"] == hashlib.sha256(raw.encode()).hexdigest()

        question_text = "What should I ask my care team about this source-reported result?"

        def prepare_question(patient_path, source_id):
            status, world = request(patient_path + "/cases/" + CASE + "/world-model")
            assert status == 200
            status, prepared = request(
                patient_path + "/cases/" + CASE + "/composer/laboratory-preflight",
                {"synthetic": True, "source_id": source_id,
                 "observation_reference": "Observation/FICTIONAL-OBS-A",
                 "question": question_text,
                 "expected_source_snapshot_sha256": world["snapshot_fingerprint"]})
            assert status == 200
            assert prepared["selected_source"]["source_id"] == source_id
            assert prepared["selected_source"]["observation_reference"] == "Observation/FICTIONAL-OBS-A"
            assert prepared["selected_source"]["source_line"] is None
            return world, prepared

        def question_body(source_id, world, prepared):
            return {"synthetic": True, "request_key": "FHIR-LAB-QUESTION-1",
                    "source_id": source_id,
                    "observation_reference": "Observation/FICTIONAL-OBS-A",
                    "question": question_text,
                    "expected_source_snapshot_sha256": world["snapshot_fingerprint"],
                    "expected_preflight_sha256": prepared["preflight_sha256"]}

        def verify_question(patient_path, question_id, expected_state):
            status, listing = request(
                patient_path + "/cases/" + CASE + "/questions/laboratory")
            assert status == 200 and listing["contract"] == "oi.synthetic-laboratory-questions/1"
            row = next(item for item in listing["questions"] if item["question_id"] == question_id)
            assert row["anchor_kind"] == "fhir_observation"
            assert row["observation_reference"] == "Observation/FICTIONAL-OBS-A"
            assert row["source_context_state"] == expected_state
            assert row["clinical_review_connected"] is False
            assert row["evidence_workflow_connected"] is False
            assert row["followthrough_connected"] is False
            assert row["clinical_approval"] is False and row["model_executed"] is False
            assert "source_line" not in row
            return row

        def serve_database(database):
            override = access / "restore.compose.json"
            override.write_text(json.dumps({"services":{"api":{"environment":{
                "OI_API_DATABASE_URL":"postgresql+pg8000://oi_api:oi_h1_synthetic_only@db:5432/" + database
            }}}}), encoding="utf-8")
            if str(override) not in compose: compose.extend(["--file",str(override)])
            command(["up","--no-deps","--force-recreate","--detach","api"]); ready()

        def restore(source_database, target):
            before = snapshot(source_database)
            dump = command(["exec","-T","db","pg_dump","-U","oi_api","-d",source_database,
                            "--format=custom"],capture_output=True).stdout
            command(["exec","-T","db","createdb","-U","oi_api",target])
            command(["exec","-T","db","pg_restore","-U","oi_api","-d",target,
                     "--exit-on-error","--no-owner"],input=dump)
            assert snapshot(target) == before
            serve_database(target)
            assert snapshot(target) == before and snapshot(source_database) == before
            return before

        save_access()
        try:
            command(["config","--quiet"]); command(["up","--build","--detach","api"]); ready()
            status, created = request("/v1/patients",{
                "synthetic":True,"request_key":"CREATE-FHIR-LAB-PROOF"})
            assert status == 201
            patient = created["patient_id"]; credential["patient_ids"]=[patient]; save_access()
            patient_path="/v1/patients/"+patient
            status, binding = request(patient_path+"/case-bindings",{
                "synthetic":True,"case_id":CASE,"source_organization":"ORG-FHIR-LAB-SOURCE",
                "source_system":"SYS-FHIR-LAB-R4","source_subject_ref":"FICTIONAL-PATIENT-A",
                "review_ref":"REVIEW-FHIR-LAB-PROOF"})
            assert status == 201 and binding["case_id"] == CASE
            endpoint=patient_path+"/cases/"+CASE+"/laboratory/fhir-r4/sources"

            status, first = request(endpoint,body(FHIR_V1,"FHIR-LAB-IMPORT-1"))
            assert status == 201 and first["version"] == 1 and first["observation_count"] == 1
            first_id=first["source_id"]
            assert request(endpoint,body(FHIR_V1,"FHIR-LAB-IMPORT-1")) == (
                200,{**first,"duplicate":True})
            verify_original(patient_path,first_id,FHIR_V1,1,"current")
            verify_world(patient_path,first_id,"4.20",0)

            question_world, question_preflight = prepare_question(patient_path, first_id)
            q_body = question_body(first_id, question_world, question_preflight)
            q_endpoint = patient_path + "/cases/" + CASE + "/questions/laboratory"
            status, saved_question = request(q_endpoint, q_body)
            assert status == 201 and saved_question["duplicate"] is False
            question_id = saved_question["question_id"]
            current_question = verify_question(
                patient_path, question_id, "current_unreviewed_question")
            assert current_question["source_id"] == first_id
            assert request(q_endpoint, q_body) == (
                200, {**saved_question, "duplicate": True})
            status, legacy_questions = request(
                patient_path + "/cases/" + CASE + "/questions")
            assert status == 200 and legacy_questions["questions"] == []

            assert request(endpoint,body(FHIR_V2,"FHIR-LAB-AMEND-WRONG"))[0] == 409
            status, second = request(endpoint,body(FHIR_V2,"FHIR-LAB-AMEND-1",first_id))
            assert status == 201 and second["version"] == 2
            second_id=second["source_id"]
            verify_original(patient_path,first_id,FHIR_V1,1,"superseded")
            verify_original(patient_path,second_id,FHIR_V2,2,"current")
            verify_world(patient_path,second_id,"5.00",1)
            stale_question = verify_question(
                patient_path, question_id, "source_reassessment_required")
            assert stale_question["source_id"] == first_id
            assert request(q_endpoint, q_body) == (
                200, {**saved_question, "duplicate": True})
            assert request(endpoint,body(FHIR_V1,"FHIR-LAB-STALE-REPLAY"))[0] == 409

            state=snapshot()
            assert state["revision"] == SCHEMA_REVISION
            assert len(state["sources"])==2 and len(state["fhir_sources"])==2
            assert len(state["observations"])==2 and len(state["commands"])==2
            assert len(state["questions"])==1
            persisted_question, = state["questions"]
            assert persisted_question["question_id"] == question_id
            assert persisted_question["anchor_kind"] == "fhir_observation"
            assert persisted_question["source_line"] is None
            assert persisted_question["observation_reference"] == "Observation/FICTIONAL-OBS-A"
            for row,raw in zip(state["sources"],(FHIR_V1,FHIR_V2)):
                digest=hashlib.sha256(raw.encode()).hexdigest()
                assert row["sha256"] == row["raw_sha256"] == digest

            for service in ("api","db"):
                before=snapshot(); command(["restart",service]); ready()
                assert snapshot() == before
                verify_original(patient_path,first_id,FHIR_V1,1,"superseded")
                verify_original(patient_path,second_id,FHIR_V2,2,"current")
                verify_world(patient_path,second_id,"5.00",1)
                verify_question(patient_path, question_id, "source_reassessment_required")
                assert request(q_endpoint, q_body) == (
                    200, {**saved_question, "duplicate": True})

            before_restore=restore("oi_api_synthetic",RESTORED)
            verify_original(patient_path,first_id,FHIR_V1,1,"superseded")
            verify_original(patient_path,second_id,FHIR_V2,2,"current")
            verify_world(patient_path,second_id,"5.00",1)
            restored_question = verify_question(
                patient_path, question_id, "source_reassessment_required")
            assert restored_question["source_id"] == first_id
            assert request(q_endpoint, q_body) == (
                200, {**saved_question, "duplicate": True})
            assert request(endpoint,body(FHIR_V2,"FHIR-LAB-AMEND-1",first_id)) == (
                200,{**second,"duplicate":True})
            after=snapshot(RESTORED)
            for key in ("sources","fhir_sources","observations","commands","questions"):
                assert after[key] == before_restore[key]

            status, revoked = request(patient_path+"/case-bindings/"+CASE+"/revoke",{
                "synthetic":True,"reason":"Fictional FHIR mapping withdrawn after restore"})
            assert status == 200 and revoked["case_id"] == CASE
            for path,payload in (
                (patient_path+"/cases/"+CASE+"/world-model",None),
                (patient_path+"/cases/"+CASE+"/sources/"+second_id,None),
                (q_endpoint,None),
                (q_endpoint,q_body),
                (endpoint,body(FHIR_V2,"FHIR-LAB-AFTER-REVOKE",second_id)),
            ):
                assert request(path,payload)[0] == 404
            print("PASS FHIR LABORATORY RECOVERY: exact JSON source versions, typed observations, "
                  "durable Observation-anchored question, amendment reassessment, exact question/source "
                  "retries, API/DB restart, pg_dump/pg_restore and restored binding revocation; "
                  "source-reported only, no clinical interpretation or downstream review/action.")
        finally:
            command(["down","--volumes","--remove-orphans"],check=False,
                    stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)


if __name__ == "__main__":
    main()
