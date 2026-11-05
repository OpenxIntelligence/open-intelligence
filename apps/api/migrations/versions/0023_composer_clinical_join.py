"""Join the Composer execution and clinical/laboratory histories without changing data."""

revision = "0023_composer_clinical_join"
down_revision = ("0020_source_event_delivery", "0022_lab_citation_source_scope")
branch_labels = None
depends_on = None


def upgrade():
    pass


def downgrade():
    # Each parent retains its own populated-history downgrade controls.
    pass
