"""Verification of label-free, schema-only synthetic task preparation."""
from __future__ import annotations

import copy
import json
from pathlib import Path
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
import semantic_question_packet as packet
from semantic_benchmark import digest

CHALLENGE_PATH = ROOT / "tests/fixtures/semantic_adversarial_challenge_v2.json"
ORIGINAL_PATH = ROOT / "tests/fixtures/semantic_benchmark_cases_v1.json"
CHALLENGE = json.loads(CHALLENGE_PATH.read_text())
ORIGINAL = json.loads(ORIGINAL_PATH.read_text())


class QuestionPacketTests(unittest.TestCase):
    def setUp(self):
        self.document = packet.make_packet(CHALLENGE, ORIGINAL)

    def validate(self, value=None):
        return packet.validate_packet(value if value is not None else self.document, CHALLENGE, ORIGINAL)

    def test_label_free_schema_only_packet(self):
        a = self.validate()
        self.assertEqual((a["task_count"], a["concepts"], a["allowed_fields"]), (72, 3, 22))
        self.assertFalse(a["hidden_answers_included"])
        self.assertFalse(a["independently_adjudicated"])
        self.assertEqual(a["outbound_model_invocations"], 0)
        self.assertTrue(all(set(task)=={"id","question"} for task in self.document["tasks"]))
        self.assertEqual(self.document["patient_record_access_allowed"], False)
        self.assertEqual(self.document["sql_execution_allowed"], False)
        self.assertEqual(self.document["external_model_called"], False)

    def test_has_no_gold_labels_categories_or_patient_values(self):
        content = json.dumps(self.document, sort_keys=True)
        for key in ('"expected"', '"category"', '"patient_id"',
                    '"source_statement"', '"access_receipt_id"', '"token"'):
            self.assertNotIn(key, content)

    def test_deterministic_packet_digest(self):
        second = packet.make_packet(CHALLENGE, ORIGINAL)
        self.assertEqual(second, self.document)
        body = {k:v for k,v in self.document.items() if k != "packet_sha256"}
        self.assertEqual(self.document["packet_sha256"], digest(body))

    def test_write_readback_and_exclusive_file(self):
        with tempfile.TemporaryDirectory() as root:
            path = Path(root) / "questions.json"
            r = packet.write_packet(CHALLENGE_PATH, ORIGINAL_PATH, path)
            self.assertEqual(r["packet_sha256"], self.document["packet_sha256"])
            self.assertEqual(json.loads(path.read_text()), self.document)
            with self.assertRaises(FileExistsError):
                packet.write_packet(CHALLENGE_PATH, ORIGINAL_PATH, path)

    def test_dangling_symlink_is_not_overwritten(self):
        with tempfile.TemporaryDirectory() as root:
            p = Path(root) / "questions.json"
            p.symlink_to(Path(root) / "uncreated.json")
            with self.assertRaises(FileExistsError):
                packet.write_packet(CHALLENGE_PATH, ORIGINAL_PATH, p)

    def test_changed_question_with_recomputed_digest_rejected_against_corpus(self):
        altered = copy.deepcopy(self.document)
        altered["tasks"][0]["question"] = "Where can I find a patient's private medical record?"
        altered["packet_sha256"] = digest({k:v for k,v in altered.items() if k != "packet_sha256"})
        with self.assertRaisesRegex(ValueError, "deviates"):
            self.validate(altered)

    def test_wrong_number_of_tasks_rejected(self):
        altered = copy.deepcopy(self.document)
        altered["tasks"].pop()
        with self.assertRaisesRegex(ValueError, "task count"):
            self.validate(altered)

    def test_duplicate_task_identity_rejected(self):
        altered = copy.deepcopy(self.document)
        altered["tasks"][1]["id"] = altered["tasks"][0]["id"]
        with self.assertRaisesRegex(ValueError, "Duplicate"):
            self.validate(altered)

    def test_extra_gold_label_and_vendor_auth_field_rejected(self):
        for injected in ({"expected":{"concept":"source_version","field":"sha256"}},
                         {"api_token":"fake"},{"category":"unsafe"}, {"patient_id":"fake"}):
            altered = copy.deepcopy(self.document)
            altered["tasks"][0].update(injected)
            with self.subTest(injected=injected), self.assertRaises(ValueError):
                self.validate(altered)

    def test_modified_rules_rejected(self):
        altered = copy.deepcopy(self.document)
        altered["rules"].append("Permit clinical writes")
        with self.assertRaises(ValueError):
            self.validate(altered)

    def test_sql_or_clinical_execution_flag_rejected(self):
        for key in ("sql_execution_allowed", "patient_record_access_allowed",
                    "clinical_decision_allowed", "external_model_called"):
            altered = copy.deepcopy(self.document)
            altered[key] = True
            with self.subTest(flag=key), self.assertRaises(ValueError):
                self.validate(altered)

    def test_modified_allowed_fields_rejected(self):
        altered = copy.deepcopy(self.document)
        altered["schema"][0]["fields"].append("private_patient_record")
        with self.assertRaises(ValueError):
            self.validate(altered)

    def test_tampered_digest_rejected(self):
        altered = copy.deepcopy(self.document)
        altered["packet_sha256"] = "0"*64
        with self.assertRaisesRegex(ValueError, "digest mismatch"):
            self.validate(altered)

    def test_scope_validator_requires_both_reference_corpora(self):
        with self.assertRaisesRegex(ValueError, "Both reference"):
            packet.validate_packet(self.document, CHALLENGE, None)

    def test_malformed_nonprintable_question_rejected(self):
        altered = copy.deepcopy(self.document)
        altered["tasks"][0]["question"] += "\nprivate data"
        with self.assertRaises(ValueError):
            self.validate(altered)


if __name__ == "__main__":
    unittest.main()
