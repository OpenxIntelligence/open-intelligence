"""Served frontend contracts that a layout-only redesign must preserve."""
from html.parser import HTMLParser
import json
from pathlib import Path
import unittest

from open_intelligence.workspace_host import workspace_html

ROOT = Path(__file__).resolve().parents[1]
CONTRACT_ATTRIBUTES = {'type', 'name', 'required', 'minlength', 'maxlength', 'min', 'max',
                       'step', 'pattern', 'accept', 'multiple', 'method', 'action'}


class Controls(HTMLParser):
    def __init__(self):
        super().__init__()
        self.ids = []
        self.forms = {}
        self.current = None
        self.select = None

    def handle_starttag(self, tag, attributes):
        attrs = dict(attributes)
        if attrs.get('id'):
            self.ids.append(attrs['id'])
        if tag == 'form':
            self.current = attrs['id']
            self.forms[self.current] = {'attributes': {k: v for k, v in attrs.items() if k in CONTRACT_ATTRIBUTES}, 'controls': {}}
        if self.current and tag in {'input', 'select', 'textarea', 'button'} and attrs.get('id'):
            control = {'tag': tag, 'attributes': {k: v for k, v in attrs.items() if k in CONTRACT_ATTRIBUTES}}
            self.forms[self.current]['controls'][attrs['id']] = control
            if tag == 'select':
                self.select = control
                self.select['options'] = []
        if tag == 'option' and self.select is not None:
            self.select['options'].append(attrs.get('value'))

    def handle_endtag(self, tag):
        if tag == 'select':
            self.select = None
        if tag == 'form':
            self.current = None


class WorkspaceRedesignTests(unittest.TestCase):
    def test_connected_host_retains_every_original_form_and_native_validation_contract(self):
        page = Controls()
        page.feed(workspace_html())
        baseline = json.loads((ROOT / 'tests/fixtures/workspace-form-contracts.json').read_text())
        self.assertEqual(len(baseline), 16)
        for form, contract in baseline.items():
            with self.subTest(form=form):
                self.assertIn(form, page.forms)
                self.assertEqual(page.forms[form], contract)

    def test_both_served_pages_have_unique_ids_and_the_original_dialogs(self):
        for html in [(ROOT / 'web/index.html').read_text(), workspace_html()]:
            page = Controls()
            page.feed(html)
            self.assertEqual(len(page.ids), len(set(page.ids)), 'Cloned controls can misdirect existing handlers')
            for identity in ['source-dialog', 'compare-dialog', 'notice', 'case-picker', 'event-list',
                             'composer-context-fingerprint', 'model-investigation-question']:
                self.assertIn(identity, page.ids)


if __name__ == '__main__':
    unittest.main()
