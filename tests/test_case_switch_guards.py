import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

# Every narrative text input / textarea in web/index.html, in document order.
# Selects, checkboxes, number/date auxiliaries, and the never-case-linked
# bibliography DOI lookup stay unguarded by design (see the scope test below).
GUARDED_NARRATIVE_FIELDS = [
    "question-text",
    "draft-observations",
    "draft-summary",
    "draft-assumptions",
    "evidence-text",
    "evidence-rationale",
    "evidence-withdraw-reason",
    "option-label",
    "option-description",
    "dependency-anchor",
    "task-label",
    "task-owner",
    "threat-description",
    "threat-anchor",
    "reviewer-label",
    "review-scope",
    "report-text",
]

GUARD_NOTICE = (
    "Save or explicitly clear the unfinished investigation draft "
    "before switching cases."
)

# Representative non-narrative controls that must stay out of the guard:
# selects, numeric/date auxiliaries, and the global (never case-linked)
# bibliography DOI lookup.
UNGUARDED_CONTROLS = [
    "case-picker",
    "timeline-filter",
    "question-choice",
    "option-epistemic",
    "dependency-kind",
    "dependency-lead",
    "dependency-deadline",
    "task-lead",
    "threat-date",
    "bibliography-doi",
]


def _case_switch_handler(javascript):
    start = javascript.index("picker.addEventListener('change'")
    end = javascript.index("refresh();", start)
    return javascript[start:end]


class CaseSwitchGuardTests(unittest.TestCase):
    def test_every_narrative_field_blocks_case_switch(self):
        handler = _case_switch_handler((ROOT / "web" / "app.js").read_text())
        guard, _ = handler.split("cancelSourceRead();")
        for field in GUARDED_NARRATIVE_FIELDS:
            self.assertIn("'%s'" % field, guard)

    def test_every_narrative_field_is_cleared_after_switch(self):
        handler = _case_switch_handler((ROOT / "web" / "app.js").read_text())
        _, clear = handler.split("cancelSourceRead();")
        for field in GUARDED_NARRATIVE_FIELDS:
            self.assertIn("'%s'" % field, clear)

    def test_guard_notice_wording_is_unchanged(self):
        javascript = (ROOT / "web" / "app.js").read_text()
        self.assertIn("notice('%s', true)" % GUARD_NOTICE, javascript)

    def test_selects_and_non_narrative_inputs_stay_unguarded(self):
        handler = _case_switch_handler((ROOT / "web" / "app.js").read_text())
        guard, _ = handler.split("cancelSourceRead();")
        for control in UNGUARDED_CONTROLS:
            self.assertNotIn("'%s'" % control, guard)

    def test_guarded_ids_exist_in_markup(self):
        html = (ROOT / "web" / "index.html").read_text()
        for field in GUARDED_NARRATIVE_FIELDS:
            self.assertIn('id="%s"' % field, html)


if __name__ == "__main__":
    unittest.main()
