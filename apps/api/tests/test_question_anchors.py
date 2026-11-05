"""Strict identity-only anchors; no source access, currentness or write authority."""
from copy import deepcopy
from importlib import import_module, util
import json
import unittest

from open_intelligence.patient_registry import PatientRegistryError
from question_anchor_fixtures import compatibility_outputs, PID, CASE, SID


def text_fields():
    return {'contract': 'oi.question-source-anchor/1', 'anchor_kind': 'text_line',
            'patient_id': PID, 'case_id': CASE, 'source_id': SID,
            'source_version': 1, 'source_sha256': 'a' * 64, 'source_line': 8}


def lab_fields():
    data = text_fields()
    del data['source_line']
    return data | {'anchor_kind': 'fhir_observation',
                   'resource_reference': 'Observation/FICTIONAL-OBS-A',
                   'specimen_reference': 'Specimen/FICTIONAL-SPECIMEN-A',
                   'report_reference': 'DiagnosticReport/FICTIONAL-REPORT-A'}


class QuestionAnchorContractTests(unittest.TestCase):
    def setUp(self):
        self.assertIsNotNone(util.find_spec('oi_api.question_anchors'),
                             'The shared typed question-source anchor contract is missing')
        self.module = import_module('oi_api.question_anchors')

    def test_text_anchor_roundtrips_without_invented_resource_fields(self):
        fields = text_fields()
        result = self.module.parse_question_anchor(fields)
        self.assertEqual(result.model_dump(mode='json'), fields)
        self.assertNotIn('resource_reference', result.model_dump())

    def test_lab_anchor_roundtrips_without_a_fake_text_line(self):
        fields = lab_fields()
        result = self.module.parse_question_anchor(fields)
        self.assertEqual(result.model_dump(mode='json'), fields)
        self.assertNotIn('source_line', result.model_dump())

    def test_variant_and_contract_are_explicit_not_inferred(self):
        for fields in (text_fields(), lab_fields()):
            for field in ('contract', 'anchor_kind'):
                with self.subTest(kind=fields['anchor_kind'], missing=field), \
                     self.assertRaises(PatientRegistryError):
                    self.module.parse_question_anchor({k: v for k, v in fields.items() if k != field})
            for change in ({'contract': 'oi.question-source-anchor/0'},
                           {'anchor_kind': 'unknown'}, {'anchor_kind': True}):
                with self.subTest(change=change), self.assertRaises(PatientRegistryError):
                    self.module.parse_question_anchor(fields | change)

    def test_every_identity_field_is_required(self):
        for fields in (text_fields(), lab_fields()):
            for field in fields:
                with self.subTest(kind=fields['anchor_kind'], missing=field), \
                     self.assertRaises(PatientRegistryError):
                    self.module.parse_question_anchor({k: v for k, v in fields.items() if k != field})

    def test_unknown_fields_and_authority_claims_are_rejected(self):
        for fields in (text_fields(), lab_fields()):
            for key, value in (('question_id', 'QUESTION-' + 'D' * 32),
                               ('clinical_approval', True), ('model_execution_authorized', True),
                               ('current', True), ('original_text', 'Do not copy records'),
                               ('access_receipt_id', 'ACCESS-' + 'C' * 32)):
                with self.subTest(key=key), self.assertRaises(PatientRegistryError):
                    self.module.parse_question_anchor(fields | {key: value})

    def test_mixed_anchor_variants_are_rejected_even_when_null(self):
        for extra in ({'source_line': 1}, {'source_line': None}, {'line': 1}):
            with self.subTest(extra=extra), self.assertRaises(PatientRegistryError):
                self.module.parse_question_anchor(lab_fields() | extra)
        for extra in ({'resource_reference': None},
                      {'resource_reference': 'Observation/FICTIONAL-OBS-A'},
                      {'specimen_reference': 'Specimen/FICTIONAL-SPECIMEN-A'}):
            with self.subTest(extra=extra), self.assertRaises(PatientRegistryError):
                self.module.parse_question_anchor(text_fields() | extra)

    def test_lines_and_versions_do_not_coerce_booleans_strings_or_floats(self):
        for field in ('source_line', 'source_version'):
            for value in (True, False, 1.0, '1', None, 0, -1):
                with self.subTest(field=field, value=value), self.assertRaises(PatientRegistryError):
                    self.module.parse_question_anchor(text_fields() | {field: value})
        with self.assertRaises(PatientRegistryError):
            self.module.parse_question_anchor(text_fields() | {'source_line': 10001})
        for line in (1, 10000):
            self.assertEqual(self.module.parse_question_anchor(
                text_fields() | {'source_line': line}).source_line, line)

    def test_scope_ids_and_hashes_remain_exact(self):
        invalid = {'patient_id': ('', True, ' PATIENT-A', 'PATIENT-A\n'),
                   'case_id': ('CASE-OTHER\n', 'OTHER', 1),
                   'source_id': ('SRC-' + 'a' * 32, SID + '\n', SID + '/1', False),
                   'source_sha256': ('A' * 64, 'a' * 63, 'a' * 64 + '\n', True)}
        for field, values in invalid.items():
            for value in values:
                with self.subTest(field=field, value=value), self.assertRaises(PatientRegistryError):
                    self.module.parse_question_anchor(text_fields() | {field: value})

    def test_each_fhir_reference_is_local_and_exactly_typed(self):
        for field, kind in (('resource_reference', 'Observation'),
                            ('specimen_reference', 'Specimen'),
                            ('report_reference', 'DiagnosticReport')):
            for value in (None, True, f'https://example.invalid/{kind}/A', f'{kind}/A/_history/2',
                          f'{kind}/A?x=1', f'{kind}/A#x', f'{kind}/A\n', f'{kind}/',
                          f'{kind}/' + 'A' * 65, 'Patient/A', f'{kind}/A%2FB'):
                with self.subTest(field=field, value=value), self.assertRaises(PatientRegistryError):
                    self.module.parse_question_anchor(lab_fields() | {field: value})
            valid = kind + '/A.b-09'
            self.assertEqual(getattr(self.module.parse_question_anchor(
                lab_fields() | {field: valid}), field), valid)

    def test_input_must_be_a_plain_mapping_not_a_model_or_json_string(self):
        for value in (None, [], json.dumps(text_fields()), True):
            with self.subTest(value=value), self.assertRaises(PatientRegistryError):
                self.module.parse_question_anchor(value)
        parsed = self.module.parse_question_anchor(text_fields())
        with self.assertRaises(PatientRegistryError):
            self.module.parse_question_anchor(parsed)

    def test_anchor_is_immutable_and_does_not_alias_input(self):
        data = lab_fields()
        result = self.module.parse_question_anchor(data)
        data['resource_reference'] = 'Observation/OTHER'
        self.assertEqual(result.resource_reference, 'Observation/FICTIONAL-OBS-A')
        with self.assertRaises((ValueError, TypeError, AttributeError)):
            result.source_version = 2
        dumped = result.model_dump()
        dumped['source_version'] = 3
        self.assertEqual(result.source_version, 1)

    def test_any_scope_source_or_resource_change_changes_identity(self):
        data = lab_fields()
        original = self.module.parse_question_anchor(data)
        for change in ({'patient_id': 'PATIENT-OTHER'}, {'case_id': 'CASE-OTHER'},
                       {'source_id': 'SRC-' + 'B' * 32}, {'source_version': 2},
                       {'source_sha256': 'b' * 64}, {'resource_reference': 'Observation/OTHER'},
                       {'specimen_reference': 'Specimen/OTHER'},
                       {'report_reference': 'DiagnosticReport/OTHER'}):
            with self.subTest(change=change):
                self.assertNotEqual(original, self.module.parse_question_anchor(data | change))

    def test_preflight_adapters_preserve_the_exact_identity_and_input(self):
        outputs = compatibility_outputs()
        for name in ('text_preflight', 'lab_precision', 'lab_masked'):
            prepared = outputs[name]
            before = deepcopy(prepared)
            anchor = self.module.anchor_from_preflight(prepared)
            self.assertEqual(anchor.patient_id, prepared['patient_id'])
            self.assertEqual(anchor.case_id, prepared['case_id'])
            self.assertEqual(anchor.source_id, prepared['selected_source']['source_id'])
            self.assertEqual(anchor.source_sha256, prepared['selected_source']['sha256'])
            self.assertEqual(anchor.source_version, prepared['selected_source']['version'])
            self.assertEqual(prepared, before)
            self.assertNotIn('value_text', anchor.model_dump())
            self.assertNotIn('question', anchor.model_dump())

    def test_preflight_adapters_reject_mixed_or_unknown_contracts(self):
        outputs = compatibility_outputs()
        for base in (outputs['text_preflight'], outputs['lab_precision']):
            for change in ({'contract': 'other'}, {'patient_id': None}, {'selected_source': None}):
                with self.subTest(change=change), self.assertRaises(PatientRegistryError):
                    self.module.anchor_from_preflight(base | change)
        for extra in ({'line': 1}, {'source_line': None}, {'anchor_kind': 'text_line'}):
            p = deepcopy(outputs['lab_precision']); p['selected_source'].update(extra)
            with self.subTest(extra=extra), self.assertRaises(PatientRegistryError):
                self.module.anchor_from_preflight(p)
        for extra in ({'resource_reference': None}, {'anchor_kind': 'fhir_observation'}):
            p = deepcopy(outputs['text_preflight']); p['selected_source'].update(extra)
            with self.subTest(extra=extra), self.assertRaises(PatientRegistryError):
                self.module.anchor_from_preflight(p)

    def test_legacy_adapter_does_not_infer_a_lab_anchor_or_change_row(self):
        row = compatibility_outputs()['question_current']
        before = deepcopy(row)
        anchor = self.module.legacy_text_question_anchor(row)
        self.assertEqual(anchor.model_dump(mode='json'), text_fields())
        self.assertEqual(row, before)
        for extra in ({'source_line': None}, {'anchor_kind': 'fhir_observation'},
                      {'resource_reference': 'Observation/FICTIONAL-OBS-A'}):
            with self.subTest(extra=extra), self.assertRaises(PatientRegistryError):
                self.module.legacy_text_question_anchor(row | extra)

    def test_wrong_scope_matching_anchor_is_not_treated_as_same_identity(self):
        row = compatibility_outputs()['question_current']
        left = self.module.legacy_text_question_anchor(row)
        for field, value in (('patient_id', 'PATIENT-OTHER'), ('case_id', 'CASE-OTHER')):
            self.assertNotEqual(left, self.module.legacy_text_question_anchor(row | {field: value}))
