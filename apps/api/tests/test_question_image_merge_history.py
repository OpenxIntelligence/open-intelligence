"""Actual PostgreSQL 16 migration graph acceptance for published H1 sibling owners.

Do not rewrite the independent 0006_source_questions and 0006_image_custody
revisions. 0007_question_snapshot_contract remains a required ancestor.
Tests use the same disposable source-owned database fixture as the H1 API.
"""
from sqlalchemy import inspect, text

from oi_api.migrate import migrate
from test_source_versions import SourceVersionFixture


MERGED = "0008_questions_images_merge"


class QuestionImageMergeHistoryTests(SourceVersionFixture):
    def assert_combined(self):
        with self.engine.connect() as connection:
            revisions = connection.execute(text(
                "SELECT version_num FROM public.alembic_version"
            )).scalars().all()
            self.assertEqual(revisions, [MERGED])
            self.assertEqual(connection.execute(text(
                "SELECT count(*) FROM information_schema.columns "
                "WHERE table_schema='investigation' AND table_name='source_questions' "
                "AND column_name='source_snapshot_contract'"
            )).scalar_one(), 1)
        self.assertIn("source_questions", inspect(self.engine).get_table_names(schema="investigation"))
        self.assertIn("dicom_objects", inspect(self.engine).get_table_names(schema="clinical_source"))
        self.assertIn("source_image_links", inspect(self.engine).get_table_names(schema="clinical_source"))

    def test_both_original_migration_branches_have_one_explicit_head(self):
        self.assert_combined()
        from oi_api.contracts import SCHEMA_REVISION
        self.assertEqual(SCHEMA_REVISION, MERGED)

    def test_already_applied_image_owner_upgrades_without_adoption_or_renaming(self):
        migrate(self.admin, "downgrade", "0005_source_versions")
        migrate(self.admin, "upgrade", "0006_image_custody")
        with self.engine.connect() as connection:
            self.assertEqual(connection.execute(text(
                "SELECT version_num FROM public.alembic_version"
            )).scalar_one(), "0006_image_custody")
        self.assertNotIn("source_questions", inspect(self.engine).get_table_names(schema="investigation"))
        self.assertIn("dicom_objects", inspect(self.engine).get_table_names(schema="clinical_source"))
        migrate(self.admin, "upgrade", "head")
        self.assert_combined()

    def test_already_applied_question_owner_upgrades_without_adoption_or_renaming(self):
        migrate(self.admin, "downgrade", "0005_source_versions")
        migrate(self.admin, "upgrade", "0007_question_snapshot_contract")
        with self.engine.connect() as connection:
            self.assertEqual(connection.execute(text(
                "SELECT version_num FROM public.alembic_version"
            )).scalar_one(), "0007_question_snapshot_contract")
        self.assertIn("source_questions", inspect(self.engine).get_table_names(schema="investigation"))
        self.assertNotIn("dicom_objects", inspect(self.engine).get_table_names(schema="clinical_source"))
        migrate(self.admin, "upgrade", "head")
        self.assert_combined()
