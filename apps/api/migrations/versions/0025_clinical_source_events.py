"""Join the clinical core with the source-journal outbox and its Composer consumer."""

revision = "0025_clinical_source_events"
down_revision = ("0024_clinical_execution_join", "0020_source_event_delivery")
branch_labels = None
depends_on = None


def upgrade():
    pass


def downgrade():
    # The source and clinical predecessors enforce their own populated-history guards.
    pass
