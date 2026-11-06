"""Analysis dimension (slice D3): A2 Longitudinal + A3 Molecular + T1
imaging comparison + T2 lab/marker series + T4 line of therapy.

D3 acceptance: all five toolsets implemented and tested; no model
calls inside any toolset; suite green with zero new failures.

Fixtures are independently authored synthetic reports imported through
the one import path, plus synthetic ledger evidence assessed through
the human-authored assessment path. No live model call is made here:
every toolset is deterministic code over the ledger.
"""

import ast
import tempfile
import unittest
from pathlib import Path

from open_intelligence import CaseStore, InvalidInput
from open_intelligence.imaging import compare_imaging
from open_intelligence.lab_series import lab_series
from open_intelligence.longitudinal import longitudinal_picture
from open_intelligence.molecular import gene_for_key, molecular_evidence
from open_intelligence.specimen_chain import validate_specimen_chain
from open_intelligence.terminology import codings_for
from open_intelligence.therapy import (
    compute_therapy_lines,
    mark_therapy_lines_stale,
    record_therapy_lines,
    therapy_lines,
)
from open_intelligence.vertical import get_vertical

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src" / "open_intelligence"

D3_MODULES = (
    "longitudinal",
    "lab_series",
    "imaging",
    "molecular",
    "therapy",
)


def report(patient, document, kind, event_date, findings, *, specimen=None,
           issued=None, amends=None):
    """Build one synthetic report in the OI-SYNTHETIC-REPORT/1 format."""
    lines = ["OI-SYNTHETIC-REPORT/1", f"Patient: {patient}",
             f"Document: {document}", f"Type: {kind}",
             f"Event-Date: {event_date}", f"Issued-At: {issued or event_date}"]
    if specimen:
        lines.append(f"Specimen: {specimen}")
    if amends:
        lines.append(f"Amends: {amends}")
    for key, state, quote in findings:
        lines.append(f"Finding: {key}|{state}|{quote}")
    return ("\n".join(lines) + "\n").encode("utf-8")


def evidence(key, title, statement, *, issued="2026-05-09", amends=None):
    """Build one synthetic evidence record in the OI-SYNTHETIC-EVIDENCE/1 format."""
    lines = ["OI-SYNTHETIC-EVIDENCE/1", f"Evidence: {key}",
             f"Title: {title}", f"Issued-At: {issued}",
             "Rights: original-synthetic", f"Statement: {statement}"]
    if amends:
        lines.append(f"Amends: {amends}")
    return ("\n".join(lines) + "\n").encode("utf-8")


class AnalysisTestBase(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.TemporaryDirectory()
        self.store = CaseStore(Path(self.dir.name) / "t.db")
        self.store.add_case("CASE-ALPHA", "Fictional Alpha")

    def tearDown(self):
        self.dir.cleanup()

    def import_report(self, case_id, raw):
        return self.store.import_report(case_id, raw)["source_id"]

    def import_evidence(self, raw):
        return self.store.import_synthetic_evidence(raw)["evidence_version_id"]

    def assess(self, case_id, evidence_version_id, relation="supports",
               applicability="applicable"):
        question = self.store.add_question(
            case_id, "What does this fictional evidence support?")
        return self.store.assess_synthetic_evidence(
            case_id, question, evidence_version_id, relation, applicability,
            "Fictional assessment rationale for the test case only.")


class LongitudinalTests(AnalysisTestBase):
    def test_tracks_are_ordered_and_changes_recorded(self):
        self.import_report("CASE-ALPHA", report(
            "CASE-ALPHA", "PATH-A", "pathology", "2026-05-03",
            [("marker-a", "not-reported", "Marker A was not tested.")],
            specimen="SPEC-A"))
        self.import_report("CASE-ALPHA", report(
            "CASE-ALPHA", "PATH-B", "pathology", "2026-05-10",
            [("marker-a", "reported", "Marker A was detected in the sample.")],
            specimen="SPEC-B"))
        picture = longitudinal_picture(self.store, "CASE-ALPHA")
        track = picture.tracks["marker-a"]
        self.assertEqual([p["occurred"] for p in track],
                         ["2026-05-03", "2026-05-10"])
        self.assertEqual([p["certainty"] for p in track],
                         ["not-reported", "reported"])
        self.assertEqual(len(picture.changes), 1)
        change = picture.changes[0]
        self.assertEqual(change["finding_key"], "marker-a")
        self.assertEqual(change["from_certainty"], "not-reported")
        self.assertEqual(change["to_certainty"], "reported")
        self.assertEqual(picture.same_date_conflicts, [])
        self.assertEqual(picture.gaps, [{
            "start_date": "2026-05-04", "end_date": "2026-05-09",
            "coverage": "unknown", "before_occurred": "2026-05-03",
            "after_occurred": "2026-05-10"}])

    def test_same_date_conflict_is_reported_unknown(self):
        self.import_report("CASE-ALPHA", report(
            "CASE-ALPHA", "PATH-A", "pathology", "2026-05-03",
            [("marker-a", "reported", "Marker A was detected.")],
            specimen="SPEC-A"))
        self.import_report("CASE-ALPHA", report(
            "CASE-ALPHA", "PATH-B", "pathology", "2026-05-03",
            [("marker-a", "not-reported", "Marker A was not tested.")],
            specimen="SPEC-B"))
        picture = longitudinal_picture(self.store, "CASE-ALPHA")
        self.assertEqual(len(picture.same_date_conflicts), 1)
        conflict = picture.same_date_conflicts[0]
        self.assertEqual(conflict["finding_key"], "marker-a")
        self.assertEqual(conflict["occurred"], "2026-05-03")
        self.assertEqual(conflict["certainties"], ["not-reported", "reported"])
        self.assertEqual(conflict["status"], "unknown")
        # A same-date conflict is not a change: no winner is picked.
        self.assertEqual(picture.changes, [])

    def test_superseded_versions_do_not_appear_in_tracks(self):
        original = (Path(__file__).resolve().parents[1] / "examples"
                    / "synthetic" / "alpha-pathology-original.txt").read_bytes()
        amended = (Path(__file__).resolve().parents[1] / "examples"
                   / "synthetic" / "alpha-pathology-amended.txt").read_bytes()
        self.import_report("CASE-ALPHA", original)
        self.import_report("CASE-ALPHA", amended)
        picture = longitudinal_picture(self.store, "CASE-ALPHA")
        self.assertEqual(
            [p["certainty"] for p in picture.tracks["marker-a"]],
            ["negative"])
        self.assertEqual(len(picture.tracks["marker-a"]), 1)

    def test_unknown_case_raises(self):
        with self.assertRaises(InvalidInput):
            longitudinal_picture(self.store, "CASE-NOPE")


class LabSeriesTests(AnalysisTestBase):
    def _lab(self, document, event_date, quote, *, specimen="SPEC-LAB"):
        return self.import_report("CASE-ALPHA", report(
            "CASE-ALPHA", document, "laboratory", event_date,
            [("hemoglobin", "reported", quote)], specimen=specimen))

    def test_series_points_deltas_and_loinc_binding(self):
        self._lab("LAB-A", "2026-05-03", "Hemoglobin was measured as 11.2 g/dL.")
        self._lab("LAB-B", "2026-05-10", "Hemoglobin was measured as 12.0 g/dL.")
        result = lab_series(self.store, "CASE-ALPHA",
                            codings_for=codings_for)
        series = result.series["hemoglobin"]
        self.assertEqual(
            [(p["occurred"], p["value"], p["unit"]) for p in series["points"]],
            [("2026-05-03", 11.2, "g/dL"), ("2026-05-10", 12.0, "g/dL")])
        self.assertEqual(len(series["deltas"]), 1)
        delta = series["deltas"][0]
        self.assertEqual(delta["delta_status"], "computed")
        self.assertAlmostEqual(delta["absolute"], 0.8)
        self.assertAlmostEqual(delta["percent"], 0.8 / 11.2 * 100.0)
        self.assertEqual(series["codings"], [{
            "system": "http://loinc.org", "code": "718-7",
            "display": "Hemoglobin [Mass/volume] in Blood"}])
        self.assertEqual(result.unbound, [])

    def test_unbound_analyte_is_listed_not_fabricated(self):
        self.import_report("CASE-ALPHA", report(
            "CASE-ALPHA", "LAB-A", "laboratory", "2026-05-03",
            [("marker-x", "reported", "Marker X was measured as 4.5 units.")],
            specimen="SPEC-LAB"))
        result = lab_series(self.store, "CASE-ALPHA",
                            codings_for=codings_for)
        self.assertEqual(result.series["marker-x"]["codings"], [])
        self.assertEqual(result.unbound, ["marker-x"])

    def test_unparseable_and_ambiguous_points_are_typed(self):
        self.import_report("CASE-ALPHA", report(
            "CASE-ALPHA", "LAB-A", "laboratory", "2026-05-03",
            [("hemoglobin", "reported", "Hemoglobin was not quantified.")],
            specimen="SPEC-LAB"))
        self.import_report("CASE-ALPHA", report(
            "CASE-ALPHA", "LAB-B", "laboratory", "2026-05-10",
            [("hemoglobin", "reported",
              "Hemoglobin 11.2 g/dL on repeat of 10.9 g/dL.")],
            specimen="SPEC-LAB"))
        result = lab_series(self.store, "CASE-ALPHA")
        points = result.series["hemoglobin"]["points"]
        self.assertEqual([p["parse_status"] for p in points],
                         ["unparseable", "ambiguous"])
        # No delta is ever computed from an unparsed point.
        self.assertEqual(result.series["hemoglobin"]["deltas"], [])

    def test_unit_mismatch_and_percent_undefined(self):
        self._lab("LAB-A", "2026-05-03", "Hemoglobin was measured as 11.2 g/dL.")
        self._lab("LAB-B", "2026-05-10", "Hemoglobin was measured as 112 g/L.")
        self._lab("LAB-C", "2026-05-17", "Hemoglobin was measured as 0.0 g/L.")
        self._lab("LAB-D", "2026-05-24", "Hemoglobin was measured as 1.0 g/L.")
        result = lab_series(self.store, "CASE-ALPHA")
        deltas = result.series["hemoglobin"]["deltas"]
        self.assertEqual([d["delta_status"] for d in deltas],
                         ["unit_mismatch", "computed", "percent_undefined"])
        self.assertIsNone(deltas[0]["absolute"])
        self.assertAlmostEqual(deltas[1]["absolute"], -112.0)
        self.assertIsNone(deltas[2]["percent"])
        self.assertAlmostEqual(deltas[2]["absolute"], 1.0)

    def test_missing_unit_is_recorded_not_guessed(self):
        self._lab("LAB-A", "2026-05-03", "Hemoglobin was measured as 11.2.")
        self._lab("LAB-B", "2026-05-10", "Hemoglobin was measured as 12.0.")
        result = lab_series(self.store, "CASE-ALPHA")
        points = result.series["hemoglobin"]["points"]
        self.assertEqual([p["unit"] for p in points],
                         ["unit_not_stated", "unit_not_stated"])
        self.assertEqual(result.series["hemoglobin"]["deltas"][0]["delta_status"],
                         "computed")

    def test_non_laboratory_findings_are_not_series(self):
        self.import_report("CASE-ALPHA", report(
            "CASE-ALPHA", "PATH-A", "pathology", "2026-05-03",
            [("hemoglobin", "reported", "Hemoglobin was measured as 11.2 g/dL.")],
            specimen="SPEC-A"))
        result = lab_series(self.store, "CASE-ALPHA")
        self.assertEqual(result.series, {})

    def test_cross_specimen_transition_chain_status(self):
        first = self._lab("LAB-A", "2026-05-03",
                          "Hemoglobin was measured as 11.2 g/dL.",
                          specimen="SPEC-A")
        second = self._lab("LAB-B", "2026-05-10",
                           "Hemoglobin was measured as 12.0 g/dL.",
                           specimen="SPEC-B")
        # No validator supplied: the transition is recorded, not assumed.
        result = lab_series(self.store, "CASE-ALPHA")
        self.assertEqual(len(result.chain_transitions), 1)
        self.assertEqual(result.chain_transitions[0]["checked"], False)
        self.assertEqual(result.chain_transitions[0]["reason"],
                         "no_chain_validator")
        # A validator that reports a break: the break is a typed record.
        # An asset must anchor a source before there is anything to check.
        block = self.store.add_biological_asset(
            "CASE-ALPHA", "BLOCK-LAB", "ffpe_block", "EPISODE-A", "2026-05-03",
            first, specimen_state="recorded", specimen_id="SPEC-A")

        def broken_chain(store, case_id, asset_pk):
            return validate_specimen_chain(store, case_id, 999999)
        result = lab_series(self.store, "CASE-ALPHA",
                            validate_chain=broken_chain)
        self.assertEqual(result.chain_transitions[0]["checked"], True)
        self.assertEqual(
            {b["type"] for b in result.chain_transitions[0]["breaks"]},
            {"missing_asset"})
        # An intact real chain over assets anchored to both sources.
        self.store.add_biological_asset(
            "CASE-ALPHA", "SLIDE-LAB", "slide", "EPISODE-A", "2026-05-04",
            second, parent_asset_id=block, specimen_state="recorded",
            specimen_id="SPEC-A")
        result = lab_series(self.store, "CASE-ALPHA",
                            validate_chain=validate_specimen_chain)
        self.assertEqual(result.chain_transitions[0]["checked"], True)
        self.assertEqual(result.chain_transitions[0]["breaks"], [])

    def test_unknown_case_raises(self):
        with self.assertRaises(InvalidInput):
            lab_series(self.store, "CASE-NOPE")


class ImagingComparisonTests(AnalysisTestBase):
    def _imaging(self, document, event_date, findings, *, specimen=None):
        return self.import_report("CASE-ALPHA", report(
            "CASE-ALPHA", document, "imaging", event_date, findings,
            specimen=specimen))

    def _dicom(self, study_uid, modality, source_id=None):
        return self.store.record_dicom_report("CASE-ALPHA", {
            "study_uid": study_uid, "modality": modality,
            "accession": "ACC-" + study_uid[-3:],
            "report_text": "Fictional imaging report narrative.",
            "source_version_id": source_id})

    def test_consecutive_pair_diff(self):
        first = self._imaging("IMG-A", "2026-05-17", [
            ("lesion-size", "reported",
             "A fictional reference lesion was measured as 31 mm."),
            ("comparison", "pending",
             "Prior images are unavailable for comparison."),
            ("old-finding", "reported", "An old fictional finding."),
        ])
        second = self._imaging("IMG-B", "2026-06-17", [
            ("lesion-size", "reported",
             "A fictional reference lesion was measured as 31 mm."),
            ("comparison", "reported",
             "Comparison with the prior fictional scan was performed."),
            ("new-finding", "reported", "A new fictional finding."),
        ])
        self._dicom("OI-SYNTHETIC-STUDY-MR1", "MR", first)
        self._dicom("OI-SYNTHETIC-STUDY-MR2", "MR", second)
        result = compare_imaging(self.store, "CASE-ALPHA")
        self.assertEqual(len(result.comparisons), 1)
        comparison = result.comparisons[0]
        self.assertEqual(comparison["modality"], "MR")
        self.assertEqual(comparison["persisting"], ["lesion-size"])
        self.assertEqual(comparison["changed_state"], [{
            "finding_key": "comparison",
            "from_certainty": "pending", "to_certainty": "reported"}])
        self.assertEqual(comparison["added"], ["new-finding"])
        self.assertEqual(comparison["removed"], ["old-finding"])
        self.assertEqual(comparison["chain"]["checked"], False)
        self.assertEqual(comparison["chain"]["reason"], "no_chain_validator")
        self.assertEqual(result.unpaired, [])
        self.assertEqual(result.unanchored, [])

    def test_unpaired_and_unanchored_are_listed(self):
        only = self._imaging("IMG-A", "2026-05-17", [
            ("lesion-size", "reported",
             "A fictional reference lesion was measured as 31 mm."),
        ])
        self._dicom("OI-SYNTHETIC-STUDY-CT1", "CT", only)
        self._imaging("IMG-B", "2026-06-17", [
            ("lesion-size", "reported",
             "A fictional reference lesion was measured as 31 mm."),
        ])
        self._dicom("OI-SYNTHETIC-STUDY-MR9", "MR", None)
        result = compare_imaging(self.store, "CASE-ALPHA")
        self.assertEqual(result.comparisons, [])
        reasons = {(item["document_id"], item["reason"])
                   for item in result.unpaired}
        self.assertEqual(reasons, {("IMG-A", "no_other_study_of_modality"),
                                   ("IMG-B", "modality_unknown")})
        self.assertEqual(
            [(item["study_uid"], item["reason"]) for item in result.unanchored],
            [("OI-SYNTHETIC-STUDY-MR9", "unanchored")])

    def test_chain_break_is_recorded_on_the_pair(self):
        first = self._imaging("IMG-A", "2026-05-17", [
            ("lesion-size", "reported",
             "A fictional reference lesion was measured as 31 mm."),
        ], specimen="SPEC-A")
        second = self._imaging("IMG-B", "2026-06-17", [
            ("lesion-size", "reported",
             "A fictional reference lesion was measured as 31 mm."),
        ], specimen="SPEC-B")
        self._dicom("OI-SYNTHETIC-STUDY-MR1", "MR", first)
        self._dicom("OI-SYNTHETIC-STUDY-MR2", "MR", second)
        block = self.store.add_biological_asset(
            "CASE-ALPHA", "BLOCK-IMG", "ffpe_block", "EPISODE-A", "2026-05-17",
            first, specimen_state="recorded", specimen_id="SPEC-A")
        self.store.add_biological_asset(
            "CASE-ALPHA", "SLIDE-IMG", "slide", "EPISODE-A", "2026-05-18",
            second, parent_asset_id=block, specimen_state="recorded",
            specimen_id="SPEC-DIFFERENT")
        result = compare_imaging(self.store, "CASE-ALPHA",
                                 validate_chain=validate_specimen_chain)
        self.assertEqual(len(result.comparisons), 1)
        chain = result.comparisons[0]["chain"]
        self.assertEqual(chain["checked"], True)
        self.assertEqual({b["type"] for b in chain["breaks"]},
                         {"specimen_mismatch"})

    def test_unknown_case_raises(self):
        with self.assertRaises(InvalidInput):
            compare_imaging(self.store, "CASE-NOPE")


class MolecularEvidenceTests(AnalysisTestBase):
    def _molecular(self, document, event_date, findings, *, specimen="SPEC-MOL"):
        return self.import_report("CASE-ALPHA", report(
            "CASE-ALPHA", document, "molecular", event_date, findings,
            specimen=specimen))

    def _link_case(self):
        self._molecular("MOL-A", "2026-05-03", [
            ("variant-egfr-l858r", "reported",
             "Fictional variant EGFR L858R was detected."),
            ("kras", "reported", "Fictional variant KRAS was detected."),
        ])
        civic = self.import_evidence(evidence(
            "CIVIC-EGFR-001", "Fictional CIViC record for EGFR",
            "This fictional record discusses EGFR variant evidence."))
        clinvar = self.import_evidence(evidence(
            "CLINVAR-KRAS-001", "Fictional ClinVar record for KRAS",
            "This fictional record discusses KRAS variant evidence."))
        self.assess("CASE-ALPHA", civic, "supports", "applicable")
        self.assess("CASE-ALPHA", clinvar, "contradicts", "limited")
        return civic, clinvar

    def test_variant_identities_link_to_pinned_evidence(self):
        self.assertEqual(gene_for_key("variant-egfr-l858r"), "egfr")
        self.assertEqual(gene_for_key("kras"), "kras")
        self._link_case()
        result = molecular_evidence(self.store, "CASE-ALPHA")
        by_gene = {variant["gene"]: variant for variant in result.variants}
        self.assertEqual(sorted(by_gene), ["egfr", "kras"])
        self.assertEqual(
            [(link["evidence_key"], link["relation"], link["applicability"])
             for link in by_gene["egfr"]["links"]],
            [("CIVIC-EGFR-001", "supports", "applicable")])
        self.assertEqual(
            [(link["evidence_key"], link["relation"], link["applicability"])
             for link in by_gene["kras"]["links"]],
            [("CLINVAR-KRAS-001", "contradicts", "limited")])
        self.assertEqual(result.unassessed, [])
        self.assertEqual(result.unrecognized_prefix, [])

    def test_gene_matching_is_token_exact(self):
        self._molecular("MOL-A", "2026-05-03", [
            ("egfr", "reported", "Fictional variant EGFR was detected."),
        ])
        near = self.import_evidence(evidence(
            "CIVIC-EGFR2-001", "Fictional CIViC record for EGFR2",
            "This fictional record discusses EGFR2 variant evidence."))
        self.assess("CASE-ALPHA", near, "supports", "applicable")
        result = molecular_evidence(self.store, "CASE-ALPHA")
        self.assertEqual(result.variants[0]["links"], [])
        self.assertEqual(result.unassessed, [])
        self.assertEqual(result.unrecognized_prefix, [])

    def test_unassessed_and_unrecognized_prefix_are_listed_not_linked(self):
        self._molecular("MOL-A", "2026-05-03", [
            ("egfr", "reported", "Fictional variant EGFR was detected."),
        ])
        self.import_evidence(evidence(
            "CIVIC-EGFR-002", "Fictional CIViC record for EGFR",
            "This fictional record discusses EGFR variant evidence."))
        other = self.import_evidence(evidence(
            "EVID-EGFR-003", "Fictional other-source record for EGFR",
            "This fictional record discusses EGFR variant evidence."))
        self.assess("CASE-ALPHA", other, "supports", "applicable")
        result = molecular_evidence(self.store, "CASE-ALPHA")
        self.assertEqual(result.variants[0]["links"], [])
        self.assertEqual(
            [entry["evidence_key"] for entry in result.unassessed],
            ["CIVIC-EGFR-002"])
        self.assertEqual(
            [entry["evidence_key"] for entry in result.unrecognized_prefix],
            ["EVID-EGFR-003"])

    def test_superseded_evidence_does_not_link(self):
        self._molecular("MOL-A", "2026-05-03", [
            ("egfr", "reported", "Fictional variant EGFR was detected."),
        ])
        first = self.import_evidence(evidence(
            "CIVIC-EGFR-004", "Fictional CIViC record for EGFR",
            "This fictional record discusses EGFR variant evidence."))
        self.assess("CASE-ALPHA", first, "supports", "applicable")
        self.import_evidence(evidence(
            "CIVIC-EGFR-004", "Fictional CIViC record for EGFR, revised",
            "This fictional record discusses EGFR variant evidence.",
            amends="CIVIC-EGFR-004@1"))
        result = molecular_evidence(self.store, "CASE-ALPHA")
        self.assertEqual(result.variants[0]["links"], [])
        self.assertEqual(
            [entry["evidence_key"] for entry in result.unassessed],
            ["CIVIC-EGFR-004"])

    def test_genomic_delta_table_records_certainty_changes(self):
        self._molecular("MOL-A", "2026-05-03", [
            ("egfr", "reported", "Fictional variant EGFR was detected."),
        ])
        self._molecular("MOL-B", "2026-05-10", [
            ("egfr", "not-reported", "Fictional variant EGFR was not tested."),
        ])
        result = molecular_evidence(self.store, "CASE-ALPHA")
        self.assertEqual(len(result.variant_deltas), 1)
        delta = result.variant_deltas[0]
        self.assertEqual(delta["gene"], "egfr")
        self.assertEqual(
            [p["certainty"] for p in delta["points"]],
            ["reported", "not-reported"])
        self.assertEqual(len(delta["changes"]), 1)
        self.assertEqual(delta["changes"][0]["from_certainty"], "reported")
        self.assertEqual(delta["changes"][0]["to_certainty"], "not-reported")

    def test_non_molecular_findings_are_not_variants(self):
        self.import_report("CASE-ALPHA", report(
            "CASE-ALPHA", "PATH-A", "pathology", "2026-05-03",
            [("egfr", "reported", "Fictional variant EGFR was detected.")],
            specimen="SPEC-A"))
        result = molecular_evidence(self.store, "CASE-ALPHA")
        self.assertEqual(result.variants, [])

    def test_unknown_case_raises(self):
        with self.assertRaises(InvalidInput):
            molecular_evidence(self.store, "CASE-NOPE")


class TherapyLinesTests(AnalysisTestBase):
    REGIMENS = ("regimen-a", "regimen-b")

    def _therapy(self, document, event_date, findings):
        return self.import_report("CASE-ALPHA", report(
            "CASE-ALPHA", document, "clinical", event_date, findings))

    def _three_occurrences(self):
        self._therapy("CLIN-A", "2026-05-03", [
            ("regimen-a", "reported", "Fictional regimen A was given.")])
        self._therapy("CLIN-B", "2026-05-10", [
            ("regimen-b", "reported", "Fictional regimen B was given.")])
        self._therapy("CLIN-C", "2026-05-17", [
            ("regimen-a", "reported", "Fictional regimen A was given again.")])

    def test_ruleset_v1_reappearance_starts_a_new_line(self):
        self._three_occurrences()
        result = compute_therapy_lines(
            self.store, "CASE-ALPHA", self.REGIMENS,
            ruleset_version="lot-rules-1")
        self.assertEqual(result.ruleset_version, "lot-rules-1")
        self.assertEqual(
            [(line["line_number"], line["regimen_key"],
              line["first_occurred"], line["last_occurred"])
             for line in result.lines],
            [(1, "regimen-a", "2026-05-03", "2026-05-03"),
             (2, "regimen-b", "2026-05-10", "2026-05-10"),
             (3, "regimen-a", "2026-05-17", "2026-05-17")])
        self.assertEqual(result.not_counted, [])

    def test_ruleset_v2_reappearance_resumes_the_earlier_line(self):
        self._three_occurrences()
        result = compute_therapy_lines(
            self.store, "CASE-ALPHA", self.REGIMENS,
            ruleset_version="lot-rules-2")
        self.assertEqual(
            [(line["line_number"], line["regimen_key"],
              line["first_occurred"], line["last_occurred"])
             for line in result.lines],
            [(1, "regimen-a", "2026-05-03", "2026-05-17"),
             (2, "regimen-b", "2026-05-10", "2026-05-10")])

    def test_default_ruleset_comes_from_the_vertical(self):
        self._therapy("CLIN-A", "2026-05-03", [
            ("regimen-a", "reported", "Fictional regimen A was given.")])
        result = compute_therapy_lines(self.store, "CASE-ALPHA", self.REGIMENS)
        self.assertEqual(result.ruleset_version, "lot-rules-1")
        self.assertEqual(len(result.lines), 1)

    def test_non_reported_regimen_is_not_counted(self):
        self._therapy("CLIN-A", "2026-05-03", [
            ("regimen-a", "reported", "Fictional regimen A was given."),
            ("regimen-b", "pending", "Fictional regimen B is awaiting review.")])
        result = compute_therapy_lines(
            self.store, "CASE-ALPHA", self.REGIMENS,
            ruleset_version="lot-rules-1")
        self.assertEqual(len(result.lines), 1)
        self.assertEqual(len(result.not_counted), 1)
        self.assertEqual(result.not_counted[0]["finding_key"], "regimen-b")
        self.assertEqual(result.not_counted[0]["reason"],
                         "not_reported_certainty")

    def test_record_marks_previous_batch_stale_on_ruleset_change(self):
        self._three_occurrences()
        first = record_therapy_lines(
            self.store, "CASE-ALPHA", self.REGIMENS,
            ruleset_version="lot-rules-1")
        self.assertEqual(len(first.recorded_ids), 3)
        self.assertEqual(
            [(row["line_number"], row["state"])
             for row in therapy_lines(self.store, "CASE-ALPHA")],
            [(1, "current"), (2, "current"), (3, "current")])
        second = record_therapy_lines(
            self.store, "CASE-ALPHA", self.REGIMENS,
            ruleset_version="lot-rules-2")
        self.assertEqual(len(second.recorded_ids), 2)
        all_rows = therapy_lines(self.store, "CASE-ALPHA", include_stale=True)
        stale = [row for row in all_rows if row["state"] == "stale"]
        current = [row for row in all_rows if row["state"] == "current"]
        self.assertEqual(len(stale), 3)
        self.assertTrue(all(row["stale_reason"] == "ruleset_changed"
                            for row in stale))
        self.assertTrue(all(row["ruleset_version"] == "lot-rules-1"
                            for row in stale))
        self.assertEqual(len(current), 2)
        self.assertTrue(all(row["ruleset_version"] == "lot-rules-2"
                            for row in current))
        # Recomputing under the same version stales with reason recomputed.
        record_therapy_lines(
            self.store, "CASE-ALPHA", self.REGIMENS,
            ruleset_version="lot-rules-2")
        all_rows = therapy_lines(self.store, "CASE-ALPHA", include_stale=True)
        recomputed = [row for row in all_rows
                      if row["stale_reason"] == "recomputed"]
        self.assertEqual(len(recomputed), 2)

    def test_mark_stale_without_recomputing(self):
        self._three_occurrences()
        record_therapy_lines(
            self.store, "CASE-ALPHA", self.REGIMENS,
            ruleset_version="lot-rules-1")
        marked = mark_therapy_lines_stale(
            self.store, "CASE-ALPHA", "lot-rules-2")
        self.assertEqual(marked, 3)
        self.assertEqual(therapy_lines(self.store, "CASE-ALPHA"), [])
        self.assertEqual(len(therapy_lines(
            self.store, "CASE-ALPHA", include_stale=True)), 3)
        # Marking again under the same version marks nothing.
        self.assertEqual(mark_therapy_lines_stale(
            self.store, "CASE-ALPHA", "lot-rules-2"), 0)

    def test_unknown_ruleset_fails_closed(self):
        self._therapy("CLIN-A", "2026-05-03", [
            ("regimen-a", "reported", "Fictional regimen A was given.")])
        with self.assertRaises(InvalidInput):
            compute_therapy_lines(
                self.store, "CASE-ALPHA", self.REGIMENS,
                vertical=get_vertical("cardiology"))
        with self.assertRaises(InvalidInput):
            compute_therapy_lines(
                self.store, "CASE-ALPHA", self.REGIMENS,
                ruleset_version="lot-rules-99")

    def test_invalid_inputs_fail_closed(self):
        with self.assertRaises(InvalidInput):
            compute_therapy_lines(self.store, "CASE-ALPHA", ())
        with self.assertRaises(InvalidInput):
            compute_therapy_lines(
                self.store, "CASE-ALPHA", ("Bad Key!",))
        with self.assertRaises(InvalidInput):
            compute_therapy_lines(self.store, "CASE-NOPE", self.REGIMENS)
        with self.assertRaises(InvalidInput):
            mark_therapy_lines_stale(self.store, "CASE-NOPE", "lot-rules-2")


class NoModelCallsTests(unittest.TestCase):
    def test_toolsets_do_not_touch_the_model_call_path(self):
        forbidden = {
            "open_intelligence.investigation",
            "open_intelligence.skeptic",
            "open_intelligence.__main__",
        }
        for name in D3_MODULES:
            path = SRC / f"{name}.py"
            tree = ast.parse(path.read_text())
            imported = set()
            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    imported.update(alias.name for alias in node.names)
                elif isinstance(node, ast.ImportFrom):
                    if node.level == 0:
                        imported.add(node.module or "")
                    else:
                        imported.add("open_intelligence." + (node.module or ""))
            self.assertEqual(imported & forbidden, set(),
                             f"{name} imports a model-call module")
            self.assertNotIn("muse-spark", path.read_text(),
                             f"{name} names a model")

    def test_dimension_modules_are_registered_in_the_tripwire(self):
        boundary = (ROOT / "tests" / "test_vertical_boundary.py").read_text()
        for name in D3_MODULES:
            self.assertIn(f'"open_intelligence.{name}"', boundary)


if __name__ == "__main__":
    unittest.main()
