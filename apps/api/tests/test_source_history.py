"""Historical H1 reads over actual PostgreSQL; independently invented records only."""
from datetime import datetime, timedelta, timezone
from urllib.parse import quote
from unittest.mock import patch
from sqlalchemy import text
from oi_api.app import create_app
from oi_api import patients as routes
from oi_api.source_world_model import project_source_world_model
from http_support import running_server
from test_patients import request, TOKEN_A, TOKEN_B
from test_source_versions import SourceVersionFixture, ORIGINAL, AMENDED

class SourceHistoryHTTPTests(SourceVersionFixture):
    def route(self, patient, cutoff, case='CASE-ALPHA'):
        return f'/v1/patients/{patient}/cases/{case}/world-model/history?received_through='+quote(cutoff, safe='')

    def current(self, base, patient):
        status, body, _ = request(base, f'/v1/patients/{patient}/cases/CASE-ALPHA/world-model', token=TOKEN_A)
        self.assertEqual(status, 200, body)
        return body

    def events(self):
        with self.engine.connect() as c:
            return c.execute(text('SELECT count(*) FROM identity.identity_domain_events')).scalar_one()

    def test_amendment_reconstructs_exact_original_without_hindsight_and_survives_restart(self):
        with running_server(create_app(self.settings)) as base:
            patient = self.setup_case(base)
            self.assertEqual(self.ingest(base, patient)[0], 201)
            before = self.current(base, patient)
            cutoff = before['as_of_received_at']
            self.assertEqual(self.ingest(base, patient, AMENDED)[0], 201)
            current = self.current(base, patient)
            status, result, _ = request(base, self.route(patient, cutoff), token=TOKEN_A)
            self.assertEqual(status, 200, result)
            historical = result['world_model']
            for key in ('snapshot_fingerprint', 'summary', 'observations', 'current_sources', 'history'):
                self.assertEqual(historical[key], before[key], key)
            self.assertTrue(result['historical_only'])
            self.assertNotIn(current['current_sources'][0]['source_id'], str(result))
            self.assertEqual(self.current(base, patient)['snapshot_fingerprint'], current['snapshot_fingerprint'])
            with self.engine.connect() as c:
                receipt = c.execute(text("SELECT metadata_json FROM identity.identity_domain_events WHERE event_type='source.history_prepared'")).scalar_one()
                self.assertEqual(receipt['receipt_id'], historical['access_receipt_id'])
                self.assertEqual(receipt['received_through'], cutoff)
        with running_server(create_app(self.settings)) as base:
            status, reopened, _ = request(base, self.route(patient, cutoff), token=TOKEN_A)
            self.assertEqual(status, 200, reopened)
            self.assertEqual(reopened['world_model']['snapshot_fingerprint'], before['snapshot_fingerprint'])

    def test_late_arriving_older_event_and_empty_cutoff(self):
        with running_server(create_app(self.settings)) as base:
            patient = self.setup_case(base)
            self.ingest(base, patient)
            before = self.current(base, patient)
            cutoff = before['as_of_received_at']
            late = ORIGINAL.replace('DOC-ONE','DOC-LATE').replace('2026-01-10','2025-01-10')
            self.assertEqual(self.ingest(base, patient, late)[0], 201)
            result = request(base, self.route(patient, cutoff), token=TOKEN_A)
            self.assertEqual(result[0], 200, result)
            self.assertEqual(result[1]['world_model']['summary']['current_sources'], 1)
            self.assertNotIn('DOC-LATE', str(result[1]))
            earlier=(datetime.fromisoformat(cutoff)-timedelta(microseconds=1)).isoformat()
            status, empty, _ = request(base, self.route(patient, earlier), token=TOKEN_A)
            self.assertEqual(status, 200, empty)
            self.assertEqual(empty['world_model']['summary']['current_sources'], 0)

    def test_historical_reads_require_current_patient_case_and_source_authority(self):
        with running_server(create_app(self.settings)) as base:
            patient = self.setup_case(base)
            self.ingest(base, patient)
            cutoff = self.current(base, patient)['as_of_received_at']
            route = self.route(patient, cutoff)
            for token, url in ((TOKEN_B,route),(TOKEN_A,self.route(patient,cutoff,'CASE-OTHER'))):
                before=self.events()
                self.assertEqual(request(base,url,token=token)[0],404)
                self.assertEqual(self.events(),before)
            self.creds[0]['actions'].remove('source_read');self.write()
            before=self.events()
            self.assertEqual(request(base,route,token=TOKEN_A)[0],404)
            self.assertEqual(self.events(),before)

    def test_final_revocation_and_response_failure_roll_back_both_history_and_read_receipts(self):
        with running_server(create_app(self.settings)) as base:
            patient=self.setup_case(base);self.ingest(base,patient)
            route=self.route(patient,self.current(base,patient)['as_of_received_at'])
            before=self.events()
            def withdraw(index,labs):
                result=project_source_world_model(index,labs)
                self.creds[0]['actions'].remove('source_read');self.write()
                return result
            with patch.object(routes,'project_source_world_model',side_effect=withdraw):
                self.assertEqual(request(base,route,token=TOKEN_A)[0],404)
            self.assertEqual(self.events(),before)
            self.creds[0]['actions'].append('source_read');self.write()
            with patch.object(routes.SourceHistory,'model_dump',side_effect=RuntimeError('synthetic encoding fault')):
                self.assertEqual(request(base,route,token=TOKEN_A)[0],503)
            self.assertEqual(self.events(),before)

    def test_invalid_naive_and_future_cutoffs_do_not_create_receipts(self):
        with running_server(create_app(self.settings)) as base:
            patient=self.setup_case(base)
            for cutoff in ('invalid', '2026-01-01T12:00:00.000000', (datetime.now(timezone.utc)+timedelta(days=1)).isoformat()):
                before=self.events()
                self.assertIn(request(base,self.route(patient,cutoff),token=TOKEN_A)[0],(400,422))
                self.assertEqual(self.events(),before)

    def test_corrupted_historical_original_withholds_projection(self):
        with running_server(create_app(self.settings)) as base:
            patient=self.setup_case(base);self.ingest(base,patient)
            before=self.current(base,patient)
            self.ingest(base,patient,AMENDED)
            # Existing source-integrity fixture convention: temporarily disable
            # write guards solely to simulate disk/storage corruption.
            with self.engine.begin() as c:
                c.execute(text('ALTER TABLE clinical_source.source_versions DISABLE TRIGGER USER'))
                c.execute(text("UPDATE clinical_source.source_versions SET sha256=:bad WHERE source_id=:id"),
                          {'bad':'f'*64,'id':before['current_sources'][0]['source_id']})
                c.execute(text('ALTER TABLE clinical_source.source_versions ENABLE TRIGGER USER'))
            events=self.events()
            status,body,_=request(base,self.route(patient,before['as_of_received_at']),token=TOKEN_A)
            self.assertEqual(status,503,body)
            self.assertEqual(self.events(),events)
            self.assertNotIn('Fictional café',str(body))
