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

    def test_each_input_adapter_and_composer_is_mounted_once(self):
        from open_intelligence.workspace_host import workspace_html
        page = workspace_html()
        for asset in ('/intake.js', '/document-intake.js', '/composer.js', '/report.js'):
            self.assertEqual(page.count('src="' + asset + '"'), 1, asset)
        for control in ('source-upload-form', 'intake-upload-form', 'composer-context'):
            self.assertEqual(page.count('id="' + control + '"'), 1, control)


if __name__ == '__main__':
    unittest.main()
