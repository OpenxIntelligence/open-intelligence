"""Durable synthetic Composer execution over existing H1 question/source owners.

This is the PostgreSQL continuation of the Composer run contract. It neither
reuses human follow-through tasks as jobs nor adds patient/source authority.
"""
from alembic import op
from alembic.util.exc import CommandError
from sqlalchemy import text


revision = "0019_composer_runs"
down_revision = "0018_laboratory_questions"
branch_labels = None
depends_on = None


def upgrade():
    conn = op.get_bind()
    for name in (
        "composer_tool_runs", "composer_tool_run_events", "composer_tool_run_results",
        "guard_composer_run", "guard_composer_run_event", "guard_composer_run_result",
        "require_composer_run_consistency",
    ):
        existing = conn.execute(text(
            "SELECT 1 FROM pg_class c JOIN pg_namespace n ON n.oid=c.relnamespace "
            "WHERE n.nspname='investigation' AND c.relname=:name UNION ALL "
            "SELECT 1 FROM pg_proc p JOIN pg_namespace n ON n.oid=p.pronamespace "
            "WHERE n.nspname='investigation' AND p.proname=:name LIMIT 1"
        ), {"name": name}).scalar_one_or_none()
        if existing is not None:
            raise CommandError("Existing Composer execution owner requires explicit reconciliation")

    conn.exec_driver_sql("""
        CREATE TABLE investigation.composer_tool_runs (
            run_id text PRIMARY KEY CHECK (run_id ~ '^RUN-[0-9A-F]{32}$'),
            patient_id text NOT NULL REFERENCES identity.identity_patients(patient_id),
            case_id text NOT NULL REFERENCES coordination.patient_case_bindings(case_id),
            question_id text NOT NULL REFERENCES investigation.source_questions(question_id),
            origin_org text NOT NULL CHECK (char_length(origin_org) BETWEEN 3 AND 128),
            actor text NOT NULL CHECK (char_length(actor) BETWEEN 3 AND 128),
            purpose text NOT NULL CHECK (purpose='operations'),
            kind text NOT NULL CHECK (kind='source-question-brief/1'),
            source_snapshot_contract text NOT NULL
                CHECK (source_snapshot_contract='oi.pg-source-world-model/1'),
            source_snapshot_sha256 char(64) NOT NULL CHECK (source_snapshot_sha256 ~ '^[0-9a-f]{64}$'),
            preflight_sha256 char(64) NOT NULL CHECK (preflight_sha256 ~ '^[0-9a-f]{64}$'),
            source_id text NOT NULL CHECK (source_id ~ '^SRC-[0-9A-F]{32}$'),
            source_version integer NOT NULL CHECK (source_version>=1),
            source_sha256 char(64) NOT NULL CHECK (source_sha256 ~ '^[0-9a-f]{64}$'),
            source_line integer NOT NULL CHECK (source_line BETWEEN 1 AND 10000),
            request_key text NOT NULL CHECK (char_length(request_key) BETWEEN 3 AND 128),
            request_digest char(64) NOT NULL CHECK (request_digest ~ '^[0-9a-f]{64}$'),
            state text NOT NULL DEFAULT 'queued'
                CHECK (state IN ('queued','running','completed','blocked','stale','cancelled','failed')),
            revision integer NOT NULL DEFAULT 1 CHECK (revision>=1),
            attempt_count integer NOT NULL DEFAULT 0 CHECK (attempt_count BETWEEN 0 AND 3),
            max_attempts integer NOT NULL DEFAULT 3 CHECK (max_attempts=3),
            lease_token text CHECK (lease_token ~ '^LEASE-[0-9A-F]{32}$'),
            lease_expires_at timestamptz,
            available_at timestamptz NOT NULL DEFAULT clock_timestamp(),
            created_at timestamptz NOT NULL DEFAULT clock_timestamp(),
            updated_at timestamptz NOT NULL DEFAULT clock_timestamp(),
            UNIQUE (origin_org,actor,purpose,request_key),
            FOREIGN KEY (source_id,source_line)
                REFERENCES clinical_source.assertions(source_id,source_line),
            CHECK ((state='running' AND lease_token IS NOT NULL AND lease_expires_at IS NOT NULL
                    AND attempt_count>=1)
                   OR (state<>'running' AND lease_token IS NULL AND lease_expires_at IS NULL)),
            CHECK (state<>'queued' OR attempt_count<max_attempts),
            CHECK (state NOT IN ('completed','failed') OR attempt_count>=1)
        );
        CREATE INDEX idx_oi_composer_run_scope ON investigation.composer_tool_runs
            (patient_id,case_id,question_id,created_at,run_id);
        CREATE INDEX idx_oi_composer_run_claim ON investigation.composer_tool_runs
            (origin_org,actor,purpose,patient_id,case_id,state,available_at,lease_expires_at,run_id);

        CREATE TABLE investigation.composer_tool_run_events (
            id bigserial PRIMARY KEY,
            run_id text NOT NULL REFERENCES investigation.composer_tool_runs(run_id),
            revision integer NOT NULL CHECK (revision>=1),
            state text NOT NULL
                CHECK (state IN ('queued','running','completed','blocked','stale','cancelled','failed')),
            attempt_count integer NOT NULL CHECK (attempt_count BETWEEN 0 AND 3),
            reason_code text NOT NULL CHECK (reason_code IN (
                'queued','claimed','lease_recovered','retryable_failure','attempts_exhausted',
                'completed','cancelled','source_changed','authority_unavailable','invalid_output')),
            created_at timestamptz NOT NULL DEFAULT clock_timestamp(),
            UNIQUE (run_id,revision)
        );

        CREATE TABLE investigation.composer_tool_run_results (
            run_id text PRIMARY KEY REFERENCES investigation.composer_tool_runs(run_id),
            result_json jsonb NOT NULL
                CHECK (jsonb_typeof(result_json)='object' AND octet_length(result_json::text)<=131072),
            result_sha256 char(64) NOT NULL CHECK (result_sha256 ~ '^[0-9a-f]{64}$'),
            created_at timestamptz NOT NULL DEFAULT clock_timestamp()
        );

        CREATE FUNCTION investigation.guard_composer_run() RETURNS trigger
        LANGUAGE plpgsql AS $oi_composer_run$
        DECLARE stamp timestamptz := clock_timestamp();
        BEGIN
            IF TG_OP='INSERT' THEN
                IF NEW.state IS DISTINCT FROM 'queued' OR NEW.revision IS DISTINCT FROM 1
                   OR NEW.attempt_count IS DISTINCT FROM 0 OR NEW.max_attempts IS DISTINCT FROM 3
                   OR NEW.lease_token IS NOT NULL OR NEW.lease_expires_at IS NOT NULL THEN
                    RAISE EXCEPTION 'OI-COMPOSER-INITIAL-STATE';
                END IF;
                -- Preserve the source owner's patient SHARE -> binding UPDATE
                -- order. The binding lock serializes source amendment/revocation.
                PERFORM 1 FROM identity.identity_patients p
                    WHERE p.patient_id=NEW.patient_id AND p.origin_org=NEW.origin_org
                      AND p.status='active' FOR SHARE;
                IF NOT FOUND THEN RAISE EXCEPTION 'OI-COMPOSER-PATIENT-BOUNDARY'; END IF;
                PERFORM 1 FROM coordination.patient_case_bindings b
                    WHERE b.case_id=NEW.case_id AND b.patient_id=NEW.patient_id
                      AND b.origin_org=NEW.origin_org AND b.status='active'
                      AND b.purpose=NEW.purpose FOR UPDATE;
                IF NOT FOUND THEN RAISE EXCEPTION 'OI-COMPOSER-CASE-BOUNDARY'; END IF;
                IF NOT EXISTS (
                    SELECT 1 FROM investigation.source_questions q
                    JOIN clinical_source.source_versions s ON s.source_id=q.source_id
                    WHERE q.question_id=NEW.question_id AND q.patient_id=NEW.patient_id
                      AND q.case_id=NEW.case_id AND q.origin_org=NEW.origin_org
                      AND q.purpose=NEW.purpose AND q.source_line IS NOT NULL
                      AND q.source_snapshot_contract=NEW.source_snapshot_contract
                      AND q.source_snapshot_sha256=NEW.source_snapshot_sha256
                      AND q.preflight_sha256=NEW.preflight_sha256
                      AND q.source_id=NEW.source_id AND q.source_line=NEW.source_line
                      AND q.source_version=NEW.source_version AND q.source_sha256=NEW.source_sha256
                      AND s.case_id=NEW.case_id AND s.state='current'
                      AND s.version=NEW.source_version AND s.sha256=NEW.source_sha256
                ) THEN RAISE EXCEPTION 'OI-COMPOSER-QUESTION-SOURCE-BOUNDARY'; END IF;
                NEW.created_at := stamp;
                NEW.updated_at := stamp;
                NEW.available_at := stamp;
                RETURN NEW;
            END IF;

            IF ROW(NEW.run_id,NEW.patient_id,NEW.case_id,NEW.question_id,NEW.origin_org,NEW.actor,
                   NEW.purpose,NEW.kind,NEW.source_snapshot_contract,NEW.source_snapshot_sha256,
                   NEW.preflight_sha256,NEW.source_id,NEW.source_version,NEW.source_sha256,
                   NEW.source_line,NEW.request_key,NEW.request_digest,NEW.max_attempts,NEW.created_at)
               IS DISTINCT FROM
               ROW(OLD.run_id,OLD.patient_id,OLD.case_id,OLD.question_id,OLD.origin_org,OLD.actor,
                   OLD.purpose,OLD.kind,OLD.source_snapshot_contract,OLD.source_snapshot_sha256,
                   OLD.preflight_sha256,OLD.source_id,OLD.source_version,OLD.source_sha256,
                   OLD.source_line,OLD.request_key,OLD.request_digest,OLD.max_attempts,OLD.created_at) THEN
                RAISE EXCEPTION 'OI-COMPOSER-INTENT-IMMUTABLE';
            END IF;
            IF OLD.state IN ('completed','blocked','stale','cancelled','failed') THEN
                RAISE EXCEPTION 'OI-COMPOSER-TERMINAL';
            END IF;
            IF NEW.revision IS DISTINCT FROM OLD.revision+1 THEN
                RAISE EXCEPTION 'OI-COMPOSER-REVISION';
            END IF;

            IF NEW.state='running' THEN
                IF OLD.state NOT IN ('queued','running')
                   OR OLD.attempt_count>=OLD.max_attempts
                   OR NEW.attempt_count IS DISTINCT FROM OLD.attempt_count+1 THEN
                    RAISE EXCEPTION 'OI-COMPOSER-ATTEMPT';
                END IF;
                IF NEW.lease_token IS NULL OR NEW.lease_expires_at IS NULL
                   OR NEW.lease_token IS NOT DISTINCT FROM OLD.lease_token
                   OR NEW.lease_expires_at<=stamp
                   OR NEW.lease_expires_at>stamp+interval '300 seconds'
                   OR (OLD.state='running' AND OLD.lease_expires_at>stamp)
                   OR (OLD.state='queued' AND OLD.available_at>stamp) THEN
                    RAISE EXCEPTION 'OI-COMPOSER-LEASE';
                END IF;
            ELSE
                IF NEW.attempt_count IS DISTINCT FROM OLD.attempt_count
                   OR NEW.lease_token IS NOT NULL OR NEW.lease_expires_at IS NOT NULL THEN
                    RAISE EXCEPTION 'OI-COMPOSER-LIFECYCLE';
                END IF;
                IF NEW.state='queued' THEN
                    IF OLD.state<>'running' OR OLD.attempt_count>=OLD.max_attempts
                       OR OLD.lease_expires_at<=stamp OR NEW.available_at<=stamp
                       OR NEW.available_at>stamp+interval '60 seconds' THEN
                        RAISE EXCEPTION 'OI-COMPOSER-RETRY';
                    END IF;
                ELSIF NEW.state='completed' THEN
                    IF OLD.state<>'running' OR OLD.lease_token IS NULL
                       OR OLD.lease_expires_at IS NULL OR OLD.lease_expires_at<=stamp THEN
                        RAISE EXCEPTION 'OI-COMPOSER-LEASE';
                    END IF;
                ELSIF NEW.state='failed' THEN
                    IF OLD.state<>'running' THEN RAISE EXCEPTION 'OI-COMPOSER-LIFECYCLE'; END IF;
                ELSIF NEW.state NOT IN ('blocked','stale','cancelled') THEN
                    RAISE EXCEPTION 'OI-COMPOSER-LIFECYCLE';
                END IF;
            END IF;
            NEW.updated_at := stamp;
            RETURN NEW;
        END;
        $oi_composer_run$;

        CREATE FUNCTION investigation.guard_composer_run_event() RETURNS trigger
        LANGUAGE plpgsql AS $oi_composer_event$
        DECLARE
            run_row investigation.composer_tool_runs%ROWTYPE;
            prior investigation.composer_tool_run_events%ROWTYPE;
            valid_reason boolean := false;
        BEGIN
            SELECT * INTO run_row FROM investigation.composer_tool_runs
                WHERE run_id=NEW.run_id FOR UPDATE;
            IF NOT FOUND OR NEW.revision IS DISTINCT FROM run_row.revision
               OR NEW.state IS DISTINCT FROM run_row.state
               OR NEW.attempt_count IS DISTINCT FROM run_row.attempt_count THEN
                RAISE EXCEPTION 'OI-COMPOSER-EVENT-STATE';
            END IF;
            SELECT * INTO prior FROM investigation.composer_tool_run_events
                WHERE run_id=NEW.run_id ORDER BY revision DESC LIMIT 1;
            IF NEW.revision IS DISTINCT FROM COALESCE(prior.revision,0)+1 THEN
                RAISE EXCEPTION 'OI-COMPOSER-EVENT-REVISION';
            END IF;
            IF NEW.revision=1 THEN
                valid_reason := NEW.state='queued' AND NEW.attempt_count=0 AND NEW.reason_code='queued';
            ELSIF NEW.state='running' THEN
                valid_reason := NEW.attempt_count=prior.attempt_count+1
                    AND ((prior.state='queued' AND NEW.reason_code='claimed')
                         OR (prior.state='running' AND NEW.reason_code='lease_recovered'));
            ELSE
                valid_reason := NEW.attempt_count=prior.attempt_count AND
                    CASE NEW.state
                        WHEN 'queued' THEN prior.state='running' AND NEW.reason_code='retryable_failure'
                        WHEN 'completed' THEN prior.state='running' AND NEW.reason_code='completed'
                        WHEN 'cancelled' THEN NEW.reason_code='cancelled'
                        WHEN 'stale' THEN NEW.reason_code='source_changed'
                        WHEN 'blocked' THEN NEW.reason_code='authority_unavailable'
                        WHEN 'failed' THEN prior.state='running' AND
                            ((NEW.reason_code='attempts_exhausted' AND NEW.attempt_count=run_row.max_attempts)
                             OR (NEW.reason_code='invalid_output' AND NEW.attempt_count>=1))
                        ELSE false
                    END;
            END IF;
            IF valid_reason IS NOT TRUE THEN RAISE EXCEPTION 'OI-COMPOSER-EVENT-REASON'; END IF;
            NEW.created_at := clock_timestamp();
            RETURN NEW;
        END;
        $oi_composer_event$;

        CREATE FUNCTION investigation.guard_composer_run_result() RETURNS trigger
        LANGUAGE plpgsql AS $oi_composer_result$
        BEGIN
            NEW.created_at := clock_timestamp();
            RETURN NEW;
        END;
        $oi_composer_result$;

        CREATE FUNCTION investigation.require_composer_run_consistency() RETURNS trigger
        LANGUAGE plpgsql AS $oi_composer_consistency$
        DECLARE
            run_row investigation.composer_tool_runs%ROWTYPE;
            latest investigation.composer_tool_run_events%ROWTYPE;
            event_count bigint;
            has_result boolean;
        BEGIN
            -- Each run image, including intermediate transitions within one
            -- transaction, requires its own exact append-only lifecycle event.
            IF TG_TABLE_NAME='composer_tool_runs' THEN
                IF NOT EXISTS (
                    SELECT 1 FROM investigation.composer_tool_run_events e
                    WHERE e.run_id=NEW.run_id AND e.revision=NEW.revision
                      AND e.state=NEW.state AND e.attempt_count=NEW.attempt_count
                ) THEN RAISE EXCEPTION 'OI-COMPOSER-RUN-HISTORY'; END IF;
            END IF;
            SELECT * INTO run_row FROM investigation.composer_tool_runs WHERE run_id=NEW.run_id;
            IF NOT FOUND THEN RAISE EXCEPTION 'OI-COMPOSER-RUN-HISTORY'; END IF;
            SELECT * INTO latest FROM investigation.composer_tool_run_events
                WHERE run_id=NEW.run_id ORDER BY revision DESC LIMIT 1;
            SELECT count(*) INTO event_count FROM investigation.composer_tool_run_events
                WHERE run_id=NEW.run_id;
            IF latest.revision IS DISTINCT FROM run_row.revision
               OR latest.state IS DISTINCT FROM run_row.state
               OR latest.attempt_count IS DISTINCT FROM run_row.attempt_count
               OR event_count<>run_row.revision THEN
                RAISE EXCEPTION 'OI-COMPOSER-RUN-HISTORY';
            END IF;
            has_result := EXISTS (SELECT 1 FROM investigation.composer_tool_run_results
                                  WHERE run_id=NEW.run_id);
            IF (run_row.state='completed') IS DISTINCT FROM has_result THEN
                RAISE EXCEPTION 'OI-COMPOSER-RUN-RESULT';
            END IF;
            RETURN NULL;
        END;
        $oi_composer_consistency$;

        CREATE TRIGGER oi_composer_run_guard BEFORE INSERT OR UPDATE ON investigation.composer_tool_runs
            FOR EACH ROW EXECUTE FUNCTION investigation.guard_composer_run();
        CREATE TRIGGER oi_composer_run_delete_guard BEFORE DELETE ON investigation.composer_tool_runs
            FOR EACH ROW EXECUTE FUNCTION identity.reject_registry_history_mutation();
        CREATE TRIGGER oi_composer_run_no_truncate BEFORE TRUNCATE ON investigation.composer_tool_runs
            FOR EACH STATEMENT EXECUTE FUNCTION identity.reject_registry_history_mutation();
        CREATE TRIGGER oi_composer_run_event_guard BEFORE INSERT ON investigation.composer_tool_run_events
            FOR EACH ROW EXECUTE FUNCTION investigation.guard_composer_run_event();
        CREATE TRIGGER oi_composer_run_event_immutable BEFORE UPDATE OR DELETE ON investigation.composer_tool_run_events
            FOR EACH ROW EXECUTE FUNCTION identity.reject_registry_history_mutation();
        CREATE TRIGGER oi_composer_run_event_no_truncate BEFORE TRUNCATE ON investigation.composer_tool_run_events
            FOR EACH STATEMENT EXECUTE FUNCTION identity.reject_registry_history_mutation();
        CREATE TRIGGER oi_composer_run_result_guard BEFORE INSERT ON investigation.composer_tool_run_results
            FOR EACH ROW EXECUTE FUNCTION investigation.guard_composer_run_result();
        CREATE TRIGGER oi_composer_run_result_immutable BEFORE UPDATE OR DELETE ON investigation.composer_tool_run_results
            FOR EACH ROW EXECUTE FUNCTION identity.reject_registry_history_mutation();
        CREATE TRIGGER oi_composer_run_result_no_truncate BEFORE TRUNCATE ON investigation.composer_tool_run_results
            FOR EACH STATEMENT EXECUTE FUNCTION identity.reject_registry_history_mutation();

        CREATE CONSTRAINT TRIGGER oi_composer_run_consistency
            AFTER INSERT OR UPDATE ON investigation.composer_tool_runs
            DEFERRABLE INITIALLY DEFERRED FOR EACH ROW
            EXECUTE FUNCTION investigation.require_composer_run_consistency();
        CREATE CONSTRAINT TRIGGER oi_composer_run_event_consistency
            AFTER INSERT ON investigation.composer_tool_run_events
            DEFERRABLE INITIALLY DEFERRED FOR EACH ROW
            EXECUTE FUNCTION investigation.require_composer_run_consistency();
        CREATE CONSTRAINT TRIGGER oi_composer_run_result_consistency
            AFTER INSERT ON investigation.composer_tool_run_results
            DEFERRABLE INITIALLY DEFERRED FOR EACH ROW
            EXECUTE FUNCTION investigation.require_composer_run_consistency();
    """)


def downgrade():
    conn = op.get_bind()
    conn.exec_driver_sql(
        "LOCK TABLE investigation.composer_tool_runs, investigation.composer_tool_run_events, "
        "investigation.composer_tool_run_results IN ACCESS EXCLUSIVE MODE"
    )
    if conn.exec_driver_sql("""
        SELECT EXISTS(SELECT 1 FROM investigation.composer_tool_runs)
            OR EXISTS(SELECT 1 FROM investigation.composer_tool_run_events)
            OR EXISTS(SELECT 1 FROM investigation.composer_tool_run_results)
    """).scalar_one():
        raise CommandError("Stored Composer execution history requires explicit reconciliation")
    conn.exec_driver_sql("""
        DROP TABLE investigation.composer_tool_run_results;
        DROP TABLE investigation.composer_tool_run_events;
        DROP TABLE investigation.composer_tool_runs;
        DROP FUNCTION investigation.require_composer_run_consistency();
        DROP FUNCTION investigation.guard_composer_run_result();
        DROP FUNCTION investigation.guard_composer_run_event();
        DROP FUNCTION investigation.guard_composer_run();
    """)
