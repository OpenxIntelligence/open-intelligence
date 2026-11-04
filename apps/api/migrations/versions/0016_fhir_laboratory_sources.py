"""Persist bounded FHIR R4 laboratory originals under the existing source owner.

This migration adds dependent modality tables only.  The canonical source/version
row remains clinical_source.source_versions; patient/case authority remains in
the existing identity/coordination owners.  No clinical interpretation, external
FHIR connectivity, PHI permission or second patient/source ledger is introduced.
"""
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
        if conn.execute(text(
            "SELECT to_regclass('clinical_source.' || :name)"
        ), {"name": name}).scalar_one() is not None:
            raise CommandError("Existing FHIR laboratory objects require explicit reconciliation")

    conn.exec_driver_sql("""
        CREATE TABLE clinical_source.fhir_laboratory_sources (
            source_id text PRIMARY KEY
                REFERENCES clinical_source.source_versions(source_id),
            source_organization text NOT NULL
                CHECK (char_length(source_organization) BETWEEN 3 AND 128),
            source_system text NOT NULL
                CHECK (char_length(source_system) BETWEEN 3 AND 128),
            subject_reference text NOT NULL
                CHECK (char_length(subject_reference) BETWEEN 3 AND 128),
            specimen_reference text NOT NULL
                CHECK (char_length(specimen_reference) BETWEEN 3 AND 128),
            specimen_type_text text NOT NULL
                CHECK (char_length(specimen_type_text) BETWEEN 1 AND 100),
            specimen_collected_at timestamptz NOT NULL,
            report_reference text NOT NULL
                CHECK (char_length(report_reference) BETWEEN 3 AND 128),
            report_effective_at timestamptz NOT NULL,
            report_issued_at timestamptz NOT NULL,
            fhir_release text NOT NULL CHECK (fhir_release='R4'),
            profile_contract text NOT NULL
                CHECK (profile_contract='oi.fhir-r4-laboratory-custody/1'),
            observation_count integer NOT NULL CHECK (observation_count BETWEEN 1 AND 16)
        );

        CREATE TABLE clinical_source.fhir_laboratory_observations (
            source_id text NOT NULL
                REFERENCES clinical_source.fhir_laboratory_sources(source_id),
            observation_reference text NOT NULL
                CHECK (char_length(observation_reference) BETWEEN 3 AND 128),
            position integer NOT NULL CHECK (position BETWEEN 1 AND 16),
            loinc_code text NOT NULL CHECK (loinc_code ~ '^[0-9]{1,6}-[0-9]$'),
            effective_at timestamptz NOT NULL,
            issued_at timestamptz NOT NULL,
            status text NOT NULL CHECK (status IN ('reported_value','reported_absent')),
            value_text text,
            unit_code text,
            absent_reason text,
            source_reported boolean NOT NULL CHECK (source_reported),
            clinical_review text NOT NULL CHECK (clinical_review='not_performed'),
            PRIMARY KEY (source_id, observation_reference),
            UNIQUE (source_id, position),
            CHECK (
              (status='reported_value' AND value_text IS NOT NULL
                 AND char_length(value_text) BETWEEN 1 AND 64
                 AND unit_code IS NOT NULL AND char_length(unit_code) BETWEEN 1 AND 32
                 AND absent_reason IS NULL)
              OR
              (status='reported_absent' AND value_text IS NULL AND unit_code IS NULL
                 AND absent_reason IN ('unknown','not-performed','error','masked'))
            )
        );

        CREATE TABLE clinical_source.fhir_laboratory_commands (
            origin_org text NOT NULL CHECK (char_length(origin_org) BETWEEN 3 AND 128),
            patient_id text NOT NULL REFERENCES identity.identity_patients(patient_id),
            case_id text NOT NULL REFERENCES coordination.patient_case_bindings(case_id),
            request_key text NOT NULL CHECK (char_length(request_key) BETWEEN 3 AND 128),
            request_digest char(64) NOT NULL CHECK (request_digest ~ '^[0-9a-f]{64}$'),
            source_id text NOT NULL REFERENCES clinical_source.fhir_laboratory_sources(source_id),
            created_at timestamptz NOT NULL DEFAULT now(),
            PRIMARY KEY (origin_org, case_id, request_key)
        );

        CREATE FUNCTION clinical_source.guard_fhir_laboratory_source_insert() RETURNS trigger
        LANGUAGE plpgsql AS $oi_fhir_source_guard$
        DECLARE parent_kind text;
        BEGIN
          SELECT kind INTO parent_kind FROM clinical_source.source_versions
            WHERE source_id=NEW.source_id;
          IF parent_kind IS DISTINCT FROM 'laboratory' THEN
            RAISE EXCEPTION 'OI-FHIR-LAB-SOURCE-OWNER';
          END IF;
          RETURN NEW;
        END;
        $oi_fhir_source_guard$;

        CREATE FUNCTION clinical_source.guard_fhir_laboratory_command_insert() RETURNS trigger
        LANGUAGE plpgsql AS $oi_fhir_command_guard$
        DECLARE mapped_patient text;
        DECLARE source_case text;
        BEGIN
          SELECT patient_id INTO mapped_patient FROM coordination.patient_case_bindings
            WHERE case_id=NEW.case_id;
          SELECT s.case_id INTO source_case
            FROM clinical_source.source_versions s
            JOIN clinical_source.fhir_laboratory_sources f ON f.source_id=s.source_id
            WHERE f.source_id=NEW.source_id;
          IF mapped_patient IS DISTINCT FROM NEW.patient_id
             OR source_case IS DISTINCT FROM NEW.case_id THEN
            RAISE EXCEPTION 'OI-FHIR-LAB-COMMAND-SCOPE';
          END IF;
          RETURN NEW;
        END;
        $oi_fhir_command_guard$;

        CREATE TRIGGER oi_fhir_source_insert_guard BEFORE INSERT
          ON clinical_source.fhir_laboratory_sources
          FOR EACH ROW EXECUTE FUNCTION clinical_source.guard_fhir_laboratory_source_insert();
        CREATE TRIGGER oi_fhir_source_update_guard BEFORE UPDATE
          ON clinical_source.fhir_laboratory_sources
          FOR EACH ROW EXECUTE FUNCTION identity.reject_registry_history_mutation();
        CREATE TRIGGER oi_fhir_source_delete_guard BEFORE DELETE
          ON clinical_source.fhir_laboratory_sources
          FOR EACH ROW EXECUTE FUNCTION identity.reject_registry_history_mutation();

        CREATE TRIGGER oi_fhir_observation_update_guard BEFORE UPDATE
          ON clinical_source.fhir_laboratory_observations
          FOR EACH ROW EXECUTE FUNCTION identity.reject_registry_history_mutation();
        CREATE TRIGGER oi_fhir_observation_delete_guard BEFORE DELETE
          ON clinical_source.fhir_laboratory_observations
          FOR EACH ROW EXECUTE FUNCTION identity.reject_registry_history_mutation();

        CREATE TRIGGER oi_fhir_command_insert_guard BEFORE INSERT
          ON clinical_source.fhir_laboratory_commands
          FOR EACH ROW EXECUTE FUNCTION clinical_source.guard_fhir_laboratory_command_insert();
        CREATE TRIGGER oi_fhir_command_update_guard BEFORE UPDATE
          ON clinical_source.fhir_laboratory_commands
          FOR EACH ROW EXECUTE FUNCTION identity.reject_registry_history_mutation();
        CREATE TRIGGER oi_fhir_command_delete_guard BEFORE DELETE
          ON clinical_source.fhir_laboratory_commands
          FOR EACH ROW EXECUTE FUNCTION identity.reject_registry_history_mutation();
    """)


def downgrade():
    conn = op.get_bind()
    populated = conn.execute(text("""
        SELECT
          EXISTS(SELECT 1 FROM clinical_source.fhir_laboratory_sources)
          OR EXISTS(SELECT 1 FROM clinical_source.fhir_laboratory_observations)
          OR EXISTS(SELECT 1 FROM clinical_source.fhir_laboratory_commands)
    """)).scalar_one()
    if populated:
        raise CommandError("FHIR laboratory history requires explicit reconciliation before downgrade")
    for statement in (
        "DROP TABLE clinical_source.fhir_laboratory_commands",
        "DROP TABLE clinical_source.fhir_laboratory_observations",
        "DROP TABLE clinical_source.fhir_laboratory_sources",
        "DROP FUNCTION clinical_source.guard_fhir_laboratory_command_insert()",
        "DROP FUNCTION clinical_source.guard_fhir_laboratory_source_insert()",
    ):
        conn.exec_driver_sql(statement)
