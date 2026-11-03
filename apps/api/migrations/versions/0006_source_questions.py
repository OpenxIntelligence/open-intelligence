"""Port the original first-party question intake contract to canonical PG16.

This is the ONE H1 question owner, not an approval/review queue. Source-custody
remains clinical_source, patient identity remains identity. All persisted
references are immutable and questions are fictional and unreviewed.
"""
from alembic import op
from alembic.util.exc import CommandError
from sqlalchemy import text

revision = "0006_source_questions"
down_revision = "0005_source_versions"
branch_labels = None
depends_on = None


def upgrade():
    conn = op.get_bind()
    objects = (
        ("investigation", "source_questions"),
        ("investigation", "guard_question_insert"),
    )
    for schema, name in objects:
        existing = conn.execute(text(
            "SELECT 1 FROM pg_class c JOIN pg_namespace n ON n.oid=c.relnamespace "
            "WHERE n.nspname=:schema AND c.relname=:name UNION ALL "
            "SELECT 1 FROM pg_proc p JOIN pg_namespace n ON n.oid=p.pronamespace "
            "WHERE n.nspname=:schema AND p.proname=:name LIMIT 1"
        ), {"schema": schema, "name": name}).scalar_one_or_none()
        if existing is not None:
            raise CommandError("Existing investigation owner requires explicit reconciliation")

    conn.exec_driver_sql("""
        CREATE SCHEMA IF NOT EXISTS investigation;
        CREATE TABLE investigation.source_questions (
            question_id text PRIMARY KEY
                CHECK (question_id ~ '^QUESTION-[0-9A-F]{32}$'),
            patient_id text NOT NULL REFERENCES identity.identity_patients(patient_id),
            case_id text NOT NULL REFERENCES coordination.patient_case_bindings(case_id),
            origin_org text NOT NULL,
            request_key text NOT NULL
                CHECK (char_length(request_key) BETWEEN 3 AND 128),
            intent_sha256 char(64) NOT NULL
                CHECK (intent_sha256 ~ '^[0-9a-f]{64}$'),
            actor text NOT NULL,
            purpose text NOT NULL CHECK (purpose='operations'),
            question text NOT NULL
                CHECK (char_length(question) BETWEEN 8 AND 500
                       AND question=btrim(question)
                       AND strpos(question,chr(10))=0
                       AND strpos(question,chr(13))=0),
            source_id text NOT NULL,
            source_line integer NOT NULL CHECK (source_line BETWEEN 1 AND 10000),
            source_sha256 char(64) NOT NULL
                CHECK (source_sha256 ~ '^[0-9a-f]{64}$'),
            source_version integer NOT NULL CHECK (source_version>=1),
            source_snapshot_sha256 char(64) NOT NULL
                CHECK (source_snapshot_sha256 ~ '^[0-9a-f]{64}$'),
            preflight_sha256 char(64) NOT NULL
                CHECK (preflight_sha256 ~ '^[0-9a-f]{64}$'),
            created_at timestamptz NOT NULL DEFAULT now(),
            UNIQUE (patient_id,request_key),
            FOREIGN KEY (source_id,source_line)
                REFERENCES clinical_source.assertions(source_id,source_line)
        );
        CREATE INDEX idx_oi_questions_patient_case
          ON investigation.source_questions(patient_id,case_id,created_at,question_id);

        CREATE FUNCTION investigation.guard_question_insert() RETURNS trigger
        LANGUAGE plpgsql AS $oi_question$
        BEGIN
            IF NOT EXISTS (
                SELECT 1 FROM identity.identity_patients p
                JOIN coordination.patient_case_bindings b
                  ON b.patient_id=p.patient_id
                WHERE p.patient_id=NEW.patient_id
                  AND p.origin_org=NEW.origin_org AND p.status='active'
                  AND b.case_id=NEW.case_id AND b.origin_org=NEW.origin_org
                  AND b.status='active'
            ) THEN RAISE EXCEPTION 'OI-QUESTION-IDENTITY-BOUNDARY'; END IF;
            IF NOT EXISTS (
                SELECT 1 FROM clinical_source.source_versions s
                JOIN clinical_source.assertions a
                  ON a.source_id=s.source_id
                WHERE s.source_id=NEW.source_id
                  AND s.case_id=NEW.case_id AND s.state='current'
                  AND s.version=NEW.source_version
                  AND s.sha256=NEW.source_sha256
                  AND a.source_line=NEW.source_line
            ) THEN RAISE EXCEPTION 'OI-QUESTION-SOURCE-BOUNDARY'; END IF;
            RETURN NEW;
        END;
        $oi_question$;
        CREATE TRIGGER oi_question_insert_guard
          BEFORE INSERT ON investigation.source_questions
          FOR EACH ROW EXECUTE FUNCTION investigation.guard_question_insert();
        CREATE TRIGGER oi_question_update_guard
          BEFORE UPDATE ON investigation.source_questions
          FOR EACH ROW EXECUTE FUNCTION identity.reject_registry_history_mutation();
        CREATE TRIGGER oi_question_delete_guard
          BEFORE DELETE ON investigation.source_questions
          FOR EACH ROW EXECUTE FUNCTION identity.reject_registry_history_mutation();
    """)


def downgrade():
    conn = op.get_bind()
    for statement in (
        "DROP TABLE investigation.source_questions",
        "DROP FUNCTION investigation.guard_question_insert()",
    ):
        conn.exec_driver_sql(statement)
    # The namespace is deliberately retained, no unreviewed CASCADE.
