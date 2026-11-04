"""Durable second-opinion packet drafts over canonical sources and questions.

Packets preserve exact selected source versions and source-grounded questions.
They are preparation records only: no recipient verification, record transmission,
referral, appointment, clinical approval, or external side effect is created.
"""
from alembic import op
from alembic.util.exc import CommandError
from sqlalchemy import text

revision = "0012_second_opinion_packets"
down_revision = "0011_evidence_convergence"
branch_labels = None
depends_on = None


def upgrade():
    conn = op.get_bind()
    for schema, name in (
        ("coordination", "second_opinion_packets"),
        ("coordination", "second_opinion_packet_sources"),
        ("coordination", "second_opinion_packet_questions"),
        ("coordination", "guard_second_opinion_packet_insert"),
        ("coordination", "guard_second_opinion_packet_source_insert"),
        ("coordination", "guard_second_opinion_packet_question_insert"),
    ):
        existing = conn.execute(text(
            "SELECT 1 FROM pg_class c JOIN pg_namespace n ON n.oid=c.relnamespace "
            "WHERE n.nspname=:schema AND c.relname=:name UNION ALL "
            "SELECT 1 FROM pg_proc p JOIN pg_namespace n ON n.oid=p.pronamespace "
            "WHERE n.nspname=:schema AND p.proname=:name LIMIT 1"
        ), {"schema": schema, "name": name}).scalar_one_or_none()
        if existing is not None:
            raise CommandError("Existing second-opinion packet owner requires explicit reconciliation")

    conn.exec_driver_sql("""
        CREATE TABLE coordination.second_opinion_packets (
            packet_id text PRIMARY KEY CHECK (packet_id ~ '^SECONDOP-[0-9A-F]{32}$'),
            patient_id text NOT NULL REFERENCES identity.identity_patients(patient_id),
            case_id text NOT NULL REFERENCES coordination.patient_case_bindings(case_id),
            origin_org text NOT NULL,
            request_key text NOT NULL CHECK (char_length(request_key) BETWEEN 3 AND 128),
            intent_sha256 char(64) NOT NULL CHECK (intent_sha256 ~ '^[0-9a-f]{64}$'),
            actor text NOT NULL,
            purpose text NOT NULL CHECK (purpose='operations'),
            title text NOT NULL CHECK (
                char_length(title) BETWEEN 8 AND 300
                AND title=btrim(title)
                AND strpos(title,chr(10))=0
                AND strpos(title,chr(13))=0),
            source_snapshot_contract text NOT NULL
                CHECK (source_snapshot_contract='oi.pg-source-world-model/1'),
            source_snapshot_sha256 char(64) NOT NULL
                CHECK (source_snapshot_sha256 ~ '^[0-9a-f]{64}$'),
            created_at timestamptz NOT NULL DEFAULT now(),
            UNIQUE(patient_id,request_key)
        );

        CREATE TABLE coordination.second_opinion_packet_sources (
            packet_id text NOT NULL REFERENCES coordination.second_opinion_packets(packet_id),
            ordinal smallint NOT NULL CHECK (ordinal BETWEEN 1 AND 32),
            source_id text NOT NULL REFERENCES clinical_source.source_versions(source_id),
            source_version integer NOT NULL CHECK (source_version >= 1),
            source_sha256 char(64) NOT NULL CHECK (source_sha256 ~ '^[0-9a-f]{64}$'),
            PRIMARY KEY(packet_id,ordinal),
            UNIQUE(packet_id,source_id)
        );

        CREATE TABLE coordination.second_opinion_packet_questions (
            packet_id text NOT NULL REFERENCES coordination.second_opinion_packets(packet_id),
            ordinal smallint NOT NULL CHECK (ordinal BETWEEN 1 AND 16),
            question_id text NOT NULL REFERENCES investigation.source_questions(question_id),
            PRIMARY KEY(packet_id,ordinal),
            UNIQUE(packet_id,question_id)
        );

        CREATE INDEX idx_oi_second_opinion_case
          ON coordination.second_opinion_packets(patient_id,case_id,created_at,packet_id);

        CREATE FUNCTION coordination.guard_second_opinion_packet_insert()
        RETURNS trigger LANGUAGE plpgsql AS $oi_second_opinion_packet$
        BEGIN
          IF NOT EXISTS (
            SELECT 1
            FROM identity.identity_patients p
            JOIN coordination.patient_case_bindings b ON b.patient_id=p.patient_id
            WHERE p.patient_id=NEW.patient_id AND p.origin_org=NEW.origin_org
              AND p.status='active' AND b.case_id=NEW.case_id
              AND b.origin_org=NEW.origin_org AND b.status='active'
              AND b.purpose=NEW.purpose
          ) THEN RAISE EXCEPTION 'OI-SECOND-OPINION-PACKET-SCOPE'; END IF;
          RETURN NEW;
        END;
        $oi_second_opinion_packet$;

        CREATE FUNCTION coordination.guard_second_opinion_packet_source_insert()
        RETURNS trigger LANGUAGE plpgsql AS $oi_second_opinion_source$
        BEGIN
          IF NOT EXISTS (
            SELECT 1 FROM coordination.second_opinion_packets p
            JOIN clinical_source.source_versions s ON s.source_id=NEW.source_id
            WHERE p.packet_id=NEW.packet_id
              AND s.case_id=p.case_id
              AND s.version=NEW.source_version
              AND s.sha256=NEW.source_sha256
              AND s.state='current'
          ) THEN RAISE EXCEPTION 'OI-SECOND-OPINION-SOURCE-BOUNDARY'; END IF;
          RETURN NEW;
        END;
        $oi_second_opinion_source$;

        CREATE FUNCTION coordination.guard_second_opinion_packet_question_insert()
        RETURNS trigger LANGUAGE plpgsql AS $oi_second_opinion_question$
        BEGIN
          IF NOT EXISTS (
            SELECT 1 FROM coordination.second_opinion_packets p
            JOIN investigation.source_questions q ON q.question_id=NEW.question_id
            JOIN coordination.second_opinion_packet_sources s
              ON s.packet_id=p.packet_id AND s.source_id=q.source_id
            JOIN clinical_source.source_versions v ON v.source_id=q.source_id
            WHERE p.packet_id=NEW.packet_id
              AND q.patient_id=p.patient_id AND q.case_id=p.case_id
              AND q.origin_org=p.origin_org AND q.purpose='operations'
              AND q.source_snapshot_contract=p.source_snapshot_contract
              AND q.source_snapshot_sha256=p.source_snapshot_sha256
              AND v.state='current'
          ) THEN RAISE EXCEPTION 'OI-SECOND-OPINION-QUESTION-BOUNDARY'; END IF;
          RETURN NEW;
        END;
        $oi_second_opinion_question$;

        CREATE TRIGGER oi_second_opinion_packet_insert_guard
          BEFORE INSERT ON coordination.second_opinion_packets
          FOR EACH ROW EXECUTE FUNCTION coordination.guard_second_opinion_packet_insert();
        CREATE TRIGGER oi_second_opinion_packet_update_guard
          BEFORE UPDATE OR DELETE ON coordination.second_opinion_packets
          FOR EACH ROW EXECUTE FUNCTION identity.reject_registry_history_mutation();

        CREATE TRIGGER oi_second_opinion_source_insert_guard
          BEFORE INSERT ON coordination.second_opinion_packet_sources
          FOR EACH ROW EXECUTE FUNCTION coordination.guard_second_opinion_packet_source_insert();
        CREATE TRIGGER oi_second_opinion_source_history_guard
          BEFORE UPDATE OR DELETE ON coordination.second_opinion_packet_sources
          FOR EACH ROW EXECUTE FUNCTION identity.reject_registry_history_mutation();

        CREATE TRIGGER oi_second_opinion_question_insert_guard
          BEFORE INSERT ON coordination.second_opinion_packet_questions
          FOR EACH ROW EXECUTE FUNCTION coordination.guard_second_opinion_packet_question_insert();
        CREATE TRIGGER oi_second_opinion_question_history_guard
          BEFORE UPDATE OR DELETE ON coordination.second_opinion_packet_questions
          FOR EACH ROW EXECUTE FUNCTION identity.reject_registry_history_mutation();
    """)


def downgrade():
    conn = op.get_bind()
    if conn.execute(text("SELECT EXISTS(SELECT 1 FROM coordination.second_opinion_packets)")).scalar_one():
        raise CommandError("Second-opinion packet history requires explicit reconciliation before downgrade")
    for statement in (
        "DROP TABLE coordination.second_opinion_packet_questions",
        "DROP TABLE coordination.second_opinion_packet_sources",
        "DROP TABLE coordination.second_opinion_packets",
        "DROP FUNCTION coordination.guard_second_opinion_packet_question_insert()",
        "DROP FUNCTION coordination.guard_second_opinion_packet_source_insert()",
        "DROP FUNCTION coordination.guard_second_opinion_packet_insert()",
    ):
        conn.exec_driver_sql(statement)
