"""Original fictional tests for public-data audit calculations; no patient data."""
import unittest
from public_evidence_probe import profile_csv, profile_gdc

class ProfileTests(unittest.TestCase):
    def test_csv_counts_actual_rows(self):
        self.assertEqual(profile_csv(b'Patient ID,EGFR\nR01-001,Wildtype\nR01-002,Not collected\n')['rows'], 2)
    def test_csv_unknown_is_not_negative(self):
        r=profile_csv(b'Patient ID,EGFR\nR01-001,Wildtype\nR01-002,Not collected\nR01-003,\n')
        self.assertEqual(r['missing_by_column'].get('EGFR',0), 2)
    def test_csv_identifiers_not_in_aggregate_output(self):
        import json
        self.assertNotIn('R01-001', json.dumps(profile_csv(b'Patient ID,EGFR\nR01-001,Wildtype\n')))
    def test_csv_duplicate_identifiers_counted(self):
        self.assertEqual(profile_csv(b'Patient ID,X\nR01-001,1\nR01-001,2\n')['duplicate_identifiers'], 1)
    def test_gdc_empty_has_no_coverage(self):
        self.assertEqual(profile_gdc([])['cases'], 0)
    def test_gdc_case_count_not_joined_rows(self):
        cases=[{'case_id':'fictional','samples':[{'sample_id':'a'},{'sample_id':'b'}],
                'diagnoses':[{'diagnosis_id':'d1'},{'diagnosis_id':'d2'},{'diagnosis_id':'d3'}]}]
        p=profile_gdc(cases)
        self.assertEqual(p['cases'],1)
        self.assertEqual(p['naive_diagnosis_sample_inner_join_rows'],6)
    def test_gdc_missing_treatment_is_unknown(self):
        r=profile_gdc([{'case_id':'fictional','diagnoses':[{}], 'samples':[]}])
        self.assertEqual(r['cases_with_treatment_records'],0)
        self.assertEqual(r['treatments'],0)
        self.assertFalse(r['absence_interpreted_as_no_treatment'])
    def test_gdc_treatment_time_zero_is_present(self):
        r=profile_gdc([{'case_id':'fictional','diagnoses':[{'treatments':[{'treatment_id':'t','days_to_treatment_start':0}]}]}])
        self.assertEqual(r['treatments_with_numeric_start_offset'],1)
    def test_gdc_no_identifiers_in_report(self):
        import json
        r=profile_gdc([{'case_id':'SECRET-FICTIONAL','diagnoses':[], 'samples':[]}])
        self.assertNotIn('SECRET-FICTIONAL', json.dumps(r))
if __name__=='__main__': unittest.main(verbosity=2)
