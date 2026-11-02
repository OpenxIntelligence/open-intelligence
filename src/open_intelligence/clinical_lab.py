"""First-party synthetic clinical-order and laboratory operational contracts.

This is a bounded, original Python/SQLite implementation in the *existing*
CaseStore database. It is not a deployed EHR, LIS, clinical laboratory,
authenticated clinician order system, or diagnostic reporting service.

Clinical commands, provenance and workflow events are fictional engineering
records. Original report bytes and assertions remain in CaseStore.
"""
from __future__ import annotations

import sqlite3
from collections.abc import Callable, Mapping

from .store import CaseStore, InvalidInput, now_utc, valid_id, KEY


SCHEMA = """
CREATE TABLE IF NOT EXISTS clinical_lab_orders (
  id INTEGER PRIMARY KEY,
  case_id TEXT NOT NULL REFERENCES cases(case_id),
  order_key TEXT NOT NULL,
  source_version_id INTEGER NOT NULL REFERENCES source_versions(id),
  test_label TEXT NOT NULL,
  requested_by TEXT NOT NULL,
  state TEXT NOT NULL CHECK(state IN ('requested','cancelled')),
  created_at TEXT NOT NULL,
  cancelled_reason TEXT,
  UNIQUE(case_id,order_key)
);
CREATE TABLE IF NOT EXISTS clinical_lab_accessions (
  id INTEGER PRIMARY KEY,
  case_id TEXT NOT NULL REFERENCES cases(case_id),
  order_id INTEGER NOT NULL REFERENCES clinical_lab_orders(id),
  accession_key TEXT NOT NULL,
  specimen_id TEXT NOT NULL,
  received_by TEXT NOT NULL,
  created_at TEXT NOT NULL,
  UNIQUE(case_id,accession_key),
  UNIQUE(order_id,specimen_id)
);
CREATE TABLE IF NOT EXISTS clinical_lab_qc (
  id INTEGER PRIMARY KEY,
  case_id TEXT NOT NULL REFERENCES cases(case_id),
  accession_id INTEGER NOT NULL REFERENCES clinical_lab_accessions(id),
  qc_key TEXT NOT NULL,
  source_version_id INTEGER NOT NULL REFERENCES source_versions(id),
  outcome TEXT NOT NULL CHECK(outcome IN ('passed','failed','pending')),
  checked_by TEXT NOT NULL,
  created_at TEXT NOT NULL,
  UNIQUE(case_id,qc_key)
);
CREATE TABLE IF NOT EXISTS clinical_lab_releases (
  id INTEGER PRIMARY KEY,
  case_id TEXT NOT NULL REFERENCES cases(case_id),
  accession_id INTEGER NOT NULL REFERENCES clinical_lab_accessions(id),
  release_key TEXT NOT NULL,
  source_version_id INTEGER NOT NULL REFERENCES source_versions(id),
  assertion_id INTEGER NOT NULL REFERENCES assertions(id),
  qc_id INTEGER NOT NULL REFERENCES clinical_lab_qc(id),
  finding_key TEXT NOT NULL,
  reported_state TEXT NOT NULL,
  released_by TEXT NOT NULL,
  created_at TEXT NOT NULL,
  UNIQUE(case_id,release_key)
);
CREATE INDEX IF NOT EXISTS idx_clinical_lab_order_case ON clinical_lab_orders(case_id,id);
CREATE INDEX IF NOT EXISTS idx_clinical_lab_accession_order ON clinical_lab_accessions(order_id,id);
CREATE INDEX IF NOT EXISTS idx_clinical_lab_qc_accession ON clinical_lab_qc(accession_id,id);
CREATE INDEX IF NOT EXISTS idx_clinical_lab_release_accession ON clinical_lab_releases(accession_id,id);
"""


def _label(value: str, name: str, length: int = 180) -> str:
    if not isinstance(value, str) or not 2 <= len(value.strip()) <= length:
        raise InvalidInput(name + " must contain 2–" + str(length) + " characters")
    return value.strip()


def _positive_int(value: int, name: str) -> int:
    if type(value) is not int or value < 1:
        raise InvalidInput(name + " must be a positive source identifier")
    return value


def _result(row: sqlite3.Row, duplicate: bool) -> dict:
    return {"id": int(row["id"]), "duplicate": duplicate}


class ClinicalLabOperations:
    """Synthetic-only first-party order-to-LIS operations in the canonical DB.

    Each command owns one explicit transactional state change, with the existing
    CaseStore event log. Identity, source bytes and review are never duplicated.
    Reviewer labels are NOT verified clinician credentials.
    """

    def __init__(self, store: CaseStore, event_hook: Callable[[str, str, Mapping[str, object]], None] | None = None):
        if not isinstance(store, CaseStore):
            raise TypeError("ClinicalLabOperations requires an existing CaseStore")
        if store.db.in_transaction:
            raise InvalidInput("Initialize clinical laboratory tables outside a transaction")
        self.store = store
        self.db = store.db
        self.event_hook = event_hook
        self.db.executescript(SCHEMA)

    def _emit(self, case_id: str, kind: str, **details: object) -> None:
        """Append local journal and optional transport in the SAME transaction.

        A publisher MUST leave legacy-case events unbound to canonical patients
        until PF-01 identity reconciliation is verified. The hook must not
        commit or publish synchronously over the network.
        """
        if not self.db.in_transaction:
            raise InvalidInput("Laboratory event requires active domain transaction")
        self.store._event(case_id, kind, **details)
        if self.event_hook is not None:
            self.event_hook(case_id, kind, details)

    def _source(self, case_id: str, source_id: int, kind: str) -> sqlite3.Row:
        _positive_int(source_id, "Source")
        row = self.db.execute(
            """SELECT * FROM source_versions
               WHERE case_id=? AND id=? AND state='current'""",
            (case_id, source_id)).fetchone()
        if not row or row["kind"] != kind:
            raise InvalidInput("Current " + kind + " source not found in this case")
        return row

    def _order(self, case_id: str, order_key: str) -> sqlite3.Row:
        row = self.db.execute(
            "SELECT * FROM clinical_lab_orders WHERE case_id=? AND order_key=?",
            (case_id, order_key)).fetchone()
        if row is None:
            raise InvalidInput("Clinical laboratory order is absent from this case")
        return row

    def _accession(self, case_id: str, accession_key: str) -> sqlite3.Row:
        row = self.db.execute(
            """SELECT a.*,o.state AS order_state,
                      o.source_version_id AS order_source_version_id
               FROM clinical_lab_accessions a
               JOIN clinical_lab_orders o ON o.id=a.order_id
               WHERE a.case_id=? AND a.accession_key=? AND o.case_id=?""",
            (case_id, accession_key, case_id)).fetchone()
        if row is None:
            raise InvalidInput("Specimen accession is absent from this case")
        return row

    def _lab_source(self, case_id: str, source_id: int, specimen_id: str) -> sqlite3.Row:
        source = self._source(case_id, source_id, "laboratory")
        if source["specimen_id"] != specimen_id:
            raise InvalidInput("Laboratory source specimen does not match accession")
        return source

    def request_lab_order(self, case_id: str, order_key: str,
                          source_version_id: int, test_label: str,
                          requested_by: str) -> dict:
        self.store._case(case_id)
        valid_id(order_key)
        _positive_int(source_version_id, "Order source")
        test_label = _label(test_label, "Test label")
        requested_by = _label(requested_by, "Synthetic requester", 80)
        with self.db:
            self.db.execute("BEGIN IMMEDIATE")
            existing = self.db.execute(
                "SELECT * FROM clinical_lab_orders WHERE case_id=? AND order_key=?",
                (case_id, order_key)).fetchone()
            if existing is not None:
                if (existing["source_version_id"], existing["test_label"],
                        existing["requested_by"]) != (source_version_id, test_label, requested_by):
                    raise InvalidInput("Conflicting clinical order idempotency key")
                return _result(existing, True)
            self._source(case_id, source_version_id, "clinical")
            authored_order = self.db.execute(
                """SELECT 1 FROM assertions
                   WHERE case_id=? AND source_version_id=? AND finding_key='order'
                     AND certainty='reported'""",
                (case_id, source_version_id)).fetchone()
            if authored_order is None:
                raise InvalidInput("Clinical order requires an authored reported order source")
            cur = self.db.execute(
                """INSERT INTO clinical_lab_orders
                   (case_id,order_key,source_version_id,test_label,requested_by,state,created_at)
                   VALUES (?,?,?,?,?,'requested',?)""",
                (case_id, order_key, source_version_id, test_label,
                 requested_by, now_utc()))
            self._emit(case_id, "clinical_lab_order_requested",
                              order_id=cur.lastrowid, order_key=order_key,
                              source_version_id=source_version_id)
            return {"id": int(cur.lastrowid), "duplicate": False}

    def cancel_order(self, case_id: str, order_key: str, reason: str) -> dict:
        self.store._case(case_id)
        valid_id(order_key)
        reason = _label(reason, "Synthetic cancellation reason", 600)
        with self.db:
            self.db.execute("BEGIN IMMEDIATE")
            order = self._order(case_id, order_key)
            if order["state"] == "cancelled":
                if order["cancelled_reason"] != reason:
                    raise InvalidInput("Conflicting cancellation for this order")
                return {"id": int(order["id"]), "duplicate": True, "state": "cancelled"}
            existing_accession = self.db.execute(
                "SELECT 1 FROM clinical_lab_accessions WHERE order_id=?",
                (order["id"],)).fetchone()
            if existing_accession:
                raise InvalidInput("Cannot cancel an already-accessioned synthetic order")
            self.db.execute(
                """UPDATE clinical_lab_orders SET state='cancelled',cancelled_reason=?
                   WHERE id=?""", (reason, order["id"]))
            self._emit(case_id, "clinical_lab_order_cancelled",
                              order_id=order["id"], order_key=order_key)
            return {"id": int(order["id"]), "duplicate": False, "state": "cancelled"}

    def accession_specimen(self, case_id: str, order_key: str,
                           accession_key: str, specimen_id: str,
                           received_by: str) -> dict:
        self.store._case(case_id)
        valid_id(order_key)
        valid_id(accession_key)
        valid_id(specimen_id)
        received_by = _label(received_by, "Synthetic accessioner", 80)
        with self.db:
            self.db.execute("BEGIN IMMEDIATE")
            order = self._order(case_id, order_key)
            existing = self.db.execute(
                "SELECT * FROM clinical_lab_accessions WHERE case_id=? AND accession_key=?",
                (case_id, accession_key)).fetchone()
            if existing is not None:
                if (existing["order_id"], existing["specimen_id"],
                        existing["received_by"]) != (order["id"], specimen_id, received_by):
                    raise InvalidInput("Conflicting accession idempotency key")
                return _result(existing, True)
            if order["state"] == "cancelled":
                raise InvalidInput("Cannot accession a cancelled order")
            self._source(case_id, order["source_version_id"], "clinical")
            cur = self.db.execute(
                """INSERT INTO clinical_lab_accessions
                   (case_id,order_id,accession_key,specimen_id,received_by,created_at)
                   VALUES (?,?,?,?,?,?)""",
                (case_id, order["id"], accession_key, specimen_id,
                 received_by, now_utc()))
            self._emit(case_id, "clinical_lab_specimen_accessioned",
                              accession_id=cur.lastrowid, order_id=order["id"],
                              accession_key=accession_key, specimen_id=specimen_id)
            return {"id": int(cur.lastrowid), "duplicate": False}

    def record_quality_check(self, case_id: str, accession_key: str,
                             qc_key: str, lab_source_version_id: int,
                             outcome: str, checked_by: str) -> dict:
        self.store._case(case_id)
        valid_id(accession_key)
        valid_id(qc_key)
        _positive_int(lab_source_version_id, "Laboratory source")
        if outcome not in {"passed", "failed", "pending"}:
            raise InvalidInput("QC outcome must be passed, failed or pending")
        checked_by = _label(checked_by, "Synthetic checker", 80)
        with self.db:
            self.db.execute("BEGIN IMMEDIATE")
            accession = self._accession(case_id, accession_key)
            existing = self.db.execute(
                "SELECT * FROM clinical_lab_qc WHERE case_id=? AND qc_key=?",
                (case_id, qc_key)).fetchone()
            if existing is not None:
                if (existing["accession_id"], existing["source_version_id"],
                        existing["outcome"], existing["checked_by"]) != (
                            accession["id"], lab_source_version_id, outcome, checked_by):
                    raise InvalidInput("Conflicting QC idempotency key")
                return _result(existing, True)
            if accession["order_state"] == "cancelled":
                raise InvalidInput("Cancelled order is not eligible for QC")
            self._source(case_id, accession["order_source_version_id"], "clinical")
            self._lab_source(case_id, lab_source_version_id, accession["specimen_id"])
            cur = self.db.execute(
                """INSERT INTO clinical_lab_qc
                   (case_id,accession_id,qc_key,source_version_id,outcome,checked_by,created_at)
                   VALUES (?,?,?,?,?,?,?)""",
                (case_id, accession["id"], qc_key,
                 lab_source_version_id, outcome, checked_by, now_utc()))
            self._emit(case_id, "clinical_lab_qc_recorded",
                              accession_id=accession["id"], qc_id=cur.lastrowid,
                              outcome=outcome, source_version_id=lab_source_version_id)
            return {"id": int(cur.lastrowid), "duplicate": False}

    def release_observation(self, case_id: str, accession_key: str,
                            release_key: str, lab_source_version_id: int,
                            finding_key: str, released_by: str) -> dict:
        self.store._case(case_id)
        valid_id(accession_key)
        valid_id(release_key)
        _positive_int(lab_source_version_id, "Laboratory source")
        if not isinstance(finding_key, str) or not KEY.fullmatch(finding_key):
            raise InvalidInput("Finding key must identify a reported source assertion")
        released_by = _label(released_by, "Synthetic releaser", 80)
        with self.db:
            self.db.execute("BEGIN IMMEDIATE")
            accession = self._accession(case_id, accession_key)
            existing = self.db.execute(
                "SELECT * FROM clinical_lab_releases WHERE case_id=? AND release_key=?",
                (case_id, release_key)).fetchone()
            if existing is not None:
                if (existing["accession_id"], existing["source_version_id"],
                        existing["finding_key"], existing["released_by"]) != (
                            accession["id"], lab_source_version_id,
                            finding_key, released_by):
                    raise InvalidInput("Conflicting release idempotency key")
                return _result(existing, True)
            if accession["order_state"] == "cancelled":
                raise InvalidInput("Cannot release for a cancelled order")
            self._source(case_id, accession["order_source_version_id"], "clinical")
            self._lab_source(case_id, lab_source_version_id, accession["specimen_id"])
            qc = self.db.execute(
                """SELECT * FROM clinical_lab_qc WHERE case_id=? AND accession_id=?
                   ORDER BY id DESC LIMIT 1""",
                (case_id, accession["id"])).fetchone()
            if qc is None or qc["outcome"] != "passed" or qc["source_version_id"] != lab_source_version_id:
                raise InvalidInput("Latest QC must pass for the same current source")
            finding = self.db.execute(
                """SELECT id,certainty FROM assertions
                   WHERE case_id=? AND source_version_id=? AND finding_key=?""",
                (case_id, lab_source_version_id, finding_key)).fetchone()
            if finding is None or finding["certainty"] not in {
                    "reported", "negative", "indeterminate"}:
                raise InvalidInput("Laboratory finding is missing, pending or not releasable")
            cur = self.db.execute(
                """INSERT INTO clinical_lab_releases
                   (case_id,accession_id,release_key,source_version_id,assertion_id,
                    qc_id,finding_key,reported_state,released_by,created_at)
                   VALUES (?,?,?,?,?,?,?,?,?,?)""",
                (case_id, accession["id"], release_key, lab_source_version_id,
                 finding["id"], qc["id"], finding_key, finding["certainty"],
                 released_by, now_utc()))
            self._emit(case_id, "clinical_lab_observation_released",
                              accession_id=accession["id"], release_id=cur.lastrowid,
                              source_version_id=lab_source_version_id,
                              assertion_id=finding["id"], qc_id=qc["id"])
            return {"id": int(cur.lastrowid), "duplicate": False}

    def case_state(self, case_id: str) -> dict:
        """Read-only, transactionally consistent operational projection.

        Freshness is derived from the canonical source state and latest QC;
        historical release records are never silently rewritten by amendments.
        """
        self.store._case(case_id)
        with self.db:
            self.db.execute("BEGIN")
            orders = [dict(r) for r in self.db.execute(
                """SELECT o.*,s.state AS source_state FROM clinical_lab_orders o
                   JOIN source_versions s ON s.id=o.source_version_id
                   WHERE o.case_id=? ORDER BY o.id""", (case_id,)).fetchall()]
            accessions = [dict(r) for r in self.db.execute(
                """SELECT * FROM clinical_lab_accessions WHERE case_id=? ORDER BY id""",
                (case_id,)).fetchall()]
            qc_records = [dict(r) for r in self.db.execute(
                """SELECT * FROM clinical_lab_qc WHERE case_id=? ORDER BY id""",
                (case_id,)).fetchall()]
            releases = [dict(r) for r in self.db.execute(
                """SELECT r.*,s.state AS source_state,
                          o.source_version_id AS order_source_version_id
                   FROM clinical_lab_releases r
                   JOIN source_versions s ON s.id=r.source_version_id
                   JOIN clinical_lab_accessions a ON a.id=r.accession_id
                   JOIN clinical_lab_orders o ON o.id=a.order_id
                   WHERE r.case_id=? ORDER BY r.id""",
                (case_id,)).fetchall()]
            for release in releases:
                order_src = self.db.execute(
                    "SELECT state FROM source_versions WHERE id=?",
                    (release["order_source_version_id"],)).fetchone()
                latest_qc = self.db.execute(
                    """SELECT id,outcome,source_version_id FROM clinical_lab_qc
                       WHERE accession_id=? ORDER BY id DESC LIMIT 1""",
                    (release["accession_id"],)).fetchone()
                if release["source_state"] != "current":
                    release["freshness"] = "stale_source"
                elif not order_src or order_src["state"] != "current":
                    release["freshness"] = "stale_order_source"
                elif (not latest_qc or latest_qc["id"] != release["qc_id"] or
                      latest_qc["outcome"] != "passed" or
                      latest_qc["source_version_id"] != release["source_version_id"]):
                    release["freshness"] = "reassessment_required"
                else:
                    release["freshness"] = "current"
            return {
                "case_id": case_id,
                "mode": "synthetic_operational_contract_only",
                "orders": orders,
                "accessions": accessions,
                "qc_records": qc_records,
                "releases": releases,
                "clinical_authorization": "not_verified",
            }
