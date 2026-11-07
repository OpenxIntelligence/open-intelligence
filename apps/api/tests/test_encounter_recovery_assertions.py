"""Negative controls for the Compose drill's recovered EHR response comparison."""
from copy import deepcopy
import hashlib
import importlib.util
from pathlib import Path
import unittest

spec = importlib.util.spec_from_file_location(
    "registry_proof", Path(__file__).resolve().parents[1] / "tools/verify_connected_chart_compose.py")
probe = importlib.util.module_from_spec(spec)
spec.loader.exec_module(probe)


class RecoveredChartAssertions(unittest.TestCase):
    def setUp(self):
        patient, encounter, actor = "PAT-FICTIONAL", 14, "ACTOR-FICTIONAL"
        self.drafts = [
            {"body": "Fictional initial note.", "facility_id": "FAC-INITIAL",
             "department_id": "DEPT-INITIAL", "note_kind": "consultation"},
            {"body": "Fictional revision — café.", "facility_id": "FAC-UPDATED",
             "department_id": "DEPT-UPDATED", "note_kind": "progress"},
        ]
        schedule = {"external_key": "VISIT-PROOF", "kind": "outpatient", "service_date": "2026-05-04"}
        encounter_page = {"patient_id": patient, "next_after_id": None, "encounters": [
            dict(schedule, patient_id=patient, id=encounter, status="in_progress", revision=2,
                 created_at="2026-05-03T12:00:00+00:00", updated_at="2026-05-04T10:00:00+00:00")]}
        header_page = {"patient_id": patient, "encounter_id": encounter, "next_after_id": None, "notes": [
            {"id": 25, "note_key": probe.NOTE_KEY, "latest_version": 2}]}
        history = {"patient_id": patient, "encounter_id": encounter, "note_key": probe.NOTE_KEY,
                   "next_after_version": None, "versions": []}
        receipts = []
        for index, draft in enumerate(self.drafts, 1):
            digest = hashlib.sha256(draft["body"].encode("utf-8")).hexdigest()
            history["versions"].append(dict(draft, id=50+index, version=index, sha256=digest,
                authored_by=actor, status="draft", created_at=f"2026-05-04T10:0{index}:00+00:00",
                supersedes_id=None if index == 1 else 51, amendment_reason=None))
            receipts.append({"note_id": 25, "note_key": probe.NOTE_KEY, "version": index,
                             "status": "draft", "sha256": digest})
        self.pages = [encounter_page, header_page, history]
        self.inputs = dict(patient=patient, encounter_id=encounter, schedule=schedule, actor=actor,
                           drafts=self.drafts, receipts=receipts)

    def check(self, pages):
        return probe.verify_chart(*pages, **self.inputs)

    def test_exact_original_metadata_including_timestamps_is_compared(self):
        original = self.check(self.pages)
        self.assertEqual(self.check(deepcopy(self.pages)), original)
        restored = deepcopy(self.pages)
        restored[2]["versions"][1]["created_at"] = restored[2]["versions"][0]["created_at"]
        self.assertNotEqual(self.check(restored), original)

    def test_rejects_mislinked_scope_and_note_header(self):
        for page, field, other in ((0, "patient_id", "PAT-OTHER"), (1, "encounter_id", 22),
                                   (2, "note_key", "NOTE-OTHER")):
            with self.subTest(page=page, field=field), self.assertRaises(AssertionError):
                restored = deepcopy(self.pages)
                restored[page][field] = other
                self.check(restored)
        restored = deepcopy(self.pages)
        restored[1]["notes"][0]["id"] = 42
        with self.assertRaises(AssertionError):
            self.check(restored)

    def test_rejects_body_even_with_matching_recomputed_hash_and_broken_provenance(self):
        body = "Different fictional note."
        for changes in ({"body": body, "sha256": hashlib.sha256(body.encode("utf-8")).hexdigest()},
                        {"sha256": "0"*64}, {"supersedes_id": None}, {"authored_by": "ACTOR-OTHER"},
                        {"facility_id": self.drafts[0]["facility_id"]},
                        {"department_id": self.drafts[0]["department_id"]},
                        {"note_kind": "consultation"}, {"version": 1}, {"status": "attested"}):
            with self.subTest(fields=tuple(changes)), self.assertRaises(AssertionError):
                restored = deepcopy(self.pages)
                restored[2]["versions"][1].update(changes)
                self.check(restored)
