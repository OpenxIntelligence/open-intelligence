"""Allow governed metadata citations on an explicitly anchored laboratory question."""
from alembic import op
from alembic.util.exc import CommandError

revision = "0019_laboratory_citations"
down_revision = "0018_laboratory_questions"
branch_labels = None
depends_on = None


def upgrade():
    op.get_bind().exec_driver_sql("""
        ALTER TABLE investigation.question_evidence_links
            ADD CONSTRAINT oi_citation_question_pair UNIQUE (link_id,question_id);
        CREATE TABLE investigation.laboratory_citation_anchors (
            link_id text PRIMARY KEY,
            question_id text NOT NULL REFERENCES investigation.laboratory_question_anchors(question_id),
            source_id text NOT NULL,
            observation_reference text NOT NULL,
            rights_decision_id text NOT NULL REFERENCES investigation.evidence_rights_decisions(decision_id),
            FOREIGN KEY (source_id,observation_reference) REFERENCES
                clinical_source.fhir_laboratory_observations(source_id,observation_reference),
            FOREIGN KEY (link_id,question_id) REFERENCES
                investigation.question_evidence_links(link_id,question_id)
                DEFERRABLE INITIALLY DEFERRED
        );
        CREATE TRIGGER oi_lab_citation_immutable BEFORE UPDATE OR DELETE ON investigation.laboratory_citation_anchors
            FOR EACH ROW EXECUTE FUNCTION identity.reject_registry_history_mutation();
        CREATE TRIGGER oi_lab_citation_no_truncate BEFORE TRUNCATE ON investigation.laboratory_citation_anchors
            FOR EACH STATEMENT EXECUTE FUNCTION identity.reject_registry_history_mutation();

        CREATE FUNCTION investigation.guard_citation_question_target() RETURNS trigger
        LANGUAGE plpgsql AS $oi$
        DECLARE typed boolean;
        DECLARE decision text;
        DECLARE current_rights investigation.evidence_rights_decisions%ROWTYPE;
        BEGIN
            SELECT (q.source_line IS NULL) INTO STRICT typed
                FROM investigation.source_questions q WHERE q.question_id=NEW.question_id;
            -- The existing question_evidence_scope trigger already checks the
            -- active patient, case, organization, purpose, source and fingerprints.
            IF NOT typed THEN RETURN NEW; END IF;
            SELECT a.rights_decision_id INTO decision
                FROM investigation.laboratory_citation_anchors a
                JOIN investigation.laboratory_question_anchors qa ON qa.question_id=a.question_id
                  AND qa.source_id=a.source_id AND qa.observation_reference=a.observation_reference
                JOIN investigation.source_questions q ON q.question_id=qa.question_id AND q.source_id=qa.source_id
                JOIN clinical_source.source_versions s ON s.source_id=q.source_id AND s.version=q.source_version
                  AND s.sha256=q.source_sha256 AND s.state='current' AND s.kind='laboratory'
                WHERE a.link_id=NEW.link_id AND a.question_id=NEW.question_id;
            IF NOT FOUND THEN RAISE EXCEPTION 'OI-LAB-CITATION-ANCHOR-REQUIRED'; END IF;
            -- Rights updates serialize on the same catalog row. Persist the exact
            -- decision that allowed storage and display at the point of linking.
            PERFORM 1 FROM investigation.evidence_catalog_records e
                WHERE e.record_id=NEW.record_id AND e.version=NEW.version AND e.source_kind='fictional'
                FOR SHARE;
            IF NOT FOUND THEN RAISE EXCEPTION 'OI-LAB-CITATION-RIGHTS'; END IF;
            SELECT * INTO current_rights FROM investigation.evidence_rights_decisions d
                WHERE d.record_id=NEW.record_id AND d.version=NEW.version
                ORDER BY d.revision DESC LIMIT 1;
            IF NOT FOUND OR current_rights.decision_id IS DISTINCT FROM decision
               OR current_rights.revoked OR current_rights.superseded
               OR current_rights.permissions #>> '{metadata,store}' IS DISTINCT FROM 'allowed'
               OR current_rights.permissions #>> '{metadata,display}' IS DISTINCT FROM 'allowed'
            THEN RAISE EXCEPTION 'OI-LAB-CITATION-RIGHTS'; END IF;
            RETURN NEW;
        END;
        $oi$;
        DROP TRIGGER zz_oi_anchor_text_question_required ON investigation.question_evidence_links;
        CREATE TRIGGER zz_oi_citation_question_target BEFORE INSERT ON investigation.question_evidence_links
            FOR EACH ROW EXECUTE FUNCTION investigation.guard_citation_question_target();
    """)


def downgrade():
    conn = op.get_bind()
    conn.exec_driver_sql("LOCK TABLE investigation.question_evidence_links, investigation.laboratory_citation_anchors IN ACCESS EXCLUSIVE MODE")
    if conn.exec_driver_sql("""
        SELECT EXISTS(SELECT 1 FROM investigation.laboratory_citation_anchors) OR EXISTS (
            SELECT 1 FROM investigation.question_evidence_links l
            JOIN investigation.source_questions q ON q.question_id=l.question_id WHERE q.source_line IS NULL)
    """).scalar_one():
        raise CommandError("Stored laboratory citation history requires explicit reconciliation")
    conn.exec_driver_sql("""
        DROP TRIGGER zz_oi_citation_question_target ON investigation.question_evidence_links;
        DROP FUNCTION investigation.guard_citation_question_target();
        DROP TABLE investigation.laboratory_citation_anchors;
        ALTER TABLE investigation.question_evidence_links DROP CONSTRAINT oi_citation_question_pair;
        CREATE TRIGGER zz_oi_anchor_text_question_required BEFORE INSERT ON investigation.question_evidence_links
            FOR EACH ROW EXECUTE FUNCTION investigation.require_text_question_target();
    """)
