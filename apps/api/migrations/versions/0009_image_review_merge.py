"""Join the published image/question and review owners without changing their data.

Upgrading either published parent applies its missing sibling history before
recording this single required head. The merge itself performs no DDL and does
not rewrite source, question, image, return or domain-event history.
"""

revision = "0009_image_review_merge"
down_revision = ("0008_merge_image_questions", "0008_review_convergence")
branch_labels = None
depends_on = None


def upgrade():
    pass


def downgrade():
    # Restore both published heads. Their owners retain all DDL, immutable
    # history and restrictive downgrade checks, including review provenance.
    pass
