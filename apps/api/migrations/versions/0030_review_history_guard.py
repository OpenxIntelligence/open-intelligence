"""Prevent whole-table removal of immutable verification-return receipts."""
from alembic import op
from alembic.util.exc import CommandError

revision = "0030_review_history_guard"
down_revision = "0029_episode_history_guard"
branch_labels = None
depends_on = None


def _lock_history(conn):
    # Match the writer's binding-before-receipt order. Do not acquire a journal
    # lock here: this DDL neither changes nor reconstructs journal history.
    conn.exec_driver_sql("LOCK TABLE coordination.patient_case_bindings IN EXCLUSIVE MODE")
    conn.exec_driver_sql("LOCK TABLE investigation.question_review_receipts IN SHARE ROW EXCLUSIVE MODE")


def upgrade():
    conn = op.get_bind()
    _lock_history(conn)
    conn.exec_driver_sql("""
        CREATE TRIGGER oi_review_receipt_no_truncate
        BEFORE TRUNCATE ON investigation.question_review_receipts FOR EACH STATEMENT
        EXECUTE FUNCTION identity.reject_registry_history_mutation()
    """)


def downgrade():
    conn = op.get_bind()
    _lock_history(conn)
    if conn.exec_driver_sql("SELECT EXISTS (SELECT 1 FROM investigation.question_review_receipts)").scalar_one():
        raise CommandError("Populated review receipts require explicit preservation")
    conn.exec_driver_sql("DROP TRIGGER oi_review_receipt_no_truncate ON investigation.question_review_receipts")
