"""Connect the first-party encounter and versioned note owner to H1 patients."""
from alembic import op
from alembic.util.exc import CommandError

revision = "0019_ehr_encounters"
down_revision = "0018_laboratory_questions"
branch_labels = None
depends_on = None


def upgrade():
    connection = op.get_bind()
    connection.exec_driver_sql("CREATE SCHEMA ehr")
    for statement in (
        """CREATE TABLE ehr.clinical_encounters (
            id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
            patient_id text NOT NULL REFERENCES identity.identity_patients(patient_id),
            external_key text NOT NULL,
            kind text NOT NULL CHECK (kind IN ('outpatient','inpatient','telehealth','telephone','procedure','other')),
            service_date date NOT NULL,
            status text NOT NULL CHECK (status IN ('scheduled','in_progress','completed','cancelled')),
            revision bigint NOT NULL CHECK (revision > 0),
            created_at timestamptz NOT NULL, updated_at timestamptz NOT NULL,
            UNIQUE (patient_id,external_key))""",
        "CREATE INDEX encounter_patient_page ON ehr.clinical_encounters(patient_id,id)",
        """CREATE TABLE ehr.clinical_note_headers (
            id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
            encounter_id bigint NOT NULL REFERENCES ehr.clinical_encounters(id),
            note_key text NOT NULL, latest_version integer NOT NULL CHECK (latest_version > 0),
            UNIQUE (encounter_id,note_key))""",
        """CREATE TABLE ehr.clinical_note_versions (
            id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
            note_id bigint NOT NULL REFERENCES ehr.clinical_note_headers(id),
            version integer NOT NULL CHECK (version > 0), status text NOT NULL CHECK
               (status IN ('draft','attested','draft_correction','attested_correction')),
            body text NOT NULL, sha256 char(64) NOT NULL CHECK (sha256 ~ '^[0-9a-f]{64}$'),
            authored_by text NOT NULL, created_at timestamptz NOT NULL, supersedes_id bigint,
            amendment_reason text, facility_id text, department_id text, note_kind text,
            CHECK ((version=1) = (supersedes_id IS NULL)),
            CHECK (status NOT IN ('draft_correction','attested_correction') OR
                   NULLIF(btrim(amendment_reason),'') IS NOT NULL),
            previous_version integer GENERATED ALWAYS AS (version - 1) STORED,
            UNIQUE (note_id,version), UNIQUE (note_id,version,id),
            FOREIGN KEY (note_id,previous_version,supersedes_id)
                REFERENCES ehr.clinical_note_versions(note_id,version,id))""",
        """ALTER TABLE ehr.clinical_note_headers ADD CONSTRAINT latest_note_version_exists
            FOREIGN KEY (id,latest_version) REFERENCES ehr.clinical_note_versions(note_id,version)
            DEFERRABLE INITIALLY DEFERRED""",
        """CREATE TABLE ehr.clinical_encounter_commands (
            patient_id text NOT NULL REFERENCES identity.identity_patients(patient_id),
            request_key text NOT NULL, request_hash char(64) NOT NULL CHECK (request_hash ~ '^[0-9a-f]{64}$'),
            operation text NOT NULL, result_json text NOT NULL, occurred_at timestamptz NOT NULL,
            PRIMARY KEY (patient_id,request_key))""",
    ):
        connection.exec_driver_sql(statement)
    for table in ("clinical_encounter_commands", "clinical_note_versions"):
        connection.exec_driver_sql(f"""CREATE TRIGGER encounter_history_immutable
            BEFORE UPDATE OR DELETE ON ehr.{table}
            FOR EACH ROW EXECUTE FUNCTION identity.reject_registry_history_mutation()""")


def downgrade():
    connection = op.get_bind()
    connection.exec_driver_sql("LOCK TABLE ehr.clinical_encounters, ehr.clinical_encounter_commands IN ACCESS EXCLUSIVE MODE")
    if connection.exec_driver_sql("""SELECT EXISTS(SELECT 1 FROM ehr.clinical_encounters)
                                      OR EXISTS(SELECT 1 FROM ehr.clinical_encounter_commands)""").scalar_one():
        raise CommandError("Populated encounter or note history cannot be downgraded")
    connection.exec_driver_sql("ALTER TABLE ehr.clinical_note_headers DROP CONSTRAINT latest_note_version_exists")
    for table in ("clinical_note_versions", "clinical_note_headers", "clinical_encounter_commands", "clinical_encounters"):
        connection.exec_driver_sql(f"DROP TABLE ehr.{table}")
    connection.exec_driver_sql("DROP SCHEMA ehr")
