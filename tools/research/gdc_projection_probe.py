"""Research-only GDC hierarchy/temporal probe. No clinical importer or new store.

Public clinical/biospecimen metadata stays in RAM/in-memory SQLite and is never
printed, committed, or included in artifacts. Only aggregate receipts leave the
probe. No controlled files, cross-cohort identification, LLM calls, or inference.
GDC terms: https://gdc.cancer.gov/analyze-data/data-analysis-policies
"""
from __future__ import annotations

import argparse
import copy
import hashlib
import json
import math
import sqlite3
from collections import Counter
from pathlib import Path
from urllib.parse import urlencode

# Decompose named relationships only. Unknown fields remain intact JSON payloads.
RELATIONS = {
    'case': {'diagnoses': 'diagnosis', 'samples': 'sample', 'follow_ups': 'follow_up'},
    'diagnosis': {'treatments': 'treatment'},
    'sample': {'portions': 'portion', 'analytes': 'analyte', 'aliquots': 'aliquot'},
    'portion': {'analytes': 'analyte'},
    'analyte': {'aliquots': 'aliquot'},
}
EXPAND = ('diagnoses', 'diagnoses.treatments', 'follow_ups', 'samples',
          'samples.portions', 'samples.portions.analytes',
          'samples.portions.analytes.aliquots')
PROJECTS = ('TCGA-LUAD', 'TCGA-BRCA', 'TCGA-LAML')


def canonical(value) -> str:
    return json.dumps(value, sort_keys=True, separators=(',', ':'), ensure_ascii=False, allow_nan=False)


def digest(value) -> str:
    return hashlib.sha256(canonical(value).encode()).hexdigest()


class Projection:
    """Disposable relational projection with case-scoped parent constraints.

    Paths identify occurrences, not inferred biological equivalence. Repeated
    source IDs are retained, never silently deduplicated. This is not auth.
    """
    def __init__(self, cases: list[dict]):
        self.original_digest = digest(cases)
        self.conn = sqlite3.connect(':memory:')
        self.conn.row_factory = sqlite3.Row
        self.conn.execute('PRAGMA foreign_keys=ON')
        self.conn.execute('''CREATE TABLE nodes (
            case_key TEXT NOT NULL, path TEXT NOT NULL, kind TEXT NOT NULL,
            parent TEXT, slot TEXT, ordinal INTEGER NOT NULL,
            payload TEXT NOT NULL,
            PRIMARY KEY(case_key,path),
            UNIQUE(case_key,parent,slot,ordinal),
            FOREIGN KEY(case_key,parent) REFERENCES nodes(case_key,path),
            CHECK ((parent IS NULL AND path='' AND kind='case' AND slot IS NULL)
                OR (parent IS NOT NULL AND path<>'' AND kind<>'case' AND slot IS NOT NULL))
        )''')
        seen = set()
        try:
            with self.conn:
                for ordinal, case in enumerate(cases):
                    key = case.get('case_id') if isinstance(case, dict) else None
                    if not isinstance(key, str) or not key or key in seen:
                        raise ValueError('Missing or duplicate case identifier')
                    seen.add(key)
                    self._insert(case, key, '', 'case', None, None, ordinal)
        except Exception:
            self.conn.close()
            raise

    def _insert(self, obj, case, path, kind, parent, slot, ordinal):
        if not isinstance(obj, dict):
            raise ValueError('Expected object in clinical collection')
        payload = copy.deepcopy(obj)
        children = []
        for field, child_kind in RELATIONS.get(kind, {}).items():
            values = obj.get(field)
            if values is None:  # Preserve absent versus explicitly null.
                continue
            if not isinstance(values, list):
                raise ValueError('Expected list or null in clinical collection')
            payload[field] = []  # Empty collection is still explicitly present.
            children.extend((v, field, child_kind, i) for i, v in enumerate(values))
        self.conn.execute('INSERT INTO nodes VALUES(?,?,?,?,?,?,?)',
                          (case, path, kind, parent, slot, ordinal, canonical(payload)))
        for child, field, child_kind, i in children:
            self._insert(child, case, f'{path}/{field}/{i}', child_kind, path, field, i)

    def _restore_node(self, row):
        obj = json.loads(row['payload'])
        for child in self.conn.execute(
                'SELECT * FROM nodes WHERE case_key=? AND parent=? ORDER BY slot,ordinal',
                (row['case_key'], row['path'])).fetchall():
            obj[child['slot']].append(self._restore_node(child))
        return obj

    def restore(self) -> list[dict]:
        return [self._restore_node(r) for r in self.conn.execute(
            'SELECT * FROM nodes WHERE parent IS NULL ORDER BY ordinal').fetchall()]

    def intact(self) -> bool:
        return digest(self.restore()) == self.original_digest

    def __enter__(self):
        return self

    def __exit__(self, *_):
        self.conn.close()


def compare(old: Projection, new: Projection) -> dict:
    a = {c['case_id']: digest(c) for c in old.restore()}
    b = {c['case_id']: digest(c) for c in new.restore()}
    common = a.keys() & b.keys()
    return {'unchanged': sum(a[k] == b[k] for k in common),
            'changed': sum(a[k] != b[k] for k in common),
            'added': len(b.keys() - a.keys()), 'removed': len(a.keys() - b.keys())}


def offset(value) -> dict:
    if isinstance(value, bool):
        return {'state': 'invalid'}
    if isinstance(value, (int, float)):
        return {'state': 'numeric', 'value': value} if math.isfinite(value) else {'state': 'invalid'}
    return {'state': 'unresolved'}  # Never coerce strings or replace absence with zero.


def validate_expansions(wanted, supported) -> None:
    if not isinstance(supported, list) or not all(isinstance(x, str) for x in supported):
        raise ValueError('Expansion schema unavailable')
    if not set(wanted).issubset(supported):
        raise ValueError('Requested expansion is not advertised by the endpoint')


def audit(cases: list[dict]) -> dict:
    with Projection(cases) as db:
        kinds = ('case', 'diagnosis', 'sample', 'portion', 'analyte', 'aliquot', 'treatment', 'follow_up')
        counts = {k: db.conn.execute('SELECT COUNT(*) FROM nodes WHERE kind=?', (k,)).fetchone()[0]
                  for k in kinds}
        times = Counter(treatments=0, numeric_start=0, numeric_end=0,
                        unresolved_start=0, unresolved_end=0, invalid_start=0, invalid_end=0,
                        numeric_pairs=0, end_before_start=0, zero_start=0, negative_start=0,
                        numeric_followup=0)
        for row in db.conn.execute("SELECT kind,payload FROM nodes WHERE kind IN ('treatment','follow_up')"):
            obj = json.loads(row['payload'])
            if row['kind'] == 'follow_up':
                times['numeric_followup'] += offset(obj.get('days_to_follow_up'))['state'] == 'numeric'
                continue
            times['treatments'] += 1
            start = offset(obj.get('days_to_treatment_start'))
            end = offset(obj.get('days_to_treatment_end'))
            times[start['state'] + '_start'] += 1
            times[end['state'] + '_end'] += 1
            if start['state'] == 'numeric':
                times['zero_start'] += start['value'] == 0
                times['negative_start'] += start['value'] < 0
            if start['state'] == end['state'] == 'numeric':
                times['numeric_pairs'] += 1
                times['end_before_start'] += end['value'] < start['value']
        lengths = [(len(c.get('diagnoses') or []), len(c.get('samples') or [])) for c in cases]
        legacy_followups = sum(len(d.get('follow_ups') or []) for c in cases
                               for d in (c.get('diagnoses') or []))
        return {'counts': counts, 'roundtrip_canonical_json_equal': db.intact(),
                'foreign_key_violations': len(db.conn.execute('PRAGMA foreign_key_check').fetchall()),
                'naive_inner_join_rows': sum(d * s for d, s in lengths),
                'cases_lost_by_inner_join': sum(d == 0 or s == 0 for d, s in lengths),
                'legacy_nested_followup_count': legacy_followups,
                'time': dict(times), 'calendar_dates_inferred': False,
                'administrations_inferred': False, 'clinical_interpretation_performed': False,
                'row_level_records_published': False}


def run_probe() -> dict:
    # Reuse the existing bounded network helper; it never prints raw responses.
    from public_evidence_probe import fetch_bytes
    raw, schema_receipt = fetch_bytes('https://api.gdc.cancer.gov/cases/_mapping')
    mapping = json.loads(raw)
    supported = mapping.get('expand')
    validate_expansions(EXPAND, supported)
    report = {'purpose': 'Structural research only; not a clinical importer or adopted database',
              'schema': {'receipt': schema_receipt,
                         'requested_expansions_verified': list(EXPAND),
                         'legacy_followup_expansion_advertised': 'diagnoses.follow_ups' in supported},
              'sampling': 'First 100 case IDs per project, ascending; not random or representative',
              'rights': 'GDC open metadata policy; no reidentification, controlled data or cross-cohort linkage',
              'experiments': {}}
    for project in PROJECTS:
        params = {'filters': canonical({'op': 'in', 'content': {
                  'field': 'project.project_id', 'value': [project]}}),
                  'size': 100, 'sort': 'case_id:asc', 'expand': ','.join(EXPAND)}
        try:
            raw, receipt = fetch_bytes('https://api.gdc.cancer.gov/cases?' + urlencode(params))
            data = json.loads(raw)['data']
            cases = data['hits']; total = data['pagination']['total']
            if not cases or len(cases) != min(100, total):
                raise ValueError('Incomplete bounded response')
            result = audit(cases)
            if not result['roundtrip_canonical_json_equal'] or result['foreign_key_violations']:
                raise ValueError('Projection integrity failure')
            report['experiments'][project] = {'status': 'tested', 'query': params,
                'receipt': receipt, 'project_case_total_at_retrieval': total, 'profile': result}
            if project == 'TCGA-LUAD':
                # Controlled query comparison: only the follow-up expansion changes.
                legacy_params = dict(params)
                legacy_params['expand'] = ','.join('diagnoses.follow_ups' if p == 'follow_ups' else p for p in EXPAND)
                try:
                    prior, prior_receipt = fetch_bytes('https://api.gdc.cancer.gov/cases?' + urlencode(legacy_params))
                    previous = json.loads(prior)['data']['hits']
                    same_ids = {c['case_id'] for c in previous} == {c['case_id'] for c in cases}
                    report['legacy_query_control'] = {'status': 'tested', 'receipt': prior_receipt,
                        'same_case_set': same_ids,
                        'legacy_root_followups': sum(len(c.get('follow_ups') or []) for c in previous),
                        'legacy_diagnosis_followups': sum(len(d.get('follow_ups') or []) for c in previous
                                                       for d in (c.get('diagnoses') or [])),
                        'corrected_root_followups': result['counts']['follow_up']}
                except Exception as exc:
                    report['legacy_query_control'] = {'status': 'failed', 'error_type': type(exc).__name__}
        except Exception as exc:
            report['experiments'][project] = {'status': 'failed', 'error_type': type(exc).__name__}
    report['status'] = 'complete' if all(
        r['status'] == 'tested' for r in report['experiments'].values()) and (
        report.get('legacy_query_control', {}).get('status') == 'tested') and (
        report.get('legacy_query_control', {}).get('same_case_set') is True) else 'partial'
    return report


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument('--output', required=True, type=Path)
    args = parser.parse_args()
    try:
        report = run_probe()
    except Exception as exc:
        report = {'status': 'failed', 'error_type': type(exc).__name__,
                  'detail': 'Schema or retrieval failed; no successful data test claimed'}
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2), encoding='utf-8')
    print(json.dumps(report, indent=2))
    if report['status'] != 'complete':
        raise SystemExit(2)


if __name__ == '__main__':
    main()
