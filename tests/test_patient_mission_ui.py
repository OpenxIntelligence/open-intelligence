import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


class PatientMissionUiContractTests(unittest.TestCase):
    def test_portal_contains_semantic_patient_mission_surface(self):
        html = (ROOT / "web" / "index.html").read_text()

        self.assertIn('href="#patient-mission"', html)
        self.assertIn('id="patient-mission"', html)
        self.assertIn('id="mission-status"', html)
        self.assertIn('id="mission-summary"', html)
        self.assertIn('id="mission-known"', html)
        self.assertIn('id="mission-unresolved"', html)
        self.assertIn('id="mission-changes"', html)
        self.assertIn('id="mission-actions"', html)
        self.assertIn('id="mission-guardrails"', html)
        self.assertIn(
            "Workflow orientation only. Not a diagnosis or treatment recommendation.",
            html,
        )
        self.assertIn('<script src="/mission.js" defer></script>', html)

    def test_renderer_is_case_scoped_source_safe_and_refreshable(self):
        javascript = (ROOT / "web" / "mission.js").read_text()

        self.assertIn(
            "/api/cases/${encodeURIComponent(caseId)}/mission",
            javascript,
        )
        self.assertIn("requestSequence", javascript)
        self.assertIn("picker.value !== caseId", javascript)
        self.assertIn("MutationObserver", javascript)
        self.assertIn("textContent", javascript)
        self.assertNotIn("innerHTML", javascript)

    def test_local_server_serves_the_separate_renderer(self):
        server = (ROOT / "src" / "open_intelligence" / "__main__.py").read_text()

        self.assertIn('if path == "/mission.js":', server)
        self.assertIn('self._static("mission.js", "text/javascript; charset=utf-8")', server)


if __name__ == "__main__":
    unittest.main()
