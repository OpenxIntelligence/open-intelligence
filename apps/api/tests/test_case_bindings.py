"""Real PostgreSQL 16 patient-to-case binding tests; fictional identifiers only."""
import json
import os
from pathlib import Path
import tempfile
import unittest
from sqlalchemy import text
from sqlalchemy.engine import make_url

from oi_api.app import create_app
from oi_api.config import Settings
from oi_api.database import make_engine
from oi_api.migrate import migrate
from http_support import running_server
from test_patients import request, credential, TOKEN_A, TOKEN_B


@unittest.skipUnless(os.environ.get("OI_API_RUN_DATABASE_TESTS") == "1",
                     "Requires actual disposable PostgreSQL 16 database")
class CaseBindingsTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        url = os.environ.get("OI_API_TEST_DATABASE_URL", "")
        if not (make_url(url).database or "").startswith("oi_api_test_"):
            raise RuntimeError("A disposable oi_api_test_ database is required")
        cls.admin_settings = Settings(database_url=url)
        cls.engine = make_engine(cls.admin_settings)
        with cls.engine.connect() as c:
            if int(c.execute(text("SHOW server_version_num")).scalar_one()) // 10000 != 16:
                raise RuntimeError("Actual PostgreSQL 16 is required")

    @classmethod
    def tearDownClass(cls):
        cls.engine.dispose()

    def setUp(self):
        with self.engine.begin() as c:
            c.execute(text("DROP SCHEMA IF EXISTS investigation CASCADE"))
            c.execute(text("DROP SCHEMA IF EXISTS clinical_source CASCADE"))
            c.execute(text("DROP SCHEMA IF EXISTS coordination CASCADE"))
            c.execute(text("DROP SCHEMA IF EXISTS identity CASCADE"))
            c.execute(text("DROP TABLE IF EXISTS public.alembic_version"))
        migrate(self.admin_settings, "upgrade", "head")
        self.dir = tempfile.TemporaryDirectory()
        self.addCleanup(self.dir.cleanup)
        self.file = Path(self.dir.name)/"tokens.json"
        actions = ("patient_create", "patient_read", "case_binding_create",
                   "case_binding_read", "case_binding_revoke")
        self.creds = [credential(TOKEN_A, actions=actions),
                      credential(TOKEN_B, organization="ORG-BETA",
                                 actor="ACTOR-BETA", actions=actions)]
        self.write()
        self.settings = Settings.from_env({
            "OI_API_DATABASE_URL": self.admin_settings.database_url,
            "OI_API_ACCESS_FILE": str(self.file),
        })

    def tearDown(self):
        with self.engine.begin() as c:
            c.execute(text("DROP SCHEMA IF EXISTS investigation CASCADE"))
            c.execute(text("DROP SCHEMA IF EXISTS clinical_source CASCADE"))
            c.execute(text("DROP SCHEMA IF EXISTS coordination CASCADE"))
            c.execute(text("DROP SCHEMA IF EXISTS identity CASCADE"))
            c.execute(text("DROP TABLE IF EXISTS public.alembic_version"))

    def write(self):
        target = self.file.with_suffix(".new")
        target.write_text(json.dumps({"version": "oi.synthetic-access/1", "credentials": self.creds}))
        target.replace(self.file)

    def patient(self, base, token=TOKEN_A, key="CREATE-CASE-ALPHA"):
        status, data, _ = request(base, "/v1/patients", token=token,
                                  body={"synthetic": True, "request_key": key})
        self.assertEqual(status, 201)
        patient_id = data["patient_id"]
        digest = __import__("hashlib").sha256(token.encode()).hexdigest()
        for item in self.creds:
            if item["token_sha256"] == digest:
                item["patient_ids"].append(patient_id)
        self.write()
        return patient_id

    def bind(self, base, patient_id, token=TOKEN_A, **changes):
        body = {"synthetic": True, "case_id": "CASE-ALPHA",
                "source_organization": "ORG-EXTERNAL",
                "source_system": "SYS-FICTION",
                "source_subject_ref": "SUBJECT-SYNTH-ONE",
                "review_ref": "REVIEW-FICTION-ONE"}
        body.update(changes)
        return request(base, "/v1/patients/"+patient_id+"/case-bindings",
                       token=token, body=body)

    def view(self, base, patient_id, token=TOKEN_A):
        return request(base, "/v1/patients/"+patient_id+"/case-bindings", token=token)

    def test_durable_binding_retries_revoke_and_no_rebind(self):
        with running_server(create_app(self.settings)) as base:
            pid = self.patient(base)
            status, first, _ = self.bind(base, pid)
            self.assertEqual((status,first["duplicate"],first["source_identity_verified"]),
                             (201,False,False))
            self.assertEqual(self.bind(base,pid)[:2],(200,first|{"duplicate":True}))
            rows = self.view(base,pid)[1]["mappings"]
            self.assertEqual(len(rows),1)
            self.assertEqual(rows[0]["case_id"],"CASE-ALPHA")
            self.assertFalse(rows[0]["clinical_sources_linked"])
            self.assertFalse(rows[0]["source_identity_verified"])
            url = "/v1/patients/"+pid+"/case-bindings/CASE-ALPHA/revoke"
            data = {"synthetic":True, "reason":"Withdraw fictional case mapping"}
            self.assertEqual(request(base,url,token=TOKEN_A,body=data)[0],200)
            self.assertTrue(request(base,url,token=TOKEN_A,body=data)[1]["duplicate"])
        with running_server(create_app(self.settings)) as again:
            item = self.view(again,pid)[1]["mappings"][0]
            self.assertEqual((item["status"],item["revision"]),("revoked",2))
            self.assertEqual(self.bind(again,pid)[0],409)
        with self.engine.connect() as c:
            events=c.execute(text("SELECT event_type FROM identity.identity_domain_events WHERE patient_id=:p ORDER BY id"),
                             {"p":pid}).scalars().all()
            self.assertEqual(events,["identity.patient.created",
                                     "identity.case_binding_created",
                                     "identity.case_binding_revoked"])

    def test_strict_patient_org_case_and_action_isolation(self):
        with running_server(create_app(self.settings)) as base:
            a=self.patient(base)
            b=self.patient(base,TOKEN_B,"CREATE-CASE-BETA")
            self.assertEqual(self.bind(base,b,token=TOKEN_A)[0],404)
            self.assertEqual(self.bind(base,a,token=TOKEN_B)[0],404)
            self.assertEqual(self.view(base,a,token=TOKEN_B)[0],404)
            self.creds[0]["actions"]=["patient_create","patient_read","case_binding_read"]
            self.write()
            self.assertEqual(self.bind(base,a)[0],404)
            self.assertEqual(self.view(base,a)[0],200)
            self.creds[0]["actions"]=["patient_create","case_binding_create"]
            self.write()
            self.assertEqual(self.bind(base,a)[0],404)
            self.creds[0]["actions"]=["patient_create","patient_read","case_binding_create"]
            self.creds[0]["patient_ids"]=[]
            self.write()
            self.assertEqual(self.bind(base,a)[0],404)
        with self.engine.connect() as c:
            self.assertEqual(c.execute(text("SELECT count(*) FROM coordination.patient_case_bindings")).scalar_one(),0)

    def test_conflicting_fictional_identifiers_cannot_merge_subjects(self):
        with running_server(create_app(self.settings)) as base:
            a=self.patient(base)
            second=self.patient(base,key="CREATE-OTHER-ALPHA")
            self.assertEqual(self.bind(base,a)[0],201)
            self.assertEqual(self.bind(base,second,case_id="CASE-ALPHA")[0],409)
            self.assertEqual(self.bind(base,second,case_id="CASE-BETA")[0],409)
            self.assertEqual(self.bind(base,a,case_id="CASE-ALPHA",
                                       source_subject_ref="SUBJECT-DIFFERENT")[0],409)
            self.assertEqual(self.bind(base,a,case_id="CASE-BETA",
                                       source_subject_ref="SUBJECT-DIFFERENT")[0],201)
        with self.engine.connect() as c:
            self.assertEqual(c.execute(text("SELECT count(*) FROM coordination.patient_case_bindings")).scalar_one(),2)

    def test_real_data_fields_invalid_and_source_routes_unavailable(self):
        with running_server(create_app(self.settings)) as base:
            p=self.patient(base)
            for bad in ({"synthetic":False},{"synthetic":1},{"actor":"PRIVATE"},
                        {"case_id":"CASE-OTHER?"},
                        {"source_subject_ref":" "},
                        {"review_ref":"test\nforged"}):
                with self.subTest(bad=bad):
                    status,body,_=self.bind(base,p,**bad)
                    self.assertEqual(status,422)
                    self.assertNotIn("PRIVATE",json.dumps(body))
            self.assertEqual(request(base,"/v1/patients/"+p+"/cases/CASE-ALPHA/sources",
                                     token=TOKEN_A)[0],404)
            self.assertEqual(self.view(base,p)[1]["mappings"],[])

    def test_database_guards_and_event_failures_rollback_binding(self):
        with running_server(create_app(self.settings)) as base:
            p=self.patient(base)
            self.assertEqual(self.bind(base,p)[0],201)
            for sql in ("DELETE FROM coordination.patient_case_bindings",
                        "UPDATE coordination.patient_case_bindings SET patient_id='PAT-FORGED'",
                        "UPDATE coordination.patient_case_bindings SET status='revoked',revision=5"):
                with self.subTest(sql=sql),self.assertRaises(Exception):
                    with self.engine.begin() as c: c.execute(text(sql))
            with self.engine.begin() as c:
                c.exec_driver_sql("""CREATE FUNCTION identity.fail_case_event() RETURNS trigger
                    LANGUAGE plpgsql AS $$
                    BEGIN IF NEW.event_type='identity.case_binding_revoked' THEN
                    RAISE EXCEPTION 'AUTHORED-CASE-ROLLBACK'; END IF; RETURN NEW; END; $$;""")
                c.exec_driver_sql("CREATE TRIGGER fail_case_event BEFORE INSERT ON identity.identity_domain_events "
                                  "FOR EACH ROW EXECUTE FUNCTION identity.fail_case_event()")
            url="/v1/patients/"+p+"/case-bindings/CASE-ALPHA/revoke"
            status,_,_=request(base,url,token=TOKEN_A,body={
                "synthetic":True,"reason":"Fictional rejected audit transition"})
            self.assertEqual(status,503)
            self.assertEqual(self.view(base,p)[1]["mappings"][0]["status"],"active")
            with self.engine.begin() as c:
                c.exec_driver_sql("DROP TRIGGER fail_case_event ON identity.identity_domain_events")
                c.exec_driver_sql("DROP FUNCTION identity.fail_case_event()")
                self.assertEqual(c.execute(text("SELECT count(*) FROM identity.identity_domain_events "
                                                "WHERE event_type='identity.case_binding_revoked'")).scalar_one(),0)
