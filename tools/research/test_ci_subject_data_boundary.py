"""Repository CI must never depend on public-case personal data.

The protected research sources and parsed methods can remain archived as code.
Tests use independently authored fixtures, not live human clinical/genomic data.
"""
from pathlib import Path
import re
import unittest


ROOT = Path(__file__).resolve().parents[2]
WORKFLOWS = ROOT / ".github" / "workflows"

# These programs were research-only live acquisition entrypoints; exercising
# their pure parsers as unit tests is permitted, invoking live entrypoints is not.
LIVE_ENTRYPOINTS = (
    "public_case_intake.py",
    "rna_expression_probe.py",
    "single_cell_probe.py",
    "public_evidence_probe.py",
    "gdc_projection_probe.py",
    "clinical_semantics_probe.py",
    "trial_screening_probe.py",
)
LIVE_CMD = re.compile(
    r"(?:^|[\s;])(?:python(?:3(?:\.\d+)?)?|\$\{?PYTHON\}?)"
    r"\s+(?:-m\s+)?(?:\./)?tools/research/"
    r"(?:" + "|".join(re.escape(n) for n in LIVE_ENTRYPOINTS) + r")(?:\s|$)",
    re.M,
)


class ProtectedCaseDataCIContract(unittest.TestCase):
    def test_all_workflows_exclude_live_personal_case_downloads(self):
        workflows = sorted(WORKFLOWS.glob("*.yml")) + sorted(WORKFLOWS.glob("*.yaml"))
        self.assertTrue(workflows, "GitHub Actions workflows were not found")
        for path in workflows:
            source = path.read_text(encoding="utf-8")
            with self.subTest(path=path.name):
                self.assertNotRegex(source, LIVE_CMD)
                self.assertNotIn("allow_public_case_catalog", source)
                self.assertNotIn("approved_public_case_eval", source)
                self.assertNotIn("sid-sijbrandij-osteosarc-dataset", source)
                self.assertNotIn("osteosarc.com/data/catalog", source)

    def test_research_method_workflows_execute_fictional_tests(self):
        for filename in ("rna-analysis.yml", "single-cell-analysis.yml",
                         "public-research.yml"):
            with self.subTest(filename=filename):
                text = (WORKFLOWS / filename).read_text(encoding="utf-8")
                self.assertIn("python -m unittest discover", text)
                self.assertNotIn("--live", text)
                self.assertNotIn("approved_public_case_eval", text)


if __name__ == "__main__":
    unittest.main()
