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
GUARDED_OWNED = ("owner-label-input", "note-text")
GUARDED_SLICE = ("counterevidence-reason", "safety-detail")
GUARDED_PORTFOLIO = ("flag-reason", "dimension-note")
GUARDED_RECENT_MAIN = (
    "scoped-decision-note", "scoped-dissent-rationale",
    "ft-title", "ft-detail", "ft-reason", "ft-update-reason",
    "option-label", "dependency-anchor", "task-label", "task-owner",
    "threat-description", "threat-anchor", "reviewer-label", "review-scope",
)
GUARDED_APPOINTMENTS = (
    "appt-title", "appt-purpose", "appt-date", "appt-time", "appt-location",
    "appt-actor", "appt-reason",
    "appt-new-date", "appt-new-time", "appt-change-actor", "appt-change-reason",
)


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


    def test_recent_main_draft_fields_guarded_and_cleared(self):
        """Preserve accepted #429/#430 case-switch isolation in H1."""
        text = APP_JS.read_text()
        at = text.index("picker.addEventListener('change'")
        guard_end = text.index(".some(id => el(id).value.trim())", at)
        guard = text[at:guard_end]
        clear_start = text.index("for (const id of [", guard_end)
        clear_end = text.index("]) el(id).value = '';", clear_start)
        clear = text[clear_start:clear_end]
        for field in GUARDED_RECENT_MAIN:
            with self.subTest(field=field):
                self.assertIn("'%s'" % field, guard, "missing draft guard")
                self.assertIn("'%s'" % field, clear, "missing draft clear")

    def test_appointment_inputs_guarded_and_cleared(self):
        """D6: an unfinished appointment draft must block a case switch
        and clear once a switch is allowed — same treatment as every
        other case-scoped draft. Full-span check (like the recent-main
        test): the appointment fields sit before the eight
        test-asserted fields in the guard array and at the end of the
        clear loop, so the fixed lookbacks of the other tests are
        untouched."""
        text = APP_JS.read_text()
        at = text.index("picker.addEventListener('change'")
        guard_end = text.index(".some(id => el(id).value.trim())", at)
        guard = text[at:guard_end]
        clear_start = text.index("for (const id of [", guard_end)
        clear_end = text.index("]) el(id).value = '';", clear_start)
        clear = text[clear_start:clear_end]
        for field in GUARDED_APPOINTMENTS:
            with self.subTest(field=field):
                self.assertIn("'%s'" % field, guard, "missing draft guard")
                self.assertIn("'%s'" % field, clear, "missing draft clear")

    def test_post_submit_clears_sensitive_draft_fields(self):
        text = APP_JS.read_text()
        dep_start = text.index("el('option-dependency-form').addEventListener")
        dep_end = text.index("el('option-task-form').addEventListener", dep_start)
        self.assertIn("el('dependency-anchor').value = '';", text[dep_start:dep_end])
        rev_start = text.index("el('option-review-form').addEventListener")
        rev_end = text.index("el('visit-form').addEventListener", rev_start)
        self.assertIn("el('reviewer-label').value = '';", text[rev_start:rev_end])
        self.assertIn("el('review-scope').value = '';", text[rev_start:rev_end])
        # D6: the appointment forms clear their drafts after a
        # successful submit (create clears the create fields, change
        # clears the change fields).
        create_start = text.index("el('appointments-form').addEventListener")
        create_end = text.index("el('appointments-change-form').addEventListener", create_start)
        for field in ("appt-title", "appt-purpose", "appt-date", "appt-time",
                      "appt-location", "appt-actor", "appt-reason"):
            self.assertIn("'%s'" % field, text[create_start:create_end])
        change_start = text.index("el('appointments-change-form').addEventListener")
        change_end = text.index("el('goal-form').addEventListener", change_start)
        for field in ("appt-new-date", "appt-new-time", "appt-change-actor",
                      "appt-change-reason"):
            self.assertIn("'%s'" % field, text[change_start:change_end])


if __name__ == "__main__":
    unittest.main()
