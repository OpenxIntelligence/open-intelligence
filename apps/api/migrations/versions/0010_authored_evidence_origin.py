"""Bind immutable evidence objects to their exact creating command.

The published 0009 history stays unchanged. Its report command stored only the
whole intent digest, so a historical packet digest cannot be reconstructed by
inverting that hash. Migrated reports retain an explicit intent-digest-only
binding and their exact legacy renderer. New report origins require both the
expected packet digest and the renderer that includes frozen permissions.
"""
from alembic import op
from alembic.util.exc import CommandError
from sqlalchemy import text

revision = "0010_authored_evidence_origin"
down_revision = "0009_question_evidence"
branch_labels = None
depends_on = None

TARGETS = """
    SELECT 'assess'::text AS operation,assessment_id AS object_id,
           'assessment_id'::text AS id_field,patient_id,case_id,origin_org,question_id,actor,purpose
      FROM investigation.question_evidence_assessments
    UNION ALL
    SELECT 'report',report_id,'report_id',patient_id,case_id,origin_org,question_id,actor,purpose
      FROM investigation.question_evidence_reports
"""
MATCH = """
    c.operation=t.operation AND c.patient_id=t.patient_id AND c.case_id=t.case_id
    AND c.origin_org=t.origin_org AND c.actor=t.actor AND c.purpose=t.purpose
    AND c.result=jsonb_build_object(t.id_field,t.object_id,'question_id',t.question_id)
"""


def upgrade():
    conn = op.get_bind()
    for name in ("evidence_command_origins", "guard_evidence_command_origin_insert",
                 "require_evidence_command_origin"):
        existing = conn.execute(text(
            "SELECT 1 FROM pg_class c JOIN pg_namespace n ON n.oid=c.relnamespace "
            "WHERE n.nspname='investigation' AND c.relname=:name UNION ALL "
            "SELECT 1 FROM pg_proc p JOIN pg_namespace n ON n.oid=p.pronamespace "
            "WHERE n.nspname='investigation' AND p.proname=:name LIMIT 1"
        ), {"name": name}).scalar_one_or_none()
        if existing is not None:
            raise CommandError("Existing evidence origin owner requires explicit reconciliation")
    # Freeze the legacy targets/ledger while deriving their unique origins.
    # Deferred guards installed below also prevent a still-running old writer
    # from committing a new unbound object after the migration completes.
    conn.exec_driver_sql("LOCK TABLE investigation.question_evidence_assessments, "
                         "investigation.question_evidence_reports, investigation.evidence_commands "
                         "IN SHARE ROW EXCLUSIVE MODE")
    ambiguous = conn.execute(text(f"""
        WITH targets AS ({TARGETS})
        SELECT 1 FROM targets t LEFT JOIN investigation.evidence_commands c ON {MATCH}
        GROUP BY t.operation,t.object_id HAVING count(c.request_key)!=1 LIMIT 1
    """)).scalar_one_or_none()
    if ambiguous is not None:
        raise CommandError("Missing or ambiguous evidence creating command requires explicit reconciliation")
    conn.exec_driver_sql("""
        CREATE TABLE investigation.evidence_command_origins (
            operation text NOT NULL CHECK (operation IN ('assess','report')),
            object_id text NOT NULL,
            patient_id text NOT NULL REFERENCES identity.identity_patients(patient_id),
            case_id text NOT NULL REFERENCES coordination.patient_case_bindings(case_id),
            origin_org text NOT NULL,
            question_id text NOT NULL REFERENCES investigation.source_questions(question_id),
            request_key text NOT NULL,
            intent_sha256 char(64) NOT NULL CHECK (intent_sha256 ~ '^[0-9a-f]{64}$'),
            expected_packet_sha256 char(64) CHECK (expected_packet_sha256 ~ '^[0-9a-f]{64}$'),
            packet_binding text NOT NULL,
            report_renderer text,
            actor text NOT NULL,
            purpose text NOT NULL CHECK (purpose='operations'),
            recorded_at timestamptz NOT NULL DEFAULT clock_timestamp(),
            PRIMARY KEY (operation,object_id),
            UNIQUE (patient_id,case_id,operation,request_key),
            FOREIGN KEY (patient_id,case_id,operation,request_key)
              REFERENCES investigation.evidence_commands(patient_id,case_id,operation,request_key),
            CHECK (
                (operation='assess' AND object_id ~ '^ASSESSMENT-[0-9A-F]{32}$'
                    AND packet_binding='not_applicable' AND expected_packet_sha256 IS NULL AND report_renderer IS NULL)
                OR (operation='report' AND object_id ~ '^REPORT-[0-9A-F]{32}$' AND (
                    (packet_binding='intent_digest_only' AND expected_packet_sha256 IS NULL
                        AND report_renderer='oi.h1-evidence-text/1')
                    OR (packet_binding='explicit_digest' AND expected_packet_sha256 IS NOT NULL
                        AND report_renderer='oi.h1-evidence-text/2')
                ))
            )
        );
    """)
    # Only new metadata is inserted. No original, comparison, report, command,
    # event, body hash, snapshot hash or actor attribution is rewritten.
    conn.exec_driver_sql(f"""
        WITH targets AS ({TARGETS})
        INSERT INTO investigation.evidence_command_origins
          (operation,object_id,patient_id,case_id,origin_org,question_id,request_key,
           intent_sha256,expected_packet_sha256,packet_binding,report_renderer,actor,purpose)
        SELECT t.operation,t.object_id,t.patient_id,t.case_id,t.origin_org,t.question_id,c.request_key,
               c.intent_sha256,NULL,
               CASE WHEN t.operation='assess' THEN 'not_applicable' ELSE 'intent_digest_only' END,
               CASE WHEN t.operation='report' THEN 'oi.h1-evidence-text/1' ELSE NULL END,t.actor,t.purpose
        FROM targets t JOIN investigation.evidence_commands c ON {MATCH};
    """)
    conn.exec_driver_sql("""
        CREATE FUNCTION investigation.guard_evidence_command_origin_insert() RETURNS trigger
        LANGUAGE plpgsql AS $oi_origin$
        BEGIN
            IF NOT EXISTS (
                SELECT 1 FROM investigation.evidence_commands c
                WHERE c.patient_id=NEW.patient_id AND c.case_id=NEW.case_id
                  AND c.origin_org=NEW.origin_org AND c.actor=NEW.actor AND c.purpose=NEW.purpose
                  AND c.operation=NEW.operation AND c.request_key=NEW.request_key
                  AND c.intent_sha256=NEW.intent_sha256
                  AND c.result=jsonb_build_object(
                      CASE WHEN NEW.operation='assess' THEN 'assessment_id' ELSE 'report_id' END,
                      NEW.object_id,'question_id',NEW.question_id)
            ) THEN RAISE EXCEPTION 'OI-EVIDENCE-ORIGIN-COMMAND'; END IF;
            IF NEW.operation='assess' THEN
                IF NOT EXISTS (
                    SELECT 1 FROM investigation.question_evidence_assessments a
                    WHERE a.assessment_id=NEW.object_id AND a.patient_id=NEW.patient_id
                      AND a.case_id=NEW.case_id AND a.origin_org=NEW.origin_org
                      AND a.question_id=NEW.question_id AND a.actor=NEW.actor AND a.purpose=NEW.purpose
                ) THEN RAISE EXCEPTION 'OI-EVIDENCE-ORIGIN-ASSESSMENT'; END IF;
            ELSE
                IF NEW.packet_binding!='explicit_digest' OR NEW.expected_packet_sha256 IS NULL
                    OR NEW.report_renderer!='oi.h1-evidence-text/2' OR NOT EXISTS (
                    SELECT 1 FROM investigation.question_evidence_reports r
                    WHERE r.report_id=NEW.object_id AND r.patient_id=NEW.patient_id
                      AND r.case_id=NEW.case_id AND r.origin_org=NEW.origin_org
                      AND r.question_id=NEW.question_id AND r.actor=NEW.actor AND r.purpose=NEW.purpose
                ) THEN RAISE EXCEPTION 'OI-EVIDENCE-ORIGIN-REPORT'; END IF;
            END IF;
            RETURN NEW;
        END; $oi_origin$;
        CREATE FUNCTION investigation.require_evidence_command_origin() RETURNS trigger
        LANGUAGE plpgsql AS $oi_origin$
        DECLARE operation_name text; object_ref text;
        BEGIN
            IF TG_TABLE_NAME='question_evidence_assessments' THEN
                operation_name := 'assess'; object_ref := NEW.assessment_id;
            ELSIF TG_TABLE_NAME='question_evidence_reports' THEN
                operation_name := 'report'; object_ref := NEW.report_id;
            ELSE RAISE EXCEPTION 'OI-EVIDENCE-ORIGIN-OWNER'; END IF;
            IF NOT EXISTS (
                SELECT 1 FROM investigation.evidence_command_origins o
                WHERE o.operation=operation_name AND o.object_id=object_ref
                  AND o.patient_id=NEW.patient_id AND o.case_id=NEW.case_id
                  AND o.origin_org=NEW.origin_org AND o.question_id=NEW.question_id
                  AND o.actor=NEW.actor AND o.purpose=NEW.purpose
            ) THEN RAISE EXCEPTION 'OI-EVIDENCE-CREATING-COMMAND-REQUIRED'; END IF;
            RETURN NEW;
        END; $oi_origin$;
        CREATE CONSTRAINT TRIGGER oi_evidence_origin_required
          AFTER INSERT ON investigation.question_evidence_assessments
          DEFERRABLE INITIALLY DEFERRED FOR EACH ROW
          EXECUTE FUNCTION investigation.require_evidence_command_origin();
        CREATE CONSTRAINT TRIGGER oi_evidence_origin_required
          AFTER INSERT ON investigation.question_evidence_reports
          DEFERRABLE INITIALLY DEFERRED FOR EACH ROW
          EXECUTE FUNCTION investigation.require_evidence_command_origin();
        CREATE TRIGGER oi_evidence_scope_guard BEFORE INSERT ON investigation.evidence_command_origins
          FOR EACH ROW EXECUTE FUNCTION investigation.guard_case_evidence_scope();
        CREATE TRIGGER oi_evidence_origin_insert_guard BEFORE INSERT ON investigation.evidence_command_origins
          FOR EACH ROW EXECUTE FUNCTION investigation.guard_evidence_command_origin_insert();
        CREATE TRIGGER oi_evidence_update_guard BEFORE UPDATE ON investigation.evidence_command_origins
          FOR EACH ROW EXECUTE FUNCTION identity.reject_registry_history_mutation();
        CREATE TRIGGER oi_evidence_delete_guard BEFORE DELETE ON investigation.evidence_command_origins
          FOR EACH ROW EXECUTE FUNCTION identity.reject_registry_history_mutation();
    """)


def downgrade():
    conn = op.get_bind()
    if conn.execute(text("SELECT EXISTS(SELECT 1 FROM investigation.evidence_command_origins)")).scalar_one():
        raise CommandError("Evidence command origins require explicit reconciliation before downgrade")
    conn.exec_driver_sql("DROP TRIGGER oi_evidence_origin_required ON investigation.question_evidence_assessments")
    conn.exec_driver_sql("DROP TRIGGER oi_evidence_origin_required ON investigation.question_evidence_reports")
    conn.exec_driver_sql("DROP TABLE investigation.evidence_command_origins")
    conn.exec_driver_sql("DROP FUNCTION investigation.require_evidence_command_origin()")
    conn.exec_driver_sql("DROP FUNCTION investigation.guard_evidence_command_origin_insert()")
