"""First-party clinical encounter and authored-note domain (PD-01).

Operational state is persisted through an injected domain host that owns a
database connection, canonical patient-existence contract and event append.
The legacy CaseStore adapter is used only by the existing local prototype.
The domain itself does not create a patient registry, assume a synthetic-only
patient table, or create a parallel clinical source-import ledger.

The domain API is deliberately NOT exposed through the unauthenticated local
HTTP demonstration. Every operation requires a trusted host-supplied policy
function, which defaults to deny. Identity proofing, legally valid signatures,
PHI protection, production policy enforcement and clinical deployment must be
implemented and validated at the host boundary before real patient use.

Tests exercise real SQLite state transitions on synthetic data; domain semantics
are not mock functions or pre-rendered example responses.
"""

from __future__ import annotations

import hashlib
import json
import re
import sqlite3
from collections.abc import Callable
from datetime import datetime
from typing import Any, Protocol

from .store import CaseStore, InvalidInput, now_utc, valid_date, valid_id

ActorAuthorizer = Callable[[str, str, str, str], bool]

KEY_RE = re.compile(r"[A-Za-z0-9_.:-]{8,100}\Z")
PATIENT_RE = re.compile(r"[A-Za-z0-9][A-Za-z0-9_.:-]{1,127}\Z")
ACTOR_RE = re.compile(r"[A-Za-z0-9_.:-]{3,100}\Z")
PURPOSES = frozenset({"care", "operations", "research"})
KINDS = frozenset({"outpatient", "inpatient", "telehealth", "telephone", "procedure", "other"})
STATES = frozenset({"scheduled", "in_progress", "completed", "cancelled"})
TRANSITIONS = {
    "scheduled": frozenset({"in_progress", "cancelled"}),
    "in_progress": frozenset({"completed", "cancelled"}),
    "completed": frozenset(),
    "cancelled": frozenset(),
}

SCHEMA = """
CREATE TABLE IF NOT EXISTS clinical_encounters (
 id INTEGER PRIMARY KEY,
 patient_id TEXT NOT NULL,
 external_key TEXT NOT NULL,
 kind TEXT NOT NULL CHECK (kind IN ('outpatient','inpatient','telehealth','telephone','procedure','other')),
 service_date TEXT NOT NULL,
 status TEXT NOT NULL CHECK (status IN ('scheduled','in_progress','completed','cancelled')),
 revision INTEGER NOT NULL CHECK (revision >= 1),
 created_at TEXT NOT NULL,
 updated_at TEXT NOT NULL,
 UNIQUE(patient_id, external_key)
);
CREATE INDEX IF NOT EXISTS idx_clinical_encounter_case ON clinical_encounters(patient_id, service_date);
CREATE TABLE IF NOT EXISTS clinical_note_headers (
 id INTEGER PRIMARY KEY,
 encounter_id INTEGER NOT NULL REFERENCES clinical_encounters(id),
 note_key TEXT NOT NULL,
 latest_version INTEGER NOT NULL CHECK (latest_version >= 1),
 UNIQUE(encounter_id,note_key)
);
CREATE TABLE IF NOT EXISTS clinical_note_versions (
 id INTEGER PRIMARY KEY,
 note_id INTEGER NOT NULL REFERENCES clinical_note_headers(id),
 version INTEGER NOT NULL CHECK (version >= 1),
 status TEXT NOT NULL CHECK (status IN ('draft','attested','draft_correction','attested_correction')),
 body TEXT NOT NULL,
 sha256 TEXT NOT NULL,
 authored_by TEXT NOT NULL,
 created_at TEXT NOT NULL,
 supersedes_id INTEGER REFERENCES clinical_note_versions(id),
 amendment_reason TEXT,
 UNIQUE(note_id,version)
);
CREATE INDEX IF NOT EXISTS idx_clinical_note_version ON clinical_note_versions(note_id,version);
-- Published note versions are immutable at the database boundary. Corrections
-- append a new version; the application is never allowed to rewrite history.
CREATE TRIGGER IF NOT EXISTS clinical_note_versions_block_update
BEFORE UPDATE ON clinical_note_versions BEGIN
 SELECT RAISE(ABORT, 'Clinical note versions are immutable');
END;
CREATE TRIGGER IF NOT EXISTS clinical_note_versions_block_delete
BEFORE DELETE ON clinical_note_versions BEGIN
 SELECT RAISE(ABORT, 'Clinical note versions are immutable');
END;
CREATE TABLE IF NOT EXISTS clinical_encounter_commands (
 patient_id TEXT NOT NULL,
 request_key TEXT NOT NULL,
 operation TEXT NOT NULL,
 request_hash TEXT NOT NULL,
 result_json TEXT NOT NULL,
 occurred_at TEXT NOT NULL,
 PRIMARY KEY(patient_id,request_key)
);
CREATE TRIGGER IF NOT EXISTS clinical_encounter_commands_block_update
BEFORE UPDATE ON clinical_encounter_commands BEGIN
 SELECT RAISE(ABORT, 'Clinical commands are immutable');
END;
CREATE TRIGGER IF NOT EXISTS clinical_encounter_commands_block_delete
BEFORE DELETE ON clinical_encounter_commands BEGIN
 SELECT RAISE(ABORT, 'Clinical commands are immutable');
END;
"""


class ClinicalAuthorizationError(PermissionError):
    """Trusted host authorization was absent or denied."""


class ClinicalConflict(InvalidInput):
    """Version conflict, idempotency reuse, or forbidden state transition."""


def _safe_text(value: object, field: str, limit: int) -> str:
    if not isinstance(value, str) or not value.strip() or len(value) > limit or "\x00" in value:
        raise InvalidInput(f"{field} must be nonempty text of at most {limit} characters")
    return value.strip()


def _opaque(value: object, field: str, pattern: re.Pattern[str] = KEY_RE) -> str:
    if not isinstance(value, str) or not pattern.fullmatch(value):
        raise InvalidInput(f"{field} must be an opaque identifier")
    return value


def _timestamp_date(value: object) -> str:
    if not isinstance(value, str):
        raise InvalidInput("service_date must be YYYY-MM-DD")
    return valid_date(value)


def _fingerprint(op: str, actor_id: str, purpose: str, data: dict[str, Any]) -> str:
    canonical = json.dumps({"operation": op, "actor": actor_id, "purpose": purpose,
                            "data": data}, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


class ClinicalDomainHost(Protocol):
    """Port to the ONE patient registry and shared domain-event ledger.

    Implementations must resolve patient existence at their identity boundary,
    and append events using the SAME database transaction as this domain's
    operational writes. It is NOT sufficient to publish to a network here.
    """

    db: sqlite3.Connection

    def require_patient(self, patient_id: str) -> None: ...

    def append_event(self, patient_id: str, kind: str, **details: object) -> None: ...


class LegacyCaseHost:
    """Adapter for existing demo CaseStore; no new patient/source registry."""

    def __init__(self, store: CaseStore):
        self.store = store
        self.db = store.db

    def require_patient(self, patient_id: str) -> None:
        self.store._case(patient_id)

    def append_event(self, patient_id: str, kind: str, **details: object) -> None:
        self.store._event(patient_id, kind, **details)


class ClinicalEncounters:
    """First-party domain commands, using one existing case, source and event ledger.

    ``authorizer`` MUST come from a trusted host policy-enforcement point, not
    from client input. Both reads and writes are checked. This is a domain
    service, not a production authentication mechanism or a deployed EHR.
    """

    def __init__(self, host: ClinicalDomainHost | CaseStore,
                 authorizer: ActorAuthorizer | None = None):
        self.host = LegacyCaseHost(host) if isinstance(host, CaseStore) else host
        self.authorizer = authorizer
        # Schema and transaction ownership remain with the domain host. A
        # production host must use a migration system, not call this at runtime.
        self.host.db.executescript(SCHEMA)

    def _allow(self, actor: str, patient_id: str, action: str, purpose: str) -> None:
        _opaque(patient_id, "patient_id", PATIENT_RE)
        _opaque(actor, "actor", ACTOR_RE)
        if purpose not in PURPOSES:
            raise ClinicalAuthorizationError("Purpose not authorized")
        # fail closed both if there is no policy and if the policy throws
        try:
            allowed = bool(self.authorizer and self.authorizer(actor, patient_id, action, purpose))
        except Exception:
            allowed = False
        if not allowed:
            raise ClinicalAuthorizationError("Clinical domain access denied")
        self.host.require_patient(patient_id)

    def _encounter(self, patient_id: str, encounter_id: int):
        if type(encounter_id) is not int or encounter_id < 1:
            raise InvalidInput("Encounter id required")
        row = self.host.db.execute("SELECT * FROM clinical_encounters WHERE patient_id=? AND id=?",
                                    (patient_id, encounter_id)).fetchone()
        if row is None:
            raise InvalidInput("Encounter not found in this patient")
        return row

    def _note(self, encounter_id: int, note_key: str):
        row = self.host.db.execute("""SELECT n.*,v.id AS version_id,v.status,v.body,v.sha256,
                              v.amendment_reason FROM clinical_note_headers n
                              JOIN clinical_note_versions v ON v.note_id=n.id AND v.version=n.latest_version
                              WHERE n.encounter_id=? AND n.note_key=?""",
                                    (encounter_id, note_key)).fetchone()
        return row

    def _command(self, patient_id: str, actor: str, purpose: str, action: str,
                 request_key: str, data: dict[str, Any], mutate: Callable[[], dict]) -> dict:
        self._allow(actor, patient_id, action, purpose)
        request_key = _opaque(request_key, "request_key")
        digest = _fingerprint(action, actor, purpose, data)
        with self.host.db:
            self.host.db.execute("BEGIN IMMEDIATE")
            previous = self.host.db.execute(
                "SELECT operation,request_hash,result_json FROM clinical_encounter_commands "
                "WHERE patient_id=? AND request_key=?", (patient_id, request_key)).fetchone()
            if previous:
                if previous["operation"] != action or previous["request_hash"] != digest:
                    raise ClinicalConflict("Idempotency key reused for a different command")
                return json.loads(previous["result_json"])
            result = mutate()
            # The host policy may be revoked while a command is assembling its
            # event and domain writes. Re-check before committing the shared
            # transaction so those writes and receipts roll back together.
            # This does not replace production authorization or make a grant
            # change outside this database atomically observable.
            self._allow(actor, patient_id, action, purpose)
            self.host.db.execute("""INSERT INTO clinical_encounter_commands
               (patient_id,request_key,operation,request_hash,result_json,occurred_at)
               VALUES(?,?,?,?,?,?)""", (patient_id, request_key, action, digest,
                                            json.dumps(result, sort_keys=True), now_utc()))
            return result

    def schedule(self, patient_id: str, external_key: str, kind: str,
                 service_date: str, *, actor: str, purpose: str,
                 request_key: str) -> dict:
        external_key = valid_id(external_key)
        if kind not in KINDS:
            raise InvalidInput("Unknown encounter kind")
        service_date = _timestamp_date(service_date)
        def mutate():
            now = now_utc()
            if self.host.db.execute("SELECT 1 FROM clinical_encounters WHERE patient_id=? AND external_key=?",
                                     (patient_id, external_key)).fetchone():
                raise ClinicalConflict("Encounter key already exists")
            cursor = self.host.db.execute("""INSERT INTO clinical_encounters
              (patient_id,external_key,kind,service_date,status,revision,created_at,updated_at)
              VALUES(?,?,?,?,?,?,?,?)""", (patient_id, external_key, kind, service_date,
                                               "scheduled", 1, now, now))
            self.host.append_event(patient_id, "clinical_encounter_scheduled",
                              encounter_id=cursor.lastrowid, revision=1, actor=actor, purpose=purpose, request_key=request_key)
            return {"encounter_id": cursor.lastrowid, "status": "scheduled", "revision": 1}
        return self._command(patient_id, actor, purpose, "encounter.schedule", request_key,
                             {"external_key": external_key, "kind": kind,
                              "service_date": service_date}, mutate)

    def transition(self, patient_id: str, encounter_id: int, target: str, *,
                   expected_revision: int, actor: str, purpose: str,
                   request_key: str) -> dict:
        if target not in STATES:
            raise InvalidInput("Unknown encounter state")
        if type(expected_revision) is not int or expected_revision < 1:
            raise InvalidInput("expected_revision must be a positive integer")
        def mutate():
            row = self._encounter(patient_id, encounter_id)
            if row["revision"] != expected_revision:
                raise ClinicalConflict("Encounter revision changed; reload before writing")
            if target not in TRANSITIONS[row["status"]]:
                raise ClinicalConflict("Illegal encounter state transition")
            new_rev = row["revision"] + 1
            self.host.db.execute("UPDATE clinical_encounters SET status=?,revision=?,updated_at=? WHERE id=?",
                                  (target, new_rev, now_utc(), encounter_id))
            self.host.append_event(patient_id, "clinical_encounter_state_changed",
                              encounter_id=encounter_id, from_status=row["status"],
                              to_status=target, revision=new_rev, actor=actor, purpose=purpose, request_key=request_key)
            return {"encounter_id": encounter_id, "status": target, "revision": new_rev}
        return self._command(patient_id, actor, purpose, "encounter.transition", request_key,
                             {"encounter_id": encounter_id, "target": target,
                              "expected_revision": expected_revision}, mutate)

    def write_note(self, patient_id: str, encounter_id: int, note_key: str, body: str,
                   *, expected_version: int, correction_reason: str | None = None,
                   actor: str, purpose: str, request_key: str) -> dict:
        note_key = valid_id(note_key)
        body = _safe_text(body, "Note body", 20000)
        if type(expected_version) is not int or expected_version < 0:
            raise InvalidInput("Expected note version must be nonnegative")
        if correction_reason is not None:
            correction_reason = _safe_text(correction_reason, "Correction reason", 500)
        def mutate():
            encounter = self._encounter(patient_id, encounter_id)
            if encounter["status"] in {"cancelled", "scheduled"}:
                raise ClinicalConflict("Notes require an in-progress or completed encounter")
            prior = self._note(encounter_id, note_key)
            if prior is None:
                if expected_version != 0 or correction_reason is not None:
                    raise ClinicalConflict("New notes require expected_version=0 and no correction")
                cursor = self.host.db.execute(
                    "INSERT INTO clinical_note_headers(encounter_id,note_key,latest_version) VALUES(?,?,1)",
                    (encounter_id, note_key))
                note_id, prior_version_id, version, state = cursor.lastrowid, None, 1, "draft"
            else:
                if prior["latest_version"] != expected_version:
                    raise ClinicalConflict("Note version changed; reload before writing")
                was_attested = prior["status"] in {"attested", "attested_correction"}
                if was_attested and correction_reason is None:
                    raise ClinicalConflict("Attested notes require a correction reason; history is immutable")
                if not was_attested and correction_reason is not None:
                    raise ClinicalConflict("Cannot label an unattested draft an amendment")
                note_id = prior["id"]
                prior_version_id = prior["version_id"]
                version = expected_version + 1
                state = "draft_correction" if was_attested else prior["status"]
                self.host.db.execute("UPDATE clinical_note_headers SET latest_version=? WHERE id=?",
                                      (version, note_id))
            digest = hashlib.sha256(body.encode("utf-8")).hexdigest()
            self.host.db.execute("""INSERT INTO clinical_note_versions
              (note_id,version,status,body,sha256,authored_by,created_at,supersedes_id,amendment_reason)
              VALUES(?,?,?,?,?,?,?,?,?)""", (note_id, version, state, body, digest,
                                               actor, now_utc(), prior_version_id,
                                               correction_reason if correction_reason else (
                                                   prior["amendment_reason"] if prior is not None else None)))
            self.host.append_event(patient_id, "clinical_note_draft_saved", encounter_id=encounter_id,
                              note_id=note_id, version=version, actor=actor, purpose=purpose,
                              request_key=request_key, correction_pending=(state == "draft_correction"))
            return {"note_id": note_id, "note_key": note_key, "version": version,
                    "status": state, "sha256": digest}
        return self._command(patient_id, actor, purpose, "note.write", request_key,
                             {"encounter_id": encounter_id, "note_key": note_key,
                              "body_sha256": hashlib.sha256(body.encode("utf-8")).hexdigest(),
                              "expected_version": expected_version,
                              "correction_reason": correction_reason}, mutate)

    def attest_note(self, patient_id: str, encounter_id: int, note_key: str, *,
                    expected_version: int, actor: str, purpose: str,
                    request_key: str) -> dict:
        note_key = valid_id(note_key)
        if type(expected_version) is not int or expected_version < 1:
            raise InvalidInput("Expected note version must be positive")
        def mutate():
            encounter = self._encounter(patient_id, encounter_id)
            if encounter["status"] in {"cancelled", "scheduled"}:
                raise ClinicalConflict("Cannot attest a note for this encounter state")
            prior = self._note(encounter_id, note_key)
            if not prior or prior["latest_version"] != expected_version:
                raise ClinicalConflict("Note not found or version changed")
            if prior["status"] not in {"draft", "draft_correction"}:
                raise ClinicalConflict("Only draft note versions can be attested")
            version = expected_version + 1
            state = "attested_correction" if prior["status"] == "draft_correction" else "attested"
            self.host.db.execute("UPDATE clinical_note_headers SET latest_version=? WHERE id=?",
                                  (version, prior["id"]))
            self.host.db.execute("""INSERT INTO clinical_note_versions
              (note_id,version,status,body,sha256,authored_by,created_at,supersedes_id,amendment_reason)
              VALUES(?,?,?,?,?,?,?,?,?)""", (prior["id"], version, state, prior["body"],
                                               prior["sha256"], actor, now_utc(),
                                               prior["version_id"], prior["amendment_reason"]))
            self.host.append_event(patient_id, "clinical_note_attestation_recorded",
                              encounter_id=encounter_id, note_id=prior["id"], version=version,
                              actor=actor, purpose=purpose, request_key=request_key, corrected=(state == "attested_correction"))
            return {"note_id": prior["id"], "note_key": note_key, "version": version,
                    "status": state, "sha256": prior["sha256"]}
        return self._command(patient_id, actor, purpose, "note.attest", request_key,
                             {"encounter_id": encounter_id, "note_key": note_key,
                              "expected_version": expected_version}, mutate)

    def list_encounters(self, patient_id: str, *, actor: str, purpose: str) -> list[dict]:
        self._allow(actor, patient_id, "encounter.read", purpose)
        return [dict(row) for row in self.host.db.execute(
            "SELECT * FROM clinical_encounters WHERE patient_id=? ORDER BY service_date,id",
            (patient_id,)).fetchall()]

    def note_history(self, patient_id: str, encounter_id: int, note_key: str, *,
                     actor: str, purpose: str) -> list[dict]:
        self._allow(actor, patient_id, "note.read", purpose)
        self._encounter(patient_id, encounter_id)
        note_key = valid_id(note_key)
        return [dict(row) for row in self.host.db.execute("""
          SELECT v.id,v.version,v.status,v.body,v.sha256,v.authored_by,v.created_at,
                 v.supersedes_id,v.amendment_reason
          FROM clinical_note_headers n JOIN clinical_note_versions v ON v.note_id=n.id
          WHERE n.encounter_id=? AND n.note_key=? ORDER BY v.version
          """, (encounter_id, note_key)).fetchall()]
