"""Build the existing patient registry authorization adapter for a principal."""

from open_intelligence.postgres_registry import PostgresPatientRegistry

from .access import Principal
from .patient_consent import CONSENT_EXEMPT, EVENT


def registry_for_principal(connection, context: Principal) -> PostgresPatientRegistry:
    """Reuse caller-owned connection and principal; caller owns refresh and transaction."""
    def authorize(actor, subject, action, purpose):
        if actor != context.actor or purpose != context.purpose or action not in context.actions:
            return False
        if action == "patient_create":
            return subject == context.organization
        if action not in {"patient_permissions_read", "patient_permissions_manage", "data_use_read", "data_use_manage", "consent_read", "consent_manage", "patient_suspend", "patient_read", "record_request_create", "record_request_read", "record_request_cancel", "record_request_receive", "case_binding_create", "case_binding_read", "case_binding_revoke", "source_import", "source_read", "source_original_read", "composer_context_read", "question_create", "question_read", "image_import", "image_read", "image_original_read", "review_queue_read", "review_return", "source_brief_export", "review_packet_read", "followthrough_read", "followthrough_create", "followthrough_update", "evidence_read", "evidence_link", "authored_evidence_read", "authored_evidence_import", "authored_evidence_assess", "authored_evidence_withdraw", "authored_evidence_original_read", "evidence_report_export", "encounter.schedule", "encounter.read", "encounter.events.read", "encounter.transition", "encounter.source.link", "note.write", "note.read"} or subject not in context.patient_ids:
            return False
        cursor = connection.cursor()
        try:
            cursor.execute("SELECT origin_org FROM identity.identity_patients WHERE patient_id=%s", (subject,))
            row = cursor.fetchone()
            if row is None or row[0] != context.organization:
                return False
            if action not in {"patient_read", "patient_suspend", "patient_permissions_read", "patient_permissions_manage", "data_use_read", "data_use_manage", "consent_read", "consent_manage"}:
                cursor.execute("SELECT metadata_json->>'state' FROM identity.identity_domain_events "
                    "WHERE patient_id=%s AND event_type='identity.data_use.decided' "
                    "AND metadata_json->>'target_purpose'=%s ORDER BY id DESC LIMIT 1", (subject, purpose))
                decision = cursor.fetchone()
                if decision is not None and decision[0] != "unrestricted":
                    return False
            if action not in CONSENT_EXEMPT:
                cursor.execute("""SELECT metadata_json->>'state',
                    (metadata_json->>'valid_from')::timestamptz <= clock_timestamp()
                    AND (metadata_json->>'expires_at')::timestamptz > clock_timestamp(),
                    metadata_json->>(%s) FROM identity.identity_domain_events
                    WHERE patient_id=%s AND event_type=%s AND metadata_json->>'actor'=%s
                    AND metadata_json->>'target_purpose'=%s ORDER BY id DESC LIMIT 1""",
                    ('action.'+action, subject, EVENT, actor, purpose))
                consent = cursor.fetchone()
                if consent is None:
                    if context.consent_decisions:
                        return False
                elif consent[0] != 'granted' or consent[1] is not True or consent[2] != 'true':
                    return False
            if not context.persisted_grants or action in {"patient_permissions_read", "patient_permissions_manage", "data_use_read", "data_use_manage", "consent_read", "consent_manage"}:
                return True
            # Read current persisted scope on every owner permission check.
            # Credential scope remains an independent upper bound.
            cursor.execute("""SELECT EXISTS(SELECT 1 FROM identity.patient_access_grants g
                WHERE g.patient_id=%s AND g.actor=%s AND g.purpose=%s
                AND %s=ANY(g.actions) AND g.expires_at>clock_timestamp()
                AND NOT EXISTS(SELECT 1 FROM identity.patient_access_revocations r WHERE r.grant_id=g.grant_id))""",
                (subject, actor, purpose, action))
            return cursor.fetchone()[0] is True
        finally:
            cursor.close()

    return PostgresPatientRegistry(connection, authorize)
