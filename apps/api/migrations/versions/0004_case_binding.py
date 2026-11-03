"""Synthetic-only qualified patient-to-external-case reference binding.

Port of the existing CanonicalLabBridge reference identity principle (#95):
never infer a patient from a shared name, specimen or approximate demographics.
This establishes a *fixture-scoped* mapping, not actual identity verification
or an assertion that clinical source records exist.
"""
from alembic import op
from alembic.util.exc import CommandError
from sqlalchemy import text

revision = "0004_case_binding"
down_revision = "0003_record_acquisition"
branch_labels = None
depends_on = None


def upgrade():
    connection = op.get_bind()
    for obj in (
        "coordination.patient_case_bindings",
        "coordination.idx_oi_case_binding_patient",
        "coordination.oi_case_binding_update_guard",
        "coordination.oi_case_binding_delete_guard",
    ):
        if connection.execute(text("SELECT to_regclass(:name)"), {"name": obj}).scalar_one() is not None:
            raise CommandError("Existing case binding objects require explicit reconciliation")
    if connection.execute(text("SELECT to_regprocedure('coordination.guard_case_binding_update()')")).scalar_one() is not None:
        raise CommandError("Existing case-binding guard requires explicit reconciliation")
    connection.exec_driver_sql("""
        CREATE TABLE coordination.patient_case_bindings (
          case_id text PRIMARY KEY CHECK (case_id ~ '^CASE-[A-Z0-9-]{1,35}$'),
          patient_id text NOT NULL REFERENCES identity.identity_patients(patient_id),
          origin_org text NOT NULL,
          source_organization text NOT NULL CHECK (char_length(source_organization) BETWEEN 3 AND 128),
          source_system text NOT NULL CHECK (char_length(source_system) BETWEEN 3 AND 128),
          source_subject_ref text NOT NULL CHECK (char_length(source_subject_ref) BETWEEN 3 AND 128),
          review_ref text NOT NULL CHECK (char_length(review_ref) BETWEEN 3 AND 128),
          created_by text NOT NULL,
          purpose text NOT NULL CHECK (purpose IN ('operations','research')),
          created_at timestamptz NOT NULL DEFAULT now(),
          status text NOT NULL DEFAULT 'active' CHECK (status IN ('active','revoked')),
          revision bigint NOT NULL DEFAULT 1 CHECK (revision IN (1,2)),
          revoked_at timestamptz,
          revoked_by text,
          revocation_reason text,
          CHECK ((status='active' AND revision=1 AND revoked_at IS NULL
                  AND revoked_by IS NULL AND revocation_reason IS NULL)
              OR (status='revoked' AND revision=2 AND revoked_at IS NOT NULL
                  AND revoked_by IS NOT NULL AND char_length(revocation_reason) BETWEEN 10 AND 200)),
          UNIQUE (source_organization,source_system,source_subject_ref)
        );
        CREATE INDEX idx_oi_case_binding_patient
          ON coordination.patient_case_bindings(patient_id,case_id);
        CREATE FUNCTION coordination.guard_case_binding_update()
        RETURNS trigger LANGUAGE plpgsql AS $oi_case_guard$
        BEGIN
          IF (OLD.case_id, OLD.patient_id, OLD.origin_org, OLD.source_organization,
              OLD.source_system, OLD.source_subject_ref, OLD.review_ref,
              OLD.created_by, OLD.purpose, OLD.created_at)
             IS DISTINCT FROM
             (NEW.case_id, NEW.patient_id, NEW.origin_org, NEW.source_organization,
              NEW.source_system, NEW.source_subject_ref, NEW.review_ref,
              NEW.created_by, NEW.purpose, NEW.created_at)
          THEN RAISE EXCEPTION 'OI-CASE-BINDING-IMMUTABLE'; END IF;
          IF OLD.status!='active' OR NEW.status!='revoked'
             OR NEW.revision!=OLD.revision+1
             OR NEW.revoked_at<OLD.created_at THEN
            RAISE EXCEPTION 'OI-CASE-BINDING-STATE';
          END IF;
          RETURN NEW;
        END;
        $oi_case_guard$;
        CREATE TRIGGER oi_case_binding_update_guard
          BEFORE UPDATE ON coordination.patient_case_bindings
          FOR EACH ROW EXECUTE FUNCTION coordination.guard_case_binding_update();
        CREATE TRIGGER oi_case_binding_delete_guard
          BEFORE DELETE ON coordination.patient_case_bindings
          FOR EACH ROW EXECUTE FUNCTION identity.reject_registry_history_mutation();
        CREATE FUNCTION coordination.guard_case_binding_origin()
        RETURNS trigger LANGUAGE plpgsql AS $oi_case_guard$
        BEGIN
          IF NOT EXISTS (
            SELECT 1 FROM identity.identity_patients p
            WHERE p.patient_id=NEW.patient_id AND p.origin_org=NEW.origin_org
              AND p.status='active'
          ) THEN RAISE EXCEPTION 'OI-CASE-BINDING-PATIENT-ORIGIN'; END IF;
          RETURN NEW;
        END;
        $oi_case_guard$;
        CREATE TRIGGER oi_case_binding_origin_guard
          BEFORE INSERT ON coordination.patient_case_bindings
          FOR EACH ROW EXECUTE FUNCTION coordination.guard_case_binding_origin();
    """)


def downgrade():
    connection = op.get_bind()
    for sql in (
        "DROP TABLE coordination.patient_case_bindings",
        "DROP FUNCTION coordination.guard_case_binding_origin()",
        "DROP FUNCTION coordination.guard_case_binding_update()",
    ):
        connection.exec_driver_sql(sql)
