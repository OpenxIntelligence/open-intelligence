"""Patient authorization declarations, not identity proofing or verified consent.

Stored grants intersect the trusted credential ceiling. Administration cannot be
delegated through this service. The registry remains the patient and event owner.
"""
from datetime import datetime, timezone
import hashlib
import json
from typing import Literal
import uuid
from pydantic import Field, StrictBool, field_validator
from open_intelligence.patient_registry import PatientRegistryConflict, PatientRegistryDenied, _key
from .access import Action
from .contracts import Contract

ADMIN_ACTIONS = frozenset({"patient_permissions_read", "patient_permissions_manage"})
RESERVED_ACTIONS = ADMIN_ACTIONS | {"patient_create", "data_use_read", "data_use_manage", "consent_read", "consent_manage"}


class PermissionCommand(Contract):
    synthetic: StrictBool
    request_key: str
    authority_ref: str

    @field_validator("synthetic")
    @classmethod
    def fictional(cls, value):
        if not value:
            raise ValueError("Fictional declaration required")
        return value

    @field_validator("request_key", "authority_ref")
    @classmethod
    def opaque(cls, value):
        return _key(value, "reference")


class GrantPermission(PermissionCommand):
    actor: str
    purpose: Literal["operations", "research"]
    actions: frozenset[Action] = Field(min_length=1, max_length=64)
    relationship: Literal["patient", "guardian", "animal_owner", "care_team", "research_delegate"]
    expires_at: datetime

    @field_validator("actor")
    @classmethod
    def actor_key(cls, value):
        return _key(value, "actor")

    @field_validator("actions")
    @classmethod
    def no_administration(cls, value):
        if value & RESERVED_ACTIONS:
            raise ValueError("Administrative authority cannot be delegated here")
        return value

    @field_validator("expires_at")
    @classmethod
    def timezone_required(cls, value):
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("Explicit timezone required")
        return value.astimezone(timezone.utc)


class RevokePermission(PermissionCommand):
    expected_revision: int = Field(strict=True, ge=1, le=1)


class PostgresPatientPermissions:
    def __init__(self, registry):
        self.registry = registry

    def authorize(self, context, patient, *, write=False, command=None):
        required = ADMIN_ACTIONS if write else {"patient_permissions_read"}
        if context.purpose != "operations" or not required.issubset(context.actions) or patient not in context.patient_ids:
            raise PatientRegistryDenied("Patient permissions unavailable")
        if isinstance(command, GrantPermission) and (not command.actions.issubset(context.actions)
                or command.expires_at > context.expires_at):
            raise PatientRegistryDenied("Delegation exceeds operator scope")
        for action in required:
            self.registry._allow(context.actor, patient, action, context.purpose)

    def list(self, patient, context, *, after, prepare, recheck):
        self.authorize(context, patient)
        with self.registry.transaction():
            rows = self.registry._fetchall("""SELECT g.grant_id,g.actor,g.purpose,g.actions,g.relationship,
                g.authority_ref,g.granted_by,g.created_at,g.expires_at,r.revoked_at,r.revoked_by,r.authority_ref,
                CASE WHEN r.grant_id IS NOT NULL THEN 'revoked'
                  WHEN g.expires_at<=clock_timestamp() THEN 'expired' ELSE 'active' END
                FROM identity.patient_access_grants g LEFT JOIN identity.patient_access_revocations r USING(grant_id)
                WHERE g.patient_id=%s AND g.grant_id>%s ORDER BY g.grant_id LIMIT 26""", (patient, after))
            keys = ("grant_id", "actor", "purpose", "actions", "relationship", "authority_ref", "granted_by",
                    "created_at", "expires_at", "revoked_at", "revoked_by", "revocation_ref", "status")
            records = []
            for row in rows[:25]:
                item = dict(zip(keys, row))
                for key in ("created_at", "expires_at", "revoked_at"):
                    if item[key] is not None:
                        item[key] = item[key].isoformat()
                item["revision"] = 2 if item["status"] == "revoked" else 1
                records.append(item)
            response = prepare({"patient_id": patient, "grants": records,
                "next_after": rows[24][0] if len(rows)>25 else None,
                "available_actions": sorted(context.actions - RESERVED_ACTIONS),
                "operator_expires_at": context.expires_at.isoformat(),
                "enforcement": "persisted_grants" if context.persisted_grants else "synthetic_fixture"})
            recheck()
            return response

    def change(self, patient, context, command, *, grant_id=None, prepare, recheck):
        self.authorize(context, patient, write=True, command=command)
        value = command.model_dump(mode="json")
        if "actions" in value:
            value["actions"] = sorted(value["actions"])
        value.update(issued_by=context.actor, organization=context.organization, patient_id=patient,
                     operation="grant" if grant_id is None else "revoke", grant_id=grant_id)
        digest = hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
        with self.registry.transaction():
            row = self.registry._fetchone("SELECT status FROM identity.identity_patients "
                "WHERE patient_id=%s AND origin_org=%s FOR UPDATE", (patient, context.organization))
            if row is None or (row[0] != "active" and grant_id is None):
                raise PatientRegistryDenied("Patient permissions unavailable")
            recheck()
            if grant_id is None:
                old = self.registry._fetchone("SELECT grant_id,request_digest FROM identity.patient_access_grants "
                    "WHERE patient_id=%s AND request_key=%s", (patient, command.request_key))
                if old:
                    if old[1] != digest:
                        raise PatientRegistryConflict("Request intent conflict")
                    grant_id = old[0]
                else:
                    now = self.registry._fetchone("SELECT clock_timestamp()")[0]
                    if command.expires_at <= now:
                        raise PatientRegistryConflict("Permission expiry has passed")
                    grant_id = "GRANT-" + uuid.uuid4().hex.upper()
                    self.registry._execute("""INSERT INTO identity.patient_access_grants
                        (grant_id,patient_id,actor,purpose,actions,relationship,authority_ref,granted_by,
                         expires_at,request_key,request_digest) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)""",
                        (grant_id, patient, command.actor, command.purpose, sorted(command.actions),
                         command.relationship, command.authority_ref, context.actor, command.expires_at,
                         command.request_key, digest))
                    self.registry.append_event(patient, "identity.access.granted", grant_id=grant_id,
                        actor=context.actor, authority_ref=command.authority_ref)
            else:
                grant = self.registry._fetchone("SELECT grant_id FROM identity.patient_access_grants "
                    "WHERE patient_id=%s AND grant_id=%s", (patient, grant_id))
                if not grant:
                    raise PatientRegistryDenied("Patient permissions unavailable")
                old = self.registry._fetchone("SELECT request_digest FROM identity.patient_access_revocations "
                    "WHERE grant_id=%s", (grant_id,))
                if old:
                    if old[0] != digest:
                        raise PatientRegistryConflict("Request intent conflict")
                else:
                    self.registry._execute("""INSERT INTO identity.patient_access_revocations
                        (grant_id,revoked_by,authority_ref,request_key,request_digest) VALUES (%s,%s,%s,%s,%s)""",
                        (grant_id, context.actor, command.authority_ref, command.request_key, digest))
                    # Suspension must not prevent removal of an existing grant.
                    self.registry._write_event(patient, "identity.access.revoked", dict(grant_id=grant_id,
                        actor=context.actor, authority_ref=command.authority_ref))
            response = prepare({"patient_id": patient, "grant_id": grant_id, "duplicate": bool(old)})
            recheck()
            return response
