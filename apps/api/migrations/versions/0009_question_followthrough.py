"""First-party operational follow-through on canonical H1 source questions.

Task origins and event history are immutable. Status/owner are derived from
the latest event; no source, question or professional-review state is changed.
"""
from alembic import op
from alembic.util.exc import CommandError
from sqlalchemy import text

revision = "0009_question_followthrough"
down_revision = "0008_review_convergence"
branch_labels = None
depends_on = None


def upgrade():
    conn = op.get_bind()
    for name in (
        "question_followthrough_tasks", "question_followthrough_events",
        "guard_question_followthrough_task_insert", "guard_question_followthrough_event_insert",
    ):
        exists = conn.execute(text(
            "SELECT 1 FROM pg_class c JOIN pg_namespace n ON n.oid=c.relnamespace "
            "WHERE n.nspname='coordination' AND c.relname=:name "
            "UNION ALL SELECT 1 FROM pg_proc p JOIN pg_namespace n ON n.oid=p.pronamespace "
            "WHERE n.nspname='coordination' AND p.proname=:name LIMIT 1"
        ), {"name": name}).scalar_one_or_none()
        if exists is not None:
            raise CommandError("Existing follow-through owner requires explicit reconciliation")

    conn.exec_driver_sql("""
        CREATE TABLE coordination.question_followthrough_tasks (
            task_id text PRIMARY KEY CHECK (task_id ~ '^TASK-[0-9A-F]{32}$'),
            question_id text NOT NULL REFERENCES investigation.source_questions(question_id),
            patient_id text NOT NULL REFERENCES identity.identity_patients(patient_id),
            case_id text NOT NULL REFERENCES coordination.patient_case_bindings(case_id),
            origin_org text NOT NULL,
            actor text NOT NULL CHECK (char_length(actor) BETWEEN 3 AND 128),
            purpose text NOT NULL CHECK (purpose='operations'),
            title text NOT NULL CHECK (char_length(title) BETWEEN 3 AND 160
                AND title=btrim(title) AND title !~ '[[:cntrl:]]'),
            detail text NOT NULL DEFAULT '' CHECK (char_length(detail)<=2000
                AND detail=btrim(detail) AND detail !~ '[[:cntrl:]]'),
            initial_owner_label text NOT NULL DEFAULT '' CHECK (char_length(initial_owner_label)<=80
                AND initial_owner_label=btrim(initial_owner_label)
                AND initial_owner_label !~ '[[:cntrl:]]'),
            due_date date,
            review_trigger text NOT NULL DEFAULT '' CHECK (char_length(review_trigger)<=500
                AND review_trigger=btrim(review_trigger) AND review_trigger !~ '[[:cntrl:]]'),
            created_at timestamptz NOT NULL DEFAULT clock_timestamp(),
            source_id text NOT NULL,
            source_line integer NOT NULL CHECK (source_line BETWEEN 1 AND 10000),
            source_sha256 char(64) NOT NULL CHECK (source_sha256 ~ '^[0-9a-f]{64}$'),
            source_version integer NOT NULL CHECK (source_version>=1),
            source_snapshot_contract text NOT NULL CHECK (source_snapshot_contract='oi.pg-source-world-model/1'),
            source_snapshot_sha256 char(64) NOT NULL CHECK (source_snapshot_sha256 ~ '^[0-9a-f]{64}$'),
            preflight_sha256 char(64) NOT NULL CHECK (preflight_sha256 ~ '^[0-9a-f]{64}$'),
            CHECK (due_date IS NOT NULL OR char_length(review_trigger)>0),
            FOREIGN KEY (source_id,source_line)
                REFERENCES clinical_source.assertions(source_id,source_line)
        );
        CREATE INDEX idx_oi_followthrough_case ON coordination.question_followthrough_tasks
            (patient_id,case_id,created_at,task_id);

        CREATE TABLE coordination.question_followthrough_events (
            event_id text PRIMARY KEY CHECK (event_id ~ '^TASK-EVENT-[0-9A-F]{32}$'),
            task_id text NOT NULL REFERENCES coordination.question_followthrough_tasks(task_id),
            patient_id text NOT NULL REFERENCES identity.identity_patients(patient_id),
            case_id text NOT NULL REFERENCES coordination.patient_case_bindings(case_id),
            origin_org text NOT NULL,
            request_key text NOT NULL CHECK (char_length(request_key) BETWEEN 3 AND 128),
            intent_sha256 char(64) NOT NULL CHECK (intent_sha256 ~ '^[0-9a-f]{64}$'),
            revision integer NOT NULL CHECK (revision>=1),
            previous_status text CHECK (previous_status IN ('created','assigned','acknowledged','completed','deferred')),
            status text NOT NULL CHECK (status IN ('created','assigned','acknowledged','completed','deferred')),
            owner_label text NOT NULL DEFAULT '' CHECK (char_length(owner_label)<=80
                AND owner_label=btrim(owner_label) AND owner_label !~ '[[:cntrl:]]'),
            actor_label text NOT NULL CHECK (char_length(actor_label) BETWEEN 3 AND 128),
            purpose text NOT NULL CHECK (purpose='operations'),
            reason text NOT NULL CHECK (char_length(reason) BETWEEN 3 AND 600
                AND reason=btrim(reason) AND reason !~ '[[:cntrl:]]'),
            recorded_at timestamptz NOT NULL DEFAULT clock_timestamp(),
            UNIQUE (patient_id,request_key),
            UNIQUE (task_id,revision)
        );
        CREATE INDEX idx_oi_followthrough_event_case ON coordination.question_followthrough_events
            (patient_id,case_id,task_id,revision);

        CREATE FUNCTION coordination.guard_question_followthrough_task_insert()
        RETURNS trigger LANGUAGE plpgsql AS $oi_followthrough_task$
        BEGIN
            -- Match the source owner's patient SHARE -> binding UPDATE locks.
            -- SHARE still prevents suspension, without upgrading a patient lock
            -- while another writer holds SHARE and waits for the case binding.
            PERFORM 1 FROM identity.identity_patients p
                WHERE p.patient_id=NEW.patient_id AND p.origin_org=NEW.origin_org
                  AND p.status='active' FOR SHARE;
            IF NOT FOUND THEN RAISE EXCEPTION 'OI-FOLLOWTHROUGH-PATIENT-BOUNDARY'; END IF;
            PERFORM 1 FROM coordination.patient_case_bindings b
                WHERE b.case_id=NEW.case_id AND b.patient_id=NEW.patient_id
                  AND b.origin_org=NEW.origin_org AND b.status='active'
                  AND b.purpose=NEW.purpose FOR UPDATE;
            IF NOT FOUND THEN RAISE EXCEPTION 'OI-FOLLOWTHROUGH-CASE-BOUNDARY'; END IF;
            IF NOT EXISTS (
                SELECT 1 FROM investigation.source_questions q
                JOIN clinical_source.source_versions s ON s.source_id=q.source_id
                WHERE q.question_id=NEW.question_id AND q.patient_id=NEW.patient_id
                  AND q.case_id=NEW.case_id AND q.origin_org=NEW.origin_org
                  AND q.purpose=NEW.purpose AND q.source_id=NEW.source_id
                  AND q.source_line=NEW.source_line AND q.source_sha256=NEW.source_sha256
                  AND q.source_version=NEW.source_version
                  AND q.source_snapshot_contract=NEW.source_snapshot_contract
                  AND q.source_snapshot_sha256=NEW.source_snapshot_sha256
                  AND q.preflight_sha256=NEW.preflight_sha256
                  AND s.case_id=NEW.case_id AND s.state='current'
                  AND s.version=NEW.source_version AND s.sha256=NEW.source_sha256
            ) THEN RAISE EXCEPTION 'OI-FOLLOWTHROUGH-QUESTION-BOUNDARY'; END IF;
            IF (SELECT count(*) FROM coordination.question_followthrough_tasks
                WHERE patient_id=NEW.patient_id AND case_id=NEW.case_id)>=250 THEN
                RAISE EXCEPTION 'OI-FOLLOWTHROUGH-TASK-LIMIT';
            END IF;
            RETURN NEW;
        END;
        $oi_followthrough_task$;

        CREATE FUNCTION coordination.guard_question_followthrough_event_insert()
        RETURNS trigger LANGUAGE plpgsql AS $oi_followthrough_event$
        DECLARE
            task_row coordination.question_followthrough_tasks%ROWTYPE;
            prior_row coordination.question_followthrough_events%ROWTYPE;
        BEGIN
            SELECT * INTO task_row FROM coordination.question_followthrough_tasks
                WHERE task_id=NEW.task_id;
            IF NOT FOUND OR task_row.patient_id!=NEW.patient_id OR task_row.case_id!=NEW.case_id
                OR task_row.origin_org!=NEW.origin_org OR task_row.purpose!=NEW.purpose THEN
                RAISE EXCEPTION 'OI-FOLLOWTHROUGH-EVENT-SCOPE';
            END IF;
            PERFORM 1 FROM identity.identity_patients p
                WHERE p.patient_id=NEW.patient_id AND p.origin_org=NEW.origin_org
                  AND p.status='active' FOR SHARE;
            IF NOT FOUND THEN RAISE EXCEPTION 'OI-FOLLOWTHROUGH-PATIENT-BOUNDARY'; END IF;
            PERFORM 1 FROM coordination.patient_case_bindings b
                WHERE b.case_id=NEW.case_id AND b.patient_id=NEW.patient_id
                  AND b.origin_org=NEW.origin_org AND b.status='active'
                  AND b.purpose=NEW.purpose FOR UPDATE;
            IF NOT FOUND THEN RAISE EXCEPTION 'OI-FOLLOWTHROUGH-CASE-BOUNDARY'; END IF;
            PERFORM 1 FROM coordination.question_followthrough_tasks
                WHERE task_id=NEW.task_id FOR UPDATE;
            -- Source amendments do not forbid attributed operational updates.
            -- They never change this task's question or original source anchor.
            SELECT * INTO prior_row FROM coordination.question_followthrough_events
                WHERE task_id=NEW.task_id ORDER BY revision DESC LIMIT 1;
            IF NOT FOUND THEN
                IF NEW.revision!=1 OR NEW.previous_status IS NOT NULL OR NEW.status!='created'
                    OR NEW.owner_label!=task_row.initial_owner_label
                    OR NEW.actor_label!=task_row.actor THEN
                    RAISE EXCEPTION 'OI-FOLLOWTHROUGH-CREATION-EVENT';
                END IF;
            ELSE
                IF NEW.revision!=prior_row.revision+1
                    OR NEW.previous_status IS DISTINCT FROM prior_row.status THEN
                    RAISE EXCEPTION 'OI-FOLLOWTHROUGH-REVISION';
                END IF;
                IF NOT (CASE prior_row.status
                    WHEN 'created' THEN NEW.status IN ('assigned','deferred')
                    WHEN 'assigned' THEN NEW.status IN ('acknowledged','deferred')
                    WHEN 'acknowledged' THEN NEW.status IN ('completed','deferred')
                    WHEN 'deferred' THEN NEW.status='assigned'
                    ELSE false END) THEN
                    RAISE EXCEPTION 'OI-FOLLOWTHROUGH-LIFECYCLE';
                END IF;
                IF NEW.status='assigned' THEN
                    IF char_length(NEW.owner_label)<2 THEN
                        RAISE EXCEPTION 'OI-FOLLOWTHROUGH-OWNER';
                    END IF;
                ELSIF NEW.owner_label IS DISTINCT FROM prior_row.owner_label THEN
                    RAISE EXCEPTION 'OI-FOLLOWTHROUGH-OWNER';
                END IF;
            END IF;
            IF (SELECT count(*) FROM coordination.question_followthrough_events
                WHERE patient_id=NEW.patient_id AND case_id=NEW.case_id)>=750 THEN
                RAISE EXCEPTION 'OI-FOLLOWTHROUGH-HISTORY-LIMIT';
            END IF;
            RETURN NEW;
        END;
        $oi_followthrough_event$;

        CREATE TRIGGER oi_followthrough_task_insert_guard
            BEFORE INSERT ON coordination.question_followthrough_tasks
            FOR EACH ROW EXECUTE FUNCTION coordination.guard_question_followthrough_task_insert();
        CREATE TRIGGER oi_followthrough_event_insert_guard
            BEFORE INSERT ON coordination.question_followthrough_events
            FOR EACH ROW EXECUTE FUNCTION coordination.guard_question_followthrough_event_insert();
        CREATE TRIGGER oi_followthrough_task_immutable
            BEFORE UPDATE OR DELETE ON coordination.question_followthrough_tasks
            FOR EACH ROW EXECUTE FUNCTION identity.reject_registry_history_mutation();
        CREATE TRIGGER oi_followthrough_event_immutable
            BEFORE UPDATE OR DELETE ON coordination.question_followthrough_events
            FOR EACH ROW EXECUTE FUNCTION identity.reject_registry_history_mutation();
        CREATE TRIGGER oi_followthrough_task_no_truncate
            BEFORE TRUNCATE ON coordination.question_followthrough_tasks
            FOR EACH STATEMENT EXECUTE FUNCTION identity.reject_registry_history_mutation();
        CREATE TRIGGER oi_followthrough_event_no_truncate
            BEFORE TRUNCATE ON coordination.question_followthrough_events
            FOR EACH STATEMENT EXECUTE FUNCTION identity.reject_registry_history_mutation();
    """)


def downgrade():
    conn = op.get_bind()
    conn.exec_driver_sql(
        "LOCK TABLE coordination.question_followthrough_tasks, "
        "coordination.question_followthrough_events IN ACCESS EXCLUSIVE MODE"
    )
    present = conn.execute(text(
        "SELECT 1 FROM coordination.question_followthrough_tasks "
        "UNION ALL SELECT 1 FROM coordination.question_followthrough_events LIMIT 1"
    )).scalar_one_or_none()
    if present is not None:
        raise CommandError("Follow-through history requires explicit reconciliation before downgrade")
    for statement in (
        "DROP TABLE coordination.question_followthrough_events",
        "DROP TABLE coordination.question_followthrough_tasks",
        "DROP FUNCTION coordination.guard_question_followthrough_event_insert()",
        "DROP FUNCTION coordination.guard_question_followthrough_task_insert()",
    ):
        conn.exec_driver_sql(statement)
