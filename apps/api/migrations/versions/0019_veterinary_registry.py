"""Register veterinary subjects and cases independently of human case bindings."""
from alembic import op
from alembic.util.exc import CommandError

revision = "0019_veterinary_registry"
down_revision = "0018_laboratory_questions"
branch_labels = None
depends_on = None


def upgrade():
    connection = op.get_bind()
    connection.exec_driver_sql("""
        CREATE TABLE identity.veterinary_animals (
            animal_id text PRIMARY KEY CHECK (animal_id ~ '^ANM-[0-9A-F]{32}$'),
            species text NOT NULL CHECK (species IN ('dog', 'cat')),
            origin_org text NOT NULL,
            source_system text NOT NULL,
            source_subject_ref text NOT NULL,
            request_key text NOT NULL,
            created_by text NOT NULL,
            purpose text NOT NULL CHECK (purpose IN ('operations', 'research')),
            created_at timestamptz NOT NULL DEFAULT now(),
            UNIQUE (origin_org, request_key),
            UNIQUE (origin_org, source_system, source_subject_ref),
            UNIQUE (origin_org, animal_id)
        )
    """)
    connection.exec_driver_sql("""
        CREATE TABLE coordination.veterinary_cases (
            case_id text PRIMARY KEY CHECK (case_id ~ '^VCASE-[0-9A-F]{32}$'),
            animal_id text NOT NULL,
            origin_org text NOT NULL,
            request_key text NOT NULL,
            created_by text NOT NULL,
            purpose text NOT NULL CHECK (purpose IN ('operations', 'research')),
            created_at timestamptz NOT NULL DEFAULT now(),
            UNIQUE (origin_org, request_key),
            FOREIGN KEY (origin_org, animal_id)
                REFERENCES identity.veterinary_animals (origin_org, animal_id)
        )
    """)
    for table in ("identity.veterinary_animals", "coordination.veterinary_cases"):
        connection.exec_driver_sql(f"""
            CREATE TRIGGER veterinary_registration_immutable BEFORE UPDATE OR DELETE ON {table}
            FOR EACH ROW EXECUTE FUNCTION identity.reject_registry_history_mutation()
        """)


def downgrade():
    connection = op.get_bind()
    connection.exec_driver_sql(
        "LOCK TABLE identity.veterinary_animals, coordination.veterinary_cases IN ACCESS EXCLUSIVE MODE")
    if connection.exec_driver_sql(
            "SELECT EXISTS (SELECT FROM identity.veterinary_animals) OR "
            "EXISTS (SELECT FROM coordination.veterinary_cases)").scalar_one():
        raise CommandError("Preserve populated veterinary registration history")
    connection.exec_driver_sql("DROP TABLE coordination.veterinary_cases")
    connection.exec_driver_sql("DROP TABLE identity.veterinary_animals")
