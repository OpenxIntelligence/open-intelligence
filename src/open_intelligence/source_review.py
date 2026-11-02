"""Explicit new-source review requests inside the existing synthetic ledger.

Import alone never infers relevance. A demo operator links one later-received
first-version source finding to one earlier human-authored snapshot. This is
not clinical review, an amendment, model analysis, or an authorized action.
"""
from __future__ import annotations

import json

from .store import CaseStore, InvalidInput

EVENT_KIND = 'new_source_review_requested'
DISCLAIMER = (
    'Synthetic demo only. Sources are listed by receipt order, not clinical '
    'relevance. The operator supplies the impact rationale; the software does '
    'not establish its truth or verify professional identity. A request reopens '
    'review, not treatment, source correction, or clinical approval.'
)


def _positive_id(value: object, name: str) -> int:
    if type(value) is not int or not 1 <= value <= 9223372036854775807:
        raise InvalidInput(f'{name} must be a positive integer')
    return value


def _snapshot(store: CaseStore, case_id: str, snapshot_id: int) -> dict:
    row = store.db.execute(
        'SELECT id,question_id,state,created_at FROM snapshots WHERE case_id=? AND id=?',
        (case_id, snapshot_id)).fetchone()
    if not row:
        raise InvalidInput('Investigation snapshot not in this case')
    return dict(row)


def _events(store: CaseStore, case_id: str) -> list[dict]:
    rows = store.db.execute(
        """SELECT id,kind,details,occurred_at FROM events WHERE case_id=?
        AND kind IN ('draft_created','source_imported',?) ORDER BY id""",
        (case_id, EVENT_KIND)).fetchall()
    return [dict(row, details=json.loads(row['details'])) for row in rows]


def _created_event(events: list[dict], snapshot_id: int) -> int:
    for event in events:
        if event['kind'] == 'draft_created' and event['details'].get('snapshot_id') == snapshot_id:
            return event['id']
    raise InvalidInput('Snapshot creation receipt is missing')


def _requests(events: list[dict], snapshot_id: int) -> list[dict]:
    return [dict(event['details'], event_id=event['id'], occurred_at=event['occurred_at'])
            for event in events if event['kind'] == EVENT_KIND
            and event['details'].get('snapshot_id') == snapshot_id]


def new_source_review_context(store: CaseStore, case_id: str, snapshot_id: int) -> dict:
    """Read-only unranked inputs and durable request receipts for one snapshot."""
    _positive_id(snapshot_id, 'snapshot_id')
    store._case(case_id)
    with store.db:
        store.db.execute('BEGIN')
        snapshot = _snapshot(store, case_id, snapshot_id)
        events = _events(store, case_id)
        creation = _created_event(events, snapshot_id)
        sources = []
        for event in events:
            if event['kind'] != 'source_imported' or event['id'] <= creation:
                continue
            details = event['details']
            if details.get('amends_id') is not None:
                continue
            row = store.db.execute(
                """SELECT id,document_id,version,kind,event_date,issued_at,received_at,sha256
                FROM source_versions WHERE id=? AND case_id=? AND state='current'
                AND supersedes_id IS NULL AND version=1""", (details['source_id'], case_id)).fetchone()
            if not row or store.db.execute(
                    'SELECT 1 FROM snapshot_sources WHERE snapshot_id=? AND source_version_id=?',
                    (snapshot_id, row['id'])).fetchone():
                continue
            findings = [dict(f) for f in store.db.execute(
                'SELECT finding_key,certainty,quote,source_line FROM assertions WHERE source_version_id=? ORDER BY source_line',
                (row['id'],)).fetchall()]
            item = dict(row)
            item['source_version_id'] = item.pop('id')
            sources.append(dict(item, source_import_event_id=event['id'], findings=findings))
        return {'case_id': case_id, 'synthetic': True, 'clinical_relevance_assessed': False,
                'disclaimer': DISCLAIMER, 'snapshot': snapshot,
                'snapshot_creation_event_id': creation,
                'request_allowed': snapshot['state'] != 'stale',
                'sources': sources, 'requests': _requests(events, snapshot_id)}


def request_new_source_review(store: CaseStore, case_id: str, snapshot_id: int,
                              source_version_id: int, source_line: int,
                              reviewer_label: str, rationale: str) -> dict:
    """Atomically reopen one snapshot and its option dependents; retain originals.

    Same snapshot/source pair and identical normalized payload is idempotent.
    A changed retry is rejected rather than rewriting the original rationale.
    A recorded retry can be read after the triggering source is superseded.
    """
    for name, value in (('snapshot_id', snapshot_id), ('source_version_id', source_version_id),
                        ('source_line', source_line)):
        _positive_id(value, name)
    if not isinstance(reviewer_label, str) or not 2 <= len(reviewer_label.strip()) <= 80:
        raise InvalidInput('Provide a 2-80 character demo reviewer label')
    if not isinstance(rationale, str) or not 10 <= len(rationale.strip()) <= 800:
        raise InvalidInput('Review rationale must have 10-800 characters')
    reviewer_label, rationale = reviewer_label.strip(), rationale.strip()
    store._case(case_id)
    with store.db:
        store.db.execute('BEGIN IMMEDIATE')
        snapshot = _snapshot(store, case_id, snapshot_id)
        source = store.db.execute('SELECT * FROM source_versions WHERE case_id=? AND id=?',
                                  (case_id, source_version_id)).fetchone()
        if not source:
            raise InvalidInput('Source version not in this case')
        events = _events(store, case_id)
        payload = {'snapshot_id': snapshot_id, 'source_version_id': source_version_id,
                   'source_line': source_line, 'reviewer_label': reviewer_label, 'rationale': rationale}
        for receipt in _requests(events, snapshot_id):
            if receipt['source_version_id'] != source_version_id:
                continue
            if any(receipt[key] != value for key, value in payload.items()):
                raise InvalidInput('This snapshot/source pair already has a different review receipt')
            return {'result': 'duplicate', 'event_id': receipt['event_id'], 'synthetic': True,
                    'invalidated_snapshots': receipt['invalidated_snapshots'],
                    'invalidated_options': receipt['invalidated_options']}
        if snapshot['state'] == 'stale':
            raise InvalidInput('Snapshot already requires review; preserve it and prepare a new draft')
        if source['state'] != 'current' or source['supersedes_id'] is not None or source['version'] != 1:
            raise InvalidInput('Select a current first-version source, not an amendment or superseded source')
        if store.db.execute('SELECT 1 FROM snapshot_sources WHERE snapshot_id=? AND source_version_id=?',
                            (snapshot_id, source_version_id)).fetchone():
            raise InvalidInput('The selected source is already bound to this snapshot')
        creation = _created_event(events, snapshot_id)
        imported = next((event['id'] for event in events if event['kind'] == 'source_imported'
                         and event['details'].get('source_id') == source_version_id), None)
        if imported is None or imported <= creation:
            raise InvalidInput('Select a source received after this snapshot was created')
        finding = store.db.execute(
            'SELECT quote,finding_key,certainty FROM assertions WHERE case_id=? AND source_version_id=? AND source_line=?',
            (case_id, source_version_id, source_line)).fetchone()
        if not finding:
            raise InvalidInput('Source line must identify an exact finding, not a header or missing line')
        store.db.execute("UPDATE snapshots SET state='stale' WHERE id=? AND case_id=?", (snapshot_id, case_id))
        store.db.execute("UPDATE questions SET state='open' WHERE id=? AND case_id=?", (snapshot['question_id'], case_id))
        invalidated = store._invalidate_options(snapshot_ids={snapshot_id}, source_version_ids=set(),
                                                evidence_version_ids=set())
        store._event(case_id, EVENT_KIND, **payload, question_id=snapshot['question_id'],
                     source_sha256=source['sha256'], source_quote=finding['quote'],
                     finding_key=finding['finding_key'], reported_state=finding['certainty'],
                     snapshot_creation_event_id=creation, source_import_event_id=imported,
                     invalidated_snapshots=[snapshot_id], invalidated_options=invalidated)
        event_id = int(store.db.execute('SELECT last_insert_rowid()').fetchone()[0])
        return {'result': 'review_requested', 'event_id': event_id, 'synthetic': True,
                'invalidated_snapshots': [snapshot_id], 'invalidated_options': invalidated}
