"""Hand-derived fictional cases; no upstream patient records or model calls."""
import copy
import json
import unittest
from clinical_semantics_probe import state, treatment, followup, audit

BASE = {'case_id': 'FICTIONAL-A', 'index_date': 'Diagnosis'}
START = 'days_to_treatment_start'
END = 'days_to_treatment_end'
PATH = '/diagnoses/0/treatments/0'

class SemanticTests(unittest.TestCase):
    def test_absent_null_and_not_reported_are_distinct(self):
        self.assertEqual(state({}, 'x')['state'], 'absent')
        self.assertEqual(state({'x': None}, 'x')['state'], 'null')
        self.assertEqual(state({'x': 'Not Reported'}, 'x')['state'], 'not_reported')

    def test_unknown_not_applicable_and_empty_are_distinct(self):
        for v, wanted in [('Unknown', 'unknown'), ('Not Applicable', 'not_applicable'), ('', 'empty')]:
            with self.subTest(v=v): self.assertEqual(state({'x': v}, 'x')['state'], wanted)

    def test_original_value_is_preserved(self):
        self.assertEqual(state({'x': ' UNKNOWN '}, 'x')['raw'], ' UNKNOWN ')

    def test_zero_negative_and_integral_float_are_valid_offsets(self):
        for v in [0, -7, 2.0]:
            with self.subTest(v=v): self.assertEqual(state({'x': v}, 'x', numeric=True)['state'], 'number')

    def test_boolean_nan_infinity_and_fraction_are_not_day_counts(self):
        for v in [False, True, float('nan'), float('inf'), 0.5]:
            with self.subTest(v=repr(v)): self.assertEqual(state({'x': v}, 'x', numeric=True)['state'], 'invalid')

    def test_numeric_string_is_not_silently_coerced(self):
        self.assertEqual(state({'x': '12'}, 'x', numeric=True)['state'], 'unparsed')

    def test_type_and_intent_do_not_establish_receipt(self):
        r = treatment(BASE, {'treatment_type': 'Chemotherapy', 'treatment_intent_type': 'Cure'}, PATH)
        self.assertEqual(r['receipt'], 'absent')
        self.assertEqual(r['placement'], 'not_positive')

    def test_no_with_drug_and_dates_remains_source_reported_no(self):
        r = treatment(BASE, {'treatment_type': 'Chemotherapy', 'therapeutic_agents': 'FICTIONAL-DRUG',
                            'treatment_or_therapy': 'no', START: 1, END: 2}, PATH)
        self.assertEqual(r['receipt'], 'reported_no')
        self.assertEqual(r['placement'], 'not_positive')

    def test_yes_with_complete_relative_interval_is_not_administration(self):
        r = treatment(BASE, {'treatment_or_therapy': 'yes', START: 0, END: 5}, PATH)
        self.assertEqual(r['placement'], 'relative_interval')
        self.assertEqual(r['evidence_kind'], 'registry_treatment_assertion')
        self.assertNotIn('resourceType', r)
        self.assertNotIn('calendar_start', r)

    def test_yes_without_start_is_undated_not_day_zero(self):
        r = treatment(BASE, {'treatment_or_therapy': 'yes', END: 5}, PATH)
        self.assertEqual(r['placement'], 'unplaced')
        self.assertEqual(r['start']['state'], 'absent')

    def test_yes_without_end_has_open_end_not_known_completion(self):
        r = treatment(BASE, {'treatment_or_therapy': 'yes', START: 5}, PATH)
        self.assertEqual(r['placement'], 'relative_start_only')
        self.assertEqual(r['end']['state'], 'absent')

    def test_unknown_anchor_blocks_qualified_placement(self):
        for case in [{'case_id': 'F'}, {'case_id': 'F', 'index_date': 'Unknown'}]:
            with self.subTest(case=case):
                self.assertEqual(treatment(case, {'treatment_or_therapy': 'yes', START: 1}, PATH)['placement'], 'unplaced')

    def test_end_before_start_is_not_swapped(self):
        r = treatment(BASE, {'treatment_or_therapy': 'yes', START: 10, END: 5}, PATH)
        self.assertEqual(r['placement'], 'held_reversed_interval')
        self.assertEqual(r['start']['raw'], 10)
        self.assertEqual(r['end']['raw'], 5)

    def test_invalid_end_is_not_treated_as_open_end(self):
        self.assertEqual(treatment(BASE, {'treatment_or_therapy': 'yes', START: 1, END: True}, PATH)['placement'], 'held_invalid_time')

    def test_unrecognized_receipt_is_not_affirmative(self):
        self.assertEqual(treatment(BASE, {'treatment_or_therapy': 'probably'}, PATH)['receipt'], 'unrecognized')

    def test_workflow_state_released_is_not_treatment_completed(self):
        self.assertEqual(treatment(BASE, {'state': 'released', 'treatment_type': 'Radiation'}, PATH)['receipt'], 'absent')

    def test_doses_are_distinct_and_no_prescribed_to_delivered_fallback(self):
        r = treatment(BASE, {'prescribed_dose': 20, 'prescribed_dose_units': 'mg'}, PATH)
        self.assertEqual(r['prescribed_dose']['raw'], 20)
        self.assertEqual(r['treatment_dose']['state'], 'absent')

    def test_source_pointer_and_anchor_basis_are_retained(self):
        r = treatment(BASE, {'treatment_or_therapy': 'yes', START: -3}, PATH)
        self.assertEqual(r['source_path'], PATH)
        self.assertEqual(r['start']['source_field'], START)
        self.assertEqual(r['anchor']['raw'], 'Diagnosis')

    def test_followup_without_offset_does_not_use_created_datetime(self):
        r = followup(BASE, {'created_datetime': '2024-01-01T00:00:00Z'}, '/follow_ups/0')
        self.assertEqual(r['placement'], 'unplaced')
        self.assertEqual(r['time']['state'], 'absent')

    def test_followup_with_zero_remains_relative_report_not_encounter(self):
        r = followup(BASE, {'days_to_follow_up': 0}, '/follow_ups/0')
        self.assertEqual(r['placement'], 'relative_point')
        self.assertEqual(r['evidence_kind'], 'registry_followup_assertion')
        self.assertNotIn('resourceType', r)

    def test_no_source_mutation(self):
        c = copy.deepcopy(BASE)
        c['diagnoses'] = [{'treatments': [{'treatment_or_therapy': 'yes', START: 0}]}]
        before = copy.deepcopy(c)
        audit([c])
        self.assertEqual(c, before)

    def test_naive_type_only_control_is_measured_against_reported_receipt(self):
        c = copy.deepcopy(BASE)
        c['diagnoses'] = [{'treatments': [
            {'treatment_type': 'A', 'treatment_or_therapy': 'yes', START: 0, END: 5},
            {'treatment_type': 'A', 'treatment_or_therapy': 'no'},
            {'treatment_type': 'B', 'treatment_or_therapy': 'unknown'},
            {'treatment_type': 'B'}]}]
        r = audit([c])
        self.assertEqual(r['treatment_records'], 4)
        self.assertEqual(r['type_only_control'], {'labeled_records': 4, 'explicit_no': 1, 'not_affirmative': 3})
        self.assertEqual(r['positive_relative_intervals'], 1)

    def test_aggregate_does_not_publish_subject_or_drug_values(self):
        c = copy.deepcopy(BASE)
        c['diagnoses'] = [{'treatments': [{'therapeutic_agents': 'PRIVATE-DRUG', 'treatment_or_therapy': 'yes'}]}]
        text = json.dumps(audit([c]))
        self.assertNotIn('FICTIONAL-A', text)
        self.assertNotIn('PRIVATE-DRUG', text)

    def test_empty_cohort_has_no_positive_events(self):
        self.assertEqual(audit([])['positive_relative_intervals'], 0)

    def test_unknown_collection_is_not_fabricated_record(self):
        r = audit([dict(BASE, diagnoses=None, follow_ups=None)])
        self.assertEqual(r['treatment_records'], 0)
        self.assertEqual(r['followup_records'], 0)

    def test_malformed_collection_is_rejected(self):
        with self.assertRaises(ValueError): audit([dict(BASE, diagnoses={})])

    def test_duplicate_or_missing_case_identity_is_rejected(self):
        for cases in [[BASE, BASE], [{}]]:
            with self.subTest(cases=cases), self.assertRaises(ValueError): audit(cases)

    def test_legacy_type_control_does_not_pool_new_administered_type(self):
        c = dict(BASE, diagnoses=[{'treatments': [{'treatment_type_administered': 'Chemotherapy'}]}])
        self.assertEqual(audit([c])['type_only_control'],
                         {'labeled_records': 0, 'explicit_no': 0, 'not_affirmative': 0})

    def test_both_type_fields_are_preserved_separately(self):
        r = treatment(BASE, {'treatment_type': 'Radiation',
                             'treatment_type_administered': 'Chemotherapy'}, PATH)
        self.assertEqual(r.get('legacy_type', {}).get('raw'), 'Radiation')
        self.assertEqual(r.get('administered_type', {}).get('raw'), 'Chemotherapy')

    def test_no_indicator_and_administered_label_preserve_conflict(self):
        r = treatment(BASE, {'treatment_or_therapy': 'no',
                             'treatment_type_administered': 'Chemotherapy'}, PATH)
        self.assertEqual(r.get('receipt_consistency'), 'conflicting_source_fields')
        self.assertEqual(r['receipt'], 'reported_no')
        self.assertEqual(r['placement'], 'needs_receipt_review')

    def test_administered_label_without_indicator_is_not_erased_or_promoted(self):
        r = treatment(BASE, {'treatment_type_administered': 'Chemotherapy', START: 0}, PATH)
        self.assertEqual(r.get('receipt_consistency'), 'administered_type_without_affirmative_indicator')
        self.assertEqual(r['receipt'], 'absent')
        self.assertEqual(r['placement'], 'needs_receipt_review')

    def test_legacy_label_with_no_indicator_is_not_a_new_field_conflict(self):
        r = treatment(BASE, {'treatment_type': 'Chemotherapy', 'treatment_or_therapy': 'no'}, PATH)
        self.assertEqual(r.get('receipt_consistency'), 'indicator_only')
        self.assertEqual(r['placement'], 'not_positive')

    def test_new_field_comparison_has_its_own_denominator(self):
        c = dict(BASE, diagnoses=[{'treatments': [
            {'treatment_type_administered': 'A', 'treatment_or_therapy': 'yes'},
            {'treatment_type_administered': 'A', 'treatment_or_therapy': 'no'},
            {'treatment_type_administered': 'A'},
            {'treatment_type_administered': 'Not Reported', 'treatment_or_therapy': 'no'}]}])
        r = audit([c])
        self.assertEqual(r.get('administered_type_comparison'),
            {'labeled_records': 3, 'indicator_yes': 1, 'indicator_no': 1, 'indicator_other': 1})
        self.assertEqual(r.get('receipt_consistency_states'),
            {'indicator_and_administered_type': 1, 'conflicting_source_fields': 1,
             'administered_type_without_affirmative_indicator': 1, 'indicator_only': 1})

if __name__ == '__main__': unittest.main()
