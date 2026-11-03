"""Actual PG16 upgrade acceptance for immutable fictional question provenance."""
from datetime import datetime, timezone
import hashlib
import unittest

from sqlalchemy import text

from oi_api.app import create_app
from oi_api.migrate import migrate
from http_support import running_server
from test_patients import TOKEN_A, request
from test_source_versions import ORIGINAL, SourceVersionFixture


class QuestionFingerprintMigrationTests(SourceVersionFixture):
    def test_legacy_upgrade_preserves_history_even_when_hash_matches_canonical(self):
        # The current API requires the head schema. Create its source fixture
        # first, then recreate the actual old question schema before insertion.
        with running_server(create_app(self.settings)) as base:
            patient = self.setup_case(base)
            status, imported, _ = self.ingest(base, patient)
            self.assertEqual(status, 201, imported)
            source_id = imported["source_id"]
            prefix = f"/v1/patients/{patient}/cases/CASE-ALPHA"
            status, world, _ = request(base, prefix + "/world-model", token=TOKEN_A)
            self.assertEqual(status, 200, world)
            self.assertEqual(world["contract"], "oi.pg-source-world-model/1")
            fingerprint = world["snapshot_fingerprint"]

        migrate(self.admin, "downgrade", "0006_source_questions")
        legacy_id = "QUESTION-" + "A" * 32
        with self.engine.begin() as connection:
            self.assertEqual(connection.execute(text(
                "SELECT version_num FROM public.alembic_version"
            )).scalar_one(), "0006_source_questions")
            self.assertEqual(connection.execute(text(
                "SELECT count(*) FROM information_schema.columns "
                "WHERE table_schema='investigation' AND table_name='source_questions' "
                "AND column_name='source_snapshot_contract'"
            )).scalar_one(), 0)
            # Use the live patient/source foreign keys and insertion guards.
            # The matching hash is deliberate: provenance must still prevent
            # silently promoting a legacy row to the canonical contract.
            connection.execute(text(
                "INSERT INTO investigation.source_questions "
                "(question_id,patient_id,case_id,origin_org,request_key,intent_sha256,"
                "actor,purpose,question,source_id,source_line,source_sha256,"
                "source_version,source_snapshot_sha256,preflight_sha256,created_at) "
                "VALUES (:question_id,:patient,'CASE-ALPHA','ORG-ALPHA',"
                "'LEGACY-QUESTION-KEY',:intent,'ACTOR-ALPHA','operations',"
                ":question,:source_id,8,:source_sha256,1,:snapshot,:preflight,:created)"
            ), {
                "question_id": legacy_id,
                "patient": patient,
                "intent": "1" * 64,
                "question": "What should this fictional marker source leave unresolved?",
                "source_id": source_id,
                "source_sha256": hashlib.sha256(ORIGINAL.encode("utf-8")).hexdigest(),
                "snapshot": fingerprint,
                "preflight": "2" * 64,
                "created": datetime(2026, 1, 15, 12, 34, 56, tzinfo=timezone.utc),
            })
            before = dict(connection.execute(text(
                "SELECT * FROM investigation.source_questions WHERE question_id=:id"
            ), {"id": legacy_id}).mappings().one())

        migrate(self.admin, "upgrade", "0007_question_snapshot_contract")
        with self.engine.connect() as connection:
            self.assertEqual(connection.execute(text(
                "SELECT version_num FROM public.alembic_version"
            )).scalar_one(), "0007_question_snapshot_contract")
            migrated = dict(connection.execute(text(
                "SELECT * FROM investigation.source_questions WHERE question_id=:id"
            ), {"id": legacy_id}).mappings().one())
        self.assertEqual(migrated.pop("source_snapshot_contract"),
                         "oi.synthetic-postgres-world-model-sources/1")
        # Compare every old column, including anchors, both hashes, request
        # identity, actor/purpose and creation time; the upgrade must not rehash.
        self.assertEqual(migrated, before)

        # The published image-custody revision is an independent sibling.
        # Running the API requires the explicit combined head, not an
        # intermediate question-only revision.
        migrate(self.admin, "upgrade", "head")
        with self.engine.connect() as connection:
            self.assertEqual(connection.execute(text(
                "SELECT version_num FROM public.alembic_version"
            )).scalar_one(), "0008_questions_images_merge")

        self.creds[0]["actions"].extend((
            "composer_context_read", "question_create", "question_read",
        ))
        self.write()
        with running_server(create_app(self.settings)) as base:
            status, listing, _ = request(base, prefix + "/questions", token=TOKEN_A)
            self.assertEqual(status, 200, listing)
            self.assertEqual(len(listing["questions"]), 1)
            legacy = listing["questions"][0]
            self.assertEqual(legacy["question_id"], legacy_id)
            self.assertEqual(legacy["source_snapshot_sha256"], fingerprint)
            self.assertEqual(legacy["source_snapshot_contract"],
                             "oi.synthetic-postgres-world-model-sources/1")
            self.assertEqual(legacy["source_context_state"], "source_reassessment_required")
            self.assertEqual(legacy["human_review_state"], "not_submitted")
            self.assertFalse(legacy["clinical_approval"])

            question = "What further fictional source would clarify this reported marker?"
            status, prepared, _ = request(
                base, prefix + "/composer/source-preflight", token=TOKEN_A,
                body={
                    "synthetic": True, "source_id": source_id, "source_line": 8,
                    "question": question, "expected_source_snapshot_sha256": fingerprint,
                },
            )
            self.assertEqual(status, 200, prepared)
            self.assertEqual(prepared["source_snapshot_contract"], "oi.pg-source-world-model/1")
            status, saved, _ = request(
                base, prefix + "/questions", token=TOKEN_A,
                body={
                    "synthetic": True, "request_key": "CANONICAL-AFTER-UPGRADE",
                    "question": question, "source_id": source_id, "source_line": 8,
                    "expected_source_snapshot_sha256": fingerprint,
                    "expected_preflight_sha256": prepared["preflight_sha256"],
                },
            )
            self.assertEqual(status, 201, saved)
            self.assertFalse(saved["duplicate"])
            status, after, _ = request(base, prefix + "/questions", token=TOKEN_A)
            self.assertEqual(status, 200, after)
            self.assertEqual(len(after["questions"]), 2)
            by_id = {row["question_id"]: row for row in after["questions"]}
            self.assertEqual(by_id[legacy_id]["source_context_state"],
                             "source_reassessment_required")
            canonical = by_id[saved["question_id"]]
            self.assertEqual(canonical["source_snapshot_contract"], "oi.pg-source-world-model/1")
            self.assertEqual(canonical["source_snapshot_sha256"], fingerprint)
            self.assertEqual(canonical["source_context_state"], "current_unreviewed_question")

        with self.engine.connect() as connection:
            persisted = connection.execute(text(
                "SELECT source_snapshot_contract,source_snapshot_sha256 "
                "FROM investigation.source_questions WHERE question_id=:id"
            ), {"id": saved["question_id"]}).one()
            final_legacy = dict(connection.execute(text(
                "SELECT * FROM investigation.source_questions WHERE question_id=:id"
            ), {"id": legacy_id}).mappings().one())
        self.assertEqual(tuple(persisted), ("oi.pg-source-world-model/1", fingerprint))
        self.assertEqual(final_legacy.pop("source_snapshot_contract"),
                         "oi.synthetic-postgres-world-model-sources/1")
        self.assertEqual(final_legacy, before)


if __name__ == "__main__":
    unittest.main()
