"""Additional institutional identities owned by the existing case binding."""
from alembic import op
from alembic.util.exc import CommandError

revision = "0030_case_source_identities"
down_revision = "0029_patient_access"
branch_labels = None
depends_on = None


def upgrade():
    op.get_bind().exec_driver_sql("""
    CREATE TABLE coordination.case_source_identities (
        identity_id text PRIMARY KEY CHECK (identity_id ~ '^IDENT-[0-9A-F]{32}$'),
        case_id text NOT NULL REFERENCES coordination.patient_case_bindings(case_id),
        source_organization text NOT NULL CHECK (char_length(source_organization) BETWEEN 3 AND 128),
        source_system text NOT NULL CHECK (char_length(source_system) BETWEEN 3 AND 128),
        source_subject_ref text NOT NULL CHECK (char_length(source_subject_ref) BETWEEN 3 AND 128),
        review_ref text NOT NULL,
        created_by text NOT NULL,
        purpose text NOT NULL CHECK (purpose IN ('operations','research')),
        created_at timestamptz NOT NULL DEFAULT clock_timestamp(),
        status text NOT NULL CHECK (status IN ('linked','quarantined')),
        primary_identity boolean NOT NULL DEFAULT false,
        request_key text NOT NULL,
        request_digest text NOT NULL,
        UNIQUE (case_id,request_key),
        CHECK (NOT primary_identity OR status='linked')
    );
    CREATE UNIQUE INDEX case_source_identity_qualified ON coordination.case_source_identities
        (source_organization,source_system,source_subject_ref) WHERE status='linked';
    CREATE UNIQUE INDEX case_source_identity_primary ON coordination.case_source_identities
        (case_id) WHERE primary_identity;
    INSERT INTO coordination.case_source_identities
        (identity_id,case_id,source_organization,source_system,source_subject_ref,
         review_ref,created_by,purpose,created_at,status,primary_identity,request_key,request_digest)
    SELECT 'IDENT-' || upper(md5(case_id)),case_id,source_organization,source_system,source_subject_ref,
        review_ref,created_by,purpose,created_at,'linked',true,'primary','primary'
        FROM coordination.patient_case_bindings;
    CREATE FUNCTION coordination.copy_case_source_identity() RETURNS trigger LANGUAGE plpgsql AS $$
    BEGIN
        INSERT INTO coordination.case_source_identities
            (identity_id,case_id,source_organization,source_system,source_subject_ref,
             review_ref,created_by,purpose,created_at,status,primary_identity,request_key,request_digest)
        VALUES ('IDENT-' || upper(md5(NEW.case_id)),NEW.case_id,NEW.source_organization,
            NEW.source_system,NEW.source_subject_ref,NEW.review_ref,NEW.created_by,NEW.purpose,
            NEW.created_at,'linked',true,'primary','primary');
        RETURN NEW;
    END; $$;
    CREATE TRIGGER case_source_identity_primary_insert AFTER INSERT ON coordination.patient_case_bindings
        FOR EACH ROW EXECUTE FUNCTION coordination.copy_case_source_identity();
    CREATE FUNCTION coordination.guard_source_identity_case() RETURNS trigger LANGUAGE plpgsql AS $$
    BEGIN
        IF NOT EXISTS (SELECT 1 FROM coordination.patient_case_bindings c
            WHERE c.case_id=NEW.case_id AND c.purpose=NEW.purpose AND c.status='active'
            AND (NOT NEW.primary_identity OR (c.source_organization,c.source_system,c.source_subject_ref,
                c.review_ref,c.created_by)=(NEW.source_organization,NEW.source_system,NEW.source_subject_ref,
                NEW.review_ref,NEW.created_by))) THEN
            RAISE EXCEPTION 'OI-SOURCE-IDENTITY-CASE';
        END IF;
        RETURN NEW;
    END; $$;
    CREATE TRIGGER case_source_identity_case BEFORE INSERT ON coordination.case_source_identities
        FOR EACH ROW EXECUTE FUNCTION coordination.guard_source_identity_case();
    CREATE TRIGGER case_source_identity_immutable BEFORE UPDATE OR DELETE ON coordination.case_source_identities
        FOR EACH ROW EXECUTE FUNCTION identity.reject_registry_history_mutation();
    CREATE TRIGGER case_source_identity_no_truncate BEFORE TRUNCATE ON coordination.case_source_identities
        FOR EACH STATEMENT EXECUTE FUNCTION identity.reject_registry_history_mutation();
    """)


def downgrade():
    db = op.get_bind()
    if db.exec_driver_sql("SELECT EXISTS(SELECT 1 FROM coordination.case_source_identities WHERE NOT primary_identity)").scalar_one():
        raise CommandError("Additional source identity history must be retained; populated downgrade refused")
    db.exec_driver_sql("""
        DROP TRIGGER case_source_identity_primary_insert ON coordination.patient_case_bindings;
        DROP FUNCTION coordination.copy_case_source_identity();
        DROP TABLE coordination.case_source_identities;
        DROP FUNCTION coordination.guard_source_identity_case();
    """)
