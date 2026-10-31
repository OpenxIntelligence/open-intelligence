"""Offline synthetic evaluation packets; not product historical replay or clinical validation.

Availability timestamps are authored simulation inputs. This projector performs
no extraction, medical inference, model call, patient lookup or external request.
"""
from __future__ import annotations

import argparse
from datetime import datetime
import hashlib
import json
from pathlib import Path
import re

MAX_FIXTURE_BYTES = 1024 * 1024
MAX_SOURCE_BYTES = 65536
ID = re.compile(r'[A-Z][A-Z0-9-]{1,39}\Z')
HEX40 = re.compile(r'[0-9a-f]{40}\Z')
HEX64 = re.compile(r'[0-9a-f]{64}\Z')


def _keys(value: object, required: set[str], label: str) -> dict:
    if not isinstance(value, dict) or set(value) != required:
        raise ValueError(f'{label}: missing or unexpected fields')
    return value


def _id(value: object) -> str:
    if not isinstance(value, str) or not ID.fullmatch(value):
        raise ValueError('Invalid evaluation identifier')
    return value


def _instant(value: object) -> datetime:
    if not isinstance(value, str) or len(value) > 40:
        raise ValueError('Timestamp must be a bounded ISO-8601 string with a timezone')
    try:
        parsed = datetime.fromisoformat(value)
    except ValueError:
        raise ValueError('Invalid timestamp') from None
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise ValueError('Timestamp requires timezone')
    return parsed


def _rows(value: object, limit: int, label: str) -> list:
    if not isinstance(value, list) or not 1 <= len(value) <= limit:
        raise ValueError(f'{label}: expected a nonempty bounded list')
    return value


def validate_fixture(data: dict) -> None:
    """Check a development fixture; an authorship declaration is not legal proof."""
    _keys(data, {'schema_version', 'dataset_id', 'authorship', 'baseline_commit',
                 'cases', 'rounds', 'sources'}, 'fixture')
    if data['schema_version'] != 'OI-EVALUATION-FIXTURE/1':
        raise ValueError('Unsupported fixture schema')
    if data['authorship'] != 'original_synthetic_no_patient_data':
        raise ValueError('Only original synthetic development fixtures are supported')
    _id(data['dataset_id'])
    if not isinstance(data['baseline_commit'], str) or not HEX40.fullmatch(data['baseline_commit']):
        raise ValueError('Baseline commit must be an exact 40-character SHA')
    cases = [_id(x) for x in _rows(data['cases'], 16, 'cases')]
    if len(set(cases)) != len(cases):
        raise ValueError('Duplicate case identifier')
    round_ids = set()
    for row in _rows(data['rounds'], 16, 'rounds'):
        _keys(row, {'id', 'cutoff'}, 'round')
        rid = _id(row['id'])
        if rid in round_ids:
            raise ValueError('Duplicate round identifier')
        round_ids.add(rid)
        _instant(row['cutoff'])
    source_ids = set()
    for source in _rows(data['sources'], 64, 'sources'):
        _keys(source, {'id', 'target_case_id', 'available_at', 'kind', 'content', 'sha256'}, 'source')
        sid = _id(source['id'])
        if sid in source_ids:
            raise ValueError('Duplicate source identifier')
        source_ids.add(sid)
        if _id(source['target_case_id']) not in cases:
            raise ValueError('Source target case is outside the fixture')
        _instant(source['available_at'])
        if source['kind'] not in ('report', 'evidence'):
            raise ValueError('Unknown synthetic source kind')
        text = source['content']
        if not isinstance(text, str) or '\x00' in text or '\r' in text:
            raise ValueError('Source must contain UTF-8 text without NUL or CR')
        try:
            raw = text.encode('utf-8')
        except UnicodeEncodeError:
            raise ValueError('Source is not valid UTF-8') from None
        if not 0 < len(raw) <= MAX_SOURCE_BYTES:
            raise ValueError('Source exceeds size limit or is empty')
        magic = 'OI-SYNTHETIC-REPORT/1\n' if source['kind'] == 'report' else 'OI-SYNTHETIC-EVIDENCE/1\n'
        if not text.startswith(magic):
            raise ValueError('Source must use the declared synthetic format')
        digest = source['sha256']
        if not isinstance(digest, str) or not HEX64.fullmatch(digest) or hashlib.sha256(raw).hexdigest() != digest:
            raise ValueError('Source hash mismatch')


def build_packet(data: dict, round_id: str) -> dict:
    """Return exact available bytes; never export expected answers/future sources.

    This selects simulated arrivals, NOT accepted clinical state. Wrong-case or
    wrong-specimen challenges deliberately remain inputs for the existing ledger
    or reviewer to quarantine/reject. Duplicate deliveries remain in the packet.
    """
    validate_fixture(data)
    if not isinstance(round_id, str):
        raise ValueError('Unknown round')
    selected = next((row for row in data['rounds'] if row['id'] == round_id), None)
    if selected is None:
        raise ValueError('Unknown round')
    cutoff = _instant(selected['cutoff'])
    available = [s for s in data['sources'] if _instant(s['available_at']) <= cutoff]
    available.sort(key=lambda s: (_instant(s['available_at']), s['id']))
    return {
        'schema_version': 'OI-REVIEW-PACKET/1',
        'dataset_id': data['dataset_id'],
        'baseline_commit': data['baseline_commit'],
        'round_id': round_id,
        'simulated_cutoff': selected['cutoff'],
        'simulation_only': True,
        'evaluation_status': 'not_independently_evaluated',
        'cases': list(data['cases']),
        'sources': [{key: s[key] for key in
                    ('id', 'target_case_id', 'available_at', 'kind', 'content', 'sha256')}
                    for s in available],
    }


def _unique_object(pairs: list[tuple[str, object]]) -> dict:
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError('Duplicate JSON field')
        result[key] = value
    return result


def load_fixture(path: Path) -> dict:
    with path.open('rb') as stream:
        raw = stream.read(MAX_FIXTURE_BYTES + 1)
    if len(raw) > MAX_FIXTURE_BYTES:
        raise ValueError('Fixture exceeds size limit')
    return json.loads(raw.decode('utf-8'), object_pairs_hook=_unique_object)


def main() -> None:
    parser = argparse.ArgumentParser(description='Offline synthetic reviewer packet; no clinical use')
    parser.add_argument('fixture', type=Path)
    parser.add_argument('--round', required=True, dest='round_id')
    args = parser.parse_args()
    try:
        packet = build_packet(load_fixture(args.fixture), args.round_id)
    except (OSError, ValueError, UnicodeError) as error:
        parser.error(str(error))
    print(json.dumps(packet, indent=2, sort_keys=True, ensure_ascii=False))


if __name__ == '__main__':
    main()
