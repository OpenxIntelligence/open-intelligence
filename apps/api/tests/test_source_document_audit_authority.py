"""Actual PostgreSQL/HTTP authority after source access-event persistence.

All originals and credentials are independently fictional. The hook performs
the real event SQL before withdrawing one grant from the synthetic provider.
Snapshots cover durable owner rows, not nontransactional sequence allocation.
"""
import base64
from copy import deepcopy
import hashlib
import json
from unittest.mock import patch
from urllib.error import HTTPError
from urllib.request import Request, ProxyHandler, build_opener

from sqlalchemy import text

from http_support import running_server
from oi_api.app import create_app
from open_intelligence.postgres_registry import PostgresPatientRegistry
from test_patients import TOKEN_A, request
from test_source_versions import ORIGINAL, AMENDED, SourceVersionFixture


EVENT_TABLE = "identity.identity_domain_events"
DOCUMENT_RAW = (
    b"Independently fictional audit-tail document.\n"
    b"Marker pending.\nSecond passage.\n"
)
DOCUMENT_AMENDED = DOCUMENT_RAW + b"Independently fictional amendment.\n"


class SourceDocumentAuditAuthorityTests(SourceVersionFixture):
    def durable_rows(self):
        with self.engine.connect() as connection:
            names = connection.execute(text(
                "SELECT table_schema,table_name FROM information_schema.tables "
                "WHERE table_schema IN "
                "('identity','coordination','clinical_source','investigation') "
                "AND table_type='BASE TABLE' ORDER BY table_schema,table_name"
            )).all()
            return {
                f"{schema}.{name}": connection.execute(text(
                    f"SELECT row_to_json(t)::text FROM {schema}.{name} t "
                    "ORDER BY row_to_json(t)::text"
                )).scalars().all()
                for schema, name in names
            }

    def events(self):
        with self.engine.connect() as connection:
            return [
                tuple(row) for row in connection.execute(text(
                    "SELECT event_type,metadata_json "
                    "FROM identity.identity_domain_events ORDER BY id"
                ))
            ]

    def get_bytes(self, base, path):
        req = Request(
            base + path, headers={"Authorization": "Bearer " + TOKEN_A}
        )
        try:
            response = build_opener(ProxyHandler({})).open(req, timeout=5)
        except HTTPError as error:
            response = error
        with response:
            return response.status, response.read(), response.headers

    def withheld_then_retry(self, base, patient, path, event, action, *,
                            expected_bytes=None):
        initial = deepcopy(self.creds)
        before = self.durable_rows()
        before_events = self.events()
        append = PostgresPatientRegistry.append_event
        observed = []

        def append_then_withdraw(registry, patient_id, kind, **details):
            result = append(registry, patient_id, kind, **details)
            if patient_id == patient and kind == event:
                self.assertTrue(registry._transaction_active)
                observed.append(dict(details))
                if len(observed) == 1:
                    self.creds[0]["actions"].remove(action)
                    self.write()
            return result

        try:
            with patch.object(
                PostgresPatientRegistry, "append_event", append_then_withdraw
            ):
                status, raw, headers = self.get_bytes(base, path)
        finally:
            self.creds = initial
            self.write()

        self.assertEqual(len(observed), 1)
        self.assertEqual(
            (status, self.durable_rows() == before), (404, True)
        )
        self.assertEqual(json.loads(raw), {"detail": "Patient unavailable"})
        self.assertEqual(headers["Cache-Control"], "no-store")
        self.assertNotIn("X-Access-Receipt-ID", headers)
        self.assertNotIn("X-Content-SHA256", headers)
        self.assertNotIn("Content-Disposition", headers)
        self.assertEqual(self.events(), before_events)
        for private in (patient.encode(), TOKEN_A.encode(),
                        b"ACCESS-", b"Marker pending.", b"Fictional"):
            self.assertNotIn(private, raw)

        # Fresh authority must permit the same read without changing its owner.
        status, raw, headers = self.get_bytes(base, path)
        self.assertEqual(status, 200, raw)
        self.assertEqual(headers["Cache-Control"], "no-store")
        if expected_bytes is None:
            result = json.loads(raw)
            receipt = result["access_receipt_id"]
        else:
            self.assertEqual(raw, expected_bytes)
            self.assertEqual(
                headers["X-Content-SHA256"],
                hashlib.sha256(expected_bytes).hexdigest(),
            )
            result = raw
            receipt = headers["X-Access-Receipt-ID"]
        self.assertRegex(receipt, r"^ACCESS-[0-9A-F]{32}$")
        self.assertNotEqual(receipt, observed[0]["receipt_id"])

        after_events = self.events()
        self.assertEqual(len(after_events), len(before_events) + 1)
        self.assertEqual(after_events[:-1], before_events)
        self.assertEqual(after_events[-1][0], event)
        self.assertEqual(after_events[-1][1]["receipt_id"], receipt)
        after = self.durable_rows()
        self.assertEqual(set(after), set(before))
        for name, rows in before.items():
            if name != EVENT_TABLE:
                self.assertEqual(after[name], rows, name)
        return result

    def structured_originals(self, base):
        patient = self.setup_case(base)
        versions = []
        for original, state in ((ORIGINAL, "superseded"), (AMENDED, "current")):
            status, saved, _ = self.ingest(base, patient, original)
            self.assertEqual(status, 201, saved)
            versions.append((saved["source_id"], original, state))
        return patient, versions

    def document_originals(self, base):
        patient = self.setup_case(base)
        prefix = self.url(patient).removesuffix("/sources") + "/documents"
        versions = []
        for version, raw in enumerate((DOCUMENT_RAW, DOCUMENT_AMENDED), 1):
            metadata = {
                "document_id": "DOC-AUDIT-TAIL",
                "kind": "pathology",
                "event_date": "2026-01-10",
                "issued_at": "2026-01-11",
                "manual_transcription_confirmed": True,
            }
            if version == 2:
                metadata["amends_version"] = 1
            payload = {
                "synthetic": True,
                "filename": "fictional-audit-tail.txt",
                "original_base64": base64.b64encode(raw).decode(),
                "confirmed_case_id": "CASE-ALPHA",
                "expected_sha256": hashlib.sha256(raw).hexdigest(),
                "metadata": metadata,
                "findings": [{
                    "key": "marker", "state": "pending",
                    "quote": "Marker pending.", "line": 2,
                }],
            }
            status, saved, _ = request(
                base, prefix, token=TOKEN_A, body=payload
            )
            self.assertEqual(status, 201, saved)
            self.assertEqual(saved["version"], version)
            if version == 1:
                correction = {
                    "synthetic": True,
                    "request_key": "AUDIT-TAIL-CORRECTION",
                    "expected_revision_id": saved["annotation_revision_id"],
                    "confirmed_case_id": "CASE-ALPHA",
                    "expected_sha256": payload["expected_sha256"],
                    "reason": "Correct the independently authored selection",
                    "findings": [{
                        "key": "passage", "state": "reported",
                        "quote": "Second passage.", "line": 3,
                    }],
                }
                status, corrected, _ = request(
                    base, prefix + "/" + saved["source_id"] + "/annotations",
                    token=TOKEN_A, body=correction,
                )
                self.assertEqual(status, 201, corrected)
            versions.append((
                saved["source_id"], raw,
                "superseded" if version == 1 else "current",
                2 if version == 1 else 1,
            ))
        return patient, prefix, versions

    def test_source_index_and_world_model_withdrawal_after_real_audit(self):
        with running_server(create_app(self.settings)) as base:
            patient, _ = self.structured_originals(base)
            sources = self.url(patient)
            paths = (
                (sources, "oi.synthetic-original-sources/1"),
                (sources.removesuffix("/sources") + "/world-model",
                 "oi.pg-source-world-model/1"),
            )
            for path, contract in paths:
                with self.subTest(path=path):
                    result = self.withheld_then_retry(
                        base, patient, path, "source.read_authorized",
                        "source_read",
                    )
                    self.assertEqual(result["contract"], contract)
                    self.assertEqual(result["patient_id"], patient)
                    self.assertEqual(result["case_id"], "CASE-ALPHA")

    def test_current_and_historical_structured_originals_after_real_audit(self):
        with running_server(create_app(self.settings)) as base:
            patient, versions = self.structured_originals(base)
            for source_id, original, state in versions:
                with self.subTest(state=state):
                    result = self.withheld_then_retry(
                        base, patient, self.url(patient) + "/" + source_id,
                        "source.original_read_authorized",
                        "source_original_read",
                    )
                    self.assertEqual(result["source_id"], source_id)
                    self.assertEqual(result["state"], state)
                    self.assertEqual(result["original_text"], original)
                    self.assertEqual(
                        result["sha256"],
                        hashlib.sha256(original.encode()).hexdigest(),
                    )

    def test_document_index_and_both_detail_grants_after_real_audit(self):
        with running_server(create_app(self.settings)) as base:
            patient, prefix, versions = self.document_originals(base)
            with self.subTest(read="index", action="source_read"):
                result = self.withheld_then_retry(
                    base, patient, prefix, "source.document_read_authorized",
                    "source_read",
                )
                self.assertEqual(
                    {item["source_id"] for item in result["documents"]},
                    {item[0] for item in versions},
                )
            for source_id, raw, state, revision_count in versions:
                for action in ("source_read", "source_original_read"):
                    with self.subTest(read="detail", state=state, action=action):
                        result = self.withheld_then_retry(
                            base, patient, prefix + "/" + source_id,
                            "source.document_read_authorized", action,
                        )
                        self.assertEqual(result["source_id"], source_id)
                        self.assertEqual(result["state"], state)
                        self.assertEqual(result["preview"]["text"], raw.decode())
                        self.assertEqual(
                            [item["revision"] for item in result["revisions"]],
                            list(range(1, revision_count + 1)),
                        )
                        for revision in result["revisions"]:
                            self.assertEqual(
                                revision["classification_origin"], "user_selected"
                            )
                            self.assertEqual(
                                revision["clinical_review"], "not_performed"
                            )

    def test_current_and_historical_document_downloads_after_real_audit(self):
        with running_server(create_app(self.settings)) as base:
            patient, prefix, versions = self.document_originals(base)
            for source_id, raw, state, _ in versions:
                with self.subTest(state=state):
                    self.withheld_then_retry(
                        base, patient,
                        prefix + "/" + source_id + "/original",
                        "source.original_read_authorized",
                        "source_original_read", expected_bytes=raw,
                    )
