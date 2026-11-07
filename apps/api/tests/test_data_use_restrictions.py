"""Purpose restrictions subtract authority; no patient consent is inferred."""
from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy
import unittest
from unittest.mock import patch
from pydantic import ValidationError
from sqlalchemy import text
from oi_api.app import create_app
from oi_api.patients import DataUseDecision, DataUseState
from http_support import running_server
from test_patients import TOKEN_A, TOKEN_B, request
from test_source_versions import SourceVersionFixture


class DataUseContractTests(unittest.TestCase):
    def test_strict_bounded_decision(self):
        valid = dict(synthetic=True, request_key='DECISION-ONE', expected_revision=0,
                     target_purpose='research', state='restricted')
        self.assertEqual(DataUseDecision(**valid).expected_revision, 0)
        for change in ({'synthetic': False}, {'expected_revision': True},
                       {'expected_revision': -1}, {'expected_revision': '0'},
                       {'target_purpose': 'care'}, {'state': 'consented'},
                       {'actor': 'ACTOR-OTHER'}, {'request_key': 'person@example.org'}):
            with self.subTest(change=change), self.assertRaises(ValidationError):
                DataUseDecision(**(valid | change))


class DataUseHTTPTests(SourceVersionFixture):
    def setUp(self):
        super().setUp()
        self.creds[0]['actions'] += ['data_use_manage', 'data_use_read']
        self.write()

    def command(self, base, pid, **changes):
        body = dict(synthetic=True, request_key='DECISION-ONE', expected_revision=0,
                    target_purpose='operations', state='restricted')
        body.update(changes)
        return request(base, f'/v1/patients/{pid}/data-use', token=TOKEN_A, body=body)

    def test_restriction_blocks_sources_preserves_identity_and_retries_after_restart(self):
        with running_server(create_app(self.settings)) as base:
            pid = self.setup_case(base)
            self.assertEqual(self.ingest(base, pid)[0], 201)
            code, empty, _ = request(base, f'/v1/patients/{pid}/data-use/operations', token=TOKEN_A)
            self.assertEqual((code, empty['state'], empty['revision']), (200, 'unrecorded', 0))
            self.assertFalse(empty['consent_established'])
            code, receipt, _ = self.command(base, pid)
            self.assertEqual(code, 200, receipt)
            self.assertEqual(request(base, self.url(pid), token=TOKEN_A)[0], 404)
            self.assertEqual(self.ingest(base, pid)[0], 404)
            self.assertEqual(request(base, f'/v1/patients/{pid}', token=TOKEN_A)[0], 200)
        with running_server(create_app(self.settings)) as base:
            self.assertEqual(self.command(base, pid)[:2], (200, receipt))
            self.assertEqual(self.command(base, pid, state='unrestricted')[0], 409)
            self.assertEqual(self.command(base, pid, state='unrestricted', expected_revision=1,
                                          request_key='DECISION-TWO')[0], 200)
            self.assertEqual(request(base, self.url(pid), token=TOKEN_A)[0], 200)
            # Replaying the old decision never re-applies its restriction.
            self.assertEqual(self.command(base, pid)[:2], (200, receipt))
            self.assertEqual(request(base, self.url(pid), token=TOKEN_A)[0], 200)
            self.creds[0]['actions'].remove('source_read')
            self.write()
            self.assertEqual(request(base, self.url(pid), token=TOKEN_A)[0], 404)
        with self.engine.connect() as c:
            self.assertEqual(c.execute(text("SELECT count(*) FROM identity.identity_domain_events "
                "WHERE event_type='identity.data_use.decided'")).scalar_one(), 2)

    def test_grants_scope_purpose_and_encoding_rollback(self):
        with running_server(create_app(self.settings)) as base:
            pid = self.setup_case(base)
            original = deepcopy(self.creds)
            for action in ('patient_read', 'data_use_manage'):
                self.creds = deepcopy(original)
                self.creds[0]['actions'].remove(action)
                self.write()
                self.assertEqual(self.command(base, pid)[0], 404)
            for changes in ({'organization': 'ORG-OTHER'}, {'patient_ids': []}, {'purpose': 'research'}):
                self.creds = deepcopy(original)
                self.creds[0].update(changes)
                self.write()
                self.assertEqual(self.command(base, pid)[0], 404)
            self.creds = deepcopy(original)
            self.write()
            with patch.object(DataUseState, 'model_dump', side_effect=ValueError('private')):
                self.assertEqual(self.command(base, pid)[0], 503)
            code, value, _ = request(base, f'/v1/patients/{pid}/data-use/operations', token=TOKEN_A)
            self.assertEqual((code, value['revision']), (200, 0))
            self.assertEqual(self.command(base, pid, request_key='X' * 17000)[0], 413)
            self.assertEqual(self.command(base, pid)[0], 200)

    def test_concurrent_retry_and_final_revocation(self):
        with running_server(create_app(self.settings)) as base:
            pid = self.setup_case(base)
            original = DataUseState.model_dump
            def revoke(value, *args, **kwargs):
                result = original(value, *args, **kwargs)
                self.creds[0]['actions'].remove('data_use_manage')
                self.write()
                return result
            with patch.object(DataUseState, 'model_dump', revoke):
                self.assertEqual(self.command(base, pid)[0], 404)
            self.creds[0]['actions'].append('data_use_manage')
            self.write()
            with ThreadPoolExecutor(max_workers=2) as pool:
                replies = list(pool.map(lambda _: self.command(base, pid)[:2], range(2)))
            self.assertEqual(replies[0], replies[1])
            self.assertEqual(replies[0][0], 200)
            with self.engine.connect() as c:
                self.assertEqual(c.execute(text("SELECT count(*) FROM identity.identity_domain_events "
                    "WHERE event_type='identity.data_use.decided'")).scalar_one(), 1)

    def test_other_purpose_and_other_patient_are_unchanged(self):
        with running_server(create_app(self.settings)) as base:
            pid = self.setup_case(base)
            self.assertEqual(self.ingest(base, pid)[0], 201)
            other = self.setup_case(base, case='CASE-BETA', token=TOKEN_B, source_subject='SUBJECT-BETA')
            self.assertEqual(self.command(base, pid, target_purpose='research')[0], 200)
            self.assertEqual(request(base, self.url(pid), token=TOKEN_A)[0], 200)
            self.assertEqual(request(base, self.url(other, 'CASE-BETA'), token=TOKEN_B)[0], 200)
            self.creds[0]['purpose'] = 'research'
            self.write()
            self.assertEqual(request(base, self.url(pid), token=TOKEN_A)[0], 404)
