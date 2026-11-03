"""Actual PostgreSQL 16 acceptance: first-party source custody over case binding.

All originals are independently authored fictional reports, not medical files.
"""
import hashlib
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
from test_patients import TOKEN_A, TOKEN_B, request, credential


ORIGINAL = (
    "OI-SYNTHETIC-REPORT/1\nPatient: CASE-ALPHA\nDocument: DOC-ONE\n"
    "Type: pathology\nEvent-Date: 2026-01-10\nIssued-At: 2026-01-11\n"
    "Specimen: SPECIMEN-ONE\n"
    "Finding: marker|not-reported|Fictional café <script>literal</script>.\n"
)
AMENDED = (
    "OI-SYNTHETIC-REPORT/1\nPatient: CASE-ALPHA\nDocument: DOC-ONE\n"
    "Type: pathology\nEvent-Date: 2026-01-10\nIssued-At: 2026-01-12\n"
    "Specimen: SPECIMEN-ONE\nAmends: DOC-ONE@1\n"
    "Finding: marker|negative|Amended fictional marker is reported negative.\n"
)
DIFFERENT = (
    "OI-SYNTHETIC-REPORT/1\nPatient: CASE-BETA\nDocument: DOC-TWO\n"
    "Type: imaging\nEvent-Date: 2026-02-01\nIssued-At: 2026-02-02\n"
    "Finding: image|pending|No imaging conclusion has been reported.\n"
)


@unittest.skipUnless(os.environ.get("OI_API_RUN_DATABASE_TESTS") == "1",
                     "Requires a disposable actual PostgreSQL 16 test database")
class SourceVersionFixture(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        url = os.environ.get("OI_API_TEST_DATABASE_URL", "")
        if not (make_url(url).database or "").startswith("oi_api_test_"):
            raise RuntimeError("Source tests require disposable oi_api_test_ database")
        cls.admin = Settings(database_url=url)
        cls.engine = make_engine(cls.admin)
        with cls.engine.connect() as c:
            if int(c.execute(text("SHOW server_version_num")).scalar_one()) // 10000 != 16:
                raise RuntimeError("Actual PostgreSQL 16 required")

    @classmethod
    def tearDownClass(cls):
        cls.engine.dispose()

    def setUp(self):
        with self.engine.begin() as c:
            c.execute(text("DROP SCHEMA IF EXISTS clinical_source CASCADE"))
            c.execute(text("DROP SCHEMA IF EXISTS coordination CASCADE"))
            c.execute(text("DROP SCHEMA IF EXISTS identity CASCADE"))
            c.execute(text("DROP TABLE IF EXISTS public.alembic_version"))
        migrate(self.admin, "upgrade", "head")
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.access = Path(self.temp.name) / "access.json"
        self.creds = [
            credential(TOKEN_A, actions=(
                "patient_create", "patient_read", "case_binding_create",
                "case_binding_read", "case_binding_revoke",
                "source_import", "source_read", "source_original_read")),
            credential(TOKEN_B, organization="ORG-BETA", actor="ACTOR-BETA",
                       actions=("patient_create", "patient_read", "case_binding_create",
                                "source_import", "source_read", "source_original_read")),
        ]
        self.write()
        self.settings = Settings.from_env({
            "OI_API_DATABASE_URL": self.admin.database_url,
            "OI_API_ACCESS_FILE": str(self.access),
        })

    def tearDown(self):
        with self.engine.begin() as c:
            c.execute(text("DROP SCHEMA IF EXISTS clinical_source CASCADE"))
            c.execute(text("DROP SCHEMA IF EXISTS coordination CASCADE"))
            c.execute(text("DROP SCHEMA IF EXISTS identity CASCADE"))
            c.execute(text("DROP TABLE IF EXISTS public.alembic_version"))

    def write(self):
        temp = self.access.with_suffix(".tmp")
        temp.write_text(json.dumps({"version": "oi.synthetic-access/1",
                                    "credentials": self.creds}))
        temp.replace(self.access)

    def setup_case(self, base, *, token=TOKEN_A, case="CASE-ALPHA", key="CREATE-ALPHA",
                   source_subject="SUBJECT-ALPHA"):
        status, p, _ = request(base, "/v1/patients", token=token,
                               body={"synthetic": True, "request_key": key})
        self.assertEqual(status, 201)
        pid = p["patient_id"]
        digest = hashlib.sha256(token.encode()).hexdigest()
        for item in self.creds:
            if item["token_sha256"] == digest:
                item["patient_ids"].append(pid)
        self.write()
        status, mapped, _ = request(base, f"/v1/patients/{pid}/case-bindings",
                                    token=token, body={
            "synthetic": True, "case_id": case,
            "source_organization": "ORG-INSTITUTION", "source_system": "SYS-SYNTH",
            "source_subject_ref": source_subject, "review_ref": "REVIEW-SYNTH"
        })
        self.assertEqual((status, mapped["case_id"]), (201, case))
        return pid

    def url(self, pid, case="CASE-ALPHA"):
        return f"/v1/patients/{pid}/cases/{case}/sources"

    def ingest(self, base, pid, raw=ORIGINAL, *, case="CASE-ALPHA", token=TOKEN_A, **extra):
        return request(base, self.url(pid, case), token=token,
                       body={"synthetic": True, "original_text": raw, **extra})


class SourceVersionHTTPTests(SourceVersionFixture):
    def test_exact_bytes_amendment_assertions_and_restart(self):
        with running_server(create_app(self.settings)) as base:
            patient = self.setup_case(base)
            status, first, _ = self.ingest(base, patient)
            self.assertEqual((status, first["result"], first["version"]), (201, "imported", 1))
            self.assertEqual(self.ingest(base, patient)[:2], (200, {
                "result": "duplicate", "duplicate": True,
                "source_id": first["source_id"], "version": 1,
            }))
            status, index, _ = request(base, self.url(patient), token=TOKEN_A)
            self.assertEqual(status, 200)
            self.assertEqual(len(index["sources"]), 1)
            self.assertEqual(len(index["source_reported_assertions"]), 1)
            self.assertEqual(index["source_reported_assertions"][0]["source_line"], 8)
            self.assertEqual(index["source_reported_assertions"][0]["reported_state"], "not-reported")
            self.assertFalse(index["clinical_interpretation"])
            self.assertFalse(index["research_review_invalidation_integrated"])
            original_url = self.url(patient) + "/" + first["source_id"]
            status, original, _ = request(base, original_url, token=TOKEN_A)
            self.assertEqual((status, original["original_text"]), (200, ORIGINAL))
            self.assertEqual(original["sha256"], hashlib.sha256(ORIGINAL.encode()).hexdigest())
            self.assertEqual(self.ingest(base, patient, AMENDED)[0], 201)
            _, after, _ = request(base, self.url(patient), token=TOKEN_A)
            self.assertEqual([r["state"] for r in after["sources"]],
                             ["superseded", "current"])
            self.assertEqual(after["sources"][1]["supersedes_id"], first["source_id"])
            self.assertEqual(after["source_reported_assertions"][0]["reported_state"], "negative")
            self.assertEqual(after["source_reported_assertions"][0]["source_line"], 9)
            self.assertEqual(request(base, original_url, token=TOKEN_A)[1]["original_text"], ORIGINAL)
        with running_server(create_app(self.settings)) as restarted:
            self.assertEqual(request(restarted, self.url(patient), token=TOKEN_A)[1]["sources"][0]["sha256"],
                             hashlib.sha256(ORIGINAL.encode()).hexdigest())
        with self.engine.connect() as c:
            kinds = c.execute(text("SELECT event_type FROM identity.identity_domain_events "
                                   "WHERE patient_id=:p ORDER BY id"),
                              {"p": patient}).scalars().all()
            self.assertEqual(kinds, ["identity.patient.created", "identity.case_binding_created",
                                     "source.original.imported", "source.read_authorized",
                                     "source.original_read_authorized", "source.original.imported",
                                     "source.read_authorized", "source.original_read_authorized",
                                     "source.read_authorized"])
            self.assertEqual(c.execute(text("SELECT count(*) FROM clinical_source.assertions")).scalar_one(), 2)

    def test_mismatched_case_quarantines_original_without_placing_assertions(self):
        with running_server(create_app(self.settings)) as base:
            pid = self.setup_case(base)
            status, wrong, _ = self.ingest(base, pid, DIFFERENT)
            self.assertEqual((status, wrong["result"], wrong["source_id"]), (200, "quarantined", None))
            self.assertTrue(self.ingest(base, pid, DIFFERENT)[1]["duplicate"])
            _, index, _ = request(base, self.url(pid), token=TOKEN_A)
            self.assertEqual(index["sources"], [])
            self.assertEqual(index["source_reported_assertions"], [])
            with self.engine.connect() as c:
                self.assertEqual(c.execute(text("SELECT count(*) FROM clinical_source.quarantine")).scalar_one(), 1)
                self.assertEqual(c.execute(text("SELECT count(*) FROM clinical_source.assertions")).scalar_one(), 0)
                self.assertEqual(c.execute(text("SELECT raw FROM clinical_source.quarantine")).scalar_one(), DIFFERENT.encode())

    def test_version_collision_wrong_amendment_and_specimen_change_are_rejected(self):
        with running_server(create_app(self.settings)) as base:
            pid = self.setup_case(base)
            self.ingest(base, pid)
            wrong = ORIGINAL.replace("Fictional café", "Changed café")
            self.assertEqual(self.ingest(base, pid, wrong)[0], 409)
            self.assertEqual(self.ingest(base, pid, AMENDED.replace("SPECIMEN-ONE", "SPECIMEN-OTHER"))[0], 409)
            self.assertEqual(self.ingest(base, pid, AMENDED.replace("DOC-ONE@1", "DOC-ONE@2"))[0], 409)
            self.assertEqual(request(base, self.url(pid), token=TOKEN_A)[1]["sources"][0]["state"], "current")

    def test_wrong_patient_and_independent_source_read_grants(self):
        with running_server(create_app(self.settings)) as base:
            a = self.setup_case(base)
            b = self.setup_case(base, token=TOKEN_B, case="CASE-BETA",
                                key="CREATE-BETA", source_subject="SUBJECT-BETA")
            self.assertEqual(self.ingest(base, b, case="CASE-ALPHA", token=TOKEN_B)[0], 404)
            self.assertEqual(self.ingest(base, a, case="CASE-BETA")[0], 404)
            self.assertEqual(self.ingest(base, a)[0], 201)
            _, index, _ = request(base, self.url(a), token=TOKEN_A)
            sid = index["sources"][0]["source_id"]
            self.assertEqual(request(base, self.url(a) + "/" + sid, token=TOKEN_B)[0], 404)
            self.creds[0]["actions"].remove("source_original_read")
            self.write()
            self.assertEqual(request(base, self.url(a) + "/" + sid, token=TOKEN_A)[0], 404)
            self.assertEqual(request(base, self.url(a), token=TOKEN_A)[0], 200)
            self.creds[0]["actions"].remove("source_import")
            self.write()
            self.assertEqual(self.ingest(base, a, AMENDED)[0], 404)
            self.assertEqual(request(base, self.url(a), token=TOKEN_A)[0], 200)

    def test_binding_revocation_denies_all_source_views_and_writes(self):
        with running_server(create_app(self.settings)) as base:
            p = self.setup_case(base)
            sid = self.ingest(base, p)[1]["source_id"]
            _, cancelled, _ = request(base,
                f"/v1/patients/{p}/case-bindings/CASE-ALPHA/revoke", token=TOKEN_A,
                body={"synthetic": True, "reason": "Fictional mapping is withdrawn"})
            self.assertEqual(cancelled["case_id"], "CASE-ALPHA")
            self.assertEqual(request(base, self.url(p), token=TOKEN_A)[0], 404)
            self.assertEqual(request(base, self.url(p) + "/" + sid, token=TOKEN_A)[0], 404)
            self.assertEqual(self.ingest(base, p, AMENDED)[0], 404)

    def test_source_event_failure_rolls_back_bytes_and_assertions(self):
        with running_server(create_app(self.settings)) as base:
            pid = self.setup_case(base)
            with self.engine.begin() as c:
                c.exec_driver_sql("""CREATE FUNCTION identity.fail_source_event() RETURNS trigger
                    LANGUAGE plpgsql AS $$ BEGIN
                      IF NEW.event_type='source.original.imported' THEN
                        RAISE EXCEPTION 'AUTHORED-SOURCE-FAILURE'; END IF;
                      RETURN NEW; END; $$;""")
                c.exec_driver_sql("CREATE TRIGGER fail_source_event BEFORE INSERT "
                                  "ON identity.identity_domain_events FOR EACH ROW "
                                  "EXECUTE FUNCTION identity.fail_source_event()")
            code, data, _ = self.ingest(base, pid)
            self.assertEqual(code, 503)
            self.assertEqual(data, {"detail": "Patient registry unavailable"})
            self.assertEqual(request(base, self.url(pid), token=TOKEN_A)[1]["sources"], [])
            with self.engine.begin() as c:
                self.assertEqual(c.execute(text("SELECT count(*) FROM clinical_source.assertions")).scalar_one(), 0)
                c.exec_driver_sql("DROP TRIGGER fail_source_event ON identity.identity_domain_events")
                c.exec_driver_sql("DROP FUNCTION identity.fail_source_event()")

    def test_database_immutability_blocks_rewriting_original_bytes_and_assertions(self):
        with running_server(create_app(self.settings)) as base:
            pid = self.setup_case(base)
            self.ingest(base, pid)
            for query in (
                "DELETE FROM clinical_source.source_versions",
                "UPDATE clinical_source.source_versions SET raw=decode('78','hex')",
                "UPDATE clinical_source.assertions SET quote='forged'",
                "DELETE FROM clinical_source.assertions",
            ):
                with self.subTest(query=query), self.assertRaises(Exception):
                    with self.engine.begin() as c:
                        c.execute(text(query))
            self.assertEqual(request(base, self.url(pid), token=TOKEN_A)[1]["sources"][0]["state"], "current")


if __name__ == "__main__":
    unittest.main()
