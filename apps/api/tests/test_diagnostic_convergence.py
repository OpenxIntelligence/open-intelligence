"""Preserve populated published imaging and encounter histories at one ready head."""
import unittest

from sqlalchemy import text

from oi_api.contracts import SCHEMA_REVISION
from oi_api.database import Database
from oi_api.images import PostgresSourceImages
from oi_api.migrate import migrate
from oi_api.sources import PostgresSourceVersions
import test_encounter_source_migration as encounters
import test_evidence_convergence_migrations as evidence
from test_document_image_convergence import graph
from test_image_custody import REPORT, image_bytes
from test_source_versions import SourceVersionFixture

ENCOUNTER = "0022_encounter_sources"
IMAGING = "0023_dicom_mr_custody"


class DiagnosticGraphTests(unittest.TestCase):
    def test_one_head_preserves_both_published_revision_paths(self):
        script = graph()
        self.assertEqual(script.get_heads(), [SCHEMA_REVISION])
        self.assertEqual(set(script.get_revision(SCHEMA_REVISION).down_revision), {ENCOUNTER, IMAGING})
        self.assertEqual(script.get_revision(ENCOUNTER).down_revision, "0021_lab_citation_freshness")
        self.assertEqual(script.get_revision(IMAGING).down_revision, "0022_lab_citation_source_scope")
        self.assertEqual(script.get_revision("0022_lab_citation_source_scope").down_revision,
                         "0021_lab_citation_freshness")


class DiagnosticMigrationTests(SourceVersionFixture):
    services = evidence.EvidenceConvergenceMigrationTests.services
    snapshot = evidence.EvidenceConvergenceMigrationTests.snapshot
    seed = encounters.EncounterSourceMigrationTests.seed
    seed_lab = encounters.EncounterSourceMigrationTests.seed_lab

    def state(self):
        with self.engine.connect() as conn:
            names = [f"{schema}.{name}" for schema, name in conn.execute(text(
                "SELECT table_schema,table_name FROM information_schema.tables "
                "WHERE table_schema IN ('identity','coordination','clinical_source','investigation','ehr') "
                "AND table_type='BASE TABLE' ORDER BY table_schema,table_name"))]
            ehr_sequences = {name: tuple(conn.execute(text(f"SELECT last_value,is_called FROM ehr.{name}")).one())
                for name, in conn.execute(text("SELECT sequencename FROM pg_sequences WHERE schemaname='ehr'"))}
        return (*self.snapshot(names), ehr_sequences)

    def exercise(self, previous, *, both=False):
        migrate(self.admin, "downgrade", "0021_lab_citation_freshness")
        migrate(self.admin, "upgrade", previous)
        with self.services() as registry:
            visit = self.seed(registry, "ALPHA")
        if previous == ENCOUNTER:
            with self.engine.begin() as conn:
                encounters.EncounterSourceMigrationTests.insert(conn, visit)
        self.seed_lab(visit['patient_id'])
        if both:
            migrate(self.admin, "upgrade", IMAGING)
        modality = 'MR' if previous == IMAGING or both else 'CT'
        raw = image_bytes(patient_id='UPGRADE-SUBJECT', modality=modality)
        with self.services() as registry:
            source = PostgresSourceVersions(registry).import_original(
                visit['patient_id'], 'CASE-ALPHA', REPORT.encode(), **evidence.OPTIONS)['source_id']
            image = PostgresSourceImages(registry).import_original(
                visit['patient_id'], 'CASE-ALPHA', source, raw, **evidence.OPTIONS)
        with self.engine.connect() as conn:
            self.assertEqual(set(conn.execute(text('SELECT version_num FROM public.alembic_version')).scalars()),
                             {ENCOUNTER, IMAGING} if both else {previous})
        probe = Database(self.settings)
        self.addCleanup(probe.close)
        self.assertEqual(probe.check().status, 'schema_mismatch')
        before = self.state()
        migrate(self.admin, 'upgrade', 'head')
        migrate(self.admin, 'upgrade', 'head')
        self.assertEqual(self.state(), before)
        self.assertEqual(probe.check().status, 'ready')
        with self.engine.connect() as conn:
            self.assertEqual(conn.execute(text('SELECT version_num FROM public.alembic_version')).scalar_one(),
                             SCHEMA_REVISION)
        # Each published history gains the other owner's callable capability.
        if previous == IMAGING:
            with self.engine.begin() as conn:
                encounters.EncounterSourceMigrationTests.insert(conn, visit)
        with self.services() as registry:
            owner = PostgresSourceImages(registry)
            restored, _ = owner.original(visit['patient_id'], 'CASE-ALPHA', source, image['image_id'],
                                         **evidence.OPTIONS)
            self.assertEqual(restored, raw)
            if modality == 'CT':
                mr = image_bytes(patient_id='UPGRADE-SUBJECT', modality='MR',
                                 series_uid='2.25.201', sop_uid='2.25.202')
                self.assertEqual(owner.import_original(visit['patient_id'], 'CASE-ALPHA', source,
                                 mr, **evidence.OPTIONS)['modality'], 'MR')

    def test_populated_encounters_and_labs_gain_mr_without_rewriting_history(self):
        self.exercise(ENCOUNTER)

    def test_populated_mr_and_labs_gain_encounter_links_without_rewriting_history(self):
        self.exercise(IMAGING)

    def test_both_populated_heads_require_the_explicit_join(self):
        self.exercise(ENCOUNTER, both=True)
