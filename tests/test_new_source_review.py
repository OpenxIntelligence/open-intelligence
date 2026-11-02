"""Original fictional tests for explicit new-source review; not clinical validation."""
import importlib
import json
import sqlite3
import tempfile
import threading
import unittest
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from unittest.mock import patch

from open_intelligence import CaseStore, InvalidInput
from open_intelligence.changes import changes_since_review

A, B = 'CASE-ALPHA', 'CASE-BETA'
SAME_TIME = '2026-06-02T12:00:00+00:00'


def report(case=A, doc='PLAN-OLD', event='2026-06-01', quote='A fictional procedure is planned for June 10.', amends=None):
    extra = f'Amends: {amends}\n' if amends else ''
    return (f'OI-SYNTHETIC-REPORT/1\nPatient: {case}\nDocument: {doc}\nType: clinical\n'
            f'Event-Date: {event}\nIssued-At: 2026-06-02\nSpecimen: SAMPLE-A\n{extra}'
            f'Finding: plan|reported|{quote}\n').encode()


class NewSourceReviewTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.path = Path(self.tmp.name) / 'case.sqlite'
        self.store = CaseStore(self.path)
        self.addCleanup(self.tmp.cleanup)
        self.addCleanup(lambda: self.store.close())
        self.clock = patch('open_intelligence.store.now_utc', return_value=SAME_TIME)
        self.clock.start(); self.addCleanup(self.clock.stop)
        self.store.add_case(A, 'Fictional Alpha'); self.store.add_case(B, 'Fictional Beta')
        self.old = self.store.import_report(A, report())['source_id']
        self.q = self.store.add_question(A, 'What preparation questions remain open?')
        self.snap = self.store.create_snapshot(A, self.q, 'Original fictional discussion based on the earlier plan.', [self.old])
        self.store.acknowledge_demo_review(A, self.snap, 'Fictional reader')
        self.otherq = self.store.add_question(A, 'What does the unrelated fictional record say?')
        self.unrelated = self.store.create_snapshot(A, self.otherq, 'An unrelated fictional case question.', [self.old])
        self.store.acknowledge_demo_review(A, self.unrelated, 'Fictional reader')
        self.other_source = self.store.import_report(B, report(case=B, doc='B-PLAN'))['source_id']
        qb = self.store.add_question(B, 'What is known about the separate case?')
        self.other_snap = self.store.create_snapshot(B, qb, 'Unrelated case history.', [self.other_source])
        self.store.acknowledge_demo_review(B, self.other_snap, 'Fictional reader')
        self.new = self.store.import_report(A, report(doc='PLAN-NEW', event='2026-06-02',
            quote='The fictional procedure is rescheduled to June 17; not documented as performed.'))['source_id']
        try:
            self.module = importlib.import_module('open_intelligence.source_review')
        except ModuleNotFoundError:
            self.module = None

    def request(self, **overrides):
        self.assertIsNotNone(self.module, 'explicit new-source review command is missing')
        values = dict(case_id=A, snapshot_id=self.snap, source_version_id=self.new,
                      source_line=8, reviewer_label='Fictional coordinator',
                      rationale='The later schedule may change preparation questions; review is requested only.')
        values.update(overrides)
        return self.module.request_new_source_review(self.store, **values)

    def context(self, **overrides):
        self.assertIsNotNone(self.module, 'explicit new-source review context is missing')
        values = dict(case_id=A, snapshot_id=self.snap); values.update(overrides)
        return self.module.new_source_review_context(self.store, **values)

    def state(self, case=A):
        return self.store.state(case)

    def option(self, snapshot, label):
        return self.store.create_option(A, snapshot, label, 'Fictional preparation discussion without any clinical instruction.', 'unknown')

    def test_explicit_request_not_import_reopens_only_selected_snapshot(self):
        self.assertEqual(next(s['state'] for s in self.state()['snapshots'] if s['id']==self.snap), 'reviewed_in_demo')
        before_b = self.state(B)
        old_raw = self.store.source_text(A, self.old)
        result = self.request()
        self.assertEqual(result['result'], 'review_requested')
        self.assertEqual(result['invalidated_snapshots'], [self.snap])
        snapshots = {s['id']:s for s in self.state()['snapshots']}
        self.assertEqual(snapshots[self.snap]['state'], 'stale')
        self.assertEqual(snapshots[self.unrelated]['state'], 'reviewed_in_demo')
        self.assertEqual(snapshots[self.snap]['source_ids'], [self.old])
        self.assertEqual(snapshots[self.snap]['reviewer_label'], 'Fictional reader')
        self.assertEqual({q['id']:q['state'] for q in self.state()['questions']}, {self.q:'open', self.otherq:'addressed'})
        self.assertEqual(self.store.source_text(A, self.old), old_raw)
        self.assertEqual(self.state(B), before_b)
        self.assertEqual({s['state'] for s in self.state()['sources']}, {'current'})
        exported = self.store.export_markdown(A, self.snap)
        self.assertIn('**stale**', exported)
        self.assertIn('June 10', exported); self.assertNotIn('June 17', exported)
        with self.assertRaises(InvalidInput):
            self.store.acknowledge_demo_review(A, self.snap, 'Fictional reader')

    def test_event_retains_exact_line_hash_and_history_after_restart(self):
        result = self.request()
        self.store.close(); self.store = CaseStore(self.path)
        event = next(e for e in self.state()['events'] if e['id']==result['event_id'])
        details = event['details']
        if isinstance(details,str): details=json.loads(details)
        self.assertEqual(event['kind'], 'new_source_review_requested')
        self.assertEqual(details['source_line'],8)
        self.assertIn('June 17',details['source_quote'])
        source=next(s for s in self.state()['sources'] if s['id']==self.new)
        self.assertEqual(details['source_sha256'], source['sha256'])
        self.assertEqual(details['reviewer_label'],'Fictional coordinator')
        self.assertGreater(details['source_import_event_id'],details['snapshot_creation_event_id'])
        self.assertEqual(self.context()['requests'][0]['event_id'],result['event_id'])

    def test_options_invalidate_transitively_but_unrelated_stays_current(self):
        root=self.option(self.snap,'Fictional root')
        child=self.option(self.unrelated,'Fictional child')
        untouched=self.option(self.unrelated,'Fictional unrelated')
        self.store.add_option_dependency(A,child,'option',depends_on_option_id=root)
        result=self.request()
        self.assertEqual(set(result['invalidated_options']),{root,child})
        states={o['id']:o['review_state'] for o in self.store.option_view(A)['options']}
        self.assertEqual(states,{root:'needs_review',child:'needs_review',untouched:'current'})

    def test_identical_retry_has_same_receipt_and_no_new_events(self):
        first=self.request(); before=self.state()
        second=self.request()
        self.assertEqual(second['result'],'duplicate')
        self.assertEqual(second['event_id'],first['event_id'])
        self.assertEqual(self.state(),before)
        with self.assertRaises(InvalidInput):
            self.request(rationale='A materially changed justification cannot replace the earlier audit receipt.')
        self.assertEqual(self.state(),before)

    def test_recorded_retry_survives_superseded_trigger_and_preserves_old_quote(self):
        first=self.request()
        self.store.import_report(A, report(doc='PLAN-NEW',event='2026-06-02',
            quote='A fictional corrected schedule is still pending.',amends='PLAN-NEW@1'))
        before=self.state()
        self.assertEqual(self.request()['event_id'],first['event_id'])
        self.assertEqual(self.state(),before)
        self.assertIn('June 17',self.context()['requests'][0]['source_quote'])

    def test_two_writers_create_one_request(self):
        self.assertIsNotNone(self.module,'explicit new-source review command is missing')
        barrier=threading.Barrier(2)
        def run():
            store=CaseStore(self.path)
            try:
                barrier.wait(timeout=5)
                return self.module.request_new_source_review(store,A,self.snap,self.new,8,
                    'Fictional coordinator','The later schedule may change preparation questions; review is requested only.')
            finally: store.close()
        with ThreadPoolExecutor(max_workers=2) as pool:
            f1=pool.submit(run);f2=pool.submit(run)
            outcomes=[f1.result(timeout=10),f2.result(timeout=10)]
        self.assertEqual({o['result'] for o in outcomes},{'review_requested','duplicate'})
        self.assertEqual(len({o['event_id'] for o in outcomes}),1)

    def test_source_receipt_order_not_clinical_date_or_second_precision(self):
        late=self.store.import_report(A,report(doc='LATE-OLD',event='2026-05-01',quote='Older event, newly received fictional evidence.'))['source_id']
        result=self.request(source_version_id=late)
        self.assertEqual(result['result'],'review_requested')

    def test_context_is_read_only_and_unranked_later_sources_only(self):
        before=self.state()
        ctx=self.context()
        self.assertEqual(self.state(),before)
        self.assertTrue(ctx['synthetic']);self.assertFalse(ctx['clinical_relevance_assessed'])
        self.assertEqual([s['source_version_id'] for s in ctx['sources']], [self.new])
        self.assertEqual(ctx['sources'][0]['findings'][0]['source_line'],8)
        self.assertIn('June 17',ctx['sources'][0]['findings'][0]['quote'])

    def test_wrong_case_missing_and_invalid_inputs_are_atomic(self):
        invalids=[{'snapshot_id':self.other_snap},{'source_version_id':self.other_source},
                  {'case_id':B},{'snapshot_id':999999},{'source_version_id':999999},
                  {'snapshot_id':2**100},{'source_version_id':2**100},{'source_line':2**100},
                  {'snapshot_id':True},{'source_version_id':False},{'source_line':True},
                  {'source_line':0},{'source_line':4},{'source_line':999},
                  {'reviewer_label':' '},{'rationale':' '},{'rationale':'x'*801}]
        for values in invalids:
            with self.subTest(values=values):
                before={c:self.state(c) for c in (A,B)}
                with self.assertRaises(InvalidInput):self.request(**values)
                self.assertEqual(before,{c:self.state(c) for c in (A,B)})

    def test_existing_and_amended_sources_are_not_new_event_requests(self):
        with self.assertRaises(InvalidInput):self.request(source_version_id=self.old)
        correction=self.store.import_report(A,report(doc='PLAN-NEW',event='2026-06-02',
            quote='Fictional corrected schedule.',amends='PLAN-NEW@1'))['source_id']
        before=self.state()
        for sid in (self.new,correction):
            with self.subTest(sid=sid):
                with self.assertRaises(InvalidInput):self.request(source_version_id=sid,source_line=9 if sid==correction else 8)
        self.assertEqual(before,self.state())

    def test_already_stale_snapshot_does_not_accept_another_request(self):
        self.store.import_report(A,report(quote='Fictional correction to earlier event.',amends='PLAN-OLD@1'))
        before=self.state()
        with self.assertRaises(InvalidInput):self.request()
        self.assertEqual(before,self.state())

    def test_failure_writing_audit_rolls_back_staleness_and_dependency_changes(self):
        self.assertIsNotNone(self.module,'explicit new-source review command is missing')
        self.option(self.snap,'Fictional option')
        before=self.state()
        with patch.object(self.store,'_event',side_effect=sqlite3.OperationalError('audit write rejected')):
            with self.assertRaises(sqlite3.OperationalError):self.request()
        self.assertEqual(before,self.state())

    def test_changes_projection_names_new_source_review_not_an_amendment(self):
        self.request()
        view=changes_since_review(self.store,A)
        self.assertEqual(view['counts']['amendments'],0)
        affected=next(x for x in view['stale_investigations'] if x['snapshot_id']==self.snap)
        cause=affected['causes'][0]
        self.assertEqual(cause['cause'],'new_source_review_request')
        self.assertEqual(cause['source_version_id'],self.new)
        self.assertEqual(cause['source_line'],8)

    def test_context_rejects_cross_case_and_bad_snapshot_id(self):
        for values in ({'case_id':B},{'snapshot_id':2**100},{'snapshot_id':True},{'snapshot_id':0},{'snapshot_id':99999}):
            with self.subTest(values=values):
                with self.assertRaises(InvalidInput):self.context(**values)


if __name__=='__main__':unittest.main()
