"""Connected first-party EHR with fictional records and current request grants."""
import unittest
from unittest.mock import patch

from sqlalchemy import text

from oi_api.app import create_app
from oi_api.config import Settings
from http_support import running_server
from test_patients import TOKEN_A, TOKEN_B, request
from test_source_versions import SourceVersionFixture


class EncounterSurfaceTests(unittest.TestCase):
    def test_operational_routes_are_registered_and_require_credentials(self):
        app = create_app(Settings.from_env({}))
        prefix = "/v1/patients/{patient_id}/encounters"
        expected = {("/events", "get"), ("", "get"), ("", "post"), ("/{encounter_id}/notes", "get"), ("/{encounter_id}/transitions", "post"),
                    ("/{encounter_id}/notes/{note_key}/versions", "post"),
                    ("/{encounter_id}/notes/{note_key}/versions", "get")}
        for suffix, verb in expected:
            with self.subTest(suffix=suffix, verb=verb):
                op = app.openapi()["paths"][prefix + suffix][verb]
                self.assertEqual(op["security"], [{"SyntheticFixture": []}])
        with running_server(app) as base:
            self.assertEqual(request(base, "/v1/patients/PAT-TEST/encounters")[0], 401)


class EncounterHTTPTests(SourceVersionFixture):
    def setUp(self):
        super().setUp()
        self.creds[0]["actions"].extend(["encounter.read", "encounter.schedule", "encounter.transition",
                                        "note.read", "note.write"])
        self.write()

    schedule = {"synthetic": True, "request_key": "SCHEDULE-ONE", "external_key": "VISIT-ONE",
                "kind": "outpatient", "service_date": "2026-05-04"}

    def test_retries_revisions_history_and_independent_read_permissions(self):
        with running_server(create_app(self.settings)) as base:
            patient = self.setup_case(base)
            url = f"/v1/patients/{patient}/encounters"
            def post(path, payload):
                return request(base, path, token=TOKEN_A, body=payload)
            first = post(url, self.schedule)
            self.assertEqual(first[0], 200)
            self.assertEqual(post(url, self.schedule)[:2], first[:2])
            self.assertEqual(post(url, dict(self.schedule, service_date="2026-06-15"))[0], 409)
            visit = url + "/" + str(first[1]["encounter_id"])
            note = visit + "/notes/NOTE-ONE/versions"
            draft = {"synthetic": True, "request_key": "WRITE-ONE", "expected_version": 0,
                     "body": "Fictional consultation draft.", "note_kind": "consultation"}
            self.assertEqual(post(note, draft)[0], 409)
            move = {"synthetic": True, "request_key": "START-ONE", "target": "in_progress", "expected_revision": 1}
            self.assertEqual(post(visit + "/transitions", move)[1]["revision"], 2)
            self.assertEqual(post(visit + "/transitions", dict(move, request_key="STALE-ONE"))[0], 409)
            self.assertEqual(post(note, draft)[1]["version"], 1)
            self.assertEqual(post(note, dict(draft, request_key="WRITE-TWO", expected_version=1,
                                            body="Revised fictional draft."))[1]["version"], 2)
            self.assertEqual(post(note, dict(draft, request_key="STALE-NOTE"))[0], 409)
            history = request(base, note, token=TOKEN_A)[1]["versions"]
            self.assertEqual([v["body"] for v in history], [draft["body"], "Revised fictional draft."])
            self.assertEqual(history[1]["supersedes_id"], history[0]["id"])
            self.assertTrue(all(v["status"] == "draft" for v in history))
            self.assertEqual(request(base, url, token=TOKEN_A)[1]["encounters"][0]["revision"], 2)
            index = request(base, visit + "/notes", token=TOKEN_A)[1]
            self.assertEqual([(x["note_key"], x["latest_version"]) for x in index["notes"]], [("NOTE-ONE", 2)])
            page = request(base, note + "?limit=1", token=TOKEN_A)[1]
            self.assertEqual(page["next_after_version"], 1)
            self.assertEqual([v["version"] for v in request(base, note + "?after_version=1", token=TOKEN_A)[1]["versions"]], [2])
            self.creds[1]["actions"].extend(["note.read", "encounter.read"])
            self.creds[1]["patient_ids"].append(patient)
            self.write()
            self.assertEqual(request(base, note, token=TOKEN_B)[0], 404)
            events = url + "/events"
            self.assertEqual(request(base, events, token=TOKEN_A)[0], 404)
            self.creds[0]["actions"].append("encounter.events.read")
            self.write()
            seen = request(base, events + "?limit=2", token=TOKEN_A)[1]
            self.assertEqual([e["event_type"] for e in seen["events"]],
                             ["clinical_encounter_scheduled", "clinical_encounter_state_changed"])
            later = request(base, events + "?after_id=" + str(seen["resume_after_id"]), token=TOKEN_A)[1]
            self.assertEqual([e["note_version"] for e in later["events"]], [1, 2])
            self.assertTrue(all(e["note_key"] == "NOTE-ONE" for e in later["events"]))
            self.assertNotIn(draft["body"], str(later))
            self.assertTrue(seen["has_more"])
            self.assertFalse(later["has_more"])
            empty = request(base, events + "?after_id=" + str(later["resume_after_id"]), token=TOKEN_A)[1]
            self.assertEqual((empty["events"], empty["resume_after_id"]), ([], later["resume_after_id"]))
            self.creds[0]["actions"].remove("note.read")
            self.write()
            self.assertEqual(request(base, note, token=TOKEN_A)[0], 404)
            self.assertEqual(request(base, events, token=TOKEN_A)[0], 404)
            self.assertEqual(request(base, url, token=TOKEN_A)[0], 200)

    def test_note_read_withdrawn_during_serialization_discloses_nothing(self):
        from oi_api.encounter_routes import NoteHistory
        with running_server(create_app(self.settings)) as base:
            patient = self.setup_case(base)
            url = f"/v1/patients/{patient}/encounters"
            visit = request(base, url, token=TOKEN_A, body=self.schedule)[1]["encounter_id"]
            url += f"/{visit}/notes/NOTE-ONE/versions"
            original = NoteHistory.model_dump
            def revoke(model, **kwargs):
                rendered = original(model, **kwargs)
                self.creds[0]["actions"].remove("note.read")
                self.write()
                return rendered
            with patch.object(NoteHistory, "model_dump", revoke):
                status, body, _ = request(base, url, token=TOKEN_A)
            self.assertEqual(status, 404)
            self.assertNotIn("versions", body)
        with self.engine.connect() as conn:
            self.assertEqual(conn.execute(text("SELECT count(*) FROM identity.identity_domain_events "
                "WHERE event_type='clinical_encounter_read_authorized'")).scalar_one(), 0)

    def test_populated_encounter_history_refuses_downgrade(self):
        from alembic.util.exc import CommandError
        from oi_api.migrate import migrate
        with running_server(create_app(self.settings)) as base:
            patient = self.setup_case(base)
            url = f"/v1/patients/{patient}/encounters"
            self.assertEqual(request(base, url, token=TOKEN_A, body=self.schedule)[0], 200)
            with self.assertRaisesRegex(CommandError, "Populated encounter"):
                migrate(self.admin, "downgrade", "0018_laboratory_questions")
            self.assertEqual(request(base, url, token=TOKEN_A)[1]["encounters"][0]["external_key"], "VISIT-ONE")

    def test_authority_loss_after_receipt_insert_rolls_back_every_owner(self):
        from open_intelligence.postgres_encounters import PostgresClinicalEncounters
        original = PostgresClinicalEncounters._execute
        def revoke(owner, statement, parameters=()):
            result = original(owner, statement, parameters)
            if "INSERT INTO clinical_encounter_commands" in statement:
                self.creds[0]["actions"].remove("encounter.schedule")
                self.write()
            return result
        with running_server(create_app(self.settings)) as base:
            patient = self.setup_case(base)
            with patch.object(PostgresClinicalEncounters, "_execute", revoke):
                status, _, _ = request(base, f"/v1/patients/{patient}/encounters",
                                       token=TOKEN_A, body=self.schedule)
            self.assertEqual(status, 404)
        with self.engine.connect() as conn:
            for table in ("clinical_encounters", "clinical_encounter_commands"):
                self.assertEqual(conn.execute(text(f"SELECT count(*) FROM ehr.{table}")).scalar_one(), 0)
            self.assertEqual(conn.execute(text("SELECT count(*) FROM identity.identity_domain_events "
                "WHERE event_type='clinical_encounter_scheduled'")).scalar_one(), 0)


class EncounterActivityDeliveryTests(SourceVersionFixture):
    def test_committed_encounter_to_independent_receiver_and_revoked_grant(self):
        from contextlib import closing
        from pathlib import Path
        import sqlite3
        from urllib.parse import urlsplit
        import signal
        from oi_api.encounter_relay import FeedUnavailable, receive_once, verify_history
        from test_encounter_relay import interrupt_receiver

        self.creds[0]["actions"].extend(["encounter.read", "encounter.schedule", "encounter.transition",
                                        "note.read", "note.write", "encounter.events.read"])
        self.write()
        receiver = Path(self.temp.name) / "activity.sqlite"
        with running_server(create_app(self.settings)) as base:
            patient = self.setup_case(base)
            url = f"/v1/patients/{patient}/encounters"
            port = urlsplit(base).port

            def deliver(token=TOKEN_A):
                return receive_once(receiver, port, patient, lambda: token)

            def post(path, body):
                code, data, _ = request(base, path, token=TOKEN_A, body=body)
                self.assertEqual(code, 200, data)
                return data

            self.assertEqual(deliver()["counts"], {})
            first = post(url, EncounterHTTPTests.schedule)
            self.assertEqual(post(url, EncounterHTTPTests.schedule), first)
            visit = f'{url}/{first["encounter_id"]}'
            post(visit + "/transitions", {"synthetic": True, "request_key": "START-ONE",
                 "target": "in_progress", "expected_revision": 1})
            draft = {"synthetic": True, "request_key": "WRITE-ONE", "expected_version": 0,
                     "body": "Fictional note text stays with the EHR.", "note_kind": "consultation"}
            note = visit + "/notes/NOTE-ONE/versions"
            post(note, draft)
            expected = {"clinical_encounter_scheduled": 1, "clinical_encounter_state_changed": 1,
                        "clinical_note_draft_saved": 1}
            token_file = Path(self.temp.name) / "relay-token"
            token_file.write_text(TOKEN_A)
            interrupted = interrupt_receiver(receiver, patient, port, token_file)
            self.assertEqual(interrupted.returncode, -signal.SIGKILL, interrupted.stderr)
            with closing(sqlite3.connect(receiver)) as db:
                self.assertEqual(db.execute("SELECT count(*) FROM activity_receipts").fetchone(), (0,))
                self.assertEqual(db.execute("SELECT count(*) FROM activity_totals").fetchone(), (0,))
            result = deliver()
            self.assertEqual((result["applied"], result["counts"]), (3, expected))
            self.assertEqual(deliver()["applied"], 0)
            verification = verify_history(receiver, port, patient, lambda: TOKEN_A)
            self.assertEqual(verification["verified_events"], 3)
            post(note, dict(draft, request_key="WRITE-TWO", expected_version=1, body="Fictional revision."))
            with self.assertRaises(FeedUnavailable):
                deliver(TOKEN_B)
            self.creds[0]["actions"].remove("note.read")
            self.write()
            with self.assertRaises(FeedUnavailable):
                deliver()
            with self.assertRaises(FeedUnavailable):
                verify_history(receiver, port, patient, lambda: TOKEN_A)
            with closing(sqlite3.connect(receiver)) as db:
                self.assertEqual(db.execute("SELECT count(*) FROM activity_receipts").fetchone()[0], 3)
            self.creds[0]["actions"].append("note.read")
            self.write()
            self.assertEqual(deliver()["applied"], 1)
            verification = verify_history(receiver, port, patient, lambda: TOKEN_A)
            self.assertEqual(verification["verified_events"], 4)
            self.assertNotIn(draft["body"].encode(), receiver.read_bytes())
