"""Integration acceptance for real first-party registry, EHR and domain-event code.

Uses independently authored fictional identifiers only. An injected authorizer
in these tests is NOT real clinician proof or production consent enforcement.
"""
import json
import sqlite3
import tempfile
import unittest
from pathlib import Path

from open_intelligence.clinical_encounters import (
    ClinicalAuthorizationError, ClinicalEncounters,
)
from open_intelligence.clinical_event_host import EventedClinicalHost
from open_intelligence.patient_registry import (
    PatientRegistry, PatientRegistryDenied,
)
from open_intelligence.platform_events import (
    OutboxContractError, consume_ordered, install,
)


ACTOR = "idp:clinician-001"
ORG = "ORG-FICTIONAL-001"


class PatientEhrDomainEventIntegrationTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.path = Path(temp.name) / "canonical-operational.sqlite"
        self.db = sqlite3.connect(self.path)
        self.db.row_factory = sqlite3.Row
        self.addCleanup(self.db.close)
        self.registry = PatientRegistry(
            self.db, authorizer=lambda actor, patient, action, purpose:
            actor == ACTOR and purpose == "care",
        )
        install(self.db)
        self.host = EventedClinicalHost(self.registry)
        self.ehr = ClinicalEncounters(
            self.host, authorizer=lambda actor, patient, action, purpose:
            actor == ACTOR and purpose == "care",
        )
        self.patient = self.registry.create_patient(
            organization=ORG, actor=ACTOR, purpose="care",
            request_key="CREATE-FICTIONAL-001",
        )["patient_id"]

    def _schedule(self):
        return self.ehr.schedule(
            self.patient, "ENC-001", "outpatient", "2026-11-02",
            actor=ACTOR, purpose="care", request_key="SCHEDULE-001",
        )

    def _full_journey(self):
        appointment = self._schedule()
        encounter_id = appointment["encounter_id"]
        self.ehr.transition(
            self.patient, encounter_id, "in_progress", expected_revision=1,
            actor=ACTOR, purpose="care", request_key="BEGIN-001",
        )
        note = self.ehr.write_note(
            self.patient, encounter_id, "NOTE-001",
            "Fictional clinical narrative. Not a real person or diagnosis.",
            expected_version=0, actor=ACTOR, purpose="care",
            request_key="WRITE-001",
        )
        attested = self.ehr.attest_note(
            self.patient, encounter_id, "NOTE-001",
            expected_version=1, actor=ACTOR, purpose="care",
            request_key="ATTEST-001",
        )
        return appointment, note, attested

    def test_one_canonical_patient_record_and_atomic_ehr_events(self):
        appointment, note, attested = self._full_journey()
        self.assertEqual(appointment["status"], "scheduled")
        self.assertEqual(note["status"], "draft")
        self.assertEqual(attested["status"], "attested")
        self.assertEqual(
            self.db.execute("SELECT COUNT(*) FROM identity_patients").fetchone()[0], 1
        )
        self.assertEqual(
            self.db.execute(
                "SELECT COUNT(*) FROM sqlite_master WHERE name='cases'"
            ).fetchone()[0], 0
        )
        rows = self.db.execute(
            "SELECT envelope_json FROM platform_outbox ORDER BY seq"
        ).fetchall()
        self.assertEqual(len(rows), 4)
        events = [json.loads(r[0]) for r in rows]
        self.assertEqual(
            [e["aggregate"]["revision"] for e in events], [1, 2, 3, 4]
        )
        self.assertEqual(
            [e["event_type"] for e in events],
            [
                "clinical.encounter.scheduled",
                "clinical.encounter.state_changed",
                "clinical.note.draft_saved",
                "clinical.note.attestation_recorded",
            ],
        )
        self.assertTrue(
            all(e["subject_binding_id"] == self.patient for e in events)
        )
        self.assertTrue(
            all(e["authorization_decision_ref"] is None for e in events)
        )
        serialized = "".join(row[0] for row in rows)
        self.assertNotIn("Fictional clinical narrative", serialized)
        history = self.ehr.note_history(
            self.patient, appointment["encounter_id"], "NOTE-001",
            actor=ACTOR, purpose="care",
        )
        self.assertEqual([x["version"] for x in history], [1, 2])
        self.assertEqual(
            self.db.execute(
                "SELECT COUNT(*) FROM identity_domain_events "
                "WHERE event_type LIKE 'clinical_%'"
            ).fetchone()[0], 4,
        )

    def test_real_domain_idempotency_and_restart_does_not_repeat_events(self):
        appointment, _, _ = self._full_journey()
        self.assertEqual(self._schedule(), appointment)
        self.assertEqual(
            self.db.execute("SELECT COUNT(*) FROM platform_outbox").fetchone()[0], 4
        )
        self.db.close()
        self.db = sqlite3.connect(self.path)
        self.db.row_factory = sqlite3.Row
        self.registry = PatientRegistry(self.db, authorizer=lambda actor, *_:
                                        actor == ACTOR)
        install(self.db)
        self.ehr = ClinicalEncounters(
            EventedClinicalHost(self.registry),
            authorizer=lambda actor, *_: actor == ACTOR,
        )
        self.assertEqual(self._schedule(), appointment)
        self.assertEqual(
            self.db.execute("SELECT COUNT(*) FROM platform_outbox").fetchone()[0], 4
        )
        self.assertEqual(
            len(self.ehr.note_history(
                self.patient, appointment["encounter_id"], "NOTE-001",
                actor=ACTOR, purpose="care",
            )), 2
        )

    def test_receiving_domain_accepts_ordered_events_once(self):
        self._full_journey()
        incoming = [
            json.loads(row[0]) for row in self.db.execute(
                "SELECT envelope_json FROM platform_outbox ORDER BY seq"
            )
        ]
        with sqlite3.connect(":memory:") as receiver:
            install(receiver)
            receiver.execute(
                "CREATE TABLE received_clinical_events("
                "event_id TEXT PRIMARY KEY, patient_id TEXT NOT NULL)"
            )

            def apply_effect(db, event):
                db.execute(
                    "INSERT INTO received_clinical_events VALUES (?,?)",
                    (event["event_id"], event["subject_binding_id"]),
                )

            for event in incoming:
                receiver.execute("BEGIN IMMEDIATE")
                with receiver:
                    self.assertTrue(
                        consume_ordered(receiver, "REVIEW-WORKSPACE", event, apply_effect)
                    )
            receiver.execute("BEGIN IMMEDIATE")
            with receiver:
                self.assertFalse(
                    consume_ordered(receiver, "REVIEW-WORKSPACE", incoming[2], apply_effect)
                )
            self.assertEqual(
                receiver.execute(
                    "SELECT COUNT(*) FROM received_clinical_events"
                ).fetchone()[0], 4
            )
            malicious = dict(incoming[-1])
            malicious["event_id"] = "EV-MALICIOUS-BOUNDARY"
            malicious["aggregate"] = {
                **malicious["aggregate"],
                "revision": 5,
            }
            malicious["subject_binding_id"] = "PAT-OTHER-SUBJECT"
            receiver.execute("BEGIN IMMEDIATE")
            with receiver:
                with self.assertRaisesRegex(
                    OutboxContractError, "subject binding changed"
                ):
                    consume_ordered(
                        receiver, "REVIEW-WORKSPACE", malicious, apply_effect
                    )
            self.assertEqual(
                receiver.execute(
                    "SELECT COUNT(*) FROM received_clinical_events"
                ).fetchone()[0], 4
            )

    def test_missing_transport_table_rolls_back_eligible_encounter(self):
        self.db.execute("DROP TABLE platform_outbox")
        before = self.db.execute(
            "SELECT COUNT(*) FROM identity_domain_events"
        ).fetchone()[0]
        with self.assertRaises(sqlite3.OperationalError):
            self._schedule()
        self.assertEqual(
            self.db.execute("SELECT COUNT(*) FROM clinical_encounters").fetchone()[0], 0
        )
        self.assertEqual(
            self.db.execute("SELECT COUNT(*) FROM clinical_encounter_commands").fetchone()[0], 0
        )
        self.assertEqual(
            self.db.execute("SELECT COUNT(*) FROM identity_domain_events").fetchone()[0], before
        )

    def test_denied_actor_and_suspended_patient_have_no_new_operational_effect(self):
        with self.assertRaises(ClinicalAuthorizationError):
            self.ehr.schedule(
                self.patient, "ENC-001", "outpatient", "2026-11-02",
                actor="idp:unverified-2", purpose="care", request_key="DENIED-001",
            )
        self.assertEqual(
            self.db.execute("SELECT COUNT(*) FROM platform_outbox").fetchone()[0], 0
        )
        self.registry.suspend_patient(
            self.patient, actor=ACTOR, purpose="care", expected_revision=1
        )
        with self.assertRaises(PatientRegistryDenied):
            self._schedule()
        self.assertEqual(
            self.db.execute("SELECT COUNT(*) FROM platform_outbox").fetchone()[0], 0
        )


if __name__ == "__main__":
    unittest.main()
