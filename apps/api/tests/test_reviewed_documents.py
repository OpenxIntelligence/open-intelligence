"""Real HTTP/PG custody and revision tests; independently fictional material."""
import base64
from copy import deepcopy
from unittest.mock import patch
from pathlib import Path
import sys
from urllib.request import Request, ProxyHandler, build_opener

from fastapi.responses import JSONResponse
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError
from oi_api.app import create_app
from http_support import running_server
from test_patients import request, TOKEN_A, TOKEN_B
from test_source_versions import SourceVersionFixture
sys.path.insert(0,str(Path(__file__).resolve().parents[3]/'tests'))
from pdf_fixtures import text_pdf

RAW = b'\xef\xbb\xbfIndependently fictional document\r\nMarker pending.\r\nSecond passage.\r\n'


class ReviewedDocumentTests(SourceVersionFixture):
    def test_pdf_frozen_page_anchors_corrections_and_exact_binary_download(self):
        raw=text_pdf([['Independently fictional page one'],['Marker pending.','Second passage.']])
        with running_server(create_app(self.settings)) as base:
            p=self.setup_case(base);upload=self.upload(raw)|{'filename':'fictional.pdf'}
            status,preview,_=request(base,self.basepath(p)+'/preview',token=TOKEN_A,body=upload)
            self.assertEqual(status,200,preview)
            payload=upload|dict(confirmed_case_id='CASE-ALPHA',expected_sha256=preview['sha256'],
                expected_extraction_sha256=preview['extraction_sha256'],
                metadata=dict(document_id='DOC-PDF',kind='pathology',event_date='2026-01-10',issued_at='2026-01-11',manual_transcription_confirmed=True),
                findings=[dict(key='marker',state='pending',quote='Marker pending.',line=2)])
            status,saved,_=request(base,self.basepath(p),token=TOKEN_A,body=payload)
            self.assertEqual(status,201,saved)
            path=self.basepath(p)+'/'+saved['source_id']
            with patch('open_intelligence.pdf_intake.extract_pdf',side_effect=AssertionError('Saved PDF must not reparse')):
                doc=request(base,path,token=TOKEN_A)[1]
                self.assertEqual(doc['preview']['lines'][1]['page'],2)
                command=dict(synthetic=True,request_key='PDF-CORRECTION',expected_revision_id=saved['annotation_revision_id'],
                    confirmed_case_id='CASE-ALPHA',expected_sha256=preview['sha256'],expected_extraction_sha256=preview['extraction_sha256'],
                    reason='Correct the passage',findings=[dict(key='second',state='reported',quote='Second passage.',line=3)])
                self.assertEqual(request(base,path+'/annotations',token=TOKEN_A,body=command)[0],201)
                req=Request(base+path+'/original',headers={'Authorization':'Bearer '+TOKEN_A})
                with build_opener(ProxyHandler({})).open(req) as response:
                    self.assertEqual(response.read(),raw)
                    self.assertEqual(response.headers['X-Content-SHA256'],preview['sha256'])
                    self.assertEqual(response.headers['Cache-Control'],'no-store')

    def basepath(self, patient):
        return self.url(patient).removesuffix('/sources') + '/documents'

    def upload(self, raw=RAW):
        return dict(synthetic=True,filename='fictional.txt',original_base64=base64.b64encode(raw).decode())

    def prepared(self, base, patient, raw=RAW, amends=None):
        payload=self.upload(raw)
        status,preview,_=request(base,self.basepath(patient)+'/preview',token=TOKEN_A,body=payload)
        self.assertEqual(status,200,preview)
        payload.update(confirmed_case_id='CASE-ALPHA',expected_sha256=preview['sha256'],
            metadata=dict(document_id='DOC-MANUAL',kind='pathology',event_date='2026-01-10',
                          issued_at='2026-01-11',manual_transcription_confirmed=True),
            findings=[dict(key='marker',state='pending',quote='Marker pending.',line=2)])
        if amends: payload['metadata']['amends_version']=amends
        return payload

    def counts(self):
        with self.engine.connect() as c:
            return tuple(c.execute(text('SELECT count(*) FROM '+table)).scalar_one() for table in (
                'clinical_source.source_versions','clinical_source.document_intakes',
                'clinical_source.annotation_revisions','identity.identity_domain_events'))

    def test_preview_has_no_effects_and_save_preserves_bytes_and_manual_origin(self):
        with running_server(create_app(self.settings)) as base:
            p=self.setup_case(base); before=self.counts(); payload=self.prepared(base,p)
            self.assertEqual(self.counts(),before)
            status,saved,_=request(base,self.basepath(p),token=TOKEN_A,body=payload)
            self.assertEqual(status,201,saved)
            path=self.basepath(p)+'/'+saved['source_id']
            status,doc,_=request(base,path,token=TOKEN_A)
            self.assertEqual(status,200,doc)
            self.assertEqual(doc['preview']['text'],RAW.decode())
            self.assertEqual(doc['revisions'][0]['classification_origin'],'user_selected')
            self.assertEqual(doc['revisions'][0]['clinical_review'],'not_performed')
            self.assertEqual(request(base,self.basepath(p),token=TOKEN_A,body=payload)[0],200)
            self.assertEqual(self.counts()[:3],(1,1,1))
            # These manual states cannot appear as source-authored observations.
            index=request(base,self.url(p),token=TOKEN_A)[1]
            self.assertEqual(index['source_reported_assertions'],[])
            self.assertEqual(request(base,path,token=TOKEN_B)[0],404)
            altered=deepcopy(payload);altered['findings'][0]['state']='negative'
            self.assertEqual(request(base,self.basepath(p),token=TOKEN_A,body=altered)[0],409)

    def test_corrected_selection_is_immutable_idempotent_and_stale_edit_fails(self):
        with running_server(create_app(self.settings)) as base:
            p=self.setup_case(base);payload=self.prepared(base,p)
            saved=request(base,self.basepath(p),token=TOKEN_A,body=payload)[1]
            path=self.basepath(p)+'/'+saved['source_id']
            command=dict(synthetic=True,request_key='CORRECT-ONE',expected_revision_id=saved['annotation_revision_id'],
                         confirmed_case_id='CASE-ALPHA',expected_sha256=payload['expected_sha256'],
                         reason='Correct selected passage',findings=[dict(key='passage',state='reported',quote='Second passage.',line=3)])
            status,revision,_=request(base,path+'/annotations',token=TOKEN_A,body=command)
            self.assertEqual(status,201,revision)
            status,retry,_=request(base,path+'/annotations',token=TOKEN_A,body=command)
            self.assertEqual(status,200,retry);self.assertEqual(retry['annotation_revision_id'],revision['annotation_revision_id'])
            self.assertEqual(request(base,path+'/annotations',token=TOKEN_A,body=command|{'request_key':'OTHER-KEY'})[0],409)
            doc=request(base,path,token=TOKEN_A)[1]
            self.assertEqual([r['revision'] for r in doc['revisions']],[1,2])
            self.assertEqual(doc['revisions'][0]['findings'],payload['findings'])
            # Catch outside the transaction so a rejected mutation rolls back;
            # pg8000 correctly refuses to commit an already failed transaction.
            with self.assertRaisesRegex(DBAPIError, 'OI-IDENTITY-HISTORY-IMMUTABLE'):
                with self.engine.begin() as c:
                    c.execute(text("UPDATE clinical_source.annotation_revisions SET reason='rewrite'"))
            self.assertEqual(request(base,path,token=TOKEN_A)[1]['revisions'],doc['revisions'])

    def test_amendment_preserves_historical_original_and_correction_history(self):
        with running_server(create_app(self.settings)) as base:
            p=self.setup_case(base); first=self.prepared(base,p)
            a=request(base,self.basepath(p),token=TOKEN_A,body=first)[1]
            second=self.prepared(base,p,RAW+b'Fictional amendment.\r\n',1)
            status,b,_=request(base,self.basepath(p),token=TOKEN_A,body=second)
            self.assertEqual(status,201,b);self.assertEqual(b['version'],2)
            current_path = self.basepath(p) + "/" + b["source_id"]
            status, current, _ = request(base, current_path, token=TOKEN_A)
            self.assertEqual(status, 200, current)
            self.assertEqual((current["version"], current["state"]), (2, "current"))
            self.assertEqual(current["preview"]["text"], (RAW + b"Fictional amendment.\r\n").decode())
            req = Request(base + current_path + "/original",
                          headers={"Authorization": "Bearer " + TOKEN_A})
            with build_opener(ProxyHandler({})).open(req) as response:
                self.assertEqual(response.read(), RAW + b"Fictional amendment.\r\n")
            status, retry, _ = request(base, self.basepath(p), token=TOKEN_A, body=second)
            self.assertEqual((status, retry), (200, {**b, "duplicate": True}))
            old=request(base,self.basepath(p)+'/'+a['source_id'],token=TOKEN_A)[1]
            self.assertEqual(old['state'],'superseded');self.assertEqual(old['preview']['text'],RAW.decode())
            self.assertEqual(request(base,self.basepath(p),token=TOKEN_A,body=first)[0],200)

    def test_final_encoding_revocation_rolls_back_import(self):
        with running_server(create_app(self.settings)) as base:
            p=self.setup_case(base);payload=self.prepared(base,p);before=self.counts()
            render=JSONResponse.render
            def revoke(response,value):
                encoded=render(response,value)
                if isinstance(value,dict) and value.get('annotation_revision_id'):
                    self.creds[0]['actions'].remove('source_import');self.write()
                return encoded
            with patch.object(JSONResponse,'render',revoke):
                status,body,_=request(base,self.basepath(p),token=TOKEN_A,body=payload)
            self.assertEqual(status,404,body);self.assertEqual(self.counts(),before)

    def test_forged_quote_wrong_confirmation_and_mixed_format_amendment_are_denied(self):
        with running_server(create_app(self.settings)) as base:
            p=self.setup_case(base);payload=self.prepared(base,p);before=self.counts()
            for altered in (payload|{'confirmed_case_id':'CASE-OTHER'},payload|{'expected_sha256':'0'*64},
                            payload|{'findings':[dict(key='bad',state='reported',quote='Invented',line=2)]}):
                self.assertEqual(request(base,self.basepath(p),token=TOKEN_A,body=altered)[0],422)
            self.assertEqual(self.counts(),before)
            self.assertEqual(self.ingest(base,p)[0],201)
            mixed=deepcopy(payload);mixed['metadata']['document_id']='DOC-ONE';mixed['metadata']['amends_version']=1
            self.assertEqual(request(base,self.basepath(p),token=TOKEN_A,body=mixed)[0],409)

    def test_original_encoding_revocation_withholds_binary_and_does_not_add_receipt(self):
        from fastapi import Response
        from urllib.error import HTTPError
        with running_server(create_app(self.settings)) as base:
            p=self.setup_case(base);payload=self.prepared(base,p)
            saved=request(base,self.basepath(p),token=TOKEN_A,body=payload)[1]
            before=self.counts();render=Response.render
            def revoke(response,value):
                encoded=render(response,value)
                if value==RAW:
                    self.creds[0]['actions'].remove('source_original_read');self.write()
                return encoded
            req=Request(base+self.basepath(p)+'/'+saved['source_id']+'/original',headers={'Authorization':'Bearer '+TOKEN_A})
            with patch.object(Response,'render',revoke), self.assertRaises(HTTPError) as caught:
                build_opener(ProxyHandler({})).open(req)
            self.assertEqual(caught.exception.code,404)
            self.assertNotIn(b'Marker',caught.exception.read());caught.exception.close()
            self.assertEqual(self.counts(),before)

    def test_reviewed_question_requires_separate_grants_and_preserves_historical_anchor(self):
        from alembic.util.exc import CommandError
        from oi_api.migrate import migrate
        with running_server(create_app(self.settings)) as base:
            patient=self.setup_case(base)
            saved=request(base,self.basepath(patient),token=TOKEN_A,body=self.prepared(base,patient))[1]
            path=self.basepath(patient)+'/'+saved['source_id']
            rev=saved['annotation_revision_id']
            selected=request(base,path+'/selections/'+rev+'/marker',token=TOKEN_A)[1]
            command=dict(synthetic=True,request_key='MANUAL-QUESTION-ONE',revision_id=rev,
                         selection_key='marker',anchor_sha256=selected['anchor_sha256'],
                         question='Which fictional report describes the pending marker?')
            endpoint=path+'/questions'
            self.assertEqual(request(base,endpoint,token=TOKEN_A,body=command)[0],404)
            self.creds[0]['actions'].append('question_create');self.write()
            status,receipt,_=request(base,endpoint,token=TOKEN_A,body=command)
            self.assertEqual(status,201,receipt)
            self.assertEqual(request(base,endpoint,token=TOKEN_A)[0],404)
            self.creds[0]['actions'].append('question_read');self.write()
            self.assertEqual(request(base,endpoint,token=TOKEN_B)[0],404)
            search = endpoint + '/' + receipt['question_id'] + '/evidence-search'
            query = dict(synthetic=True, query='continuity')
            self.assertEqual(request(base, search, token=TOKEN_A, body=query)[0], 404)
            self.creds[0]['actions'].append('evidence_read'); self.write()
            from oi_api.database import Database
            from oi_api.evidence_catalog import seed_fictional_records, fictional_records
            from open_intelligence.postgres_registry import PostgresPatientRegistry
            with Database(self.settings).registry_connection() as connection:
                seed_fictional_records(PostgresPatientRegistry(connection, lambda *args: False),
                                      fictional_records(), recorded_by='FIXTURE-AUTHOR')
            code, results, _ = request(base, search, token=TOKEN_A, body=query)
            self.assertEqual(code, 200, results)
            self.assertEqual(results['question_id'], receipt['question_id'])
            self.assertIn('FICT-RECORD-CONTINUITY@1', [row['citation'] for row in results['records']])
            self.assertEqual(results['source_context_state'], 'current_unreviewed_question')
            self.assertEqual(request(base, search, token=TOKEN_B, body=query)[0], 404)
            from oi_api.reviewed_documents import fingerprint
            links_path = search.replace('evidence-search', 'evidence-links')
            record = next(row for row in results['records'] if row['citation']=='FICT-RECORD-CONTINUITY@1')
            link = dict(synthetic=True, request_key='PASSAGE-CITATION-ONE',
                        citation=record['citation'], expected_metadata_sha256=record['metadata_sha256'],
                        source_snapshot_contract='oi.reviewed-document-selection/1',
                        expected_source_snapshot_sha256=selected['anchor_sha256'],
                        expected_preflight_sha256=fingerprint([selected['anchor_sha256'], command['question']]))
            self.assertEqual(request(base, links_path, token=TOKEN_A, body=link)[0], 404)
            self.creds[0]['actions'].append('evidence_link'); self.write()
            code, link_receipt, _ = request(base, links_path, token=TOKEN_A, body=link)
            self.assertEqual(code, 201, link_receipt)
            self.assertEqual(request(base, links_path, token=TOKEN_A, body=link)[1],
                             {**link_receipt, 'duplicate': True})
            self.assertEqual(request(base, links_path, token=TOKEN_A, body={**link,'citation':'FICT-OTHER@1'})[0],409)
            self.assertEqual(request(base, links_path, token=TOKEN_A)[1]['links'][0]['record']['citation'],record['citation'])
            with self.assertRaises(CommandError):
                migrate(self.admin,'downgrade','0019_reviewed_questions')
            with self.assertRaises(CommandError):
                migrate(self.admin,'downgrade','0018_laboratory_questions')
            with self.assertRaisesRegex(DBAPIError,'OI-LAB-QUESTION-ANCHOR-CONTRACT'), self.engine.begin() as conn:
                conn.execute(text("INSERT INTO investigation.laboratory_question_anchors(question_id,source_id,observation_reference) VALUES (:qid,:sid,'Observation/OTHER')"),
                             dict(qid=receipt['question_id'],sid=saved['source_id']))
            for statement in ('DELETE FROM investigation.reviewed_question_anchors',
                              'UPDATE investigation.reviewed_question_anchors SET manual_key=manual_key'):
                with self.assertRaises(DBAPIError), self.engine.begin() as conn:
                    conn.execute(text(statement))
            correct=dict(synthetic=True,request_key='MANUAL-CORRECTION',expected_revision_id=rev,
                         confirmed_case_id='CASE-ALPHA',expected_sha256=selected['anchor']['original_sha256'],
                         reason='Select a different fictional passage',
                         findings=[dict(key='next',state='reported',quote='Second passage.',line=3)])
            self.assertEqual(request(base,path+'/annotations',token=TOKEN_A,body=correct)[0],201)
            self.assertEqual(request(base,endpoint,token=TOKEN_A,body=command)[1],dict(question_id=receipt['question_id'],duplicate=True))
            self.assertEqual(request(base,endpoint,token=TOKEN_A,body={**command,'request_key':'STALE-NEW'})[0],409)
            status,packet,_=request(base,endpoint,token=TOKEN_A)
            self.assertEqual(status,200)
            question,=packet['questions']
            self.assertEqual(question['selection']['anchor'],selected['anchor'])
            self.assertEqual(question['selection']['selection_state'],'selection_reassessment_required')
            self.assertEqual(request(base, search, token=TOKEN_A, body=query)[1]['source_context_state'],
                             'source_reassessment_required')
            self.assertEqual(request(base, links_path, token=TOKEN_A, body={**link,'request_key':'STALE-CITATION'})[0],409)
            self.assertEqual(request(base, links_path, token=TOKEN_A, body=link)[1],
                             {**link_receipt, 'duplicate': True})
            from oi_api.evidence_catalog import append_rights_decision
            with Database(self.settings).registry_connection() as connection:
                append_rights_decision(PostgresPatientRegistry(connection, lambda *args: False),
                    'FICT-RECORD-CONTINUITY','1', recorded_by='FIXTURE-AUTHOR',
                    permissions={'metadata':{'store':'allowed','display':'allowed'}},
                    revoked=True, superseded=False, reason='Fictional permission withdrawal')
            hidden = request(base, links_path, token=TOKEN_A)[1]
            self.assertEqual(hidden['source_context_state'], 'source_reassessment_required')
            self.assertEqual(hidden['links'][0]['status'], 'rights_restricted')
            self.assertIsNone(hidden['links'][0]['record'])
            self.creds[0]['actions'].remove('source_original_read');self.write()
            self.assertEqual(request(base,endpoint,token=TOKEN_A)[0],404)
            self.assertEqual(request(base,endpoint,token=TOKEN_A,body=command)[0],404)
            self.assertEqual(request(base, search, token=TOKEN_A, body=query)[0], 404)
            self.assertEqual(request(base, links_path, token=TOKEN_A)[0], 404)
