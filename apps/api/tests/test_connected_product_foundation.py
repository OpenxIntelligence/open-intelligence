"""Join both published product histories without discarding populated owner state."""
import unittest

from sqlalchemy import text
from oi_api.contracts import SCHEMA_REVISION
from oi_api.migrate import migrate
from test_document_image_convergence import graph
import test_encounter_source_migration as encounter_fixture
from test_source_versions import SourceVersionFixture
import test_evidence_convergence_migrations as evidence


class ConnectedProductGraphTests(unittest.TestCase):
    def test_join_retains_both_published_heads(self):
        script = graph()
        self.assertEqual(script.get_heads(), [SCHEMA_REVISION])
        self.assertEqual(set(script.get_revision("0028_connected_product").down_revision),
                         {'0027_source_event_purpose', '0022_encounter_sources'})
        self.assertEqual(script.get_revision('0022_encounter_sources').down_revision,
                         '0021_lab_citation_freshness')
        self.assertEqual(script.get_revision('0027_source_event_purpose').down_revision,
                         '0026_integrated_core')


class ConnectedProductUpgradeTests(SourceVersionFixture):
    services = evidence.EvidenceConvergenceMigrationTests.services
    seed = encounter_fixture.EncounterSourceMigrationTests.seed
    insert = staticmethod(encounter_fixture.EncounterSourceMigrationTests.insert)

    def snapshot(self):
        with self.engine.connect() as connection:
            tables = connection.execute(text("SELECT schemaname,tablename FROM pg_tables "
                "WHERE schemaname IN ('identity','ehr','coordination','clinical_source','investigation') "
                "ORDER BY 1,2")).all()
            return {f'{schema}.{table}': connection.execute(text(
                f'SELECT to_jsonb(t)::text FROM {schema}.{table} t ORDER BY 1')).scalars().all()
                for schema, table in tables}

    def upgrade_from(self, parent):
        migrate(self.admin, 'downgrade', 'base')
        migrate(self.admin, 'upgrade', parent)
        with self.services() as registry:
            intent = self.seed(registry, 'ALPHA')
        if parent == '0022_encounter_sources':
            with self.engine.begin() as connection:
                self.insert(connection, intent)
        before = self.snapshot()
        migrate(self.admin, 'upgrade', 'head')
        after = self.snapshot()
        for table, rows in before.items():
            self.assertEqual(after[table], rows, table)
        with self.engine.connect() as connection:
            self.assertEqual(connection.execute(text('SELECT version_num FROM public.alembic_version'))
                             .scalars().all(), [SCHEMA_REVISION])
            self.assertIsNotNone(connection.execute(text("SELECT to_regclass('ehr.encounter_source_links')")).scalar_one())
            self.assertIsNotNone(connection.execute(text("SELECT to_regclass('coordination.source_event_outbox')")).scalar_one())
        # Re-applying head is a no-op; all rows stay attributable to their original owner.
        migrate(self.admin, 'upgrade', 'head')
        self.assertEqual(self.snapshot(), after)

    def test_upgrade_populated_diagnostic_history(self):
        self.upgrade_from('0022_encounter_sources')

    def test_upgrade_populated_execution_history(self):
        self.upgrade_from('0027_source_event_purpose')
