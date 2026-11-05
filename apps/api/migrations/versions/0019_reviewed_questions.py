"""Bind manually selected questions to immutable source review revisions."""
from alembic import op
from alembic.util.exc import CommandError

revision = "0019_reviewed_questions"
down_revision = "0018_laboratory_questions"
branch_labels = depends_on = None


def guards(conn, manual):
    condition = "NEW.source_line IS NULL" + (" AND NEW.source_snapshot_contract <> 'oi.reviewed-document-selection/1'" if manual else "")
    conn.exec_driver_sql(f"""
        DROP TRIGGER oi_lab_question_insert_guard ON investigation.source_questions;
        DROP TRIGGER oi_lab_question_requires_child ON investigation.source_questions;
        CREATE TRIGGER oi_lab_question_insert_guard BEFORE INSERT ON investigation.source_questions
          FOR EACH ROW WHEN ({condition}) EXECUTE FUNCTION investigation.guard_lab_question_insert();
        CREATE CONSTRAINT TRIGGER oi_lab_question_requires_child AFTER INSERT ON investigation.source_questions
          DEFERRABLE INITIALLY DEFERRED FOR EACH ROW WHEN ({condition})
          EXECUTE FUNCTION investigation.require_lab_question_child();
    """)


def snapshot_contract(conn, manual):
    values = "'oi.synthetic-postgres-world-model-sources/1','oi.pg-source-world-model/1'"
    if manual:
        values += ",'oi.reviewed-document-selection/1'"
    conn.exec_driver_sql(f"""ALTER TABLE investigation.source_questions DROP CONSTRAINT oi_question_snapshot_contract,
        ADD CONSTRAINT oi_question_snapshot_contract CHECK(source_snapshot_contract IN ({values}))""")


def upgrade():
    conn = op.get_bind()
    snapshot_contract(conn, True)
    conn.exec_driver_sql("""
      CREATE FUNCTION investigation.require_lab_question_contract() RETURNS trigger LANGUAGE plpgsql AS $$
      BEGIN
        IF EXISTS(SELECT 1 FROM investigation.source_questions WHERE question_id=NEW.question_id
                  AND source_snapshot_contract='oi.reviewed-document-selection/1')
        THEN RAISE EXCEPTION 'OI-LAB-QUESTION-ANCHOR-CONTRACT'; END IF;
        RETURN NEW;
      END; $$;
      CREATE TRIGGER oi_lab_anchor_contract BEFORE INSERT ON investigation.laboratory_question_anchors
        FOR EACH ROW EXECUTE FUNCTION investigation.require_lab_question_contract();
      CREATE TABLE investigation.reviewed_question_anchors(
        question_id text PRIMARY KEY REFERENCES investigation.source_questions(question_id),
        manual_revision text NOT NULL REFERENCES clinical_source.annotation_revisions(revision_id),
        manual_key text NOT NULL CHECK(manual_key ~ '^[a-z][a-z0-9_-]{0,59}$'));
      ALTER TABLE investigation.source_questions ADD CONSTRAINT oi_manual_question_null_line CHECK
        (source_snapshot_contract <> 'oi.reviewed-document-selection/1' OR source_line IS NULL);
      CREATE FUNCTION investigation.guard_manual_question() RETURNS trigger LANGUAGE plpgsql AS $$
      BEGIN
        IF NOT EXISTS(SELECT 1 FROM investigation.source_questions q JOIN identity.identity_patients p ON p.patient_id=q.patient_id
          JOIN coordination.patient_case_bindings b ON b.patient_id=p.patient_id
          JOIN clinical_source.source_versions s ON s.case_id=b.case_id
          JOIN clinical_source.annotation_revisions r ON r.source_id=s.source_id
          WHERE q.question_id=NEW.question_id AND q.source_snapshot_contract='oi.reviewed-document-selection/1' AND p.patient_id=q.patient_id AND p.origin_org=q.origin_org AND p.status='active'
            AND b.case_id=q.case_id AND b.origin_org=q.origin_org AND b.purpose=q.purpose AND b.status='active'
            AND s.source_id=q.source_id AND s.state='current' AND s.version=q.source_version AND s.sha256=q.source_sha256
            AND r.revision_id=NEW.manual_revision AND EXISTS(SELECT 1 FROM jsonb_array_elements(r.findings_json) f WHERE f->>'key'=NEW.manual_key)
            AND NOT EXISTS(SELECT 1 FROM clinical_source.annotation_revisions n WHERE n.source_id=r.source_id AND n.revision>r.revision)
          FOR SHARE OF p,b,s,r) THEN RAISE EXCEPTION 'OI-MANUAL-QUESTION-BOUNDARY'; END IF;
        RETURN NEW;
      END; $$;
      CREATE TRIGGER oi_manual_question_insert BEFORE INSERT ON investigation.reviewed_question_anchors
        FOR EACH ROW EXECUTE FUNCTION investigation.guard_manual_question();
      CREATE FUNCTION investigation.require_manual_question_child() RETURNS trigger LANGUAGE plpgsql AS $$
      BEGIN
        IF NOT EXISTS(SELECT 1 FROM investigation.reviewed_question_anchors WHERE question_id=NEW.question_id)
        THEN RAISE EXCEPTION 'OI-MANUAL-QUESTION-MISSING-ANCHOR'; END IF;
        RETURN NULL;
      END; $$;
      CREATE CONSTRAINT TRIGGER oi_manual_question_requires_child AFTER INSERT ON investigation.source_questions
        DEFERRABLE INITIALLY DEFERRED FOR EACH ROW WHEN(NEW.source_snapshot_contract='oi.reviewed-document-selection/1')
        EXECUTE FUNCTION investigation.require_manual_question_child();
      CREATE TRIGGER oi_manual_anchor_mutation BEFORE UPDATE OR DELETE ON investigation.reviewed_question_anchors
        FOR EACH ROW EXECUTE FUNCTION identity.reject_registry_history_mutation();
      CREATE TRIGGER oi_manual_anchor_truncate BEFORE TRUNCATE ON investigation.reviewed_question_anchors
        FOR EACH STATEMENT EXECUTE FUNCTION identity.reject_registry_history_mutation();
    """)
    guards(conn, True)


def downgrade():
    conn = op.get_bind()
    if conn.exec_driver_sql("SELECT 1 FROM investigation.reviewed_question_anchors LIMIT 1").first():
        raise CommandError("Reviewed questions require preservation before downgrade")
    guards(conn, False)
    conn.exec_driver_sql("""DROP TRIGGER oi_lab_anchor_contract ON investigation.laboratory_question_anchors;
      DROP FUNCTION investigation.require_lab_question_contract();
      DROP TRIGGER oi_manual_question_requires_child ON investigation.source_questions;
      DROP FUNCTION investigation.require_manual_question_child();
      DROP TABLE investigation.reviewed_question_anchors;
      DROP FUNCTION investigation.guard_manual_question();
      ALTER TABLE investigation.source_questions DROP CONSTRAINT oi_manual_question_null_line;""")
    snapshot_contract(conn, False)
