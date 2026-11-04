"""Persist strict FHIR R4 laboratory sources as children of canonical source_versions."""
from alembic import op
from alembic.util.exc import CommandError
from sqlalchemy import text

revision = "0016_fhir_laboratory_sources"
down_revision = "0015_manual_report_context"
branch_labels = None
depends_on = None


def upgrade():
    conn = op.get_bind()
    for name in ("fhir_laboratory_sources", "fhir_laboratory_observations",
                 "fhir_laboratory_commands"):
        if conn.execute(text("SELECT to_regclass(:name)"), {"name": "clinical_source." + name}).scalar_one() is not None:
            raise CommandError("Existing FHIR laboratory owner requires explicit reconciliation")
    op.execute("""
        CREATE TABLE clinical_source.fhir_laboratory_sources (
            source_id text PRIMARY KEY REFERENCES clinical_source.source_versions(source_id),
            case_id text NOT NULL REFERENCES coordination.patient_case_bindings(case_id),
            subject_reference text NOT NULL,
            specimen_reference text NOT NULL,
            specimen_type_text text NOT NULL CHECK (char_length(specimen_type_text) BETWEEN 1 AND 100),
            specimen_collected_at text NOT NULL,
            report_reference text NOT NULL,
            parser_contract text NOT NULL CHECK (parser_contract='oi.fhir-r4-laboratory-source/1'),
            clinical_review text NOT NULL CHECK (clinical_review='not_performed'),
            created_at timestamptz NOT NULL DEFAULT clock_timestamp()
        );
        CREATE TABLE clinical_source.fhir_laboratory_observations (
            source_id text NOT NULL REFERENCES clinical_source.fhir_laboratory_sources(source_id),
            ordinal integer NOT NULL CHECK (ordinal BETWEEN 1 AND 16),
            observation_reference text NOT NULL,
            loinc_code text NOT NULL,
            effective_at text NOT NULL,
            issued_at text NOT NULL,
            status text NOT NULL CHECK (status IN ('reported_value','reported_absent')),
            value_text text,
            unit_code text,
            absent_reason text,
            source_reported boolean NOT NULL CHECK (source_reported),
            clinical_review text NOT NULL CHECK (clinical_review='not_performed'),
            PRIMARY KEY(source_id,observation_reference),
            UNIQUE(source_id,ordinal),
            CHECK (
                (status='reported_value' AND value_text IS NOT NULL AND unit_code IS NOT NULL AND absent_reason IS NULL)
                OR
                (status='reported_absent' AND value_text IS NULL AND unit_code IS NULL AND absent_reason IS NOT NULL)
            )
        );
        CREATE TABLE clinical_source.fhir_laboratory_commands (
            case_id text NOT NULL REFERENCES coordination.patient_case_bindings(case_id),
            request_key text NOT NULL,
            intent_sha256 char(64) NOT NULL CHECK (intent_sha256 ~ '^[0-9a-f]{64}$'),
            source_id text NOT NULL REFERENCES clinical_source.fhir_laboratory_sources(source_id),
            result text NOT NULL CHECK (result IN ('imported','duplicate')),
            actor text NOT NULL,
            purpose text NOT NULL CHECK (purpose='operations'),
            created_at timestamptz NOT NULL DEFAULT clock_timestamp(),
            PRIMARY KEY(case_id,request_key)
        );
        CREATE FUNCTION clinical_source.guard_fhir_laboratory_source_insert() RETURNS trigger
        LANGUAGE plpgsql AS $$
        BEGIN
            IF NOT EXISTS (
                SELECT 1 FROM clinical_source.source_versions s
                WHERE s.source_id=NEW.source_id AND s.case_id=NEW.case_id AND s.kind='laboratory'
            ) THEN RAISE EXCEPTION 'OI-FHIR-LAB-SOURCE-BOUNDARY'; END IF;
            RETURN NEW;
        END; $$;
        CREATE FUNCTION clinical_source.guard_fhir_laboratory_command_insert() RETURNS trigger
        LANGUAGE plpgsql AS $$
        BEGIN
            IF NOT EXISTS (
                SELECT 1 FROM clinical_source.fhir_laboratory_sources f
                WHERE f.source_id=NEW.source_id AND f.case_id=NEW.case_id
            ) THEN RAISE EXCEPTION 'OI-FHIR-LAB-COMMAND-BOUNDARY'; END IF;
            RETURN NEW;
        END; $$;
        CREATE TRIGGER oi_fhir_lab_source_insert BEFORE INSERT ON clinical_source.fhir_laboratory_sources
            FOR EACH ROW EXECUTE FUNCTION clinical_source.guard_fhir_laboratory_source_insert();
        CREATE TRIGGER oi_fhir_lab_command_insert BEFORE INSERT ON clinical_source.fhir_laboratory_commands
            FOR EACH ROW EXECUTE FUNCTION clinical_source.guard_fhir_laboratory_command_insert();
        CREATE TRIGGER oi_fhir_lab_source_update BEFORE UPDATE ON clinical_source.fhir_laboratory_sources
            FOR EACH ROW EXECUTE FUNCTION identity.reject_registry_history_mutation();
        CREATE TRIGGER oi_fhir_lab_source_delete BEFORE DELETE ON clinical_source.fhir_laboratory_sources
            FOR EACH ROW EXECUTE FUNCTION identity.reject_registry_history_mutation();
        CREATE TRIGGER oi_fhir_lab_obs_update BEFORE UPDATE ON clinical_source.fhir_laboratory_observations
            FOR EACH ROW EXECUTE FUNCTION identity.reject_registry_history_mutation();
        CREATE TRIGGER oi_fhir_lab_obs_delete BEFORE DELETE ON clinical_source.fhir_laboratory_observations
            FOR EACH ROW EXECUTE FUNCTION identity.reject_registry_history_mutation();
        CREATE TRIGGER oi_fhir_lab_cmd_update BEFORE UPDATE ON clinical_source.fhir_laboratory_commands
            FOR EACH ROW EXECUTE FUNCTION identity.reject_registry_history_mutation();
        CREATE TRIGGER oi_fhir_lab_cmd_delete BEFORE DELETE ON clinical_source.fhir_laboratory_commands
            FOR EACH ROW EXECUTE FUNCTION identity.reject_registry_history_mutation();
    """)


def downgrade():
    conn = op.get_bind()
    populated = conn.execute(text("""
        SELECT EXISTS(SELECT 1 FROM clinical_source.fhir_laboratory_sources)
            OR EXISTS(SELECT 1 FROM clinical_source.fhir_laboratory_observations)
            OR EXISTS(SELECT 1 FROM clinical_source.fhir_laboratory_commands)
    """)).scalar_one()
    if populated:
        raise CommandError("Preserved FHIR laboratory history requires explicit reconciliation before downgrade")
    op.execute("DROP TABLE clinical_source.fhir_laboratory_commands")
    op.execute("DROP TABLE clinical_source.fhir_laboratory_observations")
    op.execute("DROP TABLE clinical_source.fhir_laboratory_sources")
    op.execute("DROP FUNCTION clinical_source.guard_fhir_laboratory_command_insert()")
    op.execute("DROP FUNCTION clinical_source.guard_fhir_laboratory_source_insert()")
