"""Real HTTP/PG journey for independently fictional manual record context."""
import unittest
from copy import deepcopy
from unittest.mock import patch

from fastapi.responses import JSONResponse
from sqlalchemy import text

from oi_api.app import create_app
from oi_api.config import Settings
from open_intelligence.postgres_registry import PostgresPatientRegistry
from http_support import running_server
from test_patients import TOKEN_A, TOKEN_B, request
from test_canonical_review_flow import create_question
from test_authored_evidence_postgres import EvidenceFixture
import test_reviewed_documents as documents


class ManualPassageRoutes(unittest.TestCase):
    def test_manual_passages_extend_existing_question_routes(self):
        paths = create_app(Settings.from_env({})).openapi()['paths']
        path = '/v1/patients/{patient_id}/cases/{case_id}/questions/{question_id}/manual-passages'
        self.assertIn(path, paths)
        self.assertEqual(set(paths[path]), {'get', 'post'})


class QuestionManualPassagesHTTPTests(EvidenceFixture):
    basepath = documents.ReviewedDocumentTests.basepath
    upload = documents.ReviewedDocumentTests.upload
    prepared = documents.ReviewedDocumentTests.prepared

    def setup_manual(self, base):
        patient = self.setup_case(base)
        payload = self.prepared(base, patient)
        code, doc, _ = request(base, self.basepath(patient), token=TOKEN_A, body=payload)
        self.assertEqual(code, 201, doc)
        code, source, _ = self.ingest(base, patient)
        self.assertEqual(code, 201, source)
        question, _ = create_question(self, base, patient, source['source_id'])
        path = self.prefix(patient, question) + '/manual-passages'
        code, empty, _ = request(base, path, token=TOKEN_A)
        self.assertEqual(code, 200, empty)
        selection_url = self.basepath(patient)+'/'+doc['source_id']+'/selections/'+doc['annotation_revision_id']+'/marker'
        code, selection, _ = request(base, selection_url, token=TOKEN_A)
        self.assertEqual(code, 200, selection)
        reference = dict(source_id=doc['source_id'], annotation_revision_id=doc['annotation_revision_id'],
                         selection_key='marker', anchor_sha256=selection['anchor_sha256'])
        command = dict(synthetic=True, request_key='PASSAGES-ONE', expected_context_sha256=empty['context_sha256'], references=[reference])
        return patient, question, payload, doc, path, selection, command

    def save(self, base, path, command):
        code, receipt, _ = request(base, path, token=TOKEN_A, body=command)
        self.assertEqual(code, 201, receipt)
        code, packet, headers = request(base, path, token=TOKEN_A)
        self.assertEqual(code, 200, packet)
        self.assertEqual(headers['Cache-Control'], 'no-store')
        return receipt, packet

    def correct(self, base, patient, payload, doc):
        command = dict(synthetic=True,request_key='PASSAGE-CORRECTION',expected_revision_id=doc['annotation_revision_id'],
                       confirmed_case_id='CASE-ALPHA',expected_sha256=payload['expected_sha256'],
                       reason='Select a narrower exact quotation',findings=[dict(key='marker',state='indeterminate',quote='pending.',line=2)])
        code, result, _ = request(base,self.basepath(patient)+'/'+doc['source_id']+'/annotations',token=TOKEN_A,body=command)
        self.assertEqual(code,201,result)
        return result

    def counts(self):
        with self.engine.connect() as db:
            return tuple(db.execute(text('SELECT count(*) FROM '+table)).scalar_one() for table in (
                'investigation.question_passage_revisions', 'investigation.question_evidence_reports', 'identity.identity_domain_events'))

    def test_attach_retry_restart_and_no_assertion_promotion(self):
        with running_server(create_app(self.settings)) as base:
            p,q,_,_,path,selection,command = self.setup_manual(base)
            receipt, packet = self.save(base,path,command)
            self.assertEqual(packet['passages'][0]['anchor'],selection['anchor'])
            self.assertEqual(packet['revision_id'],receipt['revision_id'])
            self.assertEqual(packet['state'],'current_unreviewed')
            self.assertEqual(packet['question_id'],q)
            before = self.counts()
            code, retry, _ = request(base,path,token=TOKEN_A,body=command)
            self.assertEqual(code,200,retry)
            self.assertEqual(retry,receipt|{'duplicate':True})
            self.assertEqual(self.counts()[:2],before[:2])
            assertions=request(base,self.url(p),token=TOKEN_A)[1]['source_reported_assertions']
            self.assertEqual(len(assertions),1)
        with running_server(create_app(self.settings)) as base:
            again=request(base,path,token=TOKEN_A)[1]
            self.assertEqual(again['context_sha256'],packet['context_sha256'])
            self.assertEqual(again['passages'],packet['passages'])
            self.assertNotEqual(again['access_receipt_id'],packet['access_receipt_id'])

    def test_changed_intent_stale_writer_and_foreign_or_forged_reference_fail_closed(self):
        with running_server(create_app(self.settings)) as base:
            _,_,_,_,path,_,command=self.setup_manual(base)
            self.save(base,path,command)
            for body,expected in [(command|{'references':[]},409),
                                  (command|{'request_key':'STALE-WRITER','references':[]},409)]:
                before=self.counts()
                self.assertEqual(request(base,path,token=TOKEN_A,body=body)[0],expected)
                self.assertEqual(self.counts(),before)
            current=request(base,path,token=TOKEN_A)[1]
            for change in [{'anchor_sha256':'0'*64},{'annotation_revision_id':'ANN-'+'0'*32},{'source_id':'SRC-'+'0'*32}]:
                body=command|dict(request_key='FORGED',expected_context_sha256=current['context_sha256'],
                                  references=[command['references'][0]|change])
                before=self.counts()
                self.assertIn(request(base,path,token=TOKEN_A,body=body)[0],(404,409))
                self.assertEqual(self.counts(),before)
            self.assertEqual(request(base,path,token=TOKEN_B)[0],404)
            self.assertEqual(request(base,path.replace('CASE-ALPHA','CASE-BETA'),token=TOKEN_A)[0],404)

    def test_correction_preserves_exact_anchor_retry_and_explicit_clear(self):
        with running_server(create_app(self.settings)) as base:
            p,_,payload,doc,path,selection,command=self.setup_manual(base)
            receipt,packet=self.save(base,path,command)
            self.correct(base,p,payload,doc)
            code,stale,_=request(base,path,token=TOKEN_A)
            self.assertEqual(code,200,stale)
            self.assertEqual(stale['state'],'reassessment_required')
            self.assertEqual(stale['passages'][0]['anchor'],selection['anchor'])
            self.assertNotEqual(stale['context_sha256'],packet['context_sha256'])
            self.assertEqual(request(base,path,token=TOKEN_A,body=command)[1],receipt|{'duplicate':True})
            rejected=command|dict(request_key='STALE-SELECTION',expected_context_sha256=stale['context_sha256'])
            self.assertEqual(request(base,path,token=TOKEN_A,body=rejected)[0],409)
            _,cleared=self.save(base,path,rejected|dict(request_key='CLEAR-PASSAGES',references=[]))
            self.assertEqual(cleared['passages'],[])
            self.assertEqual(cleared['revision'],2)
            with self.engine.connect() as db:
                self.assertEqual(db.execute(text('SELECT count(*) FROM investigation.question_passage_revisions')).scalar_one(),2)

    def test_revocation_after_encoding_or_audit_rolls_back_every_side_effect(self):
        with running_server(create_app(self.settings)) as base:
            _,_,_,_,path,_,command=self.setup_manual(base)
            render=JSONResponse.render
            for phase in ('encoding','audit'):
                self.creds[0]['actions']=list(set(self.creds[0]['actions'])|{'source_original_read'});self.write()
                before=self.counts()
                def revoke():
                    self.creds[0]['actions'].remove('source_original_read');self.write()
                def encode(response,content):
                    result=render(response,content)
                    if isinstance(content,dict) and 'revision_id' in content and 'duplicate' in content: revoke()
                    return result
                append=PostgresPatientRegistry.append_event
                def audit(registry,patient,event,**kwargs):
                    result=append(registry,patient,event,**kwargs)
                    if event=='source.read_authorized': revoke()
                    return result
                with patch.object(JSONResponse,'render',encode) if phase=='encoding' else patch.object(PostgresPatientRegistry,'append_event',audit):
                    code,body,_=request(base,path,token=TOKEN_A,body=command)
                self.assertEqual(code,404,body)
                self.assertEqual(self.counts(),before)

    def test_original_read_is_required_only_when_manual_text_is_disclosed(self):
        with running_server(create_app(self.settings)) as base:
            p,q,_,_,path,_,command=self.setup_manual(base)
            code,evidence,_=self.imported(base,p,q);self.assertEqual(code,201,evidence)
            packet=self.packet(base,p,q)
            code,assessment,_=self.assessed(base,p,q,self.assessment_body(packet,evidence['evidence_id']))
            self.assertEqual(code,201,assessment)

            # Freeze a legacy report before any manual context exists.
            legacy_body=self.report_body(self.packet(base,p,q),[assessment['assessment_id']],key='LEGACY-NO-MANUAL')
            code,legacy,_=self.reported(base,p,q,legacy_body);self.assertEqual(code,201,legacy)
            _,manual=self.save(base,path,command)

            # Removing original-read authority must not hide unrelated evidence
            # metadata or a legacy report that contains no manual quotation.
            self.creds[0]['actions'].remove('source_original_read');self.write()
            packet=self.packet(base,p,q)
            code,old,_=self.read_report(base,p,q,legacy['report_id'])
            self.assertEqual(code,200,old)
            self.assertEqual(old['state'],'historical_reassessment_required')
            self.assertNotIn('manual_passages',old['snapshot'])

            # Direct manual disclosure and creation of a new report that would
            # freeze that text still fail closed under the independent grant.
            self.assertEqual(request(base,path,token=TOKEN_A)[0],404)
            new_body=self.report_body(packet,[assessment['assessment_id']],key='MANUAL-WITHOUT-ORIGINAL')
            new_body['expected_manual_context_sha256']=manual['context_sha256']
            self.assertEqual(self.reported(base,p,q,new_body)[0],404)

    def test_report_freezes_manual_context_and_correction_invalidates_without_rewriting(self):
        with running_server(create_app(self.settings)) as base:
            p,q,payload,doc,path,selection,command=self.setup_manual(base)
            _,context=self.save(base,path,command)
            code,evidence,_=self.imported(base,p,q);self.assertEqual(code,201,evidence)
            packet=self.packet(base,p,q)
            code,assessment,_=self.assessed(base,p,q,self.assessment_body(packet,evidence['evidence_id']))
            self.assertEqual(code,201,assessment)
            body=self.report_body(self.packet(base,p,q),[assessment['assessment_id']])
            self.assertEqual(self.reported(base,p,q,body)[0],409)
            body['expected_manual_context_sha256']=context['context_sha256']
            code,saved,_=self.reported(base,p,q,body);self.assertEqual(code,201,saved)
            code,report,_=self.read_report(base,p,q,saved['report_id']);self.assertEqual(code,200,report)
            frozen=report['snapshot']['manual_passages']
            self.assertEqual(frozen['passages'][0]['anchor'],selection['anchor'])
            self.assertIn('ADDITIONAL MANUAL RECORD CONTEXT',report['body'])
            self.assertIn('Marker pending.',report['body'])
            self.correct(base,p,payload,doc)
            code,old,_=self.read_report(base,p,q,saved['report_id']);self.assertEqual(code,200,old)
            self.assertEqual(old['body'],report['body'])
            self.assertEqual(old['snapshot'],report['snapshot'])
            self.assertEqual(old['state'],'historical_reassessment_required')
            self.assertEqual(self.reported(base,p,q,body)[1],saved|{'duplicate':True})
            self.assertEqual(self.reported(base,p,q,body|{'request_key':'NEW-STALE-REPORT'})[0],409)
            stale=request(base,path,token=TOKEN_A)[1]
            self.save(base,path,command|dict(request_key='REMOVE',expected_context_sha256=stale['context_sha256'],references=[]))
            self.creds[0]['actions'].remove('source_original_read');self.write()
            self.assertEqual(self.read_report(base,p,q,saved['report_id'])[0],404)
