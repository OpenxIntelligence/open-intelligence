"""Join published image and authored-report histories without changing their data.

Each parent retains its migrations, canonical owners, immutable records and
rights. Upgrading from either published head installs its missing sibling;
this final joining node changes only Alembic version bookkeeping.
"""

revision = "0012_image_report_convergence"
down_revision = ("0011_evidence_convergence", "0011_image_evidence_merge")
branch_labels = None
depends_on = None


def upgrade():
    pass


def downgrade():
    # Restore both published heads; owner-specific downgrade guards still apply.
    pass
