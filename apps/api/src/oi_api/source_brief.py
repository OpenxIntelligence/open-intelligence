"""Deterministic plain-text brief of an already validated source-only snapshot.

No model, clinical interpretation, review transition, external evidence or new
ledger. The API owns authorization, canonical source reads and freshness checks.
"""
from __future__ import annotations

import hashlib
import json
from datetime import datetime
from open_intelligence.patient_registry import PatientRegistryError

MAX_ENVELOPE_BYTES = 65_536


def render_source_brief(model: dict, *, prepared_at: str) -> dict:
    """Render exact reported text, not clinical meaning, from the source owner."""
    if (model.get('contract') != 'oi.synthetic-postgres-world-model-sources/1'
            or model.get('synthetic') is not True
            or model.get('clinical_approval') is not False
            or model.get('authority') != 'source_report_only_unreviewed'):
        raise PatientRegistryError('Unqualified source snapshot')
    try:
        when = datetime.fromisoformat(prepared_at.replace('Z', '+00:00'))
        if when.tzinfo is None or when.utcoffset() is None:
            raise ValueError()
    except (ValueError, TypeError, AttributeError):
        raise PatientRegistryError('Invalid preparation time') from None

    lines = [
        'Open Intelligence — Source-linked brief',
        'INDEPENDENTLY FICTIONAL DEVELOPMENT DATA ONLY',
        '',
        'Source statements only. Clinical review: not established.',
        'No diagnosis, treatment recommendation, AI answer or medical approval is provided.',
        'This brief does not establish a complete medical record.',
        'It is a snapshot, not a live view. Refresh sources before subsequent use.',
        'An exported copy cannot be revoked or silently updated.',
        '',
        f'Patient ID: {model["patient_id"]}',
        f'Source case: {model["case_id"]}',
        f'Prepared at: {prepared_at}',
        f'Source snapshot SHA-256: {model["source_snapshot_sha256"]}',
        '', 'CURRENT SOURCE-REPORTED OBSERVATIONS',
    ]
    if not model['observations']:
        lines.append('No current source-reported observations are available; absence is not a negative finding.')
    for source in model['current_sources']:
        lines += ['', f'Document: {source["document_id"]}@{source["version"]}',
            f'Original source ID: {source["source_version_id"]}',
            f'Original SHA-256: {source["source_sha256"]}',
            f'Kind: {source["kind"]}',
            f'Specimen: {source["specimen_id"] or "not recorded"}',
            f'Event date: {source["event_date"]}', f'Issued date: {source["issued_at"]}',
            f'Received at: {source["received_at"]}']
        for finding in model['observations']:
            if finding['source_version_id'] != source['source_version_id']:
                continue
            lines += ['', f'Finding key: {finding["finding_key"]}',
                f'Source-reported state: {finding["reported_state"]}',
                f'Original line: {finding["source_line"]}',
                'Exact source statement (literal text):', finding['source_statement']]
    lines += ['', 'UNRESOLVED SOURCE STATEMENTS']
    if not model['unresolved']:
        lines.append('No unresolved labels in this bounded projection. This is not clinical clearance.')
    for finding in model['unresolved']:
        lines.append(f'{finding["source_version_id"]} line {finding["source_line"]}: '
                     f'{finding["finding_key"]} — {finding["reported_state"]}')
    lines += ['', 'SOURCE-LABEL DISAGREEMENTS']
    if not model['conflicts']:
        lines.append('None detected by the limited same-specimen/date/key rule; not independent adjudication.')
    for conflict in model['conflicts']:
        lines += [f'{conflict["finding_key"]} / {conflict["specimen_id"]} / {conflict["event_date"]}',
                  'Source labels: ' + ' / '.join(conflict['reported_states']),
                  'Clinical interpretation: not performed.']
        lines.extend(f'{ref["source_version_id"]} line {ref["source_line"]}'
                     for ref in conflict['observation_refs'])
    lines += ['', 'HISTORICAL SOURCE VERSIONS',
              'Prior originals are preserved, not substituted for current findings.']
    if not model['history']:
        lines.append('No superseded versions in this snapshot.')
    for source in model['history']:
        lines += [f'{source["document_id"]}@{source["version"]} / {source["source_version_id"]}',
                  f'State: {source["state"]}; original SHA-256: {source["source_sha256"]}',
                  f'Event: {source["event_date"]}; issued: {source["issued_at"]}; received: {source["received_at"]}']
    lines += ['', 'LIMITATIONS', *model['limitations'],
              'No external publications or clinical guidelines are included.',
              'No clinical review, preparation/delivery receipt, or verified external action is recorded.', '']
    body = '\n'.join(lines)
    envelope = dict(contract='oi.synthetic-source-brief/1', synthetic=True,
        patient_id=model['patient_id'], case_id=model['case_id'],
        source_snapshot_sha256=model['source_snapshot_sha256'], prepared_at=prepared_at,
        media_type='text/plain;charset=utf-8', body=body,
        body_sha256=hashlib.sha256(body.encode('utf-8')).hexdigest(), clinical_approval=False)
    # Bound the actual UTF-8 JSON envelope, not just text/character count; an
    # over-limit result is refused intact, never silently truncated.
    if len(json.dumps(envelope, ensure_ascii=False, separators=(',', ':')).encode('utf-8')) > MAX_ENVELOPE_BYTES:
        raise PatientRegistryError('Source brief exceeds bounded response size')
    return envelope
