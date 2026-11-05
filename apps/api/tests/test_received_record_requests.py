"""PostgreSQL 16 contract: fulfill a fictional record request from an exact source.

One canonical patient registry; one original-source owner; receipt in original
identity domain events. No patient data, hospital contact, or clinical review.
"""
import json
from datetime import datetime
import unittest
from unittest.mock import patch

from sqlalchemy import text

from oi_api.app import create_app
from oi_api.record_requests import PostgresRecordRequests
from open_intelligence.postgres_registry import PostgresPatientRegistry

from test_patients import request, TOKEN_A, TOKEN_B
from test_source_versions import SourceVersionHTTPTests as SourceFixture, ORIGINAL, AMENDED


class ReceivedRecordHTTPTests(SourceFixture):
    # Inherit the actual source/identity/PG16 fixture and its regression tests
    # rather than replacing the source owner or its isolated database setup.

    def setUp(self):
        super().setUp()
        for credential in self.creds:
            credential["actions"].extend((
                "record_request_create", "record_request_read",
                "record_request_cancel", "record_request_receive",
            ))
        self.write()

    def record_url(self, patient):
        return f"/v1/patients/{patient}/record-requests"

    def create_request(self, base, patient, *, token=TOKEN_A, kind="pathology",
                       key="RECORD-SYNTH-001"):
        return request(base, self.record_url(patient), token=token, body={
            "synthetic": True, "request_key": key, "kind": kind,
            "record_label": "Independently fictional original report",
            "source_organization": "Fictional institution",
        })

    def receive(self, base, patient, request_id, source_id, *,
                token=TOKEN_A, case="CASE-ALPHA", **overrides):
        values = {"synthetic": True, "case_id": case, "source_id": source_id}
        values.update(overrides)
        return request(base, self.record_url(patient) + "/" + request_id + "/receive",
                       token=token, body=values)

    def list_records(self, base, patient, *, token=TOKEN_A):
        return request(base, self.record_url(patient), token=token)

    def test_exact_source_receive_is_idempotent_and_restart_persists_one_receipt(self):
        with self.subTest("real PostgreSQL plus exact-source HTTP"):
            with __import__("http_support").running_server(create_app(self.settings)) as base:
                patient = self.setup_case(base)
                req = self.create_request(base, patient)
                self.assertEqual(req[0], 201)
                request_id = req[1]["request_id"]
                initial = self.list_records(base, patient)[1]
                self.assertTrue(initial["source_receipts_enabled"])
                self.assertEqual(initial["requests"][0]["receipt_status"], "not_received")
                self.assertIsNone(initial["requests"][0]["source_reference"])
                original = self.ingest(base, patient)
                self.assertEqual(original[0], 201)
                source_id = original[1]["source_id"]
                receipt = self.receive(base, patient, request_id, source_id)
                self.assertEqual((receipt[0], receipt[1]["duplicate"]), (201, False))
                self.assertEqual(receipt[1]["source_id"], source_id)
                self.assertEqual(self.receive(base, patient, request_id, source_id)[0], 200)
                self.assertTrue(self.receive(base, patient, request_id, source_id)[1]["duplicate"])
                self.assertEqual(self.create_request(base, patient)[1]["request_id"], request_id)
                row = self.list_records(base, patient)[1]["requests"][0]
                self.assertEqual((row["status"], row["revision"]), ("received", 2))
                self.assertEqual(row["receipt_status"], "source_current_unreviewed")
                self.assertEqual(row["source_reference"]["source_id"], source_id)
                self.assertEqual(row["source_reference"]["version"], 1)
                # The receipt is an event, not a mutation of record_requests.
                # The displayed last activity must reflect that actual event.
                with self.engine.connect() as audit:
                    receipt_at = audit.execute(text(
                        "SELECT occurred_at FROM identity.identity_domain_events "
                        "WHERE patient_id=:patient AND event_type='record.request.received' "
                        "AND metadata_json->>'request_id'=:request_id"
                    ), {"patient": patient, "request_id": request_id}).scalar_one()
                self.assertEqual(datetime.fromisoformat(row["updated_at"].replace("Z", "+00:00")), receipt_at)
                self.assertFalse(row["external_request_sent"])
                self.assertEqual(request(base, self.record_url(patient) + "/" +
                    request_id + "/cancel", token=TOKEN_A,
                    body={"synthetic": True, "reason": "Fictional correction"})[0], 409)
                self.assertEqual(self.ingest(base, patient, AMENDED)[0], 201)
                updated = self.list_records(base, patient)[1]["requests"][0]
                self.assertEqual(updated["receipt_status"],
                                 "source_superseded_reconciliation_required")
                self.assertEqual(updated["source_reference"]["source_id"], source_id)
                self.assertEqual(datetime.fromisoformat(updated["updated_at"].replace("Z", "+00:00")), receipt_at)
                # A historical receipt cannot be silently switched to the new
                # source version, even after a correction was imported.
                sources = request(base, self.url(patient), token=TOKEN_A)[1]["sources"]
                amended_id = sources[1]["source_id"]
                self.assertEqual(self.receive(base, patient, request_id, amended_id)[0], 409)
            with __import__("http_support").running_server(create_app(self.settings)) as restarted:
                current = self.list_records(restarted, patient)[1]["requests"][0]
                self.assertEqual(current["source_reference"]["source_id"], source_id)
                self.assertEqual(current["receipt_status"],
                                 "source_superseded_reconciliation_required")
        with self.engine.connect() as connection:
            rows = connection.execute(text(
                "SELECT event_type FROM identity.identity_domain_events "
                "WHERE patient_id=:id AND event_type='record.request.received'"
            ), {"id": patient}).scalars().all()
            self.assertEqual(rows, ["record.request.received"])
            self.assertEqual(connection.execute(text(
                "SELECT COUNT(*) FROM coordination.record_requests WHERE patient_id=:id"
            ), {"id": patient}).scalar_one(), 1)

    def test_amended_original_before_first_receipt_cannot_satisfy_request(self):
        # A correction arriving before the receive call must not be accepted
        # as though its superseded original were still current.
        with __import__("http_support").running_server(create_app(self.settings)) as base:
            patient = self.setup_case(base)
            request_id = self.create_request(base, patient)[1]["request_id"]
            historical_id = self.ingest(base, patient)[1]["source_id"]
            current = self.ingest(base, patient, AMENDED)
            self.assertEqual(current[0], 201)
            current_id = current[1]["source_id"]
            stale = self.receive(base, patient, request_id, historical_id)
            self.assertEqual(stale[0], 409)
            pending = self.list_records(base, patient)[1]["requests"][0]
            self.assertEqual((pending["status"], pending["receipt_status"]),
                             ("requested", "not_received"))
            self.assertIsNone(pending["source_reference"])
            with self.engine.connect() as audit:
                self.assertEqual(audit.execute(text(
                    "SELECT COUNT(*) FROM identity.identity_domain_events "
                    "WHERE event_type='record.request.received' AND patient_id=:patient"
                ), {"patient": patient}).scalar_one(), 0)
            accepted = self.receive(base, patient, request_id, current_id)
            self.assertEqual((accepted[0], accepted[1]["version"]), (201, 2))
            received = self.list_records(base, patient)[1]["requests"][0]
            self.assertEqual(received["source_reference"]["source_id"], current_id)
            self.assertEqual(received["source_reference"]["version"], 2)
            self.assertEqual(received["receipt_status"], "source_current_unreviewed")

    def test_wrong_case_kind_patient_and_cancelled_request_are_denied(self):
        with __import__("http_support").running_server(create_app(self.settings)) as base:
            patient = self.setup_case(base)
            other = self.setup_case(base, token=TOKEN_B, case="CASE-BETA",
                                    key="CREATE-BETA", source_subject="SUBJECT-BETA")
            source_id = self.ingest(base, patient)[1]["source_id"]
            wrong_kind = self.create_request(base, patient, kind="imaging", key="RECORD-IMAGE")
            request_id = wrong_kind[1]["request_id"]
            self.assertEqual(self.receive(base, patient, request_id, source_id)[0], 404)
            self.assertEqual(self.receive(base, other, request_id, source_id,
                                          token=TOKEN_B, case="CASE-BETA")[0], 404)
            correct = self.create_request(base, patient)
            rid = correct[1]["request_id"]
            self.assertEqual(self.receive(base, patient, rid, source_id,
                                          case="CASE-BETA")[0], 404)
            self.assertEqual(self.receive(base, patient, rid, source_id,
                                          token=TOKEN_B)[0], 404)
            cancel = request(base, self.record_url(patient) + "/" + rid + "/cancel",
                             token=TOKEN_A,
                             body={"synthetic": True,
                                   "reason": "Cancelled before receipt was linked"})
            self.assertEqual(cancel[0], 200)
            self.assertEqual(self.receive(base, patient, rid, source_id)[0], 409)
            self.assertEqual(self.list_records(base, patient)[1]["requests"][1]["status"],
                             "cancelled")
        with self.engine.connect() as c:
            self.assertEqual(c.execute(text(
                "SELECT COUNT(*) FROM identity.identity_domain_events "
                "WHERE event_type='record.request.received'"
            )).scalar_one(), 0)

    def test_source_permission_and_receipt_permission_are_independent(self):
        with __import__("http_support").running_server(create_app(self.settings)) as base:
            pid = self.setup_case(base)
            rid = self.create_request(base, pid)[1]["request_id"]
            sid = self.ingest(base, pid)[1]["source_id"]
            self.creds[0]["actions"].remove("record_request_receive")
            self.write()
            self.assertEqual(self.receive(base, pid, rid, sid)[0], 404)
            self.creds[0]["actions"].append("record_request_receive")
            self.creds[0]["actions"].remove("source_read")
            self.write()
            self.assertEqual(self.receive(base, pid, rid, sid)[0], 404)
            readable = self.list_records(base, pid)
            self.assertEqual(readable[0], 200)
            self.assertIsNone(readable[1]["requests"][0]["source_reference"])
            self.creds[0]["actions"].append("source_read")
            self.write()
            self.assertEqual(self.receive(base, pid, rid, sid)[0], 201)
            self.creds[0]["actions"].remove("source_read")
            self.write()
            restricted = self.list_records(base, pid)[1]["requests"][0]
            self.assertEqual(restricted["status"], "received")
            self.assertIsNone(restricted["source_reference"])
            self.assertEqual(request(base, self.url(pid) + "/" + sid,
                                     token=TOKEN_A)[0], 200)

    def test_revoked_binding_blocks_receipt_source_reference_and_new_writes(self):
        with __import__("http_support").running_server(create_app(self.settings)) as base:
            pid = self.setup_case(base)
            rid = self.create_request(base, pid)[1]["request_id"]
            sid = self.ingest(base, pid)[1]["source_id"]
            self.assertEqual(self.receive(base, pid, rid, sid)[0], 201)
            revoked = request(base,
                f"/v1/patients/{pid}/case-bindings/CASE-ALPHA/revoke",
                token=TOKEN_A, body={
                    "synthetic": True,
                    "reason": "Fictional case relationship withdrawn for safety"
                })
            self.assertEqual(revoked[0], 200)
            row = self.list_records(base, pid)[1]["requests"][0]
            self.assertEqual(row["status"], "received")
            self.assertEqual(row["receipt_status"], "binding_revoked_not_usable")
            self.assertIsNone(row["source_reference"])
            self.assertEqual(self.receive(base, pid, rid, sid)[0], 404)

    def test_event_failure_does_not_leave_a_received_receipt(self):
        with __import__("http_support").running_server(create_app(self.settings)) as base:
            pid = self.setup_case(base)
            rid = self.create_request(base, pid)[1]["request_id"]
            sid = self.ingest(base, pid)[1]["source_id"]
            prior = PostgresPatientRegistry.append_event
            def rejected(registry, patient_id, event_type, **details):
                if event_type == "record.request.received":
                    raise RuntimeError("Fictional event store refused the write")
                return prior(registry, patient_id, event_type, **details)
            with patch.object(PostgresPatientRegistry, "append_event", rejected):
                self.assertEqual(self.receive(base, pid, rid, sid)[0], 503)
            row = self.list_records(base, pid)[1]["requests"][0]
            self.assertEqual((row["status"], row["receipt_status"]),
                             ("requested", "not_received"))
            self.assertEqual(self.receive(base, pid, rid, sid)[0], 201)
            self.assertEqual(self.list_records(base, pid)[1]["requests"][0]["status"],
                             "received")


if __name__ == "__main__":
    unittest.main()
