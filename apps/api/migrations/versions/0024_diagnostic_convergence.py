"""Join published encounter links and CT/MR custody without rewriting either history."""

revision = "0024_diagnostic_convergence"
down_revision = ("0022_encounter_sources", "0023_dicom_mr_custody")
branch_labels = None
depends_on = None


def upgrade():
    pass


def downgrade():
    pass
