"""Literal provenance and legacy-compatible report snapshot controls."""
from copy import deepcopy
import json
import unittest
from unittest.mock import Mock, patch

from pydantic import ValidationError
from oi_api.question_passage_contracts import ManualContext, ReplaceQuestionPassages, context_hash
from oi_api.reviewed_documents import selection_reference, fingerprint
from oi_api.authored_evidence_contracts import checked_report_snapshot
from oi_api.evidence_report import render_evidence_report
from open_intelligence.patient_registry import PatientRegistryError
from open_intelligence.postgres_registry import PostgresPatientRegistry
from oi_api.question_passages import QuestionPassages
from oi_api.sources import PostgresSourceVersions
from test_document_selection_reference import document, REVISION
from test_authored_evidence_contracts import snapshot


def manual_snapshot():
    snap=snapshot();q=snap['question']
    d=document();d['case_id']=q['case_id']
    resolved=selection_reference(d,q['patient_id'],q['case_id'],REVISION,'marker')
    passage={k:resolved[k] for k in ('anchor','anchor_sha256','source_state','latest_annotation_revision_id','selection_state')}
    c=dict(contract='oi.question-manual-passages/1',patient_id=q['patient_id'],case_id=q['case_id'],question_id=q['question_id'],
           revision_id='PASSAGES-'+'E'*32,revision=1,attached_by='ACTOR-ALPHA',attached_at='2026-11-03T11:00:00+00:00',
           passages=[passage],state='current_unreviewed')
    c['context_sha256']=context_hash(c)
    return snap|{'manual_passages':c}


class ManualContextContracts(unittest.TestCase):
    def test_only_known_legacy_schemas_may_lack_manual_metadata(self):
        for revision in ('0010_authored_evidence_origin','0011_evidence_convergence','0012_reviewed_documents','0013_document_image_convergence'):
            registry=Mock()
            registry._transaction_active=True
            registry._fetchone.return_value=(None,)
            registry._fetchall.return_value=[(revision,)]
            self.assertIsNone(QuestionPassages(registry).metadata_locked({})['revision_id'])
            with self.assertRaisesRegex(RuntimeError,'owner unavailable'):
                QuestionPassages(registry).metadata_locked({},revision_id='PASSAGES-'+'A'*32)
        for revisions in ([], [('0014_question_passages',)], [('0015_manual_report_context',)],
                          [('unknown_revision',)], [('0010_authored_evidence_origin',),('0010_question_evidence',)]):
            registry=Mock()
            registry._transaction_active=True
            registry._fetchone.return_value=(None,)
            registry._fetchall.return_value=revisions
            with self.assertRaisesRegex(RuntimeError,'owner unavailable'):
                QuestionPassages(registry).metadata_locked({})


    def test_empty_manual_read_obeys_the_actual_primitive_event_contract(self):
        db=Mock(autocommit=False)
        registry=PostgresPatientRegistry(db)
        registry._fetchone=Mock(return_value=('QUESTION-'+'A'*32,))
        registry._fetchall=Mock(return_value=[])
        registry.require_patient=Mock()
        registry._execute=Mock()
        def source_read(owner, patient, case, **kwargs):
            return kwargs['prepare_response']({'access_receipt_id':'ACCESS-'+'B'*32})
        with patch.object(PostgresSourceVersions,'list_locked',source_read):
            result=QuestionPassages(registry).perform('PAT-FICTIONAL','CASE-ALPHA','QUESTION-'+'A'*32,
                organization='ORG-FICTIONAL',actor='ACTOR-FICTIONAL',purpose='operations',
                recheck_authority=lambda original:None,prepare_response=lambda result:result)
        self.assertEqual(result['passages'],[])
        details=json.loads(registry._execute.call_args.args[1][2])
        self.assertEqual(details['reference_count'],0)
        self.assertEqual(details['references_sha256'],fingerprint([]))
        db.commit.assert_called_once();db.rollback.assert_not_called()

    def test_manual_report_preserves_distinct_authority_and_exact_anchor(self):
        snap=manual_snapshot()
        self.assertEqual(checked_report_snapshot(snap),snap)
        body=render_evidence_report(snap,renderer='oi.h1-evidence-text/3')
        self.assertIn('ADDITIONAL MANUAL RECORD CONTEXT',body)
        self.assertIn('Exact manual quotation: "Marker pending."',body)
        self.assertIn('physical page not applicable',body)
        self.assertIn('metadata/ml_use: unknown',body)
        for renderer in ('oi.h1-evidence-text/1','oi.h1-evidence-text/2'):
            with self.assertRaises(PatientRegistryError): render_evidence_report(snap,renderer=renderer)
        with self.assertRaises(PatientRegistryError): render_evidence_report(snapshot(),renderer='oi.h1-evidence-text/3')

    def test_false_scope_freshness_or_annotation_shape_is_rejected_even_when_rehashed(self):
        mutations=[lambda c:c.update(patient_id='PAT-OTHER'),
                   lambda c:c['passages'][0]['anchor'].update(classification_origin='source_authored'),
                   lambda c:c['passages'][0]['anchor'].update(clinical_review='approved'),
                   lambda c:c['passages'][0]['anchor'].update(line=True),
                   lambda c:c['passages'][0]['anchor'].update(page=1),
                   lambda c:c['passages'][0]['anchor'].update(selected_at='2026-11-03T12:00:00+00:99'),
                   lambda c:c['passages'][0].update(selection_state='selection_reassessment_required'),
                   lambda c:c.update(revision=True),lambda c:c.update(state='reassessment_required'),
                   lambda c:c['passages'].append(deepcopy(c['passages'][0]))]
        for mutate in mutations:
            s=manual_snapshot();c=s['manual_passages'];mutate(c)
            for p in c['passages']:p['anchor_sha256']=fingerprint(p['anchor'])
            c['context_sha256']=context_hash(c)
            with self.subTest(context=c),self.assertRaises(ValidationError): checked_report_snapshot(s)

    def test_hashes_and_distinct_reference_commands_are_required(self):
        c=manual_snapshot()['manual_passages']
        c['passages'][0]['anchor']['quote']='Invented replacement'
        with self.assertRaises(ValidationError): ManualContext(**c)
        a=c['passages'][0]['anchor']
        ref={k:a[k] for k in ('source_id','annotation_revision_id','selection_key')}|{'anchor_sha256':'a'*64}
        command=dict(synthetic=True,request_key='MANUAL-ONE',expected_context_sha256='b'*64,references=[ref,ref])
        with self.assertRaises(ValidationError): ReplaceQuestionPassages(**command)
        command['references']=[ref];command['synthetic']=1
        with self.assertRaises(ValidationError): ReplaceQuestionPassages(**command)
