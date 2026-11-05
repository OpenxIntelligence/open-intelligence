"""Reference-only links between the H1 encounter, case binding and source owners."""
from open_intelligence.clinical_encounters import ClinicalConflict, EncounterNotFound, _opaque
from open_intelligence.patient_registry import PatientRegistryDenied, _key
from open_intelligence.store import InvalidInput

from .source_integrity import SourceIntegrityError
from .sources import PostgresSourceVersions


class PostgresEncounterSources:
    """Use the encounter route's transaction, patient lock and final authority check."""

    def __init__(self, patients):
        self.patients = patients
        self.sources = PostgresSourceVersions(patients)

    def _scope(self, patient_id, encounter_id, case_id, organization, purpose):
        if not self.patients._transaction_active:
            raise RuntimeError("Encounter source access requires an active patient transaction")
        if purpose != "operations":
            raise PatientRegistryDenied("Encounter unavailable")
        self.sources._binding(patient_id, case_id, organization, purpose)
        if not self.patients._fetchone(
            "SELECT id FROM ehr.clinical_encounters WHERE id=%s AND patient_id=%s FOR SHARE",
            (encounter_id, patient_id),
        ):
            raise EncounterNotFound("Encounter unavailable")

    def _original(self, case_id, source_id):
        # Reviewed document intake owns a different format and authority boundary.
        if self.sources._is_reviewed(source_id):
            raise PatientRegistryDenied("Source unavailable")
        source, _ = self.sources._validated_original(case_id, source_id)
        return source

    def link(self, patient_id, encounter_id, case_id, source_id, expected_version,
             expected_sha256, request_key, *, actor, organization, purpose):
        self._scope(patient_id, encounter_id, case_id, organization, purpose)
        _opaque(request_key, "request_key")
        _key(actor, "actor")
        source = self._original(case_id, source_id)
        if (source["version"], source["sha256"]) != (expected_version, expected_sha256):
            raise ClinicalConflict("Source version conflict")
        intent = (encounter_id, case_id, source_id, expected_version, expected_sha256,
                  organization, actor, purpose)
        previous = self.patients._fetchone(
            "SELECT id,encounter_id,case_id,source_id,version,sha256,origin_org,actor,purpose "
            "FROM ehr.encounter_source_links WHERE patient_id=%s AND request_key=%s",
            (patient_id, request_key),
        )
        if previous is not None:
            if tuple(previous[1:]) != intent:
                raise ClinicalConflict("Request key already used")
            return {"id": previous[0], "duplicate": True}
        if source["state"] != "current":
            raise ClinicalConflict("Source version superseded")
        row = self.patients._fetchone(
            "INSERT INTO ehr.encounter_source_links(patient_id,request_key,encounter_id,case_id,"
            "source_id,version,sha256,origin_org,actor,purpose) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s) "
            "ON CONFLICT DO NOTHING RETURNING id", (patient_id, request_key, *intent),
        )
        if row is None:
            raise ClinicalConflict("Encounter source already linked or key already used")
        self.patients.append_event(patient_id, "clinical_encounter_source_linked",
            link_id=row[0], encounter_id=encounter_id, case_id=case_id, source_id=source_id,
            source_version=expected_version, sha256=expected_sha256, actor=actor, purpose=purpose)
        return {"id": row[0], "duplicate": False}

    def list(self, patient_id, encounter_id, case_id, after_id, limit, *, organization):
        if type(after_id) is not int or not 0 <= after_id <= 2**63-1 or type(limit) is not int or not 1 <= limit <= 26:
            raise InvalidInput("Invalid encounter source page")
        self._scope(patient_id, encounter_id, case_id, organization, "operations")
        rows = self.patients._fetchall(
            "SELECT id,source_id,version,sha256 FROM ehr.encounter_source_links "
            "WHERE encounter_id=%s AND patient_id=%s AND case_id=%s AND origin_org=%s AND id>%s "
            "ORDER BY id LIMIT %s", (encounter_id, patient_id, case_id, organization, after_id, limit),
        )
        result = []
        for link_id, source_id, version, sha256 in rows:
            source = self._original(case_id, source_id)
            if (version, sha256) != (source["version"], source["sha256"]):
                raise SourceIntegrityError("Stored encounter source reference mismatch")
            result.append(dict(id=link_id, encounter_id=encounter_id, patient_id=patient_id, case_id=case_id,
                               source_id=source_id, version=version, sha256=sha256, source_state=source["state"]))
        return result
