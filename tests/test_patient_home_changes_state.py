"""Patient home must never claim nothing changed before the changes fetch
succeeds for the current case.

Regression test for the #366 fix loop. The patient home is client-side
JavaScript, and the browser journey needs Chromium, so this test asserts the
rendering structure statically: the reassurance line may only render behind a
known-state check, a loading line must exist for the pending state, an error
line must exist for the failed state, and a failed fetch must record the case
and repaint the home instead of being swallowed.
"""

import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
VIEWS = ROOT / "web" / "views.js"


def window(text, start, end):
    begin = text.index(start)
    stop = text.index(end, begin)
    return text[begin:stop]


class PatientHomeChangesStateTest(unittest.TestCase):
    def setUp(self):
        self.text = VIEWS.read_text(encoding="utf-8")

    def test_error_case_is_tracked(self):
        self.assertIn("let changesErrorCase", self.text)

    def test_paint_home_has_loading_error_and_guarded_reassurance(self):
        home = window(self.text, "function paintHome(state)", "function paintPrepare(state)")
        self.assertIn("Nothing has changed", home)
        self.assertIn("Checking for updates", home)
        self.assertIn("could not check for updates", home)
        # The reassurance must sit behind the known-state branch, not behind
        # a bare "no amendments" check.
        self.assertIn("changesKnown", home)
        self.assertIn("else if (!amendments.length)", home)

    def test_failed_fetch_records_case_and_repaints_home(self):
        loader = window(self.text, "async function loadChanges(state)", "const UNRESOLVED")
        caught = loader[loader.index("catch (_)"):]
        self.assertIn("changesErrorCase = requested", caught)
        self.assertIn("paintHome(ready())", caught)

    def test_success_clears_error_case(self):
        loader = window(self.text, "async function loadChanges(state)", "const UNRESOLVED")
        self.assertIn("changesErrorCase = null", loader)


if __name__ == "__main__":
    unittest.main()
