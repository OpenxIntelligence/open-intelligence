"""Explicit Alembic merge of published first-party question and image owners.

Do not rename/squash the source-owned revisions. This merge has no DDL:
both branches create disjoint tables beneath the same canonical patient,
case binding and source owners. Alembic must apply BOTH branches before
advancing readiness; a single previously applied branch is not sufficient.
"""
from alembic import op
from sqlalchemy import text

revision = "0008_questions_images_merge"
down_revision = ("0007_question_snapshot_contract", "0006_image_custody")
branch_labels = None
depends_on = None


def upgrade():
    connection = op.get_bind()
    checks = (
        ("investigation", "source_questions"),
        ("clinical_source", "dicom_objects"),
        ("clinical_source", "source_image_links"),
    )
    for schema, name in checks:
        exists = connection.execute(
            text("SELECT to_regclass(:identifier) IS NOT NULL"),
            {"identifier": f"{schema}.{name}"},
        ).scalar_one()
        if not exists:
            raise RuntimeError("Canonical question/image owners are not both installed")
    contract = connection.execute(text(
        "SELECT 1 FROM information_schema.columns "
        "WHERE table_schema='investigation' AND table_name='source_questions' "
        "AND column_name='source_snapshot_contract'"
    )).scalar_one_or_none()
    if contract is None:
        raise RuntimeError("Canonical question fingerprint revision is missing")


def downgrade():
    # Alembic traverses the two existing owners; we deliberately do not
    # delete, rename, adopt or mutate anything in this merge node.
    pass
