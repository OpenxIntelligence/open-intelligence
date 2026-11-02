"""Hand-authored nonclinical rows and fictional objects; no patient datasets."""
import unittest
from public_evidence_probe import profile_csv, profile_gdc

class ProfileTests(unittest.TestCase):
    def test_csv_counts_actual_rows(self):
        raw=b'Patient ID,FEATURE_A,FEATURE_B\nSYN-PROFILE-A,alpha,9\nSYN-PROFILE-B,beta,0\nSYN-PROFILE-C,gamma,13\n'
        self.assertEqual(profile_csv(raw)['rows'], 3)
        self.assertEqual(profile_csv(raw)['columns'], 3)
    def test_csv_unknown_is_not_negative(self):
        raw=b'Patient ID,FEATURE_A,FEATURE_B\nSYN-PROFILE-A,alpha,9\nSYN-PROFILE-B,Not collected,0\nSYN-PROFILE-C,,13\nSYN-PROFILE-D,delta,1\n'
        r=profile_csv(raw)
        self.assertEqual(r['missing_by_column'].get('FEATURE_A',0), 2)
        self.assertEqual(r['missing_by_column'].get('FEATURE_B',0), 0)
    def test_csv_identifiers_not_in_aggregate_output(self):
        import json
        self.assertNotIn('SYN-PROFILE-A', json.dumps(profile_csv(b'Patient ID,FEATURE_A\nSYN-PROFILE-A,alpha\n')))
    def test_csv_duplicate_identifiers_counted(self):
        self.assertEqual(profile_csv(b'Patient ID,FEATURE_A\nSYN-PROFILE-A,8\nSYN-PROFILE-B,21\nSYN-PROFILE-A,5\n')['duplicate_identifiers'], 1)
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
    def test_gdc_followups_count_root_records_and_case_coverage(self):
        cases = [{'case_id': 'FICTIONAL-A', 'diagnoses': [{}],
                  'follow_ups': [{'follow_up_id': 'F1'}, {'follow_up_id': 'F2'}]},
                 {'case_id': 'FICTIONAL-B', 'diagnoses': [], 'follow_ups': []}]
        result = profile_gdc(cases)
        self.assertEqual(result['follow_ups'], 2)
        self.assertEqual(result['cases_with_followup_records'], 1)

    def test_public_metadata_fetch_helper_remains_available_with_mocked_transport(self):
        import hashlib
        from unittest.mock import patch
        from public_evidence_probe import fetch_bytes
        url = 'https://example.invalid/fictional-publication-metadata'
        payload = b'{"title":"Independently authored metadata fixture"}'
        with patch('public_evidence_probe.urlopen') as opener:
            response = opener.return_value.__enter__.return_value
            response.read.return_value = payload
            response.geturl.return_value = url
            raw, receipt = fetch_bytes(url)
            opener.assert_called_once()
        self.assertEqual(raw, payload)
        self.assertEqual(receipt['sha256'], hashlib.sha256(payload).hexdigest())
        self.assertEqual(receipt['bytes'], len(payload))

if __name__=='__main__': unittest.main(verbosity=2)
