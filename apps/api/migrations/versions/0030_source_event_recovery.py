"""Explicit, immutable recovery requests for the existing source-event consumer.

No source, event, actor, scope or attempt identity is replaced. Recovery only
queues a new attempt of the existing current-context reconciliation, never a
previous external effect. All published migrations and terminal history remain
intact. Existing delivery fencing and acknowledgement consistency still apply.
"""
from alembic import op
from alembic.util.exc import CommandError

revision = "0030_source_event_recovery"
down_revision = "0029_patient_access"
branch_labels = None
depends_on = None


def upgrade():
    op.get_bind().exec_driver_sql("""
    LOCK TABLE coordination.source_event_deliveries,
        coordination.source_event_delivery_events,
        investigation.composer_source_event_receipts IN ACCESS EXCLUSIVE MODE;
    CREATE TABLE coordination.source_event_recoveries (
        delivery_id text NOT NULL REFERENCES coordination.source_event_deliveries(delivery_id),
        failed_revision integer NOT NULL CHECK(failed_revision>=1),
        recovery_revision integer NOT NULL CHECK(recovery_revision=failed_revision+1),
        recorded_at timestamptz NOT NULL DEFAULT clock_timestamp(),
        PRIMARY KEY(delivery_id,failed_revision),
        UNIQUE(delivery_id,recovery_revision),
        FOREIGN KEY(delivery_id,failed_revision)
            REFERENCES coordination.source_event_delivery_events(delivery_id,revision)
    );
    CREATE FUNCTION coordination.guard_source_event_recovery() RETURNS trigger LANGUAGE plpgsql AS $oi$
    DECLARE delivery coordination.source_event_deliveries%ROWTYPE;
    BEGIN
        SELECT * INTO delivery FROM coordination.source_event_deliveries
            WHERE delivery_id=NEW.delivery_id FOR UPDATE;
        IF NOT FOUND OR delivery.consumer<>'composer-source-context/1'
           OR delivery.purpose<>'operations' OR delivery.state<>'dead_letter'
           OR delivery.revision IS DISTINCT FROM NEW.failed_revision
           OR NEW.recovery_revision IS DISTINCT FROM NEW.failed_revision+1
           OR NOT EXISTS(SELECT 1 FROM coordination.source_event_delivery_events e
                WHERE e.delivery_id=NEW.delivery_id AND e.revision=NEW.failed_revision
                  AND e.state='dead_letter'
                  AND e.reason_code IN('retryable_failure','lease_expired','authority_unavailable')) THEN
            RAISE EXCEPTION 'OI-DELIVERY-RECOVERY-TARGET'; END IF;
        NEW.recorded_at:=clock_timestamp();RETURN NEW;
    END; $oi$;
    CREATE TRIGGER oi_source_recovery_guard BEFORE INSERT ON coordination.source_event_recoveries
        FOR EACH ROW EXECUTE FUNCTION coordination.guard_source_event_recovery();
    CREATE TRIGGER oi_source_recovery_immutable BEFORE UPDATE OR DELETE ON coordination.source_event_recoveries
        FOR EACH ROW EXECUTE FUNCTION identity.reject_registry_history_mutation();
    CREATE TRIGGER oi_source_recovery_no_truncate BEFORE TRUNCATE ON coordination.source_event_recoveries
        FOR EACH STATEMENT EXECUTE FUNCTION identity.reject_registry_history_mutation();
    ALTER TABLE coordination.source_event_delivery_events
        DROP CONSTRAINT source_event_delivery_events_reason_code_check;
    ALTER TABLE coordination.source_event_delivery_events
        ADD CONSTRAINT source_event_delivery_events_reason_code_check CHECK(reason_code IN(
            'queued','claimed','lease_expired','continued','delivered','retryable_failure',
            'authority_unavailable','invalid_event','recovery_requested'));
    CREATE OR REPLACE FUNCTION coordination.guard_source_event_delivery() RETURNS trigger LANGUAGE plpgsql AS $oi$
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
        IF OLD.state='dead_letter' THEN
            IF NEW.state<>'queued' OR NEW.revision IS DISTINCT FROM OLD.revision+1
               OR NEW.attempt_count IS DISTINCT FROM OLD.attempt_count OR NEW.failure_count<>0
               OR NEW.lease_token IS NOT NULL OR NEW.lease_expires_at IS NOT NULL
               OR NOT EXISTS(SELECT 1 FROM coordination.source_event_recoveries r
                    WHERE r.delivery_id=OLD.delivery_id AND r.failed_revision=OLD.revision
                      AND r.recovery_revision=NEW.revision) THEN
                RAISE EXCEPTION 'OI-DELIVERY-RECOVERY'; END IF;
            NEW.available_at:=stamp;NEW.updated_at:=stamp;RETURN NEW;
        END IF;
        IF OLD.state='delivered' OR NEW.revision IS DISTINCT FROM OLD.revision+1 THEN
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

    CREATE OR REPLACE FUNCTION coordination.guard_source_event_delivery_event() RETURNS trigger LANGUAGE plpgsql AS $oi$
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
        ELSIF NEW.reason_code='recovery_requested' THEN
            valid:=prior.state='dead_letter'
                AND prior.reason_code IN('retryable_failure','lease_expired','authority_unavailable')
                AND NEW.state='queued' AND NEW.failure_count=0
                AND NEW.attempt_count=prior.attempt_count
                AND EXISTS(SELECT 1 FROM coordination.source_event_recoveries r
                    WHERE r.delivery_id=NEW.delivery_id AND r.failed_revision=prior.revision
                      AND r.recovery_revision=NEW.revision);
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

    CREATE OR REPLACE FUNCTION coordination.require_source_delivery_consistency() RETURNS trigger LANGUAGE plpgsql AS $oi$
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
        IF EXISTS(SELECT 1 FROM coordination.source_event_recoveries r
                  WHERE r.delivery_id=NEW.delivery_id AND NOT EXISTS(
                    SELECT 1 FROM coordination.source_event_delivery_events failed
                    JOIN coordination.source_event_delivery_events recovered
                      ON recovered.delivery_id=failed.delivery_id
                    WHERE failed.delivery_id=r.delivery_id AND failed.revision=r.failed_revision
                      AND failed.state='dead_letter'
                      AND failed.reason_code IN('retryable_failure','lease_expired','authority_unavailable')
                      AND recovered.revision=r.recovery_revision AND recovered.state='queued'
                      AND recovered.reason_code='recovery_requested' AND recovered.failure_count=0
                      AND recovered.attempt_count=failed.attempt_count)) THEN
            RAISE EXCEPTION 'OI-DELIVERY-ORPHAN-RECOVERY'; END IF;
        IF EXISTS(SELECT 1 FROM coordination.source_event_delivery_events e
                  WHERE e.delivery_id=NEW.delivery_id AND e.reason_code='recovery_requested'
                    AND NOT EXISTS(SELECT 1 FROM coordination.source_event_recoveries r
                      WHERE r.delivery_id=e.delivery_id AND r.recovery_revision=e.revision)) THEN
            RAISE EXCEPTION 'OI-DELIVERY-MISSING-RECOVERY'; END IF;
        RETURN NULL;
    END; $oi$;
    CREATE CONSTRAINT TRIGGER oi_source_recovery_consistency AFTER INSERT ON coordination.source_event_recoveries
        DEFERRABLE INITIALLY DEFERRED FOR EACH ROW
        EXECUTE FUNCTION coordination.require_source_delivery_consistency();
    """)


def downgrade():
    conn = op.get_bind()
    conn.exec_driver_sql("""
        LOCK TABLE coordination.source_event_deliveries,
            coordination.source_event_delivery_events,
            investigation.composer_source_event_receipts,
            coordination.source_event_recoveries IN ACCESS EXCLUSIVE MODE
    """)
    if conn.exec_driver_sql("""
        SELECT EXISTS(SELECT 1 FROM coordination.source_event_recoveries)
            OR EXISTS(SELECT 1 FROM coordination.source_event_delivery_events
                      WHERE reason_code='recovery_requested')
    """).scalar_one():
        raise CommandError("Source event recovery history must be retained; populated downgrade refused")
    # Restore the published delivery contracts before dropping the new child.
    conn.exec_driver_sql("""
    CREATE OR REPLACE FUNCTION coordination.guard_source_event_delivery() RETURNS trigger LANGUAGE plpgsql AS $oi$
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

    CREATE OR REPLACE FUNCTION coordination.guard_source_event_delivery_event() RETURNS trigger LANGUAGE plpgsql AS $oi$
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

    CREATE OR REPLACE FUNCTION coordination.require_source_delivery_consistency() RETURNS trigger LANGUAGE plpgsql AS $oi$
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
    DROP TABLE coordination.source_event_recoveries;
    DROP FUNCTION coordination.guard_source_event_recovery();
    ALTER TABLE coordination.source_event_delivery_events
        DROP CONSTRAINT source_event_delivery_events_reason_code_check;
    ALTER TABLE coordination.source_event_delivery_events
        ADD CONSTRAINT source_event_delivery_events_reason_code_check CHECK(reason_code IN(
            'queued','claimed','lease_expired','continued','delivered','retryable_failure',
            'authority_unavailable','invalid_event'));
    """)
