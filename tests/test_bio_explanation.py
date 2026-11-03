import json
import tempfile
import threading
import unittest
from http.server import ThreadingHTTPServer
from pathlib import Path
from urllib.error import HTTPError
from urllib.request import Request, urlopen

from open_intelligence import CaseStore, InvalidInput
from open_intelligence.__main__ import FICTIONAL_ACTOR_HEADER, Handler, seed

ROOT = Path(__file__).resolve().parents[1]
SAMPLE = ROOT / 'examples' / 'synthetic'


def report(name):
    return (SAMPLE / name).read_bytes()


def second_specimen_report():
    """A distinct new-specimen document: new Document, Specimen, and Event-Date."""
    return (report('alpha-pathology-original.txt')
            .replace(b'Document: PATH-ALPHA', b'Document: PATH-ALPHA-2')
            .replace(b'Specimen: BIOPSY-ALPHA', b'Specimen: BIOPSY-ALPHA-2')
            .replace(b'Event-Date: 2026-05-03', b'Event-Date: 2026-06-20')
            .replace(b'Issued-At: 2026-05-05', b'Issued-At: 2026-06-22'))


class BioExplanationTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.store = CaseStore(Path(self.tmp.name) / 'test.sqlite')
        self.store.add_case('CASE-ALPHA', 'Fictional Alpha')
        self.store.add_case('CASE-BETA', 'Fictional Beta')
        self.path = self.store.import_report('CASE-ALPHA', report('alpha-pathology-original.txt'))
        self.img = self.store.import_report('CASE-ALPHA', report('alpha-imaging.txt'))
        self.beta = self.store.import_report('CASE-BETA', report('beta-pathology.txt'))
        self.q1 = self.store.add_question(
            'CASE-ALPHA', 'Fictional question: what links the observed cells across samples?')

    def tearDown(self):
        self.store.close()
        self.tmp.cleanup()

    def explain(self, **kwargs):
        params = dict(
            question_id=self.q1, label='Fictional mechanism A',
            mechanism_text=('Fictional outline of how the observed cells might relate; '
                            'no interpretation recorded.'),
            episode_id='EPISODE-A', source_version_id=self.path['source_id'])
        params.update(kwargs)
        return self.store.add_bio_explanation('CASE-ALPHA', **params)

    def block(self, asset_id='BLOCK-A', episode='EPISODE-A', specimen='BIOPSY-ALPHA'):
        return self.store.add_biological_asset(
            'CASE-ALPHA', asset_id, 'ffpe_block', episode, '2026-05-03',
            self.path['source_id'], specimen_state='recorded', specimen_id=specimen)

    def observe(self, explanation, **kwargs):
        params = dict(
            method_label='Fictional Assay Panel FAP-7',
            result_note='Fictional signal pattern noted; no interpretation recorded.',
            source_version_id=self.path['source_id'],
            reference_kind='patient_normal')
        params.update(kwargs)
        return self.store.record_bio_assay_observation('CASE-ALPHA', explanation, **params)

    def test_competing_hypotheses_survive_side_by_side(self):
        first = self.explain()
        before = [dict(r) for r in self.store.state('CASE-ALPHA')['bio_explanations']]
        second = self.explain(
            label='Fictional mechanism B',
            mechanism_text='Fictional alternative outline; both stay visible until reviewed.')
        rows = self.store.state('CASE-ALPHA')['bio_explanations']
        self.assertEqual([r['id'] for r in rows], [first, second])
        self.assertEqual([r['question_id'] for r in rows], [self.q1, self.q1])
        self.assertEqual([r['state'] for r in rows], ['current', 'current'])
        # Creating the second explanation did not alter the first.
        self.assertEqual([dict(r) for r in rows if r['id'] == first], before)

    def test_new_specimen_is_never_confused_with_amendment(self):
        exp = self.explain(specimen_state='recorded', specimen_id='BIOPSY-ALPHA')
        outcome = self.store.import_report('CASE-ALPHA', second_specimen_report())
        self.assertEqual(outcome['result'], 'imported')
        self.assertEqual(outcome['version'], 1)
        self.assertEqual(outcome['invalidated_bio_explanations'], [])
        self.assertEqual(outcome['invalidated_bio_assay_observations'], [])
        self.assertEqual(outcome['invalidated_snapshots'], [])
        state = self.store.state('CASE-ALPHA')
        original = [s for s in state['sources'] if s['document_id'] == 'PATH-ALPHA']
        self.assertEqual([(s['version'], s['state']) for s in original], [(1, 'current')])
        added = [s for s in state['sources'] if s['document_id'] == 'PATH-ALPHA-2']
        self.assertEqual([(s['version'], s['state']) for s in added], [(1, 'current')])
        rows = {r['id']: r for r in state['bio_explanations']}
        self.assertEqual(rows[exp]['state'], 'current')
        # The new specimen anchors its own explanation; contexts stay distinct.
        other = self.explain(label='Fictional mechanism C',
                             source_version_id=added[0]['id'],
                             specimen_state='recorded', specimen_id='BIOPSY-ALPHA-2')
        rows = {r['id']: r for r in self.store.state('CASE-ALPHA')['bio_explanations']}
        self.assertEqual(rows[other]['specimen_id'], 'BIOPSY-ALPHA-2')
        self.assertEqual(rows[exp]['specimen_id'], 'BIOPSY-ALPHA')

    def test_assays_from_different_blocks_are_never_silently_pooled(self):
        exp = self.explain()
        block_a = self.block('BLOCK-A')
        block_b = self.block('BLOCK-B')
        obs_a = self.observe(exp, tissue_block_state='recorded',
                             tissue_block_asset_id=block_a)
        obs_b = self.observe(exp, tissue_block_state='recorded',
                             tissue_block_asset_id=block_b)
        rows = {r['id']: r for r in self.store.state('CASE-ALPHA')['bio_assay_observations']}
        self.assertEqual(set(rows), {obs_a, obs_b})
        self.assertEqual(rows[obs_a]['tissue_block_asset_id'], block_a)
        self.assertEqual(rows[obs_b]['tissue_block_asset_id'], block_b)
        self.assertNotEqual(rows[obs_a]['tissue_block_asset_id'],
                            rows[obs_b]['tissue_block_asset_id'])
        for row in rows.values():
            self.assertEqual(row['tissue_block_state'], 'recorded')
            self.assertIsNotNone(row['tissue_block_asset_id'])
        # Unknown block must not silently carry an asset, and vice versa.
        with self.assertRaisesRegex(InvalidInput, 'must not carry an asset ID'):
            self.observe(exp, tissue_block_asset_id=block_a)
        with self.assertRaisesRegex(InvalidInput, 'requires a biological asset ID'):
            self.observe(exp, tissue_block_state='recorded')

    def test_cross_episode_and_derivative_blocks_rejected(self):
        exp = self.explain()
        other_episode = self.block('BLOCK-OTHER', episode='EPISODE-B')
        with self.assertRaisesRegex(InvalidInput, 'never pooled across episodes'):
            self.observe(exp, tissue_block_state='recorded',
                         tissue_block_asset_id=other_episode)
        parent = self.block('BLOCK-PARENT')
        slide = self.store.add_biological_asset(
            'CASE-ALPHA', 'SLIDE-A', 'slide', 'EPISODE-A', '2026-05-10',
            self.path['source_id'], parent_asset_id=parent)
        with self.assertRaisesRegex(InvalidInput, 'physical tissue block'):
            self.observe(exp, tissue_block_state='recorded',
                         tissue_block_asset_id=slide)
        self.assertEqual(self.store.state('CASE-ALPHA')['bio_assay_observations'], [])

    def test_missing_matched_control_identified_as_missing(self):
        exp = self.explain()
        missing = self.observe(exp, matched_control_state='missing')
        recorded = self.observe(exp, matched_control_state='recorded',
                                matched_control_specimen='NORMAL-ALPHA')
        rows = {r['id']: r for r in self.store.state('CASE-ALPHA')['bio_assay_observations']}
        self.assertEqual(rows[missing]['matched_control_state'], 'missing')
        self.assertIsNone(rows[missing]['matched_control_specimen'])
        self.assertEqual(rows[recorded]['matched_control_state'], 'recorded')
        self.assertEqual(rows[recorded]['matched_control_specimen'], 'NORMAL-ALPHA')
        with self.assertRaisesRegex(InvalidInput, 'must not carry a specimen ID'):
            self.observe(exp, matched_control_state='missing',
                         matched_control_specimen='NORMAL-ALPHA')
        with self.assertRaisesRegex(InvalidInput, 'requires a specimen ID'):
            self.observe(exp, matched_control_state='recorded')

    def test_external_reference_distinguished_from_patient_normal(self):
        exp = self.explain()
        own = self.observe(exp, reference_kind='patient_normal')
        ext = self.observe(exp, reference_kind='external_population')
        rows = {r['id']: r for r in self.store.state('CASE-ALPHA')['bio_assay_observations']}
        self.assertEqual(rows[own]['reference_kind'], 'patient_normal')
        self.assertEqual(rows[ext]['reference_kind'], 'external_population')
        with self.assertRaisesRegex(InvalidInput, 'Reference kind must be'):
            self.observe(exp, reference_kind='cohort')
        with self.assertRaisesRegex(InvalidInput, 'Reference kind must be'):
            self.observe(exp, reference_kind=None)
        # reference_kind has no default: an explicit choice is required.
        with self.assertRaises(TypeError):
            self.store.record_bio_assay_observation(
                'CASE-ALPHA', exp, 'Fictional Assay Panel FAP-7',
                'Fictional signal pattern noted; no interpretation recorded.',
                self.path['source_id'])

    def test_amendment_stales_only_dependent_explanations(self):
        path_exp = self.explain()
        img_exp = self.explain(label='Fictional mechanism B',
                               source_version_id=self.img['source_id'])
        path_obs = self.observe(path_exp)
        img_obs = self.observe(img_exp, source_version_id=self.img['source_id'])
        update = self.store.import_report('CASE-ALPHA', report('alpha-pathology-amended.txt'))
        self.assertEqual(update['invalidated_bio_explanations'], [path_exp])
        self.assertEqual(update['invalidated_bio_assay_observations'], [path_obs])
        state = self.store.state('CASE-ALPHA')
        rows = {r['id']: r for r in state['bio_explanations']}
        self.assertEqual(rows[path_exp]['state'], 'stale')
        self.assertEqual(rows[img_exp]['state'], 'current')
        obs = {r['id']: r for r in state['bio_assay_observations']}
        self.assertEqual(obs[path_obs]['state'], 'stale')
        self.assertEqual(obs[img_obs]['state'], 'current')
        # The competing hypothesis on the same question survives the amendment.
        self.assertEqual(rows[img_exp]['question_id'], self.q1)
        # A stale anchor cannot start new work; history is preserved instead.
        with self.assertRaisesRegex(InvalidInput, 'superseded'):
            self.explain(source_version_id=self.path['source_id'])
        # A stale explanation cannot grow new observations; propose anew instead.
        with self.assertRaisesRegex(InvalidInput, 'stale'):
            self.observe(path_exp, source_version_id=update['source_id'])
        fresh = self.explain(label='Fictional mechanism D',
                             source_version_id=update['source_id'])
        new_obs = self.observe(fresh, source_version_id=update['source_id'])
        rows = {r['id']: r for r in self.store.state('CASE-ALPHA')['bio_explanations']}
        obs = {r['id']: r for r in self.store.state('CASE-ALPHA')['bio_assay_observations']}
        self.assertEqual(rows[fresh]['state'], 'current')
        self.assertEqual(obs[new_obs]['state'], 'current')

    def test_specimen_confusion_rejected(self):
        with self.assertRaisesRegex(InvalidInput, 'never an amendment'):
            self.explain(specimen_state='recorded', specimen_id='BIOPSY-OTHER')
        with self.assertRaisesRegex(InvalidInput, 'must not carry a specimen ID'):
            self.explain(specimen_id='BIOPSY-ALPHA')
        with self.assertRaisesRegex(InvalidInput, 'requires a specimen ID'):
            self.explain(specimen_state='recorded')
        exp = self.explain(specimen_state='recorded', specimen_id='BIOPSY-ALPHA')
        self.assertEqual(
            self.store.state('CASE-ALPHA')['bio_explanations'][0]['specimen_id'],
            'BIOPSY-ALPHA')
        other_block = self.block('BLOCK-OTHER-SPEC', specimen='BIOPSY-OTHER-SPEC')
        with self.assertRaisesRegex(InvalidInput, 'never an amendment'):
            self.observe(exp, tissue_block_state='recorded',
                         tissue_block_asset_id=other_block)
        # A source without a specimen records no contradiction to check.
        allowed = self.observe(exp, tissue_block_state='recorded',
                               tissue_block_asset_id=other_block,
                               source_version_id=self.img['source_id'])
        rows = {r['id']: r for r in self.store.state('CASE-ALPHA')['bio_assay_observations']}
        self.assertEqual(rows[allowed]['tissue_block_asset_id'], other_block)

    def test_lesion_and_clinical_context_states(self):
        with self.assertRaisesRegex(InvalidInput, 'requires a lesion ID'):
            self.explain(lesion_state='recorded')
        with self.assertRaisesRegex(InvalidInput, 'must not carry a lesion ID'):
            self.explain(lesion_id='LESION-A')
        with self.assertRaisesRegex(InvalidInput, 'requires a 1–120 character label'):
            self.explain(clinical_context_state='known', clinical_context_value='  ')
        with self.assertRaisesRegex(InvalidInput, 'must not carry a label'):
            self.explain(clinical_context_value='Fictional baseline time point T0')
        exp = self.explain(lesion_state='recorded', lesion_id='LESION-A',
                           clinical_context_state='known',
                           clinical_context_value='Fictional baseline time point T0')
        row = self.store.state('CASE-ALPHA')['bio_explanations'][0]
        self.assertEqual(row['id'], exp)
        self.assertEqual(row['lesion_id'], 'LESION-A')
        self.assertEqual(row['lesion_state'], 'recorded')
        self.assertEqual(row['clinical_context_value'], 'Fictional baseline time point T0')
        self.assertEqual(row['clinical_context_state'], 'known')

    def test_guarded_language_rejected(self):
        for field_kwargs in (
            {'label': 'Fictional stage II mechanism'},
            {'mechanism_text': 'Fictional outline with tumor grade noted.'},
            {'clinical_context_state': 'known',
             'clinical_context_value': 'Fictional post-treatment review'},
        ):
            with self.subTest(field_kwargs=field_kwargs):
                with self.assertRaisesRegex(InvalidInput, 'must not state'):
                    self.explain(**field_kwargs)
        exp = self.explain()
        with self.assertRaisesRegex(InvalidInput, 'must not state'):
            self.observe(exp, method_label='Fictional response assay')
        with self.assertRaisesRegex(InvalidInput, 'must not state'):
            self.observe(exp, result_note='Fictional signal shows disease progression noted.')
        with self.assertRaisesRegex(InvalidInput, '10–1000'):
            self.explain(mechanism_text='Too short')
        self.assertEqual(len(self.store.state('CASE-ALPHA')['bio_explanations']), 1)
        self.assertEqual(self.store.state('CASE-ALPHA')['bio_assay_observations'], [])

    def test_cross_case_isolation(self):
        exp = self.explain()
        beta_q = self.store.add_question(
            'CASE-BETA', 'Fictional beta question for isolation check?')
        with self.assertRaisesRegex(InvalidInput, 'not in this case'):
            self.store.add_bio_explanation(
                'CASE-BETA', self.q1, 'Fictional label',
                'Fictional mechanism text for isolation check.',
                'EPISODE-A', self.beta['source_id'])
        with self.assertRaisesRegex(InvalidInput, 'another case'):
            self.store.add_bio_explanation(
                'CASE-BETA', beta_q, 'Fictional label',
                'Fictional mechanism text for isolation check.',
                'EPISODE-A', self.path['source_id'])
        with self.assertRaisesRegex(InvalidInput, 'not in this case'):
            self.store.record_bio_assay_observation(
                'CASE-BETA', exp, 'Fictional Assay Panel FAP-7',
                'Fictional signal pattern noted; no interpretation recorded.',
                self.beta['source_id'], 'unknown')
        self.assertEqual(self.store.state('CASE-BETA')['bio_explanations'], [])
        self.assertEqual(self.store.state('CASE-BETA')['bio_assay_observations'], [])
        self.assertEqual(len(self.store.state('CASE-ALPHA')['bio_explanations']), 1)


class BioExplanationHttpTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        cls.path = str(Path(cls.tmp.name) / 'server.sqlite')
        seed(cls.path)
        bound_handler = type('BoundHandlerForBioTest', (Handler,), {'db_path': cls.path})
        cls.server = ThreadingHTTPServer(('127.0.0.1', 0), bound_handler)
        cls.port = cls.server.server_address[1]
        cls.thread = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.thread.start()

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.server.server_close()
        cls.thread.join(timeout=5)
        cls.tmp.cleanup()

    def request(self, path, data=None):
        values = {FICTIONAL_ACTOR_HEADER: 'FICTIONAL-NAVIGATOR-A'}
        if data is not None:
            values['Content-Type'] = 'application/json'
        request = Request(f'http://127.0.0.1:{self.port}{path}',
                          data=None if data is None else json.dumps(data).encode(),
                          headers=values)
        try:
            with urlopen(request, timeout=5) as response:
                return response.status, json.loads(response.read())
        except HTTPError as err:
            return err.code, json.loads(err.read())

    def test_bio_routes_create_and_list(self):
        status, data = self.request('/api/cases/CASE-ALPHA/state')
        self.assertEqual(status, 200)
        source_id = data['sources'][0]['id']
        status, created = self.request(
            '/api/cases/CASE-ALPHA/questions',
            {'question': 'Fictional bio context question for route check?'})
        self.assertEqual(status, 201)
        status, exp = self.request('/api/cases/CASE-ALPHA/bio-explanations', {
            'question_id': created['question_id'], 'label': 'Fictional route mechanism',
            'mechanism_text': 'Fictional mechanism text recorded through the route.',
            'episode_id': 'EPISODE-A', 'source_version_id': source_id})
        self.assertEqual(status, 201)
        eid = exp['bio_explanation_id']
        status, obs = self.request(
            f'/api/cases/CASE-ALPHA/bio-explanations/{eid}/assay-observations', {
                'method_label': 'Fictional Assay Panel FAP-7',
                'result_note': 'Fictional route signal noted; no interpretation recorded.',
                'source_version_id': source_id, 'reference_kind': 'external_population',
                'tissue_block_state': 'unknown', 'matched_control_state': 'missing'})
        self.assertEqual(status, 201)
        self.assertIsInstance(obs['bio_assay_observation_id'], int)
        status, data = self.request('/api/cases/CASE-ALPHA/state')
        self.assertEqual([r['id'] for r in data['bio_explanations']], [eid])
        self.assertEqual([r['reference_kind'] for r in data['bio_assay_observations']],
                         ['external_population'])
        self.assertEqual([r['matched_control_state'] for r in data['bio_assay_observations']],
                         ['missing'])

    def test_bio_routes_reject_guarded_and_cross_case_text(self):
        status, beta = self.request('/api/cases/CASE-BETA/state')
        self.assertEqual(status, 200)
        beta_source = beta['sources'][0]['id']
        status, created = self.request(
            '/api/cases/CASE-BETA/questions',
            {'question': 'Fictional beta route question for rejection check?'})
        self.assertEqual(status, 201)
        status, error = self.request('/api/cases/CASE-BETA/bio-explanations', {
            'question_id': created['question_id'], 'label': 'Fictional stage II label',
            'mechanism_text': 'Fictional mechanism text for rejection check.',
            'episode_id': 'EPISODE-A', 'source_version_id': beta_source})
        self.assertEqual(status, 422)
        self.assertIn('must not state', error['error'])
        status, alpha = self.request('/api/cases/CASE-ALPHA/state')
        alpha_source = alpha['sources'][0]['id']
        status, error = self.request('/api/cases/CASE-ALPHA/bio-explanations', {
            'question_id': created['question_id'], 'label': 'Fictional cross-case label',
            'mechanism_text': 'Fictional mechanism text for cross-case rejection check.',
            'episode_id': 'EPISODE-A', 'source_version_id': alpha_source})
        self.assertEqual(status, 422)
        self.assertIn('not in this case', error['error'])


class BioExplanationUiContractTests(unittest.TestCase):
    def test_case_view_links_and_labels_the_explanation_surface(self):
        html = (ROOT / 'web' / 'index.html').read_text()
        self.assertIn('href="#biological-explanation"', html)
        self.assertIn('id="biological-explanation"', html)
        self.assertIn('id="bio-explanation-list"', html)
        self.assertIn('id="bio-explanation-form"', html)
        self.assertIn('id="bio-assay-form"', html)
        for element_id in ('bio-question-choice', 'bio-label', 'bio-mechanism',
                           'bio-episode', 'bio-specimen-state', 'bio-specimen-id',
                           'bio-lesion-state', 'bio-lesion-id', 'bio-clinical-state',
                           'bio-clinical-value', 'bio-source-choice',
                           'bio-assay-explanation-choice', 'bio-method', 'bio-result-note',
                           'bio-assay-source-choice', 'bio-block-state', 'bio-block-choice',
                           'bio-control-state', 'bio-control-specimen', 'bio-reference-kind'):
            self.assertIn(f'id="{element_id}"', html)
        # Fictional, non-clinical framing is part of the surface contract.
        self.assertIn('FICTIONAL CONTEXT ONLY', html)
        self.assertIn('not a mutation list', html)
        self.assertIn('not clinical software', html)
        self.assertIn("Patient's own normal tissue", html)
        self.assertIn('External reference population (not this patient)', html)
        self.assertIn('Missing — identified as missing', html)

    def test_renderer_keeps_hypotheses_separate_and_text_safe(self):
        javascript = (ROOT / 'web' / 'app.js').read_text()
        self.assertIn('renderBioExplanations', javascript)
        self.assertIn('/bio-explanations', javascript)
        self.assertIn('/assay-observations', javascript)
        # Competing hypotheses render as separate cards, never merged.
        self.assertIn('competing hypotheses are never merged', javascript)
        # Assays group under per-block headings but keep separate cards.
        self.assertIn('assays from different blocks are never merged', javascript)
        self.assertIn('not pooled with any block', javascript)
        # Missing controls and reference kinds stay explicit in plain words.
        self.assertIn('Matched control MISSING', javascript)
        self.assertIn("patient's own normal tissue", javascript)
        self.assertIn('external reference population (not this patient)', javascript)
        # Unfinished narratives block case switches instead of crossing cases.
        self.assertIn('bio-mechanism', javascript)
        self.assertIn('bio-result-note', javascript)
        # Source and authored text must never become HTML.
        self.assertNotIn('innerHTML', javascript)


if __name__ == '__main__':
    unittest.main()
