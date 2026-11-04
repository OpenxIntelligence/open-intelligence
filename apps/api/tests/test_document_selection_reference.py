"""Immutable manual-passage references; independently authored fixtures only."""
from copy import deepcopy
import hashlib
import unittest

from open_intelligence.document_intake import preview_text
from open_intelligence.patient_registry import PatientRegistryDenied, PatientRegistryError
from oi_api import reviewed_documents as module

PATIENT = 'PAT-' + 'A' * 32
SOURCE = 'SRC-' + 'B' * 32
REVISION = 'ANN-' + 'C' * 32
NEXT = 'ANN-' + 'D' * 32


def document():
    raw = b'Independently fictional record\nMarker pending.\n'
    return dict(source_id=SOURCE,case_id='CASE-ALPHA',document_id='DOC-MANUAL',version=1,
                sha256=hashlib.sha256(raw).hexdigest(),state='current',
                preview=preview_text(raw,'fictional.txt'),revisions=[dict(
                    revision_id=REVISION,revision=1,review_sha256='e'*64,
                    actor='ACTOR-ALPHA',created_at='2026-11-03T10:00:00+00:00',
                    findings=[dict(key='marker',state='pending',quote='Marker pending.',line=2)],
                    classification_origin='user_selected',clinical_review='not_performed')])


class DocumentSelectionReferenceTests(unittest.TestCase):
    def resolve(self, doc=None, revision=REVISION, key='marker'):
        resolver = getattr(module, 'selection_reference', None)
        self.assertTrue(callable(resolver), 'The source owner must resolve an exact saved selection')
        return resolver(document() if doc is None else doc, PATIENT, 'CASE-ALPHA', revision, key)

    def test_exact_text_anchor_retains_human_attribution_and_literal_quote(self):
        result = self.resolve()
        self.assertEqual(result['contract'],'oi.reviewed-document-selection/1')
        self.assertEqual(result['anchor'],dict(
            patient_id=PATIENT,case_id='CASE-ALPHA',source_id=SOURCE,document_id='DOC-MANUAL',
            source_version=1,original_sha256=document()['sha256'],
            extraction_method='utf8-plain-text-v1',extraction_sha256=None,
            annotation_revision_id=REVISION,annotation_revision=1,review_sha256='e'*64,
            selected_by='ACTOR-ALPHA',selected_at='2026-11-03T10:00:00+00:00',
            selection_key='marker',selected_state='pending',quote='Marker pending.',line=2,page=None,
            classification_origin='user_selected',clinical_review='not_performed'))
        self.assertEqual(result['anchor_sha256'],hashlib.sha256(module.canonical(result['anchor']).encode()).hexdigest())
        self.assertEqual(result['selection_state'],'current_unreviewed_selection')
        self.assertFalse(result['clinical_approval'])
        self.assertFalse(result['model_execution'])

    def test_correction_never_retargets_a_previous_revision_or_changes_its_hash(self):
        before=self.resolve();doc=document();new=deepcopy(doc['revisions'][0])
        new.update(revision_id=NEXT,revision=2,review_sha256='f'*64)
        new['findings'][0]['quote']='pending.'
        doc['revisions'].append(new)
        old=self.resolve(doc)
        self.assertEqual(old['anchor'],before['anchor'])
        self.assertEqual(old['anchor_sha256'],before['anchor_sha256'])
        self.assertEqual(old['selection_state'],'selection_reassessment_required')
        self.assertEqual(old['latest_annotation_revision_id'],NEXT)
        current=self.resolve(doc,NEXT)
        self.assertEqual(current['anchor']['quote'],'pending.')
        self.assertNotEqual(current['anchor_sha256'],old['anchor_sha256'])

    def test_amendment_changes_freshness_without_rewriting_old_anchor(self):
        before=self.resolve();doc=document();doc['state']='superseded'
        old=self.resolve(doc)
        self.assertEqual(old['anchor'],before['anchor'])
        self.assertEqual(old['anchor_sha256'],before['anchor_sha256'])
        self.assertEqual(old['selection_state'],'selection_reassessment_required')

    def test_pdf_page_comes_from_the_frozen_selected_line(self):
        doc=document();doc['preview'].update(extraction_method='frozen-pdf-test',extraction_sha256='a'*64)
        doc['preview']['lines'][0]['page']=1;doc['preview']['lines'][1]['page']=2
        result=self.resolve(doc)
        self.assertEqual(result['anchor']['page'],2)
        self.assertEqual(result['anchor']['line'],2)
        self.assertEqual(result['anchor']['extraction_sha256'],'a'*64)

    def test_unknown_revision_or_key_does_not_fall_back_to_current_selection(self):
        for revision,key in [('ANN-'+'0'*32,'marker'),(REVISION,'missing')]:
            with self.subTest(revision=revision,key=key), self.assertRaises(PatientRegistryDenied):
                self.resolve(revision=revision,key=key)

    def test_noncanonical_identifiers_and_wrong_case_are_rejected(self):
        for revision,key in [(REVISION+'\n','marker'),(REVISION,'marker\n'),(None,'marker'),(REVISION,True)]:
            with self.subTest(revision=revision,key=key), self.assertRaises(PatientRegistryError):
                self.resolve(revision=revision,key=key)
        doc=document();doc['case_id']='CASE-BETA'
        with self.assertRaises(PatientRegistryDenied):self.resolve(doc)


if __name__=='__main__':unittest.main()
