"""Link existing encounters to exact, case-owned structured source versions."""
from alembic import op
from alembic.util.exc import CommandError

revision = "0022_encounter_sources"
down_revision = "0021_lab_citation_freshness"
branch_labels = None
depends_on = None


def upgrade():
    op.get_bind().exec_driver_sql("""
        ALTER TABLE ehr.clinical_encounters ADD CONSTRAINT encounter_source_patient_key
            UNIQUE (id, patient_id);
        ALTER TABLE coordination.patient_case_bindings ADD CONSTRAINT encounter_source_binding_key
            UNIQUE (case_id, patient_id, origin_org);
        ALTER TABLE clinical_source.source_versions ADD CONSTRAINT encounter_source_version_key
            UNIQUE (source_id, case_id, version, sha256);

        CREATE TABLE ehr.encounter_source_links (
            id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
            patient_id text NOT NULL, encounter_id bigint NOT NULL, case_id text NOT NULL,
            source_id text NOT NULL, version integer NOT NULL, sha256 char(64) NOT NULL,
            origin_org text NOT NULL, actor text NOT NULL CHECK (actor ~ '^[A-Za-z0-9][A-Za-z0-9_.:-]{2,127}$'),
            purpose text NOT NULL CHECK (purpose='operations'),
            request_key text NOT NULL CHECK (request_key ~ '^[A-Za-z0-9_.:-]{8,100}$'),
            created_at timestamptz NOT NULL DEFAULT now(),
            UNIQUE (patient_id, request_key),
            UNIQUE (encounter_id, source_id),
            FOREIGN KEY (encounter_id, patient_id)
                REFERENCES ehr.clinical_encounters(id, patient_id),
            FOREIGN KEY (case_id, patient_id, origin_org)
                REFERENCES coordination.patient_case_bindings(case_id, patient_id, origin_org),
            FOREIGN KEY (source_id, case_id, version, sha256)
                REFERENCES clinical_source.source_versions(source_id, case_id, version, sha256)
        );
        CREATE INDEX encounter_source_page ON ehr.encounter_source_links(encounter_id, case_id, id);

        CREATE FUNCTION ehr.guard_encounter_source_insert() RETURNS trigger LANGUAGE plpgsql AS $guard$
        BEGIN
            -- Take the same patient, then case locks as the supported source writer.
            PERFORM 1 FROM identity.identity_patients
                WHERE patient_id=NEW.patient_id AND origin_org=NEW.origin_org AND status='active' FOR SHARE;
            IF NOT FOUND THEN RAISE EXCEPTION 'OI-ENCOUNTER-SOURCE-SCOPE'; END IF;
            PERFORM 1 FROM coordination.patient_case_bindings
                WHERE case_id=NEW.case_id AND patient_id=NEW.patient_id AND origin_org=NEW.origin_org
                AND status='active' AND purpose=NEW.purpose FOR UPDATE;
            IF NOT FOUND THEN RAISE EXCEPTION 'OI-ENCOUNTER-SOURCE-SCOPE'; END IF;
            PERFORM 1 FROM clinical_source.source_versions
                WHERE source_id=NEW.source_id AND case_id=NEW.case_id AND state='current' FOR SHARE;
            IF NOT FOUND OR EXISTS (SELECT 1 FROM clinical_source.document_intakes WHERE source_id=NEW.source_id)
                THEN RAISE EXCEPTION 'OI-ENCOUNTER-SOURCE-UNAVAILABLE'; END IF;
            RETURN NEW;
        END;
        $guard$;
        CREATE TRIGGER encounter_source_scope BEFORE INSERT ON ehr.encounter_source_links
            FOR EACH ROW EXECUTE FUNCTION ehr.guard_encounter_source_insert();
        CREATE TRIGGER encounter_source_immutable BEFORE UPDATE OR DELETE ON ehr.encounter_source_links
            FOR EACH ROW EXECUTE FUNCTION identity.reject_registry_history_mutation();
        CREATE TRIGGER encounter_source_no_truncate BEFORE TRUNCATE ON ehr.encounter_source_links
            FOR EACH STATEMENT EXECUTE FUNCTION identity.reject_registry_history_mutation();
    """)


def downgrade():
    conn = op.get_bind()
    conn.exec_driver_sql("LOCK TABLE ehr.encounter_source_links IN ACCESS EXCLUSIVE MODE")
    if conn.exec_driver_sql("SELECT EXISTS(SELECT 1 FROM ehr.encounter_source_links)").scalar_one():
        raise CommandError("Populated encounter source links cannot be downgraded")
    conn.exec_driver_sql("""
        DROP TABLE ehr.encounter_source_links;
        DROP FUNCTION ehr.guard_encounter_source_insert();
        ALTER TABLE clinical_source.source_versions DROP CONSTRAINT encounter_source_version_key;
        ALTER TABLE coordination.patient_case_bindings DROP CONSTRAINT encounter_source_binding_key;
        ALTER TABLE ehr.clinical_encounters DROP CONSTRAINT encounter_source_patient_key;
    """)
