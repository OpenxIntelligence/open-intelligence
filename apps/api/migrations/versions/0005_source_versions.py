"""Port the original CaseStore source-version and assertion contract to PG16.

The one H1 clinical_source source owner stores original synthetic report bytes,
source-version history and exact authored finding lines. Patient identity remains
in identity.identity_patients, cases in coordination.patient_case_bindings. No
new patient registry, diagnostic inference, authorization or PHI acceptance.
"""
from alembic import op
from alembic.util.exc import CommandError
from sqlalchemy import text

revision = "0005_source_versions"
down_revision = "0004_case_binding"
branch_labels = None
depends_on = None


def upgrade():
    conn = op.get_bind()
    # Never silently adopt a preexisting table lacking immutable-source guards.
    for name in ("source_versions", "assertions", "quarantine"):
        existing = conn.execute(text(
            "SELECT c.relname FROM pg_class c JOIN pg_namespace n ON c.relnamespace=n.oid "
            "WHERE n.nspname='clinical_source' AND c.relname=:name"
        ), {"name": name}).scalar_one_or_none()
        if existing is not None:
            raise CommandError("Existing original-source objects need explicit owner reconciliation")
    conn.exec_driver_sql("""
        CREATE SCHEMA IF NOT EXISTS clinical_source;
        CREATE TABLE clinical_source.source_versions (
            source_id text PRIMARY KEY CHECK (source_id ~ '^SRC-[0-9A-F]{32}$'),
            case_id text NOT NULL REFERENCES coordination.patient_case_bindings(case_id),
            document_id text NOT NULL CHECK (document_id ~ '^[A-Z][A-Z0-9-]{1,39}$'),
            version integer NOT NULL CHECK (version >= 1),
            sha256 char(64) NOT NULL CHECK (sha256 ~ '^[0-9a-f]{64}$'),
            raw bytea NOT NULL CHECK (octet_length(raw) BETWEEN 1 AND 65536),
            kind text NOT NULL CHECK (kind IN ('clinical','pathology','laboratory','imaging','molecular','other')),
            event_date date NOT NULL,
            issued_at date NOT NULL,
            received_at timestamptz NOT NULL DEFAULT now(),
            specimen_id text,
            state text NOT NULL CHECK (state IN ('current','superseded')),
            supersedes_id text REFERENCES clinical_source.source_versions(source_id),
            CHECK ((version=1 AND supersedes_id IS NULL) OR (version>1 AND supersedes_id IS NOT NULL)),
            UNIQUE(case_id,document_id,version),
            UNIQUE(case_id,document_id,sha256)
        );
        CREATE UNIQUE INDEX idx_oi_source_one_current
            ON clinical_source.source_versions(case_id,document_id) WHERE state='current';
        CREATE INDEX idx_oi_source_case ON clinical_source.source_versions(case_id,document_id,version);
        CREATE TABLE clinical_source.assertions (
            assertion_id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
            source_id text NOT NULL REFERENCES clinical_source.source_versions(source_id),
            finding_key text NOT NULL CHECK (finding_key ~ '^[a-z][a-z0-9_-]{0,59}$'),
            certainty text NOT NULL CHECK (certainty IN ('reported','negative','pending',
                            'indeterminate','not-reported','not-assessed','conflicting')),
            quote text NOT NULL CHECK (char_length(quote) BETWEEN 1 AND 1200),
            source_line integer NOT NULL CHECK (source_line >= 1),
            UNIQUE(source_id,finding_key),
            UNIQUE(source_id,source_line)
        );
        CREATE TABLE clinical_source.quarantine (
            quarantine_id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
            target_case_id text NOT NULL REFERENCES coordination.patient_case_bindings(case_id),
            declared_case_id text NOT NULL,
            sha256 char(64) NOT NULL CHECK (sha256 ~ '^[0-9a-f]{64}$'),
            raw bytea NOT NULL CHECK (octet_length(raw) BETWEEN 1 AND 65536),
            reason text NOT NULL CHECK (reason='case_mismatch'),
            received_at timestamptz NOT NULL DEFAULT now(),
            UNIQUE(target_case_id,sha256)
        );
        CREATE FUNCTION clinical_source.guard_version_history() RETURNS trigger
        LANGUAGE plpgsql AS $oi_source_guard$
        BEGIN
            IF (OLD.source_id,OLD.case_id,OLD.document_id,OLD.version,OLD.sha256,OLD.raw,
                OLD.kind,OLD.event_date,OLD.issued_at,OLD.received_at,OLD.specimen_id,OLD.supersedes_id)
               IS DISTINCT FROM
               (NEW.source_id,NEW.case_id,NEW.document_id,NEW.version,NEW.sha256,NEW.raw,
                NEW.kind,NEW.event_date,NEW.issued_at,NEW.received_at,NEW.specimen_id,NEW.supersedes_id)
            THEN RAISE EXCEPTION 'OI-ORIGINAL-SOURCE-IMMUTABLE'; END IF;
            IF OLD.state!='current' OR NEW.state!='superseded' THEN
                RAISE EXCEPTION 'OI-ORIGINAL-SOURCE-STATE'; END IF;
            RETURN NEW;
        END;
        $oi_source_guard$;
        CREATE TRIGGER oi_source_update_guard BEFORE UPDATE ON clinical_source.source_versions
            FOR EACH ROW EXECUTE FUNCTION clinical_source.guard_version_history();
        CREATE TRIGGER oi_source_delete_guard BEFORE DELETE ON clinical_source.source_versions
            FOR EACH ROW EXECUTE FUNCTION identity.reject_registry_history_mutation();
        CREATE TRIGGER oi_assertion_update_guard BEFORE UPDATE ON clinical_source.assertions
            FOR EACH ROW EXECUTE FUNCTION identity.reject_registry_history_mutation();
        CREATE TRIGGER oi_assertion_delete_guard BEFORE DELETE ON clinical_source.assertions
            FOR EACH ROW EXECUTE FUNCTION identity.reject_registry_history_mutation();
        CREATE TRIGGER oi_quarantine_update_guard BEFORE UPDATE ON clinical_source.quarantine
            FOR EACH ROW EXECUTE FUNCTION identity.reject_registry_history_mutation();
        CREATE TRIGGER oi_quarantine_delete_guard BEFORE DELETE ON clinical_source.quarantine
            FOR EACH ROW EXECUTE FUNCTION identity.reject_registry_history_mutation();
    """)


def downgrade():
    conn = op.get_bind()
    for statement in (
        "DROP TABLE clinical_source.assertions",
        "DROP TABLE clinical_source.quarantine",
        "DROP TABLE clinical_source.source_versions",
        "DROP FUNCTION clinical_source.guard_version_history()",
    ):
        conn.exec_driver_sql(statement)
    # Leave the namespace; do not CASCADE into an unreviewed external dependency.
