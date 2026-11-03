"""PostgreSQL persistence for the ORIGINAL first-party clinical encounter domain.

B-01c experimental port. The clinical state machine, validation, note
fingerprints and command hashing remain in `clinical_encounters.py`. This
adapter provides a strictly bounded SQLite-shaped *domain host*, not a
separate EHR or identity ledger. SQL migrations happen outside handlers.

The caller must supply PostgresPatientRegistry on a non-autocommit pg8000
connection, and an injected host authorizer; neither is a verified IdP or a
consent service. Never expose this adapter on the unauthenticated demo API.
"""
from __future__ import annotations

import re
from contextlib import nullcontext
from datetime import date, datetime
from typing import Any, Callable

from .clinical_encounters import (
    ClinicalEncounters, ClinicalAuthorizationError, ClinicalConflict,
)
from .postgres_registry import PostgresPatientRegistry
from .patient_registry import PatientRegistryDenied, PatientRegistryError


# The only SQL identifiers that this first-party module is permitted to use.
# No caller-controlled SQL or table names can reach this adapter.
_TABLES = (
    "clinical_encounter_commands", "clinical_note_versions",
    "clinical_note_headers", "clinical_encounters",
)
_INSERT_IDS = ("clinical_encounters", "clinical_note_headers")


class _Result:
    """Materialized cursor so reads never escape the transaction or share cursors."""

    def __init__(self, rows: list[dict], lastrowid: int | None = None):
        self._rows = rows
        self.lastrowid = lastrowid

    def fetchone(self) -> dict | None:
        return self._rows.pop(0) if self._rows else None

    def fetchall(self) -> list[dict]:
        result = self._rows
        self._rows = []
        return result


def _normalized(value: Any) -> Any:
    if isinstance(value, (date, datetime)):
        return value.isoformat(timespec="seconds") if isinstance(value, datetime) else value.isoformat()
    return value


class _ClinicalSQL:
    """Small, audited translation of *known* ClinicalEncounters SQL statements.

    This is intentionally NOT a general SQL dialect translator. Application
    statements are kept in the original domain; new statement shapes must be
    explicitly reviewed and exercised before they become supported.
    """

    def __init__(self, registry: PostgresPatientRegistry):
        self.registry = registry
        self._ctx: Any = None
        self._patient: str | None = None
        self._reauthorize: Callable[[], None] | None = None

    def command_scope(self, patient_id: str, verify: Callable[[], None]) -> None:
        if self._ctx is not None:
            raise PatientRegistryError("command already active")
        self._patient, self._reauthorize = patient_id, verify

    def clear_scope(self) -> None:
        self._patient, self._reauthorize = None, None

    def __enter__(self):
        self._ctx = self.registry.transaction()
        self._ctx.__enter__()
        return self

    def __exit__(self, *exc_info):
        try:
            return self._ctx.__exit__(*exc_info)
        finally:
            self._ctx = None

    def execute(self, statement: str, params: tuple = ()) -> _Result:
        sql = statement.strip()
        if sql.upper() == "BEGIN IMMEDIATE":
            if not self.registry._transaction_active or not self._patient:
                raise PatientRegistryError("encounter lock requires command transaction")
            # Serializes ALL commands for a patient and interlocks with
            # suspension, preventing lost optimistic revisions and stale access.
            row = self.registry._fetchone(
                "SELECT status FROM identity.identity_patients "
                "WHERE patient_id=%s FOR UPDATE", (self._patient,)
            )
            if row is None or row[0] != "active":
                raise ClinicalAuthorizationError("inactive patient")
            # Re-evaluate after acquiring lock; authorization was first checked
            # before starting the command transaction.
            if self._reauthorize is None:
                raise ClinicalAuthorizationError("missing command authorization")
            self._reauthorize()
            return _Result([])

        operation = sql.split(None, 1)[0].upper() if sql else ""
        if operation not in {"SELECT", "INSERT", "UPDATE"}:
            raise PatientRegistryError("unsupported clinical domain SQL")
        # Exactly one parameter marker per bound parameter, in static source.
        if sql.count("?") != len(params) or "%s" in sql:
            raise PatientRegistryError("unexpected clinical SQL parameters")
        target = None
        for table in _INSERT_IDS:
            if re.match(r"^INSERT\s+INTO\s+" + table + r"\b", sql, re.I):
                target = table
                break
        for table in _TABLES:
            sql = re.sub(r"\b" + table + r"\b", "ehr." + table, sql)
        sql = sql.replace("?", "%s")
        if target:
            sql += " RETURNING id"
        def materialize() -> _Result:
            cur = self.registry.db.cursor()
            try:
                cur.execute(sql, params)
                if cur.description is None:
                    return _Result([])
                cols = [column[0] for column in cur.description]
                items = [{name: _normalized(value) for name, value in zip(cols, row)}
                         for row in cur.fetchall()]
                return _Result(items, items[0]["id"] if target and items else None)
            finally:
                cur.close()
        if self.registry._transaction_active:
            return materialize()
        if operation != "SELECT":
            raise PatientRegistryError("clinical writes require explicit transaction")
        # A read is materialized *inside* its own transaction; callers cannot
        # keep an implicit PostgreSQL transaction open by forgetting to close a cursor.
        with self.registry.transaction():
            return materialize()


class PostgresClinicalHost:
    """One canonical PostgreSQL identity owner + domain events, same transaction."""

    def __init__(self, registry: PostgresPatientRegistry):
        if not isinstance(registry, PostgresPatientRegistry):
            raise TypeError("PostgresClinicalHost requires canonical PostgresPatientRegistry")
        self.registry = registry
        self.db = _ClinicalSQL(registry)

    def require_patient(self, patient_id: str) -> None:
        self.registry.require_patient(patient_id)

    def append_event(self, patient_id: str, kind: str, **details: object) -> None:
        if not self.registry._transaction_active:
            raise PatientRegistryError("clinical event requires command transaction")
        self.registry.append_event(patient_id, kind, **details)


class PostgresClinicalEncounters(ClinicalEncounters):
    """Original ClinicalEncounters behavior on a PostgreSQL persistence host."""

    def __init__(self, registry: PostgresPatientRegistry,
                 authorizer: Callable[[str, str, str, str], bool] | None = None):
        # Do not call base __init__: it installs SQLite DDL using executescript.
        # The PG schema must be migrated/verified before service construction.
        self.host = PostgresClinicalHost(registry)
        self.authorizer = authorizer

    def _command(self, patient_id: str, actor: str, purpose: str, action: str,
                 request_key: str, data: dict, mutate: Callable[[], dict]) -> dict:
        sql_host = self.host.db
        sql_host.command_scope(
            patient_id,
            lambda: self._allow(actor, patient_id, action, purpose),
        )
        try:
            return super()._command(patient_id, actor, purpose, action,
                                    request_key, data, mutate)
        finally:
            sql_host.clear_scope()
