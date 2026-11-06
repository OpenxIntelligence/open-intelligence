"""Preserve bounded observation and citation references from an authorized inspection."""
from alembic import op
from alembic.util.exc import CommandError

revision = "0025_lab_inspection_snapshots"
down_revision = "0024_fhir_coded_results"
branch_labels = None
depends_on = None


def upgrade():
    op.get_bind().exec_driver_sql("""
        CREATE TABLE investigation.laboratory_inspection_snapshots (
            snapshot_id text PRIMARY KEY CHECK(snapshot_id ~ '^LAB-SNAPSHOT-[0-9A-F]{32}$'),
            patient_id text NOT NULL REFERENCES identity.identity_patients(patient_id),
            case_id text NOT NULL REFERENCES coordination.patient_case_bindings(case_id),
            question_id text NOT NULL REFERENCES investigation.laboratory_question_anchors(question_id),
            origin_org text NOT NULL, actor text NOT NULL, purpose text NOT NULL CHECK(purpose='operations'),
            request_key text NOT NULL CHECK(char_length(request_key) BETWEEN 3 AND 128),
            capture_access_receipt_id text NOT NULL UNIQUE CHECK(capture_access_receipt_id ~ '^ACCESS-[0-9A-F]{32}$'),
            captured_at timestamptz NOT NULL,
            captured_report_sha256 text NOT NULL CHECK(captured_report_sha256 ~ '^[0-9a-f]{64}$'),
            manifest jsonb NOT NULL CHECK(jsonb_typeof(manifest)='object' AND octet_length(manifest::text)<=131072),
            manifest_sha256 text NOT NULL CHECK(manifest_sha256 ~ '^[0-9a-f]{64}$'),
            UNIQUE(patient_id,request_key)
        );
        CREATE INDEX idx_lab_snapshot_question ON investigation.laboratory_inspection_snapshots
            (question_id,captured_at,snapshot_id);
        CREATE FUNCTION investigation.guard_laboratory_inspection_snapshot() RETURNS trigger
        LANGUAGE plpgsql AS $guard$
        DECLARE entry jsonb; DECLARE exact_anchor jsonb; DECLARE basis_hash text;
        DECLARE decision investigation.evidence_rights_decisions%ROWTYPE;
        BEGIN
            IF current_setting('transaction_isolation') <> 'read committed' THEN
                RAISE EXCEPTION 'OI-LAB-SNAPSHOT-READ-COMMITTED-REQUIRED';
            END IF;
            PERFORM 1 FROM identity.identity_patients p WHERE p.patient_id=NEW.patient_id
                AND p.origin_org=NEW.origin_org AND p.status='active' FOR SHARE;
            IF NOT FOUND THEN RAISE EXCEPTION 'OI-LAB-SNAPSHOT-SCOPE'; END IF;
            PERFORM 1 FROM coordination.patient_case_bindings b WHERE b.patient_id=NEW.patient_id
                AND b.case_id=NEW.case_id AND b.origin_org=NEW.origin_org AND b.purpose=NEW.purpose
                AND b.status='active' FOR UPDATE;
            IF NOT FOUND THEN RAISE EXCEPTION 'OI-LAB-SNAPSHOT-SCOPE'; END IF;
            SELECT jsonb_build_object(
                'source_id',q.source_id,'source_version',q.source_version,'source_sha256',q.source_sha256,
                'observation_reference',a.observation_reference,
                'source_snapshot_sha256',q.source_snapshot_sha256,'preflight_sha256',q.preflight_sha256)
            INTO exact_anchor FROM investigation.source_questions q
                JOIN investigation.laboratory_question_anchors a ON a.question_id=q.question_id AND a.source_id=q.source_id
                WHERE q.question_id=NEW.question_id AND q.patient_id=NEW.patient_id AND q.case_id=NEW.case_id
                  AND q.origin_org=NEW.origin_org AND q.purpose=NEW.purpose AND q.source_line IS NULL;
            IF NOT FOUND OR exact_anchor IS DISTINCT FROM NEW.manifest->'anchor'
                THEN RAISE EXCEPTION 'OI-LAB-SNAPSHOT-ANCHOR'; END IF;
            IF NOT (NEW.manifest ?& ARRAY['anchor','source_context_state','links'])
                OR NEW.manifest - ARRAY['anchor','source_context_state','links'] <> '{}'::jsonb
                OR jsonb_typeof(NEW.manifest->'source_context_state') IS DISTINCT FROM 'string'
                OR NEW.manifest->>'source_context_state' NOT IN ('current_unreviewed_question','source_reassessment_required')
                OR jsonb_typeof(NEW.manifest->'links') IS DISTINCT FROM 'array'
                THEN RAISE EXCEPTION 'OI-LAB-SNAPSHOT-MANIFEST'; END IF;
            IF jsonb_array_length(NEW.manifest->'links')>100 OR
                (SELECT count(DISTINCT x->>'link_id') FROM jsonb_array_elements(NEW.manifest->'links') x)
                    <> jsonb_array_length(NEW.manifest->'links') OR
                (SELECT count(*) FROM investigation.question_evidence_links WHERE question_id=NEW.question_id)
                    <> jsonb_array_length(NEW.manifest->'links')
                THEN RAISE EXCEPTION 'OI-LAB-SNAPSHOT-CITATIONS'; END IF;
            FOR entry IN SELECT jsonb_array_elements(NEW.manifest->'links') LOOP
                IF NOT (entry ?& ARRAY['link_id','citation','metadata_sha256','status','rights_decision_id'])
                    OR entry - ARRAY['link_id','citation','metadata_sha256','status','rights_decision_id'] <> '{}'::jsonb
                    OR jsonb_typeof(entry->'status') IS DISTINCT FROM 'string'
                    OR entry->>'status' NOT IN ('available','rights_restricted','superseded','unavailable')
                    OR NOT EXISTS (SELECT 1 FROM investigation.question_evidence_links l
                        JOIN investigation.laboratory_citation_anchors a ON a.link_id=l.link_id
                        WHERE l.question_id=NEW.question_id AND a.question_id=l.question_id
                          AND l.patient_id=NEW.patient_id AND l.case_id=NEW.case_id AND l.origin_org=NEW.origin_org
                          AND l.purpose=NEW.purpose AND l.link_id=entry->>'link_id'
                          AND l.record_id||'@'||l.version=entry->>'citation' AND l.metadata_sha256=entry->>'metadata_sha256')
                    THEN RAISE EXCEPTION 'OI-LAB-SNAPSHOT-CITATIONS'; END IF;
                -- Rights writers lock this exact record before appending decisions.
                PERFORM 1 FROM investigation.evidence_catalog_records c JOIN investigation.question_evidence_links l
                    ON l.record_id=c.record_id AND l.version=c.version WHERE l.link_id=entry->>'link_id' FOR SHARE OF c;
                SELECT d.* INTO decision FROM investigation.evidence_rights_decisions d
                    JOIN investigation.question_evidence_links l ON l.record_id=d.record_id AND l.version=d.version
                    WHERE l.link_id=entry->>'link_id' ORDER BY d.revision DESC LIMIT 1;
                IF NOT FOUND OR decision.decision_id IS DISTINCT FROM entry->>'rights_decision_id'
                    OR (entry->>'status'='available' AND (decision.revoked OR decision.superseded
                        OR decision.permissions #>> '{metadata,store}' IS DISTINCT FROM 'allowed'
                        OR decision.permissions #>> '{metadata,display}' IS DISTINCT FROM 'allowed'))
                    THEN RAISE EXCEPTION 'OI-LAB-SNAPSHOT-RIGHTS'; END IF;
            END LOOP;
            -- Capture must have rendered this exact inspection through the canonical
            -- report owner in this transaction. Past reads cannot attest a new capture.
            SELECT encode(sha256(convert_to(COALESCE(string_agg((e->>'link_id')||':'||(e->>'status'),chr(10)
                ORDER BY ord),''),'UTF8')),'hex') INTO basis_hash
                FROM jsonb_array_elements(NEW.manifest->'links') WITH ORDINALITY AS m(e,ord);
            IF NOT EXISTS (SELECT 1 FROM identity.identity_domain_events j
                WHERE j.xmin=pg_current_xact_id()::xid AND j.patient_id=NEW.patient_id
                AND j.event_type='investigation.laboratory_citation_report.read_authorized'
                AND j.metadata_json->>'case_id'=NEW.case_id AND j.metadata_json->>'question_id'=NEW.question_id
                AND j.metadata_json->>'actor'=NEW.actor
                AND j.metadata_json->>'source_access_receipt_id'=NEW.capture_access_receipt_id
                AND j.metadata_json->>'report_sha256'=NEW.captured_report_sha256
                AND j.metadata_json->>'source_context_state'=NEW.manifest->>'source_context_state'
                AND j.metadata_json->>'membership_sha256'=basis_hash
            ) THEN RAISE EXCEPTION 'OI-LAB-SNAPSHOT-INSPECTION-REQUIRED'; END IF;
            IF (SELECT count(*) FROM investigation.laboratory_inspection_snapshots
                  WHERE question_id=NEW.question_id)>=100 THEN RAISE EXCEPTION 'OI-LAB-SNAPSHOT-LIMIT'; END IF;
            RETURN NEW;
        END;
        $guard$;
        CREATE TRIGGER oi_lab_snapshot_insert BEFORE INSERT ON investigation.laboratory_inspection_snapshots
            FOR EACH ROW EXECUTE FUNCTION investigation.guard_laboratory_inspection_snapshot();
        CREATE TRIGGER oi_lab_snapshot_immutable BEFORE UPDATE OR DELETE ON investigation.laboratory_inspection_snapshots
            FOR EACH ROW EXECUTE FUNCTION identity.reject_registry_history_mutation();
        CREATE TRIGGER oi_lab_snapshot_no_truncate BEFORE TRUNCATE ON investigation.laboratory_inspection_snapshots
            FOR EACH STATEMENT EXECUTE FUNCTION identity.reject_registry_history_mutation();
    """)


def downgrade():
    conn = op.get_bind()
    conn.exec_driver_sql("LOCK TABLE investigation.laboratory_inspection_snapshots IN ACCESS EXCLUSIVE MODE")
    if conn.exec_driver_sql("SELECT EXISTS(SELECT 1 FROM investigation.laboratory_inspection_snapshots)").scalar_one():
        raise CommandError("Stored laboratory inspection snapshots require explicit reconciliation")
    conn.exec_driver_sql("DROP TABLE investigation.laboratory_inspection_snapshots")
    conn.exec_driver_sql("DROP FUNCTION investigation.guard_laboratory_inspection_snapshot()")
