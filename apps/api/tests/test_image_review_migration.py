"""Join the published image/question and review histories without rewriting either."""

from pathlib import Path
import unittest

from alembic.config import Config
from alembic.script import ScriptDirectory
from alembic.util.exc import CommandError
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError

from oi_api.contracts import SCHEMA_REVISION
from oi_api.migrate import migrate
from test_migration_convergence import (
    FIXTURE_TIME, PATIENT_ID, TABLE_ORDER, PopulatedMigrationFixture,
)


API_ROOT = Path(__file__).resolve().parents[1]
MERGE_REVISION = "0009_image_review_merge"
IMAGE_QUESTION_REVISION = "0008_merge_image_questions"
REVIEW_REVISION = "0008_review_convergence"
QUESTION_ID = "QUESTION-" + "C" * 32
RECEIPT_ID = "REVIEW-" + "D" * 32


class ImageReviewMigrationGraphTests(unittest.TestCase):
    def test_published_image_review_merge_preserves_both_original_owner_histories(self):
        script = ScriptDirectory.from_config(Config(str(API_ROOT / "alembic.ini")))
        self.assertEqual(script.get_revision(MERGE_REVISION).down_revision,
                         (IMAGE_QUESTION_REVISION, REVIEW_REVISION))
        self.assertEqual(script.get_revision(IMAGE_QUESTION_REVISION).down_revision,
                         ("0007_question_snapshot_contract", "0006_image_custody"))
        self.assertEqual(script.get_revision(REVIEW_REVISION).down_revision,
                         ("0007_question_snapshot_contract", "0007_question_review_returns"))


class PopulatedImageReviewFixture(PopulatedMigrationFixture):
    """Actual PG16 full-row preservation from both immutable published heads.

    Parent readiness intentionally refuses the current application, so fixtures
    are authored through each parent's unchanged SQL constraints and triggers.
    API lifecycle and semantic fingerprints have their separate HTTP acceptance.
    """

    table_order = {
        **TABLE_ORDER,
        "investigation.question_review_receipts": "receipt_id",
    }

    def _seed_return(self):
        with self.engine.begin() as connection:
            connection.execute(text(
                "INSERT INTO investigation.question_review_receipts "
                "(receipt_id,question_id,patient_id,case_id,origin_org,request_key,"
                "intent_sha256,queue_fingerprint,source_snapshot_sha256,actor,purpose,"
                "action,reason,source_snapshot_contract,queue_fingerprint_contract,created_at) "
                "VALUES (:receipt,:question,:patient,'CASE-MERGE','ORG-MERGE',"
                "'REVIEW-MERGE-REQUEST',:intent,:queue,:snapshot,'ACTOR-MERGE',"
                "'operations','returned','Independently verify this authored fictional source.',"
                "'oi.pg-source-world-model/1','oi.synthetic-source-review-return/2',:created)"
            ), {"receipt": RECEIPT_ID, "question": QUESTION_ID, "patient": PATIENT_ID,
                "intent": "5" * 64, "queue": "6" * 64, "snapshot": "3" * 64,
                "created": FIXTURE_TIME})
            self._event(
                connection, "investigation.review.returned_for_verification",
                question_id=QUESTION_ID, receipt_id=RECEIPT_ID,
                source_snapshot_sha256="3" * 64,
                source_snapshot_contract="oi.pg-source-world-model/1",
                queue_fingerprint="6" * 64,
                queue_fingerprint_contract="oi.synthetic-source-review-return/2",
            )

    def _assert_review_guards(self):
        before = self._snapshot()
        for statement in (
            "UPDATE investigation.question_review_receipts SET reason='Changed fictional history.'",
            "DELETE FROM investigation.question_review_receipts",
        ):
            with self.subTest(statement=statement), self.assertRaises(SQLAlchemyError):
                with self.engine.begin() as connection:
                    connection.execute(text(statement))

        # These values satisfy the table's contract-pair CHECK. The original
        # insert guard must independently reject another organization and a
        # legacy contract applied to a canonical question after the merge.
        for organization, source_contract, queue_contract in (
            ("ORG-OTHER", "oi.pg-source-world-model/1", "oi.synthetic-source-review-return/2"),
            ("ORG-MERGE", "oi.synthetic-postgres-world-model-sources/1",
             "oi.synthetic-source-review-return/1"),
        ):
            with self.subTest(organization=organization, source_contract=source_contract):
                with self.assertRaises(SQLAlchemyError):
                    with self.engine.begin() as connection:
                        connection.execute(text(
                            "INSERT INTO investigation.question_review_receipts "
                            "(receipt_id,question_id,patient_id,case_id,origin_org,request_key,"
                            "intent_sha256,queue_fingerprint,source_snapshot_sha256,actor,purpose,"
                            "action,reason,source_snapshot_contract,queue_fingerprint_contract) "
                            "SELECT :receipt,question_id,patient_id,case_id,:organization,"
                            "'FORGED-MERGE-RETURN',intent_sha256,queue_fingerprint,"
                            "source_snapshot_sha256,actor,purpose,action,reason,"
                            ":source_contract,:queue_contract "
                            "FROM investigation.question_review_receipts WHERE receipt_id=:original"
                        ), {"receipt": "REVIEW-" + "E" * 32, "organization": organization,
                            "source_contract": source_contract, "queue_contract": queue_contract,
                            "original": RECEIPT_ID})
        self.assertEqual(self._snapshot(), before)


class PopulatedImageReviewUpgradeTests(PopulatedImageReviewFixture):
    def _seed_parent(self, revision):
        migrate(self.settings, "upgrade", revision)
        self.assertEqual(self._heads(), {revision})
        self._seed_common()
        self._seed_questions()
        if revision == IMAGE_QUESTION_REVISION:
            self._seed_image()
        else:
            self._seed_return()
        self._assert_readiness(False)

    def _upgrade_populated_parent(self, revision):
        self._seed_parent(revision)
        missing = (("investigation.question_review_receipts",)
                   if revision == IMAGE_QUESTION_REVISION else
                   ("clinical_source.dicom_objects", "clinical_source.source_image_links"))
        before = self._snapshot()
        self.assertTrue(all(table not in before for table in missing))

        migrate(self.settings, "upgrade", MERGE_REVISION)
        self.assertEqual(self._heads(), {MERGE_REVISION})
        self.assertEqual(self._snapshot(before), before)
        after = self._snapshot()
        for table in missing:
            self.assertEqual(after[table], [])
        self._assert_readiness(False)
        migrate(self.settings, "upgrade", "head")
        self.assertEqual(self._heads(), {SCHEMA_REVISION})
        self.assertEqual(self._snapshot(), after)
        self._assert_readiness(True)

        if revision == IMAGE_QUESTION_REVISION:
            self._seed_return()
        else:
            self._seed_image()
        self._assert_immutable_owners()
        self._assert_review_guards()

    def test_populated_image_question_head_preserves_original_rows_and_adds_review_owner(self):
        self._upgrade_populated_parent(IMAGE_QUESTION_REVISION)

    def test_populated_review_head_preserves_original_rows_and_adds_image_owner(self):
        self._upgrade_populated_parent(REVIEW_REVISION)

    def test_two_populated_published_heads_remain_unready_until_explicit_merge(self):
        self._seed_parent(REVIEW_REVISION)
        migrate(self.settings, "upgrade", IMAGE_QUESTION_REVISION)
        self._seed_image()
        self.assertEqual(self._heads(), {IMAGE_QUESTION_REVISION, REVIEW_REVISION})
        self._assert_readiness(False)
        before = self._snapshot()

        migrate(self.settings, "upgrade", MERGE_REVISION)
        self.assertEqual(self._heads(), {MERGE_REVISION})
        self.assertEqual(self._snapshot(), before)
        self._assert_readiness(False)
        migrate(self.settings, "upgrade", "head")
        self.assertEqual(self._heads(), {SCHEMA_REVISION})
        self.assertEqual(self._snapshot(), before)
        self._assert_readiness(True)
        self._assert_immutable_owners()
        self._assert_review_guards()

    def test_unknown_review_owner_rolls_back_without_advancing_image_question_head(self):
        self._seed_parent(IMAGE_QUESTION_REVISION)
        before = self._snapshot()
        with self.engine.begin() as connection:
            connection.execute(text(
                "CREATE TABLE investigation.question_review_receipts (legacy text)"
            ))
            connection.execute(text(
                "INSERT INTO investigation.question_review_receipts VALUES ('AUTHORED-LEGACY-REVIEW')"
            ))

        with self.assertRaises(CommandError):
            migrate(self.settings, "upgrade", "head")
        self.assertEqual(self._heads(), {IMAGE_QUESTION_REVISION})
        self.assertEqual(self._snapshot(before), before)
        with self.engine.connect() as connection:
            self.assertEqual(connection.execute(text(
                "SELECT legacy FROM investigation.question_review_receipts"
            )).scalar_one(), "AUTHORED-LEGACY-REVIEW")
            self.assertIsNone(connection.execute(text(
                "SELECT to_regprocedure('investigation.guard_review_return_insert()')"
            )).scalar_one())
        self._assert_readiness(False)

    def test_unknown_image_owner_rolls_back_without_advancing_review_head(self):
        self._seed_parent(REVIEW_REVISION)
        before = self._snapshot()
        with self.engine.begin() as connection:
            connection.execute(text("CREATE TABLE clinical_source.dicom_objects (legacy text)"))
            connection.execute(text(
                "INSERT INTO clinical_source.dicom_objects VALUES ('AUTHORED-LEGACY-IMAGE')"
            ))

        with self.assertRaises(CommandError):
            migrate(self.settings, "upgrade", "head")
        self.assertEqual(self._heads(), {REVIEW_REVISION})
        self.assertEqual(self._snapshot(before), before)
        with self.engine.connect() as connection:
            self.assertEqual(connection.execute(text(
                "SELECT legacy FROM clinical_source.dicom_objects"
            )).scalar_one(), "AUTHORED-LEGACY-IMAGE")
            self.assertIsNone(connection.execute(text(
                "SELECT to_regclass('clinical_source.source_image_links')"
            )).scalar_one())
        self._assert_readiness(False)

    def test_review_provenance_guard_rolls_back_downgrade_of_combined_head(self):
        self._seed_parent(REVIEW_REVISION)
        # Keep this proof on the last pre-outbox head so the intended review
        # provenance guard, rather than a newer owner, must reject downgrade.
        migrate(self.settings, "upgrade", "0019_composer_runs")
        self._seed_image()
        before = self._snapshot()

        with self.assertRaisesRegex(CommandError, "Canonical review history"):
            migrate(self.settings, "downgrade", "0005_source_versions")
        self.assertEqual(self._heads(), {"0019_composer_runs"})
        self.assertEqual(self._snapshot(), before)
        self._assert_readiness(False)


if __name__ == "__main__":
    unittest.main()
