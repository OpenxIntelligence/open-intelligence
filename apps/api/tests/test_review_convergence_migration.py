"""Actual PG16 upgrades from both preserved question/review migration histories.

Rows are independently fictional and inserted with the original foreign keys
and immutable-history guards enabled. No migration or legacy hash is rewritten.
"""
from datetime import datetime, timezone
import hashlib
import json
import unittest

from sqlalchemy import text

from oi_api.app import create_app
from oi_api.migrate import migrate
from http_support import running_server
from test_canonical_review_flow import RETURN_REASON, create_question
from test_patients import TOKEN_A, request
from test_source_versions import ORIGINAL, SourceVersionFixture


LEGACY_SOURCE = "oi.synthetic-postgres-world-model-sources/1"
CANONICAL_SOURCE = "oi.pg-source-world-model/1"
LEGACY_QUEUE = "oi.synthetic-source-review-return/1"
CANONICAL_QUEUE = "oi.synthetic-source-review-return/2"
LEGACY_QUESTION = "QUESTION-" + "A" * 32
OLD_CANONICAL_QUESTION = "QUESTION-" + "B" * 32
LEGACY_RECEIPT = "REVIEW-" + "C" * 32
LEGACY_RETURN_KEY = "LEGACY-RETURN-KEY"
QUESTION = "Which independently fictional source details still need verification?"


def legacy_hash(value):
    """Seal authored v1 fixture data without importing the new review owner."""
    return hashlib.sha256(json.dumps(
        value, sort_keys=True, separators=(",", ":"), ensure_ascii=False,
    ).encode("utf-8")).hexdigest()


class ReviewConvergenceMigrationTests(SourceVersionFixture):
    def rows(self, table, patient):
        with self.engine.connect() as connection:
            return [dict(row) for row in connection.execute(text(
                f"SELECT * FROM investigation.{table} WHERE patient_id=:patient"
            ), {"patient": patient}).mappings()]

    def events(self, patient):
        with self.engine.connect() as connection:
            return [dict(row) for row in connection.execute(text(
                "SELECT * FROM identity.identity_domain_events "
                "WHERE patient_id=:patient ORDER BY id"
            ), {"patient": patient}).mappings()]

    def seed_old_history(self, patient, source_id, fingerprint, *, snapshot_branch):
        created = datetime(2026, 1, 15, 12, 34, 56, tzinfo=timezone.utc)
        source_hash = hashlib.sha256(ORIGINAL.encode("utf-8")).hexdigest()
        queue_hash = legacy_hash({
            "version": LEGACY_QUEUE, "question_id": LEGACY_QUESTION,
            "patient_id": patient, "case_id": "CASE-ALPHA", "question": QUESTION,
            "source_id": source_id, "source_line": 8, "source_sha256": source_hash,
            "source_version": 1, "source_snapshot_sha256": fingerprint,
            "preflight_sha256": "2" * 64,
        })
        with self.engine.begin() as connection:
            def event(kind, metadata):
                connection.execute(text(
                    "INSERT INTO identity.identity_domain_events "
                    "(patient_id,event_type,metadata_json,occurred_at) "
                    "VALUES (:patient,:kind,CAST(:metadata AS jsonb),:created)"
                ), {"patient": patient, "kind": kind,
                    "metadata": json.dumps(metadata), "created": created})

            questions = [(LEGACY_QUESTION, False)]
            if snapshot_branch:
                questions.append((OLD_CANONICAL_QUESTION, True))
            for question_id, canonical in questions:
                # Omitting provenance uses the original snapshot-branch default;
                # the return branch does not have that column at all yet.
                column = ",source_snapshot_contract" if canonical else ""
                value = ",:source_contract" if canonical else ""
                parameters = {
                    "qid": question_id, "patient": patient,
                    "key": "OLD-CANONICAL-QUESTION" if canonical else "OLD-LEGACY-QUESTION",
                    "question": QUESTION, "source": source_id, "source_hash": source_hash,
                    "snapshot": fingerprint, "intent": "1" * 64,
                    "preflight": "2" * 64, "created": created,
                }
                if canonical:
                    parameters["source_contract"] = CANONICAL_SOURCE
                connection.execute(text(
                    "INSERT INTO investigation.source_questions "
                    "(question_id,patient_id,case_id,origin_org,request_key,intent_sha256,"
                    "actor,purpose,question,source_id,source_line,source_sha256,source_version,"
                    "source_snapshot_sha256,preflight_sha256,created_at" + column + ") "
                    "VALUES (:qid,:patient,'CASE-ALPHA','ORG-ALPHA',:key,:intent,"
                    "'ACTOR-ALPHA','operations',:question,:source,8,:source_hash,1,"
                    ":snapshot,:preflight,:created" + value + ")"
                ), parameters)
                metadata = {"question_id": question_id, "case_id": "CASE-ALPHA",
                            "source_id": source_id, "source_line": 8,
                            "source_snapshot_sha256": fingerprint, "actor": "ACTOR-ALPHA"}
                if canonical:
                    metadata["source_snapshot_contract"] = CANONICAL_SOURCE
                event("investigation.question.created", metadata)

            if not snapshot_branch:
                intent = legacy_hash({
                    "patient_id": patient, "case_id": "CASE-ALPHA",
                    "question_id": LEGACY_QUESTION, "organization": "ORG-ALPHA",
                    "actor": "ACTOR-ALPHA", "purpose": "operations",
                    "request_key": LEGACY_RETURN_KEY, "queue_fingerprint": queue_hash,
                    "reason": RETURN_REASON, "action": "returned",
                })
                connection.execute(text(
                    "INSERT INTO investigation.question_review_receipts "
                    "(receipt_id,question_id,patient_id,case_id,origin_org,request_key,"
                    "intent_sha256,queue_fingerprint,source_snapshot_sha256,actor,purpose,"
                    "action,reason,created_at) VALUES (:receipt,:question,:patient,"
                    "'CASE-ALPHA','ORG-ALPHA',:key,:intent,:queue,:snapshot,'ACTOR-ALPHA',"
                    "'operations','returned',:reason,:created)"
                ), {"receipt": LEGACY_RECEIPT, "question": LEGACY_QUESTION,
                    "patient": patient, "key": LEGACY_RETURN_KEY, "intent": intent,
                    "queue": queue_hash, "snapshot": fingerprint,
                    "reason": RETURN_REASON, "created": created})
                event("investigation.review.returned_for_verification", {
                    "case_id": "CASE-ALPHA", "question_id": LEGACY_QUESTION,
                    "receipt_id": LEGACY_RECEIPT, "queue_fingerprint": queue_hash,
                    "actor": "ACTOR-ALPHA",
                })
        return queue_hash

    def assert_old_rows_preserved(self, patient, questions_before, receipts_before):
        questions_after = {row["question_id"]: row for row in self.rows("source_questions", patient)}
        for before in questions_before:
            after = dict(questions_after[before["question_id"]])
            if "source_snapshot_contract" not in before:
                self.assertEqual(after.pop("source_snapshot_contract"), LEGACY_SOURCE)
            self.assertEqual(after, before)
        receipts_after = {row["receipt_id"]: row for row in self.rows("question_review_receipts", patient)}
        for before in receipts_before:
            after = dict(receipts_after[before["receipt_id"]])
            self.assertEqual(after.pop("source_snapshot_contract"), LEGACY_SOURCE)
            self.assertEqual(after.pop("queue_fingerprint_contract"), LEGACY_QUEUE)
            self.assertEqual(after, before)

    def exercise_upgrade(self, starting_revision):
        snapshot_branch = starting_revision == "0007_question_snapshot_contract"
        # Current HTTP readiness correctly requires head. Seed only unchanged
        # patient/source owners there, then establish each real old schema.
        with running_server(create_app(self.settings)) as base:
            patient = self.setup_case(base)
            status, source, _ = self.ingest(base, patient)
            self.assertEqual(status, 201, source)
            prefix = f"/v1/patients/{patient}/cases/CASE-ALPHA"
            status, world, _ = request(base, prefix + "/world-model", token=TOKEN_A)
            self.assertEqual(status, 200, world)
            fingerprint = world["snapshot_fingerprint"]
        migrate(self.admin, "downgrade", "0006_source_questions")
        migrate(self.admin, "upgrade", starting_revision)
        with self.engine.connect() as connection:
            self.assertEqual(connection.execute(text(
                "SELECT version_num FROM public.alembic_version"
            )).scalars().all(), [starting_revision])
            question_columns = set(connection.execute(text(
                "SELECT column_name FROM information_schema.columns "
                "WHERE table_schema='investigation' AND table_name='source_questions'"
            )).scalars())
            self.assertEqual("source_snapshot_contract" in question_columns, snapshot_branch)
        old_queue_hash = self.seed_old_history(
            patient, source["source_id"], fingerprint, snapshot_branch=snapshot_branch
        )
        questions_before = self.rows("source_questions", patient)
        receipts_before = [] if snapshot_branch else self.rows("question_review_receipts", patient)
        events_before = self.events(patient)

        migrate(self.admin, "upgrade", "0008_review_convergence")
        with self.engine.connect() as connection:
            self.assertEqual(connection.execute(text(
                "SELECT version_num FROM public.alembic_version"
            )).scalars().all(), ["0008_review_convergence"])
        self.assert_old_rows_preserved(patient, questions_before, receipts_before)
        self.assertEqual(self.events(patient), events_before)
        self.assertEqual(len(self.rows("question_review_receipts", patient)), len(receipts_before))

        # Preserve the historical merge proof, then satisfy the current API
        # readiness contract without changing any question or review history.
        migrate(self.admin, "upgrade", "head")
        self.creds[0]["actions"].extend(("composer_context_read", "question_create",
                                         "question_read", "review_queue_read", "review_return"))
        self.write()
        with running_server(create_app(self.settings)) as base:
            status, queue, _ = request(base, prefix + "/review-queue", token=TOKEN_A)
            self.assertEqual(status, 200, queue)
            legacy = next(row for row in queue["items"] if row["question_id"] == LEGACY_QUESTION)
            # The hash equals the actual canonical snapshot; contract provenance
            # must independently prevent historical questions becoming current.
            self.assertEqual(legacy["source_snapshot_sha256"], fingerprint)
            self.assertEqual(legacy["source_snapshot_contract"], LEGACY_SOURCE)
            self.assertEqual(legacy["review_state"], "source_reassessment_required")
            self.assertIsNone(legacy["queue_fingerprint"])
            self.assertIsNone(legacy["current_return_receipt_id"])
            self.assertEqual((legacy["return_count"], legacy["prior_return_count"]),
                             (0, len(receipts_before)))
            if snapshot_branch:
                prior_canonical = next(row for row in queue["items"]
                                       if row["question_id"] == OLD_CANONICAL_QUESTION)
                self.assertEqual(prior_canonical["source_snapshot_contract"], CANONICAL_SOURCE)
                self.assertEqual(prior_canonical["review_state"], "awaiting_independent_verification")
            else:
                self.assertEqual(queue["receipts"][0]["source_snapshot_contract"], LEGACY_SOURCE)
                self.assertEqual(queue["receipts"][0]["queue_fingerprint_contract"], LEGACY_QUEUE)

            before_denials = self.events(patient)
            return_url = prefix + f"/questions/{LEGACY_QUESTION}/return-for-verification"
            for key in ("NEW-RETURN-FOR-LEGACY", LEGACY_RETURN_KEY) if receipts_before else ("NEW-RETURN-FOR-LEGACY",):
                status, denied, _ = request(base, return_url, token=TOKEN_A, body={
                    "synthetic": True, "request_key": key,
                    "expected_queue_fingerprint": old_queue_hash, "reason": RETURN_REASON,
                })
                self.assertEqual(status, 409, denied)
            self.assertEqual(self.events(patient), before_denials)
            self.assertEqual(len(self.rows("question_review_receipts", patient)), len(receipts_before))

            new_question, _ = create_question(
                self, base, patient, source["source_id"], request_key="QUESTION-AFTER-MERGE"
            )
            status, current, _ = request(base, prefix + "/review-queue", token=TOKEN_A)
            self.assertEqual(status, 200, current)
            item = next(row for row in current["items"] if row["question_id"] == new_question)
            self.assertEqual(item["source_snapshot_contract"], CANONICAL_SOURCE)
            self.assertEqual(item["queue_fingerprint_contract"], CANONICAL_QUEUE)
            status, saved, _ = request(
                base, prefix + f"/questions/{new_question}/return-for-verification",
                token=TOKEN_A, body={
                    "synthetic": True, "request_key": "CANONICAL-RETURN-AFTER-MERGE",
                    "expected_queue_fingerprint": item["queue_fingerprint"], "reason": RETURN_REASON,
                },
            )
            self.assertEqual(status, 201, saved)
            new_receipt = next(row for row in self.rows("question_review_receipts", patient)
                               if row["receipt_id"] == saved["receipt_id"])
            self.assertEqual(new_receipt["source_snapshot_contract"], CANONICAL_SOURCE)
            self.assertEqual(new_receipt["queue_fingerprint_contract"], CANONICAL_QUEUE)
            self.assertNotEqual(new_receipt["receipt_id"], LEGACY_RECEIPT)
        self.assert_old_rows_preserved(patient, questions_before, receipts_before)
        self.assertEqual(self.events(patient)[:len(events_before)], events_before)

    def test_upgrade_from_original_snapshot_contract_history(self):
        self.exercise_upgrade("0007_question_snapshot_contract")

    def test_upgrade_from_original_review_return_history(self):
        self.exercise_upgrade("0007_question_review_returns")


if __name__ == "__main__":
    unittest.main()
