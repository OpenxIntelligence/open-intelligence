"""Durable local synthetic Composer run journal over canonical CaseStore.

This is a task ledger, not a second patient record, medical authorization,
background agent, or scientific interpretation service.
"""
from __future__ import annotations

import hmac
import json
import re

from .composer import composer_context_fingerprint
from .composer_lab import composer_lab_trend
from .store import CaseStore, InvalidInput, now_utc

TOKEN = re.compile(r"[a-f0-9]{64}\Z")
KEY = re.compile(r"[a-z][a-z0-9_-]{0,59}\Z")
IDEMPOTENCY = re.compile(r"[A-Za-z0-9][A-Za-z0-9_-]{7,63}\Z")

SCHEMA = """
CREATE TABLE IF NOT EXISTS composer_tool_runs (
 id INTEGER PRIMARY KEY,
 case_id TEXT NOT NULL REFERENCES cases(case_id),
 question_id INTEGER NOT NULL REFERENCES questions(id),
 kind TEXT NOT NULL CHECK(kind='synthetic-lab-trend'),
 finding_key TEXT NOT NULL,
 context_fingerprint TEXT NOT NULL,
 idempotency_key TEXT NOT NULL,
 state TEXT NOT NULL CHECK(state IN
  ('queued','running','completed','blocked','stale','cancelled','failed')),
 result_json TEXT,
 failure_code TEXT,
 created_at TEXT NOT NULL,
 updated_at TEXT NOT NULL,
 UNIQUE(case_id,idempotency_key)
);
CREATE INDEX IF NOT EXISTS composer_runs_case
 ON composer_tool_runs(case_id,id DESC);
CREATE TABLE IF NOT EXISTS composer_tool_run_events (
 id INTEGER PRIMARY KEY,
 run_id INTEGER NOT NULL REFERENCES composer_tool_runs(id),
 state TEXT NOT NULL,
 occurred_at TEXT NOT NULL,
 reason TEXT NOT NULL
);
"""


class DurableComposerRuns:
    def __init__(self, store: CaseStore):
        self.store = store
        self.db = store.db
        self.db.executescript(SCHEMA)

    def _row(self, case_id: str, run_id: int) -> dict:
        self.store._case(case_id)
        if type(run_id) is not int or run_id < 1:
            raise InvalidInput("Run ID must be positive")
        row = self.db.execute(
            "SELECT * FROM composer_tool_runs WHERE id=? AND case_id=?",
            (run_id,case_id)).fetchone()
        if row is None:
            raise InvalidInput("Run not in this synthetic case")
        return dict(row)

    def _event(self, run_id: int, state: str, reason: str) -> None:
        self.db.execute(
            "INSERT INTO composer_tool_run_events(run_id,state,occurred_at,reason) VALUES(?,?,?,?)",
            (run_id,state,now_utc(),reason))

    def _transition(self, row: dict, state: str, reason: str,
                    result: dict | None = None) -> None:
        self.db.execute(
            "UPDATE composer_tool_runs SET state=?,updated_at=?,result_json=?,failure_code=? WHERE id=?",
            (state, now_utc(),
             json.dumps(result,sort_keys=True,ensure_ascii=False) if result is not None
             else row["result_json"],
             reason if state in ("stale","blocked","cancelled","failed") else None,
             row["id"]))
        self._event(row["id"],state,reason)

    def _current(self, row: dict) -> bool:
        try:
            token = composer_context_fingerprint(
                self.store,row["case_id"],row["question_id"])
        except InvalidInput:
            return False
        return hmac.compare_digest(token,row["context_fingerprint"])

    def _reconcile(self, row: dict) -> dict:
        # Reconcile lazily on read. Original computation remains inspectable.
        if row["state"] in ("queued","completed","blocked") and not self._current(row):
            with self.db:
                self.db.execute("BEGIN IMMEDIATE")
                fresh = self._row(row["case_id"],row["id"])
                if fresh["state"] in ("queued","completed","blocked") and not self._current(fresh):
                    self._transition(fresh,"stale","source_context_changed")
            row = self._row(row["case_id"],row["id"])
        return row

    def get(self, case_id: str, run_id: int) -> dict:
        row = self._reconcile(self._row(case_id,run_id))
        events = [dict(item) for item in self.db.execute(
            "SELECT state,occurred_at,reason FROM composer_tool_run_events WHERE run_id=? ORDER BY id",
            (run_id,)).fetchall()]
        return {
            "run_id":row["id"],"case_id":row["case_id"],
            "question_id":row["question_id"],"tool_id":row["kind"],
            "finding_key":row["finding_key"],
            "context_fingerprint":row["context_fingerprint"],
            "idempotency_key":row["idempotency_key"],"state":row["state"],
            "result":json.loads(row["result_json"]) if row["result_json"] is not None else None,
            "failure_code":row["failure_code"],"created_at":row["created_at"],
            "updated_at":row["updated_at"],"events":events,
            "clinical_review_state":"not_performed",
            "clinical_authorization":"not_verified",
            "disclaimer":"Synthetic local computation record, not a clinical review or care action."
        }

    def list(self, case_id: str) -> list[dict]:
        self.store._case(case_id)
        rows = self.db.execute(
            "SELECT id FROM composer_tool_runs WHERE case_id=? ORDER BY id DESC LIMIT 40",
            (case_id,)).fetchall()
        return [self.get(case_id,int(row["id"])) for row in rows]

    def queue(self, case_id: str, question_id: int, fingerprint: str,
              finding_key: str, idempotency_key: str) -> dict:
        self.store._case(case_id)
        if type(question_id) is not int or question_id < 1:
            raise InvalidInput("question_id must be a positive integer")
        if not isinstance(fingerprint,str) or not TOKEN.fullmatch(fingerprint):
            raise InvalidInput("Current Composer context fingerprint required")
        if not isinstance(finding_key,str) or not KEY.fullmatch(finding_key):
            raise InvalidInput("Invalid synthetic lab finding key")
        if not isinstance(idempotency_key,str) or not IDEMPOTENCY.fullmatch(idempotency_key):
            raise InvalidInput("Idempotency key requires 8-64 safe characters")
        with self.db:
            self.db.execute("BEGIN IMMEDIATE")
            old = self.db.execute(
                "SELECT * FROM composer_tool_runs WHERE case_id=? AND idempotency_key=?",
                (case_id,idempotency_key)).fetchone()
            if old is not None:
                old = dict(old)
                if (old["question_id"],old["finding_key"],old["context_fingerprint"]) != (
                    question_id,finding_key,fingerprint):
                    raise InvalidInput("Idempotency key already used for a different task")
                run_id = old["id"]
            else:
                current = composer_context_fingerprint(self.store,case_id,question_id)
                if not hmac.compare_digest(current,fingerprint):
                    raise InvalidInput("stale Composer context: refresh before queueing")
                stamp = now_utc()
                cursor = self.db.execute(
                    """INSERT INTO composer_tool_runs
                     (case_id,question_id,kind,finding_key,context_fingerprint,
                      idempotency_key,state,created_at,updated_at)
                     VALUES (?,?, 'synthetic-lab-trend',?,?,?,'queued',?,?)""",
                    (case_id,question_id,finding_key,fingerprint,idempotency_key,
                     stamp,stamp))
                run_id = cursor.lastrowid
                self._event(run_id,"queued","operator_requested")
        return self.get(case_id,run_id)

    def execute(self, case_id: str, run_id: int) -> dict:
        with self.db:
            self.db.execute("BEGIN IMMEDIATE")
            row = self._row(case_id,run_id)
            if row["state"] != "queued":
                raise InvalidInput("Only queued work can be executed")
            if not self._current(row):
                self._transition(row,"stale","source_context_changed")
                stale = True
            else:
                self._transition(row,"running","execution_started")
                stale = False
        if stale:
            return self.get(case_id,run_id)
        payload = None
        error_code = None
        try:
            payload = composer_lab_trend(
                self.store,case_id,row["question_id"],
                row["context_fingerprint"],row["finding_key"])
        except InvalidInput as exc:
            error_code = "source_context_changed" if "stale" in str(exc).lower() else "input_invalid"
        except Exception:
            error_code = "internal_execution_error"
        with self.db:
            self.db.execute("BEGIN IMMEDIATE")
            latest = self._row(case_id,run_id)
            if latest["state"] != "running":
                pass  # A concurrent cancellation wins; never overwrite it.
            elif not self._current(latest) or error_code == "source_context_changed":
                self._transition(latest,"stale","source_context_changed")
            elif error_code:
                self._transition(latest,"failed",error_code)
            elif payload["status"] == "computed":
                self._transition(latest,"completed","numeric_calculation_completed",payload)
            else:
                self._transition(latest,"blocked","measurement_not_computable",payload)
        return self.get(case_id,run_id)

    def cancel(self, case_id: str, run_id: int) -> dict:
        with self.db:
            self.db.execute("BEGIN IMMEDIATE")
            row = self._row(case_id,run_id)
            if row["state"] not in ("queued","running"):
                raise InvalidInput("Only queued or running work can be cancelled")
            self._transition(row,"cancelled","operator_cancelled")
        return self.get(case_id,run_id)
