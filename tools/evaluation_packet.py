"""Build cutoff-isolated practice inputs. No clinical validation or network I/O.

The coordinator's reference key is intentionally never opened by this module.
A public practice set does not establish blind, independent evaluation.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import re

ROOT_FIELDS = {'version', 'packet_id', 'project', 'synthetic', 'status',
               'reference_code_commit', 'authorship', 'cutoffs', 'cases',
               'questions', 'sources', 'receipts'}
UTC = re.compile(r'\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z\Z')
IDENTIFIER = re.compile(r'[A-Z][A-Z0-9-]{1,79}\Z')


def fields(value: object, expected: set[str]) -> None:
    if not isinstance(value, dict) or set(value) != expected:
        raise ValueError('unexpected or missing fields')


def identifier(value: object) -> str:
    if not isinstance(value, str) or not IDENTIFIER.fullmatch(value):
        raise ValueError('invalid identifier')
    return value


def instant(value: object) -> datetime:
    if not isinstance(value, str) or not UTC.fullmatch(value):
        raise ValueError('timestamps require explicit UTC YYYY-MM-DDTHH:MM:SSZ')
    try:
        return datetime.strptime(value, '%Y-%m-%dT%H:%M:%SZ').replace(tzinfo=timezone.utc)
    except ValueError as exc:
        raise ValueError('invalid UTC timestamp') from exc


def records(value: object, expected: set[str]) -> dict:
    if not isinstance(value, list) or not value:
        raise ValueError('records must be a nonempty list')
    result = {}
    for item in value:
        fields(item, expected)
        key = identifier(item['id'])
        if key in result:
            raise ValueError('duplicate record identifier')
        result[key] = item
    return result


def validate(packet: dict) -> None:
    fields(packet, ROOT_FIELDS)
    if packet['synthetic'] is not True:
        raise ValueError('synthetic must be true')
    if type(packet['version']) is not int or packet['version'] != 1:
        raise ValueError('unsupported packet version')
    if packet['project'] != 'Open Intelligence' or packet['status'] != 'engineering-practice-only':
        raise ValueError('incorrect project or evaluation status')
    identifier(packet['packet_id'])
    if not isinstance(packet['reference_code_commit'], str) or not re.fullmatch(r'[a-f0-9]{40}', packet['reference_code_commit']):
        raise ValueError('reference code commit must be a full SHA')
    if not isinstance(packet['authorship'], str) or not packet['authorship'].strip():
        raise ValueError('authorship declaration required')
    cutoffs = packet['cutoffs']
    if not isinstance(cutoffs, dict) or not cutoffs:
        raise ValueError('cutoffs required')
    for key, timestamp in cutoffs.items():
        identifier(key)
        instant(timestamp)
    questions = packet['questions']
    if not isinstance(questions, list) or not questions or any(not isinstance(q, str) or not q.strip() for q in questions):
        raise ValueError('nonempty questions required')
    cases = records(packet['cases'], {'id', 'label'})
    for case in cases.values():
        if not isinstance(case['label'], str) or not case['label'].strip():
            raise ValueError('case label required')
    sources = records(packet['sources'], {'id', 'kind', 'sha256', 'text'})
    for source in sources.values():
        kind = source['kind']
        if kind not in ('report', 'evidence'):
            raise ValueError('unsupported source kind')
        text = source['text']
        marker = 'OI-SYNTHETIC-REPORT/1\n' if kind == 'report' else 'OI-SYNTHETIC-EVIDENCE/1\n'
        if not isinstance(text, str) or not text.startswith(marker) or '\x00' in text or '\r' in text:
            raise ValueError('source must use the declared synthetic format')
        try:
            raw = text.encode('utf-8')
        except UnicodeEncodeError as exc:
            raise ValueError('invalid source UTF-8') from exc
        if len(raw) > 65536:
            raise ValueError('source exceeds 64 KiB')
        if not isinstance(source['sha256'], str) or hashlib.sha256(raw).hexdigest() != source['sha256']:
            raise ValueError('source hash mismatch')
    receipts = records(packet['receipts'], {'id', 'source_id', 'target_case', 'received_at'})
    for receipt in receipts.values():
        source_id = receipt['source_id']
        if not isinstance(source_id, str) or source_id not in sources:
            raise ValueError('receipt refers to missing source')
        target = receipt['target_case']
        if sources[source_id]['kind'] == 'report':
            if not isinstance(target, str) or target not in cases:
                raise ValueError('report target case missing')
        elif target is not None:
            raise ValueError('evidence receipt must not carry a case attachment')
        instant(receipt['received_at'])


def bundle(packet: dict, cutoff: str) -> dict:
    """Explicit projection: no future manifest, source hashes or scoring answers."""
    validate(packet)
    if cutoff not in packet['cutoffs']:
        raise ValueError('unknown cutoff')
    end = instant(packet['cutoffs'][cutoff])
    selected = sorted((r for r in packet['receipts'] if instant(r['received_at']) <= end),
                      key=lambda r: (instant(r['received_at']), r['id']))
    source_ids = {r['source_id'] for r in selected}
    cases = {r['target_case'] for r in selected if r['target_case'] is not None}
    return {'packet_id': packet['packet_id'], 'synthetic': True,
            'status': 'engineering-practice-only', 'cutoff': packet['cutoffs'][cutoff],
            'cases': [dict(c) for c in packet['cases'] if c['id'] in cases],
            'questions': list(packet['questions']),
            'sources': [dict(s) for s in packet['sources'] if s['id'] in source_ids],
            'receipts': [dict(r) for r in selected]}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--packet', type=Path, default=Path('validation/iv01/cases.json'))
    parser.add_argument('--cutoff')
    parser.add_argument('--output', type=Path)
    args = parser.parse_args()
    try:
        packet = json.loads(args.packet.read_text(encoding='utf-8'))
        validate(packet)
        if args.cutoff is None and args.output is None:
            print(json.dumps({'status': 'manifest-valid-not-clinically-validated',
                              'cases': len(packet['cases']), 'sources': len(packet['sources']),
                              'receipts': len(packet['receipts'])}, sort_keys=True))
            return
        if args.cutoff is None or args.output is None:
            raise ValueError('--cutoff and --output must be supplied together')
        data = json.dumps(bundle(packet, args.cutoff), indent=2, sort_keys=True, ensure_ascii=False) + '\n'
        # Exclusive creation: never replace or append to earlier participants' input.
        with args.output.open('x', encoding='utf-8', newline='\n') as output:
            output.write(data)
        print('Created synthetic input packet: ' + str(args.output))
    except (OSError, ValueError, TypeError) as exc:
        parser.exit(2, f'Packet rejected: {exc}\n')


if __name__ == '__main__':
    main()
