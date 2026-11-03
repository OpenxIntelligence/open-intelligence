"""Port the existing first-party derived review-queue/immutable receipt pattern to H1.

This is the canonical PostgreSQL QUESTION review-return receipt owner, not
another patient/source/question store and not a clinical approval workflow.
The inbox is always projected from investigation.source_questions.
Only nonterminal 'returned' receipts can be written. This migration cannot
introduce a professional review signature, approval or clinical decision.
"""
from alembic import op
from alembic.util.exc import CommandError
from sqlalchemy import text

revision = "0007_question_review_returns"
down_revision = "0006_source_questions"
branch_labels = None
depends_on = None


def upgrade():
    conn = op.get_bind()
    for name in ("question_review_receipts", "guard_review_return_insert"):
        exists = conn.execute(text(
            "SELECT 1 FROM pg_class c JOIN pg_namespace n ON n.oid=c.relnamespace "
            "WHERE n.nspname='investigation' AND c.relname=:name "
            "UNION ALL SELECT 1 FROM pg_proc p "
            "JOIN pg_namespace n ON n.oid=p.pronamespace "
            "WHERE n.nspname='investigation' AND p.proname=:name LIMIT 1"
        ), {"name": name}).scalar_one_or_none()
        if exists is not None:
            raise CommandError("Existing review owner requires explicit reconciliation")

    conn.exec_driver_sql("""
        CREATE TABLE investigation.question_review_receipts (
            receipt_id text PRIMARY KEY CHECK (receipt_id ~ '^REVIEW-[0-9A-F]{32}$'),
            question_id text NOT NULL REFERENCES investigation.source_questions(question_id),
            patient_id text NOT NULL REFERENCES identity.identity_patients(patient_id),
            case_id text NOT NULL REFERENCES coordination.patient_case_bindings(case_id),
            origin_org text NOT NULL,
            request_key text NOT NULL CHECK (char_length(request_key) BETWEEN 3 AND 128),
            intent_sha256 char(64) NOT NULL CHECK (intent_sha256 ~ '^[0-9a-f]{64}$'),
            queue_fingerprint char(64) NOT NULL
                CHECK (queue_fingerprint ~ '^[0-9a-f]{64}$'),
            source_snapshot_sha256 char(64) NOT NULL
                CHECK (source_snapshot_sha256 ~ '^[0-9a-f]{64}$'),
            actor text NOT NULL,
            purpose text NOT NULL CHECK (purpose='operations'),
            action text NOT NULL DEFAULT 'returned' CHECK (action='returned'),
            reason text NOT NULL
                CHECK (char_length(reason) BETWEEN 10 AND 600
                  AND reason=btrim(reason)
                  AND strpos(reason,chr(10))=0
                  AND strpos(reason,chr(13))=0),
            created_at timestamptz NOT NULL DEFAULT now(),
            UNIQUE (patient_id,request_key)
        );
        CREATE INDEX idx_oi_review_return_case_question
            ON investigation.question_review_receipts
            (patient_id,case_id,question_id,created_at,receipt_id);

        CREATE FUNCTION investigation.guard_review_return_insert()
        RETURNS trigger LANGUAGE plpgsql AS $oi_review$
        BEGIN
            IF NOT EXISTS (
                SELECT 1 FROM investigation.source_questions q
                JOIN identity.identity_patients p ON p.patient_id=q.patient_id
                JOIN coordination.patient_case_bindings b
                    ON b.case_id=q.case_id AND b.patient_id=q.patient_id
                JOIN clinical_source.source_versions s
                    ON s.source_id=q.source_id AND s.case_id=q.case_id
                WHERE q.question_id=NEW.question_id
                  AND q.patient_id=NEW.patient_id AND q.case_id=NEW.case_id
                  AND q.origin_org=NEW.origin_org
                  AND q.source_snapshot_sha256=NEW.source_snapshot_sha256
                  AND p.origin_org=NEW.origin_org AND p.status='active'
                  AND b.origin_org=NEW.origin_org AND b.status='active'
                  AND s.state='current' AND s.sha256=q.source_sha256
                  AND s.version=q.source_version
            ) THEN RAISE EXCEPTION 'OI-REVIEW-RETURN-SOURCE-BOUNDARY'; END IF;
            RETURN NEW;
        END;
        $oi_review$;
        CREATE TRIGGER oi_review_return_insert_guard
            BEFORE INSERT ON investigation.question_review_receipts
            FOR EACH ROW EXECUTE FUNCTION investigation.guard_review_return_insert();
        CREATE TRIGGER oi_review_return_immutable_update
            BEFORE UPDATE ON investigation.question_review_receipts
            FOR EACH ROW EXECUTE FUNCTION identity.reject_registry_history_mutation();
        CREATE TRIGGER oi_review_return_immutable_delete
            BEFORE DELETE ON investigation.question_review_receipts
            FOR EACH ROW EXECUTE FUNCTION identity.reject_registry_history_mutation();
    """)


def downgrade():
    conn = op.get_bind()
    conn.exec_driver_sql("DROP TABLE investigation.question_review_receipts")
    conn.exec_driver_sql("DROP FUNCTION investigation.guard_review_return_insert()")
    # Preserve the canonical question schema and every other source owner.
