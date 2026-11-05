"""Converge metadata/follow-through and authored evidence without rewriting either.

Both independently published histories retain their existing storage and rights
contracts. This merge only establishes the application's single readiness head;
it does not copy records, invent citation-to-passage links or confer new rights.
"""

revision = "0011_evidence_convergence"
down_revision = ("0010_question_evidence", "0010_authored_evidence_origin")
branch_labels = None
depends_on = None


def upgrade():
    pass


def downgrade():
    pass
