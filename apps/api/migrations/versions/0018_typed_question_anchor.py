"""Add typed FHIR Observation anchors to the canonical saved-question owner.

Existing text-line questions keep their historical source-line foreign key and
default anchor kind. Laboratory questions use the same table with a null line
and an exact Observation reference; no second question ledger is introduced.
"""
from alembic import op
from alembic.util.exc import CommandError
from sqlalchemy import text

revision = "0018_typed_question_anchor"
down_revision = "0017_lab_manual_convergence"
branch_labels = None
depends_on = None


def _guard_sql():
    return r"""
    CREATE OR REPLACE FUNCTION investigation.guard_question_insert() RETURNS trigger
    LANGUAGE plpgsql AS $oi_question$
    BEGIN
        IF NOT EXISTS (
            SELECT 1 FROM identity.identity_patients p
            JOIN coordination.patient_case_bindings b ON b.patient_id=p.patient_id
            WHERE p.patient_id=NEW.patient_id
              AND p.origin_org=NEW.origin_org AND p.status='active'
              AND b.case_id=NEW.case_id AND b.origin_org=NEW.origin_org
              AND b.status='active'
        ) THEN RAISE EXCEPTION 'OI-QUESTION-IDENTITY-BOUNDARY'; END IF;
        IF NEW.anchor_kind='text_line' THEN
            IF NEW.source_line IS NULL OR NEW.observation_reference IS NOT NULL OR NOT EXISTS (
                SELECT 1 FROM clinical_source.source_versions s
                JOIN clinical_source.assertions a ON a.source_id=s.source_id
                WHERE s.source_id=NEW.source_id
                  AND s.case_id=NEW.case_id AND s.state='current'
                  AND s.version=NEW.source_version AND s.sha256=NEW.source_sha256
                  AND a.source_line=NEW.source_line
            ) THEN RAISE EXCEPTION 'OI-QUESTION-SOURCE-BOUNDARY'; END IF;
        ELSIF NEW.anchor_kind='fhir_observation' THEN
            IF NEW.source_line IS NOT NULL OR NEW.observation_reference IS NULL OR NOT EXISTS (
                SELECT 1 FROM clinical_source.source_versions s
                JOIN clinical_source.fhir_laboratory_observations o ON o.source_id=s.source_id
                WHERE s.source_id=NEW.source_id
                  AND s.case_id=NEW.case_id AND s.state='current'
                  AND s.version=NEW.source_version AND s.sha256=NEW.source_sha256
                  AND o.observation_reference=NEW.observation_reference
            ) THEN RAISE EXCEPTION 'OI-QUESTION-SOURCE-BOUNDARY'; END IF;
        ELSE
            RAISE EXCEPTION 'OI-QUESTION-ANCHOR-KIND';
        END IF;
        RETURN NEW;
    END;
    $oi_question$;
    """


def _legacy_guard_sql():
    # Preserve the original 0006 function body whitespace as well as behavior.
    # pg_get_functiondef() exposes the stored body, and populated downgrade
    # acceptance intentionally requires byte-stable restoration.
    return r"""CREATE OR REPLACE FUNCTION investigation.guard_question_insert() RETURNS trigger
        LANGUAGE plpgsql AS $oi_question$
        BEGIN
            IF NOT EXISTS (
                SELECT 1 FROM identity.identity_patients p
                JOIN coordination.patient_case_bindings b
                  ON b.patient_id=p.patient_id
                WHERE p.patient_id=NEW.patient_id
                  AND p.origin_org=NEW.origin_org AND p.status='active'
                  AND b.case_id=NEW.case_id AND b.origin_org=NEW.origin_org
                  AND b.status='active'
            ) THEN RAISE EXCEPTION 'OI-QUESTION-IDENTITY-BOUNDARY'; END IF;
            IF NOT EXISTS (
                SELECT 1 FROM clinical_source.source_versions s
                JOIN clinical_source.assertions a
                  ON a.source_id=s.source_id
                WHERE s.source_id=NEW.source_id
                  AND s.case_id=NEW.case_id AND s.state='current'
                  AND s.version=NEW.source_version
                  AND s.sha256=NEW.source_sha256
                  AND a.source_line=NEW.source_line
            ) THEN RAISE EXCEPTION 'OI-QUESTION-SOURCE-BOUNDARY'; END IF;
            RETURN NEW;
        END;
        $oi_question$;"""


def upgrade():
    conn = op.get_bind()
    existing = conn.execute(text(
        "SELECT column_name FROM information_schema.columns "
        "WHERE table_schema='investigation' AND table_name='source_questions' "
        "AND column_name IN ('anchor_kind','observation_reference') ORDER BY column_name"
    )).scalars().all()
    if existing:
        raise CommandError("Existing typed question columns require explicit reconciliation")
    conn.exec_driver_sql("LOCK TABLE investigation.source_questions IN ACCESS EXCLUSIVE MODE")
    conn.exec_driver_sql("""
        ALTER TABLE investigation.source_questions
          ADD COLUMN anchor_kind text NOT NULL DEFAULT 'text_line'
            CHECK (anchor_kind IN ('text_line','fhir_observation')),
          ADD COLUMN observation_reference text,
          ALTER COLUMN source_line DROP NOT NULL;
        ALTER TABLE investigation.source_questions
          ADD CONSTRAINT oi_question_anchor_shape CHECK (
            (anchor_kind='text_line' AND source_line IS NOT NULL AND observation_reference IS NULL)
            OR
            (anchor_kind='fhir_observation' AND source_line IS NULL AND observation_reference IS NOT NULL
             AND observation_reference ~ '^Observation/[A-Za-z0-9.-]{1,64}$')
          ),
          ADD CONSTRAINT oi_question_fhir_observation_fk
            FOREIGN KEY (source_id,observation_reference)
            REFERENCES clinical_source.fhir_laboratory_observations(source_id,observation_reference);
    """)
    conn.exec_driver_sql(_guard_sql())


def downgrade():
    conn = op.get_bind()
    if conn.execute(text(
        "SELECT EXISTS(SELECT 1 FROM investigation.source_questions "
        "WHERE anchor_kind<>'text_line' OR observation_reference IS NOT NULL OR source_line IS NULL)"
    )).scalar_one():
        raise CommandError("Typed laboratory questions require explicit reconciliation before downgrade")
    conn.exec_driver_sql("LOCK TABLE investigation.source_questions IN ACCESS EXCLUSIVE MODE")
    conn.exec_driver_sql("""
        ALTER TABLE investigation.source_questions
          DROP CONSTRAINT oi_question_fhir_observation_fk,
          DROP CONSTRAINT oi_question_anchor_shape,
          ALTER COLUMN source_line SET NOT NULL,
          DROP COLUMN observation_reference,
          DROP COLUMN anchor_kind;
    """)
    conn.exec_driver_sql(_legacy_guard_sql())
