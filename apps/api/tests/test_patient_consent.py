"""Consent is an additional, current restriction on independently granted scope."""
from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
from datetime import datetime, timedelta, timezone
import json
import os
from pathlib import Path
import subprocess
import unittest
from unittest.mock import patch

from pydantic import ValidationError
from sqlalchemy import text
from sqlalchemy.engine import make_url
from oi_api.app import create_app
from oi_api.config import Settings, ConfigurationError
from oi_api.patient_consent import ConsentDecision
from oi_api.composer_runs import ACTIONS
from oi_api.worker import run_once
from oi_api.event_worker import run_once as deliver_once
from http_support import running_server
from test_patients import TOKEN_A, TOKEN_B, request
from test_source_versions import SourceVersionFixture
from test_patient_permissions import grant_payload


def decision(**changes):
    now = datetime.now(timezone.utc)
    return dict(synthetic=True, request_key='CONSENT-ONE', expected_revision=0,
        actor='ACTOR-ALPHA', target_purpose='operations', state='granted',
        actions=['patient_read','source_read'], decision_maker='PERSON-FICTIONAL',
        basis='self', authority_ref='DECLARATION-FICTIONAL',
        valid_from=(now-timedelta(minutes=1)).isoformat(),
        expires_at=(now+timedelta(minutes=20)).isoformat()) | changes


class ConsentContractTests(unittest.TestCase):
    def test_unambiguous_scope_and_declared_authority(self):
        valid = decision()
        for change in ({'synthetic': False}, {'expected_revision': True},
                       {'actions': ['consent_manage']}, {'actions': ['data_use_manage']},
                       {'actions': []}, {'basis': 'verified_guardian'},
                       {'actor': 'person@example.org'}, {'valid_from': '2026-01-01'},
                       {'expires_at': valid['valid_from']}, {'extra': True}):
            with self.subTest(change=change), self.assertRaises(ValidationError):
                ConsentDecision(**(valid | change))
        withdrawn = decision(state='withdrawn', actions=[], valid_from=None, expires_at=None)
        self.assertEqual(ConsentDecision(**withdrawn).state, 'withdrawn')
        with self.assertRaises(ValidationError):
            ConsentDecision(**(withdrawn | {'actions': ['source_read']}))

    def test_consent_mode_is_server_owned(self):
        self.assertTrue(Settings.from_env({'OI_API_REQUIRE_CONSENT_DECISIONS': '1'}).require_consent_decisions)
        from oi_api.access import Principal, authentication_for_settings
        context = Principal(actor='ACTOR-ONE', organization='ORG-ONE', purpose='operations',
            consent_decisions=False, expires_at=datetime.now(timezone.utc)+timedelta(hours=1))
        class Provider:
            def authenticate(self, token):
                return context
        self.assertTrue(authentication_for_settings(Settings(require_consent_decisions=True), Provider())
                        .authenticate('unused').consent_decisions)
        for value in ('true', 'false', '', '2'):
            with self.assertRaises(ConfigurationError):
                Settings.from_env({'OI_API_REQUIRE_CONSENT_DECISIONS': value})


class ConsentHTTPTests(SourceVersionFixture):
    def setUp(self):
        super().setUp()
        self.creds[0]['actions'] = sorted(set(self.creds[0]['actions']) | set(ACTIONS) |
            {'patient_permissions_read', 'patient_permissions_manage', 'consent_read', 'consent_manage',
             'data_use_read', 'data_use_manage'})
        self.write()
        self.governed = replace(self.settings, require_persisted_grants=True, require_consent_decisions=True)

    def seed(self):
        with running_server(create_app(self.settings)) as base:
            patient = self.setup_case(base)
            self.assertEqual(self.ingest(base, patient)[0], 201)
            payload = grant_payload(actions=['patient_read', *ACTIONS])
            self.assertEqual(request(base, f'/v1/patients/{patient}/permissions', token=TOKEN_A, body=payload)[0], 200)
        return patient

    def send(self, base, patient, body):
        return request(base, f'/v1/patients/{patient}/consent-decisions', token=TOKEN_A, body=body)

    def history(self, base, patient):
        return request(base, f'/v1/patients/{patient}/consent-decisions', token=TOKEN_A)

    def test_consent_permission_and_purpose_restriction_intersect(self):
        patient = self.seed()
        with running_server(create_app(self.governed)) as base:
            self.assertEqual(request(base, self.url(patient), token=TOKEN_A)[0], 404)
            self.assertEqual(self.send(base, patient, decision())[0], 200)
            self.assertEqual(request(base, self.url(patient), token=TOKEN_A)[0], 200)
            # Consent to reading cannot authorize source import or other clinical actions.
            self.assertEqual(self.ingest(base, patient)[0], 404)
            self.creds[0]['actions'].remove('source_read'); self.write()
            self.assertEqual(request(base, self.url(patient), token=TOKEN_A)[0], 404)
            self.creds[0]['actions'].append('source_read'); self.write()
            command = dict(synthetic=True, request_key='RESTRICT-ONE', expected_revision=0,
                           target_purpose='operations', state='restricted')
            self.assertEqual(request(base, f'/v1/patients/{patient}/data-use', token=TOKEN_A, body=command)[0], 200)
            self.assertEqual(request(base, self.url(patient), token=TOKEN_A)[0], 404)
            command.update(request_key='LIFT-ONE', expected_revision=1, state='unrestricted')
            self.assertEqual(request(base, f'/v1/patients/{patient}/data-use', token=TOKEN_A, body=command)[0], 200)
            self.assertEqual(request(base, self.url(patient), token=TOKEN_A)[0], 200)

    def test_withdrawal_and_old_retry_preserve_current_state_after_restart(self):
        patient = self.seed(); payload = decision()
        withdraw = decision(state='withdrawn', request_key='WITHDRAW-ONE', expected_revision=1,
                            actions=[], valid_from=None, expires_at=None)
        with running_server(create_app(self.governed)) as base:
            receipt = self.send(base, patient, payload)[1]
            self.assertEqual(self.send(base, patient, withdraw)[0], 200)
            self.assertEqual(self.send(base, patient, payload)[1], receipt | {'duplicate': True})
            self.assertEqual(request(base, self.url(patient), token=TOKEN_A)[0], 404)
            self.assertEqual(self.send(base, patient, decision(request_key='STALE-ONE'))[0], 409)
        with running_server(create_app(self.governed)) as base:
            self.assertTrue(self.send(base, patient, withdraw)[1]['duplicate'])
            rows = self.history(base, patient)[1]['decisions']
            self.assertEqual([r['revision'] for r in rows], [2, 1])
            self.assertEqual([r['status'] for r in rows], ['withdrawn', 'superseded'])
            self.assertEqual(request(base, self.url(patient), token=TOKEN_A)[0], 404)
        # Switching off positive-decision requirement cannot erase a recorded withdrawal.
        with running_server(create_app(self.settings)) as base:
            self.assertEqual(request(base, self.url(patient), token=TOKEN_A)[0], 404)

    def test_recipient_purpose_tenant_and_administration_are_independent(self):
        patient = self.seed()
        with running_server(create_app(self.governed)) as base:
            self.assertEqual(self.send(base, patient, decision(actor='ACTOR-OTHER'))[0], 200)
            self.assertEqual(self.send(base, patient, decision(request_key='RESEARCH-ONE', target_purpose='research'))[0], 200)
            self.assertEqual(request(base, self.url(patient), token=TOKEN_A)[0], 404)
            self.assertEqual(request(base, f'/v1/patients/{patient}/consent-decisions', token=TOKEN_B)[0], 404)
            self.assertEqual(self.send(base, patient, decision(actions=['patient_suspend']))[0], 422)
            self.assertEqual(self.send(base, patient, decision(expires_at='2099-01-01T00:00:00Z'))[0], 404)
            self.assertEqual(self.send(base, patient, decision(request_key='x'*17000))[0], 413)
            self.creds[0]['actions'].remove('consent_manage'); self.write()
            self.assertEqual(self.send(base, patient, decision())[0], 404)
            self.assertEqual(self.history(base, patient)[0], 200)

    def test_concurrent_retry_and_final_authority_encoding_rollback(self):
        from oi_api import patient_consent_routes as routes
        patient = self.seed(); payload = decision(); original = routes.JSONResponse
        def withdraw_authority(*args, **kwargs):
            result = original(*args, **kwargs)
            self.creds[0]['actions'].remove('consent_manage'); self.write()
            return result
        with running_server(create_app(self.governed)) as base:
            with patch.object(routes, 'JSONResponse', withdraw_authority):
                self.assertEqual(self.send(base, patient, payload)[0], 404)
            self.creds[0]['actions'].append('consent_manage'); self.write()
            with patch.object(routes, 'JSONResponse', side_effect=ValueError('PRIVATE')):
                self.assertEqual(self.send(base, patient, payload)[0], 503)
            self.assertEqual(self.history(base, patient)[1]['decisions'], [])
            with ThreadPoolExecutor(max_workers=2) as pool:
                replies = list(pool.map(lambda _: self.send(base, patient, payload), range(2)))
            self.assertEqual([r[0] for r in replies], [200, 200])
            self.assertEqual(replies[0][1]['event_id'], replies[1][1]['event_id'])

    def test_time_validity_and_both_worker_entry_points(self):
        import time
        patient = self.seed()
        for worker in (run_once, deliver_once):
            self.assertEqual(worker(self.governed, lambda: TOKEN_A, patient, 'CASE-ALPHA')['status'], 'blocked')
        now = datetime.now(timezone.utc)
        with running_server(create_app(self.governed)) as base:
            self.assertEqual(self.send(base, patient, decision(actions=list(ACTIONS),
                valid_from=(now+timedelta(seconds=2)).isoformat(),
                expires_at=(now+timedelta(seconds=4)).isoformat()))[0], 200)
            self.assertEqual(request(base, self.url(patient), token=TOKEN_A)[0], 404)
            time.sleep(2.1)
            self.assertEqual(run_once(self.governed, lambda: TOKEN_A, patient, 'CASE-ALPHA')['status'], 'idle')
            time.sleep(2.1)
            self.assertEqual(request(base, self.url(patient), token=TOKEN_A)[0], 404)
            self.assertEqual(self.history(base, patient)[1]['decisions'][0]['status'], 'expired')
        for worker in (run_once, deliver_once):
            self.assertEqual(worker(self.governed, lambda: TOKEN_A, patient, 'CASE-ALPHA')['status'], 'blocked')

    def test_backup_restore_retains_withdrawal_history_and_retry(self):
        patient = self.seed(); payload = decision()
        withdraw = decision(state='withdrawn', request_key='WITHDRAW-ONE', expected_revision=1,
                            actions=[], valid_from=None, expires_at=None)
        with running_server(create_app(self.governed)) as base:
            self.assertEqual(self.send(base, patient, payload)[0], 200)
            self.assertEqual(self.send(base, patient, withdraw)[0], 200)
            before = self.history(base, patient)[1]['decisions']
        url = make_url(self.admin.database_url)
        env = dict(os.environ, PGHOST=url.host, PGPORT=str(url.port or 5432), PGUSER=url.username,
                   PGPASSWORD=url.password or '', PGDATABASE=url.database)
        dump = Path(self.temp.name)/'consent.dump'
        subprocess.run(['pg_dump','--format=custom','--no-owner','--file',str(dump)], env=env, capture_output=True, check=True)
        with self.engine.begin() as c:
            for schema in ('investigation','clinical_source','ehr','coordination','identity'):
                c.execute(text(f'DROP SCHEMA {schema} CASCADE'))
            c.execute(text('DROP TABLE public.alembic_version'))
        subprocess.run(['pg_restore','--no-owner','--exit-on-error','--dbname',url.database,str(dump)], env=env, capture_output=True, check=True)
        with running_server(create_app(self.governed)) as base:
            self.assertEqual(self.history(base, patient)[1]['decisions'], before)
            self.assertTrue(self.send(base, patient, withdraw)[1]['duplicate'])
            self.assertEqual(request(base, self.url(patient), token=TOKEN_A)[0], 404)
        with self.assertRaises(Exception), self.engine.begin() as c:
            c.execute(text("DELETE FROM identity.identity_domain_events WHERE event_type='identity.consent.decided'"))

    def test_pagination_and_withdrawal_after_patient_suspension(self):
        patient = self.seed()
        with running_server(create_app(self.governed)) as base:
            first = self.send(base, patient, decision())[1]
            for index in range(25):
                self.assertEqual(self.send(base, patient, decision(request_key=f'CONSENT-{index}', actor=f'ACTOR-{index}'))[0], 200)
            page = self.history(base, patient)[1]
            self.assertEqual(len(page['decisions']), 25)
            code, older, _ = request(base, f'/v1/patients/{patient}/consent-decisions?before={page["next_before"]}', token=TOKEN_A)
            self.assertEqual(code, 200)
            self.assertEqual([r['event_id'] for r in older['decisions']], [first['event_id']])
            self.assertIsNone(older['next_before'])
        self.creds[0]['actions'].append('patient_suspend'); self.write()
        with running_server(create_app(self.settings)) as base:
            self.assertEqual(request(base, f'/v1/patients/{patient}/suspensions', token=TOKEN_A,
                body=dict(synthetic=True, request_key='SUSPEND-CONSENT', expected_revision=1))[0], 200)
        with running_server(create_app(self.governed)) as base:
            self.assertEqual(self.send(base, patient, decision(state='withdrawn', request_key='AFTER-SUSPENSION',
                expected_revision=1, actions=[], valid_from=None, expires_at=None))[0], 200)
            self.assertEqual(self.history(base, patient)[1]['decisions'][0]['status'], 'withdrawn')
