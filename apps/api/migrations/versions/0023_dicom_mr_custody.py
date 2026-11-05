"""Allow classic MR originals alongside CT under the existing image owner."""
from alembic import op
from alembic.util.exc import CommandError

revision = "0023_dicom_mr_custody"
down_revision = "0022_lab_citation_source_scope"
branch_labels = None
depends_on = None


def upgrade():
    op.get_bind().exec_driver_sql("""
        ALTER TABLE clinical_source.dicom_objects
            DROP CONSTRAINT dicom_objects_sop_class_uid_check,
            DROP CONSTRAINT dicom_objects_modality_check,
            ADD CONSTRAINT dicom_objects_storage_modality_check CHECK (
                (sop_class_uid = '1.2.840.10008.5.1.4.1.1.2' AND modality = 'CT') OR
                (sop_class_uid = '1.2.840.10008.5.1.4.1.1.4' AND modality = 'MR')
            )
    """)


def downgrade():
    connection = op.get_bind()
    # Keep preflight and constraint replacement in the same locked transaction.
    connection.exec_driver_sql("LOCK TABLE clinical_source.dicom_objects IN ACCESS EXCLUSIVE MODE")
    if connection.exec_driver_sql(
            "SELECT EXISTS (SELECT 1 FROM clinical_source.dicom_objects WHERE modality = 'MR')"
    ).scalar_one():
        raise CommandError("MR originals are in custody; this revision cannot be downgraded")
    connection.exec_driver_sql("""
        ALTER TABLE clinical_source.dicom_objects
            DROP CONSTRAINT dicom_objects_storage_modality_check,
            ADD CONSTRAINT dicom_objects_sop_class_uid_check
                CHECK (sop_class_uid = '1.2.840.10008.5.1.4.1.1.2'),
            ADD CONSTRAINT dicom_objects_modality_check CHECK (modality = 'CT')
    """)
