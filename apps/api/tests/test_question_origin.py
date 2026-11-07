"""Unittest regression checks for canonical question-origin validation."""
import unittest

from oi_api.question_origin import classify_question_origin, classify_stored_question_origin

Q = "QUESTION-" + "A" * 32
S = "SRC-" + "B" * 32


class QuestionOriginTests(unittest.TestCase):
    def test_source_line_origin(self):
        value = classify_question_origin(question_id=Q, source_id=S,
                                         source_line=3, observation_reference=None)
        self.assertEqual(value.kind, "source_line")
        self.assertEqual(value.line, 3)
        self.assertIsNone(value.observation_reference)

    def test_fhir_observation_origin(self):
        ref = "Observation/FICTIONAL-OBS-A"
        value = classify_question_origin(question_id=Q, source_id=S,
                                         source_line=None, observation_reference=ref)
        self.assertEqual(value.kind, "fhir_observation")
        self.assertEqual(value.observation_reference, ref)
        self.assertIsNone(value.line)

    def test_invalid_or_ambiguous_origin_rejected(self):
        cases = [
            (None, None), (1, "Observation/valid"), (0, None), (10001, None),
            (True, None), (-1, None), (None, "Patient/not-an-observation"),
            (None, "Observation/bad slash"), (None, "Observation/"),
        ]
        for line, reference in cases:
            with self.subTest(line=line, reference=reference):
                with self.assertRaises(ValueError):
                    classify_question_origin(question_id=Q, source_id=S,
                                             source_line=line, observation_reference=reference)

    def test_invalid_identifiers_rejected(self):
        with self.assertRaises(ValueError):
            classify_question_origin(question_id="QUESTION-bad", source_id=S,
                                     source_line=1, observation_reference=None)
        with self.assertRaises(ValueError):
            classify_question_origin(question_id=Q, source_id="SRC-bad",
                                     source_line=None, observation_reference="Observation/x")

    def test_stored_text_question_has_no_laboratory_child(self):
        value = classify_stored_question_origin(
            question_id=Q, source_id=S, source_line=1,
            observation_reference=None, anchor_source_id=None)
        self.assertEqual(value.kind, "source_line")

    def test_stored_laboratory_question_requires_matching_child_source(self):
        value = classify_stored_question_origin(
            question_id=Q, source_id=S, source_line=None,
            observation_reference="Observation/FICTIONAL-A", anchor_source_id=S)
        self.assertEqual(value.kind, "fhir_observation")
        for wrong in (None, "SRC-" + "C" * 32):
            with self.subTest(wrong=wrong):
                with self.assertRaises(ValueError):
                    classify_stored_question_origin(
                        question_id=Q, source_id=S, source_line=None,
                        observation_reference="Observation/FICTIONAL-A",
                        anchor_source_id=wrong)

    def test_stored_text_question_rejects_unexpected_laboratory_child(self):
        with self.assertRaises(ValueError):
            classify_stored_question_origin(
                question_id=Q, source_id=S, source_line=1,
                observation_reference=None, anchor_source_id=S)

    def test_source_line_upper_bound_matches_assertion_schema(self):
        value = classify_question_origin(question_id=Q, source_id=S,
                                         source_line=10000, observation_reference=None)
        self.assertEqual(value.line, 10000)


if __name__ == "__main__":
    unittest.main()
