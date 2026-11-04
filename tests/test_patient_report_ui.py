import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


class PatientReportUiContractTests(unittest.TestCase):
    def test_portal_contains_printable_patient_report_surface(self):
        html = (ROOT / "web" / "index.html").read_text()

        self.assertIn('href="#patient-report"', html)
        self.assertIn('id="patient-report"', html)
        self.assertIn('id="report-reading-note"', html)
        self.assertIn('id="report-meta"', html)
        self.assertIn('id="report-print"', html)
        self.assertIn('id="report-text-link"', html)
        self.assertIn('id="report-sections"', html)
        self.assertIn(
            "Fictional demo report. This is not a real patient file",
            html,
        )
        self.assertIn('<script src="/report.js" defer></script>', html)
        # Reachable from the case view: nav entry plus patient-view link.
        self.assertIn(">Plain-language report</a>", html)
        self.assertIn("Open the printable plain-language report", html)

    def test_renderer_is_case_scoped_source_safe_and_printable(self):
        javascript = (ROOT / "web" / "report.js").read_text()

        self.assertIn(
            "/api/cases/${encodeURIComponent(caseId)}/patient-report",
            javascript,
        )
        self.assertIn("?format=text", javascript)
        self.assertIn("window.print()", javascript)
        self.assertIn("requestSequence", javascript)
        self.assertIn("picker.value !== caseId", javascript)
        self.assertIn("MutationObserver", javascript)
        self.assertIn("textContent", javascript)
        self.assertNotIn("innerHTML", javascript)

    def test_local_server_serves_the_report_renderer(self):
        server = (ROOT / "src" / "open_intelligence" / "__main__.py").read_text()

        self.assertIn('if path == "/report.js":', server)
        self.assertIn('self._static("report.js", "text/javascript; charset=utf-8")', server)

    def test_print_styles_keep_fictional_labels_and_hide_actions(self):
        css = (ROOT / "web" / "style.css").read_text()

        self.assertIn(".report-actions { display: none; }", css)
        self.assertIn("#patient-report .pill-warn", css)


if __name__ == "__main__":
    unittest.main()
