"""Real PostgreSQL custody, migration and refusal checks on fictional results."""
import json
from copy import deepcopy

from alembic.util.exc import CommandError
from pg8000.exceptions import DatabaseError
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError

from oi_api.contracts import SCHEMA_REVISION
from oi_api.laboratory_fhir_r4 import prepare_laboratory_bundle
from oi_api.laboratory_fhir_store import PostgresLaboratoryFHIR
from oi_api.migrate import migrate
from oi_api.source_integrity import SourceIntegrityError
from oi_api.sources import PostgresSourceVersions
from open_intelligence.patient_registry import PatientRegistryError
import test_evidence_convergence_migrations as evidence
from test_laboratory_coded_results import ABSENT, CODING, coded_bundle
from test_laboratory_fhir_r4 import encode, example, resource
from test_source_versions import SourceVersionFixture

PARENT = "0023_dicom_mr_custody"
CASE = "CASE-ALPHA"
TABLE = "clinical_source.fhir_laboratory_observations"


class CodedLaboratoryMigrationTests(SourceVersionFixture):
    services = evidence.EvidenceConvergenceMigrationTests.services
    start_at = evidence.EvidenceConvergenceMigrationTests.start_at
    snapshot = evidence.EvidenceConvergenceMigrationTests.snapshot

    def prepared(self, bundle):
        raw = encode(bundle).replace(b"FICTIONAL-PATIENT-A", b"UPGRADE-SUBJECT")
        return prepare_laboratory_bundle(raw, expected_subject_reference="Patient/UPGRADE-SUBJECT")

    def ingest(self, patient, prepared, key, previous=None):
        with self.services() as registry:
            return PostgresLaboratoryFHIR(registry).import_bundle(
                patient, CASE, prepared, **evidence.OPTIONS,
                request_key=key, expected_previous_source_id=previous)

    def test_deferred_profile_checks_refuse_both_mismatches_and_admit_mixed_sources(self):
        patient, _, _ = self.start_at(PARENT)
        quantity = self.prepared(example())
        legacy = self.ingest(patient, quantity, "LEGACY-RESULT")
        migrate(self.admin, "upgrade", SCHEMA_REVISION)
        mixed = coded_bundle()
        report = resource(mixed, "DiagnosticReport")
        report["id"] = "FICTIONAL-MIXED-PROFILE"
        numeric = deepcopy(example()["entry"][2])
        numeric["resource"]["id"] = "FICTIONAL-OBS-NUMERIC"
        numeric["fullUrl"] = "urn:uuid:00000000-0000-4000-8000-000000000010"
        mixed["entry"].append(numeric)
        report["result"].append({"reference": numeric["fullUrl"]})
        absent = deepcopy(numeric)
        absent["resource"]["id"] = "FICTIONAL-OBS-ABSENT"
        absent["fullUrl"] = "urn:uuid:00000000-0000-4000-8000-000000000011"
        del absent["resource"]["valueQuantity"]
        absent["resource"]["dataAbsentReason"] = ABSENT
        mixed["entry"].append(absent)
        report["result"].append({"reference": absent["fullUrl"]})
        typed = self.ingest(patient, self.prepared(mixed), "MIXED-RESULT")
        with self.engine.connect() as conn:
            self.assertEqual(set(conn.execute(text(f"SELECT status FROM {TABLE} WHERE source_id=:id"),
                             {"id": typed["source_id"]}).scalars()),
                             {"reported_coded", "reported_absent", "reported_value"})
        before = self.snapshot()

        # A well-formed coded child may not be committed under a /1 source.
        with self.assertRaisesRegex(DBAPIError, "OI-FHIR-LAB-RESULT-PROFILE"):
            with self.engine.begin() as conn:
                conn.execute(text(f"""
                    INSERT INTO {TABLE}
                    SELECT (jsonb_populate_record(NULL::{TABLE}, to_jsonb(o) || CAST(:changes AS jsonb))).*
                    FROM {TABLE} o WHERE source_id=:typed AND status='reported_coded'
                """), {"typed": typed["source_id"], "changes": json.dumps({
                    "source_id": legacy["source_id"], "position": 2,
                    "observation_reference": "Observation/FICTIONAL-SECOND"})})
        self.assertEqual(self.snapshot(), before)

        # A /2 parent alone may be inserted while children are being written,
        # but committing that transaction must refuse it and its new source.
        source = "SRC-" + "F" * 32
        with self.assertRaisesRegex(DBAPIError, "OI-FHIR-LAB-RESULT-PROFILE"):
            with self.engine.begin() as conn:
                conn.execute(text("""
                    INSERT INTO clinical_source.source_versions
                    SELECT (jsonb_populate_record(NULL::clinical_source.source_versions,
                        to_jsonb(s) || CAST(:changes AS jsonb))).*
                    FROM clinical_source.source_versions s WHERE source_id=:old
                """), {"old": typed["source_id"], "changes": json.dumps({
                    "source_id": source, "document_id": "FICTIONAL-NO-CODED-CHILD"})})
                conn.execute(text("""
                    INSERT INTO clinical_source.fhir_laboratory_sources
                    SELECT (jsonb_populate_record(NULL::clinical_source.fhir_laboratory_sources,
                        to_jsonb(f) || CAST(:changes AS jsonb))).*
                    FROM clinical_source.fhir_laboratory_sources f WHERE source_id=:old
                """), {"old": typed["source_id"], "changes": json.dumps({"source_id": source})})
        self.assertEqual(self.snapshot(), before)

    def test_populated_upgrade_preserves_legacy_rows_profiles_and_historical_originals(self):
        patient, _, _ = self.start_at(PARENT)
        quantity = self.prepared(example())
        one = self.ingest(patient, quantity, "CODED-NUMERIC")
        bundle = example()
        observation = resource(bundle, "Observation")
        del observation["valueQuantity"]
        observation["dataAbsentReason"] = ABSENT
        absent = self.prepared(bundle)
        two = self.ingest(patient, absent, "CODED-ABSENT", one["source_id"])
        coded = self.prepared(coded_bundle())
        before = self.snapshot()
        # The old storage owner cannot silently drop a newly supported value.
        # This direct migration fixture does not bypass the HTTP readiness gate.
        with self.assertRaisesRegex(DatabaseError, "profile_contract_check"):
            self.ingest(patient, coded, "CODED-RESULT", two["source_id"])
        self.assertEqual(self.snapshot(), before)
        migrate(self.admin, "upgrade", SCHEMA_REVISION)
        self.assertEqual(self.snapshot(), before)
        with self.engine.connect() as conn:
            self.assertEqual(conn.execute(text(f"SELECT count(*) FROM {TABLE} WHERE coded_result IS NULL"))
                             .scalar_one(), 2)
        migrate(self.admin, "downgrade", PARENT)
        self.assertEqual(self.snapshot(), before)
        migrate(self.admin, "upgrade", SCHEMA_REVISION)
        three = self.ingest(patient, coded, "CODED-RESULT", two["source_id"])
        self.assertEqual(three["version"], 3)
        # Freeze the coded original too: a newer quantity may supersede it,
        # yet its source and /2 profile must still block downgrade.
        amended = example()
        resource(amended, "Observation")["valueQuantity"]["value"] = 6
        latest = self.prepared(amended)
        four = self.ingest(patient, latest, "CODED-AMENDMENT", three["source_id"])
        self.assertEqual(self.ingest(patient, coded, "CODED-RESULT", two["source_id"]),
                         three | {"duplicate": True})
        with self.services() as registry, registry.transaction():
            sources = PostgresSourceVersions(registry)
            for receipt, prepared in ((one, quantity), (two, absent), (three, coded), (four, latest)):
                self.assertEqual(sources._validated_original(CASE, receipt["source_id"])[1], prepared.original_bytes)
        with self.engine.connect() as conn:
            self.assertEqual(conn.execute(text("""
                SELECT profile_contract FROM clinical_source.fhir_laboratory_sources
                JOIN clinical_source.source_versions USING (source_id) ORDER BY version
            """)).scalars().all(), [x.profile_contract for x in (quantity, absent, coded, latest)])
        after = self.snapshot()
        with self.assertRaisesRegex(CommandError, "Coded laboratory history"):
            migrate(self.admin, "downgrade", PARENT)
        self.assertEqual(self.snapshot(), after)
        with self.engine.connect() as conn:
            self.assertEqual(conn.execute(text("SELECT version_num FROM public.alembic_version")).scalar_one(),
                             SCHEMA_REVISION)

        # Model a restored, schema-valid but false display in an old version.
        with self.engine.begin() as conn:
            conn.execute(text(f"ALTER TABLE {TABLE} DISABLE TRIGGER oi_fhir_observation_update_guard"))
            conn.execute(text(f"UPDATE {TABLE} SET coded_result=coded_result - 'display' WHERE source_id=:id"),
                         {"id": three["source_id"]})
            conn.execute(text(f"ALTER TABLE {TABLE} ENABLE TRIGGER oi_fhir_observation_update_guard"))
        with self.services() as registry:
            with self.assertRaises(SourceIntegrityError), registry.transaction():
                PostgresSourceVersions(registry)._validated_original(CASE, three["source_id"])
            with self.assertRaises(SourceIntegrityError):
                PostgresSourceVersions(registry).list(patient, CASE, **evidence.OPTIONS)

    def test_constraint_rejects_malformed_and_cross_arm_variants_including_sql_and_json_null(self):
        patient, _, _ = self.start_at(PARENT)
        migrate(self.admin, "upgrade", SCHEMA_REVISION)
        owner = self.prepared(coded_bundle())
        tampered = self.prepared(coded_bundle())
        tampered.observations[0]["coded_result"]["code"] = "Changed"
        with self.assertRaisesRegex(PatientRegistryError, "differs from its original"):
            self.ingest(patient, tampered, "TAMPERED-RESULT")
        receipt = self.ingest(patient, owner, "CODED-RESULT")
        with self.services() as registry, registry.transaction():
            projected, = PostgresLaboratoryFHIR(registry).current_observations_locked(CASE)
            self.assertEqual((projected["status"], projected["coded_result"]), ("reported_coded", CODING))
        params = {"id": receipt["source_id"], "status": "reported_coded", "value": None, "unit": None,
                  "absent": None, "result": json.dumps(CODING)}
        insert = text(f"""
            INSERT INTO {TABLE}
            (source_id,observation_reference,position,loinc_code,effective_at,issued_at,status,
             value_text,unit_code,absent_reason,source_reported,clinical_review,coded_result)
            SELECT source_id,'Observation/FICTIONAL-OTHER',2,loinc_code,effective_at,issued_at,
                   :status,:value,:unit,:absent,source_reported,clinical_review,CAST(:result AS jsonb)
            FROM {TABLE} WHERE source_id=:id AND position=1
        """)
        invalid = [
            {"result": None}, {"result": "null"}, {"status": "unexpected"},
            {"value": "0"}, {"unit": "1"}, {"absent": "unknown"},
            {"status": "reported_absent", "absent": "unknown"},
            {"status": "reported_absent", "result": None},
            {"status": "reported_value", "value": "0", "unit": "1"},
            {"status": "reported_value", "value": None, "unit": "1", "result": None},
        ]
        for bad in ([], "text", {}, {"system": CODING["system"]}, {"code": "A"},
                    CODING | {"system": "urn:other"}, CODING | {"system": None},
                    CODING | {"code": 3}, CODING | {"code": None}, CODING | {"code": "-x"},
                    CODING | {"code": "x\n"}, CODING | {"code": "x" * 65}, CODING | {"code": "é"},
                    CODING | {"version": None}, CODING | {"version": []}, CODING | {"version": "1 2"},
                    CODING | {"display": None}, CODING | {"display": " text"}, CODING | {"display": "text "},
                    CODING | {"display": "x\n"}, CODING | {"display": "x" * 121}, CODING | {"unexpected": True}):
            invalid.append({"result": json.dumps(bad)})
        for overrides in invalid:
            with self.subTest(overrides=overrides):
                with self.assertRaisesRegex(DBAPIError, "fhir_laboratory_observations_result_check"):
                    with self.engine.begin() as conn:
                        conn.execute(insert, params | overrides)
        with self.engine.connect() as conn:
            self.assertEqual(conn.execute(text(f"SELECT coded_result FROM {TABLE}")).scalars().all(), [CODING])
