"""Allow a canonical task to retain the exact observation of a laboratory question."""
from alembic import op
from alembic.util.exc import CommandError

revision = "0023_lab_question_followthrough"
down_revision = "0022_lab_citation_source_scope"
branch_labels = None
depends_on = None


def upgrade():
    op.get_bind().exec_driver_sql("""
        ALTER TABLE coordination.question_followthrough_tasks
            ADD COLUMN observation_reference text,
            ALTER COLUMN source_line DROP NOT NULL,
            ADD CONSTRAINT oi_followthrough_one_anchor
                CHECK ((source_line IS NULL) <> (observation_reference IS NULL)),
            ADD CONSTRAINT oi_followthrough_source_observation
                FOREIGN KEY (source_id, observation_reference) REFERENCES
                    clinical_source.fhir_laboratory_observations(source_id, observation_reference);

        -- Preserve the original text question guard, including its error order.
        DROP TRIGGER oi_followthrough_task_insert_guard ON coordination.question_followthrough_tasks;
        CREATE TRIGGER oi_followthrough_task_insert_guard BEFORE INSERT ON coordination.question_followthrough_tasks
            FOR EACH ROW WHEN (NEW.source_line IS NOT NULL)
            EXECUTE FUNCTION coordination.guard_question_followthrough_task_insert();

        -- The 0022 snapshot boundary applies to citations, new tasks and task
        -- completion. Call only after the source owner's case binding lock. A
        -- VOLATILE function at READ COMMITTED sees a concurrent import that
        -- finished while this writer waited for the lock.
        CREATE FUNCTION investigation.lab_question_sources_current(
            patient_key text, case_key text, question_key text, snapshot_sha text
        ) RETURNS boolean LANGUAGE sql VOLATILE AS $fresh$
            WITH saved AS (
                SELECT min(e.id) AS id FROM identity.identity_domain_events e
                WHERE e.patient_id=patient_key AND e.event_type='investigation.question.created'
                  AND e.metadata_json->>'case_id'=case_key AND e.metadata_json->>'question_id'=question_key
                  AND e.metadata_json->>'source_snapshot_sha256'=snapshot_sha
            )
            SELECT saved.id IS NOT NULL AND NOT EXISTS (
                SELECT s.source_id FROM clinical_source.source_versions s
                WHERE s.case_id=case_key
                  AND s.source_id NOT IN (SELECT source_id FROM clinical_source.document_intakes)
                EXCEPT
                SELECT e.metadata_json->>'source_id' FROM identity.identity_domain_events e
                WHERE e.patient_id=patient_key AND e.id < saved.id AND e.event_type='source.original.imported'
                  AND e.metadata_json->>'case_id'=case_key
            ) FROM saved;
        $fresh$;
        CREATE OR REPLACE FUNCTION investigation.require_lab_citation_current_sources() RETURNS trigger
        LANGUAGE plpgsql AS $citation$
        BEGIN
            IF EXISTS (SELECT 1 FROM investigation.laboratory_question_anchors WHERE question_id=NEW.question_id) THEN
                IF current_setting('transaction_isolation') <> 'read committed' THEN
                    RAISE EXCEPTION 'OI-LAB-CITATION-READ-COMMITTED-REQUIRED';
                END IF;
                IF NOT investigation.lab_question_sources_current(NEW.patient_id, NEW.case_id,
                        NEW.question_id, NEW.source_snapshot_sha256) THEN
                    RAISE EXCEPTION 'OI-LAB-CITATION-CASE-SOURCES-CHANGED';
                END IF;
            END IF;
            RETURN NEW;
        END; $citation$;

        CREATE FUNCTION coordination.guard_lab_followthrough_task_insert() RETURNS trigger
        LANGUAGE plpgsql AS $task$
        BEGIN
            -- Same lock order and case-wide limit as the 0009 text task owner.
            PERFORM 1 FROM identity.identity_patients p WHERE p.patient_id=NEW.patient_id
                AND p.origin_org=NEW.origin_org AND p.status='active' FOR SHARE;
            IF NOT FOUND THEN RAISE EXCEPTION 'OI-FOLLOWTHROUGH-PATIENT-BOUNDARY'; END IF;
            PERFORM 1 FROM coordination.patient_case_bindings b WHERE b.case_id=NEW.case_id
                AND b.patient_id=NEW.patient_id AND b.origin_org=NEW.origin_org AND b.status='active'
                AND b.purpose=NEW.purpose FOR UPDATE;
            IF NOT FOUND THEN RAISE EXCEPTION 'OI-FOLLOWTHROUGH-CASE-BOUNDARY'; END IF;
            IF NOT EXISTS (
                SELECT 1 FROM investigation.source_questions q
                JOIN investigation.laboratory_question_anchors a ON a.question_id=q.question_id AND a.source_id=q.source_id
                JOIN clinical_source.source_versions s ON s.source_id=q.source_id AND s.case_id=q.case_id
                WHERE q.question_id=NEW.question_id AND q.patient_id=NEW.patient_id AND q.case_id=NEW.case_id
                  AND q.origin_org=NEW.origin_org AND q.purpose=NEW.purpose AND q.source_line IS NULL
                  AND q.source_id=NEW.source_id AND a.observation_reference=NEW.observation_reference
                  AND q.source_version=NEW.source_version AND q.source_sha256=NEW.source_sha256
                  AND q.source_snapshot_contract=NEW.source_snapshot_contract
                  AND q.source_snapshot_sha256=NEW.source_snapshot_sha256 AND q.preflight_sha256=NEW.preflight_sha256
                  AND s.state='current' AND s.kind='laboratory' AND s.version=NEW.source_version AND s.sha256=NEW.source_sha256
            ) THEN RAISE EXCEPTION 'OI-FOLLOWTHROUGH-QUESTION-BOUNDARY'; END IF;
            IF current_setting('transaction_isolation') <> 'read committed' THEN
                RAISE EXCEPTION 'OI-LAB-FOLLOWTHROUGH-READ-COMMITTED-REQUIRED';
            END IF;
            IF NOT investigation.lab_question_sources_current(NEW.patient_id, NEW.case_id,
                    NEW.question_id, NEW.source_snapshot_sha256) THEN
                RAISE EXCEPTION 'OI-LAB-FOLLOWTHROUGH-CASE-SOURCES-CHANGED';
            END IF;
            IF (SELECT count(*) FROM coordination.question_followthrough_tasks
                WHERE patient_id=NEW.patient_id AND case_id=NEW.case_id)>=250 THEN
                RAISE EXCEPTION 'OI-FOLLOWTHROUGH-TASK-LIMIT';
            END IF;
            RETURN NEW;
        END; $task$;
        CREATE TRIGGER oi_lab_followthrough_task_insert BEFORE INSERT ON coordination.question_followthrough_tasks
            FOR EACH ROW WHEN (NEW.source_line IS NULL) EXECUTE FUNCTION coordination.guard_lab_followthrough_task_insert();

        CREATE FUNCTION coordination.guard_lab_followthrough_completion() RETURNS trigger
        LANGUAGE plpgsql AS $completion$
        DECLARE origin coordination.question_followthrough_tasks%ROWTYPE;
        BEGIN
            -- The earlier 0009 event guard already locked the case and task
            -- and enforced the exact prior revision and allowed transition.
            SELECT * INTO origin FROM coordination.question_followthrough_tasks
                WHERE task_id=NEW.task_id AND observation_reference IS NOT NULL;
            IF FOUND THEN
                IF current_setting('transaction_isolation') <> 'read committed' THEN
                    RAISE EXCEPTION 'OI-LAB-FOLLOWTHROUGH-READ-COMMITTED-REQUIRED';
                END IF;
                IF NOT EXISTS (SELECT 1 FROM clinical_source.source_versions WHERE source_id=origin.source_id AND state='current')
                    OR NOT investigation.lab_question_sources_current(origin.patient_id, origin.case_id,
                            origin.question_id, origin.source_snapshot_sha256) THEN
                    RAISE EXCEPTION 'OI-LAB-FOLLOWTHROUGH-CASE-SOURCES-CHANGED';
                END IF;
            END IF;
            RETURN NEW;
        END; $completion$;
        CREATE TRIGGER zz_oi_lab_followthrough_completion BEFORE INSERT ON coordination.question_followthrough_events
            FOR EACH ROW WHEN (NEW.status='completed') EXECUTE FUNCTION coordination.guard_lab_followthrough_completion();
    """)


def downgrade():
    db = op.get_bind()
    db.exec_driver_sql("LOCK TABLE coordination.question_followthrough_tasks, "
                       "coordination.question_followthrough_events IN ACCESS EXCLUSIVE MODE")
    if db.exec_driver_sql("SELECT EXISTS (SELECT 1 FROM coordination.question_followthrough_tasks "
                          "WHERE observation_reference IS NOT NULL OR source_line IS NULL)").scalar_one():
        raise CommandError("Stored laboratory task history requires explicit reconciliation before downgrade")
    # Restore the exact published 0022 trigger body; it owns no other DDL.
    op.get_context().script.get_revision(down_revision).module.upgrade()
    db.exec_driver_sql("""
        DROP TRIGGER zz_oi_lab_followthrough_completion ON coordination.question_followthrough_events;
        DROP FUNCTION coordination.guard_lab_followthrough_completion();
        DROP TRIGGER oi_lab_followthrough_task_insert ON coordination.question_followthrough_tasks;
        DROP FUNCTION coordination.guard_lab_followthrough_task_insert();
        DROP FUNCTION investigation.lab_question_sources_current(text,text,text,text);
        DROP TRIGGER oi_followthrough_task_insert_guard ON coordination.question_followthrough_tasks;
        CREATE TRIGGER oi_followthrough_task_insert_guard BEFORE INSERT ON coordination.question_followthrough_tasks
            FOR EACH ROW EXECUTE FUNCTION coordination.guard_question_followthrough_task_insert();
        ALTER TABLE coordination.question_followthrough_tasks
            DROP CONSTRAINT oi_followthrough_one_anchor, DROP CONSTRAINT oi_followthrough_source_observation,
            ALTER COLUMN source_line SET NOT NULL, DROP COLUMN observation_reference;
    """)
