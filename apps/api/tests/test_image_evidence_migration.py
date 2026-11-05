"""Preserve the published image and question-evidence owners at one ready head."""

from contextlib import contextmanager
from datetime import timedelta
import hashlib
from pathlib import Path
import unittest

from alembic.config import Config
from alembic.script import ScriptDirectory
from alembic.util.exc import CommandError
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError

from oi_api.contracts import SCHEMA_REVISION
from oi_api.evidence_catalog import (
    append_rights_decision, fictional_records, seed_fictional_records,
)
from oi_api.migrate import migrate
from open_intelligence.postgres_registry import PostgresPatientRegistry
from dicom_integrity_fixture import dicom_bytes
from test_image_review_migration import PopulatedImageReviewFixture, QUESTION_ID
from test_migration_convergence import (
    FIXTURE_TIME, IMAGE_ID, ORIGINAL, PATIENT_ID, SOURCE_ID,
)


API_ROOT = Path(__file__).resolve().parents[1]
MERGE_REVISION = "0011_image_evidence_merge"
IMAGE_REVISION = "0009_image_review_merge"
EVIDENCE_REVISION = "0010_question_evidence"
TASK_ID = "TASK-" + "A" * 32
LINK_ID = "EVIDENCE-LINK-" + "A" * 32
IMAGE_TABLES = ("clinical_source.dicom_objects", "clinical_source.source_image_links")
TASK_TABLES = ("coordination.question_followthrough_tasks",
               "coordination.question_followthrough_events")
EVIDENCE_TABLES = ("investigation.evidence_catalog_records",
                   "investigation.evidence_rights_decisions",
                   "investigation.question_evidence_links")


class ImageEvidenceMigrationGraphTests(unittest.TestCase):
    def test_application_requires_the_single_join_of_both_published_owner_histories(self):
        # A missing parent or split head would admit an incomplete application
        # schema or make `upgrade head` ambiguous.
        script = ScriptDirectory.from_config(Config(str(API_ROOT / "alembic.ini")))
        self.assertEqual(script.get_heads(), [SCHEMA_REVISION])
        self.assertEqual(script.get_revision(MERGE_REVISION).down_revision,
                         (IMAGE_REVISION, EVIDENCE_REVISION))
        self.assertIn(MERGE_REVISION, {revision.revision for revision in script.walk_revisions()})


class PopulatedImageEvidenceUpgradeTests(PopulatedImageReviewFixture):
    """Real parent SQL/constraints and owner adapters; no stamped or mocked DB.

    Each test catches an incomplete graph, lost owner history, adopted unknown
    owner, disabled guard or partially committed downgrade. The helpers have no
    inherited test methods, so these cases do not rerun old migration suites.
    """

    table_order = {
        **PopulatedImageReviewFixture.table_order,
        "coordination.record_requests": "request_id",
        "coordination.question_followthrough_tasks": "task_id",
        "coordination.question_followthrough_events": "task_id,revision",
        "investigation.evidence_catalog_records": "record_id,version",
        "investigation.evidence_rights_decisions": "record_id,version,revision",
        "investigation.question_evidence_links": "link_id",
    }

    def _schema_definition(self):
        # Compare actual owner definitions before/after a no-DDL merge or a
        # rolled-back migration, without depending on PostgreSQL object OIDs.
        schemas = "('identity','coordination','clinical_source','investigation')"
        queries = {
            "relations": "SELECT n.nspname,c.relname,c.relkind FROM pg_class c "
                         "JOIN pg_namespace n ON n.oid=c.relnamespace "
                         f"WHERE n.nspname IN {schemas} ORDER BY 1,2",
            "columns": "SELECT table_schema,table_name,column_name,ordinal_position,"
                       "data_type,udt_name,is_nullable,column_default,"
                       "character_maximum_length,is_identity,identity_generation "
                       "FROM information_schema.columns "
                       f"WHERE table_schema IN {schemas} ORDER BY 1,2,4",
            "constraints": "SELECT n.nspname,c.relname,k.conname,pg_get_constraintdef(k.oid) "
                           "FROM pg_constraint k JOIN pg_class c ON c.oid=k.conrelid "
                           "JOIN pg_namespace n ON n.oid=c.relnamespace "
                           f"WHERE n.nspname IN {schemas} ORDER BY 1,2,3",
            "indexes": "SELECT schemaname,tablename,indexname,indexdef FROM pg_indexes "
                       f"WHERE schemaname IN {schemas} ORDER BY 1,2,3",
            "functions": "SELECT n.nspname,p.proname,pg_get_functiondef(p.oid) FROM pg_proc p "
                         "JOIN pg_namespace n ON n.oid=p.pronamespace "
                         f"WHERE n.nspname IN {schemas} ORDER BY 1,2",
            "triggers": "SELECT n.nspname,c.relname,t.tgname,pg_get_triggerdef(t.oid) "
                        "FROM pg_trigger t JOIN pg_class c ON c.oid=t.tgrelid "
                        "JOIN pg_namespace n ON n.oid=c.relnamespace "
                        f"WHERE NOT t.tgisinternal AND n.nspname IN {schemas} ORDER BY 1,2,3",
        }
        with self.engine.connect() as connection:
            return {name: [tuple(row) for row in connection.execute(text(query))]
                    for name, query in queries.items()}

    def _seed_acquisition(self):
        quarantine = ORIGINAL.replace(b"CASE-MERGE", b"CASE-UNBOUND")
        with self.engine.begin() as connection:
            connection.execute(text(
                "INSERT INTO coordination.record_requests "
                "(request_id,patient_id,origin_org,request_key,intent_sha256,kind,"
                "record_label,source_organization,actor,purpose,created_at,updated_at) "
                "VALUES ('REQUEST-MERGE',:patient,'ORG-MERGE','ACQUIRE-MERGE',:intent,"
                "'imaging','Original fictional image report','ORG-INSTITUTION',"
                "'ACTOR-MERGE','operations',:created,:created)"
            ), {"patient": PATIENT_ID, "intent": "7" * 64, "created": FIXTURE_TIME})
            connection.execute(text(
                "INSERT INTO clinical_source.quarantine "
                "(target_case_id,declared_case_id,sha256,raw,reason,received_at) "
                "VALUES ('CASE-MERGE','CASE-UNBOUND',:sha,:raw,'case_mismatch',:created)"
            ), {"sha": hashlib.sha256(quarantine).hexdigest(), "raw": quarantine,
                "created": FIXTURE_TIME})

    def _seed_task(self):
        with self.engine.begin() as connection:
            connection.execute(text(
                "INSERT INTO coordination.question_followthrough_tasks "
                "(task_id,question_id,patient_id,case_id,origin_org,actor,purpose,title,detail,"
                "initial_owner_label,due_date,review_trigger,created_at,source_id,source_line,"
                "source_sha256,source_version,source_snapshot_contract,source_snapshot_sha256,"
                "preflight_sha256) SELECT :task,question_id,patient_id,case_id,origin_org,"
                "actor,purpose,'Prepare the fictional source packet','Collect original references.',"
                "'','2026-05-21','When the next source arrives',:created,source_id,source_line,"
                "source_sha256,source_version,source_snapshot_contract,source_snapshot_sha256,"
                "preflight_sha256 FROM investigation.source_questions WHERE question_id=:question"
            ), {"task": TASK_ID, "question": QUESTION_ID, "created": FIXTURE_TIME})
            previous = None
            for revision, status in enumerate(("created", "assigned", "acknowledged"), 1):
                event_id = f"TASK-EVENT-{revision:032X}"
                connection.execute(text(
                    "INSERT INTO coordination.question_followthrough_events "
                    "(event_id,task_id,patient_id,case_id,origin_org,request_key,intent_sha256,"
                    "revision,previous_status,status,owner_label,actor_label,purpose,reason,recorded_at) "
                    "VALUES (:event,:task,:patient,'CASE-MERGE','ORG-MERGE',:request,:intent,"
                    ":revision,:previous,:status,:owner,'ACTOR-MERGE','operations',"
                    "'Recorded fictional coordination history.',:recorded)"
                ), {"event": event_id, "task": TASK_ID, "patient": PATIENT_ID,
                    "request": f"TASK-MERGE-{revision}", "intent": str(revision) * 64,
                    "revision": revision, "previous": previous, "status": status,
                    "owner": "" if revision == 1 else "Fictional Coordinator",
                    "recorded": FIXTURE_TIME + timedelta(minutes=revision)})
                self._event(
                    connection, "coordination.followthrough.created" if revision == 1
                    else "coordination.followthrough.transitioned", task_id=TASK_ID,
                    event_id=event_id, question_id=QUESTION_ID, revision=revision,
                    previous_status=previous, status=status,
                )
                previous = status

    @contextmanager
    def _catalog_registry(self):
        # The old published head is deliberately not application-ready. The
        # actual catalog owner can seed this explicit migration fixture directly.
        connection = self.engine.raw_connection()
        try:
            yield PostgresPatientRegistry(connection.driver_connection, lambda *args: False)
        finally:
            connection.rollback()
            connection.close()

    def _seed_evidence(self):
        with self._catalog_registry() as registry:
            seed_fictional_records(registry, fictional_records(), recorded_by="FIXTURE-AUTHOR")
        with self.engine.begin() as connection:
            connection.execute(text(
                "INSERT INTO investigation.question_evidence_links "
                "(link_id,patient_id,case_id,question_id,origin_org,actor,purpose,request_key,"
                "intent_sha256,record_id,version,metadata_sha256,source_snapshot_contract,"
                "source_snapshot_sha256,preflight_sha256,created_at) "
                "SELECT :link,q.patient_id,q.case_id,q.question_id,q.origin_org,q.actor,q.purpose,"
                "'EVIDENCE-MERGE',:intent,e.record_id,e.version,e.metadata_sha256,"
                "q.source_snapshot_contract,q.source_snapshot_sha256,q.preflight_sha256,:created "
                "FROM investigation.source_questions q CROSS JOIN investigation.evidence_catalog_records e "
                "WHERE q.question_id=:question AND e.record_id='FICT-RECORD-CONTINUITY' AND e.version='1'"
            ), {"link": LINK_ID, "question": QUESTION_ID, "intent": "8" * 64,
                "created": FIXTURE_TIME})
            self._event(connection, "evidence.citation.linked", question_id=QUESTION_ID,
                        link_id=LINK_ID, citation="FICT-RECORD-CONTINUITY@1")
        with self._catalog_registry() as registry:
            append_rights_decision(
                registry, "FICT-RECORD-CONTINUITY", "1",
                permissions={"metadata": {"store": "allowed", "display": "allowed"}},
                revoked=True, superseded=False, recorded_by="FIXTURE-REVIEWER",
                reason="Authored withdrawal before preserving the published parent.",
            )

    def _seed_parent(self, revision):
        migrate(self.settings, "upgrade", revision)
        self.assertEqual(self._heads(), {revision})
        self._seed_common()
        self._seed_acquisition()
        self._seed_questions()
        self._seed_return()
        if revision == IMAGE_REVISION:
            self._seed_image()
        else:
            self._seed_task()
            self._seed_evidence()
        self._assert_readiness(False)

    def _assert_original_provenance(self):
        rows = self._snapshot()
        self.assertEqual(set(rows), set(self.table_order))
        self.assertTrue(all(rows.values()), "Every joined owner must have a populated fixture")
        source = rows["clinical_source.source_versions"][0]
        self.assertEqual((source["source_id"], source["raw"], source["sha256"], source["received_at"]),
                         (SOURCE_ID, ORIGINAL, hashlib.sha256(ORIGINAL).hexdigest(), FIXTURE_TIME))
        original_image = dicom_bytes(patient_id="SYNTHETIC-MERGE", issuer="ORG-INSTITUTION/SYS-SYNTH")
        image = rows["clinical_source.dicom_objects"][0]
        self.assertEqual((image["image_id"], image["raw"], image["sha256"], image["byte_count"]),
                         (IMAGE_ID, original_image, hashlib.sha256(original_image).hexdigest(), len(original_image)))
        self.assertEqual(rows["clinical_source.source_image_links"], [
            {"source_id": SOURCE_ID, "image_id": IMAGE_ID, "created_at": FIXTURE_TIME},
        ])
        self.assertEqual([(row["question_id"], row["source_snapshot_contract"])
                          for row in rows["investigation.source_questions"]], [
            ("QUESTION-" + "B" * 32, "oi.synthetic-postgres-world-model-sources/1"),
            (QUESTION_ID, "oi.pg-source-world-model/1"),
        ])
        task = rows["coordination.question_followthrough_tasks"][0]
        self.assertEqual((task["question_id"], task["source_id"], task["source_line"],
                          task["source_snapshot_contract"], task["source_snapshot_sha256"]),
                         (QUESTION_ID, SOURCE_ID, 7, "oi.pg-source-world-model/1", "3" * 64))
        link = rows["investigation.question_evidence_links"][0]
        self.assertEqual((link["link_id"], link["question_id"], link["record_id"], link["version"]),
                         (LINK_ID, QUESTION_ID, "FICT-RECORD-CONTINUITY", "1"))
        continuity_rights = [row for row in rows["investigation.evidence_rights_decisions"]
                             if row["record_id"] == "FICT-RECORD-CONTINUITY"]
        self.assertEqual([(row["revision"], row["revoked"]) for row in continuity_rights],
                         [(1, False), (2, True)])

    def _assert_combined_history_guards(self):
        self._assert_immutable_owners()
        self._assert_review_guards()
        before = self._snapshot()
        for statement in (
            "UPDATE coordination.question_followthrough_tasks SET title='Changed fictional history'",
            "DELETE FROM coordination.question_followthrough_events",
            "UPDATE investigation.evidence_catalog_records SET title='Changed fictional metadata'",
            "DELETE FROM investigation.evidence_rights_decisions",
            "UPDATE investigation.question_evidence_links SET request_key='REWRITTEN-CITATION'",
        ):
            with self.subTest(statement=statement), self.assertRaises(SQLAlchemyError):
                with self.engine.begin() as connection:
                    connection.execute(text(statement))

        # These insertions satisfy the tables' types and CHECKs but violate the
        # original owner guards. Removing a guard must fail this acceptance.
        for table, changes, reason in (
            (TASK_TABLES[0], {"task_id": "TASK-" + "F" * 32, "origin_org": "ORG-OTHER"},
             "OI-FOLLOWTHROUGH-PATIENT-BOUNDARY"),
            (TASK_TABLES[0], {"task_id": "TASK-" + "F" * 32, "source_snapshot_sha256": "0" * 64},
             "OI-FOLLOWTHROUGH-QUESTION-BOUNDARY"),
            (TASK_TABLES[1], {"event_id": "TASK-EVENT-" + "F" * 32, "request_key": "FORGED-TASK",
                             "revision": 5, "previous_status": "acknowledged", "status": "completed",
                             "owner_label": "Fictional Coordinator"}, "OI-FOLLOWTHROUGH-REVISION"),
            (EVIDENCE_TABLES[2], {"link_id": "EVIDENCE-LINK-" + "F" * 32,
                                 "request_key": "FORGED-LINK", "origin_org": "ORG-OTHER"},
             "OI-EVIDENCE-PATIENT-BOUNDARY"),
            (EVIDENCE_TABLES[2], {"link_id": "EVIDENCE-LINK-" + "F" * 32,
                                 "request_key": "FORGED-LINK", "source_snapshot_sha256": "0" * 64},
             "OI-EVIDENCE-QUESTION-BOUNDARY"),
            (EVIDENCE_TABLES[2], {"link_id": "EVIDENCE-LINK-" + "F" * 32,
                                 "request_key": "FORGED-LINK", "metadata_sha256": "0" * 64},
             "OI-EVIDENCE-CATALOG-BOUNDARY"),
        ):
            row = {**before[table][0], **changes}
            columns = ",".join(row)
            values = ",".join(":" + name for name in row)
            with self.subTest(table=table, reason=reason), self.assertRaisesRegex(SQLAlchemyError, reason):
                with self.engine.begin() as connection:
                    connection.execute(text(f"INSERT INTO {table} ({columns}) VALUES ({values})"), row)
        self.assertEqual(self._snapshot(), before)

    def _upgrade_parent(self, revision):
        self._seed_parent(revision)
        before = self._snapshot()
        missing = TASK_TABLES + EVIDENCE_TABLES if revision == IMAGE_REVISION else IMAGE_TABLES
        self.assertTrue(all(table not in before for table in missing))
        migrate(self.settings, "upgrade", "head")
        self.assertEqual(self._heads(), {SCHEMA_REVISION})
        self.assertEqual(self._snapshot(before), before)
        after = self._snapshot()
        self.assertEqual(set(after), set(self.table_order))
        self.assertTrue(all(after[table] == [] for table in missing))
        self._assert_readiness(True)
        if revision == IMAGE_REVISION:
            self._seed_task()
            self._seed_evidence()
        else:
            self._seed_image()
        self._assert_original_provenance()
        self._assert_combined_history_guards()
        complete = self._snapshot()
        migrate(self.settings, "upgrade", "head")
        self.assertEqual(self._snapshot(), complete)

    def test_populated_image_review_parent_preserves_all_rows_and_adds_empty_task_evidence_owners(self):
        self._upgrade_parent(IMAGE_REVISION)

    def test_populated_evidence_parent_preserves_task_citation_and_revoked_rights_when_adding_images(self):
        self._upgrade_parent(EVIDENCE_REVISION)

    def test_two_populated_parent_heads_require_a_no_ddl_merge_and_reversible_version_bookkeeping(self):
        self._seed_parent(IMAGE_REVISION)
        migrate(self.settings, "upgrade", EVIDENCE_REVISION)
        self._seed_task()
        self._seed_evidence()
        self.assertEqual(self._heads(), {IMAGE_REVISION, EVIDENCE_REVISION})
        self._assert_readiness(False)
        before = self._snapshot()
        definitions = self._schema_definition()
        # Prove this historical merge against its own published parents. The
        # later authored owner is deliberately absent from this no-DDL proof.
        migrate(self.settings, "upgrade", MERGE_REVISION)
        self.assertEqual(self._heads(), {MERGE_REVISION})
        self.assertEqual(self._snapshot(), before)
        self.assertEqual(self._schema_definition(), definitions)
        self._assert_readiness(False)
        self._assert_original_provenance()
        self._assert_combined_history_guards()

        # A relative -1 is ambiguous at a merge. Naming one direct parent
        # removes only 0011 and restores both published version rows.
        migrate(self.settings, "downgrade", IMAGE_REVISION)
        self.assertEqual(self._heads(), {IMAGE_REVISION, EVIDENCE_REVISION})
        self.assertEqual(self._snapshot(), before)
        self.assertEqual(self._schema_definition(), definitions)
        self._assert_readiness(False)
        migrate(self.settings, "upgrade", "head")
        self.assertEqual(self._heads(), {SCHEMA_REVISION})
        self.assertEqual(self._snapshot(), before)
        self._assert_readiness(True)

    def _reject_unknown_owner(self, revision, table):
        self._seed_parent(revision)
        before = self._snapshot()
        with self.engine.begin() as connection:
            connection.execute(text(f"CREATE TABLE {table} (legacy text)"))
            connection.execute(text(f"INSERT INTO {table} VALUES ('AUTHORED-UNKNOWN-OWNER')"))
        definitions = self._schema_definition()
        with self.assertRaises(CommandError):
            migrate(self.settings, "upgrade", "head")
        self.assertEqual(self._heads(), {revision})
        self.assertEqual(self._snapshot(before), before)
        self.assertEqual(self._schema_definition(), definitions)
        with self.engine.connect() as connection:
            self.assertEqual(connection.execute(text(f"SELECT legacy FROM {table}")).scalars().all(),
                             ["AUTHORED-UNKNOWN-OWNER"])
        self._assert_readiness(False)

    def test_unknown_image_owner_rolls_back_without_advancing_populated_evidence_parent(self):
        self._reject_unknown_owner(EVIDENCE_REVISION, IMAGE_TABLES[0])

    def test_unknown_task_owner_rolls_back_without_advancing_populated_image_parent(self):
        self._reject_unknown_owner(IMAGE_REVISION, TASK_TABLES[0])

    def test_unknown_evidence_owner_rolls_back_new_task_ddl_and_preserves_populated_images(self):
        self._reject_unknown_owner(IMAGE_REVISION, EVIDENCE_TABLES[0])
        with self.engine.connect() as connection:
            for table in TASK_TABLES:
                self.assertIsNone(connection.execute(text("SELECT to_regclass(:table)"),
                                                      {"table": table}).scalar_one())

    def _reject_populated_downgrade(self, target, reason):
        # Exercise the historical guard before 0020 adds its own populated
        # source-outbox refusal. Current-head upgrade/readiness is tested above.
        before = self._snapshot()
        definitions = self._schema_definition()
        with self.assertRaisesRegex(CommandError, reason):
            migrate(self.settings, "downgrade", target)
        self.assertEqual(self._heads(), {"0019_composer_runs"})
        self.assertEqual(self._snapshot(), before)
        self.assertEqual(self._schema_definition(), definitions)
        self._assert_readiness(False)

    def test_populated_evidence_blocks_downgrade_without_changing_images_tasks_or_receipts(self):
        self._seed_parent(EVIDENCE_REVISION)
        migrate(self.settings, "upgrade", "0019_composer_runs")
        self._seed_image()
        self._reject_populated_downgrade("0009_question_followthrough", "Populated evidence history")

    def test_populated_tasks_roll_back_removal_of_empty_evidence_schema_and_preserve_images(self):
        self._seed_parent(IMAGE_REVISION)
        migrate(self.settings, "upgrade", "0019_composer_runs")
        self._seed_task()
        self._reject_populated_downgrade("0008_review_convergence", "Follow-through history")


if __name__ == "__main__":
    unittest.main()
