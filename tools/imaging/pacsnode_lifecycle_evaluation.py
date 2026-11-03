"""Bounded fictional retained-store experiment; never an adoption decision.

Only the bounded authored 2x2 Explicit VR LE objects are supported. Original
expectations stay in this experiment; no product custody/identity schema is
introduced. The live process owner is pacsnode_lifecycle_process.py.
"""
from __future__ import annotations

from collections import Counter
from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
from hashlib import sha256
from pathlib import Path
from threading import Barrier
from typing import Callable
from urllib.parse import urlencode

from open_intelligence.store import CaseStore, InvalidInput
from open_intelligence.synthetic_dicom_roundtrip import _unpack
from tools.imaging import pacsnode_live_probe as pacs
from tools.imaging.source_bound_wado import SyntheticWadoBinding, read_source_bound_wado

AMENDMENT = (
    "OI-SYNTHETIC-REPORT/1\nPatient: CASE-ALPHA\n"
    "Document: IMG-ALPHA\nType: imaging\n"
    "Event-Date: 2026-05-17\nIssued-At: 2026-05-19\n"
    "Amends: IMG-ALPHA@1\n"
    "Finding: comparison|reported|Corrected fictional lifecycle report.\n"
).encode()


def _store_objects(base: str, payloads: list[bytes]) -> dict:
    media, body = pacs.multipart_body(payloads)
    try:
        status, response_media, response = pacs._request(
            base + '/wado/studies', method='POST', content=body,
            content_type=media, accept='application/dicom+json')
    except pacs.BackendHTTPError as error:
        return {'http_status': error.status, 'response_sha256': None,
                'response_media_type': None, 'submitted_count': len(payloads)}
    token = response_media.split(';', 1)[0].lower().strip()
    return {'http_status': status, 'response_sha256': sha256(response).hexdigest(),
            'response_media_type': (token if token in (
                'application/dicom+json', 'application/json') else 'other'),
            'response_media_sha256': sha256(response_media.encode()).hexdigest(),
            'submitted_count': len(payloads)}


def _observe_phase(result: dict, name: str, base: str, ledger: CaseStore,
                   bindings: dict, originals: dict[str, bytes]) -> dict:
    # Publish the container first: later errors cannot erase earlier SOP facts.
    phase = {'inventory_matches': False, 'objects': {}}
    result['phases'][name] = phase
    first_error = None
    try:
        studies, study_media = pacs._qido_list(base + '/wado/studies?' + urlencode({
            'StudyInstanceUID': pacs.IMAGE_STUDY_UID}))
        rows, instance_media = pacs._qido_list(
            base + f'/wado/studies/{pacs.IMAGE_STUDY_UID}/series/'
            + pacs.IMAGE_SERIES_UID + '/instances')
        study_ids = [pacs._uid_value(row, '0020000D') for row in studies]
        sop_ids = [pacs._uid_value(row, '00080018') for row in rows]
        context_matches = all(
            (tag not in row or pacs._uid_value(row, tag) == expected)
            for row in rows for tag, expected in (
                ('0020000D', pacs.IMAGE_STUDY_UID),
                ('0020000E', pacs.IMAGE_SERIES_UID)))
        phase.update(
            inventory_matches=(study_ids == [pacs.IMAGE_STUDY_UID]
                               and Counter(sop_ids) == Counter(list(originals))
                               and context_matches),
            qido_study_rows=len(studies), qido_instance_rows=len(rows),
            # Never copy an unknown backend identity into an output artifact.
            qido_sop_multiplicity={uid: sop_ids.count(uid) for uid in originals},
            qido_unexpected_sop_rows=sum(uid not in originals for uid in sop_ids),
            qido_media_types={'study': study_media, 'instance': instance_media})
    except Exception as error:
        phase['qido_failure_type'] = type(error).__name__
        first_error = error
    # A failed query does not establish that an upload had no side effects.
    # Observe both already-known objects, then retain the failed query status.
    for sop in originals:
        entry = {'http_status': None, 'returned_dicom_sha256': None,
                 'original_bytes_match': False, 'pixel_bytes_match': False,
                 'source_bound_read_accepted': False, 'identity_matches': False}
        phase['objects'][sop] = entry
        replies = []

        def capture(url, accept):
            reply = pacs._request(url, accept=accept)
            replies.append(reply)
            return reply

        try:
            entry['source_bound_receipt'] = read_source_bound_wado(
                ledger, bindings[sop], base, fetch=capture)
            entry['source_bound_read_accepted'] = True
        except pacs.BackendHTTPError as error:
            entry.update(http_status=error.status, failure_type=type(error).__name__)
        except InvalidInput as error:
            entry['guard_failure_type'] = type(error).__name__
        except Exception as error:
            entry['failure_type'] = type(error).__name__
            first_error = first_error or error
        if replies:
            try:
                if len(replies) != 1:
                    raise InvalidInput('Expected one WADO request per SOP')
                status, media, body = replies[0]
                entry['http_status'] = status
                objects = pacs.multipart_dicom_parts(media, body)
                if len(objects) != 1:
                    raise InvalidInput('Expected one returned fictional SOP')
                returned = objects[0]
                entry.update(returned_dicom_sha256=sha256(returned).hexdigest(),
                             returned_dicom_bytes=len(returned),
                             original_bytes_match=returned == originals[sop])
                parsed = _unpack(returned)
                original = _unpack(originals[sop])
                entry.update(
                    returned_pixel_sha256=parsed['pixel_sha256'],
                    pixel_bytes_match=parsed['pixel_sha256'] == original['pixel_sha256'],
                    identity_matches=(parsed['study'] == pacs.IMAGE_STUDY_UID
                                      and parsed['series'] == pacs.IMAGE_SERIES_UID
                                      and parsed['sop'] == sop),
                    explicit_uncompressed_syntax_verified=True)
            except Exception as error:
                entry['failure_type'] = type(error).__name__
                first_error = first_error or error
    if first_error is not None:
        raise first_error
    return phase


def _originals_match(phase: dict, expected_sops=pacs.SOP_UIDS) -> bool:
    return (phase['inventory_matches'] is True
            and set(phase['objects']) == set(expected_sops)
            and all(entry.get('http_status') == 200
                    and entry.get('original_bytes_match') is True
                    and entry.get('pixel_bytes_match') is True
                    and entry.get('identity_matches') is True
                    and entry.get('source_bound_read_accepted') is True
                    for entry in phase['objects'].values()))


def _refuses_before_http(ledger: CaseStore, binding: SyntheticWadoBinding,
                         base: str) -> tuple[bool, int]:
    calls = 0

    def unexpected_fetch(url, accept):
        nonlocal calls
        calls += 1
        raise InvalidInput('An invalid source reached the HTTP boundary')

    try:
        read_source_bound_wado(ledger, binding, base, fetch=unexpected_fetch)
    except InvalidInput:
        return calls == 0, calls
    return False, calls


def _conflicting_pixels(original: bytes) -> bytes:
    # This finite test fixture ends in its eight-byte OW PixelData value.
    # Refuse any other layout rather than becoming a general DICOM editor.
    parsed = _unpack(original)
    if sha256(original[-8:]).hexdigest() != parsed['pixel_sha256']:
        raise InvalidInput('Unexpected fictional pixel placement')
    changed = original[:-8] + bytes([original[-8] ^ 1]) + original[-7:]
    after = _unpack(changed)
    if (after['pixel_sha256'] == parsed['pixel_sha256']
            or any(after[key] != parsed[key] for key in
                   ('study', 'series', 'sop', 'date', 'modality'))):
        raise InvalidInput('Conflict fixture did not preserve identity')
    return changed


# Fixed fictional IDs reserved only for this finite concurrency experiment.
CONCURRENT_CONFLICT_SOP = "2.25.110026110201000000000000000006"
CONCURRENT_IDENTICAL_SOP = "2.25.110026110201000000000000000007"


def _new_authored_sop(original: bytes, sop: str) -> bytes:
    """Reidentify the known authored fixture, preserving its explicit encoding."""
    before = _unpack(original)
    if sop not in (CONCURRENT_CONFLICT_SOP, CONCURRENT_IDENTICAL_SOP):
        raise InvalidInput('Unexpected concurrency fixture identity')
    old, new = before['sop'].encode(), sop.encode()
    # One file-meta and one dataset UID; equal lengths preserve both lengths
    # and file-meta group length. Refuse every layout outside this fixture.
    if len(old) != len(new) or original.count(old) != 2:
        raise InvalidInput('Unexpected authored fixture UID placement')
    changed = original.replace(old, new)
    after = _unpack(changed)
    if after != {**before, 'sop': sop}:
        raise InvalidInput('Concurrency fixture changed unrelated fields')
    return changed


def _parallel_store_objects(base: str, payloads: tuple[bytes, bytes]) -> list[dict]:
    """Start exactly two bounded HTTP requests; retain both outcomes on failure."""
    gate = Barrier(2)

    def store_one(payload):
        try:
            gate.wait(timeout=5)
            return _store_objects(base, [payload])
        except Exception as error:
            return {'http_status': None, 'failure_type': type(error).__name__,
                    'submitted_count': 1}

    with ThreadPoolExecutor(max_workers=2) as executor:
        futures = [executor.submit(store_one, payload) for payload in payloads]
        return [future.result() for future in futures]


def _immutable_concurrency(result: dict, base: str, ledger: CaseStore,
                           bindings: dict, originals: dict[str, bytes]) -> dict[str, bytes]:
    """Exercise fresh conflicts and identical creation/replay at the real HTTP boundary.

    The expected winning object comes only from the pre-authored submission
    receiving the unique success response. WADO never defines expectations.
    """
    payloads = dict(originals)
    first_binding = bindings[pacs.SOP_UIDS[0]]
    checks = result['concurrency']
    race_original = _new_authored_sop(originals[pacs.SOP_UIDS[0]], CONCURRENT_CONFLICT_SOP)
    submissions = (race_original, _conflicting_pixels(race_original))
    race = {
        'sop_uid': CONCURRENT_CONFLICT_SOP,
        'submission_dicom_sha256': [sha256(data).hexdigest() for data in submissions],
        'submission_pixel_sha256': [_unpack(data)['pixel_sha256'] for data in submissions],
        'winner_submission_index': None, 'winner_preserved_after_rejection': False,
    }
    checks['new_sop_conflict'] = race
    race['uploads'] = _parallel_store_objects(base, submissions)
    success = [i for i, upload in enumerate(race['uploads'])
               if upload['http_status'] in (200, 201, 202)]
    rejected = [i for i, upload in enumerate(race['uploads'])
                if upload['http_status'] == 409]
    unique_winner = len(success) == 1 and len(rejected) == 1
    if unique_winner:
        race['winner_submission_index'] = success[0]
    # Even ambiguous/failed uploads may have written bytes. Retain bounded
    # observations against a declared authored candidate, then fail closed.
    expected_index = success[0] if unique_winner else 0
    race['observation_expectation_submission_index'] = expected_index
    payloads[CONCURRENT_CONFLICT_SOP] = submissions[expected_index]
    bindings[CONCURRENT_CONFLICT_SOP] = replace(
        first_binding, sop_uid=CONCURRENT_CONFLICT_SOP,
        original_dicom_sha256=sha256(submissions[expected_index]).hexdigest())
    result['immutable_original_dicom_sha256'] = {
        sop: sha256(data).hexdigest() for sop, data in payloads.items()}
    observed = _observe_phase(result, 'after_concurrent_conflict', base,
                              ledger, bindings, payloads)
    race['winner_preserved_after_rejection'] = (
        unique_winner and _originals_match(observed, payloads))
    if not race['winner_preserved_after_rejection']:
        raise InvalidInput('Concurrent conflict did not preserve a unique acknowledged winner')
    result['concurrent_conflicting_uploads_preserved_winner'] = True

    identical = _new_authored_sop(originals[pacs.SOP_UIDS[1]], CONCURRENT_IDENTICAL_SOP)
    payloads[CONCURRENT_IDENTICAL_SOP] = identical
    bindings[CONCURRENT_IDENTICAL_SOP] = replace(
        first_binding, sop_uid=CONCURRENT_IDENTICAL_SOP,
        original_dicom_sha256=sha256(identical).hexdigest())
    result['immutable_original_dicom_sha256'] = {
        sop: sha256(data).hexdigest() for sop, data in payloads.items()}
    result['immutable_original_pixel_sha256'] = {
        sop: _unpack(data)['pixel_sha256'] for sop, data in payloads.items()}
    identical_result = {'sop_uid': CONCURRENT_IDENTICAL_SOP,
                        'preserved_inventory': False}
    checks['identical_new_sop'] = identical_result
    identical_result['uploads'] = _parallel_store_objects(base, (identical, identical))
    observed = _observe_phase(result, 'after_concurrent_identical', base,
                              ledger, bindings, payloads)
    identical_result['preserved_inventory'] = (
        all(upload['http_status'] in (200, 201, 202)
            for upload in identical_result['uploads'])
        and _originals_match(observed, payloads))
    if not identical_result['preserved_inventory']:
        raise InvalidInput('Concurrent identical creation changed inventory or original bytes')

    winner = payloads[CONCURRENT_CONFLICT_SOP]
    replay = {'sop_uid': CONCURRENT_CONFLICT_SOP, 'preserved_inventory': False}
    checks['identical_replay'] = replay
    replay['uploads'] = _parallel_store_objects(base, (winner, winner))
    observed = _observe_phase(result, 'after_concurrent_identical_replay', base,
                              ledger, bindings, payloads)
    replay['preserved_inventory'] = (
        all(upload['http_status'] in (200, 201, 202) for upload in replay['uploads'])
        and _originals_match(observed, payloads))
    if not replay['preserved_inventory']:
        raise InvalidInput('Concurrent identical replay changed inventory or original bytes')
    result['concurrent_identical_uploads_preserved_inventory'] = True

    retry = {'sop_uid': CONCURRENT_CONFLICT_SOP,
             'originals_preserved_after_rejection': False}
    checks['conflict_retry'] = retry
    upload_error = None
    try:
        retry['upload'] = _store_objects(base, [submissions[1 - expected_index]])
    except Exception as error:
        retry['upload'] = {'http_status': None, 'failure_type': type(error).__name__}
        upload_error = error
    observed = _observe_phase(result, 'after_conflict_retry', base,
                              ledger, bindings, payloads)
    retry['originals_preserved_after_rejection'] = (
        retry['upload']['http_status'] == 409 and _originals_match(observed, payloads))
    if upload_error is not None:
        raise upload_error
    if not retry['originals_preserved_after_rejection']:
        raise InvalidInput('Rejected conflict retry changed an original object')
    return payloads


def run_lifecycle_evaluation(base_url: str, work_dir: Path,
                             restart_backend: Callable[[], dict], *,
                             originals: dict[str, bytes] | None = None,
                             immutable_write_checks: bool = False) -> dict:
    """Observe one seed, retrieve-only restart, replay and conflict, then amendment.

    ``originals`` and the restart callback support deterministic test injection;
    the live driver supplies the actual SIGINT/wait/restart implementation.
    No retrieved object is ever allowed to redefine the original expectations.
    """
    result = {
        'kind': 'oi.pacs-lifecycle/1', 'classification': 'HOLD_NOT_APPROVED',
        'evaluation_completed': False, 'lifecycle_acceptance_passed': False,
        'phases': {}, 'uploads': {}, 'restart_observations': [],
        'immutable_write_checks_required': immutable_write_checks is True,
        'immutable_write_checks_passed': False, 'concurrency': {},
        'concurrent_conflicting_uploads_preserved_winner': False,
        'concurrent_identical_uploads_preserved_inventory': False,
        'post_conflict_restart_preserved_originals': False,
        'source_ledger_unchanged_after_restart': False,
        'wrong_case_refused': False, 'wrong_case_http_calls': 0,
        'amendment_refused_after_restart': False,
        'amendment_http_calls_after_restart': 0,
        'conflicting_sop_rejected_and_original_preserved': False,
        'acceptance_blockers': [], 'synthetic_only': True,
        'real_patient_data_used': False, 'backend_adoption_approved': False,
        'pacs_authorization_verified': False, 'crash_recovery_verified': False,
        'power_loss_durability_verified': False, 'backup_restore_verified': False,
        'event_idempotency_verified': False, 'clinical_validation': False,
        'upstream_license_approved': False, 'standards_conformance_verified': False,
        'expected_transfer_syntax': pacs.EXPECTED_RETRIEVAL_TRANSFER_SYNTAX,
        'upstream_commit': 'e9b4334477a66967d290add9e0b9afa068f59dc0',
    }
    stage, ledger = 'prepare', None
    try:
        base = pacs.loopback_origin(base_url)
        work_dir = Path(work_dir)
        work_dir.mkdir(parents=True, exist_ok=True)
        source_path = work_dir / 'source.sqlite'
        if source_path.exists():
            raise InvalidInput('Lifecycle source fixture must start fresh')
        payloads = (dict(originals) if originals is not None else {
            uid: pacs.synthetic_part10(uid, index)[0]
            for index, uid in enumerate(pacs.SOP_UIDS, 1)})
        if set(payloads) != set(pacs.SOP_UIDS):
            raise InvalidInput('Expected exactly two authored SOP objects')
        for sop, data in payloads.items():
            decoded = _unpack(data)
            if (decoded['sop'] != sop or decoded['study'] != pacs.IMAGE_STUDY_UID
                    or decoded['series'] != pacs.IMAGE_SERIES_UID):
                raise InvalidInput('Fictional DICOM identity differs from its binding')
        result['original_dicom_sha256'] = {
            sop: sha256(data).hexdigest() for sop, data in payloads.items()}
        result['original_pixel_sha256'] = {
            sop: _unpack(data)['pixel_sha256'] for sop, data in payloads.items()}
        ledger = CaseStore(source_path)
        ledger.add_case('CASE-ALPHA', 'Independent fictional lifecycle case')
        ledger.add_case('CASE-BETA', 'Unrelated fictional lifecycle case')
        source_id = ledger.import_report(
            'CASE-ALPHA', pacs.IMAGING_REPORT.read_bytes())['source_id']
        original_state = ledger.state('CASE-ALPHA')
        source = next(s for s in original_state['sources'] if s['id'] == source_id)
        bindings = {
            sop: SyntheticWadoBinding(
                'CASE-ALPHA', source_id, source['sha256'], pacs.IMAGE_STUDY_UID,
                pacs.IMAGE_SERIES_UID, sop, result['original_dicom_sha256'][sop])
            for sop in pacs.SOP_UIDS}
        result['source_binding'] = {
            'case_id': 'CASE-ALPHA', 'source_version_id': source_id,
            'source_version': source['version'], 'source_sha256': source['sha256'],
            'source_document_id': source['document_id'],
            'source_event_date': source['event_date']}
        stage = 'seed'
        result['uploads']['seed'] = _store_objects(base, list(payloads.values()))
        if result['uploads']['seed']['http_status'] not in (200, 201, 202):
            raise InvalidInput('Initial synthetic STOW was not acknowledged')
        stage = 'baseline'
        baseline = _observe_phase(result, stage, base, ledger, bindings, payloads)
        if not _originals_match(baseline):
            raise InvalidInput('Initial original/source integrity was not established')
        refused, calls = _refuses_before_http(
            ledger, replace(bindings[pacs.SOP_UIDS[0]], case_id='CASE-BETA'), base)
        result.update(wrong_case_refused=refused, wrong_case_http_calls=calls)
        if not refused or ledger.state('CASE-ALPHA') != original_state:
            raise InvalidInput('Initial first-party source boundary failed')
        ledger.close()
        ledger = None
        stage = 'restart'
        restart = restart_backend()
        result['restart_observations'].append(restart)
        if restart.get('restart_verified') is not True or not source_path.is_file():
            raise InvalidInput('Retained backend/source restart was not verified')
        ledger = CaseStore(source_path)
        stage = 'source_after_restart'
        result['source_ledger_unchanged_after_restart'] = (
            ledger.state('CASE-ALPHA') == original_state)
        if not result['source_ledger_unchanged_after_restart']:
            raise InvalidInput('Original first-party source state changed across restart')
        stage = 'after_restart'
        persisted = _observe_phase(result, stage, base, ledger, bindings, payloads)
        if not _originals_match(persisted):
            raise InvalidInput('Retained objects failed retrieval; do not reseed')
        stage = 'identical_replay'
        result['uploads'][stage] = _store_objects(base, list(payloads.values()))
        replay = _observe_phase(result, stage, base, ledger, bindings, payloads)
        if (result['uploads'][stage]['http_status'] not in (200, 201, 202)
                or not _originals_match(replay)):
            raise InvalidInput('Identical replay did not preserve original inventory')
        stage = 'conflicting_replay'
        first = pacs.SOP_UIDS[0]
        conflict = _conflicting_pixels(payloads[first])
        result['conflicting_submission'] = {
            'sop_uid': first, 'dicom_sha256': sha256(conflict).hexdigest(),
            'pixel_sha256': _unpack(conflict)['pixel_sha256'],
            'same_identity_changed_pixels': True}
        # Even an HTTP rejection may have changed storage; always retrieve both.
        upload_error = None
        try:
            result['uploads'][stage] = _store_objects(base, [conflict])
        except Exception as error:
            result['uploads'][stage] = {'http_status': None,
                                       'failure_type': type(error).__name__}
            upload_error = error
        conflicting = _observe_phase(result, stage, base, ledger, bindings, payloads)
        if upload_error is not None:
            raise upload_error
        if not conflicting['inventory_matches']:
            raise InvalidInput('Conflict observation lost the exact SOP inventory')
        target, sibling = (conflicting['objects'][sop] for sop in pacs.SOP_UIDS)
        if not (sibling['original_bytes_match'] and sibling['pixel_bytes_match']
                and sibling['source_bound_read_accepted']):
            raise InvalidInput('Conflicting upload affected the unrelated sibling')
        if (target['http_status'] != 200 or not target['identity_matches']
                or (target['source_bound_read_accepted']
                    and not target['original_bytes_match'])):
            raise InvalidInput('Conflict observation is not an inspectable original read')
        result['conflicting_sop_rejected_and_original_preserved'] = (
            result['uploads'][stage]['http_status'] == 409
            and _originals_match(conflicting))
        if not target['original_bytes_match']:
            if (target['returned_dicom_sha256'] != sha256(conflict).hexdigest()
                    or target['source_bound_read_accepted']
                    or ledger.state('CASE-ALPHA') != original_state):
                raise InvalidInput('Changed object refusal was not causally established')
            result['changed_object_withheld_by_source_guard'] = True
            result['acceptance_blockers'].append('conflicting_sop_original_replaced')
        elif not result['conflicting_sop_rejected_and_original_preserved']:
            result['acceptance_blockers'].append('conflicting_sop_not_explicitly_rejected')
        if immutable_write_checks:
            stage = 'immutable_concurrency'
            if not result['conflicting_sop_rejected_and_original_preserved']:
                raise InvalidInput('Immutable mode requires the first explicit conflict gate')
            immutable_payloads = _immutable_concurrency(result, base, ledger, bindings, payloads)
            if ledger.state('CASE-ALPHA') != original_state:
                raise InvalidInput('Concurrency changed the original source history')
            ledger.close()
            ledger = None
            stage = 'restart_after_conflicts'
            restart = restart_backend()
            result['restart_observations'].append(restart)
            if restart.get('restart_verified') is not True or not source_path.is_file():
                raise InvalidInput('Post-conflict retained restart was not verified')
            ledger = CaseStore(source_path)
            stage = 'after_conflicts_restart'
            if ledger.state('CASE-ALPHA') != original_state:
                raise InvalidInput('Source history changed after conflict restart')
            persisted = _observe_phase(result, stage, base, ledger, bindings, immutable_payloads)
            result['post_conflict_restart_preserved_originals'] = _originals_match(
                persisted, immutable_payloads)
            if not result['post_conflict_restart_preserved_originals']:
                raise InvalidInput('Originals changed after conflicts and retained restart')
            result['immutable_write_checks_passed'] = True
        stage = 'amendment'
        ledger.import_report('CASE-ALPHA', AMENDMENT)
        amended_state = ledger.state('CASE-ALPHA')
        ledger.close()
        ledger = None
        stage = 'restart_after_amendment'
        restart = restart_backend()
        result['restart_observations'].append(restart)
        if restart.get('restart_verified') is not True or not source_path.is_file():
            raise InvalidInput('Post-amendment retained restart was not verified')
        ledger = CaseStore(source_path)
        stage = 'source_after_amendment_restart'
        if ledger.state('CASE-ALPHA') != amended_state:
            raise InvalidInput('Amended source history changed across restart')
        refused, calls = _refuses_before_http(ledger, bindings[pacs.SOP_UIDS[1]], base)
        result.update(amendment_refused_after_restart=refused,
                      amendment_http_calls_after_restart=calls)
        if not refused:
            raise InvalidInput('Restart revived a superseded source binding')
        result['evaluation_completed'] = True
        result['lifecycle_acceptance_passed'] = not result['acceptance_blockers']
    except Exception as error:
        result.update(evaluation_completed=False, lifecycle_acceptance_passed=False,
                      failure_stage=stage, failure_type=type(error).__name__)
        result['acceptance_blockers'].append('lifecycle_evaluation_incomplete')
    finally:
        if ledger is not None:
            ledger.close()
    return result


def acceptance_exit_code(receipt: dict) -> int:
    """Keep completed negative evidence distinct from an incomplete experiment."""
    if receipt.get('evaluation_completed') is not True:
        return 1
    return 0 if receipt.get('lifecycle_acceptance_passed') is True else 2
