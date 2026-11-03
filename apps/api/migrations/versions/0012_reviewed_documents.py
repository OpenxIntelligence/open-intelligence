"""Immutable reviewed-document children of the canonical original source owner."""
from alembic import op
from alembic.util.exc import CommandError
from sqlalchemy import text

revision = "0012_reviewed_documents"
down_revision = "0011_evidence_convergence"
branch_labels = None
depends_on = None


def upgrade():
    connection = op.get_bind()
    for name in ("document_intakes", "annotation_revisions"):
        if connection.execute(text("SELECT to_regclass(:name)"),
                              {"name": "clinical_source." + name}).scalar_one() is not None:
            raise CommandError("Reviewed document objects require owner reconciliation")
    op.execute("""
        CREATE TABLE clinical_source.document_intakes (
            source_id text PRIMARY KEY REFERENCES clinical_source.source_versions(source_id),
            filename text NOT NULL,
            metadata_json jsonb NOT NULL,
            receipt_json jsonb NOT NULL,
            rendition_json jsonb,
            CHECK (jsonb_typeof(metadata_json)='object'),
            CHECK (jsonb_typeof(receipt_json)='object')
        );
        CREATE TABLE clinical_source.annotation_revisions (
            revision_id text PRIMARY KEY CHECK (revision_id ~ '^ANN-[A-F0-9]{32}$'),
            source_id text NOT NULL REFERENCES clinical_source.document_intakes(source_id),
            revision integer NOT NULL CHECK (revision BETWEEN 1 AND 64),
            request_key text NOT NULL,
            intent_sha256 text NOT NULL CHECK (intent_sha256 ~ '^[a-f0-9]{64}$'),
            findings_json jsonb NOT NULL CHECK (jsonb_typeof(findings_json)='array'),
            receipt_json jsonb NOT NULL CHECK (jsonb_typeof(receipt_json)='object'),
            reason text NOT NULL,
            actor text NOT NULL,
            created_at timestamptz NOT NULL DEFAULT now(),
            UNIQUE(source_id,revision), UNIQUE(source_id,request_key)
        );
        CREATE TRIGGER oi_document_intake_update BEFORE UPDATE ON clinical_source.document_intakes
            FOR EACH ROW EXECUTE FUNCTION identity.reject_registry_history_mutation();
        CREATE TRIGGER oi_document_intake_delete BEFORE DELETE ON clinical_source.document_intakes
            FOR EACH ROW EXECUTE FUNCTION identity.reject_registry_history_mutation();
        CREATE TRIGGER oi_annotation_update BEFORE UPDATE ON clinical_source.annotation_revisions
            FOR EACH ROW EXECUTE FUNCTION identity.reject_registry_history_mutation();
        CREATE TRIGGER oi_annotation_delete BEFORE DELETE ON clinical_source.annotation_revisions
            FOR EACH ROW EXECUTE FUNCTION identity.reject_registry_history_mutation();
    """)


def downgrade():
    op.execute("DROP TABLE clinical_source.annotation_revisions")
    op.execute("DROP TABLE clinical_source.document_intakes")
