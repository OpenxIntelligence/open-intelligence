"""Pure bridge contract tests; not a PostgreSQL or clinical acceptance suite."""
import hashlib
from dataclasses import replace
import unittest

from oi_api.evidence_bridge import (
    CanonicalQuestionAnchor, EvidenceBridgeError, ProposedEvidence, bind_evidence,
)

SOURCE = hashlib.sha256(b"source").hexdigest()
QUOTE = "Fictional evidence quotation"
DIGEST = hashlib.sha256(QUOTE.encode()).hexdigest()


class EvidenceBridgeTests(unittest.TestCase):
    def setUp(self):
        self.anchor = CanonicalQuestionAnchor(
            "PAT-1", "CASE-1", "Q-1", "SRC-1", "SV-1", SOURCE, 7
        )
        self.proposal = ProposedEvidence(
            "Q-1", "PAT-1", "CASE-1", "SV-1", "E-1", "v1",
            "contradicts", QUOTE, DIGEST, frozenset({"metadata", "abstract"})
        )

    def bind(self, proposal=None, **kwargs):
        return bind_evidence(
            self.anchor, proposal or self.proposal,
            requested_content=kwargs.get("requested_content", "abstract"),
            current_source_sha256=kwargs.get("current_source_sha256", SOURCE),
        )

    def test_exact_quote_and_pending_state(self):
        packet = self.bind()
        self.assertEqual(packet.quotation, QUOTE)
        self.assertEqual(packet.relation, "contradicts")
        self.assertEqual(packet.review_state, "pending")

    def test_metadata_never_leaks_quote(self):
        self.assertIsNone(self.bind(requested_content="metadata").quotation)

    def test_full_text_requires_explicit_right(self):
        with self.assertRaises(EvidenceBridgeError):
            self.bind(requested_content="full_text")

    def test_cross_patient_case_question_and_version_fail(self):
        for field, value in [
            ("patient_id", "PAT-2"), ("case_id", "CASE-2"),
            ("question_id", "Q-2"), ("source_version_id", "SV-2"),
        ]:
            with self.subTest(field=field), self.assertRaises(EvidenceBridgeError):
                self.bind(replace(self.proposal, **{field: value}))

    def test_amendment_requires_reassessment(self):
        with self.assertRaises(EvidenceBridgeError):
            self.bind(current_source_sha256=hashlib.sha256(b"amended").hexdigest())

    def test_tampered_quote_and_unrecognized_rights_fail(self):
        for candidate in [
            replace(self.proposal, quotation="tampered"),
            replace(self.proposal, rights=frozenset({"full_text", "unknown_right"})),
            replace(self.proposal, review_state="approved"),
            replace(self.proposal, relation="clinically_proven"),
        ]:
            with self.subTest(candidate=candidate), self.assertRaises(EvidenceBridgeError):
                self.bind(candidate)

    def test_source_line_must_be_positive_integer(self):
        for line in (0, -1, True):
            with self.subTest(line=line), self.assertRaises(EvidenceBridgeError):
                bind_evidence(replace(self.anchor, source_line=line), self.proposal,
                              requested_content="abstract", current_source_sha256=SOURCE)


if __name__ == "__main__":
    unittest.main()
