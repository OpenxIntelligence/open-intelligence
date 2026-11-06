"""Synthetic animal/case identity, checked independently of human grants."""
from concurrent.futures import ThreadPoolExecutor
import os
import unittest
from unittest.mock import patch

from alembic.util.exc import CommandError
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError

from http_support import running_server
from oi_api.app import create_app
from oi_api.config import Settings
from oi_api.database import Database
from oi_api.migrate import migrate
import test_patients as human

ROOT = "/v1/veterinary/animals"
ANIMAL = {"synthetic": True, "species": "dog", "source_system": "SYN-CLINIC",
          "source_subject_ref": "SYN-ANIMAL-A", "request_key": "REGISTER-A"}
CASE = {"synthetic": True, "request_key": "OPEN-CASE-A"}
ACTIONS = ["animal_register", "animal_read", "veterinary_case_open", "veterinary_case_read"]


class VeterinaryAccessTests(unittest.TestCase):
    def test_human_grants_do_not_open_veterinary_database(self):
        from oi_api.access import Principal
        grant = human.credential(human.TOKEN_A)
        grant.pop("token_sha256")
        policy = unittest.mock.Mock()
        policy.authenticate.return_value = Principal.model_validate(grant)
        with patch.object(Database, "registry_connection") as db:
            with running_server(create_app(Settings.from_env({}), authentication=policy)) as base:
                self.assertEqual(human.request(base, ROOT, token=human.TOKEN_A, body=ANIMAL)[0], 403)
            db.assert_not_called()


@unittest.skipUnless(os.environ.get("OI_API_RUN_DATABASE_TESTS") == "1", "Requires disposable PostgreSQL 16")
class VeterinaryRegistryTests(unittest.TestCase):
    # Borrow only database lifecycle and the atomic grant-file writer.
    setUpClass = classmethod(human.PatientHTTPTests.setUpClass.__func__)
    tearDownClass = classmethod(human.PatientHTTPTests.tearDownClass.__func__)
    setUp = human.PatientHTTPTests.setUp
    tearDown = human.PatientHTTPTests.tearDown
    save_credentials = human.PatientHTTPTests.save_credentials

    def grant(self, animals=(), actions=ACTIONS, **changes):
        self.credentials[0] = {**human.credential(human.TOKEN_A, actions=actions),
                               "animal_ids": list(animals), **changes}
        self.save_credentials()

    def test_registration_and_distinct_cases_survive_application_restart(self):
        self.grant()
        with running_server(create_app(self.settings)) as base:
            def register(_):
                return human.request(base, ROOT, token=human.TOKEN_A, body=ANIMAL)[:2]
            with ThreadPoolExecutor(max_workers=3) as pool:
                receipts = list(pool.map(register, range(3)))
            self.assertEqual(sorted(code for code, _ in receipts), [200, 200, 201])
            aid, = {body["animal_id"] for _, body in receipts}
            apath = ROOT + "/" + aid
            self.assertEqual(human.request(base, apath, token=human.TOKEN_A)[0], 404)
            for change in ({"species": "cat"}, {"request_key": "OTHER-REGISTRATION"}):
                self.assertEqual(human.request(base, ROOT, token=human.TOKEN_A, body={**ANIMAL, **change})[0], 409)
            self.grant([aid])
            self.assertEqual(human.request(base, apath, token=human.TOKEN_A)[1]["species"], "dog")
            self.assertEqual(human.request(base, "/v1/patients/"+aid, token=human.TOKEN_A)[0], 404)
            cases = apath + "/cases"
            status, first, _ = human.request(base, cases, token=human.TOKEN_A, body=CASE)
            self.assertEqual(status, 201)
            status, other, _ = human.request(base, cases, token=human.TOKEN_A, body={**CASE, "request_key": "OPEN-B"})
            self.assertEqual(status, 201)
            self.assertNotEqual(other["case_id"], first["case_id"])
        with running_server(create_app(self.settings)) as base:
            status, duplicate, _ = human.request(base, cases, token=human.TOKEN_A, body=CASE)
            self.assertEqual((status, duplicate), (200, {**first, "duplicate": True}))
            path = cases + "/" + first["case_id"]
            status, case, _ = human.request(base, path, token=human.TOKEN_A)
            self.assertEqual((status, case["species"], case["animal_id"]), (200, "dog", aid))
            for changes in ({"organization": "OTHER-ORG"}, {"animal_ids": []},
                            {"actions": ["animal_read"]}, {"actions": ["veterinary_case_read"]},
                            {"patient_ids": [aid], "animal_ids": []}):
                self.grant([aid], **changes)
                self.assertEqual(human.request(base, path, token=human.TOKEN_A)[:2],
                                 (404, {"detail": "Veterinary record unavailable"}))
        with self.engine.connect() as c:
            for table, count in (("identity.veterinary_animals", 1), ("coordination.veterinary_cases", 2),
                                 ("identity.identity_patients", 0), ("coordination.patient_case_bindings", 0)):
                self.assertEqual(c.execute(text("SELECT count(*) FROM " + table)).scalar_one(), count)
        with self.assertRaisesRegex(CommandError, "veterinary"):
            migrate(self.admin_settings, "downgrade", "0018_laboratory_questions")

    def test_animal_case_binding_is_immutable_and_subject_scoped(self):
        self.grant()
        with running_server(create_app(self.settings)) as base:
            ids = []
            for mark in ("ONE", "TWO"):
                payload = {**ANIMAL, "request_key": "KEY-" + mark, "source_subject_ref": "PET-" + mark}
                ids.append(human.request(base, ROOT, token=human.TOKEN_A, body=payload)[1]["animal_id"])
            self.grant(ids)
            cases = [ROOT + "/" + a + "/cases" for a in ids]
            first = human.request(base, cases[0], token=human.TOKEN_A, body=CASE)[1]["case_id"]
            self.assertEqual(human.request(base, cases[1]+"/"+first, token=human.TOKEN_A)[0], 404)
            self.assertEqual(human.request(base, cases[1], token=human.TOKEN_A, body=CASE)[0], 409)
            for changes in ({"species": "human"}, {"species": None}, {"synthetic": 1}, {"patient_id": "PAT-ONE"}):
                self.assertEqual(human.request(base, ROOT, token=human.TOKEN_A, body={**ANIMAL, **changes})[0], 422)
        for sql in ("UPDATE coordination.veterinary_cases SET animal_id=:other",
                    "DELETE FROM identity.veterinary_animals",
                    "UPDATE identity.veterinary_animals SET species='cat'"):
            with self.assertRaises(DBAPIError), self.engine.begin() as c:
                c.execute(text(sql), {"other": ids[1]})
