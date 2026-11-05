"""Populated upgrades and boundary checks for links to canonical source versions."""
import hashlib
import unittest

from alembic.util.exc import CommandError
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError

from oi_api.case_bindings import CanonicalCaseBindings
from oi_api.contracts import SCHEMA_REVISION
from oi_api.encounter_sources import PostgresEncounterSources
from oi_api.migrate import migrate
from oi_api.source_integrity import SourceIntegrityError
from oi_api.sources import PostgresSourceVersions
from open_intelligence.postgres_encounters import PostgresClinicalEncounters

import test_evidence_convergence_migrations as evidence
import test_lab_manual_convergence as laboratory
from test_document_image_convergence import graph
from test_ehr_laboratory_convergence import EHR_TABLES
from test_source_versions import ORIGINAL, AMENDED, SourceVersionFixture


PREVIOUS = "0021_lab_citation_freshness"
REVISION = "0022_encounter_sources"
CASE = "CASE-ALPHA"
SCOPE = {"actor": "ACTOR-ALPHA", "purpose": "operations"}


class EncounterSourceGraphTests(unittest.TestCase):
    def test_new_revision_follows_the_existing_citation_guard(self):
        script = graph()
        self.assertEqual(script.get_heads(), [SCHEMA_REVISION])
        self.assertEqual(script.get_revision(REVISION).down_revision, PREVIOUS)


class EncounterSourceMigrationTests(SourceVersionFixture):
    services = evidence.EvidenceConvergenceMigrationTests.services
    snapshot = evidence.EvidenceConvergenceMigrationTests.snapshot
    seed_lab = laboratory.LabManualPopulatedMigrationTests.seed_lab

    def seed(self, registry, label):
        patient = registry.create_patient(**evidence.COMMON, request_key="REGISTRY-" + label)["patient_id"]
        case_id = "CASE-" + label
        CanonicalCaseBindings(registry).bind(patient, **evidence.COMMON, case_id=case_id,
            source_organization="ORG-INSTITUTION", source_system="SYS-SYNTH",
            source_subject_ref="UPGRADE-SUBJECT" if label == "ALPHA" else "SUBJECT-" + label,
            review_ref="REVIEW-" + label)
        original = ORIGINAL.replace(CASE, case_id).encode()
        source = PostgresSourceVersions(registry).import_original(
            patient, case_id, original, **evidence.OPTIONS)["source_id"]
        visit = PostgresClinicalEncounters(registry, registry.authorizer).schedule(
            patient, "VISIT-" + label, "outpatient", "2026-01-10", request_key="SCHEDULE-" + label,
            **SCOPE)["encounter_id"]
        return dict(patient_id=patient, encounter_id=visit, case_id=case_id, source_id=source,
                    version=1, sha256=hashlib.sha256(original).hexdigest(), origin_org="ORG-ALPHA",
                    actor="ACTOR-ALPHA", purpose="operations", request_key="LINK-" + label)

    @staticmethod
    def insert(conn, intent):
        conn.execute(text("""
            INSERT INTO ehr.encounter_source_links(patient_id,encounter_id,case_id,source_id,version,
                sha256,origin_org,actor,purpose,request_key)
            VALUES (:patient_id,:encounter_id,:case_id,:source_id,:version,:sha256,:origin_org,:actor,:purpose,:request_key)
        """), intent)

    def test_populated_upgrade_keeps_source_and_encounter_history_and_empty_downgrade(self):
        migrate(self.admin, "downgrade", PREVIOUS)
        with self.services() as registry:
            alpha = self.seed(registry, "ALPHA")
        tables, _ = self.snapshot()
        owners = list(tables) + EHR_TABLES
        before = self.snapshot(owners)
        migrate(self.admin, "upgrade", REVISION)
        self.assertEqual(self.snapshot(owners), before)
        with self.engine.connect() as conn:
            self.assertEqual(conn.execute(text("SELECT count(*) FROM ehr.encounter_source_links")).scalar_one(), 0)
        migrate(self.admin, "downgrade", PREVIOUS)
        self.assertEqual(self.snapshot(owners), before)
        migrate(self.admin, "upgrade", REVISION)
        with self.engine.begin() as conn:
            self.insert(conn, alpha)
        with self.assertRaisesRegex(CommandError, "Populated encounter source links"):
            migrate(self.admin, "downgrade", PREVIOUS)
        with self.engine.connect() as conn:
            self.assertEqual(conn.execute(text("SELECT version_num FROM public.alembic_version")).scalar_one(), REVISION)
            self.assertEqual(conn.execute(text("SELECT source_id FROM ehr.encounter_source_links")).scalar_one(),
                             alpha["source_id"])

    def test_sql_links_require_matching_owners_and_current_source_and_are_immutable(self):
        with self.services() as registry:
            alpha = self.seed(registry, "ALPHA")
            beta = self.seed(registry, "BETA")
        for changes, reason in (
            ({"encounter_id": beta["encounter_id"]}, "foreign key constraint"),
            ({"case_id": beta["case_id"]}, "OI-ENCOUNTER-SOURCE-SCOPE"),
            ({"origin_org": "ORG-OTHER"}, "OI-ENCOUNTER-SOURCE-SCOPE"),
            ({"source_id": beta["source_id"]}, "OI-ENCOUNTER-SOURCE-UNAVAILABLE"),
            ({"version": 2}, "foreign key constraint"),
            ({"sha256": "0" * 64}, "foreign key constraint"),
        ):
            with self.subTest(changes=changes), self.assertRaisesRegex(DBAPIError, reason), self.engine.begin() as conn:
                self.insert(conn, {**alpha, **changes})
        with self.engine.begin() as conn:
            self.insert(conn, alpha)
        with self.assertRaisesRegex(DBAPIError, "unique constraint"), self.engine.begin() as conn:
            self.insert(conn, {**alpha, "request_key": "DIFFERENT-KEY"})
        for statement in ("UPDATE ehr.encounter_source_links SET version=version",
                          "DELETE FROM ehr.encounter_source_links", "TRUNCATE ehr.encounter_source_links"):
            with self.subTest(statement=statement), self.assertRaisesRegex(DBAPIError, "HISTORY-IMMUTABLE"):
                with self.engine.begin() as conn:
                    conn.execute(text(statement))
        with self.services() as registry:
            PostgresSourceVersions(registry).import_original(alpha["patient_id"], CASE, AMENDED.encode(), **evidence.OPTIONS)
            visit = PostgresClinicalEncounters(registry, registry.authorizer).schedule(
                alpha["patient_id"], "LATER-VISIT", "outpatient", "2026-02-01",
                request_key="LATER-SCHEDULE", **SCOPE)["encounter_id"]
        with self.assertRaisesRegex(DBAPIError, "OI-ENCOUNTER-SOURCE-UNAVAILABLE"), self.engine.begin() as conn:
            self.insert(conn, {**alpha, "encounter_id": visit, "request_key": "STALE-LINK"})

    def test_fhir_link_checks_typed_observations_on_read_and_replay(self):
        with self.services() as registry:
            alpha = self.seed(registry, "ALPHA")
        patient, visit = alpha["patient_id"], alpha["encounter_id"]
        raw, source = self.seed_lab(patient)
        digest = hashlib.sha256(raw).hexdigest()
        args = (patient, visit, CASE, source["source_id"], 1, digest, "LAB-LINK")
        with self.services() as registry, registry.transaction():
            owner = PostgresEncounterSources(registry)
            receipt = owner.link(*args, **evidence.COMMON)
            self.assertFalse(receipt["duplicate"])
            entry, = owner.list(patient, visit, CASE, 0, 26, organization="ORG-ALPHA")
            self.assertEqual((entry["id"], entry["sha256"], entry["source_state"]), (receipt["id"], digest, "current"))
        # A schema-legal but extraneous restored child cannot be vouched for
        # by the exact bundle bytes, even when the source hash still matches.
        with self.engine.begin() as conn:
            conn.execute(text("""
                INSERT INTO clinical_source.fhir_laboratory_observations
                    (source_id,observation_reference,position,loinc_code,effective_at,issued_at,
                     status,value_text,unit_code,absent_reason,source_reported,clinical_review)
                SELECT source_id,'Observation/EXTRA',2,loinc_code,effective_at,issued_at,
                       status,value_text,unit_code,absent_reason,source_reported,clinical_review
                FROM clinical_source.fhir_laboratory_observations WHERE source_id=:source AND position=1
            """), dict(source=source["source_id"]))
        for operation in ("list", "retry"):
            with self.subTest(operation=operation), self.assertRaises(SourceIntegrityError):
                with self.services() as registry, registry.transaction():
                    owner = PostgresEncounterSources(registry)
                    if operation == "list":
                        owner.list(patient, visit, CASE, 0, 26, organization="ORG-ALPHA")
                    else:
                        owner.link(*args, **evidence.COMMON)
