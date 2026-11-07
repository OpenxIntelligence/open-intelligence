"""Validate research source custody without creating operations delivery work.

Replace only the installed capture/guard functions. Published 0020, its existing
triggers, and all custody/delivery history remain unchanged. Pre-0020 research
history still requires a separately reviewed upgrade path through its backfill.
"""
from alembic import op

revision = "0027_source_event_purpose"
down_revision = "0026_integrated_core"
branch_labels = None
depends_on = None


def upgrade():
    op.get_bind().exec_driver_sql("""
    CREATE OR REPLACE FUNCTION coordination.source_event_binding(event_key bigint)
      RETURNS TABLE(patient_id text,case_id text,origin_org text,purpose text,
                    source_id text,source_version integer,occurred_at timestamptz)
      LANGUAGE plpgsql AS $oi$
    DECLARE journal identity.identity_domain_events%ROWTYPE; bound record;
    BEGIN
        SELECT * INTO journal FROM identity.identity_domain_events WHERE id=event_key;
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
            AND s.version::text=journal.metadata_json->>'version'
            AND b.purpose IN('operations','research');
        IF NOT FOUND THEN
            RAISE EXCEPTION 'OI-SOURCE-EVENT-LINEAGE';
        END IF;
        RETURN QUERY SELECT bound.patient_id,bound.case_id,bound.origin_org,bound.purpose,
                            bound.source_id,bound.version,journal.occurred_at;
    END; $oi$;

    CREATE OR REPLACE FUNCTION coordination.guard_source_event_outbox() RETURNS trigger LANGUAGE plpgsql AS $oi$
    DECLARE bound record;
    BEGIN
        SELECT * INTO bound FROM coordination.source_event_binding(NEW.event_id);
        IF ROW(NEW.patient_id,NEW.case_id,NEW.origin_org,NEW.purpose,NEW.source_id,NEW.source_version,NEW.occurred_at)
           IS DISTINCT FROM ROW(bound.patient_id,bound.case_id,bound.origin_org,bound.purpose,bound.source_id,bound.source_version,bound.occurred_at) THEN
            RAISE EXCEPTION 'OI-SOURCE-EVENT-LINEAGE';
        END IF;
        NEW.recorded_at:=clock_timestamp();
        RETURN NEW;
    END; $oi$;

    CREATE OR REPLACE FUNCTION coordination.capture_source_event() RETURNS trigger LANGUAGE plpgsql AS $oi$
    BEGIN
        INSERT INTO coordination.source_event_outbox
            (event_id,patient_id,case_id,origin_org,purpose,source_id,source_version,occurred_at)
        SELECT NEW.id,b.patient_id,b.case_id,b.origin_org,b.purpose,
               b.source_id,b.source_version,b.occurred_at
          FROM coordination.source_event_binding(NEW.id) b WHERE b.purpose='operations';
        -- Research custody remains supported by its canonical owner. Validated
        -- research events do not create an operations-only Composer obligation.
        RETURN NULL;
    END; $oi$;
    """)


def downgrade():
    # Restore the two published implementations before removing their helper.
    # Existing research events are retained; the older live capture can refuse
    # subsequent research imports until the explicit upgrade is applied again.
    op.get_bind().exec_driver_sql("""
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
            AND s.version::text=journal.metadata_json->>'version' AND b.purpose='operations';
        IF NOT FOUND OR ROW(NEW.patient_id,NEW.case_id,NEW.origin_org,NEW.purpose,NEW.source_id,NEW.source_version,NEW.occurred_at)
           IS DISTINCT FROM ROW(bound.patient_id,bound.case_id,bound.origin_org,bound.purpose,bound.source_id,bound.version,journal.occurred_at) THEN
            RAISE EXCEPTION 'OI-SOURCE-EVENT-LINEAGE';
        END IF;
        NEW.recorded_at:=clock_timestamp();
        RETURN NEW;
    END; $oi$;

    CREATE OR REPLACE FUNCTION coordination.capture_source_event() RETURNS trigger LANGUAGE plpgsql AS $oi$
    BEGIN
        INSERT INTO coordination.source_event_outbox
            (event_id,patient_id,case_id,origin_org,purpose,source_id,source_version,occurred_at)
        SELECT NEW.id,NEW.patient_id,NEW.metadata_json->>'case_id',b.origin_org,b.purpose,
               NEW.metadata_json->>'source_id',s.version,NEW.occurred_at
          FROM coordination.patient_case_bindings b
          JOIN clinical_source.source_versions s ON s.case_id=b.case_id
          WHERE b.case_id=NEW.metadata_json->>'case_id' AND s.source_id=NEW.metadata_json->>'source_id';
        IF NOT FOUND THEN RAISE EXCEPTION 'OI-SOURCE-EVENT-LINEAGE'; END IF;
        RETURN NULL;
    END; $oi$;

    DROP FUNCTION coordination.source_event_binding(bigint);
    """)
