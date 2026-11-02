"""Whole-patient continuity research over the existing Open Intelligence ledger.

Plan: author original fictional whole-person inputs; reuse CaseStore,
PatientAccessAdapter, discovery and broker contracts; exercise initial review,
later amendment/new observation, rights withdrawal and restart. No app code,
model, external retrieval, clinical interpretation, new schema or UI is added.
Maps to OI-003/007/008/009/010/013 and the existing whole-patient research program.

Run integration assertions:
  PYTHONPATH=src python -m unittest discover -s tests -p test_whole_patient_continuity.py -v
Run descriptive boundary probes (NOT a readiness test):
  PYTHONPATH=src python tests/test_whole_patient_continuity.py --boundary-probe

The boundary probe exits zero when collection succeeds, even if a gap is
observed. Its explicit release_authorized=false must never be inferred from CI
color. No test demands that an unsafe observation stay unsafe forever.
"""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

from open_intelligence.patient_access import (
    AdapterEnvelope, AuthorizationReceipt, PatientAccessAdapter,
)
from open_intelligence.store import CaseStore, InvalidInput

A = 'CASE-WHOLE-A'
B = 'CASE-WHOLE-B'
BASELINE = '7626ec8bd91ea7451b042389cb6559339e9f332c'


def report(case, document, findings, *, event='2026-02-01', issued='2026-02-02',
           kind='clinical', specimen=None, amends=None):
    lines = ['OI-SYNTHETIC-REPORT/1', f'Patient: {case}', f'Document: {document}',
             f'Type: {kind}', f'Event-Date: {event}', f'Issued-At: {issued}']
    if specimen is not None:
        lines.append('Specimen: ' + specimen)
    if amends is not None:
        lines.append('Amends: ' + amends)
    lines.extend(f'Finding: {key}|{certainty}|{quote}' for key, certainty, quote in findings)
    return ('\n'.join(lines) + '\n').encode('utf-8')


PERSON = report(A, 'PERSON-CONTEXT', [
    ('symptom', 'reported', 'The fictional patient reports fatigue; no clinical grade is assigned.'),
    ('function', 'reported', 'Household assistance is reported; no function scale was administered.'),
    ('comorbidity', 'reported', 'A source mentions a kidney condition; its current severity is unknown.'),
    ('renal-value', 'not-reported', 'No numeric kidney-function result is supplied in this source.'),
    ('goal', 'reported', 'The fictional patient wants to remain available for family routines.'),
    ('caregiver', 'reported', 'A supporter offers transport; delegated record-access authority is unverified.'),
    ('access', 'reported', 'The patient reports travel and appointment-cost constraints.'),
])
EXPOSURE = report(A, 'EXPOSURE-CONTEXT', [
    ('treatment', 'reported', 'A fictional order was held; this source records no administration.'),
])
PATHOLOGY = report(A, 'PERSON-PATH', [
    ('marker-q', 'not-reported', 'Marker Q was not tested in the original fictional specimen.'),
], kind='pathology', specimen='SPEC-WHOLE-A')
AMENDMENT = report(A, 'PERSON-PATH', [
    ('marker-q', 'negative', 'The amended fictional report records a negative Marker Q assay.'),
], issued='2026-02-06', kind='pathology', specimen='SPEC-WHOLE-A', amends='PERSON-PATH@1')
LATER_PERSON = report(A, 'PERSON-FOLLOWUP', [
    ('symptom', 'reported', 'The fictional patient now reports difficulty completing household tasks.'),
    ('goal', 'reported', 'At this later discussion the patient prioritizes fewer journeys for appointments.'),
], event='2026-02-07', issued='2026-02-07')
OTHER = report(B, 'OTHER-CONTEXT', [
    ('goal', 'reported', 'A different fictional person states a different personal priority.'),
])
DISCOVERY = b'''OI-SYNTHETIC-DISCOVERY/1
Discovery: FICT-WHOLE-LIT
Kind: literature
Title: Original fictional care-coordination listing, not an actual publication
DOI: 10.5555/oi-whole-person-fiction
Issued-At: 2026-02-03
Rights: original-synthetic
Summary: A fictional metadata-only listing containing bibliographic labels, not a clinical assessment.
'''


def receipt(scope=('clinical', 'pathology'), receipt_id='RCPT-WHOLE-A'):
    return AuthorizationReceipt(receipt_id, 'individual-access', scope,
                                '2026-01-01', '2026-12-31')


def envelope(auth=None):
    return AdapterEnvelope('original-synthetic-adapter', 'FICT-ORG-A',
                           'fictional-text', A, 'FICT-SUBJECT-A',
                           auth or receipt(), '2026-02-10')


class WholePatientContinuityTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.db_path = Path(self.tmp.name) / 'whole-person.sqlite'
        self.store = CaseStore(self.db_path)
        self.addCleanup(lambda: self.store.close())
        self.store.add_case(A, 'Original fictional whole-person case A')
        self.store.add_case(B, 'Original fictional unrelated control B')
        self.adapter = PatientAccessAdapter(self.store)
        self.source_ids = [self.adapter.deliver(envelope(), raw)['source_id']
                           for raw in (PERSON, EXPOSURE, PATHOLOGY)]
        self.other_id = self.store.import_report(B, OTHER)['source_id']
        self.question = self.store.add_question(A, 'What does this source set support and leave unresolved?')
        self.other_question = self.store.add_question(B, 'What is the other fictional person asking?')
        permissions = {'metadata': {'store': 'allowed', 'display': 'allowed'},
                       'full_text': {'store': 'allowed', 'display': 'allowed'}}
        self.rights_id = self.store.register_rights_source(
            'WHOLE-FICTION', 'Original fictional archive', 'v1', '2026-02-03', permissions,
            attribution='AI-assisted authored fiction; no legal or clinical clearance')['rights_source_id']
        self.broker_id = self.store.create_broker_link(
            A, self.question, self.rights_id, 'context', 'unknown',
            'Original fictional evidence; applicability is not established.',
            citation_title='Fictional research context',
            excerpt='An original fictional excerpt; not evidence of patient benefit.')['broker_link_id']
        self.discovery_id = self.store.import_discovery(
            DISCOVERY, rights_source_id=self.rights_id)['discovery_id']
        self.discovery_link = self.store.link_discovery(
            A, self.question, self.discovery_id, 'unknown',
            'Fictional metadata is a lead, not support for a medical conclusion.', [self.broker_id])
        self.snapshot = self.store.create_snapshot(
            A, self.question,
            'Fictional review draft. Fatigue, daily function, comorbidity, goals and practical constraints '
            'remain source-attributed; there is no treatment recommendation.',
            self.source_ids, broker_link_ids=[self.broker_id])
        self.control = self.store.create_snapshot(
            B, self.other_question, 'Separate fictional-person review draft.', [self.other_id])
        self.store.acknowledge_demo_review(A, self.snapshot, 'Unverified demonstration reviewer')
        self.store.acknowledge_demo_review(B, self.control, 'Unverified demonstration reviewer')

    def restart(self):
        self.store.close()
        self.store = CaseStore(self.db_path)
        self.adapter = PatientAccessAdapter(self.store)

    def test_initial_record_preserves_whole_person_context_and_missingness(self):
        self.restart()
        state = self.store.state(A)
        keys = {a['finding_key']: a for a in state['assertions']}
        self.assertEqual(set(keys), {'symptom', 'function', 'comorbidity', 'renal-value',
                                    'goal', 'caregiver', 'access', 'treatment', 'marker-q'})
        self.assertEqual(keys['renal-value']['certainty'], 'not-reported')
        self.assertEqual(keys['marker-q']['certainty'], 'not-reported')
        self.assertIn('no administration', keys['treatment']['quote'])
        self.assertIn('authority is unverified', keys['caregiver']['quote'])
        for source_id, raw in zip(self.source_ids, (PERSON, EXPOSURE, PATHOLOGY)):
            saved = next(s for s in state['sources'] if s['id'] == source_id)
            self.assertEqual(saved['sha256'], hashlib.sha256(raw).hexdigest())
            self.assertEqual(self.store.source_text(A, source_id), raw.decode('utf-8'))
        text = self.store.export_markdown(A, self.snapshot)
        for raw in (PERSON, EXPOSURE, PATHOLOGY):
            self.assertIn(raw.decode('utf-8'), text)
        self.assertEqual(state['snapshots'][0]['state'], 'reviewed_in_demo')

    def test_later_update_stales_only_dependent_review_and_retains_prior_goals(self):
        self.assertEqual(self.adapter.deliver(envelope(), AMENDMENT)['version'], 2)
        newer = self.adapter.deliver(envelope(), LATER_PERSON)['source_id']
        self.restart()
        state = self.store.state(A)
        self.assertEqual(next(s for s in state['snapshots'] if s['id'] == self.snapshot)['state'], 'stale')
        self.assertEqual(next(q for q in state['questions'] if q['id'] == self.question)['state'], 'open')
        self.assertEqual(self.store.state(B)['snapshots'][0]['state'], 'reviewed_in_demo')
        goals = [a['quote'] for a in state['assertions'] if a['finding_key'] == 'goal']
        self.assertEqual(len(goals), 2)
        self.assertTrue(any('family routines' in q for q in goals))
        self.assertTrue(any('fewer journeys' in q for q in goals))
        history = self.store.export_markdown(A, self.snapshot)
        self.assertIn(PATHOLOGY.decode(), history)
        self.assertNotIn(LATER_PERSON.decode(), history)
        self.assertNotIn(AMENDMENT.decode(), history)
        self.assertIn('stale', history)
        current_ids = [s['id'] for s in state['sources'] if s['state'] == 'current']
        self.assertIn(newer, current_ids)
        replacement = self.store.create_snapshot(
            A, self.question, 'Replacement fictional draft requires fresh review; old priorities remain historical.',
            current_ids, broker_link_ids=[self.broker_id])
        self.assertEqual(next(s for s in self.store.state(A)['snapshots'] if s['id'] == replacement)['state'], 'draft')

    def test_rights_withdrawal_reaches_discovery_review_and_persists(self):
        result = self.store.revoke_rights_source(self.rights_id, 'Fictional archive withdraws the declared permissions.')
        self.assertIn(self.snapshot, result['invalidated_snapshots'])
        self.assertIn(self.discovery_link, result['invalidated_discovery_links'])
        self.restart()
        state = self.store.state(A)
        link = next(b for b in state['broker_links'] if b['id'] == self.broker_id)
        self.assertTrue(link['content_redacted'])
        self.assertIsNone(link['excerpt'])
        self.assertIsNone(link['citation_title'])
        self.assertEqual(self.store.case_discovery_links(A)[0]['state'], 'invalid')
        self.assertEqual(state['snapshots'][0]['state'], 'stale')
        self.assertEqual(self.store.state(B)['snapshots'][0]['state'], 'reviewed_in_demo')
        self.assertEqual(self.store.source_text(A, self.source_ids[0]), PERSON.decode())
        with self.assertRaises(InvalidInput):
            self.store.create_snapshot(A, self.question, 'Cannot reuse withdrawn rights in a new draft.',
                                       self.source_ids, broker_link_ids=[self.broker_id])

    def test_wrong_person_and_duplicate_arrivals_do_not_change_case_facts(self):
        before = self.store.state(A)
        wrong = self.store.import_report(A, OTHER)
        self.assertEqual(wrong['result'], 'quarantined')
        duplicate = self.adapter.deliver(envelope(), PERSON)
        self.assertEqual(duplicate['result'], 'duplicate')
        after = self.store.state(A)
        self.assertEqual(before['assertions'], after['assertions'])
        self.assertEqual(len(before['sources']), len(after['sources']))
        self.assertEqual(len(self.store.state(B)['sources']), 1)


def delivery_observation(adapter, access_envelope, raw):
    """A fixed adapter may reject by typed exception; record, do not mask it."""
    try:
        return adapter.deliver(access_envelope, raw)
    except InvalidInput as error:
        return {'result': 'rejected', 'reason': str(error),
                'exception_type': 'InvalidInput'}


def boundary_probe():
    """Collect actual adapter outcomes separately from asserted workflow behavior.

    Deliberately checks scope mismatch and replacement of the adapter instance.
    No assertion requires an unsafe result. Consumers must read each observation,
    never interpret successful collection or green CI as authorization readiness.
    """
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / 'probe.sqlite'
        store = CaseStore(path)
        store.add_case(A, 'Fictional permission boundary probe')
        adapter = PatientAccessAdapter(store)
        initial = adapter.deliver(envelope(), PERSON)
        adapter.revoke(A, 'RCPT-WHOLE-A', 'Fictional access receipt revoked for the probe.')
        same_instance = delivery_observation(adapter, envelope(), EXPOSURE)
        store.close()
        store = CaseStore(path)
        try:
            after_restart = delivery_observation(PatientAccessAdapter(store), envelope(), EXPOSURE)
            different_scope = receipt(('pathology',), 'RCPT-SCOPE-PROBE')
            clinical = report(A, 'SCOPE-MISMATCH', [('context', 'reported', 'Original fictional clinical report, not pathology.')])
            scope_result = delivery_observation(PatientAccessAdapter(store), envelope(different_scope), clinical)
            observations = {
                'initial_delivery': initial['result'],
                'revoked_receipt_same_instance': same_instance,
                'revoked_receipt_after_restart': after_restart,
                'pathology_only_scope_with_clinical_report': scope_result,
            }
            gaps = []
            if after_restart.get('result') == 'imported':
                gaps.append('adapter_revocation_not_enforced_after_restart')
            if scope_result.get('result') == 'imported':
                gaps.append('declared_scope_not_checked_against_report_kind')
            return {
                'schema': 'oi-whole-patient-boundary-observation/1',
                'inspected_baseline': BASELINE,
                # A composed index tree is not the PR merge commit that triggered CI.
                'tested_commit': (None if os.environ.get('OI_COMPOSED_TREE')
                                  else os.environ.get('GITHUB_SHA', 'local-unrecorded')),
                'tested_tree': os.environ.get('OI_COMPOSED_TREE'),
                'workflow_trigger_commit': os.environ.get('GITHUB_SHA'),
                'data': 'original-ai-assisted-fiction-only',
                'collection_completed': True,
                'observations': observations,
                'observed_gaps': gaps,
                'release_authorized': False,
                'clinical_validation_performed': False,
                'caregiver_access_implemented': False,
                'notes': 'Descriptive receipt, not identity verification. Only this synthetic adapter was probed; no whole-system authorization certification. No ML or network call.',
            }
        finally:
            store.close()


class BoundaryReceiptProvenanceTests(unittest.TestCase):
    def test_composed_source_is_a_tree_not_the_workflow_trigger_commit(self):
        with patch.dict(os.environ, {'GITHUB_SHA': 'a' * 40,
                                    'OI_COMPOSED_TREE': 'b' * 40}, clear=True):
            observed = boundary_probe()
        self.assertIsNone(observed['tested_commit'])
        self.assertEqual(observed['tested_tree'], 'b' * 40)
        self.assertEqual(observed['workflow_trigger_commit'], 'a' * 40)
        self.assertFalse(observed['release_authorized'])

    def test_ordinary_checkout_keeps_commit_identity_and_no_composed_tree(self):
        with patch.dict(os.environ, {'GITHUB_SHA': 'a' * 40}, clear=True):
            observed = boundary_probe()
        self.assertEqual(observed['tested_commit'], 'a' * 40)
        self.assertIsNone(observed['tested_tree'])
        self.assertEqual(observed['workflow_trigger_commit'], 'a' * 40)
        self.assertFalse(observed['release_authorized'])


if __name__ == '__main__':
    if sys.argv[1:] == ['--boundary-probe']:
        print(json.dumps(boundary_probe(), indent=2, sort_keys=True))
    else:
        unittest.main()
