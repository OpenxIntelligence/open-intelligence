"""Keep encounters with their patient and note histories with their encounter."""
from alembic import op
from alembic.util.exc import CommandError

revision = "0022_ehr_patient_ownership"
down_revision = "0021_lab_citation_freshness"
branch_labels = None
depends_on = None


def upgrade():
    conn = op.get_bind()
    conn.exec_driver_sql("""
        LOCK TABLE ehr.clinical_encounters, ehr.clinical_note_headers
        IN SHARE ROW EXCLUSIVE MODE
    """)
    # Check provenance before making the current ownership permanent. Historical
    # mismatches require explicit reconciliation with the source owner.
    mismatch = conn.exec_driver_sql("""
        SELECT EXISTS (
            SELECT 1 FROM ehr.clinical_encounters c
            WHERE NOT EXISTS (
                SELECT 1 FROM identity.identity_domain_events e
                WHERE e.patient_id = c.patient_id AND e.event_type = 'clinical_encounter_scheduled'
                  AND e.metadata_json->>'encounter_id' = c.id::text
            )
        ) OR EXISTS (
            SELECT 1 FROM ehr.clinical_note_versions v
            JOIN ehr.clinical_note_headers h ON h.id = v.note_id
            JOIN ehr.clinical_encounters c ON c.id = h.encounter_id
            WHERE NOT EXISTS (
                SELECT 1 FROM identity.identity_domain_events e
                WHERE e.patient_id = c.patient_id
                  AND e.event_type = CASE WHEN v.status IN ('attested','attested_correction')
                                          THEN 'clinical_note_attestation_recorded'
                                          ELSE 'clinical_note_draft_saved' END
                  AND e.metadata_json->>'note_id' = h.id::text
                  AND e.metadata_json->>'version' = v.version::text
                  AND e.metadata_json->>'encounter_id' = c.id::text
            )
        ) OR EXISTS (
            -- A move followed by a move back can leave the header correctly
            -- placed while an intervening patient's transition or draft survives.
            SELECT 1 FROM identity.identity_domain_events e
            LEFT JOIN ehr.clinical_encounters c ON c.id::text = e.metadata_json->>'encounter_id'
            LEFT JOIN ehr.clinical_note_headers h ON h.id::text = e.metadata_json->>'note_id'
            WHERE e.event_type IN ('clinical_encounter_scheduled','clinical_encounter_state_changed',
                                   'clinical_note_draft_saved','clinical_note_attestation_recorded')
              AND (c.patient_id IS DISTINCT FROM e.patient_id OR
                   (e.event_type IN ('clinical_note_draft_saved','clinical_note_attestation_recorded')
                    AND h.encounter_id IS DISTINCT FROM c.id))
        )
    """).scalar_one()
    if mismatch:
        raise CommandError("Existing encounter or note ownership requires explicit reconciliation")
    conn.exec_driver_sql("""
        CREATE TRIGGER encounter_patient_immutable
        BEFORE UPDATE OF patient_id ON ehr.clinical_encounters FOR EACH ROW
        WHEN (OLD.patient_id IS DISTINCT FROM NEW.patient_id)
        EXECUTE FUNCTION identity.reject_registry_history_mutation();
        CREATE TRIGGER note_encounter_immutable
        BEFORE UPDATE OF encounter_id ON ehr.clinical_note_headers FOR EACH ROW
        WHEN (OLD.encounter_id IS DISTINCT FROM NEW.encounter_id)
        EXECUTE FUNCTION identity.reject_registry_history_mutation();
    """)


def downgrade():
    conn = op.get_bind()
    conn.exec_driver_sql("""
        DROP TRIGGER note_encounter_immutable ON ehr.clinical_note_headers;
        DROP TRIGGER encounter_patient_immutable ON ehr.clinical_encounters;
    """)
