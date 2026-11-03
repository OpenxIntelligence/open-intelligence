"""Actual PostgreSQL16 + HTTP source-brief preparation, fictional input only."""
import hashlib
from unittest.mock import patch
from sqlalchemy import text
from oi_api.app import create_app
from http_support import running_server
from test_patients import TOKEN_A,TOKEN_B,request
from test_source_versions import SourceVersionHTTPTests as SourceFixture, ORIGINAL, AMENDED


class SourceBriefPostgresTests(SourceFixture):
    def world(self,base,pid):
        status,model,_=request(base,f'/v1/patients/{pid}/cases/CASE-ALPHA/world-model',token=TOKEN_A)
        self.assertEqual(status,200)
        return model

    def brief(self,base,pid,digest,**kwargs):
        return request(base,f'/v1/patients/{pid}/cases/{kwargs.pop("case","CASE-ALPHA")}/world-model/brief',
            token=kwargs.pop('token',TOKEN_A),body={'synthetic':True,'source_snapshot_sha256':digest,**kwargs})

    def allow(self):
        self.creds[0]['actions'].append('source_brief_export');self.write()

    def test_export_is_independently_authorized_and_read_only(self):
        with running_server(create_app(self.settings)) as base:
            pid=self.setup_case(base);self.ingest(base,pid);digest=self.world(base,pid)['source_snapshot_sha256']
            self.assertEqual(self.brief(base,pid,digest)[0],404)
            self.allow()
            with self.engine.connect() as c:before=c.execute(text('SELECT count(*) FROM identity.identity_domain_events')).scalar_one()
            status,result,headers=self.brief(base,pid,digest)
            self.assertEqual(status,200);self.assertEqual(headers['Cache-Control'],'no-store')
            self.assertEqual(result['source_snapshot_sha256'],digest)
            self.assertEqual(result['body_sha256'],hashlib.sha256(result['body'].encode()).hexdigest())
            self.assertIn('Original line: 8',result['body']);self.assertIn('not-reported',result['body'])
            self.assertFalse(result['clinical_approval'])
            with self.engine.connect() as c:self.assertEqual(before,c.execute(text('SELECT count(*) FROM identity.identity_domain_events')).scalar_one())
            self.creds[0]['actions'].remove('source_read');self.write()
            self.assertEqual(self.brief(base,pid,digest)[0],404)

    def test_correction_refuses_stale_export_and_retains_history_on_restart(self):
        with running_server(create_app(self.settings)) as base:
            pid=self.setup_case(base);self.allow();self.ingest(base,pid)
            first=self.world(base,pid);saved=self.brief(base,pid,first['source_snapshot_sha256'])[1]
            self.ingest(base,pid,AMENDED)
            self.assertEqual(self.brief(base,pid,first['source_snapshot_sha256'])[0],409)
            current=self.world(base,pid);status,new,_=self.brief(base,pid,current['source_snapshot_sha256'])
            self.assertEqual(status,200);self.assertIn('negative',new['body'])
            self.assertIn(first['current_sources'][0]['source_version_id'],new['body'])
            self.assertIn('not-reported',saved['body'])
        with running_server(create_app(self.settings)) as base:
            status,new,_=self.brief(base,pid,current['source_snapshot_sha256']);self.assertEqual(status,200)
            self.assertIn('HISTORICAL SOURCE VERSIONS',new['body'])

    def test_case_actor_binding_and_payload_are_enforced(self):
        with running_server(create_app(self.settings)) as base:
            pid=self.setup_case(base);self.allow();self.ingest(base,pid);digest=self.world(base,pid)['source_snapshot_sha256']
            self.assertEqual(self.brief(base,pid,digest,case='CASE-BETA')[0],404)
            self.assertEqual(self.brief(base,pid,digest,token=TOKEN_B)[0],404)
            for value in [None,True,{},'x'*64,'b'*64+'\n']:
                self.assertEqual(self.brief(base,pid,value)[0],422)
            self.assertEqual(self.brief(base,pid,digest,synthetic=False)[0],422)
            self.assertEqual(self.brief(base,pid,digest,clinical_approval=True)[0],422)
            status,_,_=request(base,f'/v1/patients/{pid}/case-bindings/CASE-ALPHA/revoke',token=TOKEN_A,
                body={'synthetic':True,'reason':'Fictional binding revoked'})
            self.assertEqual(status,200);self.assertEqual(self.brief(base,pid,digest)[0],404)

    def test_permission_and_source_are_rechecked_after_rendering(self):
        from oi_api.source_brief import render_source_brief
        with running_server(create_app(self.settings)) as base:
            pid=self.setup_case(base);self.allow();self.ingest(base,pid);digest=self.world(base,pid)['source_snapshot_sha256']
            def withdraw(model,**kw):
                result=render_source_brief(model,**kw)
                self.creds[0]['actions'].remove('source_brief_export');self.write()
                return result
            with patch('oi_api.patients.render_source_brief',side_effect=withdraw):
                status,body,_=self.brief(base,pid,digest)
            self.assertEqual(status,404);self.assertNotIn('body',body)
            self.allow()
            def amend(model,**kw):
                result=render_source_brief(model,**kw)
                self.assertEqual(self.ingest(base,pid,AMENDED)[0],201)
                return result
            with patch('oi_api.patients.render_source_brief',side_effect=amend):
                status,body,_=self.brief(base,pid,digest)
            self.assertEqual(status,409);self.assertNotIn('body',body)
