"""Join the published laboratory and optional manual-task histories without DDL."""

revision = "0017_lab_manual_convergence"
down_revision = (
    "0016_fhir_laboratory_sources",
    "0016_manual_task_dependency",
)
branch_labels = None
depends_on = None


def upgrade():
    pass


def downgrade():
    # Only the join is removed. Each owner retains its populated-history guard.
    pass
