"""Content identity for a synthetic laboratory report across authorized disclosures."""
from copy import deepcopy
import hashlib
import json
import unittest

from oi_api.laboratory_citation_report import inspection_digest


class LaboratoryInspectionDigestTests(unittest.TestCase):
    def setUp(self):
        self.report = {
            "contract": "oi.laboratory-source-citation-inspection/2",
            "question": "Why does the fictional report use α?",
            "reported_result": {"status": "reported_value", "value_text": "4.20"},
            "citations": {
                "patient_id": "FICT-PATIENT", "source_access_receipt_id": "ACCESS-A",
                "question_anchor": {"observation_reference": "Observation/Fictional"},
                "source_context_state": "current_unreviewed_question",
                "links": [{"citation": "FICT-A@1", "status": "available", "record": {"title": "One"}},
                          {"citation": "FICT-B@1", "status": "available", "record": {"title": "Two"}}],
            },
            "clinical_review": "not_performed", "claim_appraisal": "not_performed",
        }

    def test_digest_uses_exact_utf8_content_across_receipts_without_changing_input(self):
        original = deepcopy(self.report)
        material = deepcopy(self.report)
        del material["citations"]["source_access_receipt_id"]
        expected = hashlib.sha256(json.dumps(material, ensure_ascii=False, sort_keys=True,
                                             separators=(",", ":")).encode("utf-8")).hexdigest()
        self.assertEqual(inspection_digest(self.report), expected)
        self.assertEqual(self.report, original)
        next_read = {**self.report, "report_sha256": expected,
                     "citations": {**self.report["citations"], "source_access_receipt_id": "ACCESS-B"}}
        self.assertEqual(inspection_digest(next_read), expected)

    def test_source_identity_literal_precision_order_and_current_rights_change_the_digest(self):
        original = inspection_digest(self.report)
        def substitute(path, value):
            changed = deepcopy(self.report)
            target = changed
            for key in path[:-1]:
                target = target[key]
            target[path[-1]] = value
            return inspection_digest(changed)

        links = self.report["citations"]["links"]
        for path, value in [
            (("reported_result", "value_text"), "4.2"),
            (("reported_result",), {"status": "reported_absent", "absent_reason": "unknown"}),
            (("reported_result",), {"status": "reported_coded", "coded_result": {"code": "A"}}),
            (("citations", "question_anchor", "observation_reference"), "Observation/Sibling"),
            (("citations", "links"), list(reversed(links))),
            (("citations", "links"), [{**links[0], "record": None, "status": "rights_restricted"}, links[1]]),
            (("citations", "source_context_state"), "source_reassessment_required"),
        ]:
            with self.subTest(path=path, value=value):
                self.assertNotEqual(substitute(path, value), original)
