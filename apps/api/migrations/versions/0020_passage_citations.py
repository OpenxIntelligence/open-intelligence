"""Permit canonical citations on immutable reviewed passage questions."""
from alembic import op
from alembic.util.exc import CommandError

revision = "0020_passage_citations"
down_revision = "0019_reviewed_questions"
branch_labels = depends_on = None

def contract(conn, manual):
    allowed = "'oi.pg-source-world-model/1'"
    if manual:
        allowed += ",'oi.reviewed-document-selection/1'"
    conn.exec_driver_sql(f"""ALTER TABLE investigation.question_evidence_links
        DROP CONSTRAINT question_evidence_links_source_snapshot_contract_check,
        ADD CONSTRAINT question_evidence_links_source_snapshot_contract_check
        CHECK(source_snapshot_contract IN ({allowed}))""")

def upgrade():
    conn = op.get_bind()
    contract(conn, True)
    conn.exec_driver_sql("""
        DROP TRIGGER zz_oi_anchor_text_question_required ON investigation.question_evidence_links;
        CREATE TRIGGER zz_oi_anchor_text_question_required BEFORE INSERT ON investigation.question_evidence_links
          FOR EACH ROW WHEN(NEW.source_snapshot_contract<>'oi.reviewed-document-selection/1')
          EXECUTE FUNCTION investigation.require_text_question_target();
        CREATE FUNCTION investigation.guard_passage_citation() RETURNS trigger LANGUAGE plpgsql AS $$
        BEGIN
          IF NOT EXISTS (
            SELECT 1 FROM investigation.reviewed_question_anchors a
            JOIN clinical_source.annotation_revisions r ON r.revision_id=a.manual_revision
            WHERE a.question_id=NEW.question_id AND NOT EXISTS(
              SELECT 1 FROM clinical_source.annotation_revisions n
              WHERE n.source_id=r.source_id AND n.revision>r.revision)
          ) THEN RAISE EXCEPTION 'OI-CITATION-PASSAGE-REASSESSMENT'; END IF;
          RETURN NEW;
        END; $$;
        CREATE TRIGGER oi_passage_citation_guard BEFORE INSERT ON investigation.question_evidence_links
          FOR EACH ROW WHEN(NEW.source_snapshot_contract='oi.reviewed-document-selection/1')
          EXECUTE FUNCTION investigation.guard_passage_citation();
    """)

def downgrade():
    conn = op.get_bind()
    if conn.exec_driver_sql("""SELECT 1 FROM investigation.question_evidence_links
        WHERE source_snapshot_contract='oi.reviewed-document-selection/1' LIMIT 1""").first():
        raise CommandError("Preserve passage citations before downgrade")
    conn.exec_driver_sql("""DROP TRIGGER oi_passage_citation_guard ON investigation.question_evidence_links;
        DROP FUNCTION investigation.guard_passage_citation();
        DROP TRIGGER zz_oi_anchor_text_question_required ON investigation.question_evidence_links;
        CREATE TRIGGER zz_oi_anchor_text_question_required BEFORE INSERT ON investigation.question_evidence_links
          FOR EACH ROW EXECUTE FUNCTION investigation.require_text_question_target();""")
    contract(conn, False)
