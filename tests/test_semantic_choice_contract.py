"""Unit checks for sealed 23-choice proposal contract, without model weights."""
from __future__ import annotations

import copy
import json
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

from semantic_choice_contract import (
    ABSTAIN_CODE, MODEL_CHOICE_COUNT, SCHEMA_CHOICE_COUNT,
    build_choices, choice_to_proposal, task_messages, token_ids,
)
from semantic_question_packet import make_packet
from semantic_local_model_runner import validate_run
from semantic_benchmark import digest

CHALLENGE = json.loads((ROOT / "tests/fixtures/semantic_adversarial_challenge_v2.json").read_text())
ORIGINAL = json.loads((ROOT / "tests/fixtures/semantic_benchmark_cases_v1.json").read_text())


class FakeTokenizer:
    def encode(self, string, *, add_special_tokens=False):
        return [65 + ord(string) - ord("A")]


class ChoiceContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.packet = make_packet(CHALLENGE, ORIGINAL)
        cls.choices = build_choices(cls.packet)

    def test_expected_23_labels_and_22_fields(self):
        self.assertEqual(len(self.choices), MODEL_CHOICE_COUNT)
        self.assertEqual(len(self.choices) - 1, SCHEMA_CHOICE_COUNT)
        self.assertEqual("".join(c["code"] for c in self.choices), "ABCDEFGHIJKLMNOPQRSTUVW")
        self.assertEqual(self.choices[0], {"code": ABSTAIN_CODE, "kind": "abstain"})
        self.assertEqual(len({(x["concept"], x["field"]) for x in self.choices[1:]}), 22)

    def test_fixed_option_order_and_packet_sha_do_not_change(self):
        self.assertEqual(build_choices(self.packet), self.choices)
        self.assertEqual(build_choices(copy.deepcopy(self.packet)), self.choices)

    def test_prompt_contains_no_answer_key_or_category(self):
        messages = task_messages(self.packet["tasks"][0], self.choices)
        self.assertEqual([m["role"] for m in messages], ["system", "user"])
        self.assertIn("A: ABSTAIN", messages[1]["content"])
        self.assertIn("W:", messages[1]["content"])
        self.assertIn("clinical decisions", messages[0]["content"])
        self.assertIn(self.packet["tasks"][0]["question"], messages[1]["content"])
        self.assertNotIn('"expected"', json.dumps(messages))
        self.assertNotIn('"category"', json.dumps(messages))

    def test_abstain_choice_is_not_a_clinical_approval(self):
        decision = choice_to_proposal("A", self.choices, self.packet["schema_manifest_sha256"])
        self.assertEqual(decision, {"status": "abstain"})

    def test_all_field_choices_validate_against_first_party_allowlist(self):
        for c in self.choices[1:]:
            with self.subTest(code=c["code"]):
                proposal = choice_to_proposal(c["code"], self.choices, self.packet["schema_manifest_sha256"])
                self.assertEqual(proposal, {"status": "proposed", "concept": c["concept"], "field": c["field"]})

    def test_unrecognized_choice_never_grants_access(self):
        for code in ("Z", "", "abstain", " A", "0", None, {}, ["A"]):
            with self.subTest(code=code), self.assertRaises(ValueError):
                choice_to_proposal(code, self.choices, self.packet["schema_manifest_sha256"])

    def test_wrong_manifest_rejected(self):
        with self.assertRaises(ValueError):
            choice_to_proposal("B", self.choices, "0" * 64)

    def test_modified_choice_unauthorized_field_rejected(self):
        altered = copy.deepcopy(self.choices)
        altered[1]["field"] = "private_diagnosis"
        with self.assertRaises(ValueError):
            choice_to_proposal("B", altered, self.packet["schema_manifest_sha256"])

    def test_missing_or_duplicate_choice_label_rejected(self):
        for altered in (self.choices[:-1], [*self.choices[:-1], self.choices[0]]):
            with self.subTest(length=len(altered)), self.assertRaises(ValueError):
                choice_to_proposal("V", altered, self.packet["schema_manifest_sha256"])

    def test_atomic_token_ids_have_distinct_labels(self):
        ids = token_ids(FakeTokenizer(), self.choices)
        self.assertEqual(ids, list(range(65, 65 + 23)))

    def test_tokenizer_multitoken_label_rejected(self):
        class MultiTokenizer(FakeTokenizer):
            def encode(self, string, *, add_special_tokens=False):
                return [1, 2] if string == "W" else [ord(string)]
        with self.assertRaisesRegex(ValueError, "exactly one model token"):
            token_ids(MultiTokenizer(), self.choices)

    def test_tokenizer_collision_rejected(self):
        class CollisionTokenizer(FakeTokenizer):
            def encode(self, string, *, add_special_tokens=False):
                return [65]
        with self.assertRaisesRegex(ValueError, "aliases"):
            token_ids(CollisionTokenizer(), self.choices)

    def test_option_order_modified_rejected_by_token_verification(self):
        altered = copy.deepcopy(self.choices)
        altered[1]["code"] = "X"
        with self.assertRaises(ValueError):
            token_ids(FakeTokenizer(), altered)

    def test_invalid_question_structure_rejected(self):
        with self.assertRaises(ValueError):
            task_messages({"id": "B-201", "question": "valid", "patient_id": "leak"}, self.choices)

    def test_model_choice_inprocess_receipt_has_truthful_endpoint_and_scorer_fields(self):
        # Scripted existing run is modified only to test the receipt validator.
        from test_semantic_governed_runner import make_full_run
        r = make_full_run(self.packet)
        r["endpoint_kind"] = "inprocess_masked_logits_no_network"
        r["endpoint_port"] = 0
        r["run_sha256"] = digest({k: v for k, v in r.items() if k != "run_sha256"})
        self.assertEqual(validate_run(r, self.packet)["attempted"], 72)

    def test_masked_inprocess_receipt_must_not_claim_loopback_port(self):
        from test_semantic_governed_runner import make_full_run
        r = make_full_run(self.packet)
        r["endpoint_kind"] = "inprocess_masked_logits_no_network"
        r["run_sha256"] = digest({k: v for k, v in r.items() if k != "run_sha256"})
        with self.assertRaises(ValueError):
            validate_run(r, self.packet)

    def test_loopback_receipt_cannot_use_inprocess_zero_port(self):
        from test_semantic_governed_runner import make_full_run
        r = make_full_run(self.packet)
        r["endpoint_port"] = 0
        r["run_sha256"] = digest({k: v for k, v in r.items() if k != "run_sha256"})
        with self.assertRaises(ValueError):
            validate_run(r, self.packet)


if __name__ == "__main__":
    unittest.main()
