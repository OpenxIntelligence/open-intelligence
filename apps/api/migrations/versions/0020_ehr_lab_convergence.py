"""Join the EHR and laboratory citation revisions without changing stored records."""

revision = "0020_ehr_lab_convergence"
down_revision = ("0019_ehr_encounters", "0019_laboratory_citations")
branch_labels = None
depends_on = None


def upgrade():
    pass


def downgrade():
    # The parent migrations own their tables and guard removal of populated data.
    pass
