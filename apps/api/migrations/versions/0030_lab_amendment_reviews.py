"""Record independent human checks of amended laboratory follow-through sources."""
from alembic import op
from alembic.util.exc import CommandError

revision = "0030_lab_amendment_reviews"
down_revision = "0029_patient_access"
branch_labels = None
depends_on = None


def upgrade():
    db = op.get_bind()
    if db.exec_driver_sql("""
        SELECT to_regclass('investigation.laboratory_amendment_reviews') IS NOT NULL
            OR to_regprocedure('investigation.guard_lab_amendment_review_insert()') IS NOT NULL
    """).scalar_one():
        raise CommandError("Existing laboratory amendment review owner requires explicit reconciliation")
    db.exec_driver_sql("""
        CREATE TABLE investigation.laboratory_amendment_reviews (
            entry_id text PRIMARY KEY CHECK (entry_id ~ '^VERIFY-[0-9A-F]{32}$'),
            request_id text NOT NULL REFERENCES investigation.laboratory_amendment_reviews(entry_id),
            task_id text NOT NULL REFERENCES coordination.question_followthrough_tasks(task_id),
            question_id text NOT NULL REFERENCES investigation.laboratory_question_anchors(question_id),
            patient_id text NOT NULL REFERENCES identity.identity_patients(patient_id),
            case_id text NOT NULL REFERENCES coordination.patient_case_bindings(case_id),
            origin_org text NOT NULL,
            actor text NOT NULL CHECK (actor ~ '^[A-Za-z0-9][A-Za-z0-9_.:-]{2,127}$'),
            purpose text NOT NULL CHECK (purpose='operations'),
            action text NOT NULL CHECK (action IN ('request','respond')),
            reason text NOT NULL CHECK (char_length(reason) BETWEEN 3 AND 600
                AND reason=btrim(reason) AND reason !~ '[[:cntrl:]]'),
            disposition text,
            original_source_id text NOT NULL REFERENCES clinical_source.fhir_laboratory_sources(source_id),
            latest_source_id text NOT NULL REFERENCES clinical_source.fhir_laboratory_sources(source_id),
            latest_sha256 char(64) NOT NULL CHECK (latest_sha256 ~ '^[0-9a-f]{64}$'),
            request_key text NOT NULL CHECK (request_key ~ '^[A-Za-z0-9][A-Za-z0-9_.:-]{2,127}$'),
            intent_sha256 char(64) NOT NULL CHECK (intent_sha256 ~ '^[0-9a-f]{64}$'),
            recorded_at timestamptz NOT NULL DEFAULT clock_timestamp(),
            CHECK (original_source_id<>latest_source_id),
            CHECK ((action='request' AND entry_id=request_id AND disposition IS NULL)
                OR (action='respond' AND entry_id<>request_id AND disposition IS NOT NULL
                    AND disposition IN ('transcription_checked','needs_clarification'))),
            UNIQUE (patient_id,request_key)
        );
        CREATE UNIQUE INDEX oi_lab_amendment_one_request ON investigation.laboratory_amendment_reviews
            (task_id,latest_source_id) WHERE action='request';
        CREATE UNIQUE INDEX oi_lab_amendment_one_response ON investigation.laboratory_amendment_reviews
            (request_id) WHERE action='respond';
        CREATE INDEX oi_lab_amendment_case ON investigation.laboratory_amendment_reviews
            (patient_id,case_id,origin_org,recorded_at,entry_id);

        CREATE FUNCTION investigation.guard_lab_amendment_review_insert() RETURNS trigger
        LANGUAGE plpgsql AS $review$
        DECLARE binding coordination.patient_case_bindings%ROWTYPE;
        BEGIN
            -- An importer uses patient SHARE -> case UPDATE. Acquire that same lock
            -- order, then evaluate the committed successor after any wait. A fixed
            -- transaction snapshot could still see a superseded source as current.
            IF current_setting('transaction_isolation') <> 'read committed' THEN
                RAISE EXCEPTION 'OI-LAB-AMENDMENT-READ-COMMITTED-REQUIRED';
            END IF;
            PERFORM 1 FROM identity.identity_patients WHERE patient_id=NEW.patient_id
                AND origin_org=NEW.origin_org AND status='active' FOR SHARE;
            IF NOT FOUND THEN RAISE EXCEPTION 'OI-LAB-AMENDMENT-PATIENT-SCOPE'; END IF;
            SELECT * INTO binding FROM coordination.patient_case_bindings WHERE case_id=NEW.case_id
                AND patient_id=NEW.patient_id AND origin_org=NEW.origin_org AND purpose=NEW.purpose
                AND status='active' FOR UPDATE;
            IF NOT FOUND THEN RAISE EXCEPTION 'OI-LAB-AMENDMENT-CASE-SCOPE'; END IF;

            IF NOT EXISTS (
                SELECT 1 FROM coordination.question_followthrough_tasks t
                JOIN investigation.source_questions q ON q.question_id=t.question_id AND q.source_id=t.source_id
                JOIN investigation.laboratory_question_anchors a ON a.question_id=q.question_id AND a.source_id=q.source_id
                JOIN clinical_source.source_versions s ON s.source_id=t.source_id AND s.case_id=t.case_id
                WHERE t.task_id=NEW.task_id AND t.question_id=NEW.question_id AND t.source_id=NEW.original_source_id
                  AND (t.patient_id,t.case_id,t.origin_org,t.purpose)=(NEW.patient_id,NEW.case_id,NEW.origin_org,NEW.purpose)
                  AND (q.patient_id,q.case_id,q.origin_org,q.purpose)=(t.patient_id,t.case_id,t.origin_org,t.purpose)
                  AND t.source_line IS NULL AND q.source_line IS NULL AND t.observation_reference=a.observation_reference
                  AND t.source_version=q.source_version AND t.source_version=s.version
                  AND t.source_sha256=q.source_sha256 AND t.source_sha256=s.sha256
                  AND (t.source_snapshot_contract,t.source_snapshot_sha256,t.preflight_sha256)=
                      (q.source_snapshot_contract,q.source_snapshot_sha256,q.preflight_sha256)
            ) THEN RAISE EXCEPTION 'OI-LAB-AMENDMENT-TASK-ORIGIN'; END IF;

            -- A newer number or matching Observation alone cannot identify a
            -- descendant. Walk supersedes_id back to this task's original, requiring
            -- the same FHIR subject, specimen, report and event at every step. A
            -- removed Observation in the latest report is a legitimate comparison.
            IF NOT EXISTS (
                WITH RECURSIVE scoped AS NOT MATERIALIZED (
                    SELECT s.source_id,s.supersedes_id,s.version,s.document_id,s.event_date,s.specimen_id,s.sha256,s.state
                    FROM clinical_source.source_versions s JOIN clinical_source.fhir_laboratory_sources f USING(source_id)
                    WHERE s.case_id=NEW.case_id AND s.kind='laboratory'
                      AND f.source_organization=binding.source_organization AND f.source_system=binding.source_system
                      AND f.subject_reference='Patient/' || binding.source_subject_ref
                      AND f.report_reference='DiagnosticReport/' || s.document_id
                      AND f.specimen_reference='Specimen/' || s.specimen_id
                      AND encode(sha256(s.raw),'hex')=s.sha256
                ), lineage AS (
                    SELECT * FROM scoped WHERE source_id=NEW.latest_source_id AND state='current' AND sha256=NEW.latest_sha256
                    UNION ALL
                    SELECT p.* FROM scoped p JOIN lineage c ON p.source_id=c.supersedes_id
                    WHERE c.source_id<>NEW.original_source_id AND p.state='superseded' AND p.version=c.version-1
                      AND (p.document_id,p.event_date,p.specimen_id)=(c.document_id,c.event_date,c.specimen_id)
                )
                SELECT 1 FROM lineage WHERE source_id=NEW.original_source_id AND state='superseded'
            ) THEN RAISE EXCEPTION 'OI-LAB-AMENDMENT-SOURCE-LINEAGE'; END IF;

            IF NEW.action='respond' AND NOT EXISTS (
                SELECT 1 FROM investigation.laboratory_amendment_reviews r WHERE r.entry_id=NEW.request_id
                  AND r.action='request' AND r.actor<>NEW.actor
                  AND (r.patient_id,r.case_id,r.origin_org,r.purpose)=(NEW.patient_id,NEW.case_id,NEW.origin_org,NEW.purpose)
                  AND (r.task_id,r.question_id,r.original_source_id,r.latest_source_id,r.latest_sha256)=
                      (NEW.task_id,NEW.question_id,NEW.original_source_id,NEW.latest_source_id,NEW.latest_sha256)
            ) THEN RAISE EXCEPTION 'OI-LAB-AMENDMENT-RESPONSE-SCOPE'; END IF;
            IF (SELECT count(*) FROM investigation.laboratory_amendment_reviews
                WHERE case_id=NEW.case_id AND patient_id=NEW.patient_id)>=750 THEN
                RAISE EXCEPTION 'OI-LAB-AMENDMENT-CASE-LIMIT';
            END IF;
            RETURN NEW;
        END; $review$;
        CREATE TRIGGER oi_lab_amendment_insert BEFORE INSERT ON investigation.laboratory_amendment_reviews
            FOR EACH ROW EXECUTE FUNCTION investigation.guard_lab_amendment_review_insert();
        CREATE TRIGGER oi_lab_amendment_immutable BEFORE UPDATE OR DELETE ON investigation.laboratory_amendment_reviews
            FOR EACH ROW EXECUTE FUNCTION identity.reject_registry_history_mutation();
        CREATE TRIGGER oi_lab_amendment_no_truncate BEFORE TRUNCATE ON investigation.laboratory_amendment_reviews
            FOR EACH STATEMENT EXECUTE FUNCTION identity.reject_registry_history_mutation();
    """)


def downgrade():
    db = op.get_bind()
    db.exec_driver_sql("LOCK TABLE investigation.laboratory_amendment_reviews IN ACCESS EXCLUSIVE MODE")
    if db.exec_driver_sql("SELECT EXISTS (SELECT 1 FROM investigation.laboratory_amendment_reviews)").scalar_one():
        raise CommandError("Stored laboratory amendment review history requires explicit reconciliation before downgrade")
    db.exec_driver_sql("DROP TABLE investigation.laboratory_amendment_reviews")
    db.exec_driver_sql("DROP FUNCTION investigation.guard_lab_amendment_review_insert()")
