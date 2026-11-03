"""Converge the published image and question owners without rewriting history.

Alembic applies the missing parent on upgrades from either published branch.
The merge itself changes only the version graph, never source, image, question
or event data. Readiness requires this one head, not either parent alone.
"""

revision = "0008_merge_image_questions"
down_revision = ("0007_question_snapshot_contract", "0006_image_custody")
branch_labels = None
depends_on = None


def upgrade():
    pass


def downgrade():
    # Test-only downgrade restores the two recorded parent heads. Each owner
    # remains responsible for its own DDL and restrictive dependency checks.
    pass
