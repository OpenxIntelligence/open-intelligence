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

from laboratory_followthrough_recovery import LaboratoryTaskRecovery, V2
from oi_api.contracts import SCHEMA_REVISION

ROOT = Path(__file__).resolve().parents[3]
BASE = "http://127.0.0.1:8000"
CASE = "CASE-FHIR-LAB"
RESTORED = "oi_api_test_fhir_lab_restore"
REVOKED_RESTORE = "oi_api_test_fhir_lab_revoked"
OBSERVATION = "Observation/FICTIONAL-OBS-A"

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
# The amended fictional source names its targets by their exact entry fullUrls.
# Keep the first source's relative links to exercise recovery of both spellings.
FHIR_V2 = (FHIR_V1.replace('"value":4.20', '"value":5.00')
           .replace("2026-04-04T12:00:00Z", "2026-04-05T12:00:00Z")
           .replace('"Patient/FICTIONAL-PATIENT-A"', '"urn:uuid:00000000-0000-4000-8000-000000000001"')
           .replace('"Specimen/FICTIONAL-SPECIMEN-A"', '"urn:uuid:00000000-0000-4000-8000-000000000002"')
           .replace('"Observation/FICTIONAL-OBS-A"', '"urn:uuid:00000000-0000-4000-8000-000000000003"'))


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
                   "composer_context_read", "question_create", "question_read", "evidence_read", "evidence_link",
                   "followthrough_read", "followthrough_create", "followthrough_update"]
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

        def request(path, body=None, *, authenticated=True, accept=None):
            headers = {"Authorization":"Bearer " + token} if authenticated else {}
            if accept is not None: headers["Accept"] = accept
            if body is not None: headers["Content-Type"] = "application/json"
            req = Request(BASE + path, headers=headers,
                          data=None if body is None else json.dumps(body).encode())
            try:
                response = build_opener(ProxyHandler({})).open(req, timeout=8)
            except HTTPError as exc:
                response = exc
            with response:
                assert response.headers.get("Cache-Control") == "no-store"
                if accept == V2 and response.status == 200:
                    assert response.headers.get_content_type() == V2
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
              'sources',(SELECT COALESCE(json_agg(x ORDER BY x.document_id,x.version,x.source_id),'[]'::json) FROM (
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
                FROM (SELECT * FROM investigation.source_questions) x),
              'question_anchors',(SELECT COALESCE(json_agg(x ORDER BY x.question_id),'[]'::json)
                FROM (SELECT * FROM investigation.laboratory_question_anchors) x),
              'question_events',(SELECT COALESCE(json_agg(x ORDER BY x.id),'[]'::json)
                FROM (SELECT * FROM identity.identity_domain_events
                       WHERE event_type='investigation.question.created') x),
              'source_import_events',(SELECT COALESCE(json_agg(x ORDER BY x.id),'[]'::json)
                FROM (SELECT * FROM identity.identity_domain_events
                       WHERE event_type='source.original.imported'
                         AND metadata_json->>'case_id'='CASE-FHIR-LAB') x),
              'sequence_state',(SELECT COALESCE(json_agg(x ORDER BY x.schemaname,x.sequencename),'[]'::json)
                FROM (SELECT schemaname,sequencename,start_value,min_value,max_value,
                             increment_by,cycle,cache_size,last_value FROM pg_sequences
                       WHERE schemaname IN ('identity','clinical_source','investigation','coordination')) x),
              'citations',(SELECT COALESCE(json_agg(x ORDER BY x.link_id),'[]'::json)
                FROM investigation.question_evidence_links x),
              'citation_anchors',(SELECT COALESCE(json_agg(x ORDER BY x.link_id),'[]'::json)
                FROM investigation.laboratory_citation_anchors x),
              'catalog',(SELECT COALESCE(json_agg(x ORDER BY x.record_id,x.version),'[]'::json)
                FROM investigation.evidence_catalog_records x),
              'rights',(SELECT COALESCE(json_agg(x ORDER BY x.record_id,x.version,x.revision),'[]'::json)
                FROM investigation.evidence_rights_decisions x),
              'citation_events',(SELECT COALESCE(json_agg(x ORDER BY x.id),'[]'::json)
                FROM (SELECT * FROM identity.identity_domain_events
                       WHERE event_type='evidence.citation.linked') x),
              'tasks',(SELECT COALESCE(json_agg(x ORDER BY x.task_id),'[]'::json)
                FROM coordination.question_followthrough_tasks x),
              'task_events',(SELECT COALESCE(json_agg(x ORDER BY x.task_id,x.revision),'[]'::json)
                FROM coordination.question_followthrough_events x),
              'task_audit',(SELECT COALESCE(json_agg(x ORDER BY x.id),'[]'::json)
                FROM (SELECT * FROM identity.identity_domain_events
                       WHERE event_type IN ('coordination.followthrough.created','coordination.followthrough.transitioned')) x),
              'bindings',(SELECT COALESCE(json_agg(x ORDER BY x.case_id),'[]'::json)
                FROM (SELECT * FROM coordination.patient_case_bindings) x)
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
            assert lab["observation_reference"] == OBSERVATION
            assert lab["specimen_reference"] == "Specimen/FICTIONAL-SPECIMEN-A"
            assert lab["report_reference"] == "DiagnosticReport/FICTIONAL-REPORT-A"
            assert (lab["source_id"],lab["loinc_code"],lab["value_text"],lab["unit_code"]) == (
                source_id,"777-3",value,"10*9/L")
            assert lab["clinical_review"] == "not_performed" and lab["clinical_meaning"] is None
            timeline, = world["laboratory_timeline"]
            assert timeline["source_id"] == source_id
            assert timeline["clinical_interpretation"] == "not_performed"
            return world["snapshot_fingerprint"]

        def save_question(case_path, source, fingerprint, key, literal):
            fields = {"synthetic": True, "source_id": source["source_id"],
                      "observation_reference": OBSERVATION, "question": literal,
                      "expected_source_snapshot_sha256": fingerprint}
            status, preview = request(case_path + "/composer/laboratory-preflight", fields)
            assert status == 200 and preview["durable_question_created"] is False
            assert preview["selected_source"]["sha256"] == source["original_sha256"]
            command = {**fields, "expected_preflight_sha256": preview["preflight_sha256"],
                       "request_key": key}
            status, saved = request(case_path + "/composer/laboratory-questions", command)
            assert status == 201 and saved["duplicate"] is False
            return command, saved

        def verify_questions(endpoint, versions, patient):
            status, result = request(endpoint)
            assert status == 200 and (result["patient_id"], result["case_id"]) == (patient, CASE)
            rows = {item["question_id"]: item for item in result["questions"]}
            assert len(rows) == len(result["questions"]) == len(versions)
            for source, command, saved, state in versions:
                row = rows[saved["question_id"]]
                expected = {"source_id": source["source_id"], "source_version": source["version"],
                            "source_sha256": source["original_sha256"], "observation_reference": OBSERVATION,
                            "question": command["question"], "source_context_state": state,
                            "source_snapshot_sha256": command["expected_source_snapshot_sha256"],
                            "preflight_sha256": command["expected_preflight_sha256"]}
                assert all(row[k] == v for k, v in expected.items()) and "source_line" not in row
            return result["access_receipt_id"]

        def cite(questions, question, source, saved_command, term, citation, key):
            path = questions + "/" + question["question_id"]
            anchor = {"source_id": source["source_id"], "source_version": source["version"],
                      "source_sha256": source["original_sha256"], "observation_reference": OBSERVATION,
                      "source_snapshot_sha256": saved_command["expected_source_snapshot_sha256"],
                      "preflight_sha256": saved_command["expected_preflight_sha256"]}
            status, found = request(path + "/evidence-search", {"synthetic": True, "query": term})
            assert status == 200 and found["question_anchor"] == anchor
            metadata, = found["records"]
            assert (metadata["citation"], metadata["availability"]) == (citation, "metadata_only")
            assert not any(found[name] for name in ("model_executed", "clinical_approval", "content_appraised"))
            payload = {"synthetic": True, "request_key": key, "citation": citation,
                       "expected_metadata_sha256": metadata["metadata_sha256"],
                       "source_snapshot_contract": "oi.pg-source-world-model/1",
                       "expected_source_snapshot_sha256": anchor["source_snapshot_sha256"],
                       "expected_preflight_sha256": anchor["preflight_sha256"]}
            status, receipt = request(path + "/evidence-links", payload)
            assert status == 201 and receipt["duplicate"] is False
            status, result = request(path + "/evidence-links")
            assert status == 200 and result["question_anchor"] == anchor
            row, = result["links"]
            assert row["record"] == metadata and row["link_id"] == receipt["link_id"]
            return {"path": path, "anchor": anchor, "entry": row, "payload": payload,
                    "receipt": receipt, "term": term}

        def verify_citation(cited, state, *, restricted=False):
            status, result = request(cited["path"] + "/evidence-links")
            assert status == 200 and result["question_anchor"] == cited["anchor"]
            assert result["source_context_state"] == state
            row, = result["links"]
            original = cited["entry"]
            assert row == ({**original, "record": None, "status": "rights_restricted"}
                           if restricted else original)
            if restricted:
                wire = json.dumps(result)
                assert original["record"]["title"] not in wire and original["record"]["link"] not in wire
            return result["source_access_receipt_id"]

        def withdraw_fixture_rights():
            # Exercise the existing trusted operator port, only for the second fictional citation.
            command(["exec", "-T", "api", "python", "-c", """
from oi_api.config import Settings
from oi_api.database import Database
from oi_api.evidence_catalog import append_rights_decision
from open_intelligence.postgres_registry import PostgresPatientRegistry
database = Database(Settings.from_env())
try:
    with database.registry_connection() as connection:
        append_rights_decision(PostgresPatientRegistry(connection), "FICT-TRIAL-PREPARATION", "1",
            permissions={}, revoked=True, superseded=False, recorded_by="FIXTURE-LAB-REVIEWER",
            reason="Withdraw this independently fictional catalog item before backup")
finally:
    database.close()
"""])

        def verify_original(patient_path, source_id, raw, version, state):
            status, original = request(patient_path + "/cases/" + CASE + "/sources/" + source_id)
            assert status == 200
            assert (original["source_id"],original["version"],original["state"]) == (
                source_id,version,state)
            assert original["original_text"] == raw
            assert original["sha256"] == hashlib.sha256(raw.encode()).hexdigest()

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
            case_path = patient_path+"/cases/"+CASE
            endpoint = case_path+"/laboratory/fhir-r4/sources"
            questions = case_path+"/composer/laboratory-questions"

            command(["exec", "-T", "api", "python", "-m", "oi_api.evidence_catalog"])
            status, first = request(endpoint,body(FHIR_V1,"FHIR-LAB-IMPORT-1"))
            assert status == 201 and first["version"] == 1 and first["observation_count"] == 1
            first_id=first["source_id"]
            assert request(endpoint,body(FHIR_V1,"FHIR-LAB-IMPORT-1")) == (
                200,{**first,"duplicate":True})
            verify_original(patient_path,first_id,FHIR_V1,1,"current")
            first_fingerprint = verify_world(patient_path,first_id,"4.20",0)
            cmd1, saved1 = save_question(case_path, first, first_fingerprint, "LAB-QUESTION-ORIGINAL",
                                         "What does the first fictional source report?")
            verify_questions(questions, [(first, cmd1, saved1, "current_unreviewed_question")], patient)

            tasks = LaboratoryTaskRecovery(request, case_path)
            historical_task = tasks.create(first, saved1, cmd1, "LAB-TASK-ORIGINAL")
            tasks.transition(historical_task, "assigned")
            tasks.transition(historical_task, "acknowledged")
            tasks.verify_history(stale=set())

            first_cite = cite(questions, saved1, first, cmd1, "continuity", "FICT-RECORD-CONTINUITY@1", "CITE-V1")
            assert request(endpoint,body(FHIR_V2,"FHIR-LAB-AMEND-WRONG"))[0] == 409
            status, second = request(endpoint,body(FHIR_V2,"FHIR-LAB-AMEND-1",first_id))
            assert status == 201 and second["version"] == 2
            second_id=second["source_id"]
            verify_original(patient_path,first_id,FHIR_V1,1,"superseded")
            verify_original(patient_path,second_id,FHIR_V2,2,"current")
            second_fingerprint = verify_world(patient_path,second_id,"5.00",1)
            cmd2, saved2 = save_question(case_path, second, second_fingerprint, "LAB-QUESTION-AMENDED",
                                         "What changed in the amended fictional report?")
            assert saved2["question_id"] != saved1["question_id"]
            versions = [(first, cmd1, saved1, "source_reassessment_required"),
                        (second, cmd2, saved2, "current_unreviewed_question")]
            verify_questions(questions, versions, patient)
            assert request(endpoint,body(FHIR_V1,"FHIR-LAB-STALE-REPLAY"))[0] == 409

            current_task = tasks.create(second, saved2, cmd2, "LAB-TASK-AMENDED")
            for status in ("assigned", "acknowledged", "completed"):
                tasks.transition(current_task, status)
            tasks.verify_history(stale={historical_task})
            tasks.reject_stale(historical_task)

            second_cite = cite(questions, saved2, second, cmd2, "trial", "FICT-TRIAL-PREPARATION@1", "CITE-V2")
            verify_citation(first_cite, "source_reassessment_required")
            verify_citation(second_cite, "current_unreviewed_question")

            state=snapshot()
            tasks.verify_storage(state)
            assert state["revision"] == SCHEMA_REVISION
            assert len(state["sources"])==2 and len(state["fhir_sources"])==2
            assert len(state["observations"])==2 and len(state["commands"])==2
            assert len(state["citations"]) == len(state["citation_anchors"]) == len(state["citation_events"]) == 2
            by_link = {row["link_id"]: row for row in state["citations"]}
            decisions = {row["decision_id"]: row for row in state["rights"]}
            anchors_by_link = {row["link_id"]: row for row in state["citation_anchors"]}
            for cited, question in ((first_cite, saved1), (second_cite, saved2)):
                row = by_link[cited["receipt"]["link_id"]]
                decision = decisions[anchors_by_link[row["link_id"]]["rights_decision_id"]]
                assert (decision["record_id"], decision["version"]) == (row["record_id"], row["version"])
                assert decision["revoked"] is False and decision["superseded"] is False
                assert all(decision["permissions"]["metadata"][use] == "allowed" for use in ("store", "display"))
                assert (row["question_id"], row["source_snapshot_sha256"], row["preflight_sha256"]) == (
                    question["question_id"], cited["anchor"]["source_snapshot_sha256"], cited["anchor"]["preflight_sha256"])
            assert {(row["link_id"], row["question_id"], row["source_id"], row["observation_reference"])
                    for row in state["citation_anchors"]} == {
                    (first_cite["receipt"]["link_id"], saved1["question_id"], first_id, OBSERVATION),
                    (second_cite["receipt"]["link_id"], saved2["question_id"], second_id, OBSERVATION)}

            assert len(state["questions"]) == len(state["question_events"]) == len(state["question_anchors"]) == 2
            assert {event["metadata_json"]["source_id"] for event in state["source_import_events"]} == {
                first_id, second_id}
            assert len(state["source_import_events"]) == 2
            for event in state["question_events"]:
                prior_imports = {item["metadata_json"]["source_id"]
                                 for item in state["source_import_events"] if item["id"] < event["id"]}
                assert event["metadata_json"]["source_id"] in prior_imports
            assert {(a["question_id"], a["source_id"], a["observation_reference"])
                    for a in state["question_anchors"]} == {
                        (saved1["question_id"], first_id, OBSERVATION),
                        (saved2["question_id"], second_id, OBSERVATION),
                    }
            for row,raw in zip(state["sources"],(FHIR_V1,FHIR_V2)):
                digest=hashlib.sha256(raw.encode()).hexdigest()
                assert row["sha256"] == row["raw_sha256"] == digest

            for service in ("api","db"):
                before=snapshot(); command(["restart",service]); ready()
                assert snapshot() == before
                verify_original(patient_path,first_id,FHIR_V1,1,"superseded")
                verify_original(patient_path,second_id,FHIR_V2,2,"current")
                verify_world(patient_path,second_id,"5.00",1)
                verify_questions(questions, versions, patient)
                tasks.verify_history(stale={historical_task})
                tasks.replay()

                verify_citation(first_cite, "source_reassessment_required")
                verify_citation(second_cite, "current_unreviewed_question")

            withdraw_fixture_rights()
            verify_citation(second_cite, "current_unreviewed_question", restricted=True)
            before_restore=restore("oi_api_synthetic",RESTORED)
            verify_original(patient_path,first_id,FHIR_V1,1,"superseded")
            verify_original(patient_path,second_id,FHIR_V2,2,"current")
            verify_world(patient_path,second_id,"5.00",1)
            assert request(endpoint,body(FHIR_V2,"FHIR-LAB-AMEND-1",first_id)) == (
                200,{**second,"duplicate":True})
            # A restored read must commit its new receipt in the restored DB only.
            receipt = verify_questions(questions, versions, patient)
            receipts_sql = """SELECT COALESCE(json_agg(metadata_json->>'receipt_id'),'[]'::json)
                             FROM identity.identity_domain_events WHERE event_type='source.read_authorized'"""
            assert receipt in query(receipts_sql, RESTORED) and receipt not in query(receipts_sql)
            task_read = tasks.verify_history(stale={historical_task})
            assert task_read in query(receipts_sql, RESTORED) and task_read not in query(receipts_sql)
            tasks.replay()
            tasks.reject_stale(historical_task)
            first_read = verify_citation(first_cite, "source_reassessment_required")
            second_read = verify_citation(second_cite, "current_unreviewed_question", restricted=True)
            assert {first_read, second_read} <= set(query(receipts_sql, RESTORED))
            assert {first_read, second_read}.isdisjoint(query(receipts_sql))
            old_links, current_links = first_cite["path"] + "/evidence-links", second_cite["path"] + "/evidence-links"
            assert request(old_links, first_cite["payload"]) == (200, {**first_cite["receipt"], "duplicate": True})
            assert request(old_links, {**first_cite["payload"], "request_key": "NEW-STALE-CITATION"})[0] == 409
            assert request(current_links, second_cite["payload"])[0] == 404
            status, hidden = request(second_cite["path"] + "/evidence-search",
                                     {"synthetic": True, "query": second_cite["term"]})
            assert status == 200 and hidden["records"] == []

            for _, saved_command, saved, _ in versions:
                assert request(questions, saved_command) == (200, {**saved, "duplicate": True})
            assert request(questions, {**cmd1, "request_key": "STALE-RESTORED-CONTEXT"})[0] == 409
            after_reads = snapshot(RESTORED)
            assert {k: v for k, v in after_reads.items() if k != "sequence_state"} == {
                k: v for k, v in before_restore.items() if k != "sequence_state"}
            assert snapshot() == before_restore, "Restored HTTP changed the original database"

            # A new question/link exercises INSERT guards on the restored copy;
            # replaying an existing citation alone would bypass those guards.
            restored_cmd, restored_question = save_question(
                case_path, second, second_fingerprint, "LAB-QUESTION-RESTORED-NEW",
                "Which source supports this newly saved fictional laboratory question?")
            restored_cite = cite(questions, restored_question, second, restored_cmd,
                                 "continuity", "FICT-RECORD-CONTINUITY@1", "CITE-RESTORED-NEW")
            restored_task = tasks.create(second, restored_question, restored_cmd, "LAB-TASK-RESTORED-NEW")
            tasks.transition(restored_task, "assigned")
            tasks.transition(restored_task, "acknowledged")
            tasks.verify_history(stale={historical_task})
            inserted = snapshot(RESTORED)
            tasks.verify_storage(inserted)
            assert len(inserted["citations"]) == len(inserted["citation_anchors"]) == 3
            assert inserted["source_import_events"] == before_restore["source_import_events"]
            new_question_event, = [event for event in inserted["question_events"]
                                  if event["metadata_json"]["question_id"] == restored_question["question_id"]]
            assert new_question_event["id"] > max(event["id"] for event in before_restore["question_events"])
            independent = ("OI-SYNTHETIC-REPORT/1\nPatient: " + CASE +
                           "\nDocument: RESTORED-INDEPENDENT\nType: pathology\n"
                           "Event-Date: 2026-05-04\nIssued-At: 2026-05-05\n"
                           "Specimen: RESTORED-FICTIONAL-SPECIMEN\n"
                           "Finding: marker|pending|An independent fictional assay is pending.\n")
            status, imported = request(case_path + "/sources", {
                "synthetic": True, "original_text": independent})
            assert status == 201 and imported["duplicate"] is False
            changed = snapshot(RESTORED)
            new_import, = [event for event in changed["source_import_events"]
                           if event["metadata_json"]["source_id"] == imported["source_id"]]
            assert new_import["id"] > new_question_event["id"]
            assert request(restored_cite["path"] + "/evidence-links", {
                **restored_cite["payload"], "request_key": "CITE-RESTORED-STALE-NEW"})[0] == 409
            assert snapshot(RESTORED) == changed, "Rejected stale citation committed state or a receipt"
            tasks.reject_stale(restored_task)
            assert snapshot(RESTORED) == changed, "Refused stale task write committed state or a receipt"
            tasks.verify_history(stale={historical_task, current_task, restored_task})
            verify_citation(restored_cite, "source_reassessment_required")
            assert snapshot() == before_restore, "Restored writes changed the original database"

            status, revoked = request(patient_path+"/case-bindings/"+CASE+"/revoke",{
                "synthetic":True,"reason":"Fictional FHIR mapping withdrawn after restore"})
            assert status == 200 and revoked["case_id"] == CASE
            # Back up the revoked DB and point a fresh API at this second restore.
            # The credential keeps all original grants; the restored binding itself must deny.
            banned = restore(RESTORED, REVOKED_RESTORE)
            assert banned["bindings"][0]["status"] == "revoked"
            before_receipts = query(receipts_sql, REVOKED_RESTORE)
            for path,payload in (
                (questions, None), (questions, cmd1), (questions, cmd2),
                (old_links, None), (old_links, first_cite["payload"]),
                (current_links, None), (current_links, second_cite["payload"]),
                (first_cite["path"] + "/evidence-search", {"synthetic": True, "query": first_cite["term"]}),
                (patient_path+"/cases/"+CASE+"/world-model",None),
                (patient_path+"/cases/"+CASE+"/sources/"+second_id,None),
                (endpoint,body(FHIR_V2,"FHIR-LAB-AFTER-REVOKE",second_id)),
            ):
                assert request(path,payload)[0] == 404
            tasks.verify_revoked()
            assert snapshot(REVOKED_RESTORE) == banned
            assert sorted(query(receipts_sql, REVOKED_RESTORE)) == sorted(before_receipts)
            print("PASS LABORATORY FOLLOWTHROUGH RECOVERY: task origins, observation references and full "
                  "attributed history survived API/DB restarts and pg_dump/pg_restore. Both HTTP list versions, "
                  "exact retries, restored-only reads and new writes, stale completion refusal and revoked "
                  "binding denial verified on the databases actually served.")
            print("PASS LABORATORY CITATION RECOVERY: two immutable observation-bound citations, "
                  "permitted historical replay with the same link ID, restricted title withheld, "
                  "restored new citation insert and independent-import stale refusal, import receipts and sequences, "
                  "and revoked restored binding denied citation search, history and replay.")
            print("PASS FHIR LABORATORY RECOVERY: exact source versions, typed observations and "
                  "both durable question anchors survived API/DB restart and pg_dump/pg_restore; "
                  "historical/current retries preserved IDs and fresh read receipt was restore-local; "
                  "second restored revoked binding denied original, history and both retries. "
                  "Source-reported only, no clinical interpretation.")
        finally:
            command(["down","--volumes","--remove-orphans"],check=False,
                    stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)


if __name__ == "__main__":
    main()
