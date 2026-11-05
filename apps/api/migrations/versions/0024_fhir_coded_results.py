"""Preserve source-reported fictional result Codings alongside quantity and absence."""
from alembic import op
from alembic.util.exc import CommandError

revision = "0024_fhir_coded_results"
down_revision = "0023_dicom_mr_custody"
branch_labels = None
depends_on = None


def upgrade():
    conn = op.get_bind()
    conn.exec_driver_sql("""
        ALTER TABLE clinical_source.fhir_laboratory_sources
            DROP CONSTRAINT fhir_laboratory_sources_profile_contract_check,
            ADD CONSTRAINT fhir_laboratory_sources_profile_contract_check CHECK (
                profile_contract IN ('oi.fhir-r4-laboratory-custody/1','oi.fhir-r4-laboratory-custody/2')
            );
        ALTER TABLE clinical_source.fhir_laboratory_observations
            ADD COLUMN coded_result jsonb,
            DROP CONSTRAINT fhir_laboratory_observations_status_check,
            DROP CONSTRAINT fhir_laboratory_observations_check,
            ADD CONSTRAINT fhir_laboratory_observations_result_check CHECK ((
                CASE status
                WHEN 'reported_value' THEN
                    char_length(value_text) BETWEEN 1 AND 64
                    AND char_length(unit_code) BETWEEN 1 AND 32
                    AND absent_reason IS NULL AND coded_result IS NULL
                WHEN 'reported_absent' THEN
                    value_text IS NULL AND unit_code IS NULL AND coded_result IS NULL
                    AND absent_reason IN ('unknown','not-performed','error','masked')
                WHEN 'reported_coded' THEN
                    value_text IS NULL AND unit_code IS NULL AND absent_reason IS NULL AND
                    CASE WHEN jsonb_typeof(coded_result) = 'object' THEN
                        coded_result - ARRAY['system','code','version','display'] = '{}'::jsonb
                        AND coded_result @> '{"system":"urn:oi:synthetic:lab-results"}'::jsonb
                        AND jsonb_typeof(coded_result->'code') = 'string'
                        AND (coded_result->>'code') COLLATE "C" ~ '^[A-Za-z0-9][A-Za-z0-9._-]{0,63}$'
                        AND (NOT (coded_result ? 'version') OR (
                            jsonb_typeof(coded_result->'version') = 'string' AND
                            (coded_result->>'version') COLLATE "C" ~ '^[A-Za-z0-9][A-Za-z0-9._-]{0,63}$'))
                        AND (NOT (coded_result ? 'display') OR (
                            jsonb_typeof(coded_result->'display') = 'string' AND
                            (coded_result->>'display') COLLATE "C" ~ '^[ -~]{1,120}$' AND
                            (coded_result->>'display') = btrim(coded_result->>'display', ' ')))
                    ELSE false END
                ELSE false END
            ) IS TRUE);

        CREATE FUNCTION clinical_source.verify_fhir_laboratory_result_profile() RETURNS trigger
        LANGUAGE plpgsql AS $oi_lab_profile$
        BEGIN
            IF (SELECT profile_contract='oi.fhir-r4-laboratory-custody/2'
                  FROM clinical_source.fhir_laboratory_sources WHERE source_id=NEW.source_id)
                IS DISTINCT FROM EXISTS (
                    SELECT 1 FROM clinical_source.fhir_laboratory_observations
                    WHERE source_id=NEW.source_id AND status='reported_coded'
                ) THEN
                RAISE EXCEPTION 'OI-FHIR-LAB-RESULT-PROFILE';
            END IF;
            RETURN NULL;
        END;
        $oi_lab_profile$;

        CREATE CONSTRAINT TRIGGER oi_fhir_new_coded_profile
            AFTER INSERT ON clinical_source.fhir_laboratory_sources
            DEFERRABLE INITIALLY DEFERRED FOR EACH ROW
            WHEN (NEW.profile_contract='oi.fhir-r4-laboratory-custody/2')
            EXECUTE FUNCTION clinical_source.verify_fhir_laboratory_result_profile();
        CREATE CONSTRAINT TRIGGER oi_fhir_new_coded_result
            AFTER INSERT ON clinical_source.fhir_laboratory_observations
            DEFERRABLE INITIALLY DEFERRED FOR EACH ROW
            WHEN (NEW.status='reported_coded')
            EXECUTE FUNCTION clinical_source.verify_fhir_laboratory_result_profile()
    """)


def downgrade():
    conn = op.get_bind()
    conn.exec_driver_sql("""
        LOCK TABLE clinical_source.fhir_laboratory_sources,
                   clinical_source.fhir_laboratory_observations IN ACCESS EXCLUSIVE MODE
    """)
    if conn.exec_driver_sql("""
        SELECT EXISTS (SELECT 1 FROM clinical_source.fhir_laboratory_sources
                       WHERE profile_contract = 'oi.fhir-r4-laboratory-custody/2')
            OR EXISTS (SELECT 1 FROM clinical_source.fhir_laboratory_observations
                       WHERE status='reported_coded' OR coded_result IS NOT NULL)
    """).scalar_one():
        raise CommandError("Coded laboratory history requires explicit reconciliation before downgrade")
    conn.exec_driver_sql("""
        DROP TRIGGER oi_fhir_new_coded_profile ON clinical_source.fhir_laboratory_sources;
        DROP TRIGGER oi_fhir_new_coded_result ON clinical_source.fhir_laboratory_observations;
        DROP FUNCTION clinical_source.verify_fhir_laboratory_result_profile();
        ALTER TABLE clinical_source.fhir_laboratory_observations
            DROP CONSTRAINT fhir_laboratory_observations_result_check,
            DROP COLUMN coded_result,
            ADD CONSTRAINT fhir_laboratory_observations_status_check
                CHECK (status IN ('reported_value','reported_absent')),
            ADD CONSTRAINT fhir_laboratory_observations_check CHECK (
                (status='reported_value' AND value_text IS NOT NULL
                 AND char_length(value_text) BETWEEN 1 AND 64
                 AND unit_code IS NOT NULL AND char_length(unit_code) BETWEEN 1 AND 32
                 AND absent_reason IS NULL)
                OR (status='reported_absent' AND value_text IS NULL AND unit_code IS NULL
                 AND absent_reason IN ('unknown','not-performed','error','masked'))
            );
        ALTER TABLE clinical_source.fhir_laboratory_sources
            DROP CONSTRAINT fhir_laboratory_sources_profile_contract_check,
            ADD CONSTRAINT fhir_laboratory_sources_profile_contract_check
                CHECK (profile_contract='oi.fhir-r4-laboratory-custody/1')
    """)
