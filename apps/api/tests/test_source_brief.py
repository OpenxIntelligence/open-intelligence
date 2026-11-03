"""Fictional source-only export: pure rendering and existing HTTP boundary."""
import copy
import hashlib
import unittest
from datetime import datetime, timezone
from unittest.mock import patch

from oi_api.app import create_app
from oi_api.config import Settings
from http_support import running_server
from test_patients import TOKEN_A, request


def fixture():
    source = dict(source_version_id='SRC-'+'A'*32, document_id='DOC-ONE', version=1,
                  source_sha256='a'*64, kind='pathology', specimen_id='SPEC-ONE',
                  event_date='2026-01-10', issued_at='2026-01-11',
                  received_at='2026-01-12T09:00:00+00:00', state='current', supersedes_source_id=None)
    observation = dict(assertion_id=1, finding_key='marker', reported_state='not-reported',
        source_statement='Fictional café <script>literal</script> ``` text.', source_line=8,
        source_version_id=source['source_version_id'], document_id='DOC-ONE', document_version=1,
        source_sha256='a'*64, source_kind='pathology', specimen_id='SPEC-ONE', event_date='2026-01-10',
        issued_at='2026-01-11', received_at=source['received_at'], review_state='not_established', clinical_meaning=None)
    return dict(contract='oi.synthetic-postgres-world-model-sources/1', synthetic=True,
        patient_id='PAT-EXAMPLE-001', case_id='CASE-ALPHA', source_snapshot_sha256='b'*64,
        authority='source_report_only_unreviewed', clinical_interpretation='not_generated',
        clinical_approval=False, review_workflow_connected=False,
        summary=dict(current_sources=1, superseded_sources=0,current_observations=1,
                     unresolved_observations=1,source_disagreements=0),
        current_sources=[source],history=[],observations=[observation],unresolved=[observation.copy()],
        conflicts=[],limitations=['Only independently fictional sources.'])


class SourceBriefTests(unittest.TestCase):
    def render(self, value):
        from oi_api.source_brief import render_source_brief
        return render_source_brief(value, prepared_at='2026-11-02T20:00:00Z')

    def test_literal_source_uncertainty_dates_and_hashes_survive_without_mutation(self):
        value=fixture();original=copy.deepcopy(value);result=self.render(value)
        self.assertEqual(value,original)
        self.assertEqual(result['contract'],'oi.synthetic-source-brief/1')
        self.assertEqual(result['media_type'],'text/plain;charset=utf-8')
        self.assertFalse(result['clinical_approval'])
        self.assertEqual(result['body_sha256'],hashlib.sha256(result['body'].encode()).hexdigest())
        for s in ['Open Intelligence','not-reported','not established','SRC-'+'A'*32,
                  'Original line: 8','2026-01-10','2026-01-11','2026-01-12',
                  value['observations'][0]['source_statement'],'b'*64]:
            self.assertIn(s,result['body'])
        self.assertEqual(result,self.render(value))

    def test_history_is_not_emitted_as_current_finding(self):
        v=fixture();old=copy.deepcopy(v['current_sources'][0]);old.update(source_version_id='SRC-'+'C'*32,
            state='superseded',source_sha256='c'*64)
        v['history']=[old];v['summary']['superseded_sources']=1
        out=self.render(v)['body']
        self.assertIn('HISTORICAL SOURCE VERSIONS',out)
        self.assertIn(old['source_version_id'],out.split('HISTORICAL SOURCE VERSIONS')[1])
        self.assertNotIn(old['source_version_id'],out.split('HISTORICAL SOURCE VERSIONS')[0])

    def test_empty_source_set_does_not_claim_complete_or_reviewed_record(self):
        v=fixture();v.update(current_sources=[],observations=[],unresolved=[])
        v['summary'].update(current_sources=0,current_observations=0,unresolved_observations=0)
        out=self.render(v)['body']
        self.assertIn('No current source-reported observations',out)
        self.assertIn('does not establish a complete medical record',out)

    def test_oversized_output_refused_not_truncated(self):
        from open_intelligence.patient_registry import PatientRegistryError
        v=fixture();v['observations'][0]['source_statement']='x'*65536
        with self.assertRaises(PatientRegistryError):self.render(v)

    def test_api_is_typed_requires_auth_and_does_not_expose_originals(self):
        with running_server(create_app(Settings.from_env({}))) as base:
            url='/v1/patients/PAT-EXAMPLE-001/cases/CASE-ALPHA/world-model/brief'
            status,body,_=request(base,url,body={'synthetic':True,'source_snapshot_sha256':'b'*64})
            self.assertEqual(status,401)
            _,schema,_=request(base,'/v1/openapi.json')
            op=schema['paths']['/v1/patients/{patient_id}/cases/{case_id}/world-model/brief']['post']
            self.assertEqual(op['operationId'],'prepare_source_brief_v1')
            self.assertEqual(op['security'],[{'SyntheticFixture':[]}])


if __name__=='__main__':unittest.main()
