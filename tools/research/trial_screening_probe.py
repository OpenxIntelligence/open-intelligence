"""Bounded trial-registry and screening-contract RESEARCH, not eligibility advice.

ClinicalTrials.gov/NLM supplies public registry records; no endorsement implied.
Only aggregate, time-stamped observations are published, not a current trial list.
No patient records, contact details, full criteria, attachments, model calls,
referrals or enrollment actions are published/performed. Fictional annotations
exercise downstream handling, NOT clinical extraction or judgment accuracy.

Prior-art characterization: isolated parse_criteria from ncbi-nlp/TrialGPT,
commit 1b3242cd50c153a9c324661d4a0bd94fc68a4226, US Government Work notice.
Credit: Jin et al., Nature Communications 2024, doi:10.1038/s41467-024-53081-z.
Only that hash-verified pure function is executed; no upstream module imports.
"""
from __future__ import annotations
import argparse
import ast
import copy
import hashlib
import json
import re
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlencode
from gdc_projection_probe import digest

CONDITIONS = ('lung cancer', 'breast cancer', 'acute myeloid leukemia')
UPSTREAM_COMMIT = '1b3242cd50c153a9c324661d4a0bd94fc68a4226'
UPSTREAM_BASE = 'https://raw.githubusercontent.com/ncbi-nlp/TrialGPT/' + UPSTREAM_COMMIT
UPSTREAM_BLOB = 'fe2ecbc02eb700ea2cab9db5a3aa937e0e2f419c'
NLM_TERMS = 'https://www.nlm.nih.gov/databases/download.html'
CTG_TERMS = 'https://clinicaltrials.gov/about-site/terms-conditions'
AGE = re.compile(r'(0|[1-9][0-9]*) Years')
NCT = re.compile(r'NCT[0-9]{8}')
SHA = re.compile(r'[0-9a-f]{64}')


def minimum_age_check(eligibility: dict, age: int | None) -> str:
    """Only compare an explicit whole-YEARS lower bound. Never full eligibility.

Missing/other units are unknown, not a permissive default. Deliberately no
month/day conversion or assertion that absence implies an unbounded criterion.
"""
    if type(age) is not int or age < 0:
        return 'unknown'
    raw = eligibility.get('minimumAge')
    match = AGE.fullmatch(raw) if isinstance(raw, str) else None
    if not match:
        return 'unknown'
    return 'supports_lower_bound' if age >= int(match[1]) else 'contradicts_lower_bound'


def _module(protocol: dict, name: str) -> dict:
    result = protocol.get(name, {})
    if not isinstance(result, dict):
        raise ValueError('Malformed registry module')
    return result


def registry_profile(studies: list[dict]) -> dict:
    """Inspect actual trial/site denominators without publishing source text."""
    if not isinstance(studies, list) or not studies:
        raise ValueError('Missing study sample')
    counts = Counter(studies=0, sites_total=0, sites_reported_recruiting=0,
        sites_with_other_explicit_status=0, sites_missing_status=0,
        studies_without_locations=0, studies_with_mixed_explicit_site_statuses=0,
        recruiting_studies_without_reported_recruiting_site=0,
        nonrecruiting_studies_with_reported_recruiting_site=0,
        studies_with_free_text_eligibility=0, full_eligibility_decisions=0)
    statuses, site_statuses, precision = Counter(), Counter(), Counter()
    age_checks = {str(a): Counter() for a in (17, 18, 65)}
    age_checks['unknown'] = Counter()
    min_states, max_states, records, seen = Counter(), Counter(), [], set()
    date_values = []
    for study in studies:
        if not isinstance(study, dict) or not isinstance(study.get('protocolSection'), dict):
            raise ValueError('Missing protocolSection')
        p = study['protocolSection']
        nct = _module(p, 'identificationModule').get('nctId')
        if not isinstance(nct, str) or not NCT.fullmatch(nct) or nct in seen:
            raise ValueError('Missing/duplicate registry identity')
        seen.add(nct); counts['studies'] += 1
        status = _module(p, 'statusModule')
        overall = status.get('overallStatus') or 'NOT_REPORTED'
        if not isinstance(overall, str): raise ValueError('Malformed study status')
        statuses[overall] += 1
        locations = _module(p, 'contactsLocationsModule').get('locations', [])
        if not isinstance(locations, list): raise ValueError('Malformed locations')
        local_statuses = set(); recruiting = 0
        for loc in locations:
            if not isinstance(loc, dict): raise ValueError('Malformed location')
            s = loc.get('status') or 'NOT_REPORTED'
            if not isinstance(s, str): raise ValueError('Malformed site status')
            counts['sites_total'] += 1; site_statuses[s] += 1
            if s == 'RECRUITING':
                recruiting += 1; counts['sites_reported_recruiting'] += 1
            elif s == 'NOT_REPORTED': counts['sites_missing_status'] += 1
            else: counts['sites_with_other_explicit_status'] += 1
            if s != 'NOT_REPORTED': local_statuses.add(s)
        counts['studies_without_locations'] += not locations
        counts['studies_with_mixed_explicit_site_statuses'] += len(local_statuses) > 1
        counts['recruiting_studies_without_reported_recruiting_site'] += (overall == 'RECRUITING' and recruiting == 0)
        counts['nonrecruiting_studies_with_reported_recruiting_site'] += (overall != 'RECRUITING' and overall != 'NOT_REPORTED' and recruiting > 0)
        e = _module(p, 'eligibilityModule')
        text = e.get('eligibilityCriteria')
        if text is not None and not isinstance(text, str): raise ValueError('Malformed eligibility text')
        counts['studies_with_free_text_eligibility'] += bool(text and text.strip())
        for key, tally in [('minimumAge', min_states), ('maximumAge', max_states)]:
            v = e.get(key)
            state = ('absent' if key not in e else 'null' if v is None else
                     'whole_years' if isinstance(v, str) and AGE.fullmatch(v) else 'other_unparsed')
            tally[state] += 1
        for age in (17,18,65): age_checks[str(age)][minimum_age_check(e,age)] += 1
        age_checks['unknown'][minimum_age_check(e,None)] += 1
        verified = status.get('statusVerifiedDate')
        prec = ('day' if isinstance(verified,str) and re.fullmatch(r'\d{4}-\d{2}-\d{2}', verified) else
                'month' if isinstance(verified,str) and re.fullmatch(r'\d{4}-\d{2}',verified) else
                'absent' if verified is None else 'other')
        precision[prec] += 1
        update = status.get('lastUpdatePostDateStruct', {})
        if not isinstance(update, dict): raise ValueError('Malformed update date')
        dt = update.get('date')
        if isinstance(dt,str) and re.fullmatch(r'\d{4}-\d{2}-\d{2}',dt): date_values.append(dt)
        records.append((nct,digest(e)))
    return {**dict(counts), 'overall_statuses': dict(statuses), 'site_statuses': dict(site_statuses),
        'minimum_age_states':dict(min_states),'maximum_age_states':dict(max_states),
        'structured_minimum_age_checks':{k:dict(v) for k,v in age_checks.items()},
        'verification_date_precision':dict(precision),
        'oldest_update_in_sample':min(date_values) if date_values else None,
        'newest_update_in_sample':max(date_values) if date_values else None,
        'criteria_set_sha256':digest(sorted(records)),
        'no_recruiting_site_means':'No site reported recruiting in this payload; not proof of closure or absent capacity',
        'age_check_scope':'Lower bound only; other age restrictions and free-text criteria remain unassessed',
        'record_text_or_contact_details_published':False}


def criterion_state(kind: str, truth: bool | str | None) -> str:
    """Interpret an ALREADY ANNOTATED predicate, not extract medical truth.

For an exclusion, True means the excluded condition is present. Explicit unknown
and conflict cannot become False merely because a fact is unmentioned.
"""
    if kind not in ('inclusion','exclusion'): raise ValueError('Unsupported criterion kind')
    if truth is None: return 'unknown'
    if type(truth) is str and truth == 'conflict': return 'conflict'
    if type(truth) is not bool: raise ValueError('Truth must be Boolean, unknown or conflict')
    return 'supported' if truth == (kind == 'inclusion') else 'contradicted'


def review_packet(case_id: str, patient_sha: str, trial_sha: str,
                  criteria: dict[str,str], assessments: list[dict]) -> dict:
    """Characterize downstream completeness/freshness using fictional annotations.

Hashes/refs are caller-supplied for this experiment. They do not authenticate a
source or establish clinical entailment, scope or adequate history coverage.
"""
    if not isinstance(case_id,str) or not case_id or not all(isinstance(h,str) and SHA.fullmatch(h) for h in (patient_sha,trial_sha)):
        raise ValueError('Missing case/snapshot context')
    if not isinstance(criteria,dict) or not criteria or any(not isinstance(k,str) or not k or v not in ('inclusion','exclusion') for k,v in criteria.items()):
        raise ValueError('Explicit nonempty criterion inventory required')
    if not isinstance(assessments,list): raise ValueError('Malformed assessments')
    states = {k:'unknown' for k in criteria}; reasons={k:'unassessed' for k in criteria}; seen=set()
    for a in assessments:
        if not isinstance(a,dict) or a.get('criterion_id') not in criteria or a['criterion_id'] in seen:
            raise ValueError('Unexpected or duplicate criterion assessment')
        key=a['criterion_id'];seen.add(key)
        if (a.get('case_id'),a.get('patient_sha256'),a.get('trial_sha256')) != (case_id,patient_sha,trial_sha):
            reasons[key]='source_context_changed';continue
        truth=a.get('truth'); value=criterion_state(criteria[key],truth)
        refs=a.get('evidence_refs')
        if value != 'unknown' and (not isinstance(refs,list) or not refs or any(not isinstance(r,str) or not r.strip() for r in refs)):
            reasons[key]='missing_evidence_reference';continue
        states[key]=value;reasons[key]='annotated_predicate' if value != 'unknown' else 'explicit_unknown'
    values=list(states.values())
    disposition = ('needs_review' if 'conflict' in values else
                   'potential_incompatibility' if 'contradicted' in values else
                   'needs_information' if 'unknown' in values else 'encoded_criteria_supported')
    return {'case_id':case_id,'patient_sha256':patient_sha,'trial_sha256':trial_sha,
            'criterion_inventory':copy.deepcopy(criteria),'states':states,'reasons':reasons,
            'disposition':disposition,'final_eligibility':None,
            'scope':'Only explicitly encoded criteria; no protocol-completeness or enrollment judgment'}


def packet_is_current(packet: dict, case_id: str, patient_sha: str, trial_sha: str) -> bool:
    return isinstance(packet,dict) and (packet.get('case_id'),packet.get('patient_sha256'),packet.get('trial_sha256')) == (case_id,patient_sha,trial_sha)


def fictional_experiment() -> dict:
    """Small declared counterexamples, not a clinical accuracy benchmark."""
    inventory={'I1':'inclusion','E1':'exclusion'}
    def annotation(cid,truth,**change):
        a={'criterion_id':cid,'truth':truth,'case_id':'FICTIONAL-A',
           'patient_sha256':'a'*64,'trial_sha256':'b'*64,'evidence_refs':['fictional-note#1']}
        a.update(change);return a
    cases=[('explicit-negative-exclusion', [annotation('I1',True),annotation('E1',False)],'encoded_criteria_supported'),
           ('missing-exclusion',[annotation('I1',True)],'needs_information'),
           ('unknown-exclusion',[annotation('I1',True),annotation('E1',None)],'needs_information'),
           ('present-exclusion',[annotation('I1',True),annotation('E1',True)],'potential_incompatibility'),
           ('conflicting-exclusion',[annotation('I1',True),annotation('E1','conflict')],'needs_review'),
           ('old-patient-snapshot',[annotation('I1',True),annotation('E1',False,patient_sha256='c'*64)],'needs_information'),
           ('old-trial-snapshot',[annotation('I1',True),annotation('E1',False,trial_sha256='c'*64)],'needs_information'),
           ('wrong-case',[annotation('I1',True),annotation('E1',False,case_id='FICTIONAL-B')],'needs_information')]
    out=[]
    for name,annotations,want in cases:
        p=review_packet('FICTIONAL-A','a'*64,'b'*64,inventory,annotations)
        naive=not any(a['criterion_id']=='E1' and a.get('truth') is True for a in annotations)
        out.append({'scenario':name,'expected':want,'actual':p['disposition'],
                    'states':p['states'],'naive_missing_as_false_pass':naive,
                    'expected_behavior_matched':p['disposition']==want,'final_eligibility':p['final_eligibility']})
    return {'scope':'Eight authored counterexamples; no model or clinical accuracy evaluation',
            'scenarios':out,'expected_behavior_matched':sum(x['expected_behavior_matched'] for x in out),
            'naive_pass_but_context_or_evidence_unresolved':sum(x['naive_missing_as_false_pass'] and x['actual'] in ('needs_information','needs_review') for x in out)}


def upstream_parser_experiment() -> dict:
    from public_evidence_probe import fetch_bytes
    raw,receipt=fetch_bytes(UPSTREAM_BASE+'/trialgpt_matching/TrialGPT.py')
    actual=hashlib.sha1(b'blob '+str(len(raw)).encode()+b'\0'+raw).hexdigest()
    if actual != UPSTREAM_BLOB: raise ValueError('Unexpected upstream source; inspect before execution')
    notice,license_receipt=fetch_bytes(UPSTREAM_BASE+'/LICENSE')
    if b'PUBLIC DOMAIN NOTICE' not in notice: raise ValueError('Upstream notice changed')
    tree=ast.parse(raw.decode('utf-8'))
    nodes=[n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name=='parse_criteria']
    if len(nodes)!=1:raise ValueError('Parser not found')
    ns={'__builtins__':{'len':len}}
    # Execute only the inspected pure helper from a fixed source blob; not imports,
    # provider clients, other functions, patient data or API keys.
    exec(compile(ast.Module(body=nodes,type_ignores=[]),'<pinned-pure-helper>','exec'),ns)
    examples=[('blank-line-separated-heading','Inclusion Criteria\n\nALPHA_18 required.\n\nBETA_MARKER required.'),
              ('heading-attached-to-first-item','Inclusion Criteria\nALPHA_18 required.\n\nBETA_MARKER required.'),
              ('single-heading-and-list-block','Inclusion Criteria\n* ALPHA_18 required.\n* BETA_MARKER required.'),
              ('heading-words-inside-substantive-text','ALPHA_18 required to satisfy inclusion criteria.\n\nBETA_MARKER required.')]
    results=[]
    for name,text in examples:
        rendered=ns['parse_criteria'](text)
        retained=sum(token in rendered for token in ('ALPHA_18','BETA_MARKER'))
        results.append({'format':name,'input_marker_count':2,'retained_marker_count':retained,
                        'marker_count_not_retained':2-retained,'input_sha256':digest(text),'output_sha256':digest(rendered)})
    return {'source_receipt':receipt,'license_receipt':license_receipt,'git_blob_sha1':actual,
            'examples':results,'model_calls':0,
            'limit':'Input-format characterization of the pinned research helper, not hosted TrialGPT behavior or a clinical error rate',
            'attribution':'Jin et al., Matching Patients to Clinical Trials with Large Language Models, Nature Communications 2024; US Government Work'}


def run_probe() -> dict:
    from public_evidence_probe import fetch_bytes
    result={'retrieved_at':datetime.now(timezone.utc).isoformat(),
        'purpose':'Trial registry availability/criterion contract research; not patient matching or clinical eligibility',
        'sampling':'First 30 results per condition by LastUpdatePostDate descending, overall RECRUITING; not random, may overlap',
        'source':'ClinicalTrials.gov / U.S. National Library of Medicine. No NLM endorsement.',
        'terms_references':[NLM_TERMS,CTG_TERMS],
        'rights_scope':'Read public API metadata for aggregate research; no full text/attachments/contact republication or blanket licensing claim',
        'freshness':'Time-stamped snapshot, not guaranteed current or accurate trial availability',
        'fictional':fictional_experiment(),'registry':{}}
    union=set();appearances=0
    for condition in CONDITIONS:
        params={'query.cond':condition,'filter.overallStatus':'RECRUITING','pageSize':30,
                'format':'json','countTotal':'true','sort':'LastUpdatePostDate:desc'}
        try:
            raw,receipt=fetch_bytes('https://clinicaltrials.gov/api/v2/studies?'+urlencode(params))
            data=json.loads(raw);studies=data['studies']
            if type(data.get('totalCount')) is not int or len(studies)!=min(30,data['totalCount']):
                raise ValueError('Incomplete bounded registry response')
            profile=registry_profile(studies)
            if set(profile['overall_statuses'])!={'RECRUITING'}: raise ValueError('Status filter not satisfied')
            union.update(s['protocolSection']['identificationModule']['nctId'] for s in studies);appearances+=len(studies)
            result['registry'][condition]={'status':'tested','query':params,'total_search_results':data['totalCount'],
                'receipt':receipt,'profile':profile}
        except Exception as exc:
            result['registry'][condition]={'status':'failed','query':params,'error_type':type(exc).__name__,'reason':str(exc)}
    result['distinct_retrieved_studies']=len(union);result['study_appearances_across_queries']=appearances
    result['repeated_appearances_across_queries']=appearances-len(union)
    try:result['prior_art']={'status':'tested',**upstream_parser_experiment()}
    except Exception as exc:result['prior_art']={'status':'failed','error_type':type(exc).__name__,'reason':str(exc)}
    result['status']='complete' if all(v['status']=='tested' for v in result['registry'].values()) and result['prior_art']['status']=='tested' and all(x['expected_behavior_matched'] for x in result['fictional']['scenarios']) else 'partial'
    return result


def main() -> None:
    ap=argparse.ArgumentParser();ap.add_argument('--output',required=True,type=Path);args=ap.parse_args()
    result=run_probe();args.output.parent.mkdir(parents=True,exist_ok=True)
    args.output.write_text(json.dumps(result,indent=2),encoding='utf-8');print(json.dumps(result,indent=2))
    if result['status']!='complete':raise SystemExit(2)

if __name__=='__main__':main()
