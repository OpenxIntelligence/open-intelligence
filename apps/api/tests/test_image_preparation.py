"""Image disclosure ordering; database behavior is covered by the PG suite.

This small transaction double observes response/authority/event order only.
It uses the real source receipt method and independently authored DICOM bytes;
it does not claim to establish PostgreSQL rollback or HTTP delivery.
"""

from contextlib import contextmanager
from dataclasses import asdict
from datetime import date
import unittest

from dicom_integrity_fixture import dicom_bytes
from oi_api.dicom_integrity import parse_dicom
from oi_api.images import PostgresSourceImages, _FIELDS
from oi_api.sources import PostgresSourceVersions
from open_intelligence.patient_registry import PatientRegistryDenied


class TransactionTrace:
    def __init__(self, order, image_row):
        self.order = order
        self.image_row = image_row
        self.committed = []
        self.pending = []
        self.reject_event = False

    @contextmanager
    def transaction(self):
        self.pending = []
        self.order.append("begin")
        try:
            yield
        except BaseException:
            self.pending = []
            self.order.append("rollback")
            raise
        else:
            self.committed.extend(self.pending)
            self.order.append("commit")

    def _fetchall(self, sql, parameters):
        return []

    def _fetchone(self, sql, parameters):
        if "coalesce(sum(byte_count)" in sql:
            return 0, 0
        if "JOIN clinical_source.source_image_links" in sql:
            return tuple(self.image_row[field] for field in _FIELDS)
        return None

    def _execute(self, sql, parameters):
        self.pending.append(("write", parameters))

    def append_event(self, patient_id, event, **metadata):
        self.order.append("event")
        if self.reject_event:
            raise RuntimeError("AUTHORED-EVENT-FAILURE")
        self.pending.append((event, metadata))


class ImagePreparationTests(unittest.TestCase):
    def setUp(self):
        self.order = []
        self.allowed = True
        self.raw = dicom_bytes(
            patient_id="SUBJECT-ALPHA", issuer="ORG-INSTITUTION/SYS-SYNTH",
            study_uid="2.25.501", series_uid="2.25.502", sop_uid="2.25.503",
            study_date="20260201",
        )
        identity = asdict(parse_dicom(self.raw))
        identity["study_date"] = date(2026, 2, 1)
        self.source_id = "SRC-" + "A" * 32
        self.image_id = "IMG-" + "B" * 32
        image_row = {**identity, "image_id": self.image_id, "case_id": "CASE-ALPHA",
                     "raw": self.raw}
        self.registry = TransactionTrace(self.order, image_row)
        # Exercise the real receipt protocol without pretending this double is
        # a canonical registry or testing source authorization through a stub.
        source_owner = object.__new__(PostgresSourceVersions)
        source_owner.registry = self.registry
        self.images = object.__new__(PostgresSourceImages)
        self.images.registry = self.registry
        self.images.sources = source_owner
        self.images.archive = None  # This ordering double exercises local custody.
        self.images._scope = lambda *args: (
            1, {"case_id": "CASE-ALPHA", "version": 1, "sha256": "a" * 64,
                "event_date": date(2026, 2, 1)},
            ("ORG-INSTITUTION", "SYS-SYNTH", "SUBJECT-ALPHA"),
        )

    def recheck(self):
        self.order.append("authority")
        if not self.allowed:
            raise PatientRegistryDenied("Image unavailable")

    def call(self, operation, prepare=None):
        kwargs = dict(organization="ORG-ALPHA", actor="ACTOR-ALPHA",
                      purpose="operations", recheck_authority=self.recheck)
        if prepare is not None:
            kwargs["prepare_response"] = prepare
        args = ("PATIENT-ALPHA", "CASE-ALPHA", self.source_id)
        if operation == "import":
            return self.images.import_original(*args, self.raw, **kwargs)
        if operation == "index":
            return self.images.list(*args, **kwargs)
        return self.images.original(*args, self.image_id, **kwargs)

    def test_existing_source_receipt_contract_is_preserved(self):
        result = self.call("index")
        self.assertRegex(result["access_receipt_id"], r"^ACCESS-[0-9A-F]{32}$")
        self.assertEqual(self.registry.committed[0][1]["receipt_id"],
                         result["access_receipt_id"])
        self.assertEqual(self.order, ["begin", "authority", "event", "commit"])

    def test_response_is_prepared_before_final_authority_and_event_commit(self):
        for operation in ("import", "index", "original"):
            with self.subTest(operation=operation):
                self.setUp()
                marker = object()

                def prepare(*parts):
                    self.order.append("prepare")
                    self.assertEqual(self.registry.committed, [])
                    if operation == "original":
                        self.assertEqual(parts[0], self.raw)
                        self.assertRegex(parts[1], r"^ACCESS-[0-9A-F]{32}$")
                    return marker

                self.assertIs(self.call(operation, prepare), marker)
                self.assertEqual(self.order, ["begin", "prepare", "authority", "event", "commit"])

    def test_failed_preparation_withholds_response_and_new_receipt(self):
        for operation in ("import", "index", "original"):
            with self.subTest(operation=operation):
                self.setUp()

                def fail(*parts):
                    self.order.append("prepare")
                    raise RuntimeError("AUTHORED-PREPARATION-FAILURE")

                with self.assertRaisesRegex(RuntimeError, "AUTHORED-PREPARATION-FAILURE"):
                    self.call(operation, fail)
                self.assertEqual(self.registry.committed, [])
                self.assertEqual(self.order, ["begin", "prepare", "rollback"])

    def test_authority_withdrawn_during_preparation_withholds_result(self):
        for operation in ("import", "index", "original"):
            with self.subTest(operation=operation):
                self.setUp()

                def revoke(*parts):
                    self.order.append("prepare")
                    self.allowed = False
                    return parts

                with self.assertRaises(PatientRegistryDenied):
                    self.call(operation, revoke)
                self.assertEqual(self.registry.committed, [])
                self.assertEqual(self.order, ["begin", "prepare", "authority", "rollback"])

    def test_failed_event_withholds_already_prepared_result(self):
        for operation in ("import", "index", "original"):
            with self.subTest(operation=operation):
                self.setUp()
                self.registry.reject_event = True

                def prepare(*parts):
                    self.order.append("prepare")
                    return parts

                with self.assertRaisesRegex(RuntimeError, "AUTHORED-EVENT-FAILURE"):
                    self.call(operation, prepare)
                self.assertEqual(self.registry.committed, [])
                self.assertEqual(self.order, ["begin", "prepare", "authority", "event", "rollback"])

    def test_authority_withdrawn_during_audit_append_rolls_back_image_response(self):
        for operation in ("import", "index", "original"):
            with self.subTest(operation=operation):
                self.setUp()
                append_event = self.registry.append_event

                def withdraw_after_append(*args, **kwargs):
                    append_event(*args, **kwargs)
                    self.allowed = False

                self.registry.append_event = withdraw_after_append

                def prepare(*parts):
                    self.order.append("prepare")
                    return parts

                with self.assertRaises(PatientRegistryDenied):
                    self.call(operation, prepare)
                self.assertEqual(self.registry.committed, [])
                self.assertEqual(self.order, ["begin", "prepare", "authority", "event", "authority", "rollback"])


if __name__ == "__main__":
    unittest.main()
