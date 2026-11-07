"""Append-only patient access declarations and revocations."""
from alembic import op
from alembic.util.exc import CommandError

revision = "0029_patient_access"
down_revision = "0028_connected_product"
branch_labels = None
depends_on = None


def upgrade():
    op.get_bind().exec_driver_sql("""
    CREATE TABLE identity.patient_access_grants (
        grant_id text PRIMARY KEY CHECK (grant_id ~ '^GRANT-[0-9A-F]{32}$'),
        patient_id text NOT NULL REFERENCES identity.identity_patients(patient_id),
        actor text NOT NULL CHECK (actor ~ '^[A-Za-z0-9][A-Za-z0-9_.:-]{2,127}$'),
        purpose text NOT NULL CHECK (purpose IN ('operations','research')),
        actions text[] NOT NULL CHECK (cardinality(actions) BETWEEN 1 AND 64),
        relationship text NOT NULL CHECK (relationship IN ('patient','guardian','animal_owner','care_team','research_delegate')),
        authority_ref text NOT NULL CHECK (authority_ref ~ '^[A-Za-z0-9][A-Za-z0-9_.:-]{2,127}$'),
        granted_by text NOT NULL,
        expires_at timestamptz NOT NULL,
        created_at timestamptz NOT NULL DEFAULT clock_timestamp(),
        request_key text NOT NULL,
        request_digest char(64) NOT NULL,
        UNIQUE (patient_id,request_key),
        CHECK (expires_at > created_at)
    );
    CREATE INDEX patient_access_scope ON identity.patient_access_grants(patient_id,actor,purpose);
    CREATE TABLE identity.patient_access_revocations (
        grant_id text PRIMARY KEY REFERENCES identity.patient_access_grants(grant_id),
        revoked_by text NOT NULL,
        authority_ref text NOT NULL CHECK (authority_ref ~ '^[A-Za-z0-9][A-Za-z0-9_.:-]{2,127}$'),
        revoked_at timestamptz NOT NULL DEFAULT clock_timestamp(),
        request_key text NOT NULL,
        request_digest char(64) NOT NULL
    );
    CREATE TRIGGER patient_access_grant_immutable BEFORE UPDATE OR DELETE ON identity.patient_access_grants
        FOR EACH ROW EXECUTE FUNCTION identity.reject_registry_history_mutation();
    CREATE TRIGGER patient_access_grant_no_truncate BEFORE TRUNCATE ON identity.patient_access_grants
        FOR EACH STATEMENT EXECUTE FUNCTION identity.reject_registry_history_mutation();
    CREATE TRIGGER patient_access_revocation_immutable BEFORE UPDATE OR DELETE ON identity.patient_access_revocations
        FOR EACH ROW EXECUTE FUNCTION identity.reject_registry_history_mutation();
    CREATE TRIGGER patient_access_revocation_no_truncate BEFORE TRUNCATE ON identity.patient_access_revocations
        FOR EACH STATEMENT EXECUTE FUNCTION identity.reject_registry_history_mutation();
    """)


def downgrade():
    db = op.get_bind()
    if db.exec_driver_sql("SELECT EXISTS(SELECT 1 FROM identity.patient_access_grants)").scalar_one():
        raise CommandError("Patient access history must be retained; populated downgrade refused")
    db.exec_driver_sql("DROP TABLE identity.patient_access_revocations; DROP TABLE identity.patient_access_grants;")
