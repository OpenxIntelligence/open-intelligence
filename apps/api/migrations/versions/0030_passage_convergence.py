"""Join passage custody and the connected patient platform without rewriting records."""
from alembic import op

revision = "0030_passage_convergence"
down_revision = ("0029_patient_access", "0020_passage_citations")
branch_labels = depends_on = None


def upgrade():
    # Accept existing populated parent databases as well as a fresh joint upgrade.
    # The passage guard validates its own revision and the common scope guard
    # continues to bind every citation to its patient, question and catalog.
    op.get_bind().exec_driver_sql("""
        DROP TRIGGER IF EXISTS zz_oi_anchor_text_question_required ON investigation.question_evidence_links;
        DROP TRIGGER zz_oi_citation_question_target ON investigation.question_evidence_links;
        CREATE TRIGGER zz_oi_citation_question_target BEFORE INSERT ON investigation.question_evidence_links
          FOR EACH ROW WHEN(NEW.source_snapshot_contract <> 'oi.reviewed-document-selection/1')
          EXECUTE FUNCTION investigation.guard_citation_question_target();
    """)


def downgrade():
    # Each parent owns and guards removal of its persisted state. The compatible
    # target guard remains valid while both parent heads are present.
    pass
