"""Entry composition must retain the connected patient and follow-through owners."""
import importlib.util
import unittest


class ConnectedIntakeEntryTests(unittest.TestCase):
    def test_entry_keeps_source_record_report_and_followthrough_controls(self):
        self.assertIsNotNone(
            importlib.util.find_spec('open_intelligence.workspace_host'),
            'The connected workflow has no original-file intake entry host',
        )
        from open_intelligence.workspace_host import workspace_html
        page = workspace_html()
        for marker in ('case-create-form', 'source-upload-form', 'source-file',
                       'patient-report', 'report-refresh', 'followthrough-form',
                       '/patient-record.js', '/report.js', '/workspace-entry.js'):
            with self.subTest(marker=marker):
                self.assertIn(marker, page)


if __name__ == '__main__':
    unittest.main()
