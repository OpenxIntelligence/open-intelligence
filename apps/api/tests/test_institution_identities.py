"""Three independently fictional institutions, ambiguity, custody and review authority."""
import json
from unittest.mock import patch
from sqlalchemy import text
from alembic.util.exc import CommandError
from fastapi.responses import JSONResponse
from oi_api.migrate import migrate
from open_intelligence.postgres_registry import PostgresPatientRegistry
from http_support import running_server
from test_patients import request, TOKEN_A, TOKEN_B
import test_laboratory_fhir_http as laboratory_fixture
from test_laboratory_fhir_r4 import example, resource, encode


class InstitutionIdentityTests(laboratory_fixture.LaboratoryFHIRHTTPTests):
    # Reuse the disposable real-HTTP/database fixture, not its inherited test methods.
    def setUp(self):
        super().setUp()
        self.creds[0]['actions'].extend(('case_binding_read','composer_context_read','question_create','question_read'))
        self.write_access()

    def path(self, pid):
        return f'/v1/patients/{pid}/cases/CASE-LAB-A/institution-identities'

    def propose(self, base, pid, org='ORG-SECOND', subject='SECOND-PATIENT', key='PROPOSAL-SECOND'):
        return request(base, self.path(pid), token=TOKEN_A, body={
            'synthetic':True,'request_key':key,'source_organization':org,
            'source_system':'SYS-FICTIONAL-LIS','source_subject_ref':subject})

    def decision(self, base, pid, identity, decision='link', review='REVIEW-INDEPENDENT-SYNTHETIC'):
        return request(base,self.path(pid)+'/'+identity+'/decision',token=TOKEN_A,
            body={'synthetic':True,'decision':decision,'review_ref':review})

    def import_identity(self, base, pid, identity, subject, key='IMPORT-SECOND', previous=None, value='4.20'):
        bundle=json.loads(encode(example()).decode().replace('FICTIONAL-PATIENT-A',subject))
        resource(bundle,'Observation')['valueQuantity']['value']=float(value)
        return request(base, f'/v1/patients/{pid}/cases/CASE-LAB-A/laboratory/fhir-r4/sources',
            token=TOKEN_A,body={'synthetic':True,'identity_id':identity,'bundle_json':encode(bundle).decode(),
                              'request_key':key,'expected_previous_source_id':previous})

    def test_three_institutions_same_local_report_number_stay_separate_and_amend(self):
        with running_server(self.app) as base:
            pid=self.make_patient(base)
            first=self.import_source(base,pid)
            self.assertEqual(first[0],201,first)
            sources=[first[1]['source_id']]
            for n in ('SECOND','THIRD'):
                status,proposal,_=self.propose(base,pid,'ORG-'+n,n+'-PATIENT','PROPOSAL-'+n)
                self.assertEqual(status,201,proposal)
                identity=proposal['identity']['identity_id']
                self.assertEqual(proposal['identity']['status'],'quarantined')
                self.assertEqual(self.import_identity(base,pid,identity,n+'-PATIENT','IMPORT-'+n)[0],404)
                decision=self.decision(base,pid,identity)
                self.assertEqual(decision[0],200,decision)
                self.assertTrue(self.decision(base,pid,identity)[1]['duplicate'])
                imported=self.import_identity(base,pid,identity,n+'-PATIENT','IMPORT-'+n)
                self.assertEqual(imported[0],201,imported)
                sources.append(imported[1]['source_id'])
                self.assertEqual(self.import_identity(base,pid,identity,n+'-PATIENT','IMPORT-'+n)[0],200)
            self.assertEqual(len(set(sources)),3)
            path=f'/v1/patients/{pid}/cases/CASE-LAB-A'
            index=request(base,path+'/sources',token=TOKEN_A)
            self.assertEqual(index[0],200,index)
            self.assertEqual(len({row['document_id'] for row in index[1]['sources']}),3)
            world=request(base,path+'/world-model',token=TOKEN_A)
            self.assertEqual(world[0],200,world)
            self.assertEqual(len(world[1]['laboratory_observations']),3)
            fields={'synthetic':True,'source_id':sources[-1],
                    'observation_reference':'Observation/FICTIONAL-OBS-A',
                    'expected_source_snapshot_sha256':world[1]['snapshot_fingerprint'],
                    'question':'Which fictional institution supplied this laboratory result?'}
            prepared=request(base,path+'/composer/laboratory-preflight',token=TOKEN_A,body=fields)
            self.assertEqual(prepared[0],200,prepared)
            saved=request(base,path+'/composer/laboratory-questions',token=TOKEN_A,
                body={**fields,'request_key':'THIRD-QUESTION','expected_preflight_sha256':prepared[1]['preflight_sha256']})
            self.assertEqual(saved[0],201,saved)
            amended=self.import_identity(base,pid,identity,'THIRD-PATIENT','IMPORT-AMEND',sources[-1],'5.20')
            self.assertEqual(amended[0],201,amended)
            for source in sources:
                original=request(base,path+'/sources/'+source,token=TOKEN_A)
                self.assertEqual(original[0],200,original)
                attribution=request(base,path+'/sources/'+source+'/institution',token=TOKEN_A)
                self.assertEqual(attribution[0],200,attribution)
                self.assertEqual(attribution[1]['sha256'],original[1]['sha256'])
            self.assertEqual(request(base,path+'/sources',token=TOKEN_A)[0],200)
            history=request(base,path+'/composer/laboratory-questions',token=TOKEN_A)
            self.assertEqual(history[0],200,history)
            self.assertEqual(history[1]['questions'][0]['source_context_state'],'source_reassessment_required')
            self.assertEqual(self.import_identity(base,pid,identity,'THIRD-PATIENT','IMPORT-THIRD')[1]['source_id'],sources[-1])
        with running_server(self.app) as restarted:
            self.assertEqual(request(restarted,self.path(pid),token=TOKEN_A)[0],200)
            self.assertEqual(request(restarted,path+'/sources',token=TOKEN_A)[0],200)

    def test_ambiguous_namespace_stays_quarantined_until_rejected(self):
        with running_server(self.app) as base:
            pid=self.make_patient(base)
            proposal=self.propose(base,pid,'ORG-FICTIONAL-HOSPITAL','WRONG-PATIENT')[1]['identity']
            identity=proposal['identity_id']
            before=self.lab_counts()
            self.assertEqual(self.decision(base,pid,identity)[0],409)
            self.assertEqual(self.import_identity(base,pid,identity,'WRONG-PATIENT')[0],404)
            self.assertEqual(self.lab_counts(),before)
            rows=request(base,self.path(pid),token=TOKEN_A)[1]['identities']
            self.assertEqual(rows[-1]['status'],'quarantined')
            self.assertEqual(self.decision(base,pid,identity,'reject')[1]['identity']['status'],'rejected')
            self.assertEqual(self.decision(base,pid,identity)[0],409)
            self.assertEqual(self.propose(base,pid)[0],409)  # original key cannot change its tuple

    def test_current_scope_and_json_authority_rollback_every_write(self):
        with running_server(self.app) as base:
            pid=self.make_patient(base)
            self.assertEqual(request(base,self.path(pid),token=TOKEN_B)[0],404)
            self.creds[0]['purpose']='research';self.write_access()
            self.assertEqual(self.propose(base,pid)[0],404)
            self.creds[0]['purpose']='operations';self.write_access()
            render=JSONResponse.render
            def withdraw(response,content):
                result=render(response,content)
                if isinstance(content,dict) and 'identity' in content:
                    self.creds[0]['actions'].remove('case_binding_create');self.write_access()
                return result
            with patch.object(JSONResponse,'render',withdraw):
                self.assertEqual(self.propose(base,pid)[0],404)
            self.assertEqual(len(request(base,self.path(pid),token=TOKEN_A)[1]['identities']),1)

    def test_competing_cases_cannot_accept_the_same_qualified_subject(self):
        from concurrent.futures import ThreadPoolExecutor
        from threading import Barrier
        with running_server(self.app) as base:
            pid=self.make_patient(base)
            status,other,_=request(base,'/v1/patients',token=TOKEN_A,
                body={'synthetic':True,'request_key':'PATIENT-OTHER-IDENTITY'})
            self.assertEqual(status,201,other)
            other=other['patient_id'];self.creds[0]['patient_ids'].append(other);self.write_access()
            self.assertEqual(request(base,f'/v1/patients/{other}/case-bindings',token=TOKEN_A,
                body={'synthetic':True,'case_id':'CASE-LAB-B','source_organization':'ORG-OTHER',
                      'source_system':'SYS-OTHER','source_subject_ref':'OTHER-PATIENT','review_ref':'OTHER-REVIEW'})[0],201)
            first=self.propose(base,pid)[1]['identity']['identity_id']
            other_path=f'/v1/patients/{other}/cases/CASE-LAB-B/institution-identities'
            status,second,_=request(base,other_path,token=TOKEN_A,body={'synthetic':True,
                'request_key':'PROPOSAL-OTHER','source_organization':'ORG-SECOND',
                'source_system':'SYS-FICTIONAL-LIS','source_subject_ref':'SECOND-PATIENT'})
            self.assertEqual(status,201,second)
            paths=[self.path(pid)+'/'+first+'/decision',other_path+'/'+second['identity']['identity_id']+'/decision']
            gate=Barrier(2)
            def decide(path):
                gate.wait(timeout=5)
                return request(base,path,token=TOKEN_A,body={'synthetic':True,'decision':'link','review_ref':'RACE-REVIEW'})
            with ThreadPoolExecutor(max_workers=2) as executor:
                results=list(executor.map(decide,paths))
            self.assertEqual(sorted(row[0] for row in results),[200,409],results)
            with self.engine.connect() as c:
                states=c.execute(text("SELECT status FROM coordination.case_source_identities WHERE source_organization='ORG-SECOND' ORDER BY status")).scalars().all()
                self.assertEqual(states,['active','quarantined'])
            failed=next(row for row in results if row[0]==409)
            self.assertNotIn(other,json.dumps(failed));self.assertNotIn(pid,json.dumps(failed))

    def test_populated_primary_upgrade_and_roundtrip_preserve_identity_and_original(self):
        with running_server(self.app) as base:
            pid=self.make_patient(base)
            source=self.import_source(base,pid)[1]
            with self.engine.connect() as c:
                original=c.execute(text('SELECT * FROM clinical_source.source_versions')).all()
                mapping=c.execute(text('SELECT * FROM coordination.patient_case_bindings')).all()
                identity=c.execute(text('SELECT * FROM coordination.case_source_identities')).all()
            migrate(self.settings,'downgrade','0022_lab_citation_source_scope')
            migrate(self.settings,'upgrade','head')
            with self.engine.connect() as c:
                self.assertEqual(c.execute(text('SELECT * FROM clinical_source.source_versions')).all(),original)
                self.assertEqual(c.execute(text('SELECT * FROM coordination.patient_case_bindings')).all(),mapping)
                self.assertEqual(c.execute(text('SELECT * FROM coordination.case_source_identities')).all(),identity)
            self.assertEqual(self.import_source(base,pid)[1]['source_id'],source['source_id'])

    def test_immutable_events_and_decisions_rollback_and_downgrade_refuses_history(self):
        with running_server(self.app) as base:
            pid=self.make_patient(base)
            identity=self.propose(base,pid)[1]['identity']['identity_id']
            with patch.object(PostgresPatientRegistry,'append_event',side_effect=RuntimeError('synthetic event failure')):
                self.assertEqual(self.decision(base,pid,identity)[0],503)
            rows=request(base,self.path(pid),token=TOKEN_A)[1]['identities']
            self.assertEqual(rows[-1]['status'],'quarantined')
            with self.assertRaises(CommandError):
                migrate(self.settings,'downgrade','0022_lab_citation_source_scope')
            self.assertEqual(self.decision(base,pid,identity)[0],200)
            conflict=request(base,f'/v1/patients/{pid}/case-bindings',token=TOKEN_A,
                body={'synthetic':True,'case_id':'CASE-CANNOT-REUSE','source_organization':'ORG-SECOND',
                      'source_system':'SYS-FICTIONAL-LIS','source_subject_ref':'SECOND-PATIENT','review_ref':'REUSE-REVIEW'})
            self.assertEqual(conflict[0],409,conflict)
            for sql in ('DELETE FROM coordination.case_source_identities',
                        "UPDATE coordination.case_source_identities SET source_subject_ref='FORGED'",
                        "UPDATE coordination.case_source_identities SET status='quarantined'"):
                with self.assertRaises(Exception),self.engine.begin() as c:
                    c.execute(text(sql))
            revoke=f'/v1/patients/{pid}/case-bindings/CASE-LAB-A/revoke'
            self.assertEqual(request(base,revoke,token=TOKEN_A,body={'synthetic':True,'reason':'Withdraw fictional case identity'} )[0],200)
            self.assertEqual(request(base,self.path(pid),token=TOKEN_A)[0],404)
            self.assertEqual(self.import_identity(base,pid,identity,'SECOND-PATIENT')[0],404)


# The parent class supplies setup helpers. Do not silently duplicate its test suite.
for _name in dir(laboratory_fixture.LaboratoryFHIRHTTPTests):
    if _name.startswith('test_') and _name not in InstitutionIdentityTests.__dict__:
        setattr(InstitutionIdentityTests,_name,None)
