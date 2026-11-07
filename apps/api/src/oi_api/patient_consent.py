"""Versioned fictional consent decisions in the existing immutable identity journal.

These declarations are not identity proofing or legal-authority verification.
Current consent only restricts independently granted access; it cannot create it.
"""
from datetime import datetime, timezone
import hashlib
import json
from typing import Literal

from pydantic import Field, field_validator, model_validator
from open_intelligence.patient_registry import PatientRegistryConflict, PatientRegistryDenied, _key
from .access import Action
from .patient_permissions import PermissionCommand, RESERVED_ACTIONS

CONSENT_ADMIN = frozenset({'consent_read', 'consent_manage'})
CONSENT_EXEMPT = RESERVED_ACTIONS | CONSENT_ADMIN | {'patient_suspend'}
EVENT = 'identity.consent.decided'


class ConsentDecision(PermissionCommand):
    expected_revision: int = Field(strict=True, ge=0, le=9_007_199_254_740_990)
    actor: str
    target_purpose: Literal['operations', 'research']
    state: Literal['granted', 'withdrawn']
    actions: frozenset[Action] = Field(max_length=64)
    decision_maker: str
    basis: Literal['self', 'guardian', 'animal_owner', 'authorized_representative']
    valid_from: datetime | None
    expires_at: datetime | None

    @field_validator('actor', 'decision_maker')
    @classmethod
    def opaque_identity(cls, value):
        return _key(value, 'identity')

    @field_validator('valid_from', 'expires_at')
    @classmethod
    def explicit_instant(cls, value):
        if value is not None:
            if value.tzinfo is None or value.utcoffset() is None:
                raise ValueError('Explicit timezone required')
            return value.astimezone(timezone.utc)
        return value

    @model_validator(mode='after')
    def exact_decision(self):
        if self.actions & CONSENT_EXEMPT:
            raise ValueError('Administrative authority is not a consented use')
        if self.state == 'granted':
            if not self.actions or self.valid_from is None or self.expires_at is None or self.valid_from >= self.expires_at:
                raise ValueError('A grant needs explicit uses and an ordered validity interval')
        elif self.actions or self.valid_from is not None or self.expires_at is not None:
            raise ValueError('A withdrawal must not contain allowed uses or a validity interval')
        return self


class PostgresPatientConsent:
    def __init__(self, registry):
        self.registry = registry

    def authorize(self, context, patient, *, command=None):
        required = CONSENT_ADMIN if command is not None else {'consent_read'}
        if context.purpose != 'operations' or not required.issubset(context.actions) or patient not in context.patient_ids:
            raise PatientRegistryDenied('Consent decisions unavailable')
        if command is not None and command.state == 'granted' and (
                not command.actions.issubset(context.actions) or command.expires_at > context.expires_at):
            raise PatientRegistryDenied('Consent declaration exceeds operator scope')
        for action in required:
            self.registry._allow(context.actor, patient, action, context.purpose)

    def list(self, patient, context, *, before, prepare, recheck):
        self.authorize(context, patient)
        with self.registry.transaction():
            rows = self.registry._fetchall("""SELECT e.id,e.metadata_json,e.occurred_at,clock_timestamp(),
                NOT EXISTS(SELECT 1 FROM identity.identity_domain_events n
                    WHERE n.patient_id=e.patient_id AND n.event_type=e.event_type AND n.id>e.id
                    AND n.metadata_json->>'actor'=e.metadata_json->>'actor'
                    AND n.metadata_json->>'target_purpose'=e.metadata_json->>'target_purpose')
                FROM identity.identity_domain_events e WHERE e.patient_id=%s AND e.event_type=%s
                AND (%s=0 OR e.id<%s) ORDER BY e.id DESC LIMIT 26""", (patient, EVENT, before, before))
            records = []
            for event_id, value, recorded_at, now, current in rows[:25]:
                data = json.loads(value) if isinstance(value, str) else value
                # Re-validate stored decision semantics before disclosing a projection.
                command = ConsentDecision(synthetic=True, request_key=data['request_key'],
                    expected_revision=data['revision']-1,
                    **{k: data[k] for k in ('actor','target_purpose','state','decision_maker','basis','authority_ref','valid_from','expires_at')},
                    actions=[k[7:] for k, v in data.items() if k.startswith('action.') and v is True])
                status = 'superseded' if not current else ('withdrawn' if command.state == 'withdrawn' else
                    'scheduled' if command.valid_from > now else 'expired' if command.expires_at <= now else 'active')
                item = command.model_dump(mode='json', exclude={'synthetic','expected_revision','request_key'})
                item['actions'] = sorted(item['actions'])
                item.update(event_id=event_id, revision=data['revision'], status=status,
                            recorded_at=recorded_at.isoformat(), recorded_by=data['recorded_by'])
                records.append(item)
            result = prepare(dict(patient_id=patient, decisions=records,
                next_before=rows[24][0] if len(rows)>25 else None,
                available_actions=sorted(context.actions-CONSENT_EXEMPT),
                operator_expires_at=context.expires_at.isoformat(),
                enforcement='required' if context.consent_decisions else 'recorded_decisions_only',
                authority_verified=False, data_scope='patient_record'))
            recheck()
            return result

    def change(self, patient, context, command, *, prepare, recheck):
        self.authorize(context, patient, command=command)
        value = command.model_dump(mode='json')
        value['actions'] = sorted(value['actions'])
        value.update(recorded_by=context.actor, organization=context.organization, patient_id=patient)
        digest = hashlib.sha256(json.dumps(value,sort_keys=True,separators=(',', ':')).encode()).hexdigest()
        with self.registry.transaction():
            patient_row = self.registry._fetchone('SELECT status FROM identity.identity_patients '
                'WHERE patient_id=%s AND origin_org=%s FOR UPDATE', (patient,context.organization))
            if patient_row is None:
                raise PatientRegistryDenied('Consent decisions unavailable')
            recheck()
            old = self.registry._fetchone("SELECT id,metadata_json->>'request_digest',metadata_json->>'revision' "
                "FROM identity.identity_domain_events WHERE patient_id=%s AND event_type=%s "
                "AND metadata_json->>'request_key'=%s ORDER BY id DESC LIMIT 1", (patient,EVENT,command.request_key))
            if old:
                if old[1] != digest:
                    raise PatientRegistryConflict('Consent request intent changed')
                event_id, revision = old[0], int(old[2])
            else:
                if patient_row[0] != 'active' and command.state == 'granted':
                    raise PatientRegistryDenied('Inactive patient')
                latest = self.registry._fetchone("SELECT metadata_json->>'revision' FROM identity.identity_domain_events "
                    "WHERE patient_id=%s AND event_type=%s AND metadata_json->>'actor'=%s "
                    "AND metadata_json->>'target_purpose'=%s ORDER BY id DESC LIMIT 1",
                    (patient,EVENT,command.actor,command.target_purpose))
                if (int(latest[0]) if latest else 0) != command.expected_revision:
                    raise PatientRegistryConflict('Consent revision changed')
                now = self.registry._fetchone('SELECT clock_timestamp()')[0]
                if command.state == 'granted' and command.expires_at <= now:
                    raise PatientRegistryConflict('Consent validity has ended')
                revision = command.expected_revision + 1
                metadata = {k:v for k,v in value.items() if k not in ('synthetic','expected_revision','actions','patient_id','organization')}
                metadata.update(revision=revision, request_digest=digest)
                metadata.update({'action.'+action:True for action in command.actions})
                self.registry._write_event(patient, EVENT, metadata)
                event_id = self.registry._fetchone("SELECT id FROM identity.identity_domain_events WHERE "
                    "patient_id=%s AND event_type=%s AND metadata_json->>'request_key'=%s",
                    (patient,EVENT,command.request_key))[0]
            result = prepare(dict(patient_id=patient, event_id=event_id, revision=revision,
                actor=command.actor,target_purpose=command.target_purpose,state=command.state,
                request_key=command.request_key,duplicate=bool(old)))
            recheck()
            return result
