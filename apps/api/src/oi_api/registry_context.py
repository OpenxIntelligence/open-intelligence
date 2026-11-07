"""Build the existing patient registry authorization adapter for a principal."""

from open_intelligence.postgres_registry import PostgresPatientRegistry

from .access import Principal


def registry_for_principal(connection, context: Principal) -> PostgresPatientRegistry:
    """Reuse caller-owned connection and principal; caller owns refresh and transaction."""
    def authorize(actor, subject, action, purpose):
        if actor != context.actor or purpose != context.purpose or action not in context.actions:
            return False
        if action == "patient_create":
            return subject == context.organization
        if action not in {"patient_read", "record_request_create", "record_request_read", "record_request_cancel", "record_request_receive", "case_binding_create", "case_binding_read", "case_binding_revoke", "source_import", "source_read", "source_original_read", "composer_context_read", "question_create", "question_read", "image_import", "image_read", "image_original_read", "review_queue_read", "review_return", "source_brief_export", "review_packet_read", "followthrough_read", "followthrough_create", "followthrough_update", "evidence_read", "evidence_link", "authored_evidence_read", "authored_evidence_import", "authored_evidence_assess", "authored_evidence_withdraw", "authored_evidence_original_read", "evidence_report_export", "encounter.schedule", "encounter.read", "encounter.events.read", "encounter.transition", "note.write", "note.read", "episode_draft_read", "episode_draft_create"} or subject not in context.patient_ids:
            return False
        cursor = connection.cursor()
        try:
            cursor.execute("SELECT origin_org FROM identity.identity_patients WHERE patient_id=%s", (subject,))
            row = cursor.fetchone()
            return row is not None and row[0] == context.organization
        finally:
            cursor.close()

    return PostgresPatientRegistry(connection, authorize)
