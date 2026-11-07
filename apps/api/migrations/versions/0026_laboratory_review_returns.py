"""Bind canonical human return receipts to exact reopened laboratory inspections."""
from alembic import op
from alembic.util.exc import CommandError

revision = "0026_laboratory_review_returns"
down_revision = "0025_lab_inspection_snapshots"
branch_labels = None
depends_on = None

LAB = "oi.laboratory-inspection-review-return/1"


def upgrade():
    op.get_bind().exec_driver_sql(f"""
        ALTER TABLE investigation.question_review_receipts DROP CONSTRAINT oi_review_fingerprint_provenance;
        ALTER TABLE investigation.question_review_receipts ADD CONSTRAINT oi_review_fingerprint_provenance CHECK (
            (source_snapshot_contract='oi.synthetic-postgres-world-model-sources/1'
                AND queue_fingerprint_contract='oi.synthetic-source-review-return/1')
            OR (source_snapshot_contract='oi.pg-source-world-model/1'
                AND queue_fingerprint_contract IN ('oi.synthetic-source-review-return/2','{LAB}')));
        CREATE TABLE investigation.laboratory_review_origins (
            receipt_id text PRIMARY KEY REFERENCES investigation.question_review_receipts(receipt_id)
                DEFERRABLE INITIALLY DEFERRED,
            snapshot_id text NOT NULL REFERENCES investigation.laboratory_inspection_snapshots(snapshot_id),
            captured_report_sha256 text NOT NULL CHECK(captured_report_sha256 ~ '^[a-f0-9]{{64}}$'),
            report_sha256 text NOT NULL CHECK(report_sha256 ~ '^[a-f0-9]{{64}}$'),
            source_context_state text NOT NULL CHECK(source_context_state IN
                ('current_unreviewed_question','source_reassessment_required')),
            source_access_receipt_id text NOT NULL UNIQUE CHECK(source_access_receipt_id ~ '^ACCESS-[0-9A-F]{{32}}$')
        );
        CREATE INDEX oi_lab_review_snapshot ON investigation.laboratory_review_origins(snapshot_id,receipt_id);
        CREATE TRIGGER oi_lab_review_immutable BEFORE UPDATE OR DELETE ON investigation.laboratory_review_origins
            FOR EACH ROW EXECUTE FUNCTION identity.reject_registry_history_mutation();
        CREATE TRIGGER oi_lab_review_no_truncate BEFORE TRUNCATE ON investigation.laboratory_review_origins
            FOR EACH STATEMENT EXECUTE FUNCTION identity.reject_registry_history_mutation();

        -- Retain the original text guard and its provenance checks byte-for-byte.
        DROP TRIGGER oi_review_return_insert_guard ON investigation.question_review_receipts;
        CREATE TRIGGER oi_review_return_insert_guard BEFORE INSERT ON investigation.question_review_receipts
            FOR EACH ROW WHEN (NEW.queue_fingerprint_contract<>'{LAB}')
            EXECUTE FUNCTION investigation.guard_review_return_insert();
        DROP TRIGGER oi_anchor_text_question_required ON investigation.question_review_receipts;
        CREATE TRIGGER oi_anchor_text_question_required BEFORE INSERT ON investigation.question_review_receipts
            FOR EACH ROW WHEN (NEW.queue_fingerprint_contract<>'{LAB}')
            EXECUTE FUNCTION investigation.require_text_question_target();

        CREATE FUNCTION investigation.guard_laboratory_review_return() RETURNS trigger
        LANGUAGE plpgsql AS $guard$
        DECLARE origin investigation.laboratory_review_origins%ROWTYPE;
        DECLARE snapshot investigation.laboratory_inspection_snapshots%ROWTYPE;
        BEGIN
            IF current_setting('transaction_isolation') <> 'read committed' THEN
                RAISE EXCEPTION 'OI-LAB-REVIEW-READ-COMMITTED-REQUIRED';
            END IF;
            SELECT * INTO origin FROM investigation.laboratory_review_origins WHERE receipt_id=NEW.receipt_id;
            IF NOT FOUND THEN RAISE EXCEPTION 'OI-LAB-REVIEW-ORIGIN-REQUIRED'; END IF;
            SELECT * INTO snapshot FROM investigation.laboratory_inspection_snapshots WHERE snapshot_id=origin.snapshot_id;
            IF NOT FOUND OR snapshot.patient_id IS DISTINCT FROM NEW.patient_id
                OR snapshot.case_id IS DISTINCT FROM NEW.case_id OR snapshot.question_id IS DISTINCT FROM NEW.question_id
                OR snapshot.origin_org IS DISTINCT FROM NEW.origin_org OR snapshot.purpose IS DISTINCT FROM NEW.purpose
                OR snapshot.captured_report_sha256 IS DISTINCT FROM origin.captured_report_sha256
                OR NEW.source_snapshot_contract IS DISTINCT FROM 'oi.pg-source-world-model/1'
                OR NEW.source_snapshot_sha256 IS DISTINCT FROM snapshot.manifest #>> '{{anchor,source_snapshot_sha256}}'
                THEN RAISE EXCEPTION 'OI-LAB-REVIEW-SNAPSHOT-BOUNDARY'; END IF;
            PERFORM 1 FROM identity.identity_patients p WHERE p.patient_id=NEW.patient_id
                AND p.origin_org=NEW.origin_org AND p.status='active' FOR SHARE;
            IF NOT FOUND THEN RAISE EXCEPTION 'OI-LAB-REVIEW-SCOPE'; END IF;
            PERFORM 1 FROM coordination.patient_case_bindings b WHERE b.patient_id=NEW.patient_id
                AND b.case_id=NEW.case_id AND b.origin_org=NEW.origin_org AND b.purpose=NEW.purpose
                AND b.status='active' FOR UPDATE;
            IF NOT FOUND THEN RAISE EXCEPTION 'OI-LAB-REVIEW-SCOPE'; END IF;
            PERFORM 1 FROM investigation.source_questions q
                JOIN investigation.laboratory_question_anchors a USING(question_id)
                JOIN clinical_source.source_versions s ON s.source_id=q.source_id AND s.case_id=q.case_id
                    AND s.version=q.source_version AND s.sha256=q.source_sha256 AND s.kind='laboratory'
                WHERE q.question_id=NEW.question_id AND q.patient_id=NEW.patient_id AND q.case_id=NEW.case_id
                    AND q.origin_org=NEW.origin_org AND q.purpose=NEW.purpose AND q.source_line IS NULL
                    AND a.source_id=q.source_id AND q.source_snapshot_sha256=NEW.source_snapshot_sha256
                    AND q.source_snapshot_contract=NEW.source_snapshot_contract
                    AND (s.state='current' OR origin.source_context_state='source_reassessment_required');
            IF NOT FOUND THEN RAISE EXCEPTION 'OI-LAB-REVIEW-QUESTION-BOUNDARY'; END IF;
            -- The normal report owner has held source and metadata-rights locks
            -- through this same-transaction reopening and the eventual commit.
            IF NOT EXISTS (SELECT 1 FROM identity.identity_domain_events j
                WHERE j.xmin=pg_current_xact_id()::xid AND j.patient_id=NEW.patient_id
                    AND j.event_type='investigation.laboratory_snapshot.reopened'
                    AND j.metadata_json->>'case_id'=NEW.case_id AND j.metadata_json->>'question_id'=NEW.question_id
                    AND j.metadata_json->>'snapshot_id'=origin.snapshot_id AND j.metadata_json->>'actor'=NEW.actor
                    AND j.metadata_json->>'source_access_receipt_id'=origin.source_access_receipt_id
                    AND j.metadata_json->>'captured_report_sha256'=origin.captured_report_sha256
                    AND j.metadata_json->>'report_sha256'=origin.report_sha256
                    AND j.metadata_json->>'source_context_state'=origin.source_context_state
            ) THEN RAISE EXCEPTION 'OI-LAB-REVIEW-REOPEN-REQUIRED'; END IF;
            IF (SELECT count(*) FROM investigation.question_review_receipts
                WHERE patient_id=NEW.patient_id AND case_id=NEW.case_id AND origin_org=NEW.origin_org)>=750
                THEN RAISE EXCEPTION 'OI-LAB-REVIEW-LIMIT'; END IF;
            IF (SELECT count(*) FROM investigation.laboratory_review_origins
                WHERE snapshot_id=origin.snapshot_id)>100 THEN RAISE EXCEPTION 'OI-LAB-REVIEW-LIMIT'; END IF;
            RETURN NEW;
        END;
        $guard$;
        CREATE TRIGGER oi_laboratory_review_insert BEFORE INSERT ON investigation.question_review_receipts
            FOR EACH ROW WHEN (NEW.queue_fingerprint_contract='{LAB}')
            EXECUTE FUNCTION investigation.guard_laboratory_review_return();
        -- A child cannot be attached to an existing text receipt after its insert.
        CREATE FUNCTION investigation.check_laboratory_review_origin() RETURNS trigger
        LANGUAGE plpgsql AS $guard$
        BEGIN
            IF NOT EXISTS (SELECT 1 FROM investigation.question_review_receipts r
                JOIN investigation.laboratory_inspection_snapshots s ON s.snapshot_id=NEW.snapshot_id
                WHERE r.receipt_id=NEW.receipt_id AND r.queue_fingerprint_contract='{LAB}'
                    AND r.patient_id=s.patient_id AND r.case_id=s.case_id AND r.question_id=s.question_id
                    AND r.origin_org=s.origin_org AND r.purpose=s.purpose
                    AND s.captured_report_sha256=NEW.captured_report_sha256)
                THEN RAISE EXCEPTION 'OI-LAB-REVIEW-ORIGIN-BOUNDARY'; END IF;
            RETURN NEW;
        END;
        $guard$;
        CREATE CONSTRAINT TRIGGER oi_lab_review_origin_valid AFTER INSERT ON investigation.laboratory_review_origins
            DEFERRABLE INITIALLY DEFERRED FOR EACH ROW
            EXECUTE FUNCTION investigation.check_laboratory_review_origin();
    """)


def downgrade():
    conn = op.get_bind()
    conn.exec_driver_sql("LOCK TABLE investigation.question_review_receipts, investigation.laboratory_review_origins IN ACCESS EXCLUSIVE MODE")
    if conn.exec_driver_sql(f"SELECT EXISTS(SELECT 1 FROM investigation.laboratory_review_origins) OR EXISTS("
                           f"SELECT 1 FROM investigation.question_review_receipts WHERE queue_fingerprint_contract='{LAB}')").scalar_one():
        raise CommandError("Stored laboratory review receipts require explicit reconciliation")
    conn.exec_driver_sql(f"""
        DROP TRIGGER oi_laboratory_review_insert ON investigation.question_review_receipts;
        DROP FUNCTION investigation.guard_laboratory_review_return();
        DROP TABLE investigation.laboratory_review_origins;
        DROP FUNCTION investigation.check_laboratory_review_origin();
        DROP TRIGGER oi_review_return_insert_guard ON investigation.question_review_receipts;
        CREATE TRIGGER oi_review_return_insert_guard BEFORE INSERT ON investigation.question_review_receipts
            FOR EACH ROW EXECUTE FUNCTION investigation.guard_review_return_insert();
        DROP TRIGGER oi_anchor_text_question_required ON investigation.question_review_receipts;
        CREATE TRIGGER oi_anchor_text_question_required BEFORE INSERT ON investigation.question_review_receipts
            FOR EACH ROW EXECUTE FUNCTION investigation.require_text_question_target();
        ALTER TABLE investigation.question_review_receipts DROP CONSTRAINT oi_review_fingerprint_provenance;
        ALTER TABLE investigation.question_review_receipts ADD CONSTRAINT oi_review_fingerprint_provenance CHECK (
            (source_snapshot_contract='oi.synthetic-postgres-world-model-sources/1'
                AND queue_fingerprint_contract='oi.synthetic-source-review-return/1')
            OR (source_snapshot_contract='oi.pg-source-world-model/1'
                AND queue_fingerprint_contract='oi.synthetic-source-review-return/2'));
    """)
