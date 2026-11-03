"""Owned-question narrative inputs must be case-switch guarded and cleared.

An unfinished owner label or evidence note must never be silently
discarded by a case switch, nor attached to another case: the picker
guard blocks the switch while the text is non-empty, and the clear loop
empties it once a switch is allowed.
"""
import unittest
from pathlib import Path

APP_JS = Path(__file__).resolve().parents[1] / "web" / "app.js"
GUARDED = ("owner-label-input", "note-text")


class CaseSwitchGuardTests(unittest.TestCase):
    def test_owned_question_inputs_guarded_and_cleared(self):
        text = APP_JS.read_text()
        guard_at = text.index(".some(id => el(id).value.trim())")
        guard_block = text[max(0, guard_at - 600):guard_at]
        clear_at = text.index("for (const id of [")
        clear_block = text[clear_at:clear_at + 500]
        for field in GUARDED:
            self.assertIn("'%s'" % field, guard_block,
                          "%s missing from the case-switch guard array" % field)
            self.assertIn("'%s'" % field, clear_block,
                          "%s missing from the case-switch clear loop" % field)


if __name__ == "__main__":
    unittest.main()
