"""Research-only semantic audit; not a clinical importer, FHIR exporter or model.

GDC open case metadata remains in memory. Only aggregate counts and receipts are
published. No reidentification, subject linkage, controlled files or LLM calls.
GDC policy: https://gdc.cancer.gov/analyze-data/data-analysis-policies
Meaning: pinned NCI-GDC dictionary plus FHIR R4 MedicationStatement/Administration.
"""
from __future__ import annotations
import argparse
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
        elif isinstance(value, (int, float)):
            label = 'number' if math.isfinite(value) and float(value).is_integer() else 'invalid'
        else:
            label = 'unparsed'
    else:
        label = 'value'
    result['state'] = label
    return result


def anchor_known(anchor: dict) -> bool:
    return anchor['state'] == 'value' and isinstance(anchor['raw'], str)


def treatment(case: dict, obj: dict, path: str) -> dict:
    raw = state(obj, 'treatment_or_therapy')
    receipt = raw['state']
    if receipt == 'value':
        token = raw['raw'].strip().casefold() if isinstance(raw['raw'], str) else None
        receipt = {'yes': 'reported_yes', 'no': 'reported_no'}.get(token, 'unrecognized')
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
    return {'evidence_kind': 'registry_treatment_assertion', 'source_path': path,
            'receipt': receipt, 'receipt_source': raw, 'anchor': anchor,
            'start': start, 'end': end, 'placement': placement,
            'prescribed_dose': state(obj, 'prescribed_dose'),
            'treatment_dose': state(obj, 'treatment_dose')}


def followup(case: dict, obj: dict, path: str) -> dict:
    time = state(obj, 'days_to_follow_up', True)
    anchor = state(case, 'index_date')
    placement = 'relative_point' if time['state'] == 'number' and anchor_known(anchor) else 'unplaced'
    if time['state'] in ('invalid', 'unparsed'):
        placement = 'held_invalid_time'
    return {'evidence_kind': 'registry_followup_assertion', 'source_path': path,
            'time': time, 'anchor': anchor, 'placement': placement}


def audit(cases: list[dict]) -> dict:
    before = digest(cases)
    receipts, placements, anchors, starts, ends = (Counter() for _ in range(5))
    f_times, f_places = Counter(), Counter()
    control = Counter(labeled_records=0, explicit_no=0, not_affirmative=0)
    counts = Counter(treatment_records=0, followup_records=0, positive_relative_intervals=0,
                     positive_records_without_numeric_start=0, nonpositive_with_numeric_start=0,
                     prescribed_without_treatment_dose=0, reversed_numeric_pairs=0,
                     affirmative_with_reversed_pair=0, start_at_capping_boundary=0,
                     false_day_zero_if_missing_defaulted=0)
    with Projection(cases) as db:
        roots = {r['case_key']: json.loads(r['payload']) for r in db.conn.execute("SELECT * FROM nodes WHERE kind='case'")}
        for row in db.conn.execute("SELECT * FROM nodes WHERE kind IN ('treatment','follow_up')"):
            obj = json.loads(row['payload']); case = roots[row['case_key']]
            if row['kind'] == 'follow_up':
                r = followup(case, obj, row['path'])
                counts['followup_records'] += 1
                f_times[r['time']['state']] += 1; f_places[r['placement']] += 1
                continue
            r = treatment(case, obj, row['path'])
            counts['treatment_records'] += 1
            receipts[r['receipt']] += 1; placements[r['placement']] += 1
            anchors[r['anchor']['state']] += 1; starts[r['start']['state']] += 1; ends[r['end']['state']] += 1
            yes = r['receipt'] == 'reported_yes'
            counts['positive_relative_intervals'] += r['placement'] == 'relative_interval'
            counts['positive_records_without_numeric_start'] += yes and r['start']['state'] != 'number'
            counts['nonpositive_with_numeric_start'] += not yes and r['start']['state'] == 'number'
            counts['prescribed_without_treatment_dose'] += (r['prescribed_dose']['state'] == 'value' and r['treatment_dose']['state'] != 'value')
            counts['false_day_zero_if_missing_defaulted'] += r['start']['state'] in ('absent', 'null')
            counts['start_at_capping_boundary'] += r['start']['state'] == 'number' and abs(r['start']['raw']) == 32872
            if r['start']['state'] == r['end']['state'] == 'number' and r['end']['raw'] < r['start']['raw']:
                counts['reversed_numeric_pairs'] += 1
                counts['affirmative_with_reversed_pair'] += yes
            labeled = any(state(obj, key)['state'] == 'value' and isinstance(obj.get(key), str)
                          for key in ('treatment_type', 'treatment_type_administered'))
            if labeled:
                control['labeled_records'] += 1
                control['explicit_no'] += r['receipt'] == 'reported_no'
                control['not_affirmative'] += not yes
    return {'cases': len(cases), **dict(counts), 'receipt_states': dict(receipts),
            'treatment_placements': dict(placements), 'anchor_states_on_treatments': dict(anchors),
            'start_states': dict(starts), 'end_states': dict(ends),
            'followup_time_states': dict(f_times), 'followup_placements': dict(f_places),
            'type_only_control': dict(control), 'source_unchanged': before == digest(cases),
            'denominator': 'Source object occurrences, not adjudicated administrations or encounters',
            'calendar_dates_generated': 0, 'fhir_resources_generated': 0,
            'clinical_decisions_generated': 0, 'row_level_records_published': False}


def run_probe() -> dict:
    from public_evidence_probe import fetch_bytes
    raw, mapping_receipt = fetch_bytes('https://api.gdc.cancer.gov/cases/_mapping')
    validate_expansions(EXPAND, json.loads(raw).get('expand'))
    terms, terms_receipt = fetch_bytes(TERMS_URL)
    required = ('treatment_type:', 'treatment_or_therapy:', 'index_date:', 'days_to_treatment_start:', 'days_to_follow_up:')
    if not all(name in terms.decode('utf-8') for name in required):
        raise ValueError('Pinned semantic reference missing expected terms')
    result = {'purpose': 'Source-semantic characterization; not clinical validation or FHIR conformance',
              'sampling': 'First 100 case IDs ascending per project; not random or representative',
              'mapping_receipt': mapping_receipt, 'semantic_reference': terms_receipt,
              'dictionary_commit': DICT_COMMIT, 'experiments': {}}
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
