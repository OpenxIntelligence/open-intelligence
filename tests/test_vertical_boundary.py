"""Tests for the vertical interface (program plan slice V1).

V1 makes "multi-vertical" real instead of aspirational: the core holds
no oncology knowledge; oncology lives behind the vertical interface,
and the first proving vertical — a minimal synthetic cardiology
vertical — registers through that interface and runs the same pipeline
(route, K-checks, Skeptic, T6) with no core change beyond the
interface itself.

No live model call is made here: the Skeptic and repair model calls
are injectable, and the end-to-end test drives them with stubs. The
live prompt is verified separately against the Meta Model API on
synthetic data.
"""

import ast
import re
import unittest
from pathlib import Path

from open_intelligence.evidence_catalog import LINK_TEMPLATES, SOURCE_KINDS
from open_intelligence.investigation import validate_output
from open_intelligence.kchecks import (
    KCheckContext,
    Slot,
    SourceVersionInfo,
    derive_claim_slots,
    run_kchecks,
)
from open_intelligence.orchestrator import decide_route
from open_intelligence.skeptic import run_verification
from open_intelligence.store import CaseStore
from open_intelligence.vertical import (
    Vertical,
    VerticalError,
    build_scope_patterns,
    default_vertical,
    get_vertical,
    list_verticals,
    register_vertical,
)

SRC = Path(__file__).resolve().parents[1] / "src" / "open_intelligence"

# Dimension modules (program plan slices D1-D9) must not import each
# other; cross-dimension interaction happens only through the ledger
# and `route.decided`. D1 populates the list with the data-integration
# dimension modules; each later dimension slice appends its own.
DIMENSION_MODULES: tuple[str, ...] = (
    "open_intelligence.extraction",
    "open_intelligence.specimen_chain",
    "open_intelligence.terminology",
    "open_intelligence.fhir_exchange",
    "open_intelligence.dicom",
    "open_intelligence.longitudinal",
    "open_intelligence.lab_series",
    "open_intelligence.imaging",
    "open_intelligence.molecular",
    "open_intelligence.therapy",
    "open_intelligence.patient_analytics",
    "open_intelligence.literature",
    "open_intelligence.trials",
    "open_intelligence.hypothesis",
    "open_intelligence.appointments",
    "open_intelligence.notifications",
    "open_intelligence.referrals",
    "open_intelligence.team_collaboration",
)


def _module_imports(path):
    """Absolute module names imported by one source file (AST)."""
    tree = ast.parse(path.read_text())
    imports = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                imports.add(alias.name)
        elif isinstance(node, ast.ImportFrom):
            if node.level == 0:
                base = node.module or ""
            else:
                base = "open_intelligence" + (
                    ("." + node.module) if node.module else ""
                )
            for alias in node.names:
                imports.add(f"{base}.{alias.name}" if base else alias.name)
    return imports


def _cross_dimension_violations(modules_to_imports, dimension_modules):
    """Pairs where one dimension module imports another.

    Only dimension modules are constrained: the shared core (the
    ledger, the import path) must be able to call a dimension module --
    that is how the A1 checker reaches the live arrival path. What the
    orthogonality rule forbids is one dimension module importing
    another; cross-dimension interaction happens only through the
    ledger and `route.decided`.
    """
    violations = []
    dimension_by_stem = {name.rsplit(".", 1)[-1]: name
                         for name in dimension_modules}
    for module, imports in modules_to_imports.items():
        own = dimension_by_stem.get(module)
        if own is None:
            continue
        for other in dimension_modules:
            if other == own:
                continue
            if any(imp == other or imp.startswith(other + ".")
                   for imp in imports):
                violations.append((module, other))
    return violations


def _version(version_id, *, state="current", specimen="SPEC-A",
             specimen_date="2026-05-03", report_date="2026-05-05",
             received_date="2026-05-06T10:00:00Z", supersedes_id=None):
    return SourceVersionInfo(
        id=version_id, specimen_date=specimen_date, report_date=report_date,
        received_date=received_date, state=state, supersedes_id=supersedes_id,
        sha256=f"digest-{version_id}", specimen_id=specimen)


def _cardiology_context(**overrides):
    """A small synthetic cardiology case, in the C2/C4 fixture shape.

    v1 ECG (SPEC-A) says atrial fibrillation was identified; v2 echo
    (SPEC-B) measures the ejection fraction as 31%; v4 is a second
    current ECG (SPEC-A) that disagrees with v1 on rhythm — the same
    specimen, different value, so a T6 source group forms. All
    predicates come from the cardiology vertical, resolved through the
    registry.
    """
    vertical = get_vertical("cardiology")
    versions = {
        1: _version(1),
        2: _version(2, specimen="SPEC-B", specimen_date="2026-05-17",
                    report_date="2026-05-18",
                    received_date="2026-05-19T10:00:00Z"),
        4: _version(4),
    }
    slots = [
        Slot(subject="CASE-CARDIO", field="rhythm", value="reported",
             source_version_id=1, specimen="SPEC-A",
             quote="Atrial fibrillation was identified."),
        Slot(subject="CASE-CARDIO", field="ejection-fraction",
             value="reported", source_version_id=2, specimen="SPEC-B",
             quote="The ejection fraction was measured as 31%."),
        Slot(subject="CASE-CARDIO", field="rhythm", value="not-reported",
             source_version_id=4, specimen="SPEC-A",
             quote="Atrial fibrillation was not performed."),
    ]
    context = KCheckContext(
        subject="CASE-CARDIO", source_versions=versions, derived_slots=slots,
        assessment_statements={},
        snapshot_as_of="2026-06-01T00:00:00Z",
        snapshot_source_ids={1, 2, 4},
        synonyms=dict(vertical.synonyms),
        scope_patterns=list(vertical.scope_patterns),
        condition_terms=list(vertical.condition_terms),
        substance_names=[], evidence_tiers={},
    )
    for key, value in overrides.items():
        setattr(context, key, value)
    return context


def _claim(text, source_id=1):
    return {"text": text, "support": "context",
            "citations": [{"type": "source", "id": source_id}],
            "uncertainty": "moderate", "limits": "Synthetic only."}


def _stub_call(payload):
    """A stub model call returning one canned verdict per claim."""
    def call(prompt):
        return {"reviews": [
            {"claim_index": index, "verdict": verdict,
             "reason": f"stub review {index}: {verdict}"}
            for index, verdict in enumerate(payload)]}
    return call


class ImportGraphTests(unittest.TestCase):
    def test_core_modules_do_not_import_vertical_definitions(self):
        # The tripwire: the core resolves verticals only through the
        # registry in vertical.py. A vertical definition module
        # (vertical_oncology, vertical_cardiology, ...) is imported by
        # name nowhere in src — the registry lazy-loads it by string.
        violations = []
        for path in sorted(SRC.glob("*.py")):
            for imported in _module_imports(path):
                if imported.startswith("open_intelligence.vertical_"):
                    violations.append((path.name, imported))
        self.assertEqual(violations, [])

    def test_dimension_modules_do_not_import_each_other(self):
        modules_to_imports = {
            path.stem: _module_imports(path)
            for path in sorted(SRC.glob("*.py"))
        }
        self.assertEqual(
            _cross_dimension_violations(modules_to_imports, DIMENSION_MODULES),
            [])

    def test_dimension_checker_catches_a_fake_violation(self):
        # The checker is proved on a fake graph as well as on the real
        # one, so a regression in the checker itself is caught.
        fake = {"dim_a": {"dim_b"}, "dim_b": set()}
        self.assertEqual(
            _cross_dimension_violations(fake, ("dim_a", "dim_b")),
            [("dim_a", "dim_b")])


class RegistryTests(unittest.TestCase):
    def test_oncology_resolves_with_legacy_content(self):
        oncology = get_vertical("oncology")
        self.assertEqual(oncology.synonyms["not tested"], "not-reported")
        self.assertEqual(oncology.synonyms["detected"], "reported")
        self.assertEqual(
            list(oncology.condition_terms),
            ["cancer", "carcinoma", "neoplasm", "malignancy", "malignant",
             "tumour", "tumor"])
        self.assertEqual(oncology.lot_ruleset, "lot-rules-1")
        # The evidence bindings are the catalog's values; the vertical
        # is the declaration, the catalog the storage-side contract.
        self.assertEqual(oncology.evidence_kinds, SOURCE_KINDS)
        self.assertEqual(oncology.link_templates, LINK_TEMPLATES)

    def test_scope_patterns_share_one_shape(self):
        oncology = get_vertical("oncology")
        cardiology = get_vertical("cardiology")
        self.assertEqual(len(oncology.scope_patterns), 9)
        self.assertEqual(len(cardiology.scope_patterns), 9)
        oncology_patterns = [p.pattern for p in oncology.scope_patterns]
        cardiology_patterns = [p.pattern for p in cardiology.scope_patterns]
        # The eight generic patterns are identical; only the "you
        # have" pattern carries vertical content.
        for marker in ("first[- ]line", "dose of", "mg", "eligible for",
                       "NCT", "prognosis", "should (consider", "rank"):
            self.assertTrue(
                any(marker in pattern for pattern in oncology_patterns),
                marker)
        self.assertEqual(
            [p for p in oncology_patterns if "you have" not in p],
            [p for p in cardiology_patterns if "you have" not in p])
        oncology_you_have = next(
            p for p in oncology_patterns if "you have" in p)
        cardiology_you_have = next(
            p for p in cardiology_patterns if "you have" in p)
        self.assertIn("cancer", oncology_you_have)
        self.assertIn("heart failure", cardiology_you_have)
        self.assertNotIn("cancer", cardiology_you_have)

    def test_cardiology_resolves(self):
        cardiology = get_vertical("cardiology")
        self.assertEqual(cardiology.synonyms["not performed"], "not-reported")
        self.assertEqual(cardiology.synonyms["identified"], "reported")
        self.assertIn("heart failure", cardiology.condition_terms)
        self.assertIn("myocardial infarction", cardiology.condition_terms)
        self.assertEqual(cardiology.lot_ruleset, "therapy-rules-1")
        self.assertIn("ecg", cardiology.evidence_kinds)

    def test_unknown_and_invalid_names_raise(self):
        for name in ("nope", "Bad Name", "", None, "../vertical_oncology"):
            with self.assertRaises(VerticalError, msg=repr(name)):
                get_vertical(name)

    def test_duplicate_registration_raises(self):
        register_vertical(Vertical(name="dup_test"))
        with self.assertRaises(VerticalError):
            register_vertical(Vertical(name="dup_test"))

    def test_runtime_stub_vertical_registers(self):
        stub = register_vertical(Vertical(
            name="stub_test",
            synonyms={"not done": "not-reported"},
            condition_terms=("stub-condition",),
            scope_patterns=tuple(build_scope_patterns(("stub-condition",))),
            lot_ruleset="stub-rules-1"))
        self.assertIs(get_vertical("stub_test"), stub)
        self.assertIn("stub_test", list_verticals())
        self.assertIn("oncology", list_verticals())
        self.assertIn("cardiology", list_verticals())

    def test_default_vertical_is_oncology(self):
        self.assertEqual(default_vertical().name, "oncology")
        self.assertIs(default_vertical(), get_vertical("oncology"))

    def test_terminology_bindings_live_on_the_vertical(self):
        # D2: the oncology vertical declares its own terminology
        # binding (histology -> ICD-10 C80.1); V2: cardiology
        # declares its own (ejection-fraction -> LOINC 10230-1,
        # heart-failure -> ICD-10 I50.9), pinned from the
        # publishers' own listings.
        oncology = get_vertical("oncology")
        self.assertEqual(
            oncology.terminology_bindings["histology"],
            ({"system": "http://hl7.org/fhir/sid/icd-10", "code": "C80.1",
              "display": "Malignant (primary) neoplasm, unspecified"},))
        self.assertEqual(
            get_vertical("cardiology").terminology_bindings,
            {
                "ejection-fraction": (
                    {"system": "http://loinc.org", "code": "10230-1",
                     "display": "Left ventricular Ejection fraction"},),
                "heart-failure": (
                    {"system": "http://hl7.org/fhir/sid/icd-10",
                     "code": "I50.9",
                     "display": "Heart failure, unspecified"},),
            })


class CrossVerticalBehaviourTests(unittest.TestCase):
    def test_cardiology_synonym_resolves_where_oncology_does_not(self):
        slots = _cardiology_context().derived_slots
        cardiology = get_vertical("cardiology")
        oncology = get_vertical("oncology")
        self.assertEqual(
            derive_claim_slots("Ejection fraction was not performed.",
                               slots, cardiology.synonyms),
            [{"field": "ejection-fraction", "value": "not reported"}])
        self.assertEqual(
            derive_claim_slots("Ejection fraction was not performed.",
                               slots, oncology.synonyms),
            [])

    def test_k6_you_have_is_vertical_specific(self):
        claim = _claim("You have heart failure and should know.")
        cardiology_result = run_kchecks([claim], _cardiology_context())
        self.assertEqual(cardiology_result.dropped[0]["reason"], "k6_scope")
        oncology = get_vertical("oncology")
        oncology_context = _cardiology_context(
            synonyms=dict(oncology.synonyms),
            scope_patterns=list(oncology.scope_patterns),
            condition_terms=list(oncology.condition_terms))
        oncology_result = run_kchecks([claim], oncology_context)
        self.assertEqual(len(oncology_result.kept), 1)

    def test_oncology_k6_still_drops_cancer(self):
        # The oncology path is unchanged: the same claim the C2 suite
        # pins still drops, now through the registry-resolved vertical.
        claim = _claim("You have cancer and should know.")
        oncology = get_vertical("oncology")
        context = _cardiology_context(
            synonyms=dict(oncology.synonyms),
            scope_patterns=list(oncology.scope_patterns),
            condition_terms=list(oncology.condition_terms))
        result = run_kchecks([claim], context)
        self.assertEqual(result.dropped[0]["reason"], "k6_scope")


class CardiologyEndToEndTests(unittest.TestCase):
    def setUp(self):
        self.store = CaseStore(":memory:")
        self.store.add_case("CASE-CARDIO", "Fictional cardiology case")
        self.question_id = self.store.add_question(
            "CASE-CARDIO", "What does the cardiac record report?")

    def tearDown(self):
        self.store.close()

    def test_cardiology_investigation_end_to_end(self):
        # Route: decided before any agent event, under the cardiology
        # case, through the same orchestrator as the oncology path.
        route = decide_route(self.store, "CASE-CARDIO", "evidence-summary",
                             self.question_id, "clinician")
        self.assertEqual(route["agents"], ["A1"])
        self.assertEqual(route["templateId"], "evidence-summary")

        context = _cardiology_context()
        facts = {"valid_sources": {1, 2, 4}, "valid_assessments": set()}
        validated = validate_output(
            {"claims": [
                _claim("The ejection fraction was measured as 31%.",
                       source_id=2),
                _claim("The ejection fraction was measured as 31 cm.",
                       source_id=2),
                _claim("Atrial fibrillation was identified.", source_id=1),
                _claim("You have heart failure and should know.",
                       source_id=1),
            ], "abstentions": []},
            facts["valid_sources"], facts["valid_assessments"], context)
        # The K-checks keep the supported claims and the planted
        # misstatement (it passes K1-K7 by construction, as in C4);
        # only the K6 scope claim drops here — under the cardiology
        # vertical, which is what makes it drop.
        self.assertEqual(len(validated.claims), 3)
        self.assertEqual(len(validated.dropped), 1)
        self.assertEqual(validated.dropped[0]["reason"], "k6_scope")

        # Verification: stub Skeptic supports the true claims and
        # challenges the misstatement; the repair round has nothing
        # repairable (a k6_scope drop is never repaired).
        record = run_verification(
            validated, context, facts, mode="live",
            store=self.store, case_id="CASE-CARDIO",
            skeptic_call=_stub_call(["supported", "challenged",
                                     "supported"]),
            repair_call=_stub_call([]))
        kept_texts = [claim["text"] for claim in validated.claims]
        self.assertIn("The ejection fraction was measured as 31%.",
                      kept_texts)
        self.assertIn("Atrial fibrillation was identified.", kept_texts)
        self.assertNotIn("The ejection fraction was measured as 31 cm.",
                         kept_texts)
        held = next((entry for entry in validated.dropped
                     if entry.get("reason") == "skeptic_challenged"), None)
        self.assertIsNotNone(held)
        codes = [code for code in record.get("abstention_codes", [])
                 if code.get("code") == "AB-CONFLICT"]
        origins = sorted(code.get("origin") for code in codes)
        self.assertIn("skeptic_challenge", origins)
        # The run cited source 1, which the rhythm disagreement
        # touches, so the source disagreement also fires.
        self.assertIn("source_disagreement", origins)
        groups = record.get("t6", {}).get("contradictions", [])
        rhythm = next((group for group in groups
                       if group.get("field") == "rhythm"), None)
        self.assertIsNotNone(rhythm)
        self.assertEqual(rhythm.get("origin"), "source_disagreement")
        self.assertEqual(rhythm.get("source_version_ids"), [1, 4])


if __name__ == '__main__':
    unittest.main()
