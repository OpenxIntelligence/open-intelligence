"""Reviewed institutional identities beneath the existing patient/case owner."""
from alembic import op
from alembic.util.exc import CommandError
from sqlalchemy import text

revision = "0023_institution_identities"
down_revision = "0022_lab_citation_source_scope"
branch_labels = None
depends_on = None


def upgrade():
    conn = op.get_bind()
    if conn.execute(text("SELECT to_regclass('coordination.case_source_identities')")).scalar_one():
        raise CommandError("Institution identities require explicit reconciliation")
    conn.exec_driver_sql("""
        CREATE TABLE coordination.case_source_identities (
          identity_id text PRIMARY KEY CHECK (identity_id ~ '^IDENTITY-[A-F0-9]{32}$'),
          case_id text NOT NULL REFERENCES coordination.patient_case_bindings(case_id),
          source_organization text NOT NULL CHECK (char_length(source_organization) BETWEEN 3 AND 128),
          source_system text NOT NULL CHECK (char_length(source_system) BETWEEN 3 AND 128),
          source_subject_ref text NOT NULL CHECK (char_length(source_subject_ref) BETWEEN 3 AND 128),
          primary_identity boolean NOT NULL DEFAULT false,
          request_key text NOT NULL,
          request_digest char(64) NOT NULL,
          created_by text NOT NULL,
          created_at timestamptz NOT NULL DEFAULT now(),
          status text NOT NULL CHECK (status IN ('quarantined','active','rejected')),
          review_ref text,
          reviewed_by text,
          reviewed_at timestamptz,
          CHECK ((status='quarantined' AND review_ref IS NULL AND reviewed_by IS NULL AND reviewed_at IS NULL)
            OR (status IN ('active','rejected') AND review_ref IS NOT NULL AND char_length(review_ref) BETWEEN 3 AND 128
                AND reviewed_by IS NOT NULL AND reviewed_at IS NOT NULL)),
          CHECK (NOT primary_identity OR status='active'),
          UNIQUE (case_id,request_key)
        );
        CREATE UNIQUE INDEX oi_institution_subject_unique ON coordination.case_source_identities
          (source_organization,source_system,source_subject_ref) WHERE status='active';
        CREATE UNIQUE INDEX oi_institution_namespace_unique ON coordination.case_source_identities
          (case_id,source_organization,source_system) WHERE status='active';
        CREATE UNIQUE INDEX oi_institution_primary_unique ON coordination.case_source_identities
          (case_id) WHERE primary_identity;
        CREATE FUNCTION coordination.seed_primary_source_identity() RETURNS trigger
        LANGUAGE plpgsql AS $guard$
        BEGIN
          INSERT INTO coordination.case_source_identities
            (identity_id,case_id,source_organization,source_system,source_subject_ref,
             primary_identity,request_key,request_digest,created_by,created_at,status,
             review_ref,reviewed_by,reviewed_at)
          VALUES ('IDENTITY-'||upper(md5(NEW.case_id)),NEW.case_id,NEW.source_organization,
             NEW.source_system,NEW.source_subject_ref,true,'PRIMARY',repeat('0',64),
             NEW.created_by,NEW.created_at,'active',NEW.review_ref,NEW.created_by,NEW.created_at);
          RETURN NEW;
        END; $guard$;
        INSERT INTO coordination.case_source_identities
          (identity_id,case_id,source_organization,source_system,source_subject_ref,
           primary_identity,request_key,request_digest,created_by,created_at,status,
           review_ref,reviewed_by,reviewed_at)
        SELECT 'IDENTITY-'||upper(md5(case_id)),case_id,source_organization,source_system,source_subject_ref,
           true,'PRIMARY',repeat('0',64),created_by,created_at,'active',review_ref,created_by,created_at
        FROM coordination.patient_case_bindings;
        CREATE TRIGGER oi_primary_source_identity AFTER INSERT ON coordination.patient_case_bindings
          FOR EACH ROW EXECUTE FUNCTION coordination.seed_primary_source_identity();
        CREATE FUNCTION coordination.guard_source_identity() RETURNS trigger
        LANGUAGE plpgsql AS $guard$
        BEGIN
          IF (NEW.identity_id,NEW.case_id,NEW.source_organization,NEW.source_system,
              NEW.source_subject_ref,NEW.primary_identity,NEW.request_key,NEW.request_digest,
              NEW.created_by,NEW.created_at) IS DISTINCT FROM
             (OLD.identity_id,OLD.case_id,OLD.source_organization,OLD.source_system,
              OLD.source_subject_ref,OLD.primary_identity,OLD.request_key,OLD.request_digest,
              OLD.created_by,OLD.created_at) THEN
            RAISE EXCEPTION 'OI-INSTITUTION-IDENTITY-IMMUTABLE';
          END IF;
          IF OLD.status!='quarantined' OR NEW.status NOT IN ('active','rejected')
              OR NEW.reviewed_at < OLD.created_at THEN
            RAISE EXCEPTION 'OI-INSTITUTION-IDENTITY-TRANSITION';
          END IF;
          RETURN NEW;
        END; $guard$;
        CREATE TRIGGER oi_source_identity_update BEFORE UPDATE ON coordination.case_source_identities
          FOR EACH ROW EXECUTE FUNCTION coordination.guard_source_identity();
        CREATE TRIGGER oi_source_identity_delete BEFORE DELETE ON coordination.case_source_identities
          FOR EACH ROW EXECUTE FUNCTION identity.reject_registry_history_mutation();
        CREATE OR REPLACE FUNCTION clinical_source.guard_fhir_laboratory_source_insert() RETURNS trigger
        LANGUAGE plpgsql AS $guard$
        BEGIN
          IF NOT EXISTS (
            SELECT 1 FROM clinical_source.source_versions s
            JOIN coordination.patient_case_bindings b ON b.case_id=s.case_id
            JOIN coordination.case_source_identities i ON i.case_id=b.case_id
            WHERE s.source_id=NEW.source_id AND s.kind='laboratory' AND b.status='active'
              AND i.status='active' AND i.source_organization=NEW.source_organization
              AND i.source_system=NEW.source_system
              AND ('Patient/'||i.source_subject_ref)=NEW.subject_reference
          ) THEN RAISE EXCEPTION 'OI-FHIR-LAB-SOURCE-OWNER'; END IF;
          RETURN NEW;
        END; $guard$;
    """)


def downgrade():
    conn = op.get_bind()
    if conn.execute(text("SELECT EXISTS(SELECT 1 FROM coordination.case_source_identities WHERE NOT primary_identity)")).scalar_one():
        raise CommandError("Institution identity decisions require explicit reconciliation before downgrade")
    # Restore the previous single-institution insert guard without rewriting originals.
    conn.exec_driver_sql("""
        CREATE OR REPLACE FUNCTION clinical_source.guard_fhir_laboratory_source_insert() RETURNS trigger
        LANGUAGE plpgsql AS $guard$
        BEGIN
          IF NOT EXISTS (
            SELECT 1 FROM clinical_source.source_versions s
            JOIN coordination.patient_case_bindings b ON b.case_id=s.case_id
            WHERE s.source_id=NEW.source_id AND s.kind='laboratory' AND b.status='active'
              AND b.source_organization=NEW.source_organization AND b.source_system=NEW.source_system
              AND ('Patient/'||b.source_subject_ref)=NEW.subject_reference
          ) THEN RAISE EXCEPTION 'OI-FHIR-LAB-SOURCE-OWNER'; END IF;
          RETURN NEW;
        END; $guard$;
        DROP TRIGGER oi_primary_source_identity ON coordination.patient_case_bindings;
        DROP TABLE coordination.case_source_identities;
        DROP FUNCTION coordination.seed_primary_source_identity();
        DROP FUNCTION coordination.guard_source_identity();
    """)
