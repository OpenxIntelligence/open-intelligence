"""Converge the original question-provenance and review-return migration heads.

Historic receipts retain their hashes and legacy meanings. New receipts must
explicitly bind the canonical question and queue fingerprint contracts.
"""
from alembic import op
from alembic.util.exc import CommandError
from sqlalchemy import text

revision = "0008_review_convergence"
down_revision = ("0007_question_snapshot_contract", "0007_question_review_returns")
branch_labels = None
depends_on = None


def _insert_guard(canonical: bool) -> str:
    provenance = """
                  AND q.source_snapshot_contract='oi.pg-source-world-model/1'
                  AND NEW.source_snapshot_contract=q.source_snapshot_contract
                  AND NEW.queue_fingerprint_contract='oi.synthetic-source-review-return/2'
                  AND q.purpose=NEW.purpose AND b.purpose=NEW.purpose
    """ if canonical else ""
    return f"""
        CREATE OR REPLACE FUNCTION investigation.guard_review_return_insert()
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
                  {provenance}
            ) THEN RAISE EXCEPTION 'OI-REVIEW-RETURN-SOURCE-BOUNDARY'; END IF;
            RETURN NEW;
        END;
        $oi_review$;
    """


def upgrade():
    conn = op.get_bind()
    existing = conn.execute(text(
        "SELECT 1 FROM information_schema.columns "
        "WHERE table_schema='investigation' AND table_name='question_review_receipts' "
        "AND column_name IN ('source_snapshot_contract','queue_fingerprint_contract') LIMIT 1"
    )).scalar_one_or_none()
    if existing is not None:
        raise CommandError("Existing review provenance requires explicit reconciliation")
    # Constant defaults label all prior rows without UPDATE, preserving their
    # immutable anchors, intent, actor, reason and creation time. The old writer
    # cannot create canonical receipts by omission after this convergence.
    conn.exec_driver_sql("""
        ALTER TABLE investigation.question_review_receipts
            ADD COLUMN source_snapshot_contract text NOT NULL
                DEFAULT 'oi.synthetic-postgres-world-model-sources/1',
            ADD COLUMN queue_fingerprint_contract text NOT NULL
                DEFAULT 'oi.synthetic-source-review-return/1';
        ALTER TABLE investigation.question_review_receipts
            ADD CONSTRAINT oi_review_fingerprint_provenance CHECK (
                (source_snapshot_contract='oi.synthetic-postgres-world-model-sources/1'
                    AND queue_fingerprint_contract='oi.synthetic-source-review-return/1')
                OR (source_snapshot_contract='oi.pg-source-world-model/1'
                    AND queue_fingerprint_contract='oi.synthetic-source-review-return/2')
            );
    """)
    conn.exec_driver_sql(_insert_guard(canonical=True))


def downgrade():
    conn = op.get_bind()
    canonical = conn.execute(text(
        "SELECT 1 FROM investigation.question_review_receipts "
        "WHERE source_snapshot_contract!='oi.synthetic-postgres-world-model-sources/1' "
        "OR queue_fingerprint_contract!='oi.synthetic-source-review-return/1' LIMIT 1"
    )).scalar_one_or_none()
    if canonical is not None:
        raise CommandError("Canonical review history requires explicit reconciliation before downgrade")
    # Restoring the original function and removing only legacy-default columns
    # is safe when no canonical receipt semantics would be discarded.
    conn.exec_driver_sql(_insert_guard(canonical=False))
    conn.exec_driver_sql("""
        ALTER TABLE investigation.question_review_receipts
            DROP COLUMN queue_fingerprint_contract,
            DROP COLUMN source_snapshot_contract;
    """)
