"""PD-01 first-party encounter operations regression, using synthetic test patients."""
import json
import sqlite3
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from open_intelligence.store import CaseStore, InvalidInput
from open_intelligence.clinical_encounters import (
    ClinicalEncounters, ClinicalAuthorizationError, ClinicalConflict,
)


class ClinicalEncounterTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.path = Path(self.tmp.name) / 'oi.sqlite'
        self.store = CaseStore(self.path)
        self.store.add_case('CASE-ONE', 'Independent synthetic patient')
        self.store.add_case('CASE-TWO', 'Different synthetic patient')
        self.authorized = lambda actor, case, action, purpose: (
            actor == 'idp:clinician-001' and case == 'CASE-ONE'
            and purpose == 'care' and action in {
                'encounter.schedule', 'encounter.transition', 'encounter.read',
                'note.write', 'note.read', 'note.attest'})
        self.ops = ClinicalEncounters(self.store, self.authorized)
        self.actor = {'actor': 'idp:clinician-001', 'purpose': 'care'}

    def tearDown(self):
        self.store.close()
        self.tmp.cleanup()

    def schedule(self, key='req-schedule-0001'):
        return self.ops.schedule('CASE-ONE', 'ENCOUNTER-001', 'outpatient',
                                 '2026-11-02', request_key=key, **self.actor)

    def begin(self):
        scheduled = self.schedule()
        return self.ops.transition('CASE-ONE', scheduled['encounter_id'], 'in_progress',
                                   expected_revision=1, request_key='req-begin-000001',
                                   **self.actor)

    def test_no_host_authorizer_denies_both_read_and_write(self):
        instance = ClinicalEncounters(self.store)
        with self.assertRaises(ClinicalAuthorizationError):
            instance.list_encounters('CASE-ONE', **self.actor)
        with self.assertRaises(ClinicalAuthorizationError):
            instance.schedule('CASE-ONE', 'ENCOUNTER-002', 'outpatient', '2026-11-02',
                              request_key='req-schedule-0002', **self.actor)
        self.assertEqual(self.ops.list_encounters('CASE-ONE', **self.actor), [])

    def test_fake_or_wrong_subject_or_purpose_is_denied(self):
        for actor, case, purpose in [
            ('fake:clinician-002', 'CASE-ONE', 'care'),
            ('idp:clinician-001', 'CASE-TWO', 'care'),
            ('idp:clinician-001', 'CASE-ONE', 'research')]:
            with self.subTest(actor=actor, case=case):
                with self.assertRaises(ClinicalAuthorizationError):
                    self.ops.list_encounters(case, actor=actor, purpose=purpose)
        self.assertEqual(self.store.db.execute('SELECT COUNT(*) FROM clinical_encounters').fetchone()[0], 0)

    def test_authorizer_exception_fails_closed(self):
        denial = ClinicalEncounters(self.store, lambda *_: (_ for _ in ()).throw(RuntimeError('oops')))
        with self.assertRaises(ClinicalAuthorizationError):
            denial.list_encounters('CASE-ONE', **self.actor)

    def test_schedule_persists_in_same_patient_database_and_event_ledger(self):
        a = self.schedule()
        self.assertEqual(a['status'], 'scheduled')
        self.assertEqual(a['revision'], 1)
        self.assertEqual(len(self.store.cases()), 2)
        self.assertEqual(self.ops.list_encounters('CASE-ONE', **self.actor)[0]['id'], a['encounter_id'])
        event = self.store.db.execute("SELECT * FROM events WHERE kind='clinical_encounter_scheduled'").fetchone()
        self.assertEqual(event['case_id'], 'CASE-ONE')
        detail = json.loads(event['details'])
        self.assertEqual(detail['encounter_id'], a['encounter_id'])
        self.assertNotIn('Independent synthetic patient', event['details'])
        self.assertNotIn('ENCOUNTER-001', event['details'])

    def test_commands_idempotent_across_database_restart(self):
        first = self.schedule()
        self.assertEqual(self.schedule(), first)
        count = self.store.db.execute('SELECT COUNT(*) FROM events WHERE kind=?',
                                      ('clinical_encounter_scheduled',)).fetchone()[0]
        self.assertEqual(count, 1)
        self.store.close()
        self.store = CaseStore(self.path)
        self.ops = ClinicalEncounters(self.store, self.authorized)
        self.assertEqual(self.schedule(), first)
        self.assertEqual(self.store.db.execute("SELECT COUNT(*) FROM clinical_encounters").fetchone()[0], 1)

    def test_idempotency_reuse_for_different_command_fails_closed(self):
        self.schedule()
        with self.assertRaisesRegex(ClinicalConflict, 'Idempotency'):
            self.ops.schedule('CASE-ONE', 'ENCOUNTER-002', 'telehealth', '2026-11-02',
                              request_key='req-schedule-0001', **self.actor)
        with self.assertRaisesRegex(ClinicalConflict, 'Idempotency'):
            self.ops.transition('CASE-ONE', 1, 'in_progress', expected_revision=1,
                                request_key='req-schedule-0001', **self.actor)
        self.assertEqual(len(self.ops.list_encounters('CASE-ONE', **self.actor)), 1)

    def test_unique_encounter_identifier_and_invalid_input(self):
        self.schedule()
        with self.assertRaisesRegex(ClinicalConflict, 'already exists'):
            self.ops.schedule('CASE-ONE', 'ENCOUNTER-001', 'outpatient', '2026-11-02',
                              request_key='req-other-create', **self.actor)
        with self.assertRaises(InvalidInput):
            self.ops.schedule('CASE-ONE', 'INVALID-1', 'unknown', '2026-11-02',
                              request_key='req-new-create', **self.actor)
        with self.assertRaises(InvalidInput):
            self.ops.schedule('CASE-ONE', 'INVALID-1', 'other', '2026-99-99',
                              request_key='req-new-create', **self.actor)

    def test_transition_requires_expected_version_and_valid_edges(self):
        id_ = self.schedule()['encounter_id']
        with self.assertRaises(ClinicalConflict):
            self.ops.transition('CASE-ONE', id_, 'completed', expected_revision=1,
                                request_key='req-invalid-edge', **self.actor)
        started = self.ops.transition('CASE-ONE', id_, 'in_progress', expected_revision=1,
                                      request_key='req-begin-000001', **self.actor)
        self.assertEqual(started['revision'], 2)
        with self.assertRaisesRegex(ClinicalConflict, 'revision changed'):
            self.ops.transition('CASE-ONE', id_, 'completed', expected_revision=1,
                                request_key='req-stale-rev-1', **self.actor)
        done = self.ops.transition('CASE-ONE', id_, 'completed', expected_revision=2,
                                   request_key='req-finish-00001', **self.actor)
        self.assertEqual(done['revision'], 3)
        with self.assertRaises(ClinicalConflict):
            self.ops.transition('CASE-ONE', id_, 'in_progress', expected_revision=3,
                                request_key='req-return-to-work', **self.actor)

    def test_cancelled_encounter_cannot_accept_notes(self):
        id_ = self.schedule()['encounter_id']
        self.ops.transition('CASE-ONE', id_, 'cancelled', expected_revision=1,
                            request_key='req-cancel-00001', **self.actor)
        with self.assertRaises(ClinicalConflict):
            self.ops.write_note('CASE-ONE', id_, 'NOTE-001', 'Cancelled clinical record',
                                expected_version=0, request_key='req-note-0000001', **self.actor)

    def test_note_draft_attestation_and_correction_are_immutable(self):
        id_ = self.begin()['encounter_id']
        one = self.ops.write_note('CASE-ONE', id_, 'NOTE-001', 'First clinician-authored clinical note',
                                  expected_version=0, request_key='req-note-0000001', **self.actor)
        self.assertEqual(one['status'], 'draft')
        two = self.ops.write_note('CASE-ONE', id_, 'NOTE-001', 'Corrected wording before attestation',
                                  expected_version=1, request_key='req-note-0000002', **self.actor)
        self.assertEqual(two['version'], 2)
        attested = self.ops.attest_note('CASE-ONE', id_, 'NOTE-001', expected_version=2,
                                       request_key='req-attest-00001', **self.actor)
        self.assertEqual(attested['status'], 'attested')
        with self.assertRaisesRegex(ClinicalConflict, 'correction reason'):
            self.ops.write_note('CASE-ONE', id_, 'NOTE-001', 'Silent rewrite attempted',
                                expected_version=3, request_key='req-unsafe-overwrite', **self.actor)
        pending = self.ops.write_note('CASE-ONE', id_, 'NOTE-001', 'Late corrected clinical wording',
                                      expected_version=3, correction_reason='Original transcription error',
                                      request_key='req-amend-000001', **self.actor)
        self.assertEqual(pending['status'], 'draft_correction')
        self.assertNotEqual(pending['sha256'], one['sha256'])
        final = self.ops.attest_note('CASE-ONE', id_, 'NOTE-001', expected_version=4,
                                     request_key='req-attest-00002', **self.actor)
        self.assertEqual(final['status'], 'attested_correction')
        history = self.ops.note_history('CASE-ONE', id_, 'NOTE-001', **self.actor)
        self.assertEqual([x['version'] for x in history], [1, 2, 3, 4, 5])
        self.assertEqual(history[0]['body'], 'First clinician-authored clinical note')
        self.assertEqual(history[2]['body'], 'Corrected wording before attestation')
        self.assertEqual(history[3]['amendment_reason'], 'Original transcription error')
        self.assertEqual(history[4]['supersedes_id'], history[3]['id'])
        self.assertEqual(history[4]['sha256'], history[3]['sha256'])
        self.assertEqual(self.store.db.execute("SELECT COUNT(*) FROM events WHERE kind LIKE 'clinical_note_%'").fetchone()[0], 5)
        # Clinical note text itself must never leak into the event log.
        all_events = ' '.join(e['details'] for e in self.store.db.execute('SELECT details FROM events').fetchall())
        self.assertNotIn('First clinician-authored clinical note', all_events)
        self.assertNotIn('Late corrected clinical wording', all_events)

    def test_immutable_versions_enforced_by_database_not_only_service(self):
        encounter_id = self.begin()['encounter_id']
        note = self.ops.write_note('CASE-ONE', encounter_id, 'NOTE-001',
                                   'Immutable content in the original source',
                                   expected_version=0, request_key='req-note-0000001',
                                   **self.actor)
        version_id = self.ops.note_history('CASE-ONE', encounter_id, 'NOTE-001',
                                           **self.actor)[0]['id']
        with self.assertRaisesRegex(sqlite3.IntegrityError, 'immutable'):
            with self.store.db:
                self.store.db.execute('UPDATE clinical_note_versions SET body=? WHERE id=?',
                                      ('unattributed replacement', version_id))
        with self.assertRaisesRegex(sqlite3.IntegrityError, 'immutable'):
            with self.store.db:
                self.store.db.execute('DELETE FROM clinical_note_versions WHERE id=?', (version_id,))
        with self.assertRaisesRegex(sqlite3.IntegrityError, 'immutable'):
            with self.store.db:
                self.store.db.execute('DELETE FROM clinical_encounter_commands WHERE case_id=?', ('CASE-ONE',))
        self.assertEqual(self.ops.note_history('CASE-ONE', encounter_id, 'NOTE-001',
                                               **self.actor)[0]['sha256'], note['sha256'])

    def test_no_reassignment_or_other_case_event_on_cross_patient_id(self):
        # Even a permissive test authorizer cannot escape the SQL case scope.
        created = self.schedule()
        cross_case = ClinicalEncounters(self.store, lambda *_: True)
        before = self.store.db.execute('SELECT COUNT(*) FROM events').fetchone()[0]
        with self.assertRaisesRegex(InvalidInput, 'not found in this patient'):
            cross_case.transition('CASE-TWO', created['encounter_id'], 'in_progress',
                                  expected_revision=1, request_key='req-wrong-subject',
                                  **self.actor)
        self.assertEqual(before, self.store.db.execute('SELECT COUNT(*) FROM events').fetchone()[0])

    def test_same_idempotency_key_is_not_usable_by_different_actor(self):
        self.schedule()
        alternative = ClinicalEncounters(self.store, lambda actor, *_: actor in {'idp:clinician-001', 'idp:clinician-002'})
        with self.assertRaises(ClinicalConflict):
            alternative.schedule('CASE-ONE', 'ENCOUNTER-001', 'outpatient', '2026-11-02',
                                 request_key='req-schedule-0001', actor='idp:clinician-002', purpose='care')

    def test_note_patient_scope_prevents_cross_patient_leakage(self):
        id_ = self.begin()['encounter_id']
        self.ops.write_note('CASE-ONE', id_, 'NOTE-001', 'Source-linked first-party note',
                            expected_version=0, request_key='req-note-0000001', **self.actor)
        instance = ClinicalEncounters(self.store, lambda *_: True)  # fake authorized test of ID scope
        with self.assertRaisesRegex(InvalidInput, 'not found in this patient'):
            instance.note_history('CASE-TWO', id_, 'NOTE-001', **self.actor)
        with self.assertRaisesRegex(InvalidInput, 'not found in this patient'):
            instance.write_note('CASE-TWO', id_, 'NOTE-001', 'Unsafe case crossover',
                                expected_version=1, request_key='req-wrong-case-1', **self.actor)

    def test_transaction_rolls_back_if_shared_event_insert_fails(self):
        with patch.object(self.store, '_event', side_effect=sqlite3.IntegrityError('simulated event failure')):
            with self.assertRaises(sqlite3.IntegrityError):
                self.schedule()
        self.assertEqual(self.store.db.execute('SELECT COUNT(*) FROM clinical_encounters').fetchone()[0], 0)
        self.assertEqual(self.store.db.execute('SELECT COUNT(*) FROM clinical_encounter_commands').fetchone()[0], 0)
        self.assertEqual(self.schedule()['revision'], 1)

    def test_attestation_denied_without_authority_even_if_can_edit(self):
        id_ = self.begin()['encounter_id']
        self.ops.write_note('CASE-ONE', id_, 'NOTE-001', 'Clinician draft awaiting attestation',
                            expected_version=0, request_key='req-note-0000001', **self.actor)
        no_attest = ClinicalEncounters(self.store, lambda actor, case, action, purpose: action != 'note.attest')
        with self.assertRaises(ClinicalAuthorizationError):
            no_attest.attest_note('CASE-ONE', id_, 'NOTE-001', expected_version=1,
                                  request_key='req-bypass-0001', **self.actor)
        self.assertEqual(len(self.ops.note_history('CASE-ONE', id_, 'NOTE-001', **self.actor)), 1)

    def test_idempotency_has_conflict_when_content_differs(self):
        id_ = self.begin()['encounter_id']
        first = self.ops.write_note('CASE-ONE', id_, 'NOTE-001', 'Original signed-text draft',
                                    expected_version=0, request_key='req-note-0000001', **self.actor)
        self.assertEqual(self.ops.write_note('CASE-ONE', id_, 'NOTE-001', 'Original signed-text draft',
                                             expected_version=0, request_key='req-note-0000001', **self.actor), first)
        with self.assertRaises(ClinicalConflict):
            self.ops.write_note('CASE-ONE', id_, 'NOTE-001', 'Content changed with reused key',
                                expected_version=0, request_key='req-note-0000001', **self.actor)
        self.assertEqual(len(self.ops.note_history('CASE-ONE', id_, 'NOTE-001', **self.actor)), 1)


if __name__ == '__main__':
    unittest.main()
