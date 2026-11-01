"""Original fictional tests; no true patient or trial records."""
import copy
import json
import unittest
from trial_screening_probe import (minimum_age_check, registry_profile, criterion_state,
    review_packet, packet_is_current)


def trial(nct='NCT00000001', overall='RECRUITING', locations=None, age='18 Years'):
    p={'identificationModule': {'nctId': nct},
       'statusModule': {'overallStatus': overall, 'lastUpdatePostDateStruct': {'date': '2026-01-01'},
                        'statusVerifiedDate':'2026-01'},
       'eligibilityModule': {'minimumAge':age, 'eligibilityCriteria':'Inclusion: fictional requirements.\nExclusion: fictional restrictions.'}}
    if locations is not None: p['contactsLocationsModule']={'locations':locations}
    return {'protocolSection':p}


def assessment(cid='A', truth=True, kind='inclusion', case='FICTIONAL-A', psha='a'*64, tsha='b'*64):
    return {'criterion_id':cid,'truth':truth,'case_id':case,'patient_sha256':psha,
            'trial_sha256':tsha,'evidence_refs':['fictional-source#1']}


class TrialResearchTests(unittest.TestCase):
    def test_minimum_age_boundary_is_inclusive(self):
        self.assertEqual(minimum_age_check({'minimumAge':'18 Years'},18),'supports_lower_bound')
        self.assertEqual(minimum_age_check({'minimumAge':'18 Years'},17),'contradicts_lower_bound')

    def test_minimum_age_zero_is_not_missing(self):
        self.assertEqual(minimum_age_check({'minimumAge':'0 Years'},0),'supports_lower_bound')

    def test_unknown_age_never_passes(self):
        for a in (None,True,'18',float('nan'),float('inf'),-1,18.5):
            with self.subTest(a=a): self.assertEqual(minimum_age_check({'minimumAge':'18 Years'},a),'unknown')

    def test_unsupported_age_units_are_not_approximated(self):
        for bound in ('18 Months','12 Weeks','N/A','18 years','',None,False):
            with self.subTest(bound=bound): self.assertEqual(minimum_age_check({'minimumAge':bound},20),'unknown')

    def test_absent_minimum_is_not_assumed_no_limit(self):
        self.assertEqual(minimum_age_check({},40),'unknown')

    def test_trial_status_does_not_propagate_to_sites(self):
        r=registry_profile([trial(locations=[{'status':'COMPLETED'},{}])])
        self.assertEqual(r.get('sites_total'),2)
        self.assertEqual(r.get('sites_reported_recruiting'),0)
        self.assertEqual(r.get('sites_missing_status'),1)
        self.assertEqual(r.get('recruiting_studies_without_reported_recruiting_site'),1)

    def test_no_locations_is_unknown_not_no_sites(self):
        r=registry_profile([trial()])
        self.assertEqual(r.get('studies_without_locations'),1)
        self.assertEqual(r.get('recruiting_studies_without_reported_recruiting_site'),1)

    def test_one_recruiting_site_does_not_open_other_sites(self):
        r=registry_profile([trial(locations=[{'status':'RECRUITING'},{'status':'COMPLETED'}])])
        self.assertEqual(r.get('sites_reported_recruiting'),1)
        self.assertEqual(r.get('sites_with_other_explicit_status'),1)
        self.assertEqual(r.get('studies_with_mixed_explicit_site_statuses'),1)

    def test_recruiting_site_under_closed_study_is_disagreement(self):
        r=registry_profile([trial(overall='COMPLETED',locations=[{'status':'RECRUITING'}])])
        self.assertEqual(r.get('nonrecruiting_studies_with_reported_recruiting_site'),1)

    def test_duplicate_or_missing_ids_are_rejected(self):
        for rows in ([trial(),trial()], [{'protocolSection':{}}]):
            with self.subTest(rows=rows),self.assertRaises(ValueError): registry_profile(rows)

    def test_malformed_nested_payload_is_rejected(self):
        r=trial();r['protocolSection']['contactsLocationsModule']={'locations':'not-a-list'}
        with self.assertRaises(ValueError): registry_profile([r])

    def test_profile_preserves_input_and_avoids_contact_fields(self):
        r=trial(locations=[{'status':'RECRUITING','contacts':[{'email':'private@example.test'}]}])
        before=copy.deepcopy(r);p=registry_profile([r])
        self.assertEqual(r,before)
        self.assertNotIn('private@example.test',json.dumps(p))
        self.assertEqual(p.get('studies'),1)

    def test_full_eligibility_remains_unassessed(self):
        r=registry_profile([trial()])
        self.assertEqual(r.get('studies_with_free_text_eligibility'),1)
        self.assertEqual(r.get('full_eligibility_decisions'),0)
        self.assertEqual(r.get('structured_minimum_age_checks',{}).get('65'),{'supports_lower_bound':1})

    def test_trial_source_fingerprints_change_with_criteria(self):
        a=registry_profile([trial()]);s=trial();s['protocolSection']['eligibilityModule']['eligibilityCriteria']='amended'
        b=registry_profile([s]);self.assertIsNotNone(a.get('criteria_set_sha256'))
        self.assertNotEqual(a.get('criteria_set_sha256'),b.get('criteria_set_sha256'))

    def test_month_precision_is_not_fake_exact_date(self):
        p=registry_profile([trial()]);self.assertEqual(p.get('verification_date_precision'),{'month':1})

    def test_inclusion_and_exclusion_use_opposite_polarity(self):
        table=[('inclusion',True,'supported'),('inclusion',False,'contradicted'),
               ('exclusion',True,'contradicted'),('exclusion',False,'supported')]
        for k,v,want in table:
            with self.subTest(kind=k,truth=v):self.assertEqual(criterion_state(k,v),want)

    def test_missing_and_conflict_survive_both_polarities(self):
        for k in ('inclusion','exclusion'):
            self.assertEqual(criterion_state(k,None),'unknown')
            self.assertEqual(criterion_state(k,'conflict'),'conflict')

    def test_strings_cannot_masquerade_as_boolean_facts(self):
        for v in ('false','true','no',0,1):
            with self.subTest(v=v),self.assertRaises(ValueError):criterion_state('exclusion',v)

    def test_unknown_criterion_kind_is_rejected(self):
        with self.assertRaises(ValueError):criterion_state('other',True)

    def test_missing_exclusion_is_not_auto_passed(self):
        p=review_packet('FICTIONAL-A','a'*64,'b'*64,{'A':'inclusion','B':'exclusion'},[assessment()])
        self.assertEqual(p.get('states'),{'A':'supported','B':'unknown'})
        self.assertEqual(p.get('disposition'),'needs_information')
        self.assertIsNone(p.get('final_eligibility'))

    def test_source_and_protocol_changes_invalidate_old_assessment(self):
        for key in ('patient_sha256','trial_sha256','case_id'):
            a=assessment();a[key]='changed'
            p=review_packet('FICTIONAL-A','a'*64,'b'*64,{'A':'inclusion'},[a])
            self.assertEqual(p.get('states'),{'A':'unknown'})

    def test_unsupported_claim_without_evidence_is_held(self):
        a=assessment();a['evidence_refs']=[]
        p=review_packet('FICTIONAL-A','a'*64,'b'*64,{'A':'inclusion'},[a])
        self.assertEqual(p.get('states'),{'A':'unknown'})

    def test_all_encoded_criteria_supported_is_not_final_eligibility(self):
        p=review_packet('FICTIONAL-A','a'*64,'b'*64,{'A':'inclusion'},[assessment()])
        self.assertEqual(p.get('disposition'),'encoded_criteria_supported')
        self.assertIsNone(p.get('final_eligibility'))
        self.assertTrue(packet_is_current(p,'FICTIONAL-A','a'*64,'b'*64))
        self.assertFalse(packet_is_current(p,'FICTIONAL-A','a'*64,'c'*64))

    def test_conflict_not_majority_vote(self):
        p=review_packet('FICTIONAL-A','a'*64,'b'*64,{'A':'inclusion'},[assessment(truth='conflict')])
        self.assertEqual(p.get('disposition'),'needs_review')

    def test_contradiction_does_not_hide_remaining_unknowns(self):
        p=review_packet('FICTIONAL-A','a'*64,'b'*64,{'A':'inclusion','B':'exclusion'},[assessment(truth=False)])
        self.assertEqual(p.get('disposition'),'potential_incompatibility')
        self.assertEqual(p.get('states',{}).get('B'),'unknown')

    def test_unexpected_duplicate_or_empty_criteria_fail_closed(self):
        for criteria,assessments in [({},[]),({'A':'inclusion'},[assessment(),assessment()]),
                                    ({'A':'inclusion'},[assessment('UNDECLARED')])]:
            with self.subTest(criteria=criteria),self.assertRaises(ValueError):
                review_packet('FICTIONAL-A','a'*64,'b'*64,criteria,assessments)

if __name__=='__main__':unittest.main()
