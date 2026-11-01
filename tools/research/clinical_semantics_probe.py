"""Research-only semantic audit; not a clinical importer, FHIR exporter or model.

GDC open case metadata remains in memory. Only aggregate counts and receipts are
published. No reidentification, subject linkage, controlled files or LLM calls.
GDC policy: https://gdc.cancer.gov/analyze-data/data-analysis-policies
Meaning: pinned NCI-GDC dictionary plus FHIR R4 MedicationStatement/Administration.
"""
from __future__ import annotations
import argparse
import copy
import re
import json
import math
from collections import Counter
from pathlib import Path
from urllib.parse import urlencode
from gdc_projection_probe import Projection, PROJECTS, EXPAND, canonical, digest, validate_expansions

DICT_COMMIT = '88d66b0fe361aa638977850c180bd9130d705924'
TERMS_URL = ('https://raw.githubusercontent.com/NCI-GDC/gdcdictionary/' + DICT_COMMIT +
             '/src/gdcdictionary/schemas/_terms.yaml')
SENTINELS = {'unknown': 'unknown', 'not reported': 'not_reported',
             'not applicable': 'not_applicable', 'n/a': 'not_applicable',
             'not available': 'unavailable', '': 'empty'}


# Manually cross-checked against case.yaml at DICT_COMMIT. Not a full GDC validator.
INDEX_CATEGORIES = frozenset({'Diagnosis', 'First Patient Visit', 'First Treatment',
    'Initial Genomic Sequencing', 'Recurrence', 'Sample Procurement', 'Study Enrollment'})
# The pinned treatment/follow_up schemas define these inclusive day-count bounds.
DAY_LIMIT = 32872
SOURCE_PATH = re.compile(r'^/(?:diagnoses/(?:0|[1-9][0-9]*)/treatments/(?:0|[1-9][0-9]*)|follow_ups/(?:0|[1-9][0-9]*))$')


def state(obj: dict, field: str, numeric: bool = False) -> dict:
    """Preserve raw state; never coerce text or turn absence into day zero."""
    value = obj.get(field)
    result = {'source_field': field, 'raw': value}
    if field not in obj:
        label = 'absent'
    elif value is None:
        label = 'null'
    elif isinstance(value, str) and value.strip().casefold() in SENTINELS:
        label = SENTINELS[value.strip().casefold()]
    elif numeric:
        if isinstance(value, bool):
            label = 'invalid'
        elif isinstance(value, int):
            label = 'number' if -DAY_LIMIT <= value <= DAY_LIMIT else 'invalid'
        elif isinstance(value, float):
            label = 'number' if math.isfinite(value) and value.is_integer() and -DAY_LIMIT <= value <= DAY_LIMIT else 'invalid'
        else:
            label = 'unparsed'
    else:
        label = 'value'
    result['state'] = label
    return result


def anchor_known(anchor: dict) -> bool:
    return anchor['state'] == 'value' and isinstance(anchor['raw'], str) and anchor['raw'] in INDEX_CATEGORIES


def treatment(case: dict, obj: dict, path: str) -> dict:
    raw = state(obj, 'treatment_or_therapy')
    receipt = raw['state']
    if receipt == 'value':
        token = raw['raw'].strip().casefold() if isinstance(raw['raw'], str) else None
        receipt = {'yes': 'reported_yes', 'no': 'reported_no'}.get(token, 'unrecognized')
    legacy_type = state(obj, 'treatment_type')
    administered_type = state(obj, 'treatment_type_administered')
    administered_label = (administered_type['state'] == 'value' and
                          isinstance(administered_type['raw'], str))
    consistency = 'indicator_only'
    if administered_label:
        consistency = ('indicator_and_administered_type' if receipt == 'reported_yes' else
                       'conflicting_source_fields' if receipt == 'reported_no' else
                       'administered_type_without_affirmative_indicator')
    start = state(obj, 'days_to_treatment_start', True)
    end = state(obj, 'days_to_treatment_end', True)
    anchor = state(case, 'index_date')
    placement = 'not_positive'
    if receipt == 'reported_yes':
        placement = 'unplaced'
        if start['state'] in ('invalid', 'unparsed') or end['state'] in ('invalid', 'unparsed'):
            placement = 'held_invalid_time'
        elif anchor_known(anchor) and start['state'] == 'number':
            placement = 'relative_start_only'
            if end['state'] == 'number':
                placement = 'relative_interval' if end['raw'] >= start['raw'] else 'held_reversed_interval'
    if administered_label and receipt != 'reported_yes':
        # The newer field has stronger semantics than legacy treatment_type.
        # Preserve its assertion and disagreement rather than silently choosing.
        placement = 'needs_receipt_review'
    return {'evidence_kind': 'registry_treatment_assertion', 'source_path': path,
            'receipt': receipt, 'receipt_source': raw, 'anchor': anchor,
            'legacy_type': legacy_type, 'administered_type': administered_type,
            'receipt_consistency': consistency,
            'start': start, 'end': end, 'placement': placement,
            'prescribed_dose': state(obj, 'prescribed_dose'),
            'treatment_dose': state(obj, 'treatment_dose'),
            'prescribed_dose_units': state(obj, 'prescribed_dose_units'),
            'treatment_dose_units': state(obj, 'treatment_dose_units')}


def followup(case: dict, obj: dict, path: str) -> dict:
    time = state(obj, 'days_to_follow_up', True)
    anchor = state(case, 'index_date')
    placement = 'relative_point' if time['state'] == 'number' and anchor_known(anchor) else 'unplaced'
    if time['state'] in ('invalid', 'unparsed'):
        placement = 'held_invalid_time'
    return {'evidence_kind': 'registry_followup_assertion', 'source_path': path,
            'time': time, 'anchor': anchor, 'placement': placement}


def source_at(case: dict, path: str) -> dict:
    """Resolve only supported occurrence paths, never guess identity or location."""
    if not isinstance(path, str) or not SOURCE_PATH.fullmatch(path):
        raise ValueError('Unsupported clinical source path')
    value = case
    try:
        for part in path[1:].split('/'):
            value = value[int(part)] if isinstance(value, list) else value[part]
    except (KeyError, IndexError, TypeError, ValueError) as exc:
        raise ValueError('Clinical source path does not resolve') from exc
    if not isinstance(value, dict):
        raise ValueError('Clinical source path is not an object')
    return value


def make_claim(case: dict, path: str) -> dict:
    """Bind an attributed statement to exact source content. In-memory only.

    Hashes detect mismatched content, not authenticity or clinical correctness.
    Occurrence paths and whole-case fingerprints are snapshot-local; this is not
    cross-revision identity resolution or selective dependency invalidation.
    """
    if not isinstance(case, dict) or not isinstance(case.get('case_id'), str) or not case['case_id']:
        raise ValueError('Source case identity missing')
    obj = source_at(case, path)
    builder = followup if path.startswith('/follow_ups/') else treatment
    result = builder(case, obj, path)
    result.update(source_case_id=case['case_id'], source_case_sha256=digest(case),
                  source_record_sha256=digest(obj), dictionary_commit=DICT_COMMIT,
                  temporal_basis='Source-reported relative offsets; privacy transformations may apply',
                  clinically_verified=False)
    return copy.deepcopy(result)


def verify_claim(case: dict, claim: dict) -> bool:
    """Check source attachment and deterministic derivation, not clinical truth."""
    if not isinstance(claim, dict):
        return False
    try:
        return canonical(claim) == canonical(make_claim(case, claim.get('source_path')))
    except (ValueError, KeyError, TypeError):
        return False


def audit(cases: list[dict]) -> dict:
    before = digest(cases)
    receipts, placements, anchors, starts, ends = (Counter() for _ in range(5))
    f_times, f_places = Counter(), Counter()
    control = Counter(labeled_records=0, explicit_no=0, not_affirmative=0)
    newer = Counter(labeled_records=0, indicator_yes=0, indicator_no=0, indicator_other=0)
    consistency = Counter()
    counts = Counter(treatment_records=0, followup_records=0, positive_relative_intervals=0,
                     positive_records_without_numeric_start=0, nonpositive_with_numeric_start=0,
                     prescribed_without_treatment_dose=0, reversed_numeric_pairs=0,
                     affirmative_with_reversed_pair=0, start_at_schema_boundary=0,
                     source_claims_verified=0, source_claim_verification_failures=0,
                     false_day_zero_if_missing_defaulted=0)
    with Projection(cases) as db:
        roots = {case['case_id']: case for case in cases}
        for row in db.conn.execute("SELECT * FROM nodes WHERE kind IN ('treatment','follow_up')"):
            obj = json.loads(row['payload']); case = roots[row['case_key']]
            r = make_claim(case, row['path'])
            if canonical(obj) != canonical(source_at(case, row['path'])) or not verify_claim(case, r):
                raise ValueError('Derived assertion does not match original source')
            counts['source_claims_verified'] += 1
            if row['kind'] == 'follow_up':
                counts['followup_records'] += 1
                f_times[r['time']['state']] += 1; f_places[r['placement']] += 1
                continue
            counts['treatment_records'] += 1
            receipts[r['receipt']] += 1; placements[r['placement']] += 1
            anchors[r['anchor']['state']] += 1; starts[r['start']['state']] += 1; ends[r['end']['state']] += 1
            yes = r['receipt'] == 'reported_yes'
            counts['positive_relative_intervals'] += r['placement'] == 'relative_interval'
            counts['positive_records_without_numeric_start'] += yes and r['start']['state'] != 'number'
            counts['nonpositive_with_numeric_start'] += not yes and r['start']['state'] == 'number'
            counts['prescribed_without_treatment_dose'] += (r['prescribed_dose']['state'] == 'value' and r['treatment_dose']['state'] != 'value')
            counts['false_day_zero_if_missing_defaulted'] += r['start']['state'] in ('absent', 'null')
            counts['start_at_schema_boundary'] += r['start']['state'] == 'number' and abs(r['start']['raw']) == 32872
            if r['start']['state'] == r['end']['state'] == 'number' and r['end']['raw'] < r['start']['raw']:
                counts['reversed_numeric_pairs'] += 1
                counts['affirmative_with_reversed_pair'] += yes
            consistency[r['receipt_consistency']] += 1
            new_label = r['administered_type']['state'] == 'value' and isinstance(r['administered_type']['raw'], str)
            if new_label:
                newer['labeled_records'] += 1
                newer['indicator_yes' if yes else 'indicator_no' if r['receipt'] == 'reported_no' else 'indicator_other'] += 1
            labeled = r['legacy_type']['state'] == 'value' and isinstance(r['legacy_type']['raw'], str)
            if labeled:
                control['labeled_records'] += 1
                control['explicit_no'] += r['receipt'] == 'reported_no'
                control['not_affirmative'] += not yes
    return {'cases': len(cases), **dict(counts), 'receipt_states': dict(receipts),
            'treatment_placements': dict(placements), 'anchor_states_on_treatments': dict(anchors),
            'start_states': dict(starts), 'end_states': dict(ends),
            'followup_time_states': dict(f_times), 'followup_placements': dict(f_places),
            'type_only_control': dict(control), 'administered_type_comparison': dict(newer),
            'receipt_consistency_states': dict(consistency),
            'receipt_basis': 'treatment_or_therapy indicator; newer administered-type assertion retained separately',
            'source_unchanged': before == digest(cases),
            'denominator': 'Source object occurrences, not adjudicated administrations or encounters',
            'calendar_dates_generated': 0, 'fhir_resources_generated': 0,
            'clinical_decisions_generated': 0, 'row_level_records_published': False,
            'temporal_precision': 'Reported offsets only; privacy transformations may change actual elapsed time',
            'source_verification_scope': 'Snapshot-local content/derivation, not authentication or clinical adjudication'}


def run_probe() -> dict:
    from public_evidence_probe import fetch_bytes
    raw, mapping_receipt = fetch_bytes('https://api.gdc.cancer.gov/cases/_mapping')
    validate_expansions(EXPAND, json.loads(raw).get('expand'))
    terms, terms_receipt = fetch_bytes(TERMS_URL)
    required = ('treatment_type:', 'treatment_type_administered:', 'treatment_or_therapy:', 'index_date:', 'days_to_treatment_start:', 'days_to_follow_up:')
    if not all(name in terms.decode('utf-8') for name in required):
        raise ValueError('Pinned semantic reference missing expected terms')
    schema_receipts = {}
    for schema in ('case', 'treatment', 'follow_up'):
        _, schema_receipts[schema] = fetch_bytes(
            'https://raw.githubusercontent.com/NCI-GDC/gdcdictionary/' + DICT_COMMIT +
            '/src/gdcdictionary/schemas/' + schema + '.yaml')
    result = {'purpose': 'Source-semantic characterization; not clinical validation or FHIR conformance',
              'sampling': 'First 100 case IDs ascending per project; not random or representative',
              'mapping_receipt': mapping_receipt, 'semantic_reference': terms_receipt,
              'dictionary_commit': DICT_COMMIT, 'schema_receipts': schema_receipts,
              'selected_source_rules': {'index_date_categories': sorted(INDEX_CATEGORIES),
                  'day_offset_minimum': -DAY_LIMIT, 'day_offset_maximum': DAY_LIMIT,
                  'qualification': 'Selected manually inspected field constraints; not full GDC/FHIR conformance'},
              'experiments': {}}
    for project in PROJECTS:
        params = {'filters': canonical({'op': 'in', 'content': {'field': 'project.project_id', 'value': [project]}}),
                  'size': 100, 'sort': 'case_id:asc', 'expand': ','.join(EXPAND)}
        try:
            raw, receipt = fetch_bytes('https://api.gdc.cancer.gov/cases?' + urlencode(params))
            data = json.loads(raw)['data']; cases = data['hits']
            if not cases or len(cases) != min(100, data['pagination']['total']):
                raise ValueError('Incomplete bounded response')
            profile = audit(cases)
            if not profile['source_unchanged']:
                raise ValueError('Source mutation')
            result['experiments'][project] = {'status': 'tested', 'query': params, 'receipt': receipt, 'profile': profile}
        except Exception as exc:
            result['experiments'][project] = {'status': 'failed', 'error_type': type(exc).__name__}
    result['status'] = 'complete' if all(r['status'] == 'tested' for r in result['experiments'].values()) else 'partial'
    return result


def main() -> None:
    p = argparse.ArgumentParser(); p.add_argument('--output', required=True, type=Path); args = p.parse_args()
    try:
        result = run_probe()
    except Exception as exc:
        result = {'status': 'failed', 'error_type': type(exc).__name__}
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2), encoding='utf-8')
    print(json.dumps(result, indent=2))
    if result['status'] != 'complete': raise SystemExit(2)

if __name__ == '__main__': main()
