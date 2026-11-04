"""Join image custody and question evidence without changing either owner's data.

Each published parent applies its missing sibling history before reaching this
single required head. This merge performs no DDL or source/history rewrites.
"""

revision = "0011_image_evidence_merge"
down_revision = ("0009_image_review_merge", "0010_question_evidence")
branch_labels = None
depends_on = None


def upgrade():
    pass


def downgrade():
    # Restore both published heads; their original ownership, immutability and
    # restrictive provenance/history downgrade guards remain authoritative.
    pass
