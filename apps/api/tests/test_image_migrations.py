"""Actual PG16 ownership, reversible empty migration and dependency guards."""

from alembic.util.exc import CommandError
from sqlalchemy import inspect, text
from sqlalchemy.exc import SQLAlchemyError

from oi_api.app import create_app
from oi_api.contracts import SCHEMA_REVISION
from oi_api.migrate import migrate
from http_support import running_server
from test_image_custody import REPORT, image_bytes, image_request
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
            self.assertEqual(connection.execute(text("SELECT version_num FROM public.alembic_version")).scalar_one(), SCHEMA_REVISION)

    def test_ct_survives_upgrade_and_mr_blocks_downgrade_without_mutating_history(self):
        previous = "0022_lab_citation_source_scope"
        self.creds[0]["actions"].extend(("image_import", "image_read", "image_original_read"))
        self.write()
        ct = image_bytes()
        with running_server(create_app(self.settings)) as base:
            patient = self.setup_case(base)
            source = self.ingest(base, patient, REPORT)[1]["source_id"]
            path = self.url(patient) + "/" + source + "/images"
            status, receipt, _ = image_request(base, path, raw=ct)
            self.assertEqual(status, 201, receipt)
            ct_id = receipt["image_id"]

        def snapshot():
            with self.engine.connect() as connection:
                return tuple(connection.execute(text(sql)).all() for sql in (
                    "SELECT * FROM clinical_source.dicom_objects ORDER BY image_id",
                    "SELECT * FROM clinical_source.source_image_links ORDER BY source_id,image_id",
                    "SELECT * FROM identity.identity_domain_events ORDER BY id",
                ))

        with_ct = snapshot()
        migrate(self.admin, "downgrade", previous)
        self.assertEqual(snapshot(), with_ct)
        migrate(self.admin, "upgrade", SCHEMA_REVISION)
        self.assertEqual(snapshot(), with_ct)
        with running_server(create_app(self.settings)) as base:
            self.assertEqual(image_request(base, path + "/" + ct_id)[:2], (200, ct))
            mr = image_bytes(modality="MR", series_uid="2.25.121", sop_uid="2.25.122")
            status, mr_receipt, _ = image_request(base, path, raw=mr)
            self.assertEqual(status, 201, mr_receipt)

        # A direct insert cannot pair the MR class with a CT series modality.
        with self.assertRaisesRegex(SQLAlchemyError, "dicom_objects_storage_modality_check"):
            with self.engine.begin() as connection:
                connection.execute(text("""
                    INSERT INTO clinical_source.dicom_objects (
                        image_id, case_id, raw, sha256, byte_count, patient_id, issuer,
                        study_uid, series_uid, sop_uid, sop_class_uid, transfer_syntax_uid,
                        study_date, modality, rows, columns
                    ) SELECT 'IMG-' || repeat('F',32), case_id, raw, sha256, byte_count,
                        patient_id, issuer, study_uid, series_uid, '2.25.123', sop_class_uid,
                        transfer_syntax_uid, study_date, 'CT', rows, columns
                      FROM clinical_source.dicom_objects WHERE image_id=:mr_id
                """), {"mr_id": mr_receipt["image_id"]})
        with_mr = snapshot()
        with self.assertRaisesRegex(CommandError, "MR originals are in custody"):
            migrate(self.admin, "downgrade", previous)
        self.assertEqual(snapshot(), with_mr)
        with self.engine.connect() as connection:
            self.assertEqual(connection.execute(text("SELECT version_num FROM public.alembic_version"))
                             .scalar_one(), SCHEMA_REVISION)
        with running_server(create_app(self.settings)) as base:
            self.assertEqual(image_request(base, path + "/" + mr_receipt["image_id"])[:2], (200, mr))

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
            self.assertEqual(connection.execute(text("SELECT version_num FROM public.alembic_version")).scalar_one(), SCHEMA_REVISION)
        self.assertIn("source_image_links", inspect(self.engine).get_table_names(schema="clinical_source"))
