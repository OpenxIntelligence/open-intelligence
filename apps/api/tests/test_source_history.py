"""Historical H1 reads over actual PostgreSQL; independently invented records only."""
from datetime import datetime, timedelta, timezone
from urllib.parse import quote
import unittest
from unittest.mock import patch
from oi_api.sources import PostgresSourceVersions
from open_intelligence.postgres_registry import PostgresPatientRegistry
from open_intelligence.patient_registry import PatientRegistryError
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
            for cutoff in ('invalid', '2026-01-01T12:00:00.000000', '2026-02-30T00:00:00Z',
                           '2026-01-01T00:00:00.0000001Z', '2026-01-01T00:00:00+00:99', (datetime.now(timezone.utc)+timedelta(days=1)).isoformat()):
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


    def test_history_does_not_grant_original_access_and_rechecks_after_final_audit(self):
        with running_server(create_app(self.settings)) as base:
            patient=self.setup_case(base);self.ingest(base,patient)
            model=self.current(base,patient);cutoff=model['as_of_received_at']
            original=self.url(patient)+'/'+model['current_sources'][0]['source_id']
            self.ingest(base,patient,AMENDED)
            self.creds[0]['actions'].remove('source_original_read');self.write()
            self.assertEqual(request(base,self.route(patient,cutoff),token=TOKEN_A)[0],200)
            before=self.events()
            self.assertEqual(request(base,original,token=TOKEN_A)[0],404)
            self.assertEqual(self.events(),before)
            self.creds[0]['actions'].append('source_original_read');self.write()
            self.assertEqual(request(base,original,token=TOKEN_A)[1]['original_text'],ORIGINAL)
            append=PostgresPatientRegistry.append_event
            def withdraw(registry,patient,event,**metadata):
                append(registry,patient,event,**metadata)
                if event=='source.read_authorized':
                    self.creds[0]['actions'].remove('source_read');self.write()
            before=self.events()
            with patch.object(PostgresPatientRegistry,'append_event',new=withdraw):
                self.assertEqual(request(base,self.route(patient,cutoff),token=TOKEN_A)[0],404)
            self.assertEqual(self.events(),before)

    def test_history_audit_failure_rolls_back_and_permits_fresh_retry(self):
        with running_server(create_app(self.settings)) as base:
            patient=self.setup_case(base);self.ingest(base,patient)
            route=self.route(patient,self.current(base,patient)['as_of_received_at'])
            before=self.events();append=PostgresPatientRegistry.append_event
            def fail_after_append(registry,patient,event,**metadata):
                append(registry,patient,event,**metadata)
                if event=='source.history_prepared': raise RuntimeError('fictional journal fault')
            with patch.object(PostgresPatientRegistry,'append_event',new=fail_after_append):
                self.assertEqual(request(base,route,token=TOKEN_A)[0],503)
            self.assertEqual(self.events(),before)
            self.assertEqual(request(base,route,token=TOKEN_A)[0],200)
            self.assertEqual(self.events(),before+2)

    def test_backwards_amendment_receipt_withholds_history(self):
        with running_server(create_app(self.settings)) as base:
            patient=self.setup_case(base);self.ingest(base,patient)
            cutoff=self.current(base,patient)['as_of_received_at']
            self.ingest(base,patient,AMENDED)
            with self.engine.begin() as c:
                c.execute(text('ALTER TABLE clinical_source.source_versions DISABLE TRIGGER USER'))
                c.execute(text("UPDATE clinical_source.source_versions SET received_at=:cutoff WHERE version=2"),
                          {'cutoff':datetime.fromisoformat(cutoff)-timedelta(microseconds=1)})
                c.execute(text('ALTER TABLE clinical_source.source_versions ENABLE TRIGGER USER'))
            before=self.events()
            self.assertEqual(request(base,self.route(patient,cutoff),token=TOKEN_A)[0],503)
            self.assertEqual(self.events(),before)


class ReceiptCutoffTests(unittest.TestCase):
    def test_exact_microsecond_and_equivalent_timezone(self):
        parse=PostgresSourceVersions.receipt_cutoff
        first=parse('2026-01-03T10:00:00.000001Z')
        self.assertEqual(first,parse('2026-01-03T11:00:00.000001+01:00'))
        self.assertEqual(parse('2026-01-03T10:00:00.000002Z')-first,timedelta(microseconds=1))

    def test_rejects_lossy_naive_invalid_calendar_and_future_boundaries(self):
        for value in (None,123,'2026-02-30T00:00:00Z','2026-01-01T24:00:00Z',
                      '2026-01-01T00:00:00','2026-01-01T00:00:00.0000001Z',
                      '2026-01-01T00:00:00+00:99',
                      (datetime.now(timezone.utc)+timedelta(days=1)).isoformat()):
            with self.subTest(value=value),self.assertRaises(PatientRegistryError):
                PostgresSourceVersions.receipt_cutoff(value)


class HistoryContractTests(unittest.TestCase):
    def test_single_history_wire_contract_is_shared_by_both_screens(self):
        from oi_api.config import Settings
        schema=create_app(Settings.from_env({})).openapi()
        path='/v1/patients/{patient_id}/cases/{case_id}/world-model/history'
        ref=schema['paths'][path]['get']['responses']['200']['content']['application/json']['schema']['$ref']
        model=schema['components']['schemas'][ref.rsplit('/',1)[1]]
        self.assertEqual(model['properties']['contract']['const'],'oi.pg-source-history/1')
        self.assertIn('world_model',model['required'])
        self.assertNotIn(path.replace('/world-model/history','/source-history'),schema['paths'])

    def test_invalid_cutoff_is_rejected_before_any_database_access(self):
        import json,tempfile
        from pathlib import Path
        from oi_api.config import Settings
        from oi_api.database import Database
        from test_patients import credential
        with tempfile.TemporaryDirectory() as directory:
            access=Path(directory)/'access.json'
            access.write_text(json.dumps({'version':'oi.synthetic-access/1','credentials':[
                credential(TOKEN_A,patients=['PAT-FICTIONAL'],actions=['patient_read','source_read'])]}))
            settings=Settings.from_env({'OI_API_ACCESS_FILE':str(access)})
            with patch.object(Database,'registry_connection') as connection,running_server(create_app(settings)) as base:
                for cutoff in ('2026-01-10','2026-01-10T00:00:00','9999-01-01T00:00:00Z','2026-01-10T00:00:00.0000001Z'):
                    path='/v1/patients/PAT-FICTIONAL/cases/CASE-ALPHA/world-model/history?received_through='+quote(cutoff,safe='')
                    self.assertEqual(request(base,path,token=TOKEN_A)[0],422)
                connection.assert_not_called()
