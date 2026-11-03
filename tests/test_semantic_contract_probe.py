"""Offline negative-control tests for proposed semantic metadata interoperability."""
import copy
import importlib.util
from pathlib import Path
import unittest

MODULE_PATH = Path(__file__).resolve().parents[1] / "tools" / "semantic_contract_probe.py"
spec = importlib.util.spec_from_file_location("semantic_contract_probe", MODULE_PATH)
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)


class SemanticContractProbeTests(unittest.TestCase):
    def setUp(self):
        self.candidate = {
            "contract": mod.CANDIDATE_CONTRACT,
            "source_manifest_sha256": mod.schema_manifest()["sha256"],
            "mappings": [{
                "concept": "source_version", "field": "source_id",
                "candidate_term": "source_version_identifier",
                "review_state": "unreviewed_proposal",
            }],
        }

    def test_manifest_is_deterministic_and_schema_only(self):
        a = mod.schema_manifest()
        self.assertEqual(a, mod.schema_manifest())
        self.assertFalse(a["allows_patient_data"])
        self.assertFalse(a["allows_database_connections"])
        self.assertFalse(a["allows_sql_generation_or_execution"])
        self.assertFalse(a["clinical_ontology_authoritative"])
        self.assertNotIn("patient_id", str(a))
        self.assertNotIn("source_statement", str(a))

    def test_valid_proposal_is_never_approved(self):
        result = mod.validate_mapping_candidate(self.candidate)
        self.assertFalse(result["semantic_accuracy_verified"])
        self.assertFalse(result["clinical_interpretation_authorized"])
        self.assertFalse(result["clinical_action_authorized"])
        self.assertFalse(result["writes_performed"])

    def test_rejects_raw_sql_or_extra_patient_data(self):
        for key in ("sql", "patient_id", "source_text", "connection_string"):
            candidate = copy.deepcopy(self.candidate)
            candidate[key] = "SELECT * FROM patients"
            with self.subTest(key=key), self.assertRaises(ValueError):
                mod.validate_mapping_candidate(candidate)

    def test_rejects_untrusted_row_values(self):
        candidate = copy.deepcopy(self.candidate)
        candidate["mappings"][0]["patient_value"] = "sensitive"
        with self.assertRaises(ValueError):
            mod.validate_mapping_candidate(candidate)

    def test_rejects_wrong_manifest(self):
        candidate = copy.deepcopy(self.candidate)
        candidate["source_manifest_sha256"] = "0" * 64
        with self.assertRaises(ValueError):
            mod.validate_mapping_candidate(candidate)

    def test_rejects_unlisted_field(self):
        candidate = copy.deepcopy(self.candidate)
        candidate["mappings"][0]["field"] = "clinical_treatment_recommendation"
        with self.assertRaises(ValueError):
            mod.validate_mapping_candidate(candidate)

    def test_rejects_unlisted_concept(self):
        candidate = copy.deepcopy(self.candidate)
        candidate["mappings"][0]["concept"] = "private_patient_table"
        with self.assertRaises(ValueError):
            mod.validate_mapping_candidate(candidate)

    def test_rejects_promotion_to_reviewed(self):
        candidate = copy.deepcopy(self.candidate)
        candidate["mappings"][0]["review_state"] = "clinician_approved"
        with self.assertRaises(ValueError):
            mod.validate_mapping_candidate(candidate)

    def test_rejects_duplicate_field(self):
        candidate = copy.deepcopy(self.candidate)
        candidate["mappings"].append(candidate["mappings"][0])
        with self.assertRaises(ValueError):
            mod.validate_mapping_candidate(candidate)

    def test_rejects_free_text_terms(self):
        for value in ("Patient Name", "foo;DROP TABLE", "", "x" * 65, 7):
            candidate = copy.deepcopy(self.candidate)
            candidate["mappings"][0]["candidate_term"] = value
            with self.subTest(value=value), self.assertRaises(ValueError):
                mod.validate_mapping_candidate(candidate)

    def test_rejects_non_dict_or_empty_or_oversized(self):
        with self.assertRaises(ValueError):
            mod.validate_mapping_candidate([])
        for rows in ([], self.candidate["mappings"] * 33):
            candidate = copy.deepcopy(self.candidate)
            candidate["mappings"] = rows
            with self.assertRaises(ValueError):
                mod.validate_mapping_candidate(candidate)


if __name__ == "__main__":
    unittest.main()
