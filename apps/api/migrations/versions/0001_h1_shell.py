"""Establish the H1 migration baseline without introducing clinical tables.

Canonical patient/source/evidence migrations belong to their existing domain
owners. A stamped baseline proves migration plumbing only.
"""

revision = "0001_h1_shell"
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    pass


def downgrade():
    pass
