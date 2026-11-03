"""H1 owned persistence for reviewed, immutable patient-to-source-case links.

No automatic case matching, source import, consent grant or SQLite transaction.
Existing objects are NOT silently adopted.
"""
from alembic import op
from alembic.util.exc import CommandError
from sqlalchemy import text

revision = "0003_case_binding"
down_revision = "0002_patient_registry"
branch_labels = None
depends_on = None

def upgrade():
    db = op.get_bind()
    existing = db.execute(text(
        "SELECT relname FROM pg_class c JOIN pg_namespace n ON n.oid=c.relnamespace "
        "WHERE n.nspname='identity' AND relname IN "
        "('identity_case_bindings','identity_case_binding_events')"
    )).scalars().all()
    triggers = db.execute(text(
        "SELECT proname FROM pg_proc p JOIN pg_namespace n ON n.oid=p.pronamespace "
        "WHERE n.nspname='identity' AND proname='guard_case_binding_mutation'"
    )).scalars().all()
    if existing or triggers:
        raise CommandError("Existing case-binding objects require explicit reconciliation")
    db.exec_driver_sql("""
        CREATE TABLE identity.identity_case_bindings (
            source_store_id text NOT NULL CHECK (length(source_store_id) BETWEEN 3 AND 128),
            case_id text NOT NULL CHECK (length(case_id) BETWEEN 3 AND 128),
            patient_id text NOT NULL REFERENCES identity.identity_patients(patient_id),
            source_organization text NOT NULL CHECK (length(source_organization) BETWEEN 3 AND 128),
            source_system text NOT NULL CHECK (length(source_system) BETWEEN 3 AND 128),
            source_subject_ref text NOT NULL CHECK (length(source_subject_ref) BETWEEN 3 AND 128),
            review_ref text NOT NULL CHECK (length(review_ref) BETWEEN 3 AND 128),
            created_by text NOT NULL CHECK (length(created_by) BETWEEN 3 AND 128),
            created_at timestamptz NOT NULL DEFAULT now(),
            status text NOT NULL DEFAULT 'active' CHECK (status IN ('active','revoked')),
            revoked_by text,
            revoked_at timestamptz,
            revocation_reason text,
            PRIMARY KEY (source_store_id, case_id),
            UNIQUE (source_organization,source_system,source_subject_ref),
            CHECK ((status='active' AND revoked_by IS NULL AND revoked_at IS NULL AND revocation_reason IS NULL)
                OR (status='revoked' AND revoked_by IS NOT NULL AND revoked_at IS NOT NULL
                    AND length(revocation_reason) BETWEEN 10 AND 200))
        );
        CREATE INDEX idx_case_binding_patient ON identity.identity_case_bindings(patient_id);
        CREATE FUNCTION identity.guard_case_binding_mutation() RETURNS trigger
        LANGUAGE plpgsql AS $$
        BEGIN
            IF TG_OP = 'DELETE' THEN
                RAISE EXCEPTION 'OI-CASE-BINDING-IMMUTABLE';
            END IF;
            IF NEW.source_store_id IS DISTINCT FROM OLD.source_store_id
                OR NEW.case_id IS DISTINCT FROM OLD.case_id
                OR NEW.patient_id IS DISTINCT FROM OLD.patient_id
                OR NEW.source_organization IS DISTINCT FROM OLD.source_organization
                OR NEW.source_system IS DISTINCT FROM OLD.source_system
                OR NEW.source_subject_ref IS DISTINCT FROM OLD.source_subject_ref
                OR NEW.review_ref IS DISTINCT FROM OLD.review_ref
                OR NEW.created_by IS DISTINCT FROM OLD.created_by
                OR NEW.created_at IS DISTINCT FROM OLD.created_at
                OR OLD.status <> 'active' OR NEW.status <> 'revoked'
                OR NEW.revoked_by IS NULL OR NEW.revoked_at IS NULL
                OR NEW.revocation_reason IS NULL THEN
                RAISE EXCEPTION 'OI-CASE-BINDING-IMMUTABLE';
            END IF;
            RETURN NEW;
        END;
        $$;
        CREATE TRIGGER guard_case_binding_mutation BEFORE UPDATE OR DELETE
            ON identity.identity_case_bindings
            FOR EACH ROW EXECUTE FUNCTION identity.guard_case_binding_mutation();
    """)

def downgrade():
    db = op.get_bind()
    db.exec_driver_sql("DROP TABLE identity.identity_case_bindings")
    db.exec_driver_sql("DROP FUNCTION identity.guard_case_binding_mutation()")
