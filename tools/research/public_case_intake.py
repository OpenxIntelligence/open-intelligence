"""Offline catalog reducers for independently authored fictional input fixtures.

Legacy personal-case acquisition and case-analysis entrypoints are retired.
The reserved example namespace identifies test metadata, not a live service.
A fixture declaration is not proof of privacy, provenance or clinical validity.
Maps to existing OI-004/006/008/011/014/016 contracts; no new patient store.
"""
from __future__ import annotations

import argparse
import copy
import hashlib
import json
import re
import time
from collections import Counter, defaultdict
from datetime import date, datetime, timezone
from pathlib import Path
from urllib.parse import unquote, urlsplit
from urllib.request import HTTPRedirectHandler, Request, build_opener

CATALOG_URL = 'https://catalog.example.invalid/data/catalog/datasets.json'
BUCKET = 'oi-independent-synthetic-fixtures'
REGION = 'us-west-2'
MAX_BYTES = 2 * 1024 * 1024
MAX_ROWS = 10000
DATE_IN_PATH = re.compile(r'(?<!\d)(\d{4})[.-](\d{2})[.-](\d{2})(?!\d)')


def canonical(value: object) -> str:
    return json.dumps(value, sort_keys=True, separators=(',', ':'), ensure_ascii=False, allow_nan=False)


def sha(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def timestamp(value: str) -> datetime:
    if not isinstance(value, str):
        raise ValueError('Timestamp must be text')
    result = datetime.fromisoformat(value.replace('Z', '+00:00'))
    if result.tzinfo is None:
        raise ValueError('Timestamp must include a timezone')
    return result


def _unique_keys(pairs: list[tuple]) -> dict:
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError('Duplicate JSON key')
        result[key] = value
    return result


def _reject_constant(value: str) -> None:
    raise ValueError('Nonfinite JSON value')


def validate_fetch_url(url: str) -> str:
    """Exact read allowlist, no caller-supplied credentials/query/path expansion."""
    if url != CATALOG_URL:
        raise ValueError('Endpoint not permitted')
    return url


def _identity_list(record: dict, key: str) -> list[str]:
    values = record.get(key, [])
    if not isinstance(values, list) or any(not isinstance(v, str) or not v.strip() for v in values):
        raise ValueError('Invalid identity/date collection shape')
    return values


def _location_valid(record: dict) -> bool:
    """Check declared locations, never fetch them. Agreement is not authenticity."""
    path = record.get('path')
    if not isinstance(path, str) or not path or path.startswith('/') or '\\' in path:
        return False
    if any(part in ('.', '..') for part in path.split('/')):
        return False
    s3 = record.get('s3_uri', '')
    if not isinstance(s3, str):
        return False
    uri = urlsplit(s3)
    if uri.scheme != 's3' or uri.netloc != BUCKET or uri.query or uri.fragment:
        return False
    object_path = uri.path.lstrip('/').rstrip('/')
    if object_path != path.rstrip('/'):
        if not (record.get('path_kind') == 'prefix' and record.get('include_pattern')
                and path.rsplit('/', 1)[0] == object_path):
            return False
    url = record.get('https_url', '')
    if url:
        if not isinstance(url, str):
            return False
        parsed = urlsplit(url)
        if (parsed.scheme != 'https' or parsed.netloc != f'{BUCKET}.s3.{REGION}.amazonaws.com'
                or parsed.query or parsed.fragment
                or unquote(parsed.path).lstrip('/').rstrip('/') != path.rstrip('/')):
            return False
    return True


def build_manifest(raw: bytes, retrieved_at: str) -> dict:
    """Preserve each catalog occurrence; do not infer patient or biological truth."""
    if not isinstance(raw, bytes) or not 0 < len(raw) <= MAX_BYTES:
        raise ValueError('Catalog size/type outside bounds')
    timestamp(retrieved_at)
    source = json.loads(raw.decode('utf-8'), object_pairs_hook=_unique_keys,
                        parse_constant=_reject_constant)
    if not isinstance(source, dict):
        raise ValueError('Expected catalog object')
    if source.get('bucket') != BUCKET or source.get('region') != REGION:
        raise ValueError('Catalog scope not permitted')
    if source.get('license') != 'CC0-1.0':
        raise ValueError('Unrecognized declared license')
    timestamp(source.get('listing_generated_at'))
    rows = source.get('datasets')
    if not isinstance(rows, list) or not 0 < len(rows) <= MAX_ROWS:
        raise ValueError('Expected bounded, nonempty dataset array')
    digest = sha(raw)
    entries = []
    for index, record in enumerate(rows):
        if not isinstance(record, dict):
            raise ValueError('Expected dataset object')
        samples = _identity_list(record, 'sample_id')
        specimens = _identity_list(record, 'specimen_id')
        dates = _identity_list(record, 'collection_date')
        reasons = []
        if not samples:
            reasons.append('sample_link_unresolved')
        elif len(samples) > 1:
            reasons.append('multiple_sample_links')
        if not specimens:
            reasons.append('specimen_link_unresolved')
        elif len(specimens) > 1:
            reasons.append('multiple_specimen_links')
        if not dates:
            reasons.append('collection_date_unresolved')
        elif len(dates) > 1:
            reasons.append('multiple_collection_dates')
        valid_dates = set()
        for value in dates:
            try:
                if re.fullmatch(r'\d{4}-\d{2}-\d{2}', value):
                    valid_dates.add(date.fromisoformat(value).isoformat())
                elif re.fullmatch(r'\d{4}(-\d{2})?', value):
                    # Validate components without publishing an invented day.
                    parts = [int(p) for p in value.split('-')]
                    date(parts[0], parts[1] if len(parts) == 2 else 1, 1)
                    reasons.append('partial_collection_date')
                else:
                    reasons.append('unparsed_collection_date')
            except ValueError:
                reasons.append('invalid_collection_date')
        path = record.get('path', '')
        if isinstance(path, str) and valid_dates:
            path_dates = {'-'.join(parts) for parts in DATE_IN_PATH.findall(path)}
            if path_dates - valid_dates:
                reasons.append('path_date_differs_from_collection')
        if record.get('status') != 'ok':
            reasons.append('source_status_requires_review')
        if record.get('caveat'):
            reasons.append('source_caveat_requires_review')
        donor_flag = record.get('other_donors', '')
        if not isinstance(donor_flag, str) or donor_flag.strip().casefold() not in ('', 'no'):
            reasons.append('other_donor_scope_unreviewed')
        if record.get('path_kind') == 'prefix' or record.get('include_pattern'):
            reasons.append('asset_selector_requires_review')
        for field in ('files', 'bytes', 'md5_files'):
            if field in record and (type(record[field]) is not int or record[field] < 0):
                reasons.append('invalid_listing_count')
        if not _location_valid(record):
            reasons.append('asset_location_unverified')
        entries.append({
            'source_pointer': f'/datasets/{index}', 'catalog_sha256': digest,
            'record_sha256': sha(canonical(record).encode('utf-8')),
            'source_record': copy.deepcopy(record),
            'review_reasons': sorted(set(reasons)),
            'asset_acquired': False, 'analysis_executed': False,
            'clinical_reviewed': False,
        })
    return {
        'kind': 'research_catalog_manifest', 'source_url': CATALOG_URL,
        'catalog_sha256': digest, 'retrieved_at': retrieved_at,
        'listing_generated_at': source['listing_generated_at'],
        'declared_license': source['license'], 'bucket': source['bucket'],
        'record_count': len(entries), 'entries': entries,
        'historical_availability_established': False,
        'permission_scope': 'Catalog inspection only; no per-asset authorization inferred',
    }


def verify_manifest(manifest: dict, raw: bytes) -> bool:
    """Deterministic input binding, not source authentication or clinical review."""
    try:
        return manifest == build_manifest(raw, manifest['retrieved_at'])
    except (ValueError, TypeError, KeyError, UnicodeError):
        return False


def capability(section: object, assay: object = None, table: object = None) -> str | None:
    """Declared structured fields route review; arbitrary prose is not code."""
    if assay == 'Radiology' and table == 'clinical-dicom':
        return 'imaging'
    return {
        'bulk-dna': 'molecular', 'bulk-rna': 'molecular',
        'scrna-tumor': 'single_cell', 'scrna-pbmc': 'single_cell',
        'scrna-csf': 'single_cell', 'spatial': 'spatial',
        'pathology': 'pathology', 'imaging': 'imaging',
        'pathology-imaging': 'pathology_and_imaging',
        'microbiome': 'microbiome',
    }.get(section) if isinstance(section, str) else None


PREREQUISITES = {
    'molecular': ['specimen_and_assay_review', 'asset_scope_and_integrity', 'reference_and_pipeline_qualification'],
    'single_cell': ['specimen_and_donor_review', 'asset_scope_and_integrity', 'cell_qc_and_reference_review'],
    'spatial': ['specimen_and_slide_review', 'asset_scope_and_integrity', 'coordinate_and_assay_review'],
    'pathology': ['specimen_and_slide_review', 'asset_scope_and_integrity', 'task_specific_model_qualification'],
    'imaging': ['study_and_lesion_review', 'asset_scope_and_integrity', 'task_specific_model_qualification'],
    'pathology_and_imaging': ['modality_and_specimen_review', 'asset_scope_and_integrity', 'task_specific_model_qualification'],
    'microbiome': ['sample_and_control_review', 'asset_scope_and_integrity', 'reference_and_pipeline_qualification'],
}


def plan_inputs(manifest: dict, mode: str = 'present_day', cutoff: str | None = None) -> dict:
    if mode not in ('present_day', 'historical_replay'):
        raise ValueError('Unsupported plan mode')
    if mode == 'historical_replay':
        if cutoff is None:
            raise ValueError('Historical mode needs an explicit cutoff')
        timestamp(cutoff)
    grouped = defaultdict(list)
    grouped_reasons = defaultdict(Counter)
    unknown = 0
    for entry in manifest['entries']:
        record = entry['source_record']
        domain = capability(record.get('section'), record.get('assay'), record.get('table'))
        if domain is None:
            unknown += 1
            continue
        grouped_reasons[domain].update(entry['review_reasons'])
        grouped[domain].append({k: entry[k] for k in
                               ('source_pointer', 'catalog_sha256', 'record_sha256')})
    tasks = [{
        'capability': domain, 'task_kind': 'review_input_suitability',
        'input_refs': copy.deepcopy(refs), 'prerequisites': list(PREREQUISITES[domain]),
        'input_review_reason_counts': dict(sorted(grouped_reasons[domain].items())),
        'status': 'input_review_required', 'execution_authorized': False,
        'analysis_executed': False,
    } for domain, refs in sorted(grouped.items())]
    historical = mode == 'historical_replay'
    return {
        'mode': mode, 'cutoff': cutoff,
        'status': 'held_missing_historical_availability' if historical else 'planned_not_executed',
        'tasks': tasks, 'unclassified_inputs': unknown,
        'historical_inputs_eligible': 0,
        'model_calls': 0, 'asset_downloads': 0, 'clinical_conclusions': [],
        'limitation': 'Catalog/collection dates do not prove historical availability; no analysis authorization or result is inferred.',
    }


def aggregate(manifest: dict) -> dict:
    """Only counts and fixed-vocabulary findings; no sample IDs or raw caveats."""
    entries = manifest['entries']
    reasons = Counter()
    samples_to_specimens = defaultdict(set)
    samples, specimens, locations = set(), set(), Counter()
    known_status = Counter()
    for entry in entries:
        row = entry['source_record']
        reasons.update(entry['review_reasons'])
        samples.update(row.get('sample_id', []))
        specimens.update(row.get('specimen_id', []))
        # Only unambiguous single-sample/single-specimen occurrences contribute
        # to this relationship diagnostic. Never form a many-to-many cross product.
        if len(row.get('sample_id', [])) == len(row.get('specimen_id', [])) == 1:
            samples_to_specimens[row['sample_id'][0]].add(row['specimen_id'][0])
        location = (row.get('path'), row.get('path_kind'), row.get('include_pattern'))
        if all(isinstance(v, str) for v in location) and location[0]:
            locations[location] += 1
        status = row.get('status')
        known_status[status if status in ('ok', 'caution', 'exclude', 'superseded') else 'other_or_absent'] += 1
    plan = plan_inputs(manifest)
    return {
        'catalog_occurrences': len(entries), 'distinct_sample_aliases': len(samples),
        'distinct_specimen_aliases': len(specimens),
        'samples_linked_to_multiple_specimens': sum(len(v) > 1 for v in samples_to_specimens.values()),
        'repeated_location_occurrences': sum(n - 1 for n in locations.values()),
        'occurrences_with_review_reasons': sum(bool(e['review_reasons']) for e in entries),
        'review_reason_counts': dict(sorted(reasons.items())),
        'source_status_counts': dict(sorted(known_status.items())),
        'planned_capability_input_counts': {t['capability']: len(t['input_refs']) for t in plan['tasks']},
        'unclassified_inputs': plan['unclassified_inputs'],
        'counting_scope': 'Catalog row occurrences; folders and individual rows may overlap. No unique asset-byte or file total inferred.',
        'row_level_records_published': False, 'asset_downloads': 0, 'model_calls': 0,
        'clinical_conclusions': 0,
    }


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        raise ValueError('Redirect outside fixed retrieval contract')


def fetch_catalog() -> tuple[bytes, dict]:
    """Retired personal-case entrypoint; reject before network or data access."""
    raise PermissionError('Personal-case acquisition and analysis are retired. Public narratives inform workflow research only; use independently authored synthetic fixtures. No manual opt-in exception.')


def run_probe() -> dict:
    """Retired personal-case entrypoint; reject before network or data access."""
    raise PermissionError('Personal-case acquisition and analysis are retired. Public narratives inform workflow research only; use independently authored synthetic fixtures. No manual opt-in exception.')


def main() -> None:
    raise SystemExit("Retired personal-case runner. Use only independent synthetic parser unit tests.")


if __name__ == '__main__':
    main()
