"""Original fictional fixtures; no patient records or clinical reference answers."""
import copy
import json
import sqlite3
import unittest
import gdc_projection_probe as p


def fixture():
    return [
        {'case_id': 'FICTIONAL-A', 'index_date': 'Diagnosis', 'extra': {'x': [0, False, None]},
         'diagnoses': [
             {'diagnosis_id': 'D-A1', 'treatments': [
                 {'treatment_id': 'T1', 'days_to_treatment_start': 0,
                  'days_to_treatment_end': 9, 'treatment_or_therapy': 'no'},
                 {'treatment_id': 'T2', 'days_to_treatment_start': None}]},
             {'diagnosis_id': 'D-A2', 'treatments': []}],
         'follow_ups': [{'follow_up_id': 'F-A', 'days_to_follow_up': 40}],
         'samples': [
             {'sample_id': 'S-A1', 'portions': [{'portion_id': 'P-A', 'analytes': [
                 {'analyte_id': 'N-A', 'aliquots': [{'aliquot_id': 'Q-A'}]}]}]},
             {'sample_id': 'S-A2', 'aliquots': [{'aliquot_id': 'Q-A2'}]},
             {'sample_id': 'S-A3'}]},
        {'case_id': 'FICTIONAL-B', 'samples': [], 'follow_ups': None}
    ]


class ProjectionTests(unittest.TestCase):
    def test_roundtrip_retains_all_fields_and_list_order(self):
        data = fixture()
        with p.Projection(data) as db:
            self.assertEqual(db.restore(), data)

    def test_input_is_not_modified(self):
        data = fixture(); before = copy.deepcopy(data)
        with p.Projection(data):
            pass
        self.assertEqual(data, before)

    def test_empty_null_absent_arrays_remain_distinct(self):
        data = [{'case_id': 'FICTIONAL-A', 'samples': [], 'diagnoses': None},
                {'case_id': 'FICTIONAL-B'}]
        with p.Projection(data) as db:
            out = db.restore()
        self.assertEqual(len(out), 2)
        self.assertEqual(out[0]['samples'], [])
        self.assertIsNone(out[0]['diagnoses'])
        self.assertNotIn('samples', out[1])

    def test_counts_do_not_use_diagnosis_sample_cartesian_product(self):
        out = p.audit(fixture())
        self.assertIn('case', out['counts'])
        self.assertEqual(out['counts']['case'], 2)
        self.assertEqual(out['counts']['sample'], 3)
        self.assertEqual(out['counts']['aliquot'], 2)
        self.assertEqual(out['naive_inner_join_rows'], 6)
        self.assertEqual(out['cases_lost_by_inner_join'], 1)

    def test_followups_use_case_level_not_diagnosis_level(self):
        out = p.audit(fixture())
        self.assertIn('follow_up', out['counts'])
        self.assertEqual(out['counts']['follow_up'], 1)
        self.assertEqual(out['legacy_nested_followup_count'], 0)

    def test_sql_rejects_missing_parent(self):
        with p.Projection(fixture()) as db:
            self.assertIsNotNone(db.conn)
            with self.assertRaises(sqlite3.IntegrityError):
                db.conn.execute('UPDATE nodes SET parent=? WHERE case_key=? AND path=?',
                                ('/missing', 'FICTIONAL-A', '/samples/0'))

    def test_sql_rejects_parent_existing_only_in_another_case(self):
        data = fixture()
        data[1]['samples'] = [{'sample_id': 'S-B', 'portions': [{'portion_id': 'P-B'}]}]
        with p.Projection(data) as db:
            self.assertIsNotNone(db.conn)
            with self.assertRaises(sqlite3.IntegrityError):
                db.conn.execute('UPDATE nodes SET parent=? WHERE case_key=? AND path=?',
                                ('/samples/1', 'FICTIONAL-B', '/samples/0/portions/0'))

    def test_canonical_digest_detects_dropped_child(self):
        with p.Projection(fixture()) as db:
            self.assertIsNotNone(db.conn)
            db.conn.execute('DELETE FROM nodes WHERE kind=? AND path=?',
                            ('aliquot', '/samples/0/portions/0/analytes/0/aliquots/0'))
            self.assertFalse(db.intact())

    def test_canonical_digest_detects_changed_value(self):
        with p.Projection(fixture()) as db:
            self.assertIsNotNone(db.conn)
            db.conn.execute('UPDATE nodes SET payload=? WHERE case_key=? AND path=?',
                            ('{"sample_id":"CHANGED"}', 'FICTIONAL-A', '/samples/2'))
            self.assertFalse(db.intact())

    def test_duplicate_case_id_is_rejected(self):
        with self.assertRaises(ValueError):
            p.Projection([{'case_id': 'FICTIONAL-A'}, {'case_id': 'FICTIONAL-A'}])

    def test_missing_case_id_is_rejected(self):
        with self.assertRaises(ValueError):
            p.Projection([{'samples': []}])

    def test_non_list_children_are_rejected_not_discarded(self):
        with self.assertRaises(ValueError):
            p.Projection([{'case_id': 'FICTIONAL-A', 'samples': 'not an array'}])

    def test_non_object_child_is_rejected(self):
        with self.assertRaises(ValueError):
            p.Projection([{'case_id': 'FICTIONAL-A', 'samples': [7]}])

    def test_negative_zero_offsets_preserved_without_calendar_invention(self):
        self.assertEqual(p.offset(0), {'state': 'numeric', 'value': 0})
        self.assertEqual(p.offset(-12), {'state': 'numeric', 'value': -12})

    def test_boolean_nan_infinite_offsets_not_numbers(self):
        for raw in (False, True, float('nan'), float('inf')):
            self.assertEqual(p.offset(raw)['state'], 'invalid')

    def test_text_and_missing_offsets_not_coerced(self):
        self.assertEqual(p.offset('12')['state'], 'unresolved')
        self.assertEqual(p.offset(None)['state'], 'unresolved')

    def test_temporal_profile_does_not_treat_no_therapy_as_administered(self):
        out = p.audit(fixture())
        self.assertIn('treatments', out['time'])
        self.assertEqual(out['time']['treatments'], 2)
        self.assertEqual(out['time']['numeric_start'], 1)
        self.assertEqual(out['time']['numeric_end'], 1)
        self.assertFalse(out['administrations_inferred'])
        self.assertFalse(out['calendar_dates_inferred'])

    def test_aggregate_output_contains_no_subject_or_child_identifiers(self):
        text = json.dumps(p.audit(fixture()))
        for secret in ('FICTIONAL-A', 'FICTIONAL-B', 'D-A1', 'S-A1', 'F-A'):
            self.assertNotIn(secret, text)

    def test_schema_gate_rejects_unsupported_expansion(self):
        with self.assertRaises(ValueError):
            p.validate_expansions(['diagnoses.follow_ups'], ['diagnoses', 'follow_ups'])

    def test_schema_gate_accepts_documented_expansion(self):
        self.assertIsNone(p.validate_expansions(['diagnoses', 'follow_ups'], ['diagnoses', 'follow_ups']))

    def test_snapshot_changes_detect_only_changed_case_and_preserve_old(self):
        before = fixture(); after = copy.deepcopy(before)
        after[0]['diagnoses'][0]['treatments'][0]['days_to_treatment_start'] = 1
        with p.Projection(before) as old, p.Projection(after) as new:
            self.assertEqual(p.compare(old, new), {'unchanged': 1, 'changed': 1, 'added': 0, 'removed': 0})
            self.assertEqual(old.restore(), before)

    def test_identical_import_is_same_content_not_new_clinical_event(self):
        with p.Projection(fixture()) as old, p.Projection(fixture()) as new:
            self.assertEqual(p.compare(old, new), {'unchanged': 2, 'changed': 0, 'added': 0, 'removed': 0})

    def test_array_reordering_roundtrips_without_losing_lineage(self):
        data = fixture(); data[0]['samples'].reverse()
        with p.Projection(data) as db:
            self.assertEqual(db.restore(), data)
            self.assertTrue(db.intact())

    def test_schema_gate_rejects_missing_mapping_instead_of_claiming_no_followups(self):
        with self.assertRaises(ValueError):
            p.validate_expansions(['follow_ups'], [])


if __name__ == '__main__':
    unittest.main()
