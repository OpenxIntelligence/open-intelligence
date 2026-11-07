"""Authorization-port contract tests; database execution is verified separately."""
from datetime import datetime, timedelta, timezone
from typing import get_args
import unittest

from oi_api.access import Principal
from oi_api.registry_context import registry_for_principal
from open_intelligence.patient_registry import PatientRegistryDenied


class Connection:
    autocommit = False
    def __init__(self, decisions=None, organization='ORG-FICTIONAL'):
        self.decisions = decisions or {}
        self.organization = organization
        self.result = None
        self.calls = []
    def cursor(self):
        return self
    def execute(self, statement, parameters):
        self.calls.append((statement, parameters))
        if 'origin_org' in statement:
            self.result = (self.organization,)
        else:
            self.result = self.decisions.get(parameters)
    def fetchone(self):
        return self.result
    def close(self):
        pass


class DataUseAuthorityTests(unittest.TestCase):
    def context(self, purpose='operations', actions=None):
        all_actions = get_args(get_args(Principal.model_fields['actions'].annotation)[0])
        return Principal(actor='ACTOR-FICTIONAL', organization='ORG-FICTIONAL', purpose=purpose,
                         actions=all_actions if actions is None else actions,
                         patient_ids={'PAT-FICTIONAL'},
                         expires_at=datetime.now(timezone.utc) + timedelta(hours=1))

    def test_restriction_denies_every_existing_data_action(self):
        context = self.context()
        db = Connection({('PAT-FICTIONAL', 'operations'): ('restricted',)})
        registry = registry_for_principal(db, context)
        metadata = {'patient_read', 'patient_suspend', 'data_use_read', 'data_use_manage'}
        for action in context.actions - {'patient_create'}:
            with self.subTest(action=action):
                if action in metadata:
                    registry._allow(context.actor, 'PAT-FICTIONAL', action, context.purpose)
                else:
                    with self.assertRaises(PatientRegistryDenied):
                        registry._allow(context.actor, 'PAT-FICTIONAL', action, context.purpose)

    def test_decision_is_fresh_purpose_scoped_and_cannot_supply_missing_grant(self):
        db = Connection({('PAT-FICTIONAL', 'research'): ('restricted',)})
        context = self.context()
        registry = registry_for_principal(db, context)
        registry._allow(context.actor, 'PAT-FICTIONAL', 'source_read', 'operations')
        db.decisions[('PAT-FICTIONAL', 'operations')] = ('restricted',)
        with self.assertRaises(PatientRegistryDenied):
            registry._allow(context.actor, 'PAT-FICTIONAL', 'source_read', 'operations')
        db.decisions[('PAT-FICTIONAL', 'operations')] = ('unrestricted',)
        registry._allow(context.actor, 'PAT-FICTIONAL', 'source_read', 'operations')
        limited = self.context(actions={'patient_read'})
        with self.assertRaises(PatientRegistryDenied):
            registry_for_principal(db, limited)._allow(limited.actor, 'PAT-FICTIONAL', 'source_read', 'operations')
        research = self.context('research')
        with self.assertRaises(PatientRegistryDenied):
            registry_for_principal(db, research)._allow(research.actor, 'PAT-FICTIONAL', 'source_read', 'research')

    def test_malformed_recorded_decision_and_wrong_organization_fail_closed(self):
        context = self.context()
        for value in (None, '', 'consented', 'RESTRICTED'):
            with self.subTest(value=value), self.assertRaises(PatientRegistryDenied):
                registry_for_principal(Connection({('PAT-FICTIONAL', 'operations'): (value,)}), context)._allow(
                    context.actor, 'PAT-FICTIONAL', 'source_read', 'operations')
        with self.assertRaises(PatientRegistryDenied):
            registry_for_principal(Connection(organization='ORG-OTHER'), context)._allow(
                context.actor, 'PAT-FICTIONAL', 'data_use_manage', 'operations')
