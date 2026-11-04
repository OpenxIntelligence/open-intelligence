"""Versioned fictional metadata, rights history and canonical question citations.

Adapts WS-06 / #224's evidence contract to the existing PostgreSQL owner.
No real content, new patient table, clinical interpretation or model execution.
"""
from alembic import op
from alembic.util.exc import CommandError
from sqlalchemy import text

revision = "0010_question_evidence"
down_revision = "0009_question_followthrough"
branch_labels = None
depends_on = None


def upgrade():
    connection = op.get_bind()
    for name in ("evidence_catalog_records", "evidence_rights_decisions", "question_evidence_links",
                 "guard_evidence_rights_insert", "guard_question_evidence_insert"):
        existing = connection.execute(text(
            "SELECT 1 FROM pg_class c JOIN pg_namespace n ON n.oid=c.relnamespace "
            "WHERE n.nspname='investigation' AND c.relname=:name "
            "UNION ALL SELECT 1 FROM pg_proc p JOIN pg_namespace n ON n.oid=p.pronamespace "
            "WHERE n.nspname='investigation' AND p.proname=:name LIMIT 1"
        ), {"name": name}).scalar_one_or_none()
        if existing is not None:
            raise CommandError("Existing evidence owner requires explicit reconciliation")
    connection.exec_driver_sql("""
        CREATE TABLE investigation.evidence_catalog_records (
            record_id text NOT NULL CHECK(record_id ~ '^FICT-[A-Z0-9-]+$' AND char_length(record_id)<=128),
            version text NOT NULL CHECK(version ~ '^[A-Za-z0-9._-]+$' AND char_length(version)<=64),
            source_kind text NOT NULL CHECK(source_kind='fictional'),
            title text NOT NULL CHECK(char_length(title) BETWEEN 1 AND 300),
            terms jsonb NOT NULL CHECK(jsonb_typeof(terms)='array' AND jsonb_array_length(terms)<=32),
            licence text NOT NULL CHECK(char_length(licence) BETWEEN 1 AND 128),
            link text NOT NULL CHECK(char_length(link)<=512),
            case_id text, organization text,
            metadata_sha256 char(64) NOT NULL CHECK(metadata_sha256 ~ '^[0-9a-f]{64}$'),
            created_at timestamptz NOT NULL DEFAULT clock_timestamp(),
            PRIMARY KEY(record_id,version),
            CHECK((case_id IS NULL AND organization IS NULL) OR
                  (case_id IS NOT NULL AND organization IS NOT NULL
                   AND char_length(case_id) BETWEEN 3 AND 128
                   AND char_length(organization) BETWEEN 3 AND 128))
        );
        CREATE TABLE investigation.evidence_rights_decisions (
            decision_id text PRIMARY KEY CHECK(decision_id ~ '^EVIDENCE-RIGHTS-[0-9A-F]{32}$'),
            record_id text NOT NULL, version text NOT NULL,
            revision integer NOT NULL CHECK(revision>0),
            permissions jsonb NOT NULL CHECK(jsonb_typeof(permissions)='object'),
            revoked boolean NOT NULL, superseded boolean NOT NULL,
            recorded_by text NOT NULL CHECK(char_length(recorded_by) BETWEEN 3 AND 128),
            reason text NOT NULL CHECK(char_length(reason) BETWEEN 3 AND 500),
            recorded_at timestamptz NOT NULL DEFAULT clock_timestamp(),
            FOREIGN KEY(record_id,version) REFERENCES investigation.evidence_catalog_records(record_id,version),
            UNIQUE(record_id,version,revision)
        );
        CREATE FUNCTION investigation.guard_evidence_rights_insert()
        RETURNS trigger LANGUAGE plpgsql AS $oi_rights$
        DECLARE latest integer;
        BEGIN
            -- Catalog readers take SHARE on this same immutable record. An
            -- append-only rights change cannot pass a prepared disclosure.
            PERFORM 1 FROM investigation.evidence_catalog_records
                WHERE record_id=NEW.record_id AND version=NEW.version FOR UPDATE;
            IF NOT FOUND THEN RAISE EXCEPTION 'OI-EVIDENCE-UNKNOWN-RECORD'; END IF;
            SELECT COALESCE(max(revision),0) INTO latest
                FROM investigation.evidence_rights_decisions
                WHERE record_id=NEW.record_id AND version=NEW.version;
            IF NEW.revision!=latest+1 THEN RAISE EXCEPTION 'OI-EVIDENCE-RIGHTS-REVISION'; END IF;
            RETURN NEW;
        END;
        $oi_rights$;
        CREATE TRIGGER evidence_rights_serial
            BEFORE INSERT ON investigation.evidence_rights_decisions FOR EACH ROW
            EXECUTE FUNCTION investigation.guard_evidence_rights_insert();

        CREATE TABLE investigation.question_evidence_links (
            link_id text PRIMARY KEY CHECK(link_id ~ '^EVIDENCE-LINK-[0-9A-F]{32}$'),
            patient_id text NOT NULL REFERENCES identity.identity_patients(patient_id),
            case_id text NOT NULL REFERENCES coordination.patient_case_bindings(case_id),
            question_id text NOT NULL REFERENCES investigation.source_questions(question_id),
            origin_org text NOT NULL, actor text NOT NULL,
            purpose text NOT NULL CHECK(purpose='operations'),
            request_key text NOT NULL CHECK(char_length(request_key) BETWEEN 3 AND 128),
            intent_sha256 char(64) NOT NULL CHECK(intent_sha256 ~ '^[0-9a-f]{64}$'),
            record_id text NOT NULL, version text NOT NULL,
            metadata_sha256 char(64) NOT NULL CHECK(metadata_sha256 ~ '^[0-9a-f]{64}$'),
            source_snapshot_contract text NOT NULL CHECK(source_snapshot_contract='oi.pg-source-world-model/1'),
            source_snapshot_sha256 char(64) NOT NULL CHECK(source_snapshot_sha256 ~ '^[0-9a-f]{64}$'),
            preflight_sha256 char(64) NOT NULL CHECK(preflight_sha256 ~ '^[0-9a-f]{64}$'),
            created_at timestamptz NOT NULL DEFAULT clock_timestamp(),
            FOREIGN KEY(record_id,version) REFERENCES investigation.evidence_catalog_records(record_id,version),
            UNIQUE(patient_id,request_key)
        );
        CREATE INDEX idx_question_evidence_scope ON investigation.question_evidence_links
            (patient_id,case_id,question_id,created_at,link_id);
        CREATE FUNCTION investigation.guard_question_evidence_insert()
        RETURNS trigger LANGUAGE plpgsql AS $oi_link$
        BEGIN
            PERFORM 1 FROM identity.identity_patients p
                WHERE p.patient_id=NEW.patient_id AND p.origin_org=NEW.origin_org
                  AND p.status='active' FOR SHARE;
            IF NOT FOUND THEN RAISE EXCEPTION 'OI-EVIDENCE-PATIENT-BOUNDARY'; END IF;
            PERFORM 1 FROM coordination.patient_case_bindings b
                WHERE b.case_id=NEW.case_id AND b.patient_id=NEW.patient_id
                  AND b.origin_org=NEW.origin_org AND b.status='active'
                  AND b.purpose=NEW.purpose FOR UPDATE;
            IF NOT FOUND THEN RAISE EXCEPTION 'OI-EVIDENCE-CASE-BOUNDARY'; END IF;
            IF NOT EXISTS (
                SELECT 1 FROM investigation.source_questions q
                JOIN clinical_source.source_versions s ON s.source_id=q.source_id
                WHERE q.question_id=NEW.question_id AND q.patient_id=NEW.patient_id
                  AND q.case_id=NEW.case_id AND q.origin_org=NEW.origin_org
                  AND q.purpose=NEW.purpose AND s.state='current'
                  AND s.case_id=q.case_id AND s.sha256=q.source_sha256
                  AND q.source_snapshot_contract=NEW.source_snapshot_contract
                  AND q.source_snapshot_sha256=NEW.source_snapshot_sha256
                  AND q.preflight_sha256=NEW.preflight_sha256
            ) THEN RAISE EXCEPTION 'OI-EVIDENCE-QUESTION-BOUNDARY'; END IF;
            IF NOT EXISTS (
                SELECT 1 FROM investigation.evidence_catalog_records e
                WHERE e.record_id=NEW.record_id AND e.version=NEW.version
                  AND e.metadata_sha256=NEW.metadata_sha256
                  AND ((e.case_id IS NULL AND e.organization IS NULL)
                       OR (e.case_id=NEW.case_id AND e.organization=NEW.origin_org))
            ) THEN RAISE EXCEPTION 'OI-EVIDENCE-CATALOG-BOUNDARY'; END IF;
            IF (SELECT count(*) FROM investigation.question_evidence_links
                WHERE question_id=NEW.question_id)>=100 THEN
                RAISE EXCEPTION 'OI-EVIDENCE-LINK-LIMIT';
            END IF;
            RETURN NEW;
        END;
        $oi_link$;
        CREATE TRIGGER question_evidence_scope
            BEFORE INSERT ON investigation.question_evidence_links FOR EACH ROW
            EXECUTE FUNCTION investigation.guard_question_evidence_insert();
    """)
    for table in ("evidence_catalog_records", "evidence_rights_decisions", "question_evidence_links"):
        connection.exec_driver_sql(
            f"CREATE TRIGGER evidence_history_immutable BEFORE UPDATE OR DELETE ON investigation.{table} "
            "FOR EACH ROW EXECUTE FUNCTION identity.reject_registry_history_mutation()"
        )


def downgrade():
    connection = op.get_bind()
    populated = connection.execute(text(
        "SELECT EXISTS(SELECT 1 FROM investigation.question_evidence_links) "
        "OR EXISTS(SELECT 1 FROM investigation.evidence_catalog_records)"
    )).scalar_one()
    if populated:
        raise CommandError("Populated evidence history cannot be downgraded")
    connection.exec_driver_sql("DROP TABLE investigation.question_evidence_links")
    connection.exec_driver_sql("DROP FUNCTION investigation.guard_question_evidence_insert()")
    connection.exec_driver_sql("DROP TABLE investigation.evidence_rights_decisions")
    connection.exec_driver_sql("DROP FUNCTION investigation.guard_evidence_rights_insert()")
    connection.exec_driver_sql("DROP TABLE investigation.evidence_catalog_records")
