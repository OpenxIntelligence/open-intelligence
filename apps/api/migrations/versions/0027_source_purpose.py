"""Preserve research source imports while keeping delivery operations-only.

The 0020 bootstrap also accepts research envelopes so pre-outbox histories can
reach this revision. Existing deployments receive the identical guard here.
"""
from alembic import op

revision = "0027_source_purpose"
down_revision = "0026_integrated_core"
branch_labels = None
depends_on = None


def upgrade():
    conn = op.get_bind()
    conn.exec_driver_sql("LOCK TABLE coordination.patient_case_bindings IN EXCLUSIVE MODE")
    conn.exec_driver_sql("""
    ALTER TABLE coordination.source_event_outbox DROP CONSTRAINT source_event_outbox_purpose_check;
    ALTER TABLE coordination.source_event_outbox ADD CONSTRAINT source_event_outbox_purpose_check
        CHECK(purpose IN ('operations','research'));
    CREATE OR REPLACE FUNCTION coordination.guard_source_event_outbox() RETURNS trigger LANGUAGE plpgsql AS $oi$
    DECLARE journal identity.identity_domain_events%ROWTYPE; bound record;
    BEGIN
        SELECT * INTO journal FROM identity.identity_domain_events WHERE id=NEW.event_id;
        IF NOT FOUND OR journal.event_type<>'source.original.imported'
           OR jsonb_typeof(journal.metadata_json->'case_id') IS DISTINCT FROM 'string'
           OR jsonb_typeof(journal.metadata_json->'source_id') IS DISTINCT FROM 'string'
           OR jsonb_typeof(journal.metadata_json->'version') IS DISTINCT FROM 'number'
           OR (journal.metadata_json->>'version') !~ '^[1-9][0-9]*$'
           OR jsonb_typeof(journal.metadata_json->'actor') IS DISTINCT FROM 'string'
           OR char_length(journal.metadata_json->>'actor') NOT BETWEEN 3 AND 128 THEN
            RAISE EXCEPTION 'OI-SOURCE-EVENT-METADATA';
        END IF;
        SELECT s.source_id,s.version,b.case_id,b.patient_id,b.origin_org,b.purpose
          INTO bound FROM clinical_source.source_versions s
          JOIN coordination.patient_case_bindings b ON b.case_id=s.case_id
          JOIN identity.identity_patients p ON p.patient_id=b.patient_id AND p.origin_org=b.origin_org
          WHERE s.source_id=journal.metadata_json->>'source_id'
            AND b.case_id=journal.metadata_json->>'case_id' AND b.patient_id=journal.patient_id
            AND s.version::text=journal.metadata_json->>'version' AND b.purpose IN ('operations','research');
        IF NOT FOUND OR ROW(NEW.patient_id,NEW.case_id,NEW.origin_org,NEW.purpose,NEW.source_id,NEW.source_version,NEW.occurred_at)
           IS DISTINCT FROM ROW(bound.patient_id,bound.case_id,bound.origin_org,bound.purpose,bound.source_id,bound.version,journal.occurred_at) THEN
            RAISE EXCEPTION 'OI-SOURCE-EVENT-LINEAGE';
        END IF;
        NEW.recorded_at:=clock_timestamp();
        RETURN NEW;
    END; $oi$;
    """)


def downgrade():
    # Preserve this compatibility repair on downgrade to the corrected bootstrap.
    # Removing it would make previously accepted research imports fail again.
    pass
