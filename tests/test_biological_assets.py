import tempfile
import unittest
from pathlib import Path

from open_intelligence import CaseStore, InvalidInput

ROOT = Path(__file__).resolve().parents[1]
SAMPLE = ROOT / 'examples' / 'synthetic'


def report(name):
    return (SAMPLE / name).read_bytes()


UNKNOWN = dict(location_state='unknown', location_value=None,
               quantity_state='unknown', quantity_value=None,
               custody_state='unknown', custody_value=None,
               consent_state='unknown', consent_value=None,
               rights_state='unknown', rights_value=None)


class BiologicalAssetTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.store = CaseStore(Path(self.tmp.name) / 'test.sqlite')
        self.store.add_case('CASE-ALPHA', 'Fictional Alpha')
        self.store.add_case('CASE-BETA', 'Fictional Beta')
        self.path = self.store.import_report('CASE-ALPHA', report('alpha-pathology-original.txt'))
        self.img = self.store.import_report('CASE-ALPHA', report('alpha-imaging.txt'))
        self.beta = self.store.import_report('CASE-BETA', report('beta-pathology.txt'))

    def tearDown(self):
        self.store.close()
        self.tmp.cleanup()

    def block(self, asset_id='BLOCK-ALPHA', episode='EPISODE-A', observed='2026-05-03',
              source=None, **kwargs):
        return self.store.add_biological_asset(
            'CASE-ALPHA', asset_id, 'ffpe_block', episode, observed,
            source or self.path['source_id'], specimen_state='recorded',
            specimen_id='BIOPSY-ALPHA', **kwargs)

    def test_unknown_state_preserved_and_distinct_from_no_assertion(self):
        asset = self.block()
        assertion = self.store.add_inventory_assertion(
            'CASE-ALPHA', asset, self.path['source_id'], 'Synthetic registrar', **UNKNOWN)
        bare = self.block('BLOCK-BARE', episode='EPISODE-B')
        state = self.store.state('CASE-ALPHA')
        rows = {a['id']: a for a in state['biological_inventory_assertions']}
        self.assertEqual(len(rows), 1)
        item = rows[assertion]
        self.assertEqual(item['state'], 'current')
        for field in ('location', 'quantity', 'custody', 'consent', 'rights'):
            self.assertEqual(item[field + '_state'], 'unknown')
            self.assertIsNone(item[field + '_value'])
        # No assertion row at all is a different, visible condition.
        self.assertEqual([a for a in state['biological_inventory_assertions']
                          if a['asset_id'] == bare], [])
        with self.assertRaisesRegex(InvalidInput, 'Unknown inventory location must not carry'):
            self.store.add_inventory_assertion(
                'CASE-ALPHA', asset, self.path['source_id'], 'Synthetic registrar',
                **{**UNKNOWN, 'location_value': 'Freezer 3'})
        with self.assertRaisesRegex(InvalidInput, 'Known inventory custody requires'):
            self.store.add_inventory_assertion(
                'CASE-ALPHA', asset, self.path['source_id'], 'Synthetic registrar',
                **{**UNKNOWN, 'custody_state': 'known', 'custody_value': None})

    def test_no_silent_merging_across_tumors_and_time_points(self):
        first = self.block('BLOCK-A', episode='EPISODE-A', observed='2026-05-03')
        second = self.block('BLOCK-B', episode='EPISODE-B', observed='2026-05-03')
        slide_early = self.store.add_biological_asset(
            'CASE-ALPHA', 'SLIDE-A1', 'slide', 'EPISODE-A', '2026-05-10',
            self.path['source_id'], specimen_state='recorded',
            specimen_id='BIOPSY-ALPHA', parent_asset_id=first)
        slide_late = self.store.add_biological_asset(
            'CASE-ALPHA', 'SLIDE-A2', 'slide', 'EPISODE-A', '2026-06-10',
            self.path['source_id'], specimen_state='recorded',
            specimen_id='BIOPSY-ALPHA', parent_asset_id=first)
        assets = self.store.state('CASE-ALPHA')['biological_assets']
        self.assertEqual(len(assets), 4)
        self.assertEqual(len({a['id'] for a in assets}), 4)
        self.assertEqual({a['asset_id'] for a in assets},
                         {'BLOCK-A', 'BLOCK-B', 'SLIDE-A1', 'SLIDE-A2'})
        # A derivative may not graft one tumor's lineage onto another.
        with self.assertRaisesRegex(InvalidInput, 'share its parent'):
            self.store.add_biological_asset(
                'CASE-ALPHA', 'SLIDE-X', 'slide', 'EPISODE-B', '2026-05-10',
                self.path['source_id'], specimen_state='recorded',
                specimen_id='BIOPSY-ALPHA', parent_asset_id=first)
        self.assertEqual(len(self.store.state('CASE-ALPHA')['biological_assets']), 4)
        self.assertNotEqual(slide_early, slide_late)

    def test_derivative_parent_kind_and_pointer_rules(self):
        block = self.block()
        aliquot = self.store.add_biological_asset(
            'CASE-ALPHA', 'ALIQUOT-A', 'fresh_frozen_aliquot', 'EPISODE-A', '2026-05-03',
            self.path['source_id'], specimen_state='recorded', specimen_id='BIOPSY-ALPHA')
        with self.assertRaisesRegex(InvalidInput, 'requires its parent'):
            self.store.add_biological_asset(
                'CASE-ALPHA', 'SLIDE-NOPARENT', 'slide', 'EPISODE-A', '2026-05-10',
                self.path['source_id'])
        with self.assertRaisesRegex(InvalidInput, 'has no parent'):
            self.store.add_biological_asset(
                'CASE-ALPHA', 'BLOCK-PARENTED', 'ffpe_block', 'EPISODE-A', '2026-05-03',
                self.path['source_id'], parent_asset_id=block)
        with self.assertRaisesRegex(InvalidInput, 'cannot derive'):
            self.store.add_biological_asset(
                'CASE-ALPHA', 'WSI-BAD', 'digital_wsi', 'EPISODE-A', '2026-05-11',
                self.path['source_id'], parent_asset_id=block)
        slide = self.store.add_biological_asset(
            'CASE-ALPHA', 'SLIDE-A', 'slide', 'EPISODE-A', '2026-05-10',
            self.path['source_id'], parent_asset_id=block)
        with self.assertRaisesRegex(InvalidInput, 'cannot derive'):
            self.store.add_biological_asset(
                'CASE-ALPHA', 'GEN-BAD', 'genomics_data_pointer', 'EPISODE-A', '2026-05-12',
                self.path['source_id'], parent_asset_id=slide)
        wsi = self.store.add_biological_asset(
            'CASE-ALPHA', 'WSI-A', 'digital_wsi', 'EPISODE-A', '2026-05-11',
            self.path['source_id'], parent_asset_id=slide,
            pointer_label='synthetic-wsi-pointer-A')
        genomics = self.store.add_biological_asset(
            'CASE-ALPHA', 'GEN-A', 'genomics_data_pointer', 'EPISODE-A', '2026-05-12',
            self.path['source_id'], parent_asset_id=aliquot,
            pointer_label='synthetic-genomics-pointer-A')
        self.assertNotEqual(wsi, genomics)
        with self.assertRaisesRegex(InvalidInput, 'not a URL or path'):
            self.store.add_biological_asset(
                'CASE-ALPHA', 'GEN-URL', 'genomics_data_pointer', 'EPISODE-A', '2026-05-12',
                self.path['source_id'], parent_asset_id=aliquot,
                pointer_label='https://example.invalid/file.bam')
        with self.assertRaisesRegex(InvalidInput, 'pointer label applies only'):
            self.store.add_biological_asset(
                'CASE-ALPHA', 'BLOCK-POINTER', 'ffpe_block', 'EPISODE-A', '2026-05-03',
                self.path['source_id'], pointer_label='synthetic-pointer')

    def test_source_amendment_stales_only_dependent_assertions(self):
        block = self.block()
        path_assertion = self.store.add_inventory_assertion(
            'CASE-ALPHA', block, self.path['source_id'], 'Synthetic registrar', **UNKNOWN)
        img_assertion = self.store.add_inventory_assertion(
            'CASE-ALPHA', block, self.img['source_id'], 'Synthetic registrar', **UNKNOWN)
        update = self.store.import_report('CASE-ALPHA', report('alpha-pathology-amended.txt'))
        self.assertEqual(update['invalidated_inventory_assertions'], [path_assertion])
        state = self.store.state('CASE-ALPHA')
        rows = {a['id']: a for a in state['biological_inventory_assertions']}
        self.assertEqual(rows[path_assertion]['state'], 'stale')
        self.assertEqual(rows[img_assertion]['state'], 'current')
        # Historic rows preserved: both source versions and the asset remain.
        sources = [s for s in state['sources'] if s['document_id'] == 'PATH-ALPHA']
        self.assertEqual([s['version'] for s in sources], [1, 2])
        self.assertEqual([s['state'] for s in sources], ['superseded', 'current'])
        self.assertEqual(len(state['biological_assets']), 1)
        # A stale assertion cannot be revived; re-assert against the current version.
        with self.assertRaisesRegex(InvalidInput, 'superseded'):
            self.store.add_inventory_assertion(
                'CASE-ALPHA', block, self.path['source_id'], 'Synthetic registrar', **UNKNOWN)
        fresh = self.store.add_inventory_assertion(
            'CASE-ALPHA', block, update['source_id'], 'Synthetic registrar', **UNKNOWN)
        self.assertEqual(self.store.state('CASE-ALPHA')['biological_inventory_assertions'][-1]['id'], fresh)

    def test_wrong_case_access_rejected_and_state_isolated(self):
        block = self.block()
        with self.assertRaisesRegex(InvalidInput, 'not in this case'):
            self.store.add_inventory_assertion(
                'CASE-BETA', block, self.beta['source_id'], 'Synthetic registrar', **UNKNOWN)
        with self.assertRaisesRegex(InvalidInput, 'another case'):
            self.store.add_biological_asset(
                'CASE-ALPHA', 'BLOCK-X', 'ffpe_block', 'EPISODE-A', '2026-05-03',
                self.beta['source_id'])
        with self.assertRaisesRegex(InvalidInput, 'belongs to another case'):
            self.store.add_inventory_assertion(
                'CASE-ALPHA', block, self.beta['source_id'], 'Synthetic registrar', **UNKNOWN)
        self.assertEqual(self.store.state('CASE-BETA')['biological_assets'], [])
        self.assertEqual(self.store.state('CASE-BETA')['biological_inventory_assertions'], [])
        self.assertEqual(len(self.store.state('CASE-ALPHA')['biological_assets']), 1)

    def test_specimen_anchor_and_duplicate_asset_rules(self):
        with self.assertRaisesRegex(InvalidInput, 'must not carry a specimen ID'):
            self.store.add_biological_asset(
                'CASE-ALPHA', 'BLOCK-U', 'ffpe_block', 'EPISODE-A', '2026-05-03',
                self.path['source_id'], specimen_state='unknown', specimen_id='BIOPSY-ALPHA')
        with self.assertRaisesRegex(InvalidInput, 'requires a specimen ID'):
            self.store.add_biological_asset(
                'CASE-ALPHA', 'BLOCK-R', 'ffpe_block', 'EPISODE-A', '2026-05-03',
                self.path['source_id'], specimen_state='recorded')
        self.block()
        with self.assertRaisesRegex(InvalidInput, 'already exists'):
            self.block()
        self.store.import_report('CASE-ALPHA', report('alpha-pathology-amended.txt'))
        with self.assertRaisesRegex(InvalidInput, 'superseded'):
            self.store.add_biological_asset(
                'CASE-ALPHA', 'BLOCK-OLD', 'ffpe_block', 'EPISODE-A', '2026-05-03',
                self.path['source_id'])


if __name__ == '__main__':
    unittest.main()
