"""Converge clinical execution, source delivery and encounter ownership histories."""

revision = "0026_integrated_core"
down_revision = (
    "0025_clinical_source_events",
    "0023_composer_clinical_join",
    "0023_ehr_lab_ownership_join",
)
branch_labels = None
depends_on = None


def upgrade():
    pass


def downgrade():
    # Each predecessor owns its data and its populated-downgrade protections.
    pass
