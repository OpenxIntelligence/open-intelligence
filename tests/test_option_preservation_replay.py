"""Actual CaseStore replay of an earlier packaging-only synthetic packet.

Original and explicitly derived inputs are separate. No AI inference, clinical
recommendation, live service, new ledger, or independent validation is implied.
Only the receipt clock is controlled; all application operations are real.
"""
import hashlib
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from open_intelligence import CaseStore, InvalidInput
from open_intelligence.store import parse_report, parse_synthetic_evidence
from tools.evaluation_packet import bundle

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / 'validation' / 'option_preservation_replay'
A, B = 'CASE-PRESERVE-A', 'CASE-PRESERVE-B'
UNKNOWN = {key: value for field in ('location', 'quantity', 'custody', 'consent', 'rights')
           for key, value in ((field + '_state', 'unknown'), (field + '_value', None))}


class OptionPreservationReplayTests(unittest.TestCase):
    def setUp(self):
        self.packet = json.loads((DATA / 'replay_packet.json').read_text())
        self.sources = {s['id']: s for s in self.packet['sources']}
        self.tmp = tempfile.TemporaryDirectory()
        self.db_path = Path(self.tmp.name) / 'replay.sqlite'
        self.store = CaseStore(self.db_path)
        for case in self.packet['cases']:
            self.store.add_case(case['id'], case['label'])
        self.seen = set()
        self.outcomes = {}
        self.by_source = {}

    def tearDown(self):
        self.store.close()
        self.tmp.cleanup()

    def advance(self, cutoff):
        inputs = bundle(self.packet, cutoff)
        sources = {s['id']: s for s in inputs['sources']}
        for receipt in inputs['receipts']:
            if receipt['id'] in self.seen:
                continue
            source = sources[receipt['source_id']]
            with patch('open_intelligence.store.now_utc', return_value=receipt['received_at']):
                raw = source['text'].encode('utf-8')
                if source['kind'] == 'report':
                    outcome = self.store.import_report(receipt['target_case'], raw)
                else:
                    outcome = self.store.import_synthetic_evidence(raw)
            self.seen.add(receipt['id'])
            self.outcomes[receipt['id']] = outcome
            if outcome['result'] == 'imported':
                self.by_source[source['id']] = outcome
        return inputs

    def sid(self, key):
        return self.by_source[key]['source_id']

    def option(self, case, snapshot, label):
        return self.store.create_option(case, snapshot, label,
            'Authored fictional preparation discussion; no clinical action.', 'unknown')

    def review(self, case, option, action, snapshot=None):
        return self.store.review_option(case, option, 'Synthetic reviewer', action,
            'Record-only review of an authored fictional discussion.', snapshot)

    def option_row(self, case, option):
        return next(row for row in self.store.option_view(case)['options'] if row['id'] == option)

    def snapshot(self, case, source_key, question='What remains uncertain in this fictional record?'):
        q = self.store.add_question(case, question)
        return self.store.create_snapshot(case, q,
            'Source-linked fictional preparation discussion; feasibility remains unknown.',
            [self.sid(source_key)])

    def restart(self):
        self.store.close()
        self.store = CaseStore(self.db_path)

    def test_original_packet_is_preserved_and_still_rejected_by_strict_parsers(self):
        original = json.loads((DATA / 'original_packet.json').read_text())
        self.assertEqual(len(original['sources']), 15)
        for source in original['sources']:
            raw = source['text'].encode()
            self.assertEqual(hashlib.sha256(raw).hexdigest(), source['sha256'])
            with self.subTest(source=source['id']):
                with self.assertRaises(InvalidInput):
                    (parse_report if source['kind'] == 'report' else parse_synthetic_evidence)(raw)

    def test_lineage_explains_every_source_byte_change_without_rewriting_dates(self):
        original_raw = (DATA / 'original_packet.json').read_bytes()
        replay_raw = (DATA / 'replay_packet.json').read_bytes()
        original = json.loads(original_raw)
        lineage = json.loads((DATA / 'lineage.json').read_text())
        self.assertEqual(hashlib.sha256(original_raw).hexdigest(), lineage['original_file_sha256'])
        self.assertEqual(hashlib.sha256(replay_raw).hexdigest(), lineage['replay_file_sha256'])
        self.assertEqual(original['receipts'], self.packet['receipts'])
        self.assertEqual(original['cutoffs'], self.packet['cutoffs'])
        self.assertEqual(original['cases'], self.packet['cases'])
        changes = {item['source_id']: item for item in lineage['changes']}
        self.assertEqual(set(changes), set(self.sources))
        for source in original['sources']:
            item = changes[source['id']]
            self.assertEqual(item['original_sha256'], source['sha256'])
            self.assertEqual(item['replay_sha256'], self.sources[source['id']]['sha256'])
            old_lines = source['text'].splitlines()
            replacements = {}
            for edit in item['edits']:
                selected = [old_lines[n - 1] for n in edit['original_lines']]
                expected = edit['before'] if isinstance(edit['before'], list) else [edit['before']]
                self.assertEqual(selected, expected)
                self.assertTrue(edit['reason'])
                for i, n in enumerate(edit['original_lines']):
                    self.assertNotIn(n, replacements)
                    replacements[n] = edit['after'] if i == 0 else None
            derived = [replacements.get(n, line) for n, line in enumerate(old_lines, 1)]
            self.assertEqual('\n'.join(line for line in derived if line is not None) + '\n',
                             self.sources[source['id']]['text'])
            for prefix in ('Event-Date: ', 'Issued-At: ', 'Specimen: ', 'Finding: '):
                self.assertEqual([x for x in old_lines if x.startswith(prefix)],
                    [x for x in self.sources[source['id']]['text'].splitlines() if x.startswith(prefix)])

    def test_all_stages_import_with_duplicate_and_quarantine_not_extra_sources(self):
        for cutoff, count_a, count_b, evidence_count in (
                ('T0', 3, 3, 1), ('T1', 5, 4, 2), ('T2', 7, 5, 2)):
            with self.subTest(cutoff=cutoff):
                self.advance(cutoff)
                a, b = self.store.state(A), self.store.state(B)
                self.assertEqual(len(a['sources']), count_a)
                self.assertEqual(len(b['sources']), count_b)
                self.assertEqual(len(a['evidence']), evidence_count)
                self.assertNotIn('CUSTODY-A', {r['document_id'] for r in b['sources']})
        self.assertEqual(len(self.seen), 16)
        self.assertEqual(self.outcomes['R-DUPLICATE']['result'], 'duplicate')
        self.assertEqual(self.outcomes['R-WRONG-TARGET']['result'], 'quarantined')
        self.assertEqual(len(self.store.state(B)['quarantines']), 1)

    def test_t0_sources_and_export_do_not_contain_future_information(self):
        inputs = self.advance('T0')
        early = {s['id'] for s in inputs['sources']}
        self.assertNotIn('A-INVENTORY-V2', early)
        self.assertNotIn('TRIAL-MEMO-V2', early)
        snapshot = self.snapshot(A, 'A-INVENTORY-V1')
        exported = self.store.export_markdown(A, snapshot)
        self.assertIn('Four sections', exported)
        for text in ('Zero sections remain', 'OI-TEST-ASSET-A', '2026-06-17'):
            self.assertNotIn(text, exported)
        for case in (A, B):
            for row in self.store.state(case)['sources']:
                self.assertLessEqual(row['received_at'], self.packet['cutoffs']['T0'])

    def test_bytes_hashes_source_anchors_and_receipt_times_survive_restart(self):
        self.advance('T2')
        before = {case: self.store.state(case) for case in (A, B)}
        self.restart()
        self.assertEqual(before, {case: self.store.state(case) for case in (A, B)})
        for key, outcome in self.by_source.items():
            source = self.sources[key]
            if source['kind'] == 'report':
                case = parse_report(source['text'].encode()).patient_id
                actual = self.store.source_text(case, outcome['source_id'])
                row = next(r for r in self.store.state(case)['sources'] if r['id'] == outcome['source_id'])
            else:
                actual = self.store.synthetic_evidence_text(outcome['evidence_version_id'])
                row = next(r for r in self.store.state(A)['evidence'] if r['id'] == outcome['evidence_version_id'])
            self.assertEqual(actual, source['text'])
            self.assertEqual(hashlib.sha256(actual.encode()).hexdigest(), row['sha256'])
            receipt = next(r for r in self.packet['receipts'] if r['source_id'] == key)
            self.assertEqual(row['received_at'], receipt['received_at'])
        for case in (A, B):
            for assertion in self.store.state(case)['assertions']:
                raw = self.store.source_text(case, assertion['source_version_id'])
                self.assertEqual(raw.splitlines()[assertion['source_line'] - 1],
                    'Finding: ' + '|'.join((assertion['finding_key'], assertion['certainty'], assertion['quote'])))

    def test_inventory_amendment_invalidates_asset_and_option_chain_not_unrelated(self):
        self.advance('T0')
        original = self.snapshot(A, 'A-INVENTORY-V1')
        context = self.snapshot(A, 'A-CONTEXT')
        other = self.snapshot(B, 'B-ROUTINE-CONTROL')
        root = self.option(A, original, 'Fictional material discussion')
        child = self.option(A, context, 'Fictional dependent discussion')
        grandchild = self.option(A, context, 'Fictional later discussion')
        independent = self.option(A, context, 'Fictional independent discussion')
        other_case = self.option(B, other, 'Fictional routine discussion')
        self.store.add_option_dependency(A, child, 'option', depends_on_option_id=root)
        self.store.add_option_dependency(A, grandchild, 'option', depends_on_option_id=child)
        for case, oid in ((A, root), (A, child), (A, grandchild), (A, independent), (B, other_case)):
            self.review(case, oid, 'approve')
        asset = self.store.add_biological_asset(A, 'TEST-BLOCK-A', 'ffpe_block', 'EPISODE-A',
            '2026-05-30', self.sid('A-INVENTORY-V1'), specimen_state='recorded', specimen_id='BLOCK-A-1')
        inventory = self.store.add_inventory_assertion(A, asset, self.sid('A-INVENTORY-V1'),
            'Fictional copied inventory', **{**UNKNOWN, 'quantity_state': 'known',
            'quantity_value': 'Four sections in preliminary inventory; unconfirmed'})
        self.advance('T1')
        result = self.outcomes['R-T1-01']
        self.assertEqual(set(result['invalidated_options']), {root, child, grandchild})
        self.assertEqual(result['invalidated_inventory_assertions'], [inventory])
        for oid in (root, child, grandchild):
            self.assertEqual(self.option_row(A, oid)['review_state'], 'needs_review')
        self.assertEqual(self.option_row(A, independent)['review_state'], 'current')
        self.assertEqual(self.option_row(B, other_case)['review_state'], 'current')
        fresh = self.store.add_inventory_assertion(A, asset, self.sid('A-INVENTORY-V2'),
            'Fictional custodian correction', **{**UNKNOWN, 'quantity_state': 'known',
            'quantity_value': 'Zero sections remain'})
        digital = self.store.add_biological_asset(A, 'TEST-DATA-A', 'genomics_data_pointer',
            'EPISODE-A', '2026-05-26', self.sid('A-OLDER-ACCESSION'), parent_asset_id=asset,
            pointer_label='OI-TEST-ASSET-A')
        self.restart()
        rows = {r['id']: r for r in self.store.state(A)['biological_inventory_assertions']}
        self.assertEqual(rows[inventory]['state'], 'stale')
        self.assertEqual(rows[fresh]['quantity_value'], 'Zero sections remain')
        self.assertFalse(any(r['asset_id'] == digital for r in rows.values()))
        self.assertIn('Four sections', self.store.source_text(A, self.sid('A-INVENTORY-V1')))
        self.assertEqual(self.option_row(A, grandchild)['review_state'], 'needs_review')

    def test_evidence_correction_stales_assessment_backed_option_and_preserves_old_export(self):
        self.advance('T0')
        q = self.store.add_question(B, 'What does the fictional screening memo actually support?')
        ev = self.by_source['TRIAL-MEMO-V1']['evidence_version_id']
        assessment = self.store.assess_synthetic_evidence(B, q, ev, 'context', 'limited',
            'Fictional memo only; no actual eligibility or benefit has been established.')
        snapshot = self.store.create_snapshot(B, q, 'Fictional criterion requires confirmation.',
            [self.sid('B-PLAN-V1')], [assessment])
        option = self.option(B, snapshot, 'Fictional screening clarification')
        independent = self.option(A, self.snapshot(A, 'A-CONTEXT'), 'Fictional unrelated discussion')
        self.advance('T1')
        self.assertEqual(self.option_row(B, option)['review_state'], 'needs_review')
        self.assertEqual(self.option_row(A, independent)['review_state'], 'current')
        old = self.store.export_markdown(B, snapshot)
        self.assertIn('**stale**', old)
        self.assertIn('prior administration of TX-M is an exclusion', old)
        self.assertNotIn('previous TX-M is not an exclusion', old)
        new = self.by_source['TRIAL-MEMO-V2']['evidence_version_id']
        self.assertIn('previous TX-M is not an exclusion', self.store.synthetic_evidence_text(new))
        with self.assertRaises(InvalidInput):
            self.store.create_snapshot(B, q, 'This must not reuse obsolete assessment content.',
                [self.sid('B-PLAN-V1')], [assessment])

    def test_new_plan_events_do_not_rewrite_prior_dates_or_claim_execution(self):
        self.advance('T0')
        old = self.snapshot(A, 'A-PLAN-V1')
        old_raw = self.store.source_text(A, self.sid('A-PLAN-V1'))
        self.advance('T2')
        sources = {r['document_id']: r for r in self.store.state(A)['sources']}
        self.assertEqual(sources['PLAN-A']['event_date'], '2026-06-01')
        self.assertEqual(sources['PLAN-A-UPDATE']['event_date'], '2026-06-06')
        self.assertEqual(sources['PLAN-A']['state'], 'current')
        self.assertEqual(self.store.source_text(A, self.sid('A-PLAN-V1')), old_raw)
        export = self.store.export_markdown(A, old)
        self.assertIn('2026-06-10', export)
        self.assertNotIn('2026-06-17', export)
        self.assertIn('not been documented as performed', self.store.source_text(A, self.sid('A-PLAN-V2')))
        a_rows = self.store.state(A)['assertions']
        acceptance = next(r for r in a_rows if r['finding_key'] == 'acceptance')
        self.assertEqual(acceptance['certainty'], 'not-reported')
        self.assertEqual(self.store.option_view(A)['options'], [])

    def test_rejected_option_and_reason_survive_later_sources_and_restart(self):
        self.advance('T0')
        oid = self.option(B, self.snapshot(B, 'B-UNVERIFIED-OPTION'), 'Unverified fictional candidate')
        self.review(B, oid, 'reject')
        self.advance('T2')
        self.restart()
        before = self.store.state(B)
        self.assertEqual(self.option_row(B, oid)['operational_status'], 'rejected')
        self.assertEqual(self.option_row(B, oid)['review_events'][0]['action'], 'reject')
        with self.assertRaises(InvalidInput):
            self.review(B, oid, 'approve')
        self.assertEqual(self.store.state(B), before)
        self.assertIn('not accepting new screening', self.store.source_text(B, self.sid('B-SITE-REPLY')))

    def test_duplicate_and_repeated_wrong_case_delivery_make_no_new_events(self):
        self.advance('T2')
        before = {case: self.store.state(case) for case in (A, B)}
        duplicate = self.store.import_report(A, self.sources['A-INVENTORY-V1']['text'].encode())
        wrong = self.store.import_report(B, self.sources['A-CUSTODY-CHALLENGE']['text'].encode())
        self.assertEqual(duplicate['result'], 'duplicate')
        self.assertTrue(wrong['duplicate'])
        self.assertEqual(before, {case: self.store.state(case) for case in (A, B)})

    def test_out_of_order_amendment_and_cross_case_snapshot_are_rejected(self):
        before = self.store.state(A)
        with self.assertRaises(InvalidInput):
            self.store.import_report(A, self.sources['A-INVENTORY-V2']['text'].encode())
        self.assertEqual(self.store.state(A), before)
        self.advance('T0')
        question = self.store.add_question(B, 'Fictional cross-case isolation check?')
        before_b = self.store.state(B)
        with self.assertRaises(InvalidInput):
            self.store.create_snapshot(B, question, 'This should not link another fictional subject.',
                [self.sid('A-CONTEXT')])
        self.assertEqual(self.store.state(B), before_b)

    def test_routine_control_has_no_invented_deadline(self):
        self.advance('T2')
        oid = self.option(B, self.snapshot(B, 'B-ROUTINE-CONTROL'), 'Fictional routine request')
        deadline = self.option_row(B, oid)['potential_discussion_deadline']
        self.assertIsNone(deadline['date'])
        self.assertEqual(deadline['basis'], 'unknown')
        self.assertEqual(self.option_row(B, oid)['preparation_tasks'], [])


if __name__ == '__main__':
    unittest.main()
