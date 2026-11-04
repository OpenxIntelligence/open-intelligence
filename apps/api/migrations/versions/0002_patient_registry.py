"""Install the source-owned canonical patient identity persistence on PG16.

Only the identity subset from PR #148 is composed here. The external research
auth/EHR/source/outbox fixture is not an application migration. The existing
CLI owns the transaction and restricts downgrades to explicit disposable tests.
"""

from importlib.resources import files

from alembic import op
from alembic.util.exc import CommandError
from sqlalchemy import text


revision = "0002_patient_registry"
down_revision = "0001_h1_shell"
branch_labels = None
depends_on = None


def upgrade():
    connection = op.get_bind()
    # IF NOT EXISTS in the source-owned SQL is not evidence that preexisting
    # objects satisfy its constraints. Adoption requires a separate migration.
    owned_relations = (
        "identity_patients", "identity_create_receipts", "identity_domain_events",
        "identity_patients_pkey", "identity_create_receipts_pkey", "identity_domain_events_pkey",
        "identity_domain_events_id_seq", "idx_b01b_identity_origin", "idx_b01b_identity_events",
    )
    existing_relations = connection.execute(text(
        "SELECT c.relname FROM pg_class c JOIN pg_namespace n ON n.oid=c.relnamespace "
        "WHERE n.nspname='identity'"
    )).scalars().all()
    existing_functions = connection.execute(text(
        "SELECT p.proname FROM pg_proc p JOIN pg_namespace n ON n.oid=p.pronamespace "
        "WHERE n.nspname='identity'"
    )).scalars().all()
    owned_functions = {"reject_registry_history_mutation", "guard_registration_receipt",
                       "guard_patient_identity_mutation"}
    if set(existing_relations) & set(owned_relations) or set(existing_functions) & owned_functions:
        raise CommandError("Existing canonical identity objects require explicit migration reconciliation")
    sql = files("open_intelligence").joinpath("sql/patient_registry_postgres.sql").read_text(encoding="utf-8")
    connection.exec_driver_sql(sql)


def downgrade():
    # No CASCADE: unexpected dependencies must abort the surrounding migration
    # transaction. Keep the identity namespace and any unrelated objects.
    connection = op.get_bind()
    for statement in (
        "DROP TABLE identity.identity_domain_events",
        "DROP TABLE identity.identity_create_receipts",
        "DROP TABLE identity.identity_patients",
        "DROP FUNCTION identity.guard_patient_identity_mutation()",
        "DROP FUNCTION identity.guard_registration_receipt()",
        "DROP FUNCTION identity.reject_registry_history_mutation()",
    ):
        connection.exec_driver_sql(statement)
