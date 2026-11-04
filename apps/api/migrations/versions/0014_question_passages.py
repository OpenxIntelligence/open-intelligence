"""Immutable manual context children; preserve all published source history."""
from alembic import op
from alembic.util.exc import CommandError
from sqlalchemy import text

revision='0014_question_passages'
down_revision='0013_document_image_convergence'
branch_labels=None
depends_on=None


def upgrade():
    connection=op.get_bind()
    if connection.execute(text("SELECT to_regclass('investigation.question_passage_revisions')")).scalar_one() is not None:
        raise CommandError('Existing question passage owner requires reconciliation')
    op.execute("""
        CREATE TABLE investigation.question_passage_revisions (
            revision_id text PRIMARY KEY CHECK (revision_id ~ '^PASSAGES-[A-F0-9]{32}$'),
            revision integer NOT NULL CHECK (revision BETWEEN 1 AND 64),
            patient_id text NOT NULL REFERENCES identity.identity_patients(patient_id),
            case_id text NOT NULL REFERENCES coordination.patient_case_bindings(case_id),
            origin_org text NOT NULL,
            question_id text NOT NULL REFERENCES investigation.source_questions(question_id),
            request_key text NOT NULL,
            intent_sha256 text NOT NULL CHECK (intent_sha256 ~ '^[a-f0-9]{64}$'),
            references_json jsonb NOT NULL CHECK (jsonb_typeof(references_json)='array' AND jsonb_array_length(references_json)<=20),
            command_json jsonb NOT NULL CHECK (jsonb_typeof(command_json)='object'),
            actor text NOT NULL,
            purpose text NOT NULL CHECK (purpose='operations'),
            created_at timestamptz NOT NULL DEFAULT clock_timestamp(),
            UNIQUE(question_id,revision), UNIQUE(question_id,request_key)
        );
        CREATE FUNCTION investigation.guard_question_passage_revision() RETURNS trigger LANGUAGE plpgsql AS $$
        BEGIN
            IF NOT EXISTS (SELECT 1 FROM investigation.source_questions q WHERE q.question_id=NEW.question_id
                AND q.patient_id=NEW.patient_id AND q.case_id=NEW.case_id AND q.origin_org=NEW.origin_org)
                OR NEW.revision != (SELECT coalesce(max(revision),0)+1 FROM investigation.question_passage_revisions WHERE question_id=NEW.question_id)
                OR EXISTS (SELECT 1 FROM jsonb_array_elements(NEW.references_json) r WHERE NOT EXISTS (
                    SELECT 1 FROM clinical_source.annotation_revisions a
                    JOIN clinical_source.source_versions s ON s.source_id=a.source_id
                    WHERE a.source_id=r->>'source_id' AND a.revision_id=r->>'annotation_revision_id' AND s.case_id=NEW.case_id
                )) THEN RAISE EXCEPTION 'OI-QUESTION-PASSAGE-BOUNDARY'; END IF;
            RETURN NEW;
        END; $$;
        CREATE TRIGGER oi_passage_scope BEFORE INSERT ON investigation.question_passage_revisions
            FOR EACH ROW EXECUTE FUNCTION investigation.guard_case_evidence_scope();
        CREATE TRIGGER oi_passage_insert BEFORE INSERT ON investigation.question_passage_revisions
            FOR EACH ROW EXECUTE FUNCTION investigation.guard_question_passage_revision();
        CREATE TRIGGER oi_passage_update BEFORE UPDATE ON investigation.question_passage_revisions
            FOR EACH ROW EXECUTE FUNCTION identity.reject_registry_history_mutation();
        CREATE TRIGGER oi_passage_delete BEFORE DELETE ON investigation.question_passage_revisions
            FOR EACH ROW EXECUTE FUNCTION identity.reject_registry_history_mutation();
    """)


def downgrade():
    if op.get_bind().execute(text('SELECT EXISTS(SELECT 1 FROM investigation.question_passage_revisions)')).scalar_one():
        raise CommandError('Preserved question passage history requires explicit reconciliation before downgrade')
    op.execute('DROP TABLE investigation.question_passage_revisions')
    op.execute('DROP FUNCTION investigation.guard_question_passage_revision()')
