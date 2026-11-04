"""A bounded operational record-request queue attached to canonical identity.

No clinical source-version table is installed in H1. Thus this migration does
NOT create a fake source authority or claim a request was received. Status is
limited to requested/cancelled; a later source owner must implement receipt.
"""
from alembic import op
from alembic.util.exc import CommandError
from sqlalchemy import text

revision = "0003_record_acquisition"
down_revision = "0002_patient_registry"
branch_labels = None
depends_on = None


def upgrade():
    conn = op.get_bind()
    if conn.execute(text(
        "SELECT to_regclass('coordination.record_requests')"
    )).scalar_one() is not None:
        raise CommandError("Existing record requests require explicit migration reconciliation")
    if conn.execute(text(
        "SELECT to_regprocedure('coordination.guard_record_request_update()')"
    )).scalar_one() is not None:
        raise CommandError("Existing record-request guard requires explicit reconciliation")
    conn.exec_driver_sql("""
        CREATE SCHEMA IF NOT EXISTS coordination;
        CREATE TABLE coordination.record_requests (
          request_id text PRIMARY KEY,
          patient_id text NOT NULL REFERENCES identity.identity_patients(patient_id),
          origin_org text NOT NULL,
          request_key text NOT NULL,
          intent_sha256 char(64) NOT NULL CHECK (intent_sha256 ~ '^[0-9a-f]{64}$'),
          kind text NOT NULL CHECK (kind IN ('clinical','pathology','laboratory','imaging','molecular','other')),
          record_label text NOT NULL CHECK (char_length(record_label) BETWEEN 1 AND 140),
          source_organization text NOT NULL CHECK (char_length(source_organization) BETWEEN 1 AND 100),
          actor text NOT NULL,
          purpose text NOT NULL CHECK (purpose IN ('operations','research')),
          status text NOT NULL DEFAULT 'requested' CHECK (status IN ('requested','cancelled')),
          revision bigint NOT NULL DEFAULT 1 CHECK (revision >= 1),
          cancellation_reason text,
          created_at timestamptz NOT NULL DEFAULT now(),
          updated_at timestamptz NOT NULL DEFAULT now(),
          UNIQUE(patient_id,request_key),
          CHECK ((status='requested' AND revision=1 AND cancellation_reason IS NULL)
              OR (status='cancelled' AND revision=2
                  AND char_length(cancellation_reason) BETWEEN 1 AND 200))
        );
        CREATE INDEX idx_oi_acquisition_patient ON coordination.record_requests(patient_id,created_at,request_id);
        CREATE FUNCTION coordination.guard_record_request_update()
        RETURNS trigger LANGUAGE plpgsql AS $oi_acquisition$
        BEGIN
          IF (OLD.request_id,OLD.patient_id,OLD.origin_org,OLD.request_key,OLD.intent_sha256,
              OLD.kind,OLD.record_label,OLD.source_organization,OLD.actor,OLD.purpose,OLD.created_at)
             IS DISTINCT FROM
             (NEW.request_id,NEW.patient_id,NEW.origin_org,NEW.request_key,NEW.intent_sha256,
              NEW.kind,NEW.record_label,NEW.source_organization,NEW.actor,NEW.purpose,NEW.created_at)
          THEN RAISE EXCEPTION 'OI-RECORD-REQUEST-IMMUTABLE'; END IF;
          IF OLD.status!='requested' OR NEW.status!='cancelled' OR NEW.revision!=OLD.revision+1
             OR NEW.updated_at < OLD.updated_at THEN
            RAISE EXCEPTION 'OI-RECORD-REQUEST-STATE';
          END IF;
          RETURN NEW;
        END;
        $oi_acquisition$;
        CREATE TRIGGER oi_record_request_update_guard
        BEFORE UPDATE ON coordination.record_requests
        FOR EACH ROW EXECUTE FUNCTION coordination.guard_record_request_update();
        CREATE TRIGGER oi_record_request_delete_guard
        BEFORE DELETE ON coordination.record_requests
        FOR EACH ROW EXECUTE FUNCTION identity.reject_registry_history_mutation();
        CREATE FUNCTION coordination.guard_record_request_origin()
        RETURNS trigger LANGUAGE plpgsql AS $oi_acquisition$
        BEGIN
          IF NOT EXISTS (
            SELECT 1 FROM identity.identity_patients p
            WHERE p.patient_id=NEW.patient_id AND p.origin_org=NEW.origin_org
          ) THEN RAISE EXCEPTION 'OI-RECORD-REQUEST-ORIGIN'; END IF;
          RETURN NEW;
        END;
        $oi_acquisition$;
        CREATE TRIGGER oi_record_request_origin_guard
        BEFORE INSERT ON coordination.record_requests
        FOR EACH ROW EXECUTE FUNCTION coordination.guard_record_request_origin();
    """)


def downgrade():
    conn = op.get_bind()
    for sql in (
        "DROP TABLE coordination.record_requests",
        "DROP FUNCTION coordination.guard_record_request_origin()",
        "DROP FUNCTION coordination.guard_record_request_update()",
    ):
        conn.exec_driver_sql(sql)
    # Leave the namespace for any unrelated future objects.
