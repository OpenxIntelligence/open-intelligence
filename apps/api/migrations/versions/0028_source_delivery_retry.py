"""Allow an explicitly authorized retry of an exact, recoverable failed delivery."""
from alembic import op
from alembic.util.exc import CommandError

revision = '0028_source_delivery_retry'
down_revision = '0027_source_event_purpose'
branch_labels = None
depends_on = None

REASONS = """'queued','claimed','lease_expired','continued','delivered',
             'retryable_failure','authority_unavailable','invalid_event'"""


def upgrade():
    db = op.get_bind()
    db.exec_driver_sql(f"""
        ALTER TABLE coordination.source_event_delivery_events
          DROP CONSTRAINT source_event_delivery_events_reason_code_check,
          ADD COLUMN retry_audit_id bigint UNIQUE REFERENCES identity.identity_domain_events(id),
          ADD CONSTRAINT source_event_delivery_events_reason_code_check
            CHECK (reason_code IN ({REASONS}, 'operator_retry')),
          ADD CONSTRAINT source_delivery_retry_audit_required
            CHECK ((reason_code='operator_retry') = (retry_audit_id IS NOT NULL));

        -- Keep the published guards on every existing transition. The only
        -- exception is a failed-to-queued transition with linked, immutable proof.
        DROP TRIGGER oi_source_delivery_guard ON coordination.source_event_deliveries;
        CREATE TRIGGER oi_source_delivery_insert_guard BEFORE INSERT ON coordination.source_event_deliveries
          FOR EACH ROW EXECUTE FUNCTION coordination.guard_source_event_delivery();
        CREATE TRIGGER oi_source_delivery_guard BEFORE UPDATE ON coordination.source_event_deliveries
          FOR EACH ROW WHEN (OLD.state<>'dead_letter' OR NEW.state<>'queued')
          EXECUTE FUNCTION coordination.guard_source_event_delivery();

        CREATE FUNCTION coordination.guard_source_retry_transition() RETURNS trigger LANGUAGE plpgsql AS $oi$
        BEGIN
          IF (to_jsonb(NEW) - ARRAY['state','revision','failure_count','available_at','updated_at'])
             IS DISTINCT FROM
             (to_jsonb(OLD) - ARRAY['state','revision','failure_count','available_at','updated_at'])
             OR NEW.revision IS DISTINCT FROM OLD.revision+1 OR NEW.failure_count IS DISTINCT FROM 0
             OR NOT EXISTS (
               SELECT 1 FROM coordination.source_event_delivery_events h
               WHERE h.delivery_id=OLD.delivery_id AND h.revision=OLD.revision AND h.state='dead_letter'
                 AND h.reason_code IN ('lease_expired','retryable_failure','authority_unavailable')
             )
          THEN RAISE EXCEPTION 'OI-DELIVERY-RETRY-TRANSITION'; END IF;
          NEW.updated_at:=clock_timestamp();
          NEW.available_at:=NEW.updated_at;
          RETURN NEW;
        END; $oi$;
        CREATE TRIGGER oi_source_retry_transition BEFORE UPDATE ON coordination.source_event_deliveries
          FOR EACH ROW WHEN (OLD.state='dead_letter' AND NEW.state='queued')
          EXECUTE FUNCTION coordination.guard_source_retry_transition();

        DROP TRIGGER oi_source_delivery_event_guard ON coordination.source_event_delivery_events;
        CREATE TRIGGER oi_source_delivery_event_guard BEFORE INSERT ON coordination.source_event_delivery_events
          FOR EACH ROW WHEN (NEW.reason_code<>'operator_retry')
          EXECUTE FUNCTION coordination.guard_source_event_delivery_event();

        CREATE FUNCTION coordination.guard_source_retry_event() RETURNS trigger LANGUAGE plpgsql AS $oi$
        DECLARE d coordination.source_event_deliveries%ROWTYPE;
        BEGIN
          SELECT * INTO STRICT d FROM coordination.source_event_deliveries
            WHERE delivery_id=NEW.delivery_id FOR UPDATE;
          IF ROW(NEW.revision,NEW.state,NEW.attempt_count,NEW.failure_count)
             IS DISTINCT FROM ROW(d.revision,d.state,d.attempt_count,d.failure_count)
             OR d.state<>'queued' OR d.failure_count<>0
             OR NOT EXISTS (
               SELECT 1 FROM coordination.source_event_delivery_events h
               JOIN identity.identity_domain_events j ON j.id=NEW.retry_audit_id
               WHERE h.delivery_id=d.delivery_id AND h.revision=d.revision-1 AND h.state='dead_letter'
                 AND h.reason_code IN ('lease_expired','retryable_failure','authority_unavailable')
                 AND h.attempt_count=d.attempt_count AND j.patient_id=d.patient_id
                 AND j.event_type='source.delivery.retry_authorized'
                 AND j.metadata_json=jsonb_build_object(
                   'delivery_id',d.delivery_id,'source_event_id',d.event_id,'consumer',d.consumer,
                   'case_id',d.case_id,'organization',d.origin_org,'actor',d.actor,'purpose',d.purpose,
                   'failed_revision',h.revision,'failure_reason',h.reason_code))
          THEN RAISE EXCEPTION 'OI-DELIVERY-RETRY-AUDIT'; END IF;
          NEW.created_at:=clock_timestamp();
          RETURN NEW;
        END; $oi$;
        CREATE TRIGGER oi_source_retry_event BEFORE INSERT ON coordination.source_event_delivery_events
          FOR EACH ROW WHEN (NEW.reason_code='operator_retry')
          EXECUTE FUNCTION coordination.guard_source_retry_event();
    """)


def downgrade():
    db = op.get_bind()
    db.exec_driver_sql("""LOCK TABLE coordination.source_event_deliveries,
        coordination.source_event_delivery_events IN ACCESS EXCLUSIVE MODE""")
    if db.exec_driver_sql("""SELECT EXISTS (SELECT 1 FROM coordination.source_event_delivery_events
                          WHERE retry_audit_id IS NOT NULL)""").scalar_one():
        raise CommandError('Stored source delivery retry authorizations require reconciliation')
    db.exec_driver_sql(f"""
        DROP TRIGGER oi_source_retry_event ON coordination.source_event_delivery_events;
        DROP FUNCTION coordination.guard_source_retry_event();
        DROP TRIGGER oi_source_delivery_event_guard ON coordination.source_event_delivery_events;
        CREATE TRIGGER oi_source_delivery_event_guard BEFORE INSERT ON coordination.source_event_delivery_events
          FOR EACH ROW EXECUTE FUNCTION coordination.guard_source_event_delivery_event();
        DROP TRIGGER oi_source_retry_transition ON coordination.source_event_deliveries;
        DROP FUNCTION coordination.guard_source_retry_transition();
        DROP TRIGGER oi_source_delivery_insert_guard ON coordination.source_event_deliveries;
        DROP TRIGGER oi_source_delivery_guard ON coordination.source_event_deliveries;
        CREATE TRIGGER oi_source_delivery_guard BEFORE INSERT OR UPDATE ON coordination.source_event_deliveries
          FOR EACH ROW EXECUTE FUNCTION coordination.guard_source_event_delivery();
        ALTER TABLE coordination.source_event_delivery_events
          DROP CONSTRAINT source_event_delivery_events_reason_code_check,
          DROP COLUMN retry_audit_id,
          ADD CONSTRAINT source_event_delivery_events_reason_code_check CHECK (reason_code IN ({REASONS}));
    """)
