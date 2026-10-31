import tempfile
import unittest
from pathlib import Path

from open_intelligence import CaseStore, InvalidInput, parse_report

ROOT = Path(__file__).resolve().parents[1]
SAMPLE = ROOT / 'examples' / 'synthetic'


def report(name):
    return (SAMPLE / name).read_bytes()


class StoreTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.db_path = Path(self.tmp.name) / 'test.sqlite'
        self.store = CaseStore(self.db_path)
        self.store.add_case('CASE-ALPHA', 'Fictional Alpha')
        self.store.add_case('CASE-BETA', 'Fictional Beta')

    def tearDown(self):
        self.store.close()
        self.tmp.cleanup()

    def test_original_bytes_sha_and_line_anchors(self):
        original = report('alpha-pathology-original.txt')
        result = self.store.import_report('CASE-ALPHA', original)
        self.assertEqual(result['result'], 'imported')
        state = self.store.state('CASE-ALPHA')
        source = state['sources'][0]
        self.assertEqual(source['version'], 1)
        self.assertEqual(source['event_date'], '2026-05-03')
        self.assertEqual(source['issued_at'], '2026-05-05')
        self.assertNotEqual(source['received_at'][:10], source['event_date'])
        self.assertEqual(len(source['sha256']), 64)
        self.assertEqual(self.store.source_text('CASE-ALPHA', source['id']).encode('utf-8'), original)
        lines = original.decode().splitlines()
        for item in state['assertions']:
            self.assertIn(item['quote'], lines[item['source_line'] - 1])
        statuses = {x['finding_key']: x['certainty'] for x in state['assertions']}
        self.assertEqual(statuses, {'histology': 'reported', 'marker-a': 'not-reported', 'margin': 'indeterminate'})

    def test_duplicate_import_is_noop_even_after_amendment(self):
        first = self.store.import_report('CASE-ALPHA', report('alpha-pathology-original.txt'))
        event_count = len(self.store.state('CASE-ALPHA')['events'])
        again = self.store.import_report('CASE-ALPHA', report('alpha-pathology-original.txt'))
        self.assertEqual(again, {'result': 'duplicate', 'source_id': first['source_id'], 'version': 1})
        self.assertEqual(len(self.store.state('CASE-ALPHA')['events']), event_count)
        self.store.import_report('CASE-ALPHA', report('alpha-pathology-amended.txt'))
        again_old = self.store.import_report('CASE-ALPHA', report('alpha-pathology-original.txt'))
        self.assertEqual(again_old['result'], 'duplicate')
        self.assertEqual(len(self.store.state('CASE-ALPHA')['sources']), 2)

    def test_changed_document_needs_explicit_latest_amendment(self):
        original = report('alpha-pathology-original.txt')
        self.store.import_report('CASE-ALPHA', original)
        changed = original.replace(b'not tested', b'was not tested')
        with self.assertRaisesRegex(InvalidInput, 'Amends'):
            self.store.import_report('CASE-ALPHA', changed)
        self.assertEqual(len(self.store.state('CASE-ALPHA')['sources']), 1)
        invalid = report('alpha-pathology-amended.txt').replace(b'PATH-ALPHA@1', b'PATH-ALPHA@3')
        with self.assertRaisesRegex(InvalidInput, 'Amends'):
            self.store.import_report('CASE-ALPHA', invalid)
        self.assertEqual(len(self.store.state('CASE-ALPHA')['sources']), 1)

    def test_amendment_cannot_silently_reassign_specimen_or_event(self):
        original = report('alpha-pathology-original.txt')
        self.store.import_report('CASE-ALPHA', original)
        amended = report('alpha-pathology-amended.txt')
        for updated in (
            amended.replace(b'Specimen: BIOPSY-ALPHA', b'Specimen: BIOPSY-NEW'),
            amended.replace(b'Event-Date: 2026-05-03', b'Event-Date: 2026-06-03'),
            amended.replace(b'Type: pathology', b'Type: molecular'),
        ):
            with self.subTest(updated=updated[:140]):
                with self.assertRaisesRegex(InvalidInput, 'Amendment cannot change'):
                    self.store.import_report('CASE-ALPHA', updated)
        self.assertEqual(len(self.store.state('CASE-ALPHA')['sources']), 1)
        result = self.store.import_report('CASE-ALPHA', amended)
        self.assertEqual(result['version'], 2)

    def test_amendment_invalidates_only_dependent_case_snapshot(self):
        first = self.store.import_report('CASE-ALPHA', report('alpha-pathology-original.txt'))
        img = self.store.import_report('CASE-ALPHA', report('alpha-imaging.txt'))
        beta = self.store.import_report('CASE-BETA', report('beta-pathology.txt'))
        q1 = self.store.add_question('CASE-ALPHA', 'What was actually reported about marker A?')
        q2 = self.store.add_question('CASE-ALPHA', 'What did the imaging comparison report?')
        qb = self.store.add_question('CASE-BETA', 'What remains uncertain in the fictional beta case?')
        s1 = self.store.create_snapshot('CASE-ALPHA', q1, 'Marker A has not been reported in the first source.', [first['source_id']])
        s2 = self.store.create_snapshot('CASE-ALPHA', q2, 'Only the imaging report is used for this summary.', [img['source_id']])
        sb = self.store.create_snapshot('CASE-BETA', qb, 'The beta case is an independent synthetic subject.', [beta['source_id']])
        self.store.acknowledge_demo_review('CASE-ALPHA', s1, 'Unverified synthetic reviewer')
        self.store.acknowledge_demo_review('CASE-BETA', sb, 'Unverified synthetic reviewer')
        update = self.store.import_report('CASE-ALPHA', report('alpha-pathology-amended.txt'))
        self.assertEqual(update['invalidated_snapshots'], [s1])
        alpha_state = self.store.state('CASE-ALPHA')
        states = {s['id']: s['state'] for s in alpha_state['snapshots']}
        self.assertEqual(states[s1], 'stale')
        self.assertEqual(states[s2], 'draft')
        self.assertEqual({q['id']: q['state'] for q in alpha_state['questions']}[q1], 'open')
        self.assertEqual(self.store.state('CASE-BETA')['snapshots'][0]['state'], 'reviewed_in_demo')
        self.assertEqual([x['version'] for x in alpha_state['sources'] if x['document_id'] == 'PATH-ALPHA'], [1, 2])
        self.assertEqual([x['state'] for x in alpha_state['sources'] if x['document_id'] == 'PATH-ALPHA'], ['superseded', 'current'])
        # No implicit promotion of the new findings into a reviewed conclusion.
        with self.assertRaisesRegex(InvalidInput, 'Only a current draft'):
            self.store.acknowledge_demo_review('CASE-ALPHA', s1, 'Unverified synthetic reviewer')
        self.assertIn('**stale**', self.store.export_markdown('CASE-ALPHA', s1))
        self.assertIn('Marker A was not tested', self.store.export_markdown('CASE-ALPHA', s1))
        replacement_id = self.store.create_snapshot('CASE-ALPHA', q1, 'Amended report now states that a fictional assay was negative.', [update['source_id']])
        self.assertEqual(self.store.state('CASE-ALPHA')['snapshots'][0]['state'], 'draft')
        self.assertIn('Marker A assay was performed', self.store.export_markdown('CASE-ALPHA', replacement_id))

    def test_repeated_wrong_patient_input_keeps_one_quarantine_receipt(self):
        wrong = report('wrong-patient.txt')
        first = self.store.import_report('CASE-ALPHA', wrong)
        self.assertEqual(first['result'], 'quarantined')
        before = self.store.state('CASE-ALPHA')
        again = self.store.import_report('CASE-ALPHA', wrong)
        after = self.store.state('CASE-ALPHA')
        self.assertEqual(again['quarantine_id'], first['quarantine_id'])
        self.assertTrue(again['duplicate'])
        self.assertEqual(len(after['quarantines']), 1)
        self.assertEqual(len(after['events']), len(before['events']))
        self.assertEqual(after['assertions'], [])

    def test_export_contains_source_backticks_inside_safe_fence(self):
        # Even synthetic authored text can contain Markdown delimiters.
        original = report('alpha-pathology-original.txt')
        modified = original.replace(b'not tested', b'not tested ```')
        self.assertNotEqual(original, modified)
        first = self.store.import_report('CASE-ALPHA', modified)
        question = self.store.add_question('CASE-ALPHA', 'What was not tested in this report?')
        snapshot = self.store.create_snapshot('CASE-ALPHA', question,
                                             'This is a human-authored synthetic-only draft.',
                                             [first['source_id']])
        exported = self.store.export_markdown('CASE-ALPHA', snapshot)
        self.assertIn('\n````text\n', exported)
        self.assertIn('not tested ```', exported)
        self.assertIn('\n````\n', exported)

    def test_wrong_patient_quarantined_without_facts(self):
        result = self.store.import_report('CASE-ALPHA', report('wrong-patient.txt'))
        self.assertEqual(result['result'], 'quarantined')
        state = self.store.state('CASE-ALPHA')
        self.assertEqual(len(state['quarantines']), 1)
        self.assertEqual(state['sources'], [])
        self.assertEqual(state['assertions'], [])
        self.assertEqual(self.store.state('CASE-BETA')['sources'], [])

    def test_case_scoped_refs_and_reads(self):
        first = self.store.import_report('CASE-ALPHA', report('alpha-pathology-original.txt'))
        q = self.store.add_question('CASE-BETA', 'What do the historical reports establish?')
        with self.assertRaisesRegex(InvalidInput, 'Source is missing'):
            self.store.create_snapshot('CASE-BETA', q, 'Trying to cross the synthetic case boundary.', [first['source_id']])
        with self.assertRaisesRegex(InvalidInput, 'Source not in this case'):
            self.store.source_text('CASE-BETA', first['source_id'])
        with self.assertRaisesRegex(InvalidInput, 'Question not in this case'):
            self.store.create_snapshot('CASE-ALPHA', q, 'Cannot use a question from the other case.', [first['source_id']])

    def test_recovered_state_after_reopen(self):
        self.store.import_report('CASE-ALPHA', report('alpha-pathology-original.txt'))
        q = self.store.add_question('CASE-ALPHA', 'What is not reported about molecular findings?')
        first_id = self.store.state('CASE-ALPHA')['sources'][0]['id']
        draft = self.store.create_snapshot('CASE-ALPHA', q, 'The initial report does not report this molecular finding.', [first_id])
        self.store.close()
        self.store = CaseStore(self.db_path)
        self.assertEqual(self.store.state('CASE-ALPHA')['snapshots'][0]['id'], draft)
        self.assertEqual(self.store.state('CASE-ALPHA')['assertions'][0]['source_version_id'], first_id)

    def test_invalid_text_never_becomes_partial_ingest(self):
        data = report('alpha-pathology-original.txt')
        for bad in [b'not a report', b'\xff', data.replace(b'Event-Date: 2026-05-03', b'Event-Date: yesterday'),
                    data.replace(b'Finding: margin', b'Finding: marker-a'),
                    data.replace(b'not-reported', b'positive')]:
            with self.subTest(bad=bad[:20]):
                with self.assertRaises(InvalidInput):
                    self.store.import_report('CASE-ALPHA', bad)
        self.assertEqual(self.store.state('CASE-ALPHA')['sources'], [])

    def test_mutated_snapshot_cannot_be_clinically_approved(self):
        self.store.import_report('CASE-ALPHA', report('alpha-pathology-original.txt'))
        q = self.store.add_question('CASE-ALPHA', 'What is unresolved in this fictional biopsy?')
        sid = self.store.state('CASE-ALPHA')['sources'][0]['id']
        draft = self.store.create_snapshot('CASE-ALPHA', q, 'Research draft, with no credentialed reviewer available.', [sid])
        self.store.acknowledge_demo_review('CASE-ALPHA', draft, 'A fictional person')
        self.assertEqual(self.store.state('CASE-ALPHA')['snapshots'][0]['state'], 'reviewed_in_demo')
        self.assertIn('not clinician credential verification', self.store.export_markdown('CASE-ALPHA', draft))
        with self.assertRaises(InvalidInput):
            self.store.acknowledge_demo_review('CASE-ALPHA', draft, 'Again')

    def test_parser_does_not_confuse_missing_with_negative(self):
        initial = parse_report(report('alpha-pathology-original.txt'))
        amended = parse_report(report('alpha-pathology-amended.txt'))
        old = {x.key: x.state for x in initial.findings}
        new = {x.key: x.state for x in amended.findings}
        self.assertEqual(old['marker-a'], 'not-reported')
        self.assertEqual(new['marker-a'], 'negative')
        self.assertEqual(old['margin'], 'indeterminate')
        self.assertEqual(new['margin'], 'indeterminate')


if __name__ == '__main__':
    unittest.main()
