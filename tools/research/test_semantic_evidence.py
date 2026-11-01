"""Original fictional fixtures: verify source meaning and evidence attachment."""
import copy
import json
import unittest
import clinical_semantics_probe as sem

PATH = '/diagnoses/0/treatments/0'
START, END = 'days_to_treatment_start', 'days_to_treatment_end'

def case():
    return {'case_id': 'FICTIONAL-TRACE-A', 'index_date': 'Diagnosis',
            'diagnoses': [{'diagnosis_id': 'FICTIONAL-D', 'treatments': [
                {'treatment_or_therapy': 'yes', START: 2, END: 5,
                 'prescribed_dose': 30, 'prescribed_dose_units': 'mg',
                 'treatment_dose': 20, 'treatment_dose_units': 'mg'}]}],
            'follow_ups': [{'days_to_follow_up': 12}]}

class MeaningGuards(unittest.TestCase):
    def test_unrecognized_anchor_cannot_place_treatment(self):
        c = case(); c['index_date'] = 'Made-up anchor'
        self.assertEqual(sem.treatment(c, c['diagnoses'][0]['treatments'][0], PATH)['placement'], 'unplaced')

    def test_calendar_string_is_not_an_index_category(self):
        c = case(); c['index_date'] = '2026-01-01'
        self.assertEqual(sem.followup(c, c['follow_ups'][0], '/follow_ups/0')['placement'], 'unplaced')

    def test_offsets_outside_pinned_schema_are_invalid(self):
        for v in [-32873, 32873, 10**500]:
            with self.subTest(value_category='out-of-range'):
                self.assertEqual(sem.state({'x': v}, 'x', numeric=True)['state'], 'invalid')

    def test_source_boundary_and_zero_remain_valid_numbers(self):
        for v in [-32872, 0, 32872]:
            with self.subTest(v=v):
                self.assertEqual(sem.state({'x': v}, 'x', numeric=True)['state'], 'number')

    def test_prescribed_and_received_dose_units_are_separate(self):
        c = case(); o = c['diagnoses'][0]['treatments'][0]
        o['treatment_dose_units'] = 'mg/m2'
        r = sem.treatment(c, o, PATH)
        self.assertEqual(r.get('prescribed_dose_units', {}).get('raw'), 'mg')
        self.assertEqual(r.get('treatment_dose_units', {}).get('raw'), 'mg/m2')

class EvidenceAttachment(unittest.TestCase):
    def make(self, c=None, path=PATH):
        self.assertTrue(callable(getattr(sem, 'make_claim', None)), 'source-anchored claim construction absent')
        return sem.make_claim(c or case(), path)

    def verify(self, c, claim):
        self.assertTrue(callable(getattr(sem, 'verify_claim', None)), 'claim/source check absent')
        return sem.verify_claim(c, claim)

    def test_exact_source_can_reproduce_claim(self):
        c = case(); claim = self.make(c)
        self.assertTrue(self.verify(c, claim))
        self.assertEqual(claim['source_path'], PATH)
        self.assertEqual(claim['source_case_id'], 'FICTIONAL-TRACE-A')
        self.assertEqual(claim['receipt'], 'reported_yes')

    def test_wrong_case_rejected_even_when_clinical_fields_match(self):
        c = case(); claim = self.make(c); c['case_id'] = 'FICTIONAL-TRACE-B'
        self.assertFalse(self.verify(c, claim))

    def test_amended_source_invalidates_old_claim(self):
        c = case(); claim = self.make(c)
        c['diagnoses'][0]['treatments'][0]['treatment_or_therapy'] = 'no'
        self.assertFalse(self.verify(c, claim))
        self.assertEqual(self.make(c)['receipt'], 'reported_no')
        self.assertEqual(claim['receipt'], 'reported_yes')

    def test_wrong_input_version_rejected_even_if_treatment_unchanged(self):
        c = case(); claim = self.make(c); c['index_date'] = 'Study Enrollment'
        self.assertFalse(self.verify(c, claim))

    def test_forged_positive_assertion_rejected(self):
        c = case(); c['diagnoses'][0]['treatments'][0]['treatment_or_therapy'] = 'no'
        claim = self.make(c); claim['receipt'] = 'reported_yes'
        self.assertFalse(self.verify(c, claim))

    def test_forged_raw_value_rejected(self):
        c = case(); claim = self.make(c); claim['start']['raw'] = 99
        self.assertFalse(self.verify(c, claim))

    def test_wrong_pointer_does_not_resolve_by_guessing(self):
        c = case(); claim = self.make(c); claim['source_path'] = '/diagnoses/9/treatments/0'
        self.assertFalse(self.verify(c, claim))

    def test_negative_index_cannot_select_last_record(self):
        self.assertTrue(callable(getattr(sem, 'make_claim', None)))
        with self.assertRaises(ValueError): sem.make_claim(case(), '/diagnoses/0/treatments/-1')

    def test_unsupported_source_path_rejected(self):
        self.assertTrue(callable(getattr(sem, 'make_claim', None)))
        with self.assertRaises(ValueError): sem.make_claim(case(), '/case_id')

    def test_followup_is_source_assertion_not_encounter(self):
        c = case(); claim = self.make(c, '/follow_ups/0')
        self.assertTrue(self.verify(c, claim))
        self.assertEqual(claim['evidence_kind'], 'registry_followup_assertion')
        self.assertNotIn('resourceType', claim)

    def test_claim_modification_cannot_change_original(self):
        c = case(); before = copy.deepcopy(c); claim = self.make(c)
        claim['start']['raw'] = 888
        self.assertEqual(c, before)

    def test_invalid_claim_is_false_not_exception(self):
        for bad in [None, {}, {'source_path': '/follow_ups/100'}]:
            with self.subTest(claim_type=type(bad).__name__):
                self.assertFalse(self.verify(case(), bad))

    def test_aggregate_verifies_both_source_kinds_without_publishing_ids(self):
        r = sem.audit([case()])
        self.assertEqual(r.get('source_claims_verified'), 2)
        self.assertEqual(r.get('source_claim_verification_failures'), 0)
        self.assertNotIn('FICTIONAL-TRACE-A', json.dumps(r))
        self.assertNotIn('FICTIONAL-D', json.dumps(r))

if __name__ == '__main__': unittest.main()
