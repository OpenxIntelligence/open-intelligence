"""Actual PG16/HTTP regressions for authority through World Model preparation.

All originals and credentials come from the independently fictional source
fixture. Patches retain the real projector and change authority only after it
has prepared its observations; database transactions and receipts remain real.
"""

import copy
from datetime import datetime, timedelta, timezone
import json
from unittest.mock import patch

from sqlalchemy import text
from sqlalchemy.exc import DBAPIError

from oi_api import patients as patient_routes
from oi_api.app import create_app
from oi_api.source_world_model import project_source_world_model
from http_support import running_server
from test_patients import TOKEN_A, request
from test_source_versions import SourceVersionFixture


class ProjectionAuthorityTests(SourceVersionFixture):
    def world_url(self, patient):
        return f"/v1/patients/{patient}/cases/CASE-ALPHA/world-model"

    def read_events(self):
        with self.engine.connect() as connection:
            return connection.execute(text(
                "SELECT event_type,metadata_json FROM identity.identity_domain_events "
                "WHERE event_type IN ('source.read_authorized','source.original_read_authorized') "
                "ORDER BY id"
            )).all()

    def assert_withheld(self, response, expected_status, previous_events):
        status, body, headers = response
        self.assertEqual(status, expected_status)
        self.assertEqual(set(body), {"detail"})
        self.assertEqual(headers["Cache-Control"], "no-store")
        serialized = json.dumps(body, ensure_ascii=False)
        for private in (TOKEN_A, "Fictional café", "PRIVATE-PROJECTION-FAILURE",
                        "PRIVATE-PROJECTION-PROVIDER", "PRIVATE-PROJECTION-AUDIT"):
            self.assertNotIn(private, serialized)
        self.assertEqual(self.read_events(), previous_events)

    def test_authority_changed_after_projection_withholds_view_and_receipt(self):
        with running_server(create_app(self.settings)) as base:
            patient = self.setup_case(base)
            self.assertEqual(self.ingest(base, patient)[0], 201)
            initial = copy.deepcopy(self.creds)
            changes = [
                ("source_action", {"actions": [action for action in initial[0]["actions"]
                                                if action != "source_read"]}, 404),
                ("patient_action", {"actions": [action for action in initial[0]["actions"]
                                                 if action != "patient_read"]}, 404),
                ("patient_scope", {"patient_ids": []}, 404),
                ("actor", {"actor": "ACTOR-CHANGED"}, 404),
                ("organization", {"organization": "ORG-CHANGED"}, 404),
                ("purpose", {"purpose": "research"}, 404),
                ("expiry", {"expires_at": (datetime.now(timezone.utc)
                                           - timedelta(minutes=1)).isoformat()}, 401),
            ]
            for name, change, expected in changes:
                with self.subTest(change=name):
                    self.creds = copy.deepcopy(initial)
                    self.write()
                    previous_events = self.read_events()

                    def withdraw(index):
                        result = project_source_world_model(index)
                        self.creds[0].update(change)
                        self.write()
                        return result

                    with patch.object(patient_routes, "project_source_world_model",
                                      side_effect=withdraw) as prepared:
                        response = request(base, self.world_url(patient), token=TOKEN_A)
                    prepared.assert_called_once()
                    self.assert_withheld(response, expected, previous_events)

    def test_missing_or_unreadable_authority_after_projection_withholds_view_and_receipt(self):
        with running_server(create_app(self.settings)) as base:
            patient = self.setup_case(base)
            self.assertEqual(self.ingest(base, patient)[0], 201)
            initial = copy.deepcopy(self.creds)
            for change, expected in (("credential_removed", 401),
                                     ("provider_malformed", 503),
                                     ("provider_missing", 503)):
                with self.subTest(change=change):
                    self.creds = copy.deepcopy(initial)
                    self.write()
                    previous_events = self.read_events()

                    def withdraw(index):
                        result = project_source_world_model(index)
                        if change == "credential_removed":
                            self.creds.pop(0)
                            self.write()
                        elif change == "provider_malformed":
                            self.access.write_text("PRIVATE-PROJECTION-PROVIDER")
                        else:
                            self.access.unlink()
                        return result

                    with patch.object(patient_routes, "project_source_world_model",
                                      side_effect=withdraw) as prepared:
                        response = request(base, self.world_url(patient), token=TOKEN_A)
                    prepared.assert_called_once()
                    self.assert_withheld(response, expected, previous_events)

    def test_projection_failure_withholds_view_and_rolls_back_read_receipt(self):
        with running_server(create_app(self.settings)) as base:
            patient = self.setup_case(base)
            self.assertEqual(self.ingest(base, patient)[0], 201)
            previous_events = self.read_events()

            def fail_after_projection(index):
                project_source_world_model(index)
                raise RuntimeError("PRIVATE-PROJECTION-FAILURE")

            with patch.object(patient_routes, "project_source_world_model",
                              side_effect=fail_after_projection) as prepared:
                response = request(base, self.world_url(patient), token=TOKEN_A)
            prepared.assert_called_once()
            self.assert_withheld(response, 503, previous_events)

    def test_read_receipt_failure_after_projection_withholds_view(self):
        with running_server(create_app(self.settings)) as base:
            patient = self.setup_case(base)
            self.assertEqual(self.ingest(base, patient)[0], 201)
            previous_events = self.read_events()
            with self.engine.begin() as connection:
                connection.exec_driver_sql("""
                    CREATE FUNCTION identity.reject_projection_receipt() RETURNS trigger
                    LANGUAGE plpgsql AS $$ BEGIN
                    IF NEW.event_type='source.read_authorized' THEN
                        RAISE EXCEPTION 'PRIVATE-PROJECTION-AUDIT';
                    END IF;
                    RETURN NEW; END; $$;
                """)
                connection.exec_driver_sql(
                    "CREATE TRIGGER reject_projection_receipt "
                    "BEFORE INSERT ON identity.identity_domain_events "
                    "FOR EACH ROW EXECUTE FUNCTION identity.reject_projection_receipt()"
                )
            with patch.object(patient_routes, "project_source_world_model",
                              wraps=project_source_world_model) as prepared:
                response = request(base, self.world_url(patient), token=TOKEN_A)
            prepared.assert_called_once()
            self.assert_withheld(response, 503, previous_events)

    def test_patient_and_binding_locks_cover_projection_until_receipt_commit(self):
        with running_server(create_app(self.settings)) as base:
            patient = self.setup_case(base)
            self.assertEqual(self.ingest(base, patient)[0], 201)
            previous_events = self.read_events()
            targets = (
                ("patient", "SELECT patient_id FROM identity.identity_patients "
                            "WHERE patient_id=:patient FOR UPDATE NOWAIT", {"patient": patient}),
                ("binding", "SELECT case_id FROM coordination.patient_case_bindings "
                            "WHERE case_id=:case FOR UPDATE NOWAIT", {"case": "CASE-ALPHA"}),
            )

            def attempt_lock(sql, parameters):
                # An independent PostgreSQL session competes with the active
                # HTTP read. NOWAIT proves the conflict without timing sleeps.
                with self.engine.connect() as connection:
                    try:
                        connection.execute(text(sql), parameters).scalar_one()
                    except DBAPIError as error:
                        details = error.orig.args[0] if error.orig.args else None
                        return details.get("C") if isinstance(details, dict) else None
                return "acquired"

            observed = {}

            def observe_projection(index):
                result = project_source_world_model(index)
                observed["receipts"] = self.read_events()
                observed["locks"] = [(name, attempt_lock(sql, parameters))
                                     for name, sql, parameters in targets]
                return result

            with patch.object(patient_routes, "project_source_world_model",
                              side_effect=observe_projection) as prepared:
                status, body, _ = request(base, self.world_url(patient), token=TOKEN_A)
            prepared.assert_called_once()
            self.assertEqual(status, 200)
            self.assertEqual(observed["receipts"], previous_events)
            self.assertEqual(observed["locks"], [("patient", "55P03"), ("binding", "55P03")])
            events = self.read_events()
            self.assertEqual(len(events), len(previous_events) + 1)
            self.assertEqual(events[-1][1]["receipt_id"], body["access_receipt_id"])
            for name, sql, parameters in targets:
                with self.subTest(released_lock=name):
                    self.assertEqual(attempt_lock(sql, parameters), "acquired")
