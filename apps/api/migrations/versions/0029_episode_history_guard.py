"""Keep episode creation events and their original draft rows together."""
from alembic import op
from alembic.util.exc import CommandError

revision = "0029_episode_history_guard"
down_revision = "0028_episode_core_join"
branch_labels = None
depends_on = None


def _lock_history(conn):
    # The source owner locks the binding before appending the creation event and
    # inserting the draft. In particular, never wait for the journal while
    # holding an exclusive episode lock against an in-flight save.
    conn.exec_driver_sql("""
        LOCK TABLE coordination.patient_case_bindings IN EXCLUSIVE MODE;
        LOCK TABLE identity.identity_domain_events, clinical_source.episode_drafts IN SHARE ROW EXCLUSIVE MODE
    """)


def upgrade():
    conn = op.get_bind()
    _lock_history(conn)
    if conn.exec_driver_sql("""
        SELECT EXISTS (
            SELECT 1 FROM identity.identity_domain_events e
            WHERE e.event_type = 'episode.draft_created' AND NOT EXISTS (
                SELECT 1 FROM clinical_source.episode_drafts d WHERE d.creation_event_id = e.id
            )
        )
    """).scalar_one():
        raise CommandError("Orphaned episode creation event requires explicit reconciliation")
    conn.exec_driver_sql("""
        CREATE TRIGGER oi_episode_draft_no_truncate
        BEFORE TRUNCATE ON clinical_source.episode_drafts FOR EACH STATEMENT
        EXECUTE FUNCTION identity.reject_registry_history_mutation()
    """)


def downgrade():
    conn = op.get_bind()
    _lock_history(conn)
    if conn.exec_driver_sql("SELECT EXISTS (SELECT 1 FROM clinical_source.episode_drafts)").scalar_one():
        raise CommandError("Populated episode drafts require explicit preservation")
    conn.exec_driver_sql("DROP TRIGGER oi_episode_draft_no_truncate ON clinical_source.episode_drafts")
