"""Fail-closed declaration preflight for the existing IV-01 evaluation protocol.

This verifies recorded fields and file fingerprints, not reviewer independence,
institutional approval, clinical validity, trial rights, or an actual study.
Nothing is written, activated, contacted, or scored by this program.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import io
import json
import math
from pathlib import Path
import re


PROTOCOL_FIELDS = frozenset({
    'evaluation_id', 'status', 'packet_id', 'application_commit', 'packet_commit',
    'independent_reviewer_ids', 'conflicts_declared', 'prior_key_exposure_recorded',
    'source_rights_reviewed', 'clinical_reference_review_complete',
    'metric_denominators_frozen', 'arm_order_plan', 'empirical_thresholds',
    'engineering_invariants', 'stop_owner', 'approval_record', 'results_observed',
})
THRESHOLD_FIELDS = frozenset({
    'source_fidelity_minimum', 'missingness_fidelity_minimum',
    'maximum_omissions', 'acceptable_review_burden_change',
})
SAFETY_FIELDS = frozenset({
    'future_source_leaks', 'answer_key_in_participant_packet',
    'hash_mismatches_accepted', 'overwrites_of_existing_packet',
})
RESULT_COLUMNS = (
    'evaluation_id,packet_commit,application_commit,run_id,reviewer_id,case_id,'
    'cutoff,arm,opportunity_id,claim_id,denominator_eligible,source_ids,'
    'source_versions,source_lines,outcome,severity,missingness_error,'
    'identity_error,post_cutoff_leak,unsupported_claim,false_urgency,'
    'acquisition_minutes,preparation_minutes,correction_minutes,review_minutes,'
    'coordination_minutes,prior_key_exposure,disagreement,adjudicator_outcome,'
    'reason,evidence_location'
).split(',')
SHA = re.compile(r'[a-f0-9]{40}\Z')
REVIEWER = re.compile(r'[A-Z0-9][A-Z0-9_-]{1,79}\Z')
MAX_PROTOCOL = 32 * 1024
MAX_PACKET = 1024 * 1024
MAX_TEMPLATE = 16 * 1024


class PreflightError(ValueError):
    """Input contract is structurally invalid, not simply incomplete."""


def _json_object(raw: bytes, *, limit: int, label: str) -> dict:
    if not isinstance(raw, bytes) or not 0 < len(raw) <= limit:
        raise PreflightError(f'{label} exceeds size boundary or is empty')

    def unique_pairs(pairs):
        value = {}
        for key, item in pairs:
            if key in value:
                raise PreflightError(f'duplicate JSON key in {label}: {key}')
            value[key] = item
        return value

    def no_constants(token):
        raise PreflightError(f'non-finite JSON value in {label}: {token}')

    try:
        value = json.loads(raw.decode('utf-8'), object_pairs_hook=unique_pairs,
                           parse_constant=no_constants)
    except (UnicodeError, json.JSONDecodeError) as exc:
        raise PreflightError(f'invalid UTF-8 JSON in {label}') from exc
    if not isinstance(value, dict):
        raise PreflightError(f'{label} must be a JSON object')
    return value


def _schema(value: object, expected: frozenset[str], *, label: str) -> dict:
    if not isinstance(value, dict) or set(value) != expected:
        raise PreflightError(f'{label} unexpected or missing fields')
    return value


def _template(raw: bytes) -> None:
    if not isinstance(raw, bytes) or not 0 < len(raw) <= MAX_TEMPLATE:
        raise PreflightError('results template exceeds size boundary or is empty')
    try:
        text = raw.decode('utf-8-sig')
        rows = list(csv.reader(io.StringIO(text, newline=''), strict=True))
    except (UnicodeError, csv.Error) as exc:
        raise PreflightError('results template invalid UTF-8/CSV') from exc
    if not rows or rows[0] != RESULT_COLUMNS:
        raise PreflightError('results template headers differ from approved 31-column schema')
    if len(rows) != 1:
        raise PreflightError('results template is not blank; no observed results belong in public preregistration')


def _text(value: object) -> bool:
    return isinstance(value, str) and bool(value.strip()) and len(value) <= 1000


def _fraction(value: object, low: float = 0.0, high: float = 1.0) -> bool:
    return (type(value) in (float, int) and math.isfinite(value)
            and low <= value <= high)


def inspect_inputs(protocol_raw: bytes, packet_raw: bytes,
                   results_template_raw: bytes) -> dict:
    """Return deterministic evidence of declared readiness; never claim authorization.

    The preflight checks protocol declarations and metadata linkage only. Run
    the separate IV-01 packet generator to validate source hashes and cutoffs.
    """
    protocol = _schema(_json_object(protocol_raw, limit=MAX_PROTOCOL, label='protocol'),
                       PROTOCOL_FIELDS, label='protocol')
    packet = _json_object(packet_raw, limit=MAX_PACKET, label='packet')
    if (packet.get('packet_id') != protocol['packet_id'] or
            packet.get('project') != 'Open Intelligence' or
            packet.get('synthetic') is not True or
            packet.get('status') != 'engineering-practice-only'):
        raise PreflightError('packet_id/project/synthetic/status do not match permitted manifest')
    if not isinstance(packet.get('sources'), list) or not isinstance(packet.get('receipts'), list):
        raise PreflightError('packet sources and receipts must be arrays')
    _template(results_template_raw)
    t = _schema(protocol['empirical_thresholds'], THRESHOLD_FIELDS,
                label='empirical_thresholds')
    invariants = _schema(protocol['engineering_invariants'], SAFETY_FIELDS,
                         label='engineering_invariants')
    blockers = []
    if protocol['status'] != 'activated':
        blockers.append('status: protocol must be explicitly declared activated before scored use')
    if not _text(protocol['evaluation_id']):
        blockers.append('evaluation_id: frozen identifier is missing')
    if not _text(protocol['packet_id']):
        blockers.append('packet_id: identifier is missing')
    for key in ('application_commit', 'packet_commit'):
        value = protocol[key]
        if not isinstance(value, str) or not SHA.fullmatch(value):
            blockers.append(key + ': exact 40-character lowercase commit SHA required')
    reviewers = protocol['independent_reviewer_ids']
    if (not isinstance(reviewers, list) or len(reviewers) < 2 or
            any(not isinstance(r, str) or not REVIEWER.fullmatch(r) for r in reviewers) or
            len(set(reviewers)) != len(reviewers)):
        blockers.append('independent_reviewer_ids: two distinct anonymized reviewer IDs required')
    for key in ('conflicts_declared', 'prior_key_exposure_recorded',
                'source_rights_reviewed', 'clinical_reference_review_complete',
                'metric_denominators_frozen'):
        if protocol[key] is not True:
            blockers.append(key + ': required affirmative declaration is missing')
    for key in ('arm_order_plan', 'stop_owner', 'approval_record'):
        if not _text(protocol[key]):
            blockers.append(key + ': required accountable record is missing')
    for key in ('source_fidelity_minimum', 'missingness_fidelity_minimum'):
        if not _fraction(t[key]):
            blockers.append('empirical_thresholds.' + key + ': numeric fraction 0–1 required')
    if type(t['maximum_omissions']) is not int or t['maximum_omissions'] < 0:
        blockers.append('empirical_thresholds.maximum_omissions: nonnegative integer required')
    if not _fraction(t['acceptable_review_burden_change'], -1.0, 1.0):
        blockers.append('empirical_thresholds.acceptable_review_burden_change: fraction -1–1 required')
    for key in sorted(SAFETY_FIELDS):
        if type(invariants[key]) is not int or invariants[key] != 0:
            blockers.append('engineering_invariants.' + key + ': must remain zero')
    if protocol['results_observed'] is not False:
        blockers.append('results_observed: cannot activate or refreeze after results inspection')
    ready = not blockers
    return {
        'gate': 'declarations_complete_unverified' if ready else 'blocked',
        'declarations_complete': ready,
        'scoring_authorized': False,
        'blinded_evaluation_established': False,
        'clinical_or_release_approved': False,
        'independent_validation_performed': False,
        'blockers': blockers,
        'packet_id': protocol['packet_id'],
        'source_count': len(packet['sources']),
        'receipt_count': len(packet['receipts']),
        'fingerprints': {
            'protocol_sha256': hashlib.sha256(protocol_raw).hexdigest(),
            'manifest_sha256': hashlib.sha256(packet_raw).hexdigest(),
            'results_template_sha256': hashlib.sha256(results_template_raw).hexdigest(),
        },
    }


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--protocol', type=Path, default=Path('validation/iv01/protocol.json'))
    parser.add_argument('--manifest', type=Path, default=Path('validation/iv01/cases.json'))
    parser.add_argument('--template', type=Path, default=Path('validation/iv01/results_template.csv'))
    parser.add_argument('--require-complete', action='store_true', help='Fail when required declarations are incomplete; does not grant approval')
    args = parser.parse_args(argv)
    try:
        result = inspect_inputs(args.protocol.read_bytes(), args.manifest.read_bytes(),
                                args.template.read_bytes())
    except (OSError, PreflightError) as exc:
        print(json.dumps({'gate': 'invalid_input', 'clinical_or_release_approved': False,
                          'error': str(exc)}, sort_keys=True))
        return 2
    print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
    return 3 if args.require_complete and not result['declarations_complete'] else 0


if __name__ == '__main__':
    raise SystemExit(main())
