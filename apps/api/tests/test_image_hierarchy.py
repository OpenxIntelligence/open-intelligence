"""Source-bound CT hierarchy checks on independently invented identifiers."""
from datetime import date
import unittest

from oi_api.images import _hierarchy_agrees


class HierarchyTests(unittest.TestCase):
    first = ("2.25.11", "2.25.12", "2.25.13", date(2026, 1, 1))

    def test_multiple_instances_series_and_studies_and_exact_retry(self):
        study, series, _, day = self.first
        inventory = [self.first, (study, series, "2.25.14", day),
                     (study, "2.25.15", "2.25.16", day),
                     ("2.25.21", "2.25.22", "2.25.23", day)]
        self.assertTrue(_hierarchy_agrees(inventory, inventory))
        self.assertTrue(_hierarchy_agrees([self.first], inventory))

    def test_conflicting_parent_role_or_study_date_fails_in_either_input(self):
        study, series, sop, day = self.first
        for conflict in (("2.25.88", series, "2.25.19", day),
                         (study, "2.25.88", sop, day),
                         (study, "2.25.81", "2.25.82", date(2026, 1, 2)),
                         (series, "2.25.81", "2.25.82", day)):
            with self.subTest(conflict=conflict):
                self.assertFalse(_hierarchy_agrees([self.first, conflict], []))
                self.assertFalse(_hierarchy_agrees([self.first], [conflict]))
        self.assertFalse(_hierarchy_agrees([(study, study, sop, day)], []))

    def test_unrelated_historical_ambiguity_does_not_hide_a_separate_study(self):
        earlier = ("2.25.21", "2.25.22", "2.25.23", date(2025, 1, 1))
        other = ("2.25.31", "2.25.22", "2.25.33", date(2025, 1, 2))
        self.assertTrue(_hierarchy_agrees([self.first], [earlier, other]))
