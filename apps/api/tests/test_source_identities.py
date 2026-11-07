"""Fictional institutional identity, original custody and recovery on PostgreSQL16."""
import hashlib
import os
from pathlib import Path
import subprocess
import unittest
from concurrent.futures import ThreadPoolExecutor
from unittest.mock import patch
from alembic.util.exc import CommandError
from sqlalchemy import text
from sqlalchemy.engine import make_url
from oi_api.app import create_app
from oi_api.migrate import migrate
from oi_api.contracts import SCHEMA_REVISION
from oi_api.patients import CreateSourceIdentity
from pydantic import ValidationError
import test_laboratory_fhir_http as lab
from test_laboratory_fhir_r4 import example, encode
from test_patients import TOKEN_A, TOKEN_B, request
from http_support import running_server


class SourceIdentityWireTests(unittest.TestCase):
    def test_input_never_coerces_synthetic_marker_or_accepts_authority(self):
        body=dict(synthetic=True,request_key='IDENTITY-TWO',review_ref='REVIEW-TWO',
            source_organization='ORG-TWO',source_system='SYS-TWO',source_subject_ref='SUBJECT-TWO')
        self.assertTrue(CreateSourceIdentity(**body).synthetic)
        for change in ({'synthetic':1},{'synthetic':'true'},{'actor':'OTHER'},{'status':'linked'}):
            with self.subTest(change=change),self.assertRaises(ValidationError):
                CreateSourceIdentity(**(body|change))


@unittest.skipUnless(os.environ.get('OI_API_RUN_DATABASE_TESTS')=='1','Requires disposable PostgreSQL16')
class SourceIdentityTests(unittest.TestCase):
    setUpClass=classmethod(lab.LaboratoryFHIRHTTPTests.setUpClass.__func__)
    tearDownClass=classmethod(lab.LaboratoryFHIRHTTPTests.tearDownClass.__func__)
    setUp=lab.LaboratoryFHIRHTTPTests.setUp
    tearDown=lab.LaboratoryFHIRHTTPTests.tearDown
    write_access=lab.LaboratoryFHIRHTTPTests.write_access
    make_patient=lab.LaboratoryFHIRHTTPTests.make_patient
    lab_counts=lab.LaboratoryFHIRHTTPTests.lab_counts

    def url(self,pid):
        return f'/v1/patients/{pid}/cases/CASE-LAB-A/source-identities'

    def identity(self,base,pid,suffix='B',**changes):
        body=dict(synthetic=True,request_key='SOURCE-IDENTITY-'+suffix,
            source_organization='ORG-FICTIONAL-'+suffix,source_system='SYS-FICTIONAL-LIS',
            source_subject_ref='FICTIONAL-PATIENT-'+suffix,review_ref='REVIEW-FICTIONAL-'+suffix)
        body.update(changes)
        return request(base,self.url(pid),token=TOKEN_A,body=body)

    def identities(self,base,pid):
        if 'case_binding_read' not in self.creds[0]['actions']:
            self.creds[0]['actions'].append('case_binding_read');self.write_access()
        return request(base,self.url(pid),token=TOKEN_A)

    def upload(self,base,pid,suffix,identity=None,previous=None,key=None,raw=None):
        original=encode(example()).decode().replace('FICTIONAL-PATIENT-A','FICTIONAL-PATIENT-'+suffix).replace('FICTIONAL-REPORT-A','FICTIONAL-REPORT-'+suffix)
        payload=dict(synthetic=True,request_key=key or 'IMPORT-'+suffix,bundle_json=raw or original,
                     expected_previous_source_id=previous)
        if identity is not None:payload['source_identity_id']=identity
        return request(base,f'/v1/patients/{pid}/cases/CASE-LAB-A/laboratory/fhir-r4/sources',token=TOKEN_A,body=payload)

    def test_three_institutions_originals_amendment_and_exact_retry(self):
        with running_server(self.app) as base:
            pid=self.make_patient(base)
            ids={}
            for suffix in ('B','C'):
                status,receipt,_=self.identity(base,pid,suffix)
                self.assertEqual(status,201,receipt);ids[suffix]=receipt['identity_id']
                self.assertEqual(self.identity(base,pid,suffix)[1],receipt|{'duplicate':True})
            receipts={}
            for suffix in ('A','B','C'):
                status,receipt,_=self.upload(base,pid,suffix,ids.get(suffix))
                self.assertEqual(status,201,receipt);receipts[suffix]=receipt
            self.assertEqual(len({r['source_id'] for r in receipts.values()}),3)
            rows=self.identities(base,pid)[1]['identities']
            self.assertEqual(len(rows),3);self.assertEqual(sum(r['primary_identity'] for r in rows),1)
            old=receipts['B']; original=encode(example()).decode().replace('FICTIONAL-PATIENT-A','FICTIONAL-PATIENT-B').replace('FICTIONAL-REPORT-A','FICTIONAL-REPORT-B')
            amended=original.replace('4.20','6.20')
            status,new,_=self.upload(base,pid,'B',ids['B'],old['source_id'],'AMEND-B',amended)
            self.assertEqual(status,201,new);self.assertEqual(new['version'],2)
            self.assertEqual(self.upload(base,pid,'B',ids['B'])[1],old|{'duplicate':True})
            for receipt,raw in ((old,original),(new,amended)):
                path=f'/v1/patients/{pid}/cases/CASE-LAB-A/sources/{receipt["source_id"]}/original'
                status,data,_=request(base,path,token=TOKEN_A)
                self.assertEqual(status,200,data);self.assertEqual(data['original_text'],raw)
                self.assertEqual(data['institutional_identity']['source_organization'],'ORG-FICTIONAL-B')
            status,index,_=request(base,f'/v1/patients/{pid}/cases/CASE-LAB-A/sources',token=TOKEN_A)
            self.assertEqual(status,200,index);self.assertEqual(len(index['sources']),4)
        with running_server(self.app) as base:
            self.assertEqual(self.identities(base,pid)[1]['identities'],rows)
            self.assertEqual(self.upload(base,pid,'B',ids['B'])[1],old|{'duplicate':True})

    def test_conflicting_association_quarantined_without_leaking_other_patient(self):
        with running_server(self.app) as base:
            pid=self.make_patient(base)
            status,p2,_=request(base,'/v1/patients',token=TOKEN_A,body={'synthetic':True,'request_key':'OTHER-PATIENT'})
            self.assertEqual(status,201);other=p2['patient_id']
            self.creds[0]['patient_ids'].append(other);self.write_access()
            status,_,_=request(base,f'/v1/patients/{other}/case-bindings',token=TOKEN_A,body=dict(
                synthetic=True,case_id='CASE-OTHER',source_organization='ORG-FICTIONAL-B',
                source_system='SYS-FICTIONAL-LIS',source_subject_ref='FICTIONAL-PATIENT-B',review_ref='REVIEW-OTHER'))
            self.assertEqual(status,201)
            status,held,_=self.identity(base,pid)
            self.assertEqual((status,held['status']),(201,'quarantined'))
            self.assertNotIn(other,str(held));self.assertNotIn('CASE-OTHER',str(held))
            self.assertEqual(self.identity(base,pid)[1],held|{'duplicate':True})
            before=self.lab_counts()
            self.assertEqual(self.upload(base,pid,'B',held['identity_id'])[0],404)
            self.assertEqual(self.lab_counts(),before)

    def test_report_id_collision_does_not_relabel_identical_bytes(self):
        with running_server(self.app) as base:
            pid=self.make_patient(base)
            first=self.upload(base,pid,'A');self.assertEqual(first[0],201,first)
            status,second,_=self.identity(base,pid,source_subject_ref='FICTIONAL-PATIENT-A')
            self.assertEqual(status,201)
            before=self.lab_counts()
            self.assertEqual(self.upload(base,pid,'A',second['identity_id'],key='OTHER-IMPORT')[0],409)
            self.assertEqual(self.lab_counts(),before)

    def test_wrong_identity_subject_purpose_and_independent_grants(self):
        with running_server(self.app) as base:
            pid=self.make_patient(base);identity=self.identity(base,pid)[1]['identity_id']
            self.assertEqual(self.upload(base,pid,'C',identity)[0],422)
            self.assertEqual(self.upload(base,pid,'B','IDENT-'+'F'*32)[0],404)
            self.assertEqual(request(base,self.url(pid),token=TOKEN_B)[0],404)
            self.creds[0]['purpose']='research';self.write_access()
            self.assertEqual(self.identity(base,pid,'C')[0],404)
            self.creds[0]['purpose']='operations';self.creds[0]['actions'].remove('case_binding_create');self.write_access()
            self.assertEqual(self.identity(base,pid,'C')[0],404)
            self.assertEqual(self.upload(base,pid,'B',identity)[0],201)
            self.creds[0]['actions'].remove('source_import');self.write_access()
            self.assertEqual(self.upload(base,pid,'B',identity)[0],404)

    def test_exact_retry_concurrency_and_changed_intent(self):
        with running_server(self.app) as base:
            pid=self.make_patient(base)
            with ThreadPoolExecutor(max_workers=2) as pool:
                results=list(pool.map(lambda _:self.identity(base,pid),range(2)))
            self.assertEqual(sorted(r[0] for r in results),[200,201],results)
            self.assertEqual(len({r[1]['identity_id'] for r in results}),1)
            self.assertEqual(self.identity(base,pid,review_ref='DIFFERENT-REVIEW')[0],409)
            with self.engine.connect() as c:
                self.assertEqual(c.execute(text("SELECT count(*) FROM identity.identity_domain_events WHERE event_type='identity.source_identity_recorded'")).scalar_one(),1)

    def test_concurrent_legacy_primary_creation_still_recovers_one_binding(self):
        with running_server(self.app) as base:
            pid=self.make_patient(base)
            body=dict(synthetic=True,case_id='CASE-CONCURRENT',source_organization='ORG-CONCURRENT',
                source_system='SYS-CONCURRENT',source_subject_ref='SUBJECT-CONCURRENT',review_ref='REVIEW-CONCURRENT')
            with ThreadPoolExecutor(max_workers=2) as pool:
                replies=list(pool.map(lambda _:request(base,f'/v1/patients/{pid}/case-bindings',token=TOKEN_A,body=body),range(2)))
            self.assertEqual(sorted(r[0] for r in replies),[200,201],replies)
            with self.engine.connect() as c:
                self.assertEqual(c.execute(text("SELECT count(*) FROM coordination.case_source_identities WHERE case_id='CASE-CONCURRENT'")).scalar_one(),1)

    def test_response_failure_and_late_authority_loss_rollback(self):
        from oi_api.patients import SourceIdentityReceipt
        from open_intelligence.postgres_registry import PostgresPatientRegistry
        with running_server(self.app) as base:
            pid=self.make_patient(base)
            with patch.object(SourceIdentityReceipt,'model_dump',side_effect=RuntimeError('encoding failure')):
                self.assertEqual(self.identity(base,pid)[0],503)
            original=PostgresPatientRegistry.append_event
            def revoke_after_event(registry,patient,event,**kw):
                result=original(registry,patient,event,**kw)
                if event=='identity.source_identity_recorded':
                    self.creds[0]['actions'].remove('case_binding_create');self.write_access()
                return result
            with patch.object(PostgresPatientRegistry,'append_event',revoke_after_event):
                self.assertEqual(self.identity(base,pid)[0],404)
            with self.engine.connect() as c:
                self.assertEqual(c.execute(text('SELECT count(*) FROM coordination.case_source_identities WHERE NOT primary_identity')).scalar_one(),0)
                self.assertEqual(c.execute(text("SELECT count(*) FROM identity.identity_domain_events WHERE event_type='identity.source_identity_recorded'")).scalar_one(),0)

    def test_immutable_history_and_populated_downgrade_refusal(self):
        with running_server(self.app) as base:
            pid=self.make_patient(base);self.assertEqual(self.identity(base,pid)[0],201)
        for sql in ('DELETE FROM coordination.case_source_identities','TRUNCATE coordination.case_source_identities',
                    "UPDATE coordination.case_source_identities SET status='quarantined'"):
            with self.assertRaises(Exception),self.engine.begin() as c:c.execute(text(sql))
        with self.assertRaises(CommandError):migrate(self.settings,'downgrade','0029_patient_access')
        with self.engine.connect() as c:
            self.assertEqual(c.execute(text('SELECT version_num FROM public.alembic_version')).scalar_one(),SCHEMA_REVISION)

    def test_populated_upgrade_preserves_primary_and_revoked_cases(self):
        with running_server(self.app) as base:
            pid=self.make_patient(base)
            self.assertEqual(self.upload(base,pid,'A')[0],201)
            self.assertEqual(request(base,f'/v1/patients/{pid}/case-bindings',token=TOKEN_A,body=dict(
                synthetic=True,case_id='CASE-RETIRED',source_organization='ORG-RETIRED',
                source_system='SYS-RETIRED',source_subject_ref='SUBJECT-RETIRED',review_ref='REVIEW-RETIRED'))[0],201)
            self.assertEqual(request(base,f'/v1/patients/{pid}/case-bindings/CASE-RETIRED/revoke',token=TOKEN_A,
                body={'synthetic':True,'reason':'Retire fictional historical case mapping'})[0],200)
        with self.engine.connect() as c:
            before=c.execute(text('SELECT * FROM coordination.patient_case_bindings')).all()
            sources=c.execute(text('SELECT * FROM clinical_source.source_versions')).all()
        migrate(self.settings,'downgrade','0029_patient_access')
        migrate(self.settings,'upgrade','head');migrate(self.settings,'upgrade','head')
        with self.engine.connect() as c:
            self.assertEqual(c.execute(text('SELECT * FROM coordination.patient_case_bindings')).all(),before)
            self.assertEqual(c.execute(text('SELECT * FROM clinical_source.source_versions')).all(),sources)
            self.assertEqual(c.execute(text('SELECT count(*) FROM coordination.case_source_identities WHERE primary_identity')).scalar_one(),2)

    def test_dump_restore_retains_exact_institution_original_and_revocation_denial(self):
        with running_server(self.app) as base:
            pid=self.make_patient(base);identity=self.identity(base,pid)[1]
            receipt=self.upload(base,pid,'B',identity['identity_id'])[1]
            identities=self.identities(base,pid)[1]
        url=make_url(self.settings.database_url)
        env=dict(os.environ,PGHOST=url.host,PGPORT=str(url.port or 5432),PGUSER=url.username,PGPASSWORD=url.password or '',PGDATABASE=url.database)
        dump=Path(self.folder.name)/'identities.dump'
        subprocess.run(['pg_dump','--format=custom','--no-owner','--file',str(dump)],env=env,capture_output=True,check=True)
        with self.engine.begin() as c:
            for schema in ('ehr','investigation','clinical_source','coordination','identity'):
                c.execute(text('DROP SCHEMA '+schema+' CASCADE'))
            c.execute(text('DROP TABLE public.alembic_version'))
        subprocess.run(['pg_restore','--no-owner','--exit-on-error','--dbname',url.database,str(dump)],env=env,capture_output=True,check=True)
        with running_server(self.app) as base:
            self.assertEqual(self.identities(base,pid)[1],identities)
            self.assertEqual(self.identity(base,pid)[1],identity|{'duplicate':True})
            self.assertEqual(self.upload(base,pid,'B',identity['identity_id'])[1],receipt|{'duplicate':True})
            path=f'/v1/patients/{pid}/cases/CASE-LAB-A/sources/{receipt["source_id"]}/original'
            status,original,_=request(base,path,token=TOKEN_A)
            self.assertEqual(status,200,original)
            self.assertEqual(hashlib.sha256(original['original_text'].encode()).hexdigest(),receipt['original_sha256'])
            self.assertEqual(request(base,f'/v1/patients/{pid}/case-bindings/CASE-LAB-A/revoke',token=TOKEN_A,
                body={'synthetic':True,'reason':'Withdraw fictional source associations'})[0],200)
            self.assertEqual(request(base,path,token=TOKEN_A)[0],404)
            self.assertEqual(self.identity(base,pid)[0],404)
            self.assertEqual(self.upload(base,pid,'B',identity['identity_id'])[0],404)
