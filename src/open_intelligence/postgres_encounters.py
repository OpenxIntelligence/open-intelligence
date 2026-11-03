"""PostgreSQL persistence for the existing first-party encounter state machine.

This adapter inherits the original domain workflows; it does not create another
patient owner, issue a medical signature, open an API, or run schema migrations.
Only reviewed internal SQL from ClinicalEncounters crosses the storage hooks.
The existing B-01 research driver is injected by the host, not imported here.
"""
from __future__ import annotations

from contextlib import contextmanager
from datetime import date, datetime
import re

from .clinical_encounters import ClinicalEncounters
from .patient_registry import PatientRegistryDenied, PatientRegistryError
from .postgres_registry import PostgresPatientRegistry

_TABLES = re.compile(
    r"\b(clinical_encounters|clinical_note_headers|clinical_note_versions|clinical_encounter_commands)\b"
)


def _postgres_sql(statement: str) -> str:
    """Bind markers and explicit schema for our small, literal-free SQL subset.

    Never accepts client SQL, interpolates values, changes driver-global
    paramstyle, or relies on search_path (including pg_temp). Refuse new SQL
    forms requiring a separate review instead of attempting general parsing.
    """
    if (not isinstance(statement, str) or not _TABLES.search(statement)
            or any(token in statement for token in ("'", '"', ";", "--", "/*", "%"))
            or not statement.lstrip().upper().startswith(("SELECT ", "INSERT ", "UPDATE "))):
        raise PatientRegistryError("Unsupported internal EHR SQL statement")
    return _TABLES.sub(lambda match: "ehr." + match.group(1), statement).replace("?", "%s")


def _value(value):
    # Preserve the public JSON-compatible SQLite API shape, not driver objects.
    if isinstance(value, datetime):
        return value.isoformat(timespec="seconds")
    if isinstance(value, date):
        return value.isoformat()
    return value


class _Rows:
    """Small buffered result; DB-API cursors are closed before any caller return."""
    def __init__(self, rows):
        self.rows = rows

    def fetchone(self):
        return self.rows[0] if self.rows else None

    def fetchall(self):
        return list(self.rows)


class PostgresClinicalEncounters(ClinicalEncounters):
    """One existing workflow, alternative persistence via a canonical PG registry.

    One connection is owned by one registry/service instance, not shared across
    concurrent requests. Commands lock their canonical patient row; unrelated
    patient commands remain independent. This is deliberately conservative and
    must be load-tested before changing its locking granularity.

    Tests use disposable privileged DB accounts. This adapter's injected policy
    does not establish clinical identity/consent or qualify production DB roles.
    """
    def __init__(self, host: PostgresPatientRegistry, authorizer=None):
        if not isinstance(host, PostgresPatientRegistry):
            raise PatientRegistryError("PostgreSQL encounters require canonical registry host")
        if getattr(host.db, "autocommit", None) is not False:
            raise PatientRegistryError("PostgreSQL encounters require non-autocommit connection")
        self.host = host
        self.authorizer = authorizer
        # Migrations are installed only by the deployment/test owner, never here.

    def _execute(self, statement: str, parameters: tuple = ()):
        sql = _postgres_sql(statement)
        cursor = self.host.db.cursor()
        try:
            cursor.execute(sql, parameters)
            if cursor.description is None:
                return _Rows([])
            names = [field[0] for field in cursor.description]
            return _Rows([dict(zip(names, map(_value, row))) for row in cursor.fetchall()])
        finally:
            cursor.close()

    def _insert_id(self, statement: str, parameters: tuple) -> int:
        row = self._execute(statement + " RETURNING id", parameters).fetchone()
        if row is None:
            raise PatientRegistryError("EHR insert did not return its identifier")
        return row["id"]

    @contextmanager
    def _command_transaction(self, patient_id: str, actor: str,
                             action: str, purpose: str):
        with self.host.transaction():
            self.host._execute("SET LOCAL TIME ZONE 'UTC'")
            self.host._execute("SELECT set_config('oi.request_purpose', %s, true)", (purpose,))
            row = self.host._fetchone(
                "SELECT status FROM identity.identity_patients WHERE patient_id=%s FOR UPDATE",
                (patient_id,),
            )
            if row is None or row[0] != "active":
                raise PatientRegistryDenied("unknown or inactive patient")
            self._allow(actor, patient_id, action, purpose)
            yield
            # Receipt, domain row and journal must all roll back on revocation.
            self._allow(actor, patient_id, action, purpose)

    @contextmanager
    def _read_transaction(self, patient_id: str, actor: str,
                          action: str, purpose: str):
        with self.host.transaction():
            self.host._execute("SET LOCAL TIME ZONE 'UTC'")
            self.host._execute("SELECT set_config('oi.request_purpose', %s, true)", (purpose,))
            yield
            # Narrow the revocation window; this is not a distributed policy lock.
            self._allow(actor, patient_id, action, purpose)

    def list_encounters(self, patient_id: str, *, actor: str, purpose: str) -> list[dict]:
        with self._read_transaction(patient_id, actor, "encounter.read", purpose):
            return super().list_encounters(patient_id, actor=actor, purpose=purpose)

    def note_history(self, patient_id: str, encounter_id: int, note_key: str, *,
                     actor: str, purpose: str) -> list[dict]:
        with self._read_transaction(patient_id, actor, "note.read", purpose):
            return super().note_history(patient_id, encounter_id, note_key,
                                        actor=actor, purpose=purpose)
