"""Converge published question and image owners without replacing either history."""

from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import unittest

from alembic.config import Config
from alembic.script import ScriptDirectory
from alembic.util.exc import CommandError
from sqlalchemy import text
from sqlalchemy.engine import make_url
from sqlalchemy.exc import SQLAlchemyError

from oi_api.config import Settings
from oi_api.contracts import SCHEMA_REVISION
from oi_api.database import Database, make_engine
from oi_api.migrate import migrate
from dicom_integrity_fixture import dicom_bytes


MERGE_REVISION = "0008_merge_image_questions"
QUESTION_REVISION = "0007_question_snapshot_contract"
IMAGE_REVISION = "0006_image_custody"
API_ROOT = Path(__file__).resolve().parents[1]
PATIENT_ID = "PAT-" + "A" * 32
SOURCE_ID = "SRC-" + "A" * 32
IMAGE_ID = "IMG-" + "A" * 32
FIXTURE_TIME = datetime(2026, 5, 18, 12, 34, 56, tzinfo=timezone.utc)
ORIGINAL = (
    b"OI-SYNTHETIC-REPORT/1\nPatient: CASE-MERGE\nDocument: DOC-MERGE\n"
    b"Type: imaging\nEvent-Date: 2026-05-17\nIssued-At: 2026-05-18\n"
    b"Finding: image|not-assessed|Independently authored fictional image report.\n"
)
TABLE_ORDER = {
    "identity.identity_patients": "patient_id",
    "identity.identity_create_receipts": "origin_org,request_key",
    "identity.identity_domain_events": "id",
    "coordination.patient_case_bindings": "case_id",
    "clinical_source.source_versions": "source_id",
    "clinical_source.assertions": "assertion_id",
    "clinical_source.quarantine": "quarantine_id",
    "investigation.source_questions": "question_id",
    "clinical_source.dicom_objects": "image_id",
    "clinical_source.source_image_links": "source_id,image_id",
}


class MigrationConvergenceGraphTests(unittest.TestCase):
    def test_published_image_question_merge_preserves_its_original_parents(self):
        script = ScriptDirectory.from_config(Config(str(API_ROOT / "alembic.ini")))
        self.assertEqual(script.get_revision(MERGE_REVISION).down_revision,
                         (QUESTION_REVISION, IMAGE_REVISION))
        self.assertEqual(script.get_revision(QUESTION_REVISION).down_revision,
                         "0006_source_questions")
        self.assertEqual(script.get_revision("0006_source_questions").down_revision,
                         "0005_source_versions")
        self.assertEqual(script.get_revision(IMAGE_REVISION).down_revision,
                         "0005_source_versions")


@unittest.skipUnless(os.environ.get("OI_API_RUN_DATABASE_TESTS") == "1",
                     "Requires a disposable actual PostgreSQL 16 test database")
class PopulatedMigrationFixture(unittest.TestCase):
    """Seed the actual published schemas, never stamp or relax app readiness.

    The current app correctly refuses either parent revision. Direct SQL here is
    an explicitly authored migration fixture using each parent's real constraints;
    it is not a replacement application writer or an authorization workaround.
    """

    table_order = TABLE_ORDER

    @classmethod
    def setUpClass(cls):
        url = os.environ.get("OI_API_TEST_DATABASE_URL", "")
        try:
            name = make_url(url).database
        except Exception:
            raise RuntimeError("A disposable migration test database is required") from None
        if not name or not name.startswith("oi_api_test_"):
            raise RuntimeError("Migration tests require an oi_api_test_ database")
        cls.settings = Settings(database_url=url)
        cls.engine = make_engine(cls.settings)
        with cls.engine.connect() as connection:
            version = int(connection.execute(text("SHOW server_version_num")).scalar_one())
        if version // 10000 != 16:
            cls.engine.dispose()
            raise RuntimeError("Migration acceptance requires actual PostgreSQL 16")

    @classmethod
    def tearDownClass(cls):
        cls.engine.dispose()

    def _remove_owned_fixtures(self):
        # Reuse the explicit RESTRICT cleanup for both owners. Unexpected
        # dependencies stop cleanup; no broad namespace CASCADE is added.
        from test_migrations import PostgreSQLIntegrationTests
        PostgreSQLIntegrationTests.remove_owned_fixtures(self)

    def setUp(self):
        self._remove_owned_fixtures()
        self.probe = Database(self.settings)
        self.addCleanup(self.probe.close)

    def tearDown(self):
        self._remove_owned_fixtures()

    def _heads(self):
        with self.engine.connect() as connection:
            return set(connection.execute(text(
                "SELECT version_num FROM public.alembic_version"
            )).scalars())

    def _assert_readiness(self, ready):
        self.assertEqual(self.probe.check().status,
                         "ready" if ready else "schema_mismatch")
        if ready:
            with self.probe.registry_connection() as connection:
                cursor = connection.cursor()
                try:
                    cursor.execute("SELECT version_num FROM public.alembic_version")
                    self.assertEqual([tuple(row) for row in cursor.fetchall()],
                                     [(SCHEMA_REVISION,)])
                finally:
                    cursor.close()
        else:
            with self.assertRaisesRegex(RuntimeError, "Unsupported migration state"):
                with self.probe.registry_connection():
                    self.fail("A prior or split head must not admit domain operations")

    def _snapshot(self, tables=None):
        result = {}
        with self.engine.connect() as connection:
            for table in self.table_order if tables is None else tables:
                if connection.execute(text("SELECT to_regclass(:table)"),
                                      {"table": table}).scalar_one() is not None:
                    rows = connection.execute(text(
                        f"SELECT * FROM {table} ORDER BY {self.table_order[table]}"
                    )).mappings()
                    result[table] = [
                        {key: bytes(value) if isinstance(value, memoryview) else value
                         for key, value in row.items()} for row in rows
                    ]
        return result

    def _event(self, connection, kind, **details):
        connection.execute(text(
            "INSERT INTO identity.identity_domain_events "
            "(patient_id,event_type,metadata_json,occurred_at) "
            "VALUES (:patient,:kind,CAST(:details AS jsonb),:created)"
        ), {"patient": PATIENT_ID, "kind": kind, "details": json.dumps(details),
            "created": FIXTURE_TIME})

    def _seed_common(self):
        with self.engine.begin() as connection:
            connection.execute(text(
                "INSERT INTO identity.identity_patients "
                "(patient_id,origin_org,created_at,created_by) "
                "VALUES (:patient,'ORG-MERGE',:created,'ACTOR-MERGE')"
            ), {"patient": PATIENT_ID, "created": FIXTURE_TIME})
            connection.execute(text(
                "INSERT INTO identity.identity_create_receipts "
                "(origin_org,request_key,request_digest,patient_id,created_at) "
                "VALUES ('ORG-MERGE','CREATE-MERGE',:digest,:patient,:created)"
            ), {"digest": "1" * 64, "patient": PATIENT_ID, "created": FIXTURE_TIME})
            connection.execute(text(
                "INSERT INTO coordination.patient_case_bindings "
                "(case_id,patient_id,origin_org,source_organization,source_system,"
                "source_subject_ref,review_ref,created_by,purpose,created_at) "
                "VALUES ('CASE-MERGE',:patient,'ORG-MERGE','ORG-INSTITUTION',"
                "'SYS-SYNTH','SYNTHETIC-MERGE','REVIEW-MERGE','ACTOR-MERGE',"
                "'operations',:created)"
            ), {"patient": PATIENT_ID, "created": FIXTURE_TIME})
            connection.execute(text(
                "INSERT INTO clinical_source.source_versions "
                "(source_id,case_id,document_id,version,sha256,raw,kind,event_date,"
                "issued_at,received_at,state) VALUES (:source,'CASE-MERGE',"
                "'DOC-MERGE',1,:sha,:raw,'imaging','2026-05-17','2026-05-18',"
                ":created,'current')"
            ), {"source": SOURCE_ID, "sha": hashlib.sha256(ORIGINAL).hexdigest(),
                "raw": ORIGINAL, "created": FIXTURE_TIME})
            connection.execute(text(
                "INSERT INTO clinical_source.assertions "
                "(source_id,finding_key,certainty,quote,source_line) "
                "VALUES (:source,'image','not-assessed',"
                "'Independently authored fictional image report.',7)"
            ), {"source": SOURCE_ID})
            self._event(connection, "identity.patient.created", actor="ACTOR-MERGE")
            self._event(connection, "identity.case_binding_created", case_id="CASE-MERGE")
            self._event(connection, "source.original.imported", source_id=SOURCE_ID,
                        case_id="CASE-MERGE", version=1, actor="ACTOR-MERGE")

    def _seed_questions(self):
        with self.engine.begin() as connection:
            for marker, contract in (
                ("B", "oi.synthetic-postgres-world-model-sources/1"),
                ("C", "oi.pg-source-world-model/1"),
            ):
                question_id = "QUESTION-" + marker * 32
                connection.execute(text(
                    "INSERT INTO investigation.source_questions "
                    "(question_id,patient_id,case_id,origin_org,request_key,intent_sha256,"
                    "actor,purpose,question,source_id,source_line,source_sha256,source_version,"
                    "source_snapshot_sha256,preflight_sha256,source_snapshot_contract,created_at) "
                    "VALUES (:question_id,:patient,'CASE-MERGE','ORG-MERGE',:request,:intent,"
                    "'ACTOR-MERGE','operations','What remains unresolved in this fictional source?',"
                    ":source,7,:source_sha,1,:snapshot,:preflight,:contract,:created)"
                ), {"question_id": question_id, "patient": PATIENT_ID,
                    "request": "QUESTION-MERGE-" + marker, "intent": "2" * 64,
                    "source": SOURCE_ID, "source_sha": hashlib.sha256(ORIGINAL).hexdigest(),
                    "snapshot": "3" * 64, "preflight": "4" * 64,
                    "contract": contract, "created": FIXTURE_TIME})
                self._event(connection, "investigation.question.created", question_id=question_id,
                            source_snapshot_sha256="3" * 64, source_snapshot_contract=contract)

    def _seed_image(self):
        raw = dicom_bytes(patient_id="SYNTHETIC-MERGE", issuer="ORG-INSTITUTION/SYS-SYNTH")
        with self.engine.begin() as connection:
            connection.execute(text(
                "INSERT INTO clinical_source.dicom_objects "
                "(image_id,case_id,raw,sha256,byte_count,patient_id,issuer,study_uid,"
                "series_uid,sop_uid,sop_class_uid,transfer_syntax_uid,study_date,modality,"
                "rows,columns,created_at) VALUES (:image,'CASE-MERGE',:raw,:sha,:size,"
                "'SYNTHETIC-MERGE','ORG-INSTITUTION/SYS-SYNTH','2.25.11001','2.25.11002',"
                "'2.25.11003','1.2.840.10008.5.1.4.1.1.2','1.2.840.10008.1.2.1',"
                "'2026-05-17','CT',2,2,:created)"
            ), {"image": IMAGE_ID, "raw": raw, "sha": hashlib.sha256(raw).hexdigest(),
                "size": len(raw), "created": FIXTURE_TIME})
            connection.execute(text(
                "INSERT INTO clinical_source.source_image_links (source_id,image_id,created_at) "
                "VALUES (:source,:image,:created)"
            ), {"source": SOURCE_ID, "image": IMAGE_ID, "created": FIXTURE_TIME})
            self._event(connection, "image.original.imported", source_id=SOURCE_ID, image_id=IMAGE_ID)

    def _assert_immutable_owners(self):
        before = self._snapshot()
        for statement in (
            "UPDATE clinical_source.source_versions SET sha256=repeat('0',64)",
            "DELETE FROM clinical_source.assertions",
            "UPDATE investigation.source_questions SET question='Rewritten fictional history'",
            "DELETE FROM investigation.source_questions",
            "UPDATE clinical_source.dicom_objects SET sha256=repeat('0',64)",
            "DELETE FROM clinical_source.source_image_links",
            "DELETE FROM identity.identity_domain_events",
        ):
            with self.subTest(statement=statement), self.assertRaises(SQLAlchemyError):
                with self.engine.begin() as connection:
                    connection.execute(text(statement))
        self.assertEqual(self._snapshot(), before)


class PopulatedBranchUpgradeTests(PopulatedMigrationFixture):
    def _upgrade_from(self, parent):
        migrate(self.settings, "upgrade", parent)
        self.assertEqual(self._heads(), {parent})
        self._seed_common()
        if parent == QUESTION_REVISION:
            self._seed_questions()
            missing = ("clinical_source.dicom_objects", "clinical_source.source_image_links")
        else:
            self._seed_image()
            missing = ("investigation.source_questions",)
        before = self._snapshot()
        self.assertTrue(all(table not in before for table in missing))
        self._assert_readiness(False)

        # Keep the original published merge proof separate from current
        # application readiness, which also requires review, tasks and evidence.
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

        # Both owners remain usable and immutable after the missing branch is
        # applied. Adding its first record does not replace the prior owner.
        if parent == QUESTION_REVISION:
            self._seed_image()
        else:
            self._seed_questions()
        self._assert_immutable_owners()

    def test_populated_question_head_preserves_sources_questions_and_events(self):
        self._upgrade_from(QUESTION_REVISION)

    def test_populated_image_head_preserves_sources_images_links_and_events(self):
        self._upgrade_from(IMAGE_REVISION)

    def test_both_populated_owner_heads_require_the_explicit_merge(self):
        migrate(self.settings, "upgrade", QUESTION_REVISION)
        self._seed_common()
        self._seed_questions()
        migrate(self.settings, "upgrade", IMAGE_REVISION)
        self._seed_image()
        self.assertEqual(self._heads(), {QUESTION_REVISION, IMAGE_REVISION})
        before = self._snapshot()
        self._assert_readiness(False)
        migrate(self.settings, "upgrade", MERGE_REVISION)
        self.assertEqual(self._heads(), {MERGE_REVISION})
        self.assertEqual(self._snapshot(), before)
        self._assert_readiness(False)
        migrate(self.settings, "upgrade", "head")
        self.assertEqual(self._heads(), {SCHEMA_REVISION})
        self.assertEqual(self._snapshot(), before)
        self._assert_readiness(True)
        self._assert_immutable_owners()

    def test_conflicting_image_owner_rolls_back_without_advancing_question_head(self):
        migrate(self.settings, "upgrade", QUESTION_REVISION)
        self._seed_common()
        self._seed_questions()
        before = self._snapshot()
        with self.engine.begin() as connection:
            connection.execute(text("CREATE TABLE clinical_source.dicom_objects (legacy text)"))
            connection.execute(text("INSERT INTO clinical_source.dicom_objects VALUES ('AUTHORED-LEGACY')"))
        with self.assertRaises(CommandError):
            migrate(self.settings, "upgrade", "head")
        self.assertEqual(self._heads(), {QUESTION_REVISION})
        self.assertEqual(self._snapshot(before), before)
        with self.engine.connect() as connection:
            self.assertEqual(connection.execute(text(
                "SELECT legacy FROM clinical_source.dicom_objects"
            )).scalar_one(), "AUTHORED-LEGACY")
            self.assertIsNone(connection.execute(text(
                "SELECT to_regclass('clinical_source.source_image_links')"
            )).scalar_one())
        self._assert_readiness(False)


if __name__ == "__main__":
    unittest.main()
