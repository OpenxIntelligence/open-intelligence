"""Real PG16/HTTP acceptance for explicit amended-record reconciliation.

Independently authored fictional reports. No institutional communication or
clinical approval. The source owner, patient registry and event journal are real.
"""
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
import hashlib
import unittest
from unittest.mock import patch

from sqlalchemy import text
from starlette.responses import JSONResponse

from oi_api.app import create_app
from open_intelligence.postgres_registry import PostgresPatientRegistry
from http_support import running_server
from test_source_versions import SourceVersionFixture, ORIGINAL, AMENDED
from test_patients import TOKEN_A, TOKEN_B, request

THIRD = AMENDED.replace('Issued-At: 2026-01-12', 'Issued-At: 2026-01-13').replace(
    'Amends: DOC-ONE@1', 'Amends: DOC-ONE@2').replace(
    'Amended fictional marker is reported negative.', 'Second fictional correction remains source-reported.')


class RecordReconciliationTests(SourceVersionFixture):
    def setUp(self):
        super().setUp()
        self.creds[0]['actions'].extend((
            'record_request_create', 'record_request_read',
            'record_request_cancel', 'record_request_receive'))
        self.write()

    def root(self, pid):
        return f'/v1/patients/{pid}/record-requests'

    def prepared(self, base):
        pid = self.setup_case(base)
        status, body, _ = request(base, self.root(pid), token=TOKEN_A, body={
            'synthetic': True, 'request_key': 'REQ-RECON-ONE', 'kind': 'pathology',
            'record_label': 'Fictional pathology report', 'source_organization': 'Fictional laboratory'})
        self.assertEqual(status, 201)
        rid = body['request_id']
        sid = self.ingest(base, pid)[1]['source_id']
        self.assertEqual(request(base, self.root(pid) + f'/{rid}/receive', token=TOKEN_A,
            body={'synthetic': True, 'case_id': 'CASE-ALPHA', 'source_id': sid})[0], 201)
        aid = self.ingest(base, pid, AMENDED)[1]['source_id']
        return pid, rid, sid, aid

    def reconcile(self, base, pid, rid, old, new, key='RECON-ONE', **overrides):
        body = {'synthetic': True, 'case_id': 'CASE-ALPHA', 'expected_source_id': old,
                'replacement_source_id': new, 'request_key': key, 'reason_code': 'source_amendment'}
        body.update(overrides)
        return request(base, self.root(pid) + f'/{rid}/reconcile', token=TOKEN_A, body=body)

    def events(self, pid):
        with self.engine.connect() as c:
            return [(r[0], r[1]) for r in c.execute(text(
                "SELECT event_type,metadata_json FROM identity.identity_domain_events "
                "WHERE patient_id=:p AND event_type IN ('record.request.received','record.request.reconciled') "
                "ORDER BY id"), {'p': pid})]

    def test_explicit_reconciliation_retains_original_and_restart_replays_old_intent(self):
        with running_server(create_app(self.settings)) as base:
            pid, rid, sid, aid = self.prepared(base)
            before = request(base, self.root(pid), token=TOKEN_A)[1]['requests'][0]
            self.assertEqual(before['receipt_status'], 'source_superseded_reconciliation_required')
            self.assertEqual(before['source_reference']['source_id'], sid)
            status, receipt, headers = self.reconcile(base, pid, rid, sid, aid)
            self.assertEqual(status, 201)
            self.assertEqual(headers['Cache-Control'], 'no-store')
            self.assertEqual((receipt['previous_source_id'], receipt['source_id'], receipt['version']), (sid, aid, 2))
            self.assertFalse(receipt['clinical_approval'])
            self.assertFalse(receipt['external_request_sent'])
            self.assertFalse(receipt['duplicate'])
            first_id = receipt['reconciliation_id']
            after = request(base, self.root(pid), token=TOKEN_A)[1]['requests'][0]
            self.assertEqual((after['status'], after['revision'], after['receipt_status']),
                             ('received', 3, 'source_current_unreviewed'))
            self.assertEqual(after['source_reference']['source_id'], aid)
            self.assertGreaterEqual(datetime.fromisoformat(after['updated_at'].replace('Z','+00:00')),
                                    datetime.fromisoformat(before['updated_at'].replace('Z','+00:00')))
            # Existing receive never changes its original receipt on retry.
            old_retry = request(base, self.root(pid) + f'/{rid}/receive', token=TOKEN_A,
                body={'synthetic': True, 'case_id': 'CASE-ALPHA', 'source_id': sid})
            self.assertEqual((old_retry[0], old_retry[1]['source_id']), (200, sid))
            for source_id, original in ((sid, ORIGINAL), (aid, AMENDED)):
                saved = request(base, self.url(pid) + '/' + source_id, token=TOKEN_A)
                self.assertEqual(saved[1]['original_text'], original)
            history = request(base, self.root(pid) + f'/{rid}/receipt-history', token=TOKEN_A)
            self.assertEqual(history[0], 200)
            self.assertEqual([r['source_reference']['source_id'] for r in history[1]['receipts']], [sid, aid])
            self.assertEqual([r['kind'] for r in history[1]['receipts']], ['received', 'reconciled'])
            bid = self.ingest(base, pid, THIRD)[1]['source_id']
            second = self.reconcile(base, pid, rid, aid, bid, 'RECON-TWO')
            self.assertEqual(second[0], 201)
            self.assertNotEqual(second[1]['reconciliation_id'], first_id)
        with running_server(create_app(self.settings)) as restarted:
            retry = self.reconcile(restarted, pid, rid, sid, aid)
            self.assertEqual((retry[0], retry[1]['reconciliation_id'], retry[1]['duplicate']),
                             (200, first_id, True))
            self.assertEqual(request(restarted, self.root(pid), token=TOKEN_A)[1]['requests'][0]['source_reference']['source_id'], bid)
        recorded = self.events(pid)
        self.assertEqual([r[0] for r in recorded], ['record.request.received', 'record.request.reconciled', 'record.request.reconciled'])
        self.assertEqual(recorded[0][1]['source_id'], sid)

    def test_intermediate_versions_may_be_skipped_but_unrelated_or_stale_sources_may_not(self):
        with running_server(create_app(self.settings)) as base:
            pid, rid, sid, aid = self.prepared(base)
            other = self.ingest(base, pid, ORIGINAL.replace('DOC-ONE', 'DOC-OTHER'))[1]['source_id']
            self.assertEqual(self.reconcile(base, pid, rid, sid, other)[0], 409)
            bid = self.ingest(base, pid, THIRD)[1]['source_id']
            self.assertEqual(self.reconcile(base, pid, rid, sid, aid)[0], 409)
            self.assertEqual(self.reconcile(base, pid, rid, sid, bid)[0], 201)
            self.assertEqual(self.reconcile(base, pid, rid, sid, bid, 'STALE-INTENT')[0], 409)
            self.assertEqual(self.reconcile(base, pid, rid, sid, bid, reason_code='clinical_approval')[0], 422)
            self.assertEqual(len(self.events(pid)), 2)

    def test_concurrent_identical_retry_is_one_event_and_changed_key_intent_conflicts(self):
        with running_server(create_app(self.settings)) as base:
            pid, rid, sid, aid = self.prepared(base)
            with ThreadPoolExecutor(max_workers=2) as pool:
                results = list(pool.map(lambda _: self.reconcile(base, pid, rid, sid, aid), range(2)))
            self.assertEqual(sorted(r[0] for r in results), [200, 201])
            self.assertEqual(len({r[1]['reconciliation_id'] for r in results}), 1)
            self.assertEqual(self.reconcile(base, pid, rid, sid, sid)[0], 409)
            self.assertEqual(len(self.events(pid)), 2)

    def test_missing_grants_wrong_case_and_revoked_binding_are_not_reconciliation(self):
        with running_server(create_app(self.settings)) as base:
            pid, rid, sid, aid = self.prepared(base)
            for grant in ('patient_read', 'source_read', 'record_request_receive'):
                with self.subTest(grant=grant):
                    self.creds[0]['actions'].remove(grant); self.write()
                    self.assertEqual(self.reconcile(base, pid, rid, sid, aid)[0], 404)
                    self.creds[0]['actions'].append(grant); self.write()
            self.assertEqual(self.reconcile(base, pid, rid, sid, aid, case_id='CASE-OTHER')[0], 404)
            self.assertEqual(self.reconcile(base, pid, rid, sid, aid, synthetic=False)[0], 422)
            self.assertEqual(len(self.events(pid)), 1)
            self.assertEqual(self.reconcile(base, pid, rid, sid, aid)[0], 201)
            self.creds[0]['actions'].remove('source_read'); self.write()
            self.assertIsNone(request(base, self.root(pid), token=TOKEN_A)[1]['requests'][0]['source_reference'])
            self.assertEqual(request(base, self.root(pid) + f'/{rid}/receipt-history', token=TOKEN_A)[0], 404)
            self.creds[0]['actions'].append('source_read'); self.write()
            self.assertEqual(request(base, f'/v1/patients/{pid}/case-bindings/CASE-ALPHA/revoke', token=TOKEN_A,
                body={'synthetic': True, 'reason': 'Fictional access withdrawn'})[0], 200)
            self.assertEqual(self.reconcile(base, pid, rid, sid, aid)[0], 404)
            self.assertEqual(request(base, self.root(pid) + f'/{rid}/receipt-history', token=TOKEN_A)[0], 404)
            self.assertIsNone(request(base, self.root(pid), token=TOKEN_A)[1]['requests'][0]['source_reference'])

    def test_revoke_during_actual_json_encoding_rolls_back_new_receipt(self):
        with running_server(create_app(self.settings)) as base:
            pid, rid, sid, aid = self.prepared(base)
            original = JSONResponse.render
            observed = []
            def encode(response, content):
                result = original(response, content)
                if isinstance(content, dict) and 'reconciliation_id' in content:
                    observed.append(content['reconciliation_id'])
                    self.creds[0]['actions'].remove('record_request_receive'); self.write()
                return result
            with patch.object(JSONResponse, 'render', encode):
                response = self.reconcile(base, pid, rid, sid, aid)
            self.assertEqual(len(observed), 1)
            self.assertEqual(response[0], 404)
            self.assertNotIn('reconciliation_id', response[1])
            self.assertEqual(len(self.events(pid)), 1)
            self.creds[0]['actions'].append('record_request_receive'); self.write()
            self.assertEqual(self.reconcile(base, pid, rid, sid, aid)[0], 201)

    def test_event_and_encoder_failures_leave_no_successful_reconciliation(self):
        with running_server(create_app(self.settings)) as base:
            pid, rid, sid, aid = self.prepared(base)
            original_event = PostgresPatientRegistry.append_event
            def failed_event(registry, patient, event_type, **values):
                if event_type == 'record.request.reconciled':
                    raise RuntimeError('private fault must not be disclosed')
                return original_event(registry, patient, event_type, **values)
            with patch.object(PostgresPatientRegistry, 'append_event', failed_event):
                status, body, _ = self.reconcile(base, pid, rid, sid, aid)
            self.assertEqual((status, body), (503, {'detail': 'Patient registry unavailable'}))
            self.assertEqual(len(self.events(pid)), 1)
            original_render = JSONResponse.render
            def failed_render(response, content):
                if isinstance(content, dict) and 'reconciliation_id' in content:
                    raise RuntimeError('private encoding fault')
                return original_render(response, content)
            with patch.object(JSONResponse, 'render', failed_render):
                self.assertEqual(self.reconcile(base, pid, rid, sid, aid)[0], 503)
            self.assertEqual(len(self.events(pid)), 1)
            self.assertEqual(self.reconcile(base, pid, rid, sid, aid)[0], 201)


if __name__ == '__main__':
    unittest.main()
