"""Fail-closed engineering readiness; this is not clinical assessment."""
import copy
import csv
import io
import pathlib
import subprocess
import sys
import tempfile
import json
import unittest

from tools.evaluation_preflight import inspect_inputs, PreflightError

FIELDS = ('evaluation_id,packet_commit,application_commit,run_id,reviewer_id,case_id,cutoff,arm,opportunity_id,claim_id,denominator_eligible,source_ids,source_versions,source_lines,outcome,severity,missingness_error,identity_error,post_cutoff_leak,unsupported_claim,false_urgency,acquisition_minutes,preparation_minutes,correction_minutes,review_minutes,coordination_minutes,prior_key_exposure,disagreement,adjudicator_outcome,reason,evidence_location\n')


def fake_packet():
    return dict(version=1, packet_id='OI-IV01-V1', project='Open Intelligence', synthetic=True,
                status='engineering-practice-only', reference_code_commit='a'*40,
                authorship='Original fictional reference only',
                cutoffs={'T0': '2026-01-10T12:00:00Z'},
                cases=[{'id':'CASE-A','label':'Fictional A'}], questions=['What is unknown?'],
                sources=[], receipts=[])


def inactive():
    return dict(evaluation_id=None, status='not_activated', packet_id='OI-IV01-V1',
                application_commit=None, packet_commit=None,
                independent_reviewer_ids=[],conflicts_declared=False,
                prior_key_exposure_recorded=False,source_rights_reviewed=False,
                clinical_reference_review_complete=False,metric_denominators_frozen=False,
                arm_order_plan=None, empirical_thresholds=dict(source_fidelity_minimum=None,
                missingness_fidelity_minimum=None,maximum_omissions=None,
                acceptable_review_burden_change=None),
                engineering_invariants=dict(future_source_leaks=0,answer_key_in_participant_packet=0,
                hash_mismatches_accepted=0,overwrites_of_existing_packet=0),
                stop_owner=None,approval_record=None,results_observed=False)


def declared():
    p=inactive(); p.update(evaluation_id='EVAL-TEST-001',status='activated',application_commit='b'*40,
     packet_commit='c'*40, independent_reviewer_ids=['REVIEWER-01','REVIEWER-02'],
     conflicts_declared=True,prior_key_exposure_recorded=True,source_rights_reviewed=True,
     clinical_reference_review_complete=True, metric_denominators_frozen=True,
     arm_order_plan='Counterbalanced A/B/C, fixed before access',stop_owner='EVAL-OWNER-01',
     approval_record='Synthetic example approval text is not institutional proof')
    p['empirical_thresholds']=dict(source_fidelity_minimum=.95,
      missingness_fidelity_minimum=.9, maximum_omissions=0,
      acceptable_review_burden_change=.25)
    return p


def raw(data):
    return json.dumps(data,sort_keys=True,allow_nan=False).encode('utf-8')


class EvaluationPreflightTests(unittest.TestCase):
    def inspect(self, p=None, m=None, template=FIELDS):
        return inspect_inputs(raw(inactive() if p is None else p),
                              raw(fake_packet() if m is None else m),
                              template.encode('utf-8'))

    def test_public_template_remains_blocked_without_fabricated_approval(self):
        r=self.inspect()
        self.assertEqual(r['gate'],'blocked')
        self.assertFalse(r['declarations_complete'])
        self.assertFalse(r['clinical_or_release_approved'])
        self.assertFalse(r['scoring_authorized'])
        self.assertFalse(r['blinded_evaluation_established'])
        self.assertTrue(any('status' in x for x in r['blockers']))
        self.assertTrue(any('threshold' in x for x in r['blockers']))
        self.assertEqual(len(r['fingerprints']['manifest_sha256']),64)
        self.assertEqual(r['source_count'],0)

    def test_declarations_can_only_make_contract_complete_not_validated(self):
        r=self.inspect(p=declared())
        self.assertEqual(r['gate'],'declarations_complete_unverified')
        self.assertTrue(r['declarations_complete'])
        self.assertFalse(r['clinical_or_release_approved'])
        self.assertFalse(r['scoring_authorized'])
        self.assertFalse(r['blinded_evaluation_established'])
        self.assertFalse(r['independent_validation_performed'])
        self.assertEqual(r['blockers'],[])

    def test_results_already_seen_block_retroactive_activation(self):
        p=declared();p['results_observed']=True
        self.assertIn('results_observed', '\n'.join(self.inspect(p=p)['blockers']))
        self.assertEqual(self.inspect(p=p)['gate'],'blocked')

    def test_wrong_packet_identifier_and_schema_changes_rejected(self):
        p=declared();p['packet_id']='WRONG'
        with self.assertRaisesRegex(PreflightError,'packet_id'):
            self.inspect(p=p)
        p=declared();p['invented_approval']=True
        with self.assertRaisesRegex(PreflightError,'unexpected'):
            self.inspect(p=p)

    def test_duplicate_json_keys_rejected(self):
        p=raw(inactive()).decode('utf-8')[:-1] + ',"status":"activated"}'
        with self.assertRaisesRegex(PreflightError,'duplicate'):
            inspect_inputs(p.encode(),raw(fake_packet()),FIELDS.encode())

    def test_invalid_thresholds_are_blocked(self):
        for value in (True,-0.01,1.01,'0.95',None):
            p=declared();p['empirical_thresholds']['source_fidelity_minimum']=value
            with self.subTest(value=value):
                self.assertEqual(self.inspect(p=p)['gate'],'blocked')
        p=declared();p['empirical_thresholds']['maximum_omissions']=True
        self.assertEqual(self.inspect(p=p)['gate'],'blocked')

    def test_nonzero_safety_invariants_cannot_be_accepted(self):
        p=declared();p['engineering_invariants']['future_source_leaks']=1
        self.assertEqual(self.inspect(p=p)['gate'],'blocked')
        self.assertIn('future_source_leaks', ' '.join(self.inspect(p=p)['blockers']))

    def test_reviewer_and_boolean_contract_rejects_spoofs(self):
        p=declared();p['independent_reviewer_ids']=['REVIEWER-01','REVIEWER-01']
        self.assertEqual(self.inspect(p=p)['gate'],'blocked')
        p=declared();p['source_rights_reviewed']='true'
        self.assertEqual(self.inspect(p=p)['gate'],'blocked')

    def test_empty_results_template_required_and_column_changes_fail(self):
        self.assertEqual(self.inspect(p=declared())['gate'],'declarations_complete_unverified')
        with self.assertRaisesRegex(PreflightError,'not blank'):
            self.inspect(template=FIELDS+'FAKE-RESULT\n')
        with self.assertRaisesRegex(PreflightError,'headers'):
            self.inspect(template=FIELDS.replace('case_id','patient_name'))

    def test_cli_reports_blocked_default_and_nonzero_optional_gate(self):
        with tempfile.TemporaryDirectory() as folder:
            dest=pathlib.Path(folder)
            (dest/'protocol.json').write_bytes(raw(inactive()))
            (dest/'cases.json').write_bytes(raw(fake_packet()))
            (dest/'results.csv').write_text(FIELDS,encoding='utf-8')
            args=[sys.executable,'-m','tools.evaluation_preflight',
                  '--protocol',str(dest/'protocol.json'),
                  '--manifest',str(dest/'cases.json'),
                  '--template',str(dest/'results.csv')]
            root=pathlib.Path(__file__).resolve().parents[1]
            result=subprocess.run(args,cwd=root,capture_output=True,text=True)
            self.assertEqual(result.returncode,0,result.stderr)
            self.assertEqual(json.loads(result.stdout)['gate'],'blocked')
            result=subprocess.run(args+['--require-complete'],cwd=root,capture_output=True,text=True)
            self.assertEqual(result.returncode,3)
            self.assertFalse(json.loads(result.stdout)['scoring_authorized'])
            (dest/'protocol.json').write_bytes(raw(declared()))
            result=subprocess.run(args+['--require-complete'],cwd=root,capture_output=True,text=True)
            self.assertEqual(result.returncode,0,result.stderr)
            self.assertEqual(json.loads(result.stdout)['gate'],'declarations_complete_unverified')
            self.assertFalse(json.loads(result.stdout)['scoring_authorized'])

    def test_contract_is_read_only_and_fingerprints_are_repeatable(self):
        p=inactive();m=fake_packet(); before=(copy.deepcopy(p),copy.deepcopy(m))
        a=self.inspect(p=p,m=m);b=self.inspect(p=p,m=m)
        self.assertEqual(a,b)
        self.assertEqual((p,m),before)


if __name__=='__main__':
    unittest.main()
