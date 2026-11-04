"""Case-owned fictional evidence, human proposals and immutable report snapshots.

Distinct from the parallel 0009_question_followthrough owner. Convergence must
merge migration heads explicitly; no existing revision is rewritten.
"""
from alembic import op
from alembic.util.exc import CommandError
from sqlalchemy import text

revision = "0009_question_evidence"
down_revision = "0008_review_convergence"
branch_labels = None
depends_on = None

TABLES = ("case_evidence_versions", "case_evidence_withdrawals",
          "question_evidence_assessments", "question_evidence_reports", "evidence_commands")


def upgrade():
    conn = op.get_bind()
    for name in (*TABLES, "guard_case_evidence_scope", "guard_case_evidence_version",
                 "guard_case_evidence_withdrawal", "guard_question_evidence_assessment",
                 "guard_question_evidence_report"):
        existing = conn.execute(text(
            "SELECT 1 FROM pg_class c JOIN pg_namespace n ON n.oid=c.relnamespace "
            "WHERE n.nspname='investigation' AND c.relname=:name UNION ALL "
            "SELECT 1 FROM pg_proc p JOIN pg_namespace n ON n.oid=p.pronamespace "
            "WHERE n.nspname='investigation' AND p.proname=:name LIMIT 1"
        ), {"name": name}).scalar_one_or_none()
        if existing is not None:
            raise CommandError("Existing evidence owner requires explicit reconciliation")
    conn.exec_driver_sql("""
        CREATE TABLE investigation.case_evidence_versions (
            evidence_id text PRIMARY KEY CHECK (evidence_id ~ '^EVIDENCE-[0-9A-F]{32}$'),
            patient_id text NOT NULL REFERENCES identity.identity_patients(patient_id),
            case_id text NOT NULL REFERENCES coordination.patient_case_bindings(case_id),
            origin_org text NOT NULL,
            evidence_key text NOT NULL,
            version integer NOT NULL CHECK (version>=1),
            supersedes_id text REFERENCES investigation.case_evidence_versions(evidence_id),
            original_bytes bytea NOT NULL CHECK (octet_length(original_bytes) BETWEEN 1 AND 32768),
            sha256 char(64) NOT NULL CHECK (sha256 ~ '^[0-9a-f]{64}$'),
            title text NOT NULL CHECK (char_length(title) BETWEEN 4 AND 180),
            issued_at date NOT NULL,
            statement text NOT NULL CHECK (char_length(statement) BETWEEN 10 AND 1200),
            statement_line integer NOT NULL CHECK (statement_line BETWEEN 1 AND 10000),
            content_item text NOT NULL CHECK (content_item IN ('abstract','full_text','api_output')),
            permissions jsonb NOT NULL CHECK (jsonb_typeof(permissions)='object'),
            rights_sha256 char(64) NOT NULL CHECK (rights_sha256 ~ '^[0-9a-f]{64}$'),
            actor text NOT NULL,
            purpose text NOT NULL CHECK (purpose='operations'),
            created_at timestamptz NOT NULL DEFAULT clock_timestamp(),
            UNIQUE (patient_id,case_id,origin_org,evidence_key,version),
            UNIQUE (patient_id,case_id,origin_org,evidence_key,sha256)
        );
        CREATE TABLE investigation.case_evidence_withdrawals (
            withdrawal_id text PRIMARY KEY CHECK (withdrawal_id ~ '^WITHDRAWAL-[0-9A-F]{32}$'),
            evidence_id text NOT NULL UNIQUE REFERENCES investigation.case_evidence_versions(evidence_id),
            patient_id text NOT NULL REFERENCES identity.identity_patients(patient_id),
            case_id text NOT NULL REFERENCES coordination.patient_case_bindings(case_id),
            origin_org text NOT NULL,
            reason text NOT NULL CHECK (char_length(reason) BETWEEN 10 AND 600),
            actor text NOT NULL,
            purpose text NOT NULL CHECK (purpose='operations'),
            created_at timestamptz NOT NULL DEFAULT clock_timestamp()
        );
        CREATE TABLE investigation.question_evidence_assessments (
            assessment_id text PRIMARY KEY CHECK (assessment_id ~ '^ASSESSMENT-[0-9A-F]{32}$'),
            sequence_id bigint GENERATED ALWAYS AS IDENTITY UNIQUE,
            patient_id text NOT NULL REFERENCES identity.identity_patients(patient_id),
            case_id text NOT NULL REFERENCES coordination.patient_case_bindings(case_id),
            origin_org text NOT NULL,
            question_id text NOT NULL REFERENCES investigation.source_questions(question_id),
            evidence_id text NOT NULL REFERENCES investigation.case_evidence_versions(evidence_id),
            evidence_sha256 char(64) NOT NULL CHECK (evidence_sha256 ~ '^[0-9a-f]{64}$'),
            rights_sha256 char(64) NOT NULL CHECK (rights_sha256 ~ '^[0-9a-f]{64}$'),
            source_snapshot_sha256 char(64) NOT NULL CHECK (source_snapshot_sha256 ~ '^[0-9a-f]{64}$'),
            preflight_sha256 char(64) NOT NULL CHECK (preflight_sha256 ~ '^[0-9a-f]{64}$'),
            relation text NOT NULL CHECK (relation IN ('supports','contradicts','context','unknown')),
            applicability text NOT NULL CHECK (applicability IN ('applicable','limited','not_applicable','unknown')),
            quote text NOT NULL CHECK (char_length(quote) BETWEEN 1 AND 400),
            quote_start integer NOT NULL CHECK (quote_start BETWEEN 0 AND 1200),
            rationale text NOT NULL CHECK (char_length(rationale) BETWEEN 10 AND 600),
            actor text NOT NULL,
            purpose text NOT NULL CHECK (purpose='operations'),
            created_at timestamptz NOT NULL DEFAULT clock_timestamp(),
            CHECK (NOT (relation='supports' AND applicability='not_applicable'))
        );
        CREATE TABLE investigation.question_evidence_reports (
            report_id text PRIMARY KEY CHECK (report_id ~ '^REPORT-[0-9A-F]{32}$'),
            patient_id text NOT NULL REFERENCES identity.identity_patients(patient_id),
            case_id text NOT NULL REFERENCES coordination.patient_case_bindings(case_id),
            origin_org text NOT NULL,
            question_id text NOT NULL REFERENCES investigation.source_questions(question_id),
            prepared_at timestamptz NOT NULL,
            body text NOT NULL CHECK (octet_length(body) BETWEEN 1 AND 131072),
            body_sha256 char(64) NOT NULL CHECK (body_sha256 ~ '^[0-9a-f]{64}$'),
            snapshot jsonb NOT NULL CHECK (jsonb_typeof(snapshot)='object'),
            snapshot_sha256 char(64) NOT NULL CHECK (snapshot_sha256 ~ '^[0-9a-f]{64}$'),
            actor text NOT NULL,
            purpose text NOT NULL CHECK (purpose='operations'),
            created_at timestamptz NOT NULL DEFAULT clock_timestamp()
        );
        CREATE TABLE investigation.evidence_commands (
            patient_id text NOT NULL REFERENCES identity.identity_patients(patient_id),
            case_id text NOT NULL REFERENCES coordination.patient_case_bindings(case_id),
            origin_org text NOT NULL,
            operation text NOT NULL CHECK (operation IN ('import','withdraw','assess','report')),
            request_key text NOT NULL CHECK (char_length(request_key) BETWEEN 3 AND 128),
            intent_sha256 char(64) NOT NULL CHECK (intent_sha256 ~ '^[0-9a-f]{64}$'),
            result jsonb NOT NULL CHECK (jsonb_typeof(result)='object'),
            actor text NOT NULL,
            purpose text NOT NULL CHECK (purpose='operations'),
            created_at timestamptz NOT NULL DEFAULT clock_timestamp(),
            PRIMARY KEY (patient_id,case_id,operation,request_key)
        );
        CREATE INDEX oi_case_evidence_versions_scope ON investigation.case_evidence_versions
            (patient_id,case_id,origin_org,evidence_key,version);
        CREATE INDEX oi_question_evidence_assessment_scope ON investigation.question_evidence_assessments
            (patient_id,case_id,question_id,sequence_id);
        CREATE INDEX oi_question_evidence_report_scope ON investigation.question_evidence_reports
            (patient_id,case_id,question_id,prepared_at,report_id);

        CREATE FUNCTION investigation.guard_case_evidence_scope() RETURNS trigger
        LANGUAGE plpgsql AS $oi_evidence$
        BEGIN
            IF NOT EXISTS (
                SELECT 1 FROM identity.identity_patients p
                JOIN coordination.patient_case_bindings b ON b.patient_id=p.patient_id
                WHERE p.patient_id=NEW.patient_id AND p.origin_org=NEW.origin_org AND p.status='active'
                  AND b.case_id=NEW.case_id AND b.origin_org=NEW.origin_org AND b.status='active'
                  AND b.purpose=NEW.purpose
            ) THEN RAISE EXCEPTION 'OI-EVIDENCE-SCOPE-BOUNDARY'; END IF;
            RETURN NEW;
        END; $oi_evidence$;

        CREATE FUNCTION investigation.guard_case_evidence_version() RETURNS trigger
        LANGUAGE plpgsql AS $oi_evidence$
        DECLARE previous investigation.case_evidence_versions%ROWTYPE;
        BEGIN
            SELECT * INTO previous FROM investigation.case_evidence_versions
                WHERE patient_id=NEW.patient_id AND case_id=NEW.case_id AND origin_org=NEW.origin_org
                  AND evidence_key=NEW.evidence_key ORDER BY version DESC LIMIT 1;
            IF NOT FOUND THEN
                IF NEW.version!=1 OR NEW.supersedes_id IS NOT NULL THEN
                    RAISE EXCEPTION 'OI-EVIDENCE-VERSION-BOUNDARY'; END IF;
            ELSE
                IF NEW.version!=previous.version+1 OR NEW.supersedes_id IS DISTINCT FROM previous.evidence_id
                   OR EXISTS (SELECT 1 FROM investigation.case_evidence_withdrawals w
                              WHERE w.evidence_id=previous.evidence_id) THEN
                    RAISE EXCEPTION 'OI-EVIDENCE-VERSION-BOUNDARY'; END IF;
            END IF;
            RETURN NEW;
        END; $oi_evidence$;

        CREATE FUNCTION investigation.guard_case_evidence_withdrawal() RETURNS trigger
        LANGUAGE plpgsql AS $oi_evidence$
        BEGIN
            IF NOT EXISTS (
                SELECT 1 FROM investigation.case_evidence_versions e
                WHERE e.evidence_id=NEW.evidence_id AND e.patient_id=NEW.patient_id
                  AND e.case_id=NEW.case_id AND e.origin_org=NEW.origin_org
                  AND NOT EXISTS (SELECT 1 FROM investigation.case_evidence_versions newer
                     WHERE newer.case_id=e.case_id AND newer.evidence_key=e.evidence_key
                       AND newer.version>e.version)
            ) THEN RAISE EXCEPTION 'OI-EVIDENCE-WITHDRAWAL-BOUNDARY'; END IF;
            RETURN NEW;
        END; $oi_evidence$;

        CREATE FUNCTION investigation.guard_question_evidence_assessment() RETURNS trigger
        LANGUAGE plpgsql AS $oi_evidence$
        BEGIN
            IF NOT EXISTS (
                SELECT 1 FROM investigation.source_questions q
                JOIN clinical_source.source_versions s ON s.source_id=q.source_id
                JOIN investigation.case_evidence_versions e ON e.evidence_id=NEW.evidence_id
                WHERE q.question_id=NEW.question_id AND q.patient_id=NEW.patient_id
                  AND q.case_id=NEW.case_id AND q.origin_org=NEW.origin_org
                  AND q.source_snapshot_contract='oi.pg-source-world-model/1'
                  AND q.source_snapshot_sha256=NEW.source_snapshot_sha256
                  AND q.preflight_sha256=NEW.preflight_sha256
                  AND s.state='current' AND s.sha256=q.source_sha256 AND s.version=q.source_version
                  AND e.patient_id=NEW.patient_id AND e.case_id=NEW.case_id AND e.origin_org=NEW.origin_org
                  AND e.sha256=NEW.evidence_sha256 AND e.rights_sha256=NEW.rights_sha256
                  AND substring(e.statement FROM NEW.quote_start+1 FOR char_length(NEW.quote))=NEW.quote
                  AND NOT EXISTS (SELECT 1 FROM investigation.case_evidence_versions newer
                      WHERE newer.case_id=e.case_id AND newer.evidence_key=e.evidence_key AND newer.version>e.version)
                  AND NOT EXISTS (SELECT 1 FROM investigation.case_evidence_withdrawals w WHERE w.evidence_id=e.evidence_id)
            ) THEN RAISE EXCEPTION 'OI-EVIDENCE-ASSESSMENT-BOUNDARY'; END IF;
            RETURN NEW;
        END; $oi_evidence$;

        CREATE FUNCTION investigation.guard_question_evidence_report() RETURNS trigger
        LANGUAGE plpgsql AS $oi_evidence$
        BEGIN
            IF NOT EXISTS (
                SELECT 1 FROM investigation.source_questions q
                WHERE q.question_id=NEW.question_id AND q.patient_id=NEW.patient_id
                  AND q.case_id=NEW.case_id AND q.origin_org=NEW.origin_org
                  AND NEW.snapshot->'question'->>'question_id'=q.question_id
                  AND NEW.snapshot->'question'->>'patient_id'=q.patient_id
                  AND NEW.snapshot->'question'->>'case_id'=q.case_id
                  AND NEW.snapshot->'question'->>'source_snapshot_sha256'=q.source_snapshot_sha256
            ) THEN RAISE EXCEPTION 'OI-EVIDENCE-REPORT-BOUNDARY'; END IF;
            RETURN NEW;
        END; $oi_evidence$;
    """)
    for table in TABLES:
        conn.exec_driver_sql(f"""
            CREATE TRIGGER oi_evidence_scope_guard BEFORE INSERT ON investigation.{table}
              FOR EACH ROW EXECUTE FUNCTION investigation.guard_case_evidence_scope();
            CREATE TRIGGER oi_evidence_update_guard BEFORE UPDATE ON investigation.{table}
              FOR EACH ROW EXECUTE FUNCTION identity.reject_registry_history_mutation();
            CREATE TRIGGER oi_evidence_delete_guard BEFORE DELETE ON investigation.{table}
              FOR EACH ROW EXECUTE FUNCTION identity.reject_registry_history_mutation();
        """)
    for table, function in (
        ("case_evidence_versions", "guard_case_evidence_version"),
        ("case_evidence_withdrawals", "guard_case_evidence_withdrawal"),
        ("question_evidence_assessments", "guard_question_evidence_assessment"),
        ("question_evidence_reports", "guard_question_evidence_report"),
    ):
        conn.exec_driver_sql(f"CREATE TRIGGER oi_evidence_content_guard BEFORE INSERT ON investigation.{table} "
                             f"FOR EACH ROW EXECUTE FUNCTION investigation.{function}()")


def downgrade():
    conn = op.get_bind()
    if any(conn.execute(text(f"SELECT EXISTS(SELECT 1 FROM investigation.{table})")).scalar_one()
           for table in TABLES):
        raise CommandError("Evidence history requires explicit reconciliation before downgrade")
    for table in reversed(TABLES):
        conn.exec_driver_sql(f"DROP TABLE investigation.{table}")
    for name in ("guard_case_evidence_scope", "guard_case_evidence_version", "guard_case_evidence_withdrawal",
                 "guard_question_evidence_assessment", "guard_question_evidence_report"):
        conn.exec_driver_sql(f"DROP FUNCTION investigation.{name}()")
