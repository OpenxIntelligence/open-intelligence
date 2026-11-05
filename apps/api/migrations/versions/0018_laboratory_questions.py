"""Extend the immutable question ledger with source-local observation anchors."""
from alembic import op
from alembic.util.exc import CommandError

revision = "0018_laboratory_questions"
down_revision = "0017_lab_manual_convergence"
branch_labels = None
depends_on = None


def upgrade():
    # Keep all existing question columns, identifiers, rows and versioned
    # intents. A NULL line requires exactly one immutable typed child at commit.
    op.get_bind().exec_driver_sql("""
        CREATE TABLE investigation.laboratory_question_anchors (
            question_id text PRIMARY KEY REFERENCES investigation.source_questions(question_id),
            source_id text NOT NULL,
            observation_reference text NOT NULL,
            FOREIGN KEY (source_id,observation_reference) REFERENCES
                clinical_source.fhir_laboratory_observations(source_id,observation_reference)
        );
        ALTER TABLE investigation.source_questions ALTER COLUMN source_line DROP NOT NULL;
        DROP TRIGGER oi_question_insert_guard ON investigation.source_questions;
        CREATE TRIGGER oi_question_insert_guard BEFORE INSERT ON investigation.source_questions
            FOR EACH ROW WHEN (NEW.source_line IS NOT NULL)
            EXECUTE FUNCTION investigation.guard_question_insert();

        CREATE FUNCTION investigation.guard_lab_question_insert() RETURNS trigger
        LANGUAGE plpgsql AS $oi$
        BEGIN
            IF NEW.source_snapshot_contract <> 'oi.pg-source-world-model/1'
               OR NOT EXISTS (
                SELECT 1 FROM identity.identity_patients p
                JOIN coordination.patient_case_bindings b ON b.patient_id=p.patient_id
                JOIN clinical_source.source_versions s ON s.case_id=b.case_id
                JOIN clinical_source.fhir_laboratory_sources f ON f.source_id=s.source_id
                WHERE p.patient_id=NEW.patient_id AND p.origin_org=NEW.origin_org AND p.status='active'
                  AND b.case_id=NEW.case_id AND b.origin_org=NEW.origin_org
                  AND b.status='active' AND b.purpose=NEW.purpose
                  AND s.source_id=NEW.source_id AND s.sha256=NEW.source_sha256
                  AND s.version=NEW.source_version AND s.kind='laboratory' AND s.state='current'
                FOR SHARE OF p,b,s
            ) THEN RAISE EXCEPTION 'OI-LAB-QUESTION-SOURCE-BOUNDARY'; END IF;
            RETURN NEW;
        END;
        $oi$;
        CREATE TRIGGER oi_lab_question_insert_guard BEFORE INSERT ON investigation.source_questions
            FOR EACH ROW WHEN (NEW.source_line IS NULL)
            EXECUTE FUNCTION investigation.guard_lab_question_insert();

        CREATE FUNCTION investigation.guard_lab_question_child() RETURNS trigger
        LANGUAGE plpgsql AS $oi$
        BEGIN
            IF NOT EXISTS (
                SELECT 1 FROM investigation.source_questions q
                WHERE q.question_id=NEW.question_id AND q.source_line IS NULL AND q.source_id=NEW.source_id
            ) THEN RAISE EXCEPTION 'OI-LAB-QUESTION-ANCHOR-BOUNDARY'; END IF;
            RETURN NEW;
        END;
        $oi$;
        CREATE TRIGGER oi_lab_question_child_guard BEFORE INSERT ON investigation.laboratory_question_anchors
            FOR EACH ROW EXECUTE FUNCTION investigation.guard_lab_question_child();

        CREATE FUNCTION investigation.require_lab_question_child() RETURNS trigger
        LANGUAGE plpgsql AS $oi$
        BEGIN
            IF NOT EXISTS (
                SELECT 1 FROM investigation.laboratory_question_anchors a
                WHERE a.question_id=NEW.question_id AND a.source_id=NEW.source_id
            ) THEN RAISE EXCEPTION 'OI-LAB-QUESTION-MISSING-ANCHOR'; END IF;
            RETURN NULL;
        END;
        $oi$;
        CREATE CONSTRAINT TRIGGER oi_lab_question_requires_child AFTER INSERT ON investigation.source_questions
            DEFERRABLE INITIALLY DEFERRED FOR EACH ROW WHEN (NEW.source_line IS NULL)
            EXECUTE FUNCTION investigation.require_lab_question_child();
        CREATE TRIGGER oi_lab_anchor_update_guard BEFORE UPDATE OR DELETE ON investigation.laboratory_question_anchors
            FOR EACH ROW EXECUTE FUNCTION identity.reject_registry_history_mutation();
        CREATE TRIGGER oi_lab_anchor_truncate_guard BEFORE TRUNCATE ON investigation.laboratory_question_anchors
            FOR EACH STATEMENT EXECUTE FUNCTION identity.reject_registry_history_mutation();
    """)


def downgrade():
    conn = op.get_bind()
    # Exclude concurrent writers between the refusal check and removing guards.
    conn.exec_driver_sql("LOCK TABLE investigation.source_questions, investigation.laboratory_question_anchors IN ACCESS EXCLUSIVE MODE")
    if conn.exec_driver_sql("""
        SELECT EXISTS(SELECT 1 FROM investigation.source_questions WHERE source_line IS NULL)
            OR EXISTS(SELECT 1 FROM investigation.laboratory_question_anchors)
    """).scalar_one():
        raise CommandError("Stored laboratory question history requires explicit reconciliation")
    conn.exec_driver_sql("""
        DROP TRIGGER oi_lab_question_requires_child ON investigation.source_questions;
        DROP TRIGGER oi_lab_question_insert_guard ON investigation.source_questions;
        DROP TABLE investigation.laboratory_question_anchors;
        DROP FUNCTION investigation.require_lab_question_child();
        DROP FUNCTION investigation.guard_lab_question_child();
        DROP FUNCTION investigation.guard_lab_question_insert();
        DROP TRIGGER oi_question_insert_guard ON investigation.source_questions;
        CREATE TRIGGER oi_question_insert_guard BEFORE INSERT ON investigation.source_questions
            FOR EACH ROW EXECUTE FUNCTION investigation.guard_question_insert();
        ALTER TABLE investigation.source_questions ALTER COLUMN source_line SET NOT NULL;
    """)
