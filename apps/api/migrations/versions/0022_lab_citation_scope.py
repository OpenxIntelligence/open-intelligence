"""Match the canonical structured-source snapshot without changing its identity."""
from alembic import op

revision = "0022_lab_citation_source_scope"
down_revision = "0021_lab_citation_freshness"
branch_labels = None
depends_on = None


def _replace_guard(*, exclude_reviewed_documents):
    # The source owner deliberately excludes ordinary reviewed documents from
    # structured World Model snapshots. Keep that same custody boundary here;
    # do not alter question fingerprints, original rows or historical receipts.
    # Both strings are fixed migration SQL, never application-supplied input.
    source_filter = (
        "AND s.source_id NOT IN (SELECT source_id FROM clinical_source.document_intakes)"
        if exclude_reviewed_documents else ""
    )
    op.get_bind().exec_driver_sql("""
        CREATE OR REPLACE FUNCTION investigation.require_lab_citation_current_sources() RETURNS trigger
        LANGUAGE plpgsql AS $guard$
        DECLARE saved_event bigint;
        BEGIN
            IF NOT EXISTS (SELECT 1 FROM investigation.laboratory_question_anchors
                           WHERE question_id = NEW.question_id) THEN
                RETURN NEW;
            END IF;

            IF current_setting('transaction_isolation') <> 'read committed' THEN
                RAISE EXCEPTION 'OI-LAB-CITATION-READ-COMMITTED-REQUIRED';
            END IF;

            -- The existing earlier scope trigger takes the case binding lock.
            SELECT min(e.id) INTO saved_event
            FROM identity.identity_domain_events e
            WHERE e.patient_id = NEW.patient_id
              AND e.event_type = 'investigation.question.created'
              AND e.metadata_json->>'case_id' = NEW.case_id
              AND e.metadata_json->>'question_id' = NEW.question_id
              AND e.metadata_json->>'source_snapshot_sha256' = NEW.source_snapshot_sha256;

            IF saved_event IS NULL OR EXISTS (
                SELECT s.source_id FROM clinical_source.source_versions s
                WHERE s.case_id = NEW.case_id
                """ + source_filter + """
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
    """)


def upgrade():
    _replace_guard(exclude_reviewed_documents=True)


def downgrade():
    # Restore published 0021 semantics. Its own downgrade owns trigger removal.
    _replace_guard(exclude_reviewed_documents=False)
