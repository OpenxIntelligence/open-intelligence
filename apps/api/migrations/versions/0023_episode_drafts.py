"""Durable, unreviewed episode identities rooted in an immutable original source line."""
from alembic import op
from alembic.util import CommandError

revision = "0023_episode_drafts"
down_revision = "0022_lab_citation_source_scope"
branch_labels = None
depends_on = None


def upgrade():
    op.get_bind().exec_driver_sql("""
        CREATE TABLE clinical_source.episode_drafts (
            episode_id text PRIMARY KEY CHECK (episode_id ~ '^EPISODE-[0-9A-F]{32}$'),
            source_id text NOT NULL,
            source_line integer NOT NULL,
            basis_sha256 text NOT NULL CHECK (basis_sha256 ~ '^[0-9a-f]{64}$'),
            created_by text NOT NULL CHECK (char_length(created_by) BETWEEN 3 AND 128),
            creation_event_id bigint NOT NULL UNIQUE REFERENCES identity.identity_domain_events(id),
            created_at timestamptz NOT NULL DEFAULT now(),
            FOREIGN KEY (source_id, source_line) REFERENCES clinical_source.assertions(source_id, source_line),
            UNIQUE (source_id, source_line)
        );
        CREATE FUNCTION clinical_source.check_episode_creation() RETURNS trigger LANGUAGE plpgsql AS $guard$
        BEGIN
            IF NOT EXISTS (
                SELECT 1 FROM clinical_source.source_versions s
                JOIN clinical_source.assertions a USING(source_id)
                JOIN coordination.patient_case_bindings b USING(case_id)
                JOIN identity.identity_domain_events e ON e.patient_id=b.patient_id
                WHERE s.source_id=NEW.source_id AND a.source_line=NEW.source_line
                  AND a.certainty='reported' AND s.state='current' AND b.status='active'
                  AND e.id=NEW.creation_event_id AND e.event_type='episode.draft_created'
                  AND e.metadata_json=jsonb_build_object('case_id',b.case_id,'episode_id',NEW.episode_id,
                      'source_id',NEW.source_id,'source_line',NEW.source_line,'basis_sha256',NEW.basis_sha256,
                      'actor',NEW.created_by,'purpose','operations')
            ) THEN RAISE EXCEPTION 'OI-EPISODE-CREATION-ORIGIN'; END IF;
            RETURN NEW;
        END;
        $guard$;
        CREATE TRIGGER oi_episode_creation BEFORE INSERT ON clinical_source.episode_drafts
            FOR EACH ROW EXECUTE FUNCTION clinical_source.check_episode_creation();
        CREATE TRIGGER oi_episode_draft_immutable BEFORE UPDATE OR DELETE ON clinical_source.episode_drafts
            FOR EACH ROW EXECUTE FUNCTION identity.reject_registry_history_mutation();
    """)


def downgrade():
    conn = op.get_bind()
    conn.exec_driver_sql("LOCK TABLE clinical_source.episode_drafts IN ACCESS EXCLUSIVE MODE")
    if conn.exec_driver_sql("SELECT EXISTS (SELECT 1 FROM clinical_source.episode_drafts)").scalar_one():
        raise CommandError("Populated episode drafts require explicit preservation")
    conn.exec_driver_sql("DROP TABLE clinical_source.episode_drafts")
    conn.exec_driver_sql("DROP FUNCTION clinical_source.check_episode_creation()")
