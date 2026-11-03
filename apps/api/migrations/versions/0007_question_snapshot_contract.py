"""Record the fingerprint contract without rewriting immutable question anchors."""

from alembic import op
from alembic.util.exc import CommandError
from sqlalchemy import text

revision = "0007_question_snapshot_contract"
down_revision = "0006_source_questions"
branch_labels = None
depends_on = None


def upgrade():
    conn = op.get_bind()
    existing = conn.execute(text(
        "SELECT 1 FROM information_schema.columns "
        "WHERE table_schema='investigation' AND table_name='source_questions' "
        "AND column_name='source_snapshot_contract'"
    )).scalar_one_or_none()
    if existing is not None:
        raise CommandError("Existing question snapshot provenance requires explicit reconciliation")
    # A constant legacy default labels existing rows without UPDATE, preserving
    # the immutable-row guards and original fingerprints. Older writers also
    # remain legacy; the canonical owner must explicitly supply its contract.
    conn.exec_driver_sql("""
        ALTER TABLE investigation.source_questions
            ADD COLUMN source_snapshot_contract text NOT NULL
            DEFAULT 'oi.synthetic-postgres-world-model-sources/1';
        ALTER TABLE investigation.source_questions
            ADD CONSTRAINT oi_question_snapshot_contract CHECK (
                source_snapshot_contract IN (
                    'oi.synthetic-postgres-world-model-sources/1',
                    'oi.pg-source-world-model/1'
                )
            );
    """)


def downgrade():
    op.get_bind().exec_driver_sql(
        "ALTER TABLE investigation.source_questions DROP COLUMN source_snapshot_contract"
    )
