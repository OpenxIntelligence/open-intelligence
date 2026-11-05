"""Join clinical and execution histories without rewriting either predecessor."""

revision = "0024_clinical_execution_join"
down_revision = ("0023_lab_question_followthrough", "0019_composer_runs")
branch_labels = None
depends_on = None


def upgrade():
    pass


def downgrade():
    # The parent revisions own their data and enforce populated downgrade guards.
    pass
