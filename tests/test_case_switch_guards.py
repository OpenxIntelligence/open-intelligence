"""Case-switch guard coverage for owned-question, synthesis, slice, and portfolio inputs.

An unfinished owner label, evidence note, limitation-note text, author
label, counterevidence reason, safety detail, flag reason, or dimension
note must never be silently discarded by a case switch, nor attached to
another case: the picker guard blocks the switch while the text is
non-empty, and the clear loop empties it once a switch is allowed.
"""
import unittest
from pathlib import Path

APP_JS = Path(__file__).resolve().parents[1] / "web" / "app.js"
GUARDED_SYNTHESIS = ("synthesis-note-text", "synthesis-note-author")
GUARDED_OWNED = ("owner-label-input", "note-text", "question-note-text")
GUARDED_SLICE = ("counterevidence-reason", "safety-detail")
GUARDED_PORTFOLIO = ("flag-reason", "dimension-note")


class CaseSwitchGuardTests(unittest.TestCase):
    def test_synthesis_note_inputs_guarded_and_cleared(self):
        text = APP_JS.read_text()
        handler_at = text.index("picker.addEventListener('change'")
        guard_at = text.index(".some(id => el(id).value.trim())", handler_at)
        guard_block = text[max(0, guard_at - 700):guard_at]
        clear_at = text.index("for (const id of [", guard_at)
        clear_block = text[clear_at:clear_at + 600]
        for field in GUARDED_SYNTHESIS:
            self.assertIn("'%s'" % field, guard_block,
                          "%s missing from the case-switch guard array" % field)
            self.assertIn("'%s'" % field, clear_block,
                          "%s missing from the case-switch clear loop" % field)

    def test_owned_question_inputs_guarded_and_cleared(self):
        text = APP_JS.read_text()
        handler_at = text.index("picker.addEventListener('change'")
        guard_at = text.index(".some(id => el(id).value.trim())", handler_at)
        guard_block = text[max(0, guard_at - 600):guard_at]
        clear_at = text.index("for (const id of [", guard_at)
        clear_block = text[clear_at:clear_at + 500]
        for field in GUARDED_OWNED:
            self.assertIn("'%s'" % field, guard_block,
                          "%s missing from the case-switch guard array" % field)
            self.assertIn("'%s'" % field, clear_block,
                          "%s missing from the case-switch clear loop" % field)

    def test_slice_narrative_inputs_guarded_and_cleared(self):
        text = APP_JS.read_text()
        handler_at = text.index("picker.addEventListener('change'")
        guard_at = text.index(".some(id => el(id).value.trim())", handler_at)
        guard_block = text[max(0, guard_at - 700):guard_at]
        clear_at = text.index("for (const id of [", guard_at)
        clear_block = text[clear_at:clear_at + 600]
        for field in GUARDED_SLICE:
            self.assertIn("'%s'" % field, guard_block,
                          "%s missing from the case-switch guard array" % field)
            self.assertIn("'%s'" % field, clear_block,
                          "%s missing from the case-switch clear loop" % field)

    def test_portfolio_inputs_guarded_and_cleared(self):
        text = APP_JS.read_text()
        handler_at = text.index("picker.addEventListener('change'")
        guard_at = text.index(".some(id => el(id).value.trim())", handler_at)
        guard_block = text[max(0, guard_at - 700):guard_at]
        clear_at = text.index("for (const id of [", guard_at)
        clear_block = text[clear_at:clear_at + 600]
        for field in GUARDED_PORTFOLIO:
            self.assertIn("'%s'" % field, guard_block,
                          "%s missing from the case-switch guard array" % field)
            self.assertIn("'%s'" % field, clear_block,
                          "%s missing from the case-switch clear loop" % field)


if __name__ == "__main__":
    unittest.main()
