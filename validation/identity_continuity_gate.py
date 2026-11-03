"""Strict acceptance gate for the PR #51/#53 + #69 review-only composition.

Run AFTER composing the pinned identity candidate, not on the unsupported main
baseline: PYTHONPATH=src python validation/identity_continuity_gate.py -v

All data, receipt declarations and actor labels are original fictional fixtures.
This gate fails on incorrect denial/side effects. Unlike the descriptive probe,
a successful observation alone is never a passing boundary check. These four
checks are not real-world identity, consent, security or clinical qualification.
"""
from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import threading
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'tests'))
import test_whole_patient_continuity as fixtures
from open_intelligence.patient_access import PatientAccessAdapter
from open_intelligence.store import CaseStore


class ComposedAccessBoundaryTests(unittest.TestCase):
    def setUp(self):
        directory = tempfile.TemporaryDirectory(prefix='oi-composed-fiction-')
        self.addCleanup(directory.cleanup)
        self.path = Path(directory.name) / 'case.sqlite'
        self.store = CaseStore(self.path)
        self.addCleanup(lambda: self.store.close())
        self.store.add_case(fixtures.A, 'Original fictional integration case A')
        self.store.add_case(fixtures.B, 'Original fictional integration case B')
        self.adapter = PatientAccessAdapter(self.store)

    def state(self):
        return self.store.state(fixtures.A)

    def test_revocation_blocks_new_process_without_clinical_side_effects(self):
        self.adapter.deliver(fixtures.envelope(), fixtures.PERSON)
        self.adapter.revoke(fixtures.A, 'RCPT-WHOLE-A',
                            'Fictional receipt revoked before child process starts.')
        before = self.state()
        child_code = '''
import json,sys
from open_intelligence.store import CaseStore
from open_intelligence.patient_access import PatientAccessAdapter
import test_whole_patient_continuity as f
s = CaseStore(sys.argv[1])
try:
    result = f.delivery_observation(PatientAccessAdapter(s), f.envelope(), f.EXPOSURE)
    print(json.dumps(result, sort_keys=True))
finally:
    s.close()
'''
        env = dict(os.environ, PYTHONPATH=os.pathsep.join((str(ROOT / 'src'), str(ROOT / 'tests'))))
        child = subprocess.run([sys.executable, '-c', child_code, str(self.path)],
                               env=env, cwd=ROOT, capture_output=True, text=True, timeout=15)
        self.assertEqual(child.returncode, 0, child.stderr)
        observed = json.loads(child.stdout)
        self.assertEqual(observed.get('result'), 'rejected', observed)
        self.assertEqual(observed.get('reason'), 'revoked_authorization', observed)
        after = self.state()
        for field in ('sources', 'assertions', 'snapshots', 'questions'):
            self.assertEqual(after[field], before[field], field)
        accepted = [e for e in after['events'] if e['kind'] == 'adapter_delivery_accepted']
        self.assertEqual(len(accepted), 1)

    def test_scope_denial_writes_no_facts_or_successful_identity_binding(self):
        restricted = fixtures.envelope(fixtures.receipt(('pathology',), 'SCOPE-ONLY'))
        restricted.source_subject_ref = 'SHOULD-NOT-BE-BOUND'
        before = self.state()
        observed = fixtures.delivery_observation(self.adapter, restricted, fixtures.EXPOSURE)
        self.assertEqual(observed.get('result'), 'rejected', observed)
        after = self.state()
        self.assertEqual(after['sources'], before['sources'])
        self.assertEqual(after['assertions'], before['assertions'])
        self.assertFalse(any(e['kind'] == 'adapter_delivery_accepted' for e in after['events']))
        # A denied delivery must not reserve its identity and block a later valid one.
        valid = self.adapter.deliver(fixtures.envelope(), fixtures.PERSON)
        self.assertEqual(valid['result'], 'imported')
        self.assertEqual(len(self.state()['sources']), 1)

    def test_simultaneous_qualified_subject_claim_has_one_winner(self):
        barrier = threading.Barrier(2, timeout=10)

        def deliver(case_id):
            store = CaseStore(self.path)
            try:
                envelope = fixtures.envelope()
                envelope.case_id = case_id
                raw = fixtures.report(case_id, 'RACE-' + case_id,
                    [('context', 'reported', 'Original fictional simultaneous-delivery control.')])
                barrier.wait()
                return case_id, PatientAccessAdapter(store).deliver(envelope, raw)
            finally:
                store.close()

        with ThreadPoolExecutor(max_workers=2) as pool:
            futures = [pool.submit(deliver, case) for case in (fixtures.A, fixtures.B)]
            outcomes = dict(f.result(timeout=20) for f in futures)
        self.assertCountEqual([o['result'] for o in outcomes.values()], ['imported', 'rejected'])
        rejected_case = next(c for c, o in outcomes.items() if o['result'] == 'rejected')
        self.assertEqual(outcomes[rejected_case]['reason'], 'identity_collision')
        self.assertEqual(self.store.state(rejected_case)['sources'], [])
        self.assertEqual(self.store.state(rejected_case)['assertions'], [])
        self.assertEqual(sum(len(self.store.state(c)['sources']) for c in outcomes), 1)
        self.assertEqual(sum(sum(e['kind'] == 'adapter_delivery_accepted'
                                 for e in self.store.state(c)['events']) for c in outcomes), 1)

    def test_failed_amendment_receipt_restores_review_sources_and_goal_context(self):
        ids = [self.adapter.deliver(fixtures.envelope(), raw)['source_id']
               for raw in (fixtures.PERSON, fixtures.PATHOLOGY)]
        question = self.store.add_question(fixtures.A, 'What do the fictional sources leave unresolved?')
        snapshot = self.store.create_snapshot(fixtures.A, question,
            'Original fictional review retains patient goals and unknown marker status.', ids)
        self.store.acknowledge_demo_review(fixtures.A, snapshot, 'Unverified fictional reviewer')
        before = self.state()
        original_event = self.store._event

        def fail_receipt(case, kind, **details):
            if kind == 'adapter_delivery_accepted':
                raise RuntimeError('Injected fictional receipt failure')
            return original_event(case, kind, **details)

        self.store._event = fail_receipt
        try:
            with self.assertRaisesRegex(RuntimeError, 'receipt failure'):
                self.adapter.deliver(fixtures.envelope(), fixtures.AMENDMENT)
        finally:
            self.store._event = original_event
        self.store.close()
        self.store = CaseStore(self.path)
        after = self.state()
        for field in ('sources', 'assertions', 'snapshots', 'questions', 'events'):
            self.assertEqual(after[field], before[field], field)
        self.assertIn(fixtures.PATHOLOGY.decode(), self.store.export_markdown(fixtures.A, snapshot))
        self.assertEqual(after['snapshots'][0]['state'], 'reviewed_in_demo')


if __name__ == '__main__':
    unittest.main()
