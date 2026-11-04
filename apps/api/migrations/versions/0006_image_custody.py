"""Immutable bounded DICOM originals under the existing clinical_source owner.

Images are attached explicitly to exact source versions. A subsequent report
can link the same immutable object without duplicating or retargeting bytes.
This migration grants neither patient access nor clinical source authenticity.
"""

from alembic import op
from alembic.util.exc import CommandError
from sqlalchemy import text

revision = "0006_image_custody"
down_revision = "0005_source_versions"
branch_labels = None
depends_on = None


def upgrade():
    conn = op.get_bind()
    for name in ("dicom_objects", "source_image_links"):
        exists = conn.execute(text(
            "SELECT c.relname FROM pg_class c JOIN pg_namespace n ON c.relnamespace=n.oid "
            "WHERE n.nspname='clinical_source' AND c.relname=:name"), {"name": name}).scalar_one_or_none()
        if exists is not None:
            raise CommandError("Existing image custody needs explicit owner reconciliation")
    conn.exec_driver_sql("""
        CREATE TABLE clinical_source.dicom_objects (
            image_id text PRIMARY KEY CHECK (image_id ~ '^IMG-[0-9A-F]{32}$'),
            case_id text NOT NULL REFERENCES coordination.patient_case_bindings(case_id),
            raw bytea NOT NULL CHECK (octet_length(raw) BETWEEN 132 AND 2097152),
            sha256 char(64) NOT NULL CHECK (sha256 ~ '^[0-9a-f]{64}$'),
            byte_count integer NOT NULL CHECK (byte_count=octet_length(raw)),
            patient_id text NOT NULL CHECK (char_length(patient_id) BETWEEN 1 AND 64),
            issuer text NOT NULL CHECK (char_length(issuer) BETWEEN 1 AND 64),
            study_uid text NOT NULL CHECK (char_length(study_uid) BETWEEN 1 AND 64),
            series_uid text NOT NULL CHECK (char_length(series_uid) BETWEEN 1 AND 64),
            sop_uid text NOT NULL CHECK (char_length(sop_uid) BETWEEN 1 AND 64),
            sop_class_uid text NOT NULL CHECK (sop_class_uid='1.2.840.10008.5.1.4.1.1.2'),
            transfer_syntax_uid text NOT NULL CHECK (transfer_syntax_uid='1.2.840.10008.1.2.1'),
            study_date date NOT NULL,
            modality text NOT NULL CHECK (modality='CT'),
            rows integer NOT NULL CHECK (rows BETWEEN 1 AND 1024),
            columns integer NOT NULL CHECK (columns BETWEEN 1 AND 1024),
            created_at timestamptz NOT NULL DEFAULT now(),
            UNIQUE(case_id,sop_uid)
        );
        CREATE TABLE clinical_source.source_image_links (
            source_id text NOT NULL REFERENCES clinical_source.source_versions(source_id),
            image_id text NOT NULL REFERENCES clinical_source.dicom_objects(image_id),
            created_at timestamptz NOT NULL DEFAULT now(),
            PRIMARY KEY(source_id,image_id)
        );
        CREATE INDEX idx_oi_image_links_object ON clinical_source.source_image_links(image_id);
        CREATE FUNCTION clinical_source.guard_image_source_link() RETURNS trigger
        LANGUAGE plpgsql AS $oi_image_guard$
        DECLARE source_case text; source_kind text; source_state text; image_case text;
        BEGIN
            SELECT case_id,kind,state INTO source_case,source_kind,source_state
                FROM clinical_source.source_versions WHERE source_id=NEW.source_id FOR SHARE;
            SELECT case_id INTO image_case FROM clinical_source.dicom_objects WHERE image_id=NEW.image_id;
            IF source_case IS NULL OR image_case IS NULL OR source_case!=image_case
                OR source_kind!='imaging' OR source_state!='current' THEN
                RAISE EXCEPTION 'OI-IMAGE-SOURCE-MISMATCH';
            END IF;
            RETURN NEW;
        END;
        $oi_image_guard$;
        CREATE TRIGGER oi_image_link_insert_guard BEFORE INSERT ON clinical_source.source_image_links
            FOR EACH ROW EXECUTE FUNCTION clinical_source.guard_image_source_link();
        CREATE TRIGGER oi_image_update_guard BEFORE UPDATE ON clinical_source.dicom_objects
            FOR EACH ROW EXECUTE FUNCTION identity.reject_registry_history_mutation();
        CREATE TRIGGER oi_image_delete_guard BEFORE DELETE ON clinical_source.dicom_objects
            FOR EACH ROW EXECUTE FUNCTION identity.reject_registry_history_mutation();
        CREATE TRIGGER oi_image_link_update_guard BEFORE UPDATE ON clinical_source.source_image_links
            FOR EACH ROW EXECUTE FUNCTION identity.reject_registry_history_mutation();
        CREATE TRIGGER oi_image_link_delete_guard BEFORE DELETE ON clinical_source.source_image_links
            FOR EACH ROW EXECUTE FUNCTION identity.reject_registry_history_mutation();
    """)


def downgrade():
    conn = op.get_bind()
    for statement in (
        "DROP TABLE clinical_source.source_image_links",
        "DROP TABLE clinical_source.dicom_objects",
        "DROP FUNCTION clinical_source.guard_image_source_link()",
    ):
        conn.exec_driver_sql(statement)
    # RESTRICT deliberately stops unknown dependencies. No namespace is dropped.
