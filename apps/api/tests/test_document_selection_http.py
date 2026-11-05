"""Actual PG/HTTP passage-reference custody; no personal patient inputs."""
from copy import deepcopy
from unittest.mock import patch

from fastapi.responses import JSONResponse
from sqlalchemy import text
from oi_api.app import create_app
from open_intelligence.postgres_registry import PostgresPatientRegistry
from http_support import running_server
from test_patients import request, TOKEN_A, TOKEN_B
from test_source_versions import SourceVersionFixture
import test_reviewed_documents as documents


class DocumentSelectionHTTPTests(SourceVersionFixture):
    basepath=documents.ReviewedDocumentTests.basepath
    upload=documents.ReviewedDocumentTests.upload
    prepared=documents.ReviewedDocumentTests.prepared
    counts=documents.ReviewedDocumentTests.counts

    def saved_selection(self,base):
        patient=self.setup_case(base);payload=self.prepared(base,patient)
        status,saved,_=request(base,self.basepath(patient),token=TOKEN_A,body=payload)
        self.assertEqual(status,201,saved)
        path=self.basepath(patient)+'/'+saved['source_id']
        selected=path+'/selections/'+saved['annotation_revision_id']+'/marker'
        return patient,payload,saved,path,selected

    def test_exact_selection_survives_restart_and_does_not_create_assertions(self):
        with running_server(create_app(self.settings)) as base:
            patient,payload,saved,path,selected=self.saved_selection(base)
            status,first,headers=request(base,selected,token=TOKEN_A)
            self.assertEqual(status,200,first)
            self.assertEqual(headers['Cache-Control'],'no-store')
            self.assertEqual(first['anchor']['quote'],'Marker pending.')
            self.assertEqual(first['anchor']['original_sha256'],payload['expected_sha256'])
            self.assertEqual(first['anchor']['annotation_revision_id'],saved['annotation_revision_id'])
            self.assertEqual(first['anchor']['selected_by'],'ACTOR-ALPHA')
            self.assertEqual(first['anchor']['classification_origin'],'user_selected')
            self.assertFalse(first['clinical_approval'])
            self.assertEqual(request(base,self.url(patient),token=TOKEN_A)[1]['source_reported_assertions'],[])
        with running_server(create_app(self.settings)) as restarted:
            status,again,_=request(restarted,selected,token=TOKEN_A)
            self.assertEqual(status,200,again)
            self.assertEqual(again['anchor'],first['anchor'])
            self.assertEqual(again['anchor_sha256'],first['anchor_sha256'])
            self.assertNotEqual(again['access_receipt_id'],first['access_receipt_id'])

    def test_correction_and_amendment_keep_old_reference_literal_and_historical(self):
        with running_server(create_app(self.settings)) as base:
            patient,payload,saved,path,selected=self.saved_selection(base)
            status,first,_=request(base,selected,token=TOKEN_A);self.assertEqual(status,200,first)
            command=dict(synthetic=True,request_key='REFERENCE-CORRECTION',
                expected_revision_id=saved['annotation_revision_id'],confirmed_case_id='CASE-ALPHA',
                expected_sha256=payload['expected_sha256'],reason='Select a narrower exact quote',
                findings=[dict(key='marker',state='indeterminate',quote='pending.',line=2)])
            status,new,_=request(base,path+'/annotations',token=TOKEN_A,body=command)
            self.assertEqual(status,201,new)
            historical=request(base,selected,token=TOKEN_A)[1]
            self.assertEqual(historical['anchor'],first['anchor'])
            self.assertEqual(historical['anchor_sha256'],first['anchor_sha256'])
            self.assertEqual(historical['selection_state'],'selection_reassessment_required')
            latest=path+'/selections/'+new['annotation_revision_id']+'/marker'
            status,current,_=request(base,latest,token=TOKEN_A);self.assertEqual(status,200,current)
            self.assertEqual(current['anchor']['quote'],'pending.')
            self.assertEqual(current['selection_state'],'current_unreviewed_selection')
            amended=self.prepared(base,patient,documents.RAW+b'Fictional amendment.\r\n',1)
            self.assertEqual(request(base,self.basepath(patient),token=TOKEN_A,body=amended)[0],201)
            old=request(base,latest,token=TOKEN_A)[1]
            self.assertEqual(old['anchor'],current['anchor'])
            self.assertEqual(old['selection_state'],'selection_reassessment_required')

    def test_pdf_uses_frozen_page_and_original_hash_without_reextracting(self):
        raw=documents.text_pdf([['Independently fictional page one'],['Marker pending.']])
        with running_server(create_app(self.settings)) as base:
            patient=self.setup_case(base);upload=self.upload(raw)|{'filename':'fictional.pdf'}
            status,preview,_=request(base,self.basepath(patient)+'/preview',token=TOKEN_A,body=upload)
            self.assertEqual(status,200,preview)
            payload=upload|dict(confirmed_case_id='CASE-ALPHA',expected_sha256=preview['sha256'],
                expected_extraction_sha256=preview['extraction_sha256'],
                metadata=dict(document_id='DOC-PDF',kind='pathology',event_date='2026-01-10',issued_at='2026-01-11',manual_transcription_confirmed=True),
                findings=[dict(key='marker',state='pending',quote='Marker pending.',line=2)])
            status,saved,_=request(base,self.basepath(patient),token=TOKEN_A,body=payload)
            self.assertEqual(status,201,saved)
            path=self.basepath(patient)+'/'+saved['source_id']+'/selections/'+saved['annotation_revision_id']+'/marker'
            with patch('open_intelligence.pdf_intake.extract_pdf',side_effect=AssertionError('Frozen PDF cannot reparse')):
                status,result,_=request(base,path,token=TOKEN_A)
            self.assertEqual(status,200,result)
            self.assertEqual((result['anchor']['page'],result['anchor']['line']),(2,2))
            self.assertEqual(result['anchor']['extraction_sha256'],preview['extraction_sha256'])
            before=self.counts();fetch=PostgresPatientRegistry._fetchone
            def corrupt_rendition(registry,sql,params=()):
                row=fetch(registry,sql,params)
                if row is not None and 'JOIN clinical_source.document_intakes d' in sql:
                    altered=list(row);altered[15]=deepcopy(altered[15])
                    altered[15]['extraction_sha256']='0'*64
                    return tuple(altered)
                return row
            with patch.object(PostgresPatientRegistry,'_fetchone',corrupt_rendition):
                status,body,_=request(base,path,token=TOKEN_A)
            self.assertEqual((status,body),(503,{'detail':'Patient registry unavailable'}))
            self.assertEqual(self.counts(),before)

    def test_corrupted_original_or_annotation_receipt_is_withheld_without_access_event(self):
        # Fault copies of genuine stored-query results; never disable immutable
        # table triggers or represent the database as having emitted these faults.
        with running_server(create_app(self.settings)) as base:
            _,_,_,_,selected=self.saved_selection(base);before=self.counts()
            one=PostgresPatientRegistry._fetchone;many=PostgresPatientRegistry._fetchall
            def corrupt_original(registry,sql,params=()):
                row=one(registry,sql,params)
                if row is not None and 'JOIN clinical_source.document_intakes d' in sql:
                    altered=list(row);altered[5]=bytes(altered[5])+b'altered'
                    return tuple(altered)
                return row
            def corrupt_receipt(registry,sql,params=()):
                rows=many(registry,sql,params)
                if rows and 'FROM clinical_source.annotation_revisions WHERE source_id=' in sql:
                    altered=list(rows[0]);altered[3]=deepcopy(altered[3]);altered[3]['review_sha256']='0'*64
                    return [tuple(altered),*rows[1:]]
                return rows
            for method,fault in [('_fetchone',corrupt_original),('_fetchall',corrupt_receipt)]:
                with self.subTest(method=method),patch.object(PostgresPatientRegistry,method,fault):
                    status,body,_=request(base,selected,token=TOKEN_A)
                self.assertEqual((status,body),(503,{'detail':'Patient registry unavailable'}))
                self.assertEqual(self.counts(),before)
            self.assertEqual(request(base,selected,token=TOKEN_A)[0],200)

    def test_unknown_reference_wrong_tenant_and_independent_denials_leave_no_receipt(self):
        with running_server(create_app(self.settings)) as base:
            patient,_,saved,path,selected=self.saved_selection(base);before=self.counts()
            for missing in [selected.rsplit('/',1)[0]+'/missing',
                            path+'/selections/ANN-'+'0'*32+'/marker',
                            selected.replace('CASE-ALPHA','CASE-BETA')]:
                status,body,_=request(base,missing,token=TOKEN_A)
                self.assertEqual(status,404,body);self.assertNotIn('Marker',str(body))
            self.assertEqual(request(base,selected,token=TOKEN_B)[0],404)
            actions=list(self.creds[0]['actions'])
            for denied in ('patient_read','source_read','source_original_read'):
                self.creds[0]['actions']=[a for a in actions if a!=denied];self.write()
                status,body,_=request(base,selected,token=TOKEN_A)
                self.assertEqual(status,404,body);self.assertNotIn('Marker',str(body))
            self.assertEqual(self.counts(),before)

    def test_encoding_revocation_or_actor_change_withholds_reference_and_rolls_back_receipt(self):
        with running_server(create_app(self.settings)) as base:
            _,_,_,_,selected=self.saved_selection(base);original=deepcopy(self.creds[0]);before=self.counts()
            render=JSONResponse.render
            for mutation in ('revoke','actor'):
                self.creds[0]=deepcopy(original);self.write()
                def alter(response,value):
                    encoded=render(response,value)
                    if isinstance(value,dict) and value.get('contract')=='oi.reviewed-document-selection/1':
                        if mutation=='revoke':self.creds[0]['actions'].remove('source_original_read')
                        else:self.creds[0]['actor']='ACTOR-CHANGED'
                        self.write()
                    return encoded
                with patch.object(JSONResponse,'render',alter):status,body,_=request(base,selected,token=TOKEN_A)
                self.assertEqual(status,404,body);self.assertNotIn('Marker',str(body))
                self.assertEqual(self.counts(),before)

    def test_audit_time_revocation_withholds_reference_and_rolls_back_access_event(self):
        with running_server(create_app(self.settings)) as base:
            _,_,_,_,selected=self.saved_selection(base);before=self.counts()
            append=PostgresPatientRegistry.append_event
            def revoke(registry,patient_id,event_type,**fields):
                value=append(registry,patient_id,event_type,**fields)
                if event_type=='source.document_selection_read_authorized':
                    self.creds[0]['actions'].remove('source_read');self.write()
                return value
            with patch.object(PostgresPatientRegistry,'append_event',revoke):
                status,body,_=request(base,selected,token=TOKEN_A)
            self.assertEqual(status,404,body);self.assertNotIn('Marker',str(body))
            self.assertEqual(self.counts(),before)
