"""Actual PG16 ownership, reversible empty migration and dependency guards."""

from alembic.util.exc import CommandError
from sqlalchemy import inspect, text
from sqlalchemy.exc import SQLAlchemyError

from oi_api.migrate import migrate
from test_source_versions import SourceVersionFixture


class ImageMigrationTests(SourceVersionFixture):
    def test_empty_downgrade_reupgrade_preserves_other_owner_objects(self):
        with self.engine.begin() as connection:
            connection.execute(text("CREATE TABLE clinical_source.oi_unrelated_image_fixture(id integer)"))
            connection.execute(text("INSERT INTO clinical_source.oi_unrelated_image_fixture VALUES(42)"))
        migrate(self.admin, "downgrade", "0005_source_versions")
        names = set(inspect(self.engine).get_table_names(schema="clinical_source"))
        self.assertNotIn("dicom_objects", names)
        self.assertEqual(names, {"source_versions", "assertions", "quarantine", "oi_unrelated_image_fixture"})
        migrate(self.admin, "upgrade", "head")
        with self.engine.connect() as connection:
            self.assertEqual(connection.execute(text("SELECT id FROM clinical_source.oi_unrelated_image_fixture")).scalar_one(), 42)
            self.assertEqual(connection.execute(text("SELECT version_num FROM public.alembic_version")).scalar_one(), "0006_image_custody")

    def test_conflicting_image_table_is_preserved_without_silent_adoption(self):
        migrate(self.admin, "downgrade", "0005_source_versions")
        with self.engine.begin() as connection:
            connection.execute(text("CREATE TABLE clinical_source.dicom_objects(legacy text)"))
            connection.execute(text("INSERT INTO clinical_source.dicom_objects VALUES('AUTHORED-LEGACY')"))
        with self.assertRaises(CommandError):
            migrate(self.admin, "upgrade", "head")
        with self.engine.connect() as connection:
            self.assertEqual(connection.execute(text("SELECT legacy FROM clinical_source.dicom_objects")).scalar_one(), "AUTHORED-LEGACY")
            self.assertEqual(connection.execute(text("SELECT version_num FROM public.alembic_version")).scalar_one(), "0005_source_versions")

    def test_unknown_dependency_prevents_partial_downgrade(self):
        with self.engine.begin() as connection:
            connection.execute(text("CREATE TABLE clinical_source.oi_other_image_reference(image_id text REFERENCES clinical_source.dicom_objects(image_id))"))
        with self.assertRaises(SQLAlchemyError):
            migrate(self.admin, "downgrade", "0005_source_versions")
        with self.engine.connect() as connection:
            self.assertEqual(connection.execute(text("SELECT version_num FROM public.alembic_version")).scalar_one(), "0006_image_custody")
        self.assertIn("source_image_links", inspect(self.engine).get_table_names(schema="clinical_source"))
