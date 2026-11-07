"""Two independent fictional reports record different possible origins for one finding."""
import unittest

from oi_api.question_review_returns import attribution_comparison
from open_intelligence.patient_registry import PatientRegistryConflict


class AttributionPairTests(unittest.TestCase):
    def test_only_the_explicit_pair_of_comparable_originals_can_be_returned(self):
        def observation(letter, episode):
            return dict(source_id="SRC-" + letter*32, source_line=10,
                        document_id="DOC-" + letter, document_version=1, source_sha256=letter.lower()*64,
                        specimen_id="SPEC-A", event_date="2026-05-03", finding_key="nodule",
                        oncology={"role": "metastasis", "episode_id": episode})
        first, second = observation("A", "EP-A"), observation("B", "EP-B")
        anchor = dict(source_id=first["source_id"], source_line=10)
        peer = dict(source_id=second["source_id"], source_line=10)
        for episode in ("EP-B", None):
            compared = dict(second, oncology={"role": "metastasis", "episode_id": episode})
            self.assertEqual(attribution_comparison([first, compared], anchor, peer), compared)
        for changes in ({"specimen_id": None}, {"event_date":"2026-06-03"}, {"finding_key":"other"},
                        {"document_id":first["document_id"]}, {"oncology":None},
                        {"oncology":{"role":"primary","episode_id":"EP-B"}},
                        {"oncology":first["oncology"]}, {"source_line":11}):
            with self.subTest(changes=changes), self.assertRaises(PatientRegistryConflict):
                attribution_comparison([first, dict(second, **changes)], anchor, peer)
