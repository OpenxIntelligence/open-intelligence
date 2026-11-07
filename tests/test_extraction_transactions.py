"""A1 validation and persistence must share the source owner's transaction.

These tests use real CaseStore instances and two SQLite connections. A
one-shot SQL trace callback deterministically schedules a competing write
immediately before BEGIN IMMEDIATE; there are no sleeps or mocked writes.
"""

import sqlite3
import tempfile
import unittest
from pathlib import Path

from open_intelligence import CaseStore, InvalidInput
from open_intelligence.extraction import (
    record_extraction_proposal,
    validate_extraction_proposal,
)

ORIGINAL = b"""OI-SYNTHETIC-REPORT/1
Patient: CASE-ALPHA
Document: TX-ALPHA
Type: pathology
Event-Date: 2026-05-03
Issued-At: 2026-05-05
Finding: baseline|reported|Fictional original sentence.
"""
AMENDED = b"""OI-SYNTHETIC-REPORT/1
Patient: CASE-ALPHA
Document: TX-ALPHA
Type: pathology
Event-Date: 2026-05-03
Issued-At: 2026-05-06
Amends: TX-ALPHA@1
Finding: baseline|reported|Fictional revised sentence.
"""


class ExtractionTransactionTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        path = Path(temporary.name) / "case.sqlite"
        self.store = CaseStore(path)
        self.addCleanup(self.store.close)
        self.store.add_case("CASE-ALPHA", "Fictional Alpha")
        self.source_id = self.store.import_report(
            "CASE-ALPHA", ORIGINAL)["source_id"]
        self.other = CaseStore(path)
        self.addCleanup(self.other.close)
        self.other.db.execute("PRAGMA busy_timeout=0")
        self.callback_calls = []
        self.callback_errors = []

    def field(self, key="new-finding"):
        return {"finding_key": key, "certainty": "reported",
                "quote": "Fictional original sentence.", "source_line": 7}

    def assertion_keys(self, connection=None):
        connection = self.store.db if connection is None else connection
        return [row[0] for row in connection.execute(
            "SELECT finding_key FROM assertions WHERE source_version_id=? "
            "ORDER BY finding_key", (self.source_id,)).fetchall()]

    def before_begin(self, operation):
        def trace(statement):
            if (statement.strip().upper() == "BEGIN IMMEDIATE"
                    and not self.callback_calls):
                self.callback_calls.append(statement)
                # sqlite3 suppresses callback exceptions; retain and assert
                # them explicitly so a broken interleaving cannot pass.
                try:
                    operation()
                except Exception as error:
                    self.callback_errors.append(error)
        self.store.db.set_trace_callback(trace)
        self.addCleanup(self.store.db.set_trace_callback, None)

    def assert_interleaving_ran(self):
        self.assertEqual(len(self.callback_calls), 1)
        self.assertEqual(self.callback_errors, [])

    def test_amendment_before_writer_reservation_is_revalidated(self):
        self.before_begin(lambda: self.other.import_report(
            "CASE-ALPHA", AMENDED))
        result = record_extraction_proposal(
            self.store, "CASE-ALPHA", self.source_id, [self.field()])
        self.assert_interleaving_ran()
        self.assertEqual(result.kept, [])
        self.assertEqual(result.inserted_assertion_ids, [])
        self.assertEqual([item["reason"] for item in result.dropped],
                         ["superseded_source_version"])
        self.assertEqual(self.assertion_keys(), ["baseline"])
        self.assertFalse(self.store.db.in_transaction)

    def test_original_integrity_is_rechecked_after_writer_reservation(self):
        def corrupt_original():
            with self.other.db:
                self.other.db.execute(
                    "UPDATE source_versions SET raw=? WHERE id=?",
                    (b"Corrupted fixture bytes.", self.source_id))
        self.before_begin(corrupt_original)
        result = record_extraction_proposal(
            self.store, "CASE-ALPHA", self.source_id, [self.field()])
        self.assert_interleaving_ran()
        self.assertEqual(result.kept, [])
        self.assertEqual(result.inserted_assertion_ids, [])
        self.assertEqual([item["reason"] for item in result.dropped],
                         ["source_integrity_mismatch"])
        self.assertEqual(self.assertion_keys(), ["baseline"])

    def test_competing_same_key_returns_typed_drop_not_integrity_error(self):
        self.before_begin(lambda: record_extraction_proposal(
            self.other, "CASE-ALPHA", self.source_id, [self.field()]))
        result = None
        failure = None
        try:
            result = record_extraction_proposal(
                self.store, "CASE-ALPHA", self.source_id, [self.field()])
        except sqlite3.IntegrityError as error:
            failure = error
        self.assert_interleaving_ran()
        self.assertIsNone(failure, "Duplicate was checked before the writer lock")
        self.assertEqual(result.kept, [])
        self.assertEqual(result.inserted_assertion_ids, [])
        self.assertEqual([item["reason"] for item in result.dropped],
                         ["finding_already_asserted"])
        self.assertEqual(self.assertion_keys(), ["baseline", "new-finding"])
        self.assertFalse(self.store.db.in_transaction)

    def test_writer_reservation_is_held_during_source_validation(self):
        observed = []
        errors = []
        def trace(statement):
            if "FROM source_versions WHERE id=" not in statement or observed:
                return
            try:
                self.other.db.execute("BEGIN IMMEDIATE")
            except sqlite3.OperationalError as error:
                if error.sqlite_errorcode & 255 == sqlite3.SQLITE_BUSY:
                    observed.append("busy")
                else:
                    errors.append(error)
            else:
                observed.append("acquired")
                self.other.db.rollback()
        self.store.db.set_trace_callback(trace)
        self.addCleanup(self.store.db.set_trace_callback, None)
        result = record_extraction_proposal(
            self.store, "CASE-ALPHA", self.source_id, [self.field()])
        self.store.db.set_trace_callback(None)
        self.assertEqual(errors, [])
        self.assertEqual(observed, ["busy"])
        self.assertEqual(len(result.inserted_assertion_ids), 1)
        self.assertEqual(self.assertion_keys(self.other.db),
                         ["baseline", "new-finding"])

    def test_validation_only_remains_read_only(self):
        result = validate_extraction_proposal(
            self.store, "CASE-ALPHA", self.source_id, [self.field()])
        self.assertEqual(len(result.kept), 1)
        self.assertEqual(result.inserted_assertion_ids, [])
        self.assertFalse(self.store.db.in_transaction)
        self.assertEqual(self.assertion_keys(), ["baseline"])

    def test_all_rejected_standalone_proposal_leaves_no_transaction(self):
        bad_field = {**self.field(), "quote": "Absent quotation."}
        result = record_extraction_proposal(
            self.store, "CASE-ALPHA", self.source_id, [bad_field])
        self.assertEqual(result.kept, [])
        self.assertEqual(result.dropped[0]["reason"], "source_quote_mismatch")
        self.assertFalse(self.store.db.in_transaction)
        self.assertEqual(self.assertion_keys(self.other.db), ["baseline"])

    def test_invalid_container_leaves_no_standalone_transaction(self):
        with self.assertRaises(InvalidInput):
            record_extraction_proposal(
                self.store, "CASE-ALPHA", self.source_id, None)
        self.assertFalse(self.store.db.in_transaction)
        self.assertEqual(self.assertion_keys(), ["baseline"])

    def test_caller_transaction_is_not_committed_and_can_roll_back(self):
        self.store.db.execute("BEGIN IMMEDIATE")
        result = record_extraction_proposal(
            self.store, "CASE-ALPHA", self.source_id, [self.field()])
        self.assertEqual(len(result.inserted_assertion_ids), 1)
        self.assertTrue(self.store.db.in_transaction)
        self.assertEqual(self.assertion_keys(self.other.db), ["baseline"])
        self.store.db.rollback()
        self.assertEqual(self.assertion_keys(), ["baseline"])

    def test_caller_transaction_retains_control_after_a_rejected_proposal(self):
        self.store.db.execute("BEGIN IMMEDIATE")
        self.store.db.execute(
            "UPDATE cases SET label=? WHERE case_id=?",
            ("Fictional pending label", "CASE-ALPHA"))
        result = record_extraction_proposal(
            self.store, "CASE-ALPHA", self.source_id,
            [{**self.field(), "quote": "Absent quotation."}])
        self.assertEqual(result.kept, [])
        self.assertTrue(self.store.db.in_transaction)
        self.assertEqual(self.other.db.execute(
            "SELECT label FROM cases WHERE case_id='CASE-ALPHA'"
        ).fetchone()[0], "Fictional Alpha")
        self.store.db.rollback()
        self.assertEqual(self.store.db.execute(
            "SELECT label FROM cases WHERE case_id='CASE-ALPHA'"
        ).fetchone()[0], "Fictional Alpha")

    def test_standalone_insert_failure_rolls_back_every_new_assertion(self):
        self.store.db.execute("""
            CREATE TEMP TRIGGER reject_fixture_assertion
            BEFORE INSERT ON assertions
            WHEN NEW.finding_key='rejected-second'
            BEGIN SELECT RAISE(ABORT, 'fixture insertion failure'); END
        """)
        with self.assertRaisesRegex(sqlite3.IntegrityError,
                                    "fixture insertion failure"):
            record_extraction_proposal(
                self.store, "CASE-ALPHA", self.source_id,
                [self.field("accepted-first"), self.field("rejected-second")])
        self.assertFalse(self.store.db.in_transaction)
        self.assertEqual(self.assertion_keys(self.other.db), ["baseline"])


    def test_caller_insert_failure_removes_only_the_failed_batch(self):
        self.store.db.execute("""
            CREATE TEMP TRIGGER reject_nested_assertion
            BEFORE INSERT ON assertions
            WHEN NEW.finding_key='rejected-second'
            BEGIN SELECT RAISE(ABORT, 'fixture nested insertion failure'); END
        """)
        self.store.db.execute("BEGIN IMMEDIATE")
        self.store.db.execute(
            "UPDATE cases SET label=? WHERE case_id=?",
            ("Fictional pending label", "CASE-ALPHA"))
        prior = record_extraction_proposal(
            self.store, "CASE-ALPHA", self.source_id,
            [self.field("earlier-proposal")])
        self.assertEqual(len(prior.inserted_assertion_ids), 1)
        with self.assertRaisesRegex(sqlite3.IntegrityError,
                                    "fixture nested insertion failure"):
            record_extraction_proposal(
                self.store, "CASE-ALPHA", self.source_id,
                [self.field("accepted-first"), self.field("rejected-second")])
        self.assertTrue(self.store.db.in_transaction)
        self.assertEqual(self.assertion_keys(), ["baseline", "earlier-proposal"])
        self.assertEqual(self.store.db.execute(
            "SELECT label FROM cases WHERE case_id='CASE-ALPHA'"
        ).fetchone()[0], "Fictional pending label")
        self.assertEqual(self.assertion_keys(self.other.db), ["baseline"])
        self.assertEqual(self.other.db.execute(
            "SELECT label FROM cases WHERE case_id='CASE-ALPHA'"
        ).fetchone()[0], "Fictional Alpha")
        self.store.db.commit()
        self.assertEqual(self.assertion_keys(self.other.db),
                         ["baseline", "earlier-proposal"])
        self.assertEqual(self.other.db.execute(
            "SELECT label FROM cases WHERE case_id='CASE-ALPHA'"
        ).fetchone()[0], "Fictional pending label")

    def test_caller_can_retry_the_entire_failed_batch_with_complete_ids(self):
        self.store.db.execute("""
            CREATE TEMP TRIGGER reject_retry_assertion
            BEFORE INSERT ON assertions
            WHEN NEW.finding_key='retry-second'
            BEGIN SELECT RAISE(ABORT, 'fixture retry failure'); END
        """)
        self.store.db.execute("BEGIN IMMEDIATE")
        fields = [self.field("retry-first"), self.field("retry-second")]
        with self.assertRaisesRegex(sqlite3.IntegrityError, "fixture retry failure"):
            record_extraction_proposal(
                self.store, "CASE-ALPHA", self.source_id, fields)
        self.store.db.execute("DROP TRIGGER reject_retry_assertion")
        result = record_extraction_proposal(
            self.store, "CASE-ALPHA", self.source_id, fields)
        self.assertEqual(result.dropped, [])
        self.assertEqual(len(result.inserted_assertion_ids), 2)
        saved_keys = [self.store.db.execute(
            "SELECT finding_key FROM assertions WHERE id=?", (assertion_id,)
        ).fetchone()[0] for assertion_id in result.inserted_assertion_ids]
        self.assertEqual(saved_keys, ["retry-first", "retry-second"])
        self.assertTrue(self.store.db.in_transaction)
        self.assertEqual(self.assertion_keys(self.other.db), ["baseline"])
        self.store.db.rollback()
        self.assertEqual(self.assertion_keys(), ["baseline"])

    def test_caller_savepoint_can_undo_a_successful_proposal(self):
        self.store.db.execute("BEGIN IMMEDIATE")
        self.store.db.execute(
            "UPDATE cases SET label=? WHERE case_id=?",
            ("Fictional pending label", "CASE-ALPHA"))
        self.store.db.execute("SAVEPOINT caller_scope")
        result = record_extraction_proposal(
            self.store, "CASE-ALPHA", self.source_id, [self.field()])
        self.assertEqual(len(result.inserted_assertion_ids), 1)
        self.store.db.execute("ROLLBACK TO SAVEPOINT caller_scope")
        self.store.db.execute("RELEASE SAVEPOINT caller_scope")
        self.assertTrue(self.store.db.in_transaction)
        self.assertEqual(self.assertion_keys(), ["baseline"])
        self.assertEqual(self.store.db.execute(
            "SELECT label FROM cases WHERE case_id='CASE-ALPHA'"
        ).fetchone()[0], "Fictional pending label")
        self.store.db.commit()
        self.assertEqual(self.assertion_keys(self.other.db), ["baseline"])
        self.assertEqual(self.other.db.execute(
            "SELECT label FROM cases WHERE case_id='CASE-ALPHA'"
        ).fetchone()[0], "Fictional pending label")

    def test_database_rollback_preserves_original_failure_and_connection_reuse(self):
        self.store.db.execute("""
            CREATE TEMP TRIGGER rollback_nested_assertion
            BEFORE INSERT ON assertions
            WHEN NEW.finding_key='rollback-second'
            BEGIN SELECT RAISE(ROLLBACK, 'fixture whole transaction rollback'); END
        """)
        self.store.db.execute("BEGIN IMMEDIATE")
        self.store.db.execute(
            "UPDATE cases SET label=? WHERE case_id=?",
            ("Fictional pending label", "CASE-ALPHA"))
        with self.assertRaisesRegex(sqlite3.IntegrityError,
                                    "fixture whole transaction rollback"):
            record_extraction_proposal(
                self.store, "CASE-ALPHA", self.source_id,
                [self.field("rollback-first"), self.field("rollback-second")])
        self.assertFalse(self.store.db.in_transaction)
        self.assertEqual(self.assertion_keys(self.other.db), ["baseline"])
        self.assertEqual(self.other.db.execute(
            "SELECT label FROM cases WHERE case_id='CASE-ALPHA'"
        ).fetchone()[0], "Fictional Alpha")
        result = record_extraction_proposal(
            self.store, "CASE-ALPHA", self.source_id, [self.field("after-rollback")])
        self.assertEqual(len(result.inserted_assertion_ids), 1)
        self.assertEqual(self.assertion_keys(self.other.db),
                         ["after-rollback", "baseline"])

    def test_caller_validation_error_does_not_discard_pending_work(self):
        self.store.db.execute("BEGIN IMMEDIATE")
        self.store.db.execute(
            "UPDATE cases SET label=? WHERE case_id=?",
            ("Fictional pending label", "CASE-ALPHA"))
        with self.assertRaises(InvalidInput):
            record_extraction_proposal(
                self.store, "CASE-ALPHA", self.source_id, None)
        self.assertTrue(self.store.db.in_transaction)
        self.assertEqual(self.assertion_keys(), ["baseline"])
        self.assertEqual(self.store.db.execute(
            "SELECT label FROM cases WHERE case_id='CASE-ALPHA'"
        ).fetchone()[0], "Fictional pending label")
        result = record_extraction_proposal(
            self.store, "CASE-ALPHA", self.source_id, [self.field("after-invalid")])
        self.assertEqual(len(result.inserted_assertion_ids), 1)
        self.store.db.commit()
        self.assertEqual(self.assertion_keys(self.other.db),
                         ["after-invalid", "baseline"])
        self.assertEqual(self.other.db.execute(
            "SELECT label FROM cases WHERE case_id='CASE-ALPHA'"
        ).fetchone()[0], "Fictional pending label")


if __name__ == "__main__":
    unittest.main()
