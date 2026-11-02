"""Synthetic record-acquisition work queue over the canonical CaseStore.

Requests are operational tasks, NOT evidence that a test was ordered, clinically
indicated, or performed. Only original source_versions can prove receipt here.
No identity verification, real-patient authorization, messaging or outbound requests.
"""
from __future__ import annotations

import re

from .store import CaseStore, InvalidInput, TYPES, now_utc

_KEY = re.compile(r"[A-Z][A-Z0-9-]{7,63}\Z")


def _positive(value: object, label: str) -> int:
    if type(value) is not int or value <= 0 or value > 9223372036854775807:
        raise InvalidInput(f"{label} must be a positive integer")
    return value


def _text(value: object, label: str, maximum: int) -> str:
    if not isinstance(value, str) or not value.strip() or len(value.strip()) > maximum:
        raise InvalidInput(f"{label} must have 1–{maximum} characters")
    stripped = value.strip()
    if any(ord(ch) < 32 or ord(ch) == 127 for ch in stripped):
        raise InvalidInput(f"{label} contains unsupported control characters")
    return stripped


class RecordAcquisition:
    """Operates on an existing CaseStore transaction and events ledger."""

    def __init__(self, store: CaseStore):
        self.store = store

    def list(self, case_id: str) -> dict:
        self.store._case(case_id)
        rows = self.store.db.execute(
            """SELECT r.*,v.case_id AS source_case,v.document_id,
               v.version AS document_version,v.kind AS source_kind,
               v.sha256 AS source_sha256,v.state AS source_state
               FROM record_requests r LEFT JOIN source_versions v
                 ON r.received_source_id=v.id
               WHERE r.case_id=? ORDER BY r.id""", (case_id,)
        ).fetchall()
        requests = []
        for original in rows:
            row = dict(original)
            if row["status"] == "requested":
                row["receipt_state"] = "awaiting_record"
            elif row["status"] == "cancelled":
                row["receipt_state"] = "request_cancelled"
            elif (row["source_case"] != case_id or row["source_kind"] != row["kind"]
                  or row["source_state"] not in ("current", "superseded")):
                # Corruption is a failed read, not a misleading completed task.
                raise InvalidInput("Source receipt integrity could not be established")
            else:
                row["receipt_state"] = (
                    "source_current" if row["source_state"] == "current"
                    else "source_superseded_reconciliation_needed"
                )
            # Do not leak the redundant join identity or store unrestricted source text.
            row.pop("source_case")
            requests.append(row)
        return {
            "contract": "oi.synthetic-record-acquisition/1",
            "synthetic": True, "case_id": case_id, "requests": requests,
            "limitations": "No external records request was sent. Receipt means a user explicitly linked one fictional stored source; an amendment may require reconciliation.",
        }

    def create(self, case_id: str, request_key: str, kind: str, label: str,
               organization: str) -> dict:
        self.store._case(case_id)
        if not isinstance(request_key, str) or not _KEY.fullmatch(request_key):
            raise InvalidInput("Request key must be an uppercase stable idempotency token")
        if kind not in TYPES:
            raise InvalidInput("Unsupported source category")
        label = _text(label, "Requested record", 140)
        organization = _text(organization, "Requested from", 100)
        with self.store.db:
            self.store.db.execute("BEGIN IMMEDIATE")
            prior = self.store.db.execute(
                "SELECT id,kind,label,organization FROM record_requests WHERE case_id=? AND request_key=?",
                (case_id, request_key)
            ).fetchone()
            if prior:
                if (prior["kind"], prior["label"], prior["organization"]) != (kind, label, organization):
                    raise InvalidInput("Request key cannot be reused for different records")
                return {"request_id": prior["id"], "duplicate": True}
            cursor = self.store.db.execute(
                """INSERT INTO record_requests
                  (case_id,request_key,kind,label,organization,status,created_at,updated_at)
                  VALUES (?,?,?,?,?,'requested',?,?)""",
                (case_id, request_key, kind, label, organization, now_utc(), now_utc())
            )
            self.store._event(case_id, "record_acquisition_requested", request_id=cursor.lastrowid)
            return {"request_id": int(cursor.lastrowid), "duplicate": False}

    def receive(self, case_id: str, request_id: int, source_version_id: int) -> dict:
        self.store._case(case_id)
        _positive(request_id, "Request ID")
        _positive(source_version_id, "Source version ID")
        with self.store.db:
            self.store.db.execute("BEGIN IMMEDIATE")
            row = self.store.db.execute(
                "SELECT * FROM record_requests WHERE id=? AND case_id=?", (request_id, case_id)
            ).fetchone()
            if row is None:
                raise InvalidInput("Record request not in this case")
            if row["status"] == "cancelled":
                raise InvalidInput("Cancelled request cannot receive a source")
            source = self.store.db.execute(
                "SELECT id,kind,document_id,version,sha256,state,supersedes_id FROM source_versions WHERE id=? AND case_id=?",
                (source_version_id, case_id)
            ).fetchone()
            if source is None or source["state"] != "current" or source["kind"] != row["kind"]:
                raise InvalidInput("Receipt must cite a current, same-case source of the requested type")
            previous = row["received_source_id"]
            if row["status"] == "received":
                if previous == source_version_id:
                    return {"request_id": request_id, "source_version_id": source_version_id, "duplicate": True}
                old = self.store.db.execute(
                    "SELECT document_id,state FROM source_versions WHERE id=? AND case_id=?",
                    (previous, case_id)
                ).fetchone()
                if old is None or old["document_id"] != source["document_id"] or old["state"] != "superseded":
                    raise InvalidInput("A current receipt cannot be silently replaced by a different record")
            self.store.db.execute(
                "UPDATE record_requests SET status='received',received_source_id=?,updated_at=? WHERE id=? AND case_id=?",
                (source_version_id, now_utc(), request_id, case_id)
            )
            self.store._event(case_id, "record_acquisition_source_linked",
                              request_id=request_id, source_version_id=source_version_id,
                              replaced_source_version_id=previous)
            return {"request_id": request_id, "source_version_id": source_version_id, "duplicate": False}

    def cancel(self, case_id: str, request_id: int, reason: str) -> dict:
        self.store._case(case_id)
        _positive(request_id, "Request ID")
        reason = _text(reason, "Cancellation reason", 200)
        with self.store.db:
            self.store.db.execute("BEGIN IMMEDIATE")
            row = self.store.db.execute(
                "SELECT status FROM record_requests WHERE id=? AND case_id=?", (request_id, case_id)
            ).fetchone()
            if row is None:
                raise InvalidInput("Record request not in this case")
            if row["status"] == "received":
                raise InvalidInput("A received record cannot be cancelled or erased")
            if row["status"] == "cancelled":
                return {"request_id": request_id, "duplicate": True}
            self.store.db.execute(
                "UPDATE record_requests SET status='cancelled',updated_at=? WHERE id=? AND case_id=?",
                (now_utc(), request_id, case_id)
            )
            self.store._event(case_id, "record_acquisition_cancelled",
                              request_id=request_id, reason=reason)
            return {"request_id": request_id, "duplicate": False}
