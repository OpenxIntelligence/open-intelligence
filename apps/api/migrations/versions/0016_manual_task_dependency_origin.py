"""Optional immutable manual-passage dependencies of existing canonical tasks.

This adds NO task, question, source or review owner. Existing source-only tasks
remain valid without a dependency row. No medical inference or PHI ingestion.
"""
from alembic import op
from alembic.util.exc import CommandError
from sqlalchemy import text

revision = "0016_manual_task_dependency"
down_revision = "0015_manual_report_context"
branch_labels = None
depends_on = None


def upgrade():
    db = op.get_bind()
    for kind, name in (
        ("table", "question_followthrough_manual_dependencies"),
        ("function", "guard_question_followthrough_manual_dependency"),
    ):
        statement = (
            "SELECT to_regclass('coordination." + name + "')"
            if kind == "table" else
            "SELECT to_regprocedure('coordination." + name + "()')"
        )
        if db.execute(text(statement)).scalar_one() is not None:
            raise CommandError("Existing manual-task dependency owner needs reconciliation")
    op.execute("""
        CREATE TABLE coordination.question_followthrough_manual_dependencies (
            task_id text PRIMARY KEY
                REFERENCES coordination.question_followthrough_tasks(task_id),
            question_id text NOT NULL
                REFERENCES investigation.source_questions(question_id),
            revision_id text NOT NULL
                REFERENCES investigation.question_passage_revisions(revision_id),
            patient_id text NOT NULL REFERENCES identity.identity_patients(patient_id),
            case_id text NOT NULL REFERENCES coordination.patient_case_bindings(case_id),
            origin_org text NOT NULL,
            references_sha256 char(64) NOT NULL
                CHECK (references_sha256 ~ '^[0-9a-f]{64}$'),
            created_at timestamptz NOT NULL DEFAULT clock_timestamp()
        );
        CREATE INDEX idx_oi_task_manual_dependency_case
            ON coordination.question_followthrough_manual_dependencies
            (patient_id, case_id, origin_org, question_id, revision_id);

        CREATE FUNCTION coordination.guard_question_followthrough_manual_dependency()
        RETURNS trigger LANGUAGE plpgsql AS $oi_task_manual_dep$
        BEGIN
            IF NOT EXISTS (
                SELECT 1 FROM coordination.question_followthrough_tasks t
                JOIN investigation.question_passage_revisions p
                  ON p.revision_id = NEW.revision_id
                WHERE t.task_id = NEW.task_id
                  AND t.question_id = NEW.question_id
                  AND t.patient_id = NEW.patient_id
                  AND t.case_id = NEW.case_id
                  AND t.origin_org = NEW.origin_org
                  AND t.purpose = 'operations'
                  AND p.question_id = NEW.question_id
                  AND p.patient_id = NEW.patient_id
                  AND p.case_id = NEW.case_id
                  AND p.origin_org = NEW.origin_org
                  AND p.purpose = 'operations'
                  AND jsonb_array_length(p.references_json) > 0
            ) THEN
                RAISE EXCEPTION 'OI-MANUAL-TASK-DEPENDENCY-SCOPE';
            END IF;
            RETURN NEW;
        END; $oi_task_manual_dep$;

        CREATE TRIGGER oi_task_manual_dependency_scope
            BEFORE INSERT ON coordination.question_followthrough_manual_dependencies
            FOR EACH ROW
            EXECUTE FUNCTION coordination.guard_question_followthrough_manual_dependency();
        CREATE TRIGGER oi_task_manual_dependency_immutable_update
            BEFORE UPDATE ON coordination.question_followthrough_manual_dependencies
            FOR EACH ROW EXECUTE FUNCTION identity.reject_registry_history_mutation();
        CREATE TRIGGER oi_task_manual_dependency_immutable_delete
            BEFORE DELETE ON coordination.question_followthrough_manual_dependencies
            FOR EACH ROW EXECUTE FUNCTION identity.reject_registry_history_mutation();
    """)


def downgrade():
    db = op.get_bind()
    if db.execute(text(
        "SELECT EXISTS(SELECT 1 FROM coordination.question_followthrough_manual_dependencies)"
    )).scalar_one():
        raise CommandError("Stored manual task dependencies require reconciliation before downgrade")
    op.execute("DROP TABLE coordination.question_followthrough_manual_dependencies")
    op.execute("DROP FUNCTION coordination.guard_question_followthrough_manual_dependency()")
