"""Populated 0017 upgrade, relational invariants, recovery boundary and capacity."""
import json
import uuid
from unittest.mock import patch

from alembic.util.exc import CommandError
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError

from oi_api.composer_preflight import PostgresSourceComposerPreflight
from oi_api.contracts import SCHEMA_REVISION
from oi_api.laboratory_questions import MAX_LABORATORY_QUESTIONS, PostgresLaboratoryQuestions
from oi_api.migrate import migrate
from oi_api.source_world_model import project_source_world_model
from oi_api.sources import PostgresSourceVersions
from open_intelligence.patient_registry import PatientRegistryConflict
import test_evidence_convergence_migrations as evidence
import test_lab_manual_convergence as previous
from test_laboratory_fhir_r4 import OBS
from test_source_versions import SourceVersionFixture


class LaboratoryQuestionMigrationTests(SourceVersionFixture):
    services = evidence.EvidenceConvergenceMigrationTests.services
    start_at = evidence.EvidenceConvergenceMigrationTests.start_at
    snapshot = evidence.EvidenceConvergenceMigrationTests.snapshot
    seed_lab = previous.LabManualPopulatedMigrationTests.seed_lab

    def seed(self):
        patient, text_question, _ = self.start_at(previous.JOIN)
        _, source = self.seed_lab(patient)
        history = self.snapshot()
        migrate(self.admin, "upgrade", SCHEMA_REVISION)
        self.assertEqual(self.snapshot(history[0]), history)
        self.assertEqual(self.snapshot()[0]["investigation.laboratory_question_anchors"], [])
        # A new empty typed owner is reversible without changing existing rows.
        migrate(self.admin, "downgrade", previous.JOIN)
        self.assertEqual(self.snapshot(), history)
        migrate(self.admin, "upgrade", SCHEMA_REVISION)
        with self.services() as registry:
            index = PostgresSourceVersions(registry).list(patient, "CASE-ALPHA", **evidence.OPTIONS)
            payload = dict(source_id=source["source_id"], observation_reference=OBS,
                           question="What questions should we ask about this fictional observation?",
                           expected_source_snapshot_sha256=project_source_world_model(index)["snapshot_fingerprint"])
            preflight = PostgresSourceComposerPreflight(registry).preview_laboratory(
                patient, "CASE-ALPHA", **payload, **evidence.OPTIONS)
            payload.update(expected_preflight_sha256=preflight["preflight_sha256"], request_key="LAB-SAVED-ONE")
            receipt = PostgresLaboratoryQuestions(registry).save(patient, "CASE-ALPHA", **payload, **evidence.OPTIONS)
        return patient, text_question, payload, receipt

    def test_typed_anchors_reject_incomplete_mismatched_or_mutated_history(self):
        _, text_qid, payload, receipt = self.seed()
        qid, sid = receipt["question_id"], payload["source_id"]
        history = self.snapshot()
        def bad_clone(changes, marker, *, anchor=None):
            new_id = "QUESTION-" + uuid.uuid4().hex.upper()
            overrides = dict(question_id=new_id, request_key=new_id, **changes)
            with self.assertRaisesRegex(DBAPIError, marker):
                with self.engine.begin() as conn:
                    conn.execute(text("""
                        INSERT INTO investigation.source_questions
                        SELECT (jsonb_populate_record(NULL::investigation.source_questions,
                                to_jsonb(q) || CAST(:overrides AS jsonb))).*
                        FROM investigation.source_questions q WHERE q.question_id=:id
                    """), {"id": qid, "overrides": json.dumps(overrides)})
                    if anchor is not None:
                        conn.execute(text("""
                            INSERT INTO investigation.laboratory_question_anchors
                            (question_id,source_id,observation_reference) VALUES (:id,:sid,:ref)
                        """), {"id": new_id, "sid": anchor[0], "ref": anchor[1]})

        bad_clone({}, "OI-LAB-QUESTION-MISSING-ANCHOR")  # deferred until commit
        for change in ({"origin_org": "ORG-WRONG"}, {"case_id": "CASE-WRONG"},
                       {"source_sha256": "0" * 64}, {"source_version": 2}):
            with self.subTest(change=change):
                bad_clone(change, "OI-LAB-QUESTION-SOURCE-BOUNDARY")
        bad_clone({}, "OI-LAB-QUESTION-ANCHOR-BOUNDARY", anchor=("SRC-" + "B" * 32, OBS))
        bad_clone({}, "foreign key constraint", anchor=(sid, "Observation/FICTIONAL-MISSING"))

        with self.assertRaisesRegex(DBAPIError, "OI-LAB-QUESTION-ANCHOR-BOUNDARY"):
            with self.engine.begin() as conn:
                conn.execute(text("INSERT INTO investigation.laboratory_question_anchors "
                                  "(question_id,source_id,observation_reference) VALUES (:q,:s,:r)"),
                             {"q": text_qid, "s": sid, "r": OBS})
        for command in ("UPDATE investigation.laboratory_question_anchors SET source_id=source_id",
                        "DELETE FROM investigation.laboratory_question_anchors"):
            with self.subTest(command=command), self.assertRaisesRegex(DBAPIError, "HISTORY-IMMUTABLE"):
                with self.engine.begin() as conn:
                    conn.execute(text(command + " WHERE question_id=:q"), {"q": qid})

        with self.assertRaisesRegex(DBAPIError, "HISTORY-IMMUTABLE"):
            with self.engine.begin() as conn:
                conn.execute(text("TRUNCATE investigation.laboratory_question_anchors"))

        with self.assertRaisesRegex(CommandError, "Stored laboratory question history"):
            migrate(self.admin, "downgrade", previous.JOIN)
        self.assertEqual(self.snapshot(), history)
        with self.engine.connect() as conn:
            self.assertEqual(conn.execute(text("SELECT version_num FROM public.alembic_version")).scalar_one(),
                             SCHEMA_REVISION)

    def test_full_history_remains_readable_and_exact_requests_recover(self):
        patient, _, payload, receipt = self.seed()
        self.assertEqual(MAX_LABORATORY_QUESTIONS, 250)
        # Exercise the same transaction/capacity boundary with one real row.
        with patch("oi_api.laboratory_questions.MAX_LABORATORY_QUESTIONS", 1), self.services() as registry:
            owner = PostgresLaboratoryQuestions(registry)
            with self.assertRaisesRegex(PatientRegistryConflict, "capacity"):
                owner.save(patient, "CASE-ALPHA", **(payload | {"request_key": "LAB-OVER-CAP"}), **evidence.OPTIONS)
            self.assertEqual(owner.save(patient, "CASE-ALPHA", **payload, **evidence.OPTIONS),
                             receipt | {"duplicate": True})
            saved, = owner.list(patient, "CASE-ALPHA", **evidence.OPTIONS)["questions"]
            self.assertEqual(saved["question_id"], receipt["question_id"])
