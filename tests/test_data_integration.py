"""Data-integration dimension (slice D1): A1 extraction proposals and the T3 specimen chain.

A1 acceptance: no extraction without an anchor -- every field of a
proposal names a source version that exists, belongs to the case, and is
current, plus an exact quote and source line; anything else is dropped
with a typed reason, never stored. T3 acceptance: chain breaks are typed
records, never silent -- a broken chain is reported, not crashed on.
"""

import tempfile
import unittest
from pathlib import Path

from open_intelligence import CaseStore, InvalidInput
from open_intelligence.extraction import (
    record_extraction_proposal,
    validate_extraction_proposal,
)
from open_intelligence.specimen_chain import validate_specimen_chain

ROOT = Path(__file__).resolve().parents[1]
SAMPLE = ROOT / 'examples' / 'synthetic'


def report(name):
    return (SAMPLE / name).read_bytes()


class DataIntegrationTestBase(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.TemporaryDirectory()
        self.store = CaseStore(Path(self.dir.name) / 't.db')
        self.store.add_case('CASE-ALPHA', 'Fictional Alpha')
        self.store.add_case('CASE-BETA', 'Fictional Beta')
        self.alpha_v1 = self.store.import_report(
            'CASE-ALPHA', report('alpha-pathology-original.txt'))['source_id']
        self.beta_v1 = self.store.import_report(
            'CASE-BETA', report('beta-pathology.txt'))['source_id']

    def tearDown(self):
        self.dir.cleanup()

    def make_chain(self, slide_specimen_state='recorded',
                   slide_specimen_id='BIOPSY-ALPHA'):
        """Block -> slide -> WSI in CASE-ALPHA, all anchored to alpha v1."""
        block = self.store.add_biological_asset(
            'CASE-ALPHA', 'BLOCK-A', 'ffpe_block', 'EPISODE-A', '2026-05-03',
            self.alpha_v1, specimen_state='recorded',
            specimen_id='BIOPSY-ALPHA')
        slide = self.store.add_biological_asset(
            'CASE-ALPHA', 'SLIDE-A', 'slide', 'EPISODE-A', '2026-05-04',
            self.alpha_v1, parent_asset_id=block,
            specimen_state=slide_specimen_state,
            specimen_id=slide_specimen_id)
        wsi = self.store.add_biological_asset(
            'CASE-ALPHA', 'WSI-A', 'digital_wsi', 'EPISODE-A', '2026-05-05',
            self.alpha_v1, parent_asset_id=slide,
            specimen_state='recorded', specimen_id='BIOPSY-ALPHA')
        return block, slide, wsi

    def break_types(self, validation):
        return {b['type'] for b in validation.breaks}


class ExtractionProposalTests(DataIntegrationTestBase):
    def test_valid_proposal_records_assertions(self):
        fields = [{"finding_key": "new-finding", "certainty": "reported",
                   "quote": "Fictional biopsy reports a malignant epithelial neoplasm;", "source_line": 8}]
        validation = record_extraction_proposal(
            self.store, 'CASE-ALPHA', self.alpha_v1, fields)
        self.assertEqual(validation.dropped, [])
        self.assertEqual(len(validation.kept), 1)
        self.assertEqual(len(validation.inserted_assertion_ids), 1)
        row = self.store.db.execute(
            "SELECT finding_key, certainty, quote, source_line FROM assertions "
            "WHERE source_version_id=? AND finding_key=?",
            (self.alpha_v1, 'new-finding')).fetchone()
        self.assertEqual(
            (row['finding_key'], row['certainty'], row['quote'],
             row['source_line']),
            ('new-finding', 'reported', 'Fictional biopsy reports a malignant epithelial neoplasm;', 8))

    def test_unknown_source_version_drops_all_fields(self):
        fields = [{"finding_key": "new-finding", "certainty": "reported",
                   "quote": "Fictional biopsy reports a malignant epithelial neoplasm;", "source_line": 8}]
        validation = validate_extraction_proposal(
            self.store, 'CASE-ALPHA', 999999, fields)
        self.assertEqual(validation.kept, [])
        self.assertEqual(
            [d['reason'] for d in validation.dropped],
            ['unknown_source_version'])
        self.assertEqual(
            self.store.db.execute(
                "SELECT COUNT(*) FROM assertions WHERE finding_key=?",
                ('new-finding',)).fetchone()[0], 0)

    def test_wrong_case_source_version_drops_all_fields(self):
        fields = [{"finding_key": "new-finding", "certainty": "reported",
                   "quote": "Fictional biopsy reports a malignant epithelial neoplasm;", "source_line": 8}]
        validation = validate_extraction_proposal(
            self.store, 'CASE-BETA', self.alpha_v1, fields)
        self.assertEqual(validation.kept, [])
        self.assertEqual(
            [d['reason'] for d in validation.dropped],
            ['wrong_case_source_version'])

    def test_superseded_source_version_drops_all_fields(self):
        self.store.import_report(
            'CASE-ALPHA', report('alpha-pathology-amended.txt'))
        fields = [{"finding_key": "new-finding", "certainty": "reported",
                   "quote": "Fictional biopsy reports a malignant epithelial neoplasm;", "source_line": 8}]
        validation = validate_extraction_proposal(
            self.store, 'CASE-ALPHA', self.alpha_v1, fields)
        self.assertEqual(validation.kept, [])
        self.assertEqual(
            [d['reason'] for d in validation.dropped],
            ['superseded_source_version'])

    def test_invalid_source_version_id_drops_all_fields(self):
        fields = [{"finding_key": "new-finding", "certainty": "reported",
                   "quote": "Fictional biopsy reports a malignant epithelial neoplasm;", "source_line": 8}]
        for bad_id in (0, -1, 'x'):
            validation = validate_extraction_proposal(
                self.store, 'CASE-ALPHA', bad_id, fields)
            self.assertEqual(validation.kept, [])
            self.assertEqual(
                [d['reason'] for d in validation.dropped],
                ['invalid_source_version_id'])

    def test_field_level_rejections_are_typed(self):
        fields = [
            {"finding_key": "valid-key", "certainty": "reported",
             "quote": "Fictional biopsy reports a malignant epithelial neoplasm;", "source_line": 8},
            {"finding_key": "Bad Key", "certainty": "reported",
             "quote": "Bad key.", "source_line": 1},
            {"finding_key": "bad-certainty", "certainty": "certain",
             "quote": "Bad certainty.", "source_line": 1},
            {"finding_key": "no-quote", "certainty": "reported",
             "quote": "   ", "source_line": 1},
            {"finding_key": "long-quote", "certainty": "reported",
             "quote": "x" * 1201, "source_line": 1},
            {"finding_key": "bad-line", "certainty": "reported",
             "quote": "Bad line.", "source_line": 0},
            "not a dict",
            {"finding_key": "valid-key", "certainty": "reported",
             "quote": "Repeated key.", "source_line": 2},
            {"finding_key": "histology", "certainty": "reported",
             "quote": "Already asserted by the import.", "source_line": 1},
        ]
        validation = validate_extraction_proposal(
            self.store, 'CASE-ALPHA', self.alpha_v1, fields)
        self.assertEqual(
            [k['finding_key'] for k in validation.kept], ['valid-key'])
        self.assertEqual(
            sorted(d['reason'] for d in validation.dropped),
            sorted(['invalid_finding_key', 'invalid_certainty',
                    'missing_quote', 'quote_too_long',
                    'invalid_source_line', 'malformed_field',
                    'duplicate_finding_key', 'finding_already_asserted']))
        self.assertTrue(all(d['check'] == 'A1' for d in validation.dropped))

    def test_quote_and_location_must_match_original(self):
        fields = [
            {"finding_key": "invented-quote", "certainty": "reported",
             "quote": "A statement absent from the original.", "source_line": 8},
            {"finding_key": "wrong-line", "certainty": "reported",
             "quote": "Fictional biopsy reports a malignant epithelial neoplasm;", "source_line": 9},
            {"finding_key": "past-end", "certainty": "reported",
             "quote": "Fictional biopsy reports a malignant epithelial neoplasm;", "source_line": 9000},
        ]
        result = record_extraction_proposal(
            self.store, "CASE-ALPHA", self.alpha_v1, fields)
        self.assertEqual(result.kept, [])
        self.assertEqual(result.inserted_assertion_ids, [])
        self.assertEqual([d["reason"] for d in result.dropped], [
            "source_quote_mismatch", "source_quote_mismatch",
            "source_line_out_of_range"])
        self.assertEqual(self.store.db.execute(
            "SELECT COUNT(*) FROM assertions WHERE source_version_id=? "
            "AND finding_key IN ('invented-quote','wrong-line','past-end')",
            (self.alpha_v1,)).fetchone()[0], 0)

    def test_corrupted_original_is_not_usable_as_an_anchor(self):
        self.store.db.execute(
            "UPDATE source_versions SET raw=? WHERE id=?",
            (b"rewritten original", self.alpha_v1))
        result = record_extraction_proposal(
            self.store, "CASE-ALPHA", self.alpha_v1,
            [{"finding_key": "corrupt-source", "certainty": "reported",
              "quote": "Fictional biopsy reports a malignant epithelial neoplasm;", "source_line": 8}])
        self.assertEqual(result.kept, [])
        self.assertEqual(result.dropped[0]["reason"],
                         "source_integrity_mismatch")

    def test_import_path_still_creates_assertions(self):
        rows = self.store.db.execute(
            "SELECT finding_key FROM assertions WHERE source_version_id=? "
            "ORDER BY finding_key", (self.alpha_v1,)).fetchall()
        self.assertEqual(
            [r['finding_key'] for r in rows],
            ['histology', 'margin', 'marker-a'])

    def test_malformed_proposal_container_raises(self):
        with self.assertRaises(InvalidInput):
            record_extraction_proposal(
                self.store, 'CASE-ALPHA', self.alpha_v1, None)
        with self.assertRaises(InvalidInput):
            record_extraction_proposal(
                self.store, '', self.alpha_v1, [])

    def test_record_inside_a_caller_transaction_stores_with_it(self):
        fields = [{"finding_key": "tx-finding", "certainty": "reported",
                   "quote": "Fictional biopsy reports a malignant epithelial neoplasm;",
                   "source_line": 8}]
        with self.store.db:
            self.store.db.execute("BEGIN IMMEDIATE")
            validation = record_extraction_proposal(
                self.store, 'CASE-ALPHA', self.alpha_v1, fields)
        self.assertEqual(len(validation.kept), 1)
        self.assertEqual(
            self.store.db.execute(
                "SELECT COUNT(*) FROM assertions WHERE finding_key=?",
                ('tx-finding',)).fetchone()[0], 1)


class SpecimenChainTests(DataIntegrationTestBase):
    def test_intact_chain_links_carry_basis_root_first(self):
        block, slide, wsi = self.make_chain()
        validation = validate_specimen_chain(self.store, 'CASE-ALPHA', wsi)
        self.assertTrue(validation.intact)
        self.assertEqual(validation.breaks, [])
        self.assertEqual(
            [link.asset_pk for link in validation.links],
            [block, slide, wsi])
        root = validation.links[0]
        self.assertEqual(root.asset_id, 'BLOCK-A')
        self.assertEqual(root.kind, 'ffpe_block')
        self.assertEqual(root.episode_id, 'EPISODE-A')
        self.assertEqual(root.specimen_id, 'BIOPSY-ALPHA')
        self.assertEqual(root.specimen_state, 'recorded')
        self.assertEqual(root.anchor_document_id, 'PATH-ALPHA')
        self.assertEqual(root.anchor_version, 1)
        self.assertEqual(root.anchor_state, 'current')
        self.assertEqual(validation.links[-1].kind, 'digital_wsi')

    def test_unknown_specimen_link_is_typed(self):
        _, slide, wsi = self.make_chain(slide_specimen_state='unknown',
                                        slide_specimen_id=None)
        validation = validate_specimen_chain(self.store, 'CASE-ALPHA', wsi)
        self.assertFalse(validation.intact)
        self.assertEqual(self.break_types(validation), {'unknown_specimen'})
        self.assertEqual(
            [b['asset_pk'] for b in validation.breaks], [slide])

    def test_specimen_mismatch_is_typed(self):
        _, slide, wsi = self.make_chain(
            slide_specimen_id='BIOPSY-OTHER')
        validation = validate_specimen_chain(self.store, 'CASE-ALPHA', wsi)
        self.assertFalse(validation.intact)
        self.assertEqual(self.break_types(validation), {'specimen_mismatch'})
        # The slide's specimen disagrees with both its parent (the
        # block) and its child (the WSI), so both links are reported.
        self.assertEqual(
            [b['asset_pk'] for b in validation.breaks], [slide, wsi])

    def test_anchor_superseded_is_typed(self):
        _, _, wsi = self.make_chain()
        self.store.import_report(
            'CASE-ALPHA', report('alpha-pathology-amended.txt'))
        validation = validate_specimen_chain(self.store, 'CASE-ALPHA', wsi)
        self.assertFalse(validation.intact)
        self.assertEqual(self.break_types(validation), {'anchor_superseded'})
        self.assertEqual(len(validation.breaks), 3)

    def test_missing_asset_is_typed(self):
        validation = validate_specimen_chain(self.store, 'CASE-ALPHA', 999999)
        self.assertFalse(validation.intact)
        self.assertEqual(validation.links, [])
        self.assertEqual(self.break_types(validation), {'missing_asset'})

    def test_cycle_is_typed(self):
        _, slide, wsi = self.make_chain()
        # Fabricated after creation: the slide's parent becomes its own
        # child, so the chain repeats. No update path can create this.
        self.store.db.execute(
            "UPDATE biological_assets SET parent_asset_id=? WHERE id=?",
            (wsi, slide))
        validation = validate_specimen_chain(self.store, 'CASE-ALPHA', wsi)
        self.assertFalse(validation.intact)
        self.assertEqual(self.break_types(validation), {'cycle'})

    def test_missing_parent_is_typed(self):
        block, slide, _ = self.make_chain()
        # Fabricated after creation: the parent row is gone while the
        # slide still points at it. Foreign keys are off only for the
        # deletion itself, then restored.
        self.store.db.execute("PRAGMA foreign_keys=OFF")
        try:
            self.store.db.execute(
                "DELETE FROM biological_assets WHERE id=?", (block,))
        finally:
            self.store.db.execute("PRAGMA foreign_keys=ON")
        validation = validate_specimen_chain(self.store, 'CASE-ALPHA', slide)
        self.assertFalse(validation.intact)
        self.assertEqual(self.break_types(validation), {'missing_parent'})
        self.assertEqual(
            [b['asset_pk'] for b in validation.breaks], [block])

    def test_kind_violation_is_typed(self):
        _, slide, wsi = self.make_chain()
        # Fabricated after creation: the block's kind is rewritten so
        # the slide's parent kind can no longer derive a slide.
        self.store.db.execute(
            "UPDATE biological_assets SET kind='slide' WHERE asset_id=?",
            ('BLOCK-A',))
        validation = validate_specimen_chain(self.store, 'CASE-ALPHA', wsi)
        self.assertFalse(validation.intact)
        self.assertEqual(self.break_types(validation), {'kind_violation'})
        self.assertEqual(
            [b['asset_pk'] for b in validation.breaks], [slide])

    def test_episode_mismatch_is_typed(self):
        _, slide, wsi = self.make_chain()
        # Fabricated after creation: the slide moves to another episode,
        # so both adjacent pairs disagree.
        self.store.db.execute(
            "UPDATE biological_assets SET episode_id='EPISODE-B' WHERE id=?",
            (slide,))
        validation = validate_specimen_chain(self.store, 'CASE-ALPHA', wsi)
        self.assertFalse(validation.intact)
        self.assertEqual(self.break_types(validation), {'episode_mismatch'})
        self.assertEqual(len(validation.breaks), 2)

    def test_cross_case_asset_is_missing(self):
        block, _, _ = self.make_chain()
        validation = validate_specimen_chain(self.store, 'CASE-BETA', block)
        self.assertFalse(validation.intact)
        self.assertEqual(self.break_types(validation), {'missing_asset'})

    def test_invalid_asset_id_is_typed(self):
        for bad_id in (0, -1, 'x'):
            validation = validate_specimen_chain(
                self.store, 'CASE-ALPHA', bad_id)
            self.assertFalse(validation.intact)
            self.assertEqual(
                self.break_types(validation), {'invalid_asset_id'})


if __name__ == '__main__':
    unittest.main()
