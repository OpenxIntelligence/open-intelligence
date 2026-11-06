"""Case-local cancer episode labels in independently authored synthetic reports."""
import hashlib
import unittest

from oi_api.patients import SourceWorldModel
from oi_api.source_world_model import project_source_world_model
from oi_api.source_integrity import SourceIntegrityError, validate_snapshot
from open_intelligence.store import InvalidInput, parse_report
from test_source_integrity import SOURCE_ONE, original_row

HEADER = (
    "OI-SYNTHETIC-REPORT/2\nPatient: CASE-ALPHA\nDocument: DOC-ALPHA\n"
    "Type: pathology\nEvent-Date: 2026-05-03\nIssued-At: 2026-05-05\n"
    "Specimen: BIOPSY-ALPHA\n"
)
LINES = (
    "Oncology-Finding: breast|primary|EP-A|reported|Fictional breast primary.\n"
    "Oncology-Finding: colon|primary|EP-B|reported|Fictional colon primary.\n"
    "Oncology-Finding: nodule|metastasis|?|indeterminate|Fictional nodule; origin unclear.\n"
    "Finding: generic|pending|Awaiting a fictional report.\n"
)


class OncologyFindingTests(unittest.TestCase):
    def test_current_custody_returns_only_explicit_typed_anchors(self):
        raw = (HEADER + LINES).encode()
        row = original_row(raw=raw, sha256=hashlib.sha256(raw).hexdigest())
        findings = parse_report(raw, allow_oncology=True).findings
        assertions = [(SOURCE_ONE, f.key, f.state, f.quote, f.line) for f in findings]
        contexts = validate_snapshot([row], assertions, requested_case_id="CASE-ALPHA")
        self.assertEqual(contexts, {
            (SOURCE_ONE, 8): {"role": "primary", "episode_id": "EP-A"},
            (SOURCE_ONE, 9): {"role": "primary", "episode_id": "EP-B"},
            (SOURCE_ONE, 10): {"role": "metastasis", "episode_id": None},
        })
        self.assertEqual(findings[2].state, "indeterminate")
        with self.assertRaises(SourceIntegrityError):
            validate_snapshot([row], assertions[:-1], requested_case_id="CASE-ALPHA")

    def test_only_matching_attributed_findings_can_disagree(self):
        # Hold specimen, date, key and literal quotation constant. Only an
        # explicit, identical episode and role can connect these statements.
        def index_for(contexts):
            sources, assertions = [], []
            for letter, (context, state) in zip("ABCDEF", contexts):
                source_id = "SRC-" + letter * 32
                sources.append({
                    "source_id": source_id, "document_id": "DOC-" + letter, "version": 1,
                    "sha256": letter.lower() * 64, "kind": "pathology", "event_date": "2026-05-03",
                    "issued_at": "2026-05-05", "received_at": "2026-05-06T12:00:00Z",
                    "specimen_id": "SPEC-A", "state": "current", "supersedes_id": None,
                })
                assertion = {"source_id": source_id, "source_line": 8, "finding_key": "lesion",
                             "source_statement": "Fictional source statement.", "reported_state": state,
                             "clinical_review_state": "not_established"}
                if context is not None:
                    assertion["oncology"] = context
                assertions.append(assertion)
            return {"sources": sources, "source_reported_assertions": assertions,
                    "contract": "oi.synthetic-original-sources/1", "patient_id": "PAT-SYNTH",
                    "case_id": "CASE-ALPHA", "access_receipt_id": "ACCESS-" + "F" * 32,
                    "synthetic": True, "clinical_interpretation": False,
                    "research_review_invalidation_integrated": False}

        primary = {"role": "primary", "episode_id": "EP-A"}
        unknown = {"role": "metastasis", "episode_id": None}
        for other in [None, unknown, dict(primary, episode_id="EP-B"), dict(primary, role="metastasis")]:
            with self.subTest(other=other):
                world = project_source_world_model(index_for([(primary, "reported"), (other, "negative")]))
                payload = SourceWorldModel(**world).model_dump(mode="json")
                self.assertEqual(payload["conflicts"], [])
                self.assertEqual(payload["observations"][0]["oncology"], primary)
                if other is None:
                    self.assertNotIn("oncology", payload["observations"][1])
        world = project_source_world_model(index_for([(unknown, "reported"), (unknown, "negative")]))
        self.assertEqual(world["conflicts"], [])
        world = project_source_world_model(index_for([(primary, "reported"), (primary, "negative")]))
        self.assertEqual(len(world["conflicts"]), 1)
        self.assertEqual(world["conflicts"][0]["clinical_interpretation"], "not_performed")

    def test_non_lf_separator_cannot_create_a_second_attribution_on_one_source_line(self):
        for separator in ("\v", "\f", "\x1c", "\x1d", "\x1e", "\x85", "\u2028", "\u2029"):
            raw = (HEADER + LINES.replace("primary.\nOncology-Finding:", "primary." + separator + "Oncology-Finding:", 1)).encode()
            with self.subTest(separator=repr(separator)), self.assertRaises(InvalidInput):
                parse_report(raw, allow_oncology=True)

    def test_invalid_attribution_is_rejected_without_guessing(self):
        for bad in (LINES.replace("EP-A", ""), LINES.replace("EP-B", "EP-A/EP-B"),
                    LINES.replace("EP-A", "UNKNOWN"),
                    LINES.replace("|primary|", "|confirmed|"), LINES.replace("colon|", "breast|"),
                    LINES.replace("|reported|", "|diagnosed|")):
            with self.subTest(bad=bad), self.assertRaises(InvalidInput):
                parse_report((HEADER + bad).encode(), allow_oncology=True)
        with self.assertRaises(InvalidInput):
            parse_report((HEADER + LINES).encode())
        with self.assertRaises(InvalidInput):
            parse_report((HEADER.replace("/2", "/1", 1) + LINES).encode(), allow_oncology=True)
