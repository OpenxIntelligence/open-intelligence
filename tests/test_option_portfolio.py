"""Option portfolio: objections, defer/reserve holds, dimension notes.

Fictional engineering fixtures only. The portfolio states no eligibility,
benefit, safety, or authorization; every entry is a reviewable record for a
clinician, with sources cited. Deferred, rejected, and reserved entries stay
preserved and distinguishable, never silently dropped.
"""
import json
import tempfile
import threading
import unittest
from http.server import ThreadingHTTPServer
from pathlib import Path
from urllib.error import HTTPError
from urllib.request import Request, urlopen

from open_intelligence import CaseStore, InvalidInput
from open_intelligence.__main__ import Handler, seed
from session_auth import signin_demo

ROOT = Path(__file__).resolve().parents[1]
SAMPLE = ROOT / 'examples' / 'synthetic'

PORTFOLIO_STATUSES = frozenset({
    "proposed", "reviewed", "held", "rejected", "withdrawn", "expired",
    "deferred", "reserved"})


def report(name):
    return (SAMPLE / name).read_bytes()


class PortfolioStoreTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.store = CaseStore(Path(self.tmp.name) / 'portfolio.sqlite')
        self.store.add_case('CASE-ALPHA', 'Fictional Alpha')
        self.store.add_case('CASE-BETA', 'Fictional Beta')
        self.path = self.store.import_report('CASE-ALPHA', report('alpha-pathology-original.txt'))
        self.img = self.store.import_report('CASE-ALPHA', report('alpha-imaging.txt'))
        self.beta = self.store.import_report('CASE-BETA', report('beta-pathology.txt'))
        self.q = self.store.add_question('CASE-ALPHA', 'What options are discussed in this fictional case?')
        self.q_beta = self.store.add_question('CASE-BETA', 'What options are discussed in the beta case?')
        self.snap = self.store.create_snapshot(
            'CASE-ALPHA', self.q, 'A human-authored synthetic discussion draft.',
            [self.path['source_id']])
        self.snap_beta = self.store.create_snapshot(
            'CASE-BETA', self.q_beta, 'A human-authored synthetic beta draft.',
            [self.beta['source_id']])

    def tearDown(self):
        self.store.close()
        self.tmp.cleanup()

    def _option(self, case='CASE-ALPHA', snapshot=None, label='Fictional discussion item A'):
        return self.store.create_option(
            case, snapshot or (self.snap if case == 'CASE-ALPHA' else self.snap_beta),
            label, 'A fictional item discussed for planning purposes only.', 'unknown')

    def _entry(self, option_id, case='CASE-ALPHA'):
        for entry in self.store.option_portfolio(case)['options']:
            if entry['id'] == option_id:
                return entry
        self.fail(f'option {option_id} not in portfolio')

    def test_rejected_option_stays_visible_as_rejected_not_deleted(self):
        option = self._option()
        self.store.review_option('CASE-ALPHA', option, 'Synthetic reviewer', 'reject',
                                 'Rejected for fictional test purposes.')
        entry = self._entry(option)
        self.assertEqual(entry['portfolio_status'], 'rejected')
        self.assertEqual(entry['operational_status'], 'rejected')
        self.assertEqual(entry['review_events'][0]['action'], 'reject')
        self.assertEqual(self.store.option_portfolio('CASE-ALPHA')['counts'].get('rejected'), 1)
        # Still present in the underlying view too, with its history intact.
        view = {o['id']: o for o in self.store.option_view('CASE-ALPHA')['options']}
        self.assertIn(option, view)
        self.assertEqual(view[option]['operational_status'], 'rejected')

    def test_held_option_is_reviewed_when_documented_reason_changes(self):
        option = self._option()
        flag = self.store.add_option_flag(
            'CASE-ALPHA', option, 'objection', 'Fictional assay concern',
            'A fictional note questions the assay wording; hold for re-review.',
            'Synthetic recorder')
        entry = self._entry(option)
        self.assertEqual(entry['portfolio_status'], 'held')
        self.assertEqual(len(entry['objections']['open']), 1)
        with self.assertRaisesRegex(InvalidInput, 'cannot be approved'):
            self.store.review_option('CASE-ALPHA', option, 'Synthetic reviewer', 'approve',
                                     'Discussion-only review scope for this item.')
        # The reason changes: resolving the objection reopens review.
        result = self.store.resolve_option_flag(
            'CASE-ALPHA', flag, 'Synthetic reviewer', 'resolve',
            'The fictional assay wording was clarified on re-read.')
        self.assertEqual(result['result'], 'resolve')
        self.assertIn(option, result['invalidated_options'])
        entry = self._entry(option)
        self.assertEqual(entry['review_state'], 'needs_review')
        self.assertEqual(entry['objections']['open'], [])
        self.assertEqual(len(entry['objections']['resolved']), 1)
        self.assertIn('Re-review trigger', ' '.join(entry['triggers']))
        # The held option can now be re-reviewed on a replacement snapshot.
        q2 = self.store.add_question('CASE-ALPHA', 'What is discussed after the re-read?')
        replacement = self.store.create_snapshot(
            'CASE-ALPHA', q2, 'A human-authored post-clarification discussion draft.',
            [self.path['source_id'], self.img['source_id']])
        self.store.review_option('CASE-ALPHA', option, 'Synthetic reviewer', 'reconfirm',
                                 'Re-review after the recorded reason changed.', replacement)
        self.store.review_option('CASE-ALPHA', option, 'Synthetic reviewer', 'approve',
                                 'Discussion-only review scope for this item.')
        entry = self._entry(option)
        self.assertEqual(entry['portfolio_status'], 'reviewed')
        self.assertEqual(entry['review_state'], 'current')

    def test_premise_amendment_reopens_option_held_for_a_documented_reason(self):
        # Both options sit on an imaging-only snapshot, so the pathology
        # amendment cannot reach them through snapshot invalidation: only the
        # documented flag premise reopens the held option.
        imaging_snap = self.store.create_snapshot(
            'CASE-ALPHA', self.q, 'A human-authored synthetic imaging draft.',
            [self.img['source_id']])
        held = self._option(snapshot=imaging_snap)
        self.store.add_option_flag(
            'CASE-ALPHA', held, 'objection', 'Fictional wording concern',
            'Hold while the fictional pathology wording is under amendment.',
            'Synthetic recorder', source_version_id=self.path['source_id'])
        control = self._option(snapshot=imaging_snap, label='Fictional discussion item B')
        result = self.store.import_report('CASE-ALPHA', report('alpha-pathology-amended.txt'))
        self.assertIn(held, result['invalidated_options'])
        self.assertNotIn(control, result['invalidated_options'])
        self.assertEqual(self._entry(held)['review_state'], 'needs_review')
        self.assertEqual(self._entry(control)['review_state'], 'current')
        # The premise citation is preserved with its superseded state.
        premise = self._entry(held)['objections']['open'][0]['premise']
        self.assertIn('PATH-ALPHA@1', premise)
        self.assertIn('superseded', premise)

    def test_deferred_and_reserved_stay_preserved_and_distinguishable(self):
        deferred = self._option(label='Fictional deferred item')
        reserved = self._option(label='Fictional reserved item')
        rejected = self._option(label='Fictional rejected item')
        self.store.add_option_flag(
            'CASE-ALPHA', deferred, 'deferred', 'Fictional timing pause',
            'Set aside for now; a fictional timing question is still open.',
            'Synthetic recorder')
        self.store.add_option_flag(
            'CASE-ALPHA', reserved, 'reserved', 'Fictional backup item',
            'Kept in reserve while the fictional discussion continues.',
            'Synthetic recorder')
        self.store.review_option('CASE-ALPHA', rejected, 'Synthetic reviewer', 'reject',
                                 'Rejected for fictional test purposes.')
        portfolio = self.store.option_portfolio('CASE-ALPHA')
        by_id = {entry['id']: entry for entry in portfolio['options']}
        self.assertEqual(by_id[deferred]['portfolio_status'], 'deferred')
        self.assertEqual(by_id[reserved]['portfolio_status'], 'reserved')
        self.assertEqual(by_id[rejected]['portfolio_status'], 'rejected')
        self.assertEqual(portfolio['counts'].get('deferred'), 1)
        self.assertEqual(portfolio['counts'].get('reserved'), 1)
        self.assertEqual(portfolio['counts'].get('rejected'), 1)
        # Readiness keeps the hold reason visible instead of dropping the entry.
        self.assertTrue(any('Marked deferred' in item for item in by_id[deferred]['readiness']))
        self.assertTrue(any('Marked reserved' in item for item in by_id[reserved]['readiness']))
        # A second open hold is refused; the first must be resolved explicitly.
        with self.assertRaisesRegex(InvalidInput, 'Resolve the open deferral'):
            self.store.add_option_flag(
                'CASE-ALPHA', deferred, 'reserved', 'Fictional second hold',
                'Another fictional reason while the first hold is still open.',
                'Synthetic recorder')
        # Resolving the hold reopens review; the past hold stays in history.
        hold_id = by_id[deferred]['holds'][0]['id']
        self.store.resolve_option_flag('CASE-ALPHA', hold_id, 'Synthetic reviewer', 'resolve',
                                       'The fictional timing question was answered.')
        entry = self._entry(deferred)
        self.assertEqual(entry['review_state'], 'needs_review')
        self.assertEqual(entry['holds'], [])
        self.assertEqual(len(entry['past_holds']), 1)

    def test_open_flag_blocks_approval_and_prerequisite_use(self):
        held = self._option(label='Fictional held prerequisite')
        follower = self._option(label='Fictional follower item')
        self.store.add_option_flag(
            'CASE-ALPHA', held, 'deferred', 'Fictional pause',
            'Set aside for now; a fictional question is still open.',
            'Synthetic recorder')
        with self.assertRaisesRegex(InvalidInput, 'cannot be approved'):
            self.store.review_option('CASE-ALPHA', held, 'Synthetic reviewer', 'approve',
                                     'Discussion-only review scope for this item.')
        with self.assertRaisesRegex(InvalidInput, 'not current or is held'):
            self.store.add_option_dependency('CASE-ALPHA', follower, 'option',
                                             depends_on_option_id=held)
        deadline = self._entry(held)['lead_time']
        self.assertIsNone(deadline['date'])
        self.assertIn('open objection, deferral, or reservation', deadline['label'])

    def test_dimension_notes_stay_pending_until_acknowledged_with_sources_cited(self):
        option = self._option()
        ev = self.store.import_synthetic_evidence(report('demo-evidence.txt'))
        assessment = self.store.assess_synthetic_evidence(
            'CASE-ALPHA', self.q, ev['evidence_version_id'], 'context', 'limited',
            'A human-authored rationale for this fictional note.')
        notes = {}
        for dimension, premise in (
                ('scientific_plausibility', {'source_version_id': self.path['source_id']}),
                ('technical_feasibility', {'evidence_assessment_id': assessment}),
                ('access', {}),
                ('clinical_authorization', {})):
            # Neutral wording: dimension names stay in the record key, never
            # as author-controlled claims inside the guarded note text.
            notes[dimension] = self.store.add_option_dimension_note(
                'CASE-ALPHA', option, dimension,
                'A fictional recorded note on this dimension; still uncertain.',
                'An authored anchor naming the fictional source for this test.',
                'Synthetic recorder', **premise)
        entry = self._entry(option)
        self.assertEqual({entry['dimensions'][d]['state'] for d in notes}, {'pending'})
        self.assertIn('PATH-ALPHA@1', entry['dimensions']['scientific_plausibility']['notes'][0]['premise'])
        self.assertIn('EVID-ASSAY@1', entry['dimensions']['technical_feasibility']['notes'][0]['premise'])
        self.assertTrue(any('No acknowledged note on access' in item
                            for item in entry['readiness']))
        self.store.acknowledge_option_dimension_note(
            'CASE-ALPHA', notes['access'], 'Synthetic reviewer',
            'Seen in this fictional demo; not a grant of anything.')
        entry = self._entry(option)
        self.assertEqual(entry['dimensions']['access']['state'], 'acknowledged')
        self.assertEqual(entry['dimensions']['scientific_plausibility']['state'], 'pending')
        with self.assertRaisesRegex(InvalidInput, 'already acknowledged'):
            self.store.acknowledge_option_dimension_note(
                'CASE-ALPHA', notes['access'], 'Synthetic reviewer',
                'A repeated acknowledgment must not be recorded twice.')

    def test_portfolio_states_no_eligibility_benefit_or_authorization(self):
        option = self._option()
        with self.assertRaisesRegex(InvalidInput, 'eligib'):
            self.store.add_option_flag(
                'CASE-ALPHA', option, 'objection', 'Bad label',
                'This fictional subject is eligible for this item.', 'Synthetic recorder')
        with self.assertRaisesRegex(InvalidInput, 'must not declare'):
            self.store.add_option_dimension_note(
                'CASE-ALPHA', option, 'clinical_authorization',
                'This fictional item is authorized for use here.',
                'An authored anchor for this test note.', 'Synthetic recorder')
        with self.assertRaisesRegex(InvalidInput, 'must not declare'):
            self.store.add_option_dimension_note(
                'CASE-ALPHA', option, 'access',
                'A fictional access note with uncertain wording.',
                'This anchor claims a benefit that is not recorded.', 'Synthetic recorder')
        portfolio = self.store.option_portfolio('CASE-ALPHA')
        self.assertIn('states no eligibility, benefit, safety, next step, or authorization',
                      portfolio['disclaimer'])
        for entry in portfolio['options']:
            self.assertIn(entry['portfolio_status'], PORTFOLIO_STATUSES)
            for item in entry['readiness']:
                lowered = item.lower()
                self.assertNotIn('you are eligible', lowered)
                self.assertNotIn('is authorized', lowered)
                self.assertNotIn('will benefit', lowered)

    def test_cross_case_terminal_and_premise_refusals(self):
        option = self._option()
        beta_option = self._option(case='CASE-BETA')
        with self.assertRaisesRegex(InvalidInput, 'not in this case'):
            self.store.add_option_flag(
                'CASE-BETA', option, 'objection', 'Fictional cross-case flag',
                'A flag recorded against the wrong case must fail.', 'Synthetic recorder')
        with self.assertRaisesRegex(InvalidInput, 'not in this case'):
            self.store.add_option_flag(
                'CASE-ALPHA', option, 'objection', 'Fictional wrong-premise flag',
                'A premise from another case must fail.', 'Synthetic recorder',
                source_version_id=self.beta['source_id'])
        with self.assertRaisesRegex(InvalidInput, 'at most one'):
            self.store.add_option_flag(
                'CASE-ALPHA', option, 'objection', 'Fictional double premise',
                'Two premises on one flag must fail.', 'Synthetic recorder',
                source_version_id=self.path['source_id'],
                evidence_assessment_id=999)
        with self.assertRaisesRegex(InvalidInput, 'Invalid option dimension'):
            self.store.add_option_dimension_note(
                'CASE-ALPHA', option, 'triage', 'A fictional note with a bad dimension.',
                'An authored anchor for this test note.', 'Synthetic recorder')
        self.store.review_option('CASE-ALPHA', option, 'Synthetic reviewer', 'reject',
                                 'Rejected for fictional test purposes.')
        with self.assertRaisesRegex(InvalidInput, 'Preserve the terminal option'):
            self.store.add_option_flag(
                'CASE-ALPHA', option, 'objection', 'Fictional late flag',
                'New reasons belong on a new proposal, not history.', 'Synthetic recorder')
        with self.assertRaisesRegex(InvalidInput, 'Preserve the terminal option'):
            self.store.add_option_dimension_note(
                'CASE-ALPHA', option, 'access', 'A fictional note on a rejected option.',
                'An authored anchor for this test note.', 'Synthetic recorder')
        with self.assertRaisesRegex(InvalidInput, 'not in this case'):
            self.store.resolve_option_flag(
                'CASE-BETA', 999, 'Synthetic reviewer', 'resolve',
                'Resolving a missing flag must fail.')
        self.assertEqual(self._entry(beta_option, case='CASE-BETA')['portfolio_status'], 'proposed')

    def test_portfolio_is_embedded_in_case_state(self):
        option = self._option()
        state = self.store.state('CASE-ALPHA')
        self.assertIn('portfolio', state)
        self.assertEqual(state['portfolio']['case_id'], 'CASE-ALPHA')
        self.assertIn(option, [entry['id'] for entry in state['portfolio']['options']])


class PortfolioHttpTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        cls.path = str(Path(cls.tmp.name) / 'portfolio-server.sqlite')
        seed(cls.path)
        bound_handler = type('BoundHandlerForPortfolioTest', (Handler,), {'db_path': cls.path})
        cls.server = ThreadingHTTPServer(('127.0.0.1', 0), bound_handler)
        cls.port = cls.server.server_address[1]
        cls.thread = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.thread.start()
        cls._cookie = signin_demo(cls.port, cls.path)

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.server.server_close()
        cls.thread.join(timeout=5)
        cls.tmp.cleanup()

    def request(self, path, data=None):
        headers = {"Cookie": self._cookie}
        if data is not None:
            headers['Content-Type'] = 'application/json'
        request = Request(f'http://127.0.0.1:{self.port}{path}',
                          data=None if data is None else json.dumps(data).encode(),
                          headers=headers)
        try:
            with urlopen(request, timeout=5) as response:
                content = response.read()
                return response.status, json.loads(content)
        except HTTPError as err:
            return err.code, json.loads(err.read())

    def test_portfolio_routes(self):
        status, state = self.request('/api/cases/CASE-ALPHA/state')
        self.assertEqual(status, 200)
        source_id = state['sources'][0]['id']
        status, created = self.request('/api/cases/CASE-ALPHA/questions', {
            'question': 'What options are discussed in this fictional case?'})
        self.assertEqual(status, 201)
        status, draft = self.request('/api/cases/CASE-ALPHA/snapshots', {
            'question_id': created['question_id'],
            'summary': 'A human-authored synthetic discussion draft.',
            'source_ids': [source_id]})
        self.assertEqual(status, 201)
        status, option = self.request('/api/cases/CASE-ALPHA/options', {
            'snapshot_id': draft['snapshot_id'], 'label': 'Fictional portfolio item',
            'description': 'A fictional item discussed for planning purposes only.',
            'epistemic_status': 'unknown'})
        self.assertEqual(status, 201)
        option_id = option['option_id']
        status, flag = self.request(f'/api/cases/CASE-ALPHA/options/{option_id}/flags', {
            'kind': 'deferred', 'label': 'Fictional HTTP pause',
            'reason': 'Set aside through the HTTP route for this test.',
            'author_label': 'Synthetic recorder'})
        self.assertEqual(status, 201)
        status, portfolio = self.request('/api/cases/CASE-ALPHA/portfolio')
        self.assertEqual(status, 200)
        entry = next(item for item in portfolio['options'] if item['id'] == option_id)
        self.assertEqual(entry['portfolio_status'], 'deferred')
        status, resolved = self.request(
            f'/api/cases/CASE-ALPHA/flags/{flag["flag_id"]}/resolve', {
                'reviewer_label': 'Synthetic reviewer', 'action': 'resolve',
                'scope': 'The fictional pause reason changed.'})
        self.assertEqual(status, 200)
        self.assertIn(option_id, resolved['invalidated_options'])
        status, note = self.request(
            f'/api/cases/CASE-ALPHA/options/{option_id}/dimension-notes', {
                'dimension': 'access',
                'note': 'A fictional access note recorded through HTTP; still uncertain.',
                'anchor': 'An authored HTTP anchor naming the fictional source.',
                'reviewer_label': 'Synthetic recorder'})
        self.assertEqual(status, 201)
        status, ack = self.request(
            f'/api/cases/CASE-ALPHA/dimension-notes/{note["dimension_note_id"]}/acknowledge', {
                'reviewer_label': 'Synthetic reviewer',
                'scope': 'Seen through HTTP in this fictional demo.'})
        self.assertEqual(status, 200)
        self.assertEqual(ack['result'], 'acknowledged')
        status, rejected = self.request(
            f'/api/cases/CASE-ALPHA/options/{option_id}/dimension-notes', {
                'dimension': 'access', 'note': 'This fictional subject is eligible.',
                'anchor': 'An authored anchor for this test note.',
                'reviewer_label': 'Synthetic recorder'})
        self.assertEqual(status, 422)
        self.assertIn('eligib', rejected['error'])


if __name__ == '__main__':
    unittest.main()
