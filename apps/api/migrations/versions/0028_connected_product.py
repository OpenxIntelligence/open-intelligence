"""Join diagnostic encounter links with the shared clinical execution foundation.

Both published histories remain unchanged. This join introduces no domain state.
"""

revision = "0028_connected_product"
down_revision = ("0027_source_event_purpose", "0022_encounter_sources")
branch_labels = None
depends_on = None


def upgrade():
    pass


def downgrade():
    pass
