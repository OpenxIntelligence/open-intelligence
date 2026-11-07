"""Transactional source journal outbox and fenced, owner-consumed delivery."""
from alembic import op
from alembic.util.exc import CommandError

revision = '0020_source_event_delivery'
down_revision = '0019_composer_runs'
branch_labels = None
depends_on = None


def upgrade():
    conn = op.get_bind()
    conn.exec_driver_sql("""
    CREATE TABLE coordination.source_event_outbox (
        event_id bigint PRIMARY KEY REFERENCES identity.identity_domain_events(id),
        patient_id text NOT NULL REFERENCES identity.identity_patients(patient_id),
        case_id text NOT NULL REFERENCES coordination.patient_case_bindings(case_id),
        origin_org text NOT NULL,
        purpose text NOT NULL CHECK(purpose IN ('operations','research')),
        source_id text NOT NULL REFERENCES clinical_source.source_versions(source_id),
        source_version integer NOT NULL CHECK(source_version>=1),
        contract text NOT NULL DEFAULT 'oi.h1-source-context-event/1'
            CHECK(contract='oi.h1-source-context-event/1'),
        event_type text NOT NULL DEFAULT 'source.original.imported'
            CHECK(event_type='source.original.imported'),
        occurred_at timestamptz NOT NULL,
        recorded_at timestamptz NOT NULL DEFAULT clock_timestamp()
    );
    CREATE INDEX idx_source_event_outbox_scope ON coordination.source_event_outbox
        (patient_id,case_id,origin_org,event_id);

    CREATE FUNCTION coordination.guard_source_event_outbox() RETURNS trigger LANGUAGE plpgsql AS $oi$
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
    CREATE TRIGGER oi_source_event_outbox_guard BEFORE INSERT ON coordination.source_event_outbox
        FOR EACH ROW EXECUTE FUNCTION coordination.guard_source_event_outbox();

    CREATE FUNCTION coordination.capture_source_event() RETURNS trigger LANGUAGE plpgsql AS $oi$
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
    CREATE TRIGGER oi_capture_source_event AFTER INSERT ON identity.identity_domain_events
        FOR EACH ROW WHEN(NEW.event_type='source.original.imported')
        EXECUTE FUNCTION coordination.capture_source_event();

    -- Backfill every selected row, without silently dropping malformed lineage.
    -- NULL left-join values fail the same insert validator/constraints as live capture.
    INSERT INTO coordination.source_event_outbox
        (event_id,patient_id,case_id,origin_org,purpose,source_id,source_version,occurred_at)
    SELECT e.id,e.patient_id,e.metadata_json->>'case_id',b.origin_org,b.purpose,
           e.metadata_json->>'source_id',s.version,e.occurred_at
      FROM identity.identity_domain_events e
      LEFT JOIN coordination.patient_case_bindings b ON b.case_id=e.metadata_json->>'case_id'
      LEFT JOIN clinical_source.source_versions s ON s.source_id=e.metadata_json->>'source_id'
      WHERE e.event_type='source.original.imported' ORDER BY e.id;

    CREATE TABLE coordination.source_event_deliveries (
        delivery_id text PRIMARY KEY CHECK(delivery_id ~ '^DELIVERY-[0-9A-F]{32}$'),
        event_id bigint NOT NULL REFERENCES coordination.source_event_outbox(event_id),
        consumer text NOT NULL CHECK(consumer='composer-source-context/1'),
        patient_id text NOT NULL,case_id text NOT NULL,origin_org text NOT NULL,
        actor text NOT NULL CHECK(char_length(actor) BETWEEN 3 AND 128),
        purpose text NOT NULL CHECK(purpose='operations'),
        state text NOT NULL DEFAULT 'queued' CHECK(state IN('queued','running','delivered','dead_letter')),
        revision integer NOT NULL DEFAULT 1 CHECK(revision>=1),
        attempt_count integer NOT NULL DEFAULT 0 CHECK(attempt_count>=0),
        failure_count integer NOT NULL DEFAULT 0 CHECK(failure_count BETWEEN 0 AND 3),
        lease_token text CHECK(lease_token ~ '^LEASE-[0-9A-F]{32}$'),lease_expires_at timestamptz,
        available_at timestamptz NOT NULL DEFAULT clock_timestamp(),
        created_at timestamptz NOT NULL DEFAULT clock_timestamp(),
        updated_at timestamptz NOT NULL DEFAULT clock_timestamp(),
        UNIQUE(event_id,consumer,origin_org,actor,purpose),
        CHECK((state='running' AND lease_token IS NOT NULL AND lease_expires_at IS NOT NULL AND attempt_count>=1)
           OR (state<>'running' AND lease_token IS NULL AND lease_expires_at IS NULL)),
        CHECK(state='dead_letter' OR failure_count<3)
    );
    CREATE INDEX idx_source_event_delivery_claim ON coordination.source_event_deliveries
        (patient_id,case_id,origin_org,actor,purpose,state,available_at,lease_expires_at,event_id);
    CREATE TABLE coordination.source_event_delivery_events (
        delivery_id text NOT NULL REFERENCES coordination.source_event_deliveries(delivery_id),
        revision integer NOT NULL CHECK(revision>=1),state text NOT NULL,
        attempt_count integer NOT NULL CHECK(attempt_count>=0),
        failure_count integer NOT NULL CHECK(failure_count BETWEEN 0 AND 3),
        reason_code text NOT NULL CHECK(reason_code IN('queued','claimed','lease_expired','continued',
            'delivered','retryable_failure','authority_unavailable','invalid_event')),
        created_at timestamptz NOT NULL DEFAULT clock_timestamp(),PRIMARY KEY(delivery_id,revision)
    );
    CREATE TABLE investigation.composer_source_event_receipts (
        delivery_id text NOT NULL REFERENCES coordination.source_event_deliveries(delivery_id),
        attempt_count integer NOT NULL CHECK(attempt_count>=1),
        event_id bigint NOT NULL REFERENCES coordination.source_event_outbox(event_id),
        claim_token text NOT NULL CHECK(claim_token ~ '^LEASE-[0-9A-F]{32}$'),
        source_snapshot_contract text NOT NULL CHECK(source_snapshot_contract='oi.pg-source-world-model/1'),
        source_snapshot_sha256 char(64) NOT NULL CHECK(source_snapshot_sha256 ~ '^[0-9a-f]{64}$'),
        invalidated_count integer NOT NULL CHECK(invalidated_count BETWEEN 0 AND 100),
        has_more boolean NOT NULL,created_at timestamptz NOT NULL DEFAULT clock_timestamp(),
        PRIMARY KEY(delivery_id,attempt_count)
    );

    CREATE FUNCTION coordination.guard_source_event_delivery() RETURNS trigger LANGUAGE plpgsql AS $oi$
    DECLARE stamp timestamptz:=clock_timestamp(); receipt investigation.composer_source_event_receipts%ROWTYPE;
    BEGIN
        IF TG_OP='INSERT' THEN
            IF NEW.state<>'queued' OR NEW.revision<>1 OR NEW.attempt_count<>0 OR NEW.failure_count<>0
               OR NEW.lease_token IS NOT NULL OR NEW.lease_expires_at IS NOT NULL THEN
                RAISE EXCEPTION 'OI-DELIVERY-INITIAL'; END IF;
            IF NOT EXISTS(SELECT 1 FROM coordination.source_event_outbox e WHERE e.event_id=NEW.event_id
                AND ROW(e.patient_id,e.case_id,e.origin_org,e.purpose)=ROW(NEW.patient_id,NEW.case_id,NEW.origin_org,NEW.purpose)) THEN
                RAISE EXCEPTION 'OI-DELIVERY-LINEAGE'; END IF;
            NEW.created_at:=stamp;NEW.updated_at:=stamp;NEW.available_at:=stamp;RETURN NEW;
        END IF;
        IF ROW(NEW.delivery_id,NEW.event_id,NEW.consumer,NEW.patient_id,NEW.case_id,NEW.origin_org,NEW.actor,NEW.purpose,NEW.created_at)
           IS DISTINCT FROM ROW(OLD.delivery_id,OLD.event_id,OLD.consumer,OLD.patient_id,OLD.case_id,OLD.origin_org,OLD.actor,OLD.purpose,OLD.created_at) THEN
            RAISE EXCEPTION 'OI-DELIVERY-IMMUTABLE'; END IF;
        IF OLD.state IN('delivered','dead_letter') OR NEW.revision IS DISTINCT FROM OLD.revision+1 THEN
            RAISE EXCEPTION 'OI-DELIVERY-TERMINAL-REVISION'; END IF;
        IF NEW.state='running' THEN
            IF OLD.state NOT IN('queued','running') OR NEW.attempt_count IS DISTINCT FROM OLD.attempt_count+1
               OR NEW.failure_count IS DISTINCT FROM OLD.failure_count+(CASE WHEN OLD.state='running' THEN 1 ELSE 0 END)
               OR NEW.failure_count>=3 OR NEW.lease_token IS NULL OR NEW.lease_token IS NOT DISTINCT FROM OLD.lease_token
               OR NEW.lease_expires_at IS NULL OR NEW.lease_expires_at<=stamp OR NEW.lease_expires_at>stamp+interval '300 seconds'
               OR (OLD.state='running' AND OLD.lease_expires_at>stamp)
               OR (OLD.state='queued' AND OLD.available_at>stamp) THEN
                RAISE EXCEPTION 'OI-DELIVERY-CLAIM'; END IF;
        ELSE
            IF OLD.state<>'running' OR NEW.attempt_count IS DISTINCT FROM OLD.attempt_count
               OR NEW.lease_token IS NOT NULL OR NEW.lease_expires_at IS NOT NULL THEN
                RAISE EXCEPTION 'OI-DELIVERY-TRANSITION'; END IF;
            SELECT * INTO receipt FROM investigation.composer_source_event_receipts
                WHERE delivery_id=OLD.delivery_id AND attempt_count=OLD.attempt_count;
            IF FOUND THEN
                IF OLD.lease_expires_at<=stamp OR receipt.claim_token<>OLD.lease_token
                   OR NEW.failure_count<>0 OR NEW.state<>(CASE WHEN receipt.has_more THEN 'queued' ELSE 'delivered' END) THEN
                    RAISE EXCEPTION 'OI-DELIVERY-ACK'; END IF;
            ELSE
                IF NEW.failure_count IS DISTINCT FROM OLD.failure_count+1
                   OR NEW.state NOT IN('queued','dead_letter')
                   OR (NEW.state='queued' AND (NEW.failure_count>=3 OR OLD.lease_expires_at<=stamp))
                   OR (OLD.lease_expires_at<=stamp AND (NEW.state<>'dead_letter' OR NEW.failure_count<>3)) THEN
                    RAISE EXCEPTION 'OI-DELIVERY-FAILURE'; END IF;
            END IF;
            IF NEW.available_at>stamp+interval '60 seconds' THEN RAISE EXCEPTION 'OI-DELIVERY-DELAY'; END IF;
        END IF;
        NEW.updated_at:=stamp;RETURN NEW;
    END; $oi$;

    CREATE FUNCTION coordination.guard_source_event_delivery_event() RETURNS trigger LANGUAGE plpgsql AS $oi$
    DECLARE current_row coordination.source_event_deliveries%ROWTYPE;
        prior coordination.source_event_delivery_events%ROWTYPE; valid boolean:=false;
    BEGIN
        SELECT * INTO current_row FROM coordination.source_event_deliveries WHERE delivery_id=NEW.delivery_id FOR UPDATE;
        IF NOT FOUND OR ROW(NEW.revision,NEW.state,NEW.attempt_count,NEW.failure_count)
            IS DISTINCT FROM ROW(current_row.revision,current_row.state,current_row.attempt_count,current_row.failure_count) THEN
            RAISE EXCEPTION 'OI-DELIVERY-EVENT-STATE'; END IF;
        SELECT * INTO prior FROM coordination.source_event_delivery_events WHERE delivery_id=NEW.delivery_id ORDER BY revision DESC LIMIT 1;
        IF NEW.revision IS DISTINCT FROM COALESCE(prior.revision,0)+1 THEN RAISE EXCEPTION 'OI-DELIVERY-EVENT-REVISION'; END IF;
        IF NEW.revision=1 THEN valid:=NEW.reason_code='queued' AND NEW.state='queued';
        ELSIF NEW.state='running' THEN
            valid:=(prior.state='queued' AND NEW.reason_code='claimed') OR (prior.state='running' AND NEW.reason_code='lease_expired');
        ELSIF NEW.reason_code IN('continued','delivered') THEN
            valid:=prior.state='running' AND NEW.failure_count=0 AND NEW.state=CASE WHEN NEW.reason_code='continued' THEN 'queued' ELSE 'delivered' END;
        ELSIF NEW.reason_code='lease_expired' THEN
            valid:=prior.state='running' AND NEW.state='dead_letter' AND NEW.failure_count=3;
        ELSIF NEW.reason_code='retryable_failure' THEN
            valid:=prior.state='running' AND NEW.state=CASE WHEN NEW.failure_count=3 THEN 'dead_letter' ELSE 'queued' END;
        ELSIF NEW.reason_code IN('authority_unavailable','invalid_event') THEN
            valid:=prior.state='running' AND NEW.state='dead_letter';
        END IF;
        IF valid IS NOT TRUE THEN RAISE EXCEPTION 'OI-DELIVERY-EVENT-REASON'; END IF;
        NEW.created_at:=clock_timestamp();RETURN NEW;
    END; $oi$;

    CREATE FUNCTION investigation.guard_composer_source_receipt() RETURNS trigger LANGUAGE plpgsql AS $oi$
    DECLARE delivery coordination.source_event_deliveries%ROWTYPE;
    BEGIN
        SELECT * INTO delivery FROM coordination.source_event_deliveries WHERE delivery_id=NEW.delivery_id FOR UPDATE;
        IF NOT FOUND OR delivery.state<>'running' OR delivery.lease_expires_at<=clock_timestamp()
            OR ROW(NEW.event_id,NEW.attempt_count,NEW.claim_token)
               IS DISTINCT FROM ROW(delivery.event_id,delivery.attempt_count,delivery.lease_token) THEN
            RAISE EXCEPTION 'OI-DELIVERY-RECEIPT-FENCE'; END IF;
        NEW.created_at:=clock_timestamp();RETURN NEW;
    END; $oi$;

    CREATE FUNCTION coordination.require_source_delivery_consistency() RETURNS trigger LANGUAGE plpgsql AS $oi$
    DECLARE delivery coordination.source_event_deliveries%ROWTYPE;
    BEGIN
        IF TG_TABLE_NAME='source_event_deliveries' THEN
            IF NOT EXISTS(SELECT 1 FROM coordination.source_event_delivery_events e WHERE e.delivery_id=NEW.delivery_id
               AND ROW(e.revision,e.state,e.attempt_count,e.failure_count)=ROW(NEW.revision,NEW.state,NEW.attempt_count,NEW.failure_count)) THEN
                RAISE EXCEPTION 'OI-DELIVERY-HISTORY'; END IF;
        END IF;
        SELECT * INTO delivery FROM coordination.source_event_deliveries WHERE delivery_id=NEW.delivery_id;
        IF NOT FOUND OR (SELECT count(*) FROM coordination.source_event_delivery_events WHERE delivery_id=NEW.delivery_id)<>delivery.revision THEN
            RAISE EXCEPTION 'OI-DELIVERY-HISTORY'; END IF;
        IF EXISTS(SELECT 1 FROM coordination.source_event_delivery_events e WHERE e.delivery_id=NEW.delivery_id
                  AND e.reason_code IN('continued','delivered') AND NOT EXISTS(
                      SELECT 1 FROM investigation.composer_source_event_receipts r WHERE r.delivery_id=e.delivery_id
                      AND r.attempt_count=e.attempt_count AND r.has_more=(e.reason_code='continued'))) THEN
            RAISE EXCEPTION 'OI-DELIVERY-ACK-RECEIPT'; END IF;
        IF EXISTS(SELECT 1 FROM investigation.composer_source_event_receipts r WHERE r.delivery_id=NEW.delivery_id
                  AND NOT EXISTS(SELECT 1 FROM coordination.source_event_delivery_events e
                      WHERE e.delivery_id=r.delivery_id AND e.attempt_count=r.attempt_count
                      AND e.reason_code=CASE WHEN r.has_more THEN 'continued' ELSE 'delivered' END)) THEN
            RAISE EXCEPTION 'OI-DELIVERY-ORPHAN-RECEIPT'; END IF;
        RETURN NULL;
    END; $oi$;

    CREATE TRIGGER oi_source_delivery_guard BEFORE INSERT OR UPDATE ON coordination.source_event_deliveries
        FOR EACH ROW EXECUTE FUNCTION coordination.guard_source_event_delivery();
    CREATE TRIGGER oi_source_delivery_event_guard BEFORE INSERT ON coordination.source_event_delivery_events
        FOR EACH ROW EXECUTE FUNCTION coordination.guard_source_event_delivery_event();
    CREATE TRIGGER oi_source_receipt_guard BEFORE INSERT ON investigation.composer_source_event_receipts
        FOR EACH ROW EXECUTE FUNCTION investigation.guard_composer_source_receipt();
    """)
    for table in ('coordination.source_event_outbox', 'coordination.source_event_deliveries',
                  'coordination.source_event_delivery_events', 'investigation.composer_source_event_receipts'):
        mutations = 'DELETE' if table.endswith('.source_event_deliveries') else 'UPDATE OR DELETE'
        conn.exec_driver_sql(f"CREATE TRIGGER oi_source_delivery_immutable BEFORE {mutations} ON {table} FOR EACH ROW EXECUTE FUNCTION identity.reject_registry_history_mutation()")
        conn.exec_driver_sql(f"CREATE TRIGGER oi_source_delivery_no_truncate BEFORE TRUNCATE ON {table} FOR EACH STATEMENT EXECUTE FUNCTION identity.reject_registry_history_mutation()")
        if not table.endswith('.source_event_outbox'):
            operation = 'INSERT OR UPDATE' if table.endswith('.source_event_deliveries') else 'INSERT'
            conn.exec_driver_sql(f"CREATE CONSTRAINT TRIGGER oi_source_delivery_consistency AFTER {operation} ON {table} DEFERRABLE INITIALLY DEFERRED FOR EACH ROW EXECUTE FUNCTION coordination.require_source_delivery_consistency()")


def downgrade():
    conn = op.get_bind()
    conn.exec_driver_sql('LOCK TABLE identity.identity_domain_events, coordination.source_event_outbox, coordination.source_event_deliveries, coordination.source_event_delivery_events, investigation.composer_source_event_receipts IN ACCESS EXCLUSIVE MODE')
    if conn.exec_driver_sql('SELECT EXISTS(SELECT 1 FROM coordination.source_event_outbox) OR EXISTS(SELECT 1 FROM coordination.source_event_deliveries) OR EXISTS(SELECT 1 FROM coordination.source_event_delivery_events) OR EXISTS(SELECT 1 FROM investigation.composer_source_event_receipts)').scalar_one():
        raise CommandError('Stored source delivery history requires explicit reconciliation')
    conn.exec_driver_sql("""
        DROP TRIGGER oi_capture_source_event ON identity.identity_domain_events;
        DROP TABLE investigation.composer_source_event_receipts;
        DROP TABLE coordination.source_event_delivery_events;
        DROP TABLE coordination.source_event_deliveries;
        DROP TABLE coordination.source_event_outbox;
        DROP FUNCTION coordination.capture_source_event();
        DROP FUNCTION coordination.guard_source_event_outbox();
        DROP FUNCTION coordination.guard_source_event_delivery();
        DROP FUNCTION coordination.guard_source_event_delivery_event();
        DROP FUNCTION coordination.require_source_delivery_consistency();
        DROP FUNCTION investigation.guard_composer_source_receipt();
    """)
