"""Reject new laboratory citations when an intervening import changed the case."""
from alembic import op

revision = "0021_lab_citation_freshness"
down_revision = "0020_ehr_lab_convergence"
branch_labels = None
depends_on = None


def upgrade():
    op.get_bind().exec_driver_sql("""
        CREATE FUNCTION investigation.require_lab_citation_current_sources() RETURNS trigger
        LANGUAGE plpgsql AS $guard$
        DECLARE saved_event bigint;
        BEGIN
            IF NOT EXISTS (SELECT 1 FROM investigation.laboratory_question_anchors
                           WHERE question_id = NEW.question_id) THEN
                RETURN NEW;
            END IF;

            -- A transaction-wide snapshot can predate a completed import
            -- even after taking the binding lock. The supported writer uses
            -- a fresh READ COMMITTED snapshot for this final check.
            IF current_setting('transaction_isolation') <> 'read committed' THEN
                RAISE EXCEPTION 'OI-LAB-CITATION-READ-COMMITTED-REQUIRED';
            END IF;

            -- The earlier question_evidence_scope trigger takes the same case
            -- binding lock as every import. Event IDs give the order within
            -- that lock even when timestamps are equal or supplied externally.
            SELECT min(e.id) INTO saved_event
            FROM identity.identity_domain_events e
            WHERE e.patient_id = NEW.patient_id
              AND e.event_type = 'investigation.question.created'
              AND e.metadata_json->>'case_id' = NEW.case_id
              AND e.metadata_json->>'question_id' = NEW.question_id
              AND e.metadata_json->>'source_snapshot_sha256' = NEW.source_snapshot_sha256;

            -- Each immutable version needs its own import receipt preceding
            -- the save. Missing receipts also withhold a new link. Historical
            -- reads and receipt replay never insert a link.
            IF saved_event IS NULL OR EXISTS (
                SELECT s.source_id FROM clinical_source.source_versions s
                WHERE s.case_id = NEW.case_id
                EXCEPT
                SELECT e.metadata_json->>'source_id' FROM identity.identity_domain_events e
                WHERE e.patient_id = NEW.patient_id AND e.id < saved_event
                  AND e.event_type = 'source.original.imported'
                  AND e.metadata_json->>'case_id' = NEW.case_id
            ) THEN
                RAISE EXCEPTION 'OI-LAB-CITATION-CASE-SOURCES-CHANGED';
            END IF;
            RETURN NEW;
        END;
        $guard$;
        CREATE TRIGGER zzz_oi_lab_citation_current_sources
        BEFORE INSERT ON investigation.question_evidence_links
        FOR EACH ROW EXECUTE FUNCTION investigation.require_lab_citation_current_sources();
    """)


def downgrade():
    op.get_bind().exec_driver_sql("""
        DROP TRIGGER zzz_oi_lab_citation_current_sources ON investigation.question_evidence_links;
        DROP FUNCTION investigation.require_lab_citation_current_sources();
    """)
