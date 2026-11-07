"""Opt-in immutable manual-passage origins for existing Review return receipts.

Retains the canonical source-question and Review receipt owners; source-only
returns have no dependent row. No clinical review/approval or original quote.
"""
from alembic import op
from alembic.util.exc import CommandError
from sqlalchemy import text

revision = "0019_review_manual_dependency"
down_revision = "0018_laboratory_questions"
branch_labels = None
depends_on = None


def upgrade():
    db = op.get_bind()
    if (db.execute(text(
        "SELECT to_regclass('investigation.question_review_manual_dependencies')"
    )).scalar_one() is not None or db.execute(text(
        "SELECT to_regprocedure('investigation.guard_review_manual_dependency()')"
    )).scalar_one() is not None):
        raise CommandError("Existing Review manual origin must be reconciled before upgrade")
    op.execute("""
        CREATE TABLE investigation.question_review_manual_dependencies (
            receipt_id text PRIMARY KEY
                REFERENCES investigation.question_review_receipts(receipt_id),
            question_id text NOT NULL
                REFERENCES investigation.source_questions(question_id),
            revision_id text NOT NULL
                REFERENCES investigation.question_passage_revisions(revision_id),
            patient_id text NOT NULL REFERENCES identity.identity_patients(patient_id),
            case_id text NOT NULL REFERENCES coordination.patient_case_bindings(case_id),
            origin_org text NOT NULL,
            references_sha256 char(64) NOT NULL
                CHECK (references_sha256 ~ '^[0-9a-f]{64}$'),
            created_at timestamptz NOT NULL DEFAULT clock_timestamp()
        );
        CREATE INDEX idx_oi_review_manual_dependency_case
            ON investigation.question_review_manual_dependencies
            (patient_id,case_id,origin_org,question_id,revision_id);

        CREATE FUNCTION investigation.guard_review_manual_dependency()
        RETURNS trigger LANGUAGE plpgsql AS $oi_review_manual$
        BEGIN
            IF NOT EXISTS (
                SELECT 1 FROM investigation.question_review_receipts r
                JOIN investigation.question_passage_revisions p
                  ON p.revision_id=NEW.revision_id
                WHERE r.receipt_id=NEW.receipt_id
                  AND r.question_id=NEW.question_id
                  AND r.patient_id=NEW.patient_id
                  AND r.case_id=NEW.case_id
                  AND r.origin_org=NEW.origin_org
                  AND r.purpose='operations'
                  AND r.action='returned'
                  AND p.question_id=NEW.question_id
                  AND p.patient_id=NEW.patient_id
                  AND p.case_id=NEW.case_id
                  AND p.origin_org=NEW.origin_org
                  AND p.purpose='operations'
                  AND jsonb_array_length(p.references_json)>0
            ) THEN
                RAISE EXCEPTION 'OI-REVIEW-MANUAL-DEPENDENCY-SCOPE';
            END IF;
            RETURN NEW;
        END;
        $oi_review_manual$;

        CREATE TRIGGER oi_review_manual_dependency_scope
            BEFORE INSERT ON investigation.question_review_manual_dependencies
            FOR EACH ROW EXECUTE FUNCTION investigation.guard_review_manual_dependency();
        CREATE TRIGGER oi_review_manual_dependency_immutable_update
            BEFORE UPDATE ON investigation.question_review_manual_dependencies
            FOR EACH ROW EXECUTE FUNCTION identity.reject_registry_history_mutation();
        CREATE TRIGGER oi_review_manual_dependency_immutable_delete
            BEFORE DELETE ON investigation.question_review_manual_dependencies
            FOR EACH ROW EXECUTE FUNCTION identity.reject_registry_history_mutation();
        CREATE TRIGGER oi_review_manual_dependency_immutable_truncate
            BEFORE TRUNCATE ON investigation.question_review_manual_dependencies
            FOR EACH STATEMENT EXECUTE FUNCTION identity.reject_registry_history_mutation();
    """)


def downgrade():
    db = op.get_bind()
    # Keep existing patient/Review history intact; never discard bound
    # provenance just to satisfy an older migration graph.
    if db.execute(text(
        "SELECT EXISTS(SELECT 1 FROM investigation.question_review_manual_dependencies)"
    )).scalar_one():
        raise CommandError("Stored manual Review dependencies require explicit reconciliation")
    op.execute("DROP TABLE investigation.question_review_manual_dependencies")
    op.execute("DROP FUNCTION investigation.guard_review_manual_dependency()")
