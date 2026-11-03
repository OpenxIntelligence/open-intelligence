"""Allowlisted DOI metadata on the existing evidence owner; developer opt-in only.

No article content, patient data egress, model-use rights or clinical approval.
Published fictional/catalog migrations remain unchanged.
"""
from alembic import op
from alembic.util.exc import CommandError
from sqlalchemy import text

revision = "0012_crossref_metadata"
down_revision = "0011_evidence_convergence"
branch_labels = None
depends_on = None


def upgrade():
    c = op.get_bind()
    c.exec_driver_sql("""
        ALTER TABLE investigation.evidence_catalog_records
            DROP CONSTRAINT evidence_catalog_records_record_id_check,
            DROP CONSTRAINT evidence_catalog_records_source_kind_check,
            DROP CONSTRAINT evidence_catalog_records_title_check,
            ADD CONSTRAINT evidence_catalog_provider_identity CHECK (
              (source_kind='fictional' AND record_id ~ '^FICT-[A-Z0-9-]+$' AND char_length(record_id)<=128 AND char_length(title) BETWEEN 1 AND 300)
              OR (source_kind='crossref' AND record_id ~ '^10[.][0-9]{4,9}/[a-z0-9._;()/+-]+$'
                  AND char_length(record_id)<=200 AND version ~ '^[0-9a-f]{64}$'
                  AND char_length(title) BETWEEN 1 AND 500)
            );
        CREATE TABLE investigation.crossref_metadata_projections (
            record_id text NOT NULL CHECK(record_id ~ '^10[.][0-9]{4,9}/'), version text NOT NULL,
            projection jsonb NOT NULL CHECK(jsonb_typeof(projection)='object'
                AND (projection - ARRAY['doi','title','journal','year','publication_type','authors','canonical_url'])='{}'::jsonb
                AND projection ?& ARRAY['doi','title','journal','year','publication_type','authors','canonical_url']),
            projection_sha256 char(64) NOT NULL CHECK(projection_sha256=version),
            first_retrieved_at timestamptz NOT NULL,
            origin_receipt_id text NOT NULL,
            adapter_version text NOT NULL CHECK(adapter_version='oi.crossref-metadata/1'),
            policy_sha256 char(64) NOT NULL CHECK(policy_sha256 ~ '^[0-9a-f]{64}$'),
            acquisition_mode text NOT NULL CHECK(acquisition_mode IN ('provider_lookup','protocol_fixture')),
            recorded_at timestamptz NOT NULL DEFAULT clock_timestamp(),
            PRIMARY KEY(record_id,version),
            FOREIGN KEY(record_id,version) REFERENCES investigation.evidence_catalog_records(record_id,version)
        );
        CREATE TABLE investigation.crossref_retrieval_receipts (
            receipt_id text PRIMARY KEY CHECK(receipt_id ~ '^EVIDENCE-RETRIEVAL-[0-9A-F]{32}$'),
            record_id text NOT NULL, version text NOT NULL,
            patient_id text NOT NULL REFERENCES identity.identity_patients(patient_id),
            case_id text NOT NULL REFERENCES coordination.patient_case_bindings(case_id),
            question_id text NOT NULL REFERENCES investigation.source_questions(question_id),
            origin_org text NOT NULL CHECK(char_length(origin_org) BETWEEN 3 AND 128),
            actor text NOT NULL CHECK(char_length(actor) BETWEEN 3 AND 128),
            purpose text NOT NULL CHECK(purpose='operations'),
            source_snapshot_sha256 char(64) NOT NULL CHECK(source_snapshot_sha256 ~ '^[0-9a-f]{64}$'),
            preflight_sha256 char(64) NOT NULL CHECK(preflight_sha256 ~ '^[0-9a-f]{64}$'),
            provider_retrieved_at timestamptz NOT NULL,
            adapter_version text NOT NULL CHECK(adapter_version='oi.crossref-metadata/1'),
            policy_sha256 char(64) NOT NULL CHECK(policy_sha256 ~ '^[0-9a-f]{64}$'),
            acquisition_mode text NOT NULL CHECK(acquisition_mode IN ('provider_lookup','protocol_fixture')),
            recorded_at timestamptz NOT NULL DEFAULT clock_timestamp(),
            FOREIGN KEY(record_id,version) REFERENCES investigation.crossref_metadata_projections(record_id,version),
            UNIQUE(receipt_id,record_id,version)
        );
        ALTER TABLE investigation.crossref_metadata_projections ADD CONSTRAINT crossref_projection_origin
            FOREIGN KEY(origin_receipt_id,record_id,version) REFERENCES
            investigation.crossref_retrieval_receipts(receipt_id,record_id,version)
            DEFERRABLE INITIALLY DEFERRED;
        CREATE INDEX idx_crossref_retrieval_scope ON investigation.crossref_retrieval_receipts
            (patient_id,case_id,question_id,recorded_at,receipt_id);
        CREATE OR REPLACE FUNCTION investigation.guard_evidence_rights_insert()
        RETURNS trigger LANGUAGE plpgsql AS $oi_rights$
        DECLARE latest integer;
        BEGIN
            IF NEW.record_id ~ '^10[.][0-9]{4,9}/' THEN
                PERFORM pg_advisory_xact_lock(hashtextextended('oi.crossref.doi:'||NEW.record_id,0));
            END IF;
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
        CREATE FUNCTION investigation.guard_crossref_retrieval_insert()
        RETURNS trigger LANGUAGE plpgsql AS $oi_retrieval$
        BEGIN
            PERFORM 1 FROM identity.identity_patients
                WHERE patient_id=NEW.patient_id AND origin_org=NEW.origin_org AND status='active' FOR SHARE;
            IF NOT FOUND THEN RAISE EXCEPTION 'OI-CROSSREF-PATIENT-BOUNDARY'; END IF;
            PERFORM 1 FROM coordination.patient_case_bindings
                WHERE case_id=NEW.case_id AND patient_id=NEW.patient_id
                  AND origin_org=NEW.origin_org AND purpose=NEW.purpose AND status='active' FOR UPDATE;
            IF NOT FOUND THEN RAISE EXCEPTION 'OI-CROSSREF-CASE-BOUNDARY'; END IF;
            IF NOT EXISTS (
                SELECT 1 FROM investigation.source_questions q
                JOIN clinical_source.source_versions s ON s.source_id=q.source_id
                WHERE q.question_id=NEW.question_id AND q.patient_id=NEW.patient_id
                  AND q.case_id=NEW.case_id AND q.origin_org=NEW.origin_org AND q.purpose=NEW.purpose
                  AND q.source_snapshot_sha256=NEW.source_snapshot_sha256
                  AND q.preflight_sha256=NEW.preflight_sha256 AND s.state='current'
                  AND s.case_id=q.case_id AND s.sha256=q.source_sha256
            ) THEN RAISE EXCEPTION 'OI-CROSSREF-QUESTION-BOUNDARY'; END IF;
            RETURN NEW;
        END;
        $oi_retrieval$;
        CREATE TRIGGER crossref_retrieval_scope BEFORE INSERT ON investigation.crossref_retrieval_receipts
            FOR EACH ROW EXECUTE FUNCTION investigation.guard_crossref_retrieval_insert();
    """)
    for table in ("crossref_metadata_projections", "crossref_retrieval_receipts"):
        c.exec_driver_sql(f"CREATE TRIGGER crossref_history_immutable BEFORE UPDATE OR DELETE ON investigation.{table} "
                         "FOR EACH ROW EXECUTE FUNCTION identity.reject_registry_history_mutation()")
        c.exec_driver_sql(f"CREATE TRIGGER crossref_history_no_truncate BEFORE TRUNCATE ON investigation.{table} "
                         "FOR EACH STATEMENT EXECUTE FUNCTION identity.reject_registry_history_mutation()")


def downgrade():
    c = op.get_bind()
    if c.execute(text("SELECT EXISTS(SELECT 1 FROM investigation.crossref_metadata_projections) OR "
                      "EXISTS(SELECT 1 FROM investigation.evidence_catalog_records WHERE source_kind='crossref')")).scalar_one():
        raise CommandError("Populated Crossref provenance cannot be downgraded")
    c.exec_driver_sql("ALTER TABLE investigation.crossref_metadata_projections DROP CONSTRAINT crossref_projection_origin")
    c.exec_driver_sql("DROP TABLE investigation.crossref_retrieval_receipts")
    c.exec_driver_sql("DROP FUNCTION investigation.guard_crossref_retrieval_insert()")
    c.exec_driver_sql("DROP TABLE investigation.crossref_metadata_projections")
    c.exec_driver_sql("""
        ALTER TABLE investigation.evidence_catalog_records DROP CONSTRAINT evidence_catalog_provider_identity,
          ADD CONSTRAINT evidence_catalog_records_record_id_check CHECK(record_id ~ '^FICT-[A-Z0-9-]+$' AND char_length(record_id)<=128),
          ADD CONSTRAINT evidence_catalog_records_source_kind_check CHECK(source_kind='fictional'),
          ADD CONSTRAINT evidence_catalog_records_title_check CHECK(char_length(title) BETWEEN 1 AND 300);
    """)
    # The extra lock branch is unreachable for the restored FICT-only schema;
    # keeping it preserves exactly the same effective predecessor behavior.
