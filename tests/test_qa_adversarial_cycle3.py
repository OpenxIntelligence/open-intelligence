"""Adversarial QA tests, cycle 3 — Open Intelligence (inspection-derived, fictional data only).

Each test targets one suspected NEW defect traced to exact product lines
(see docs/qa-defect-register-cycle3.md). Each test is written to FAIL on
unpatched main (2451983) by construction and PASS once the defect is fixed.
Product code is not modified here. Cycle-1 findings (QA-01..QA-10) and
cycle-2 findings (QA-11..QA-17) are not re-filed; cross-references are noted
where a new finding neighbours an open one.

Authorship note: these tests were authored by code-trace inspection only.
The author did not execute them. Status: UNVERIFIED — a reviewer runs them.

Run from the repository root (reviewer): PYTHONPATH=src python -m unittest
tests.test_qa_adversarial_cycle3 -v
"""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "src"))

from open_intelligence.investigation import (  # noqa: E402
    ValidatedInvestigation,
    validate_output,
)
from open_intelligence.store import CaseStore  # noqa: E402
from open_intelligence.store import InvalidInput  # noqa: E402

REPORT_V1 = (
    "OI-SYNTHETIC-REPORT/1\n"
    "Patient: CASE-QA3\n"
    "Document: QA-DOC\n"
    "Type: pathology\n"
    "Event-Date: 2026-01-05\n"
    "Issued-At: 2026-01-06\n"
    "Specimen: QA-SPECIMEN\n"
    "Finding: qa-finding|reported|Fictional QA note for adversarial testing only.\n"
).encode("utf-8")

QUESTION = "Fictional QA question about the test source?"


def _seed_case(store: CaseStore, case_id: str = "CASE-QA3") -> tuple[int, int]:
    store.add_case(case_id, "Fictional QA case")
    patient_report = REPORT_V1.replace(b"CASE-QA3", case_id.encode("utf-8"))
    report = store.import_report(case_id, patient_report)
    qid = store.add_question(case_id, QUESTION)
    return int(report["source_id"]), int(qid)


class TestSaveInvestigationRejectsForeignQuestion(unittest.TestCase):
    """Suspected defect QA-18 (Low): save_investigation stores a question from
    another case without complaint (wrong-case attribution).

    Trace: CaseStore.save_investigation (src/open_intelligence/store.py lines
    2183-2199) checks only that the case exists (line 2185) and then inserts
    the investigation with the caller-supplied question_id. Every sibling
    write checks question case-scope (create_snapshot lines 2099-2101,
    assess_synthetic_evidence lines 1421-1423, create_broker_link lines
    1843-1845, link_discovery lines 1538-1540). The addressing UPDATE (lines
    2195-2196) silently matches zero rows for a foreign id, so the ledger
    gains an investigation in case A pointing at case B's question while its
    side effect quietly no-ops. The HTTP route is currently shielded because
    it calls investigation_facts first (__main__.py line 362), so this is a
    store-contract hole in the QA-13 sense, not a route crash.
    """

    def test_foreign_question_id_raises(self):
        store = CaseStore(":memory:")
        try:
            _seed_case(store, "CASE-QA3A")
            _, qid_b = _seed_case(store, "CASE-QA3B")
            validated = ValidatedInvestigation(
                status="abstained", claims=[],
                abstentions=[{"topic": "Fictional QA topic",
                              "reason": "insufficient_evidence"}],
                dropped=[], model="qa-replay", mode="replay")
            with self.assertRaises(InvalidInput):
                store.save_investigation("CASE-QA3A", qid_b, "evidence-summary",
                                         validated, "replay")
        finally:
            store.close()


class TestSaveInvestigationValidatesEnvelope(unittest.TestCase):
    """Suspected defect QA-19 (Low): save_investigation validates neither the
    mode nor the template before writing.

    Trace: CaseStore.save_investigation (store.py lines 2183-2199) binds
    mode and template straight into INSERT. An invalid mode escapes as a
    raw sqlite3.IntegrityError from the CHECK constraint (schema line 334)
    instead of the codebase-standard InvalidInput (422), and an unknown
    template string is stored silently as false provenance. The HTTP route
    validates both (__main__.py lines 355-358), so this is a store-contract
    hole in the QA-13 sense.
    """

    def _seeded(self) -> tuple[CaseStore, int]:
        store = CaseStore(":memory:")
        _, qid = _seed_case(store)
        return store, qid

    @staticmethod
    def _validated() -> ValidatedInvestigation:
        return ValidatedInvestigation(
            status="abstained", claims=[],
            abstentions=[{"topic": "Fictional QA topic",
                          "reason": "insufficient_evidence"}],
            dropped=[], model="qa-replay", mode="replay")

    def test_invalid_mode_raises_invalid_input(self):
        store, qid = self._seeded()
        try:
            with self.assertRaises(InvalidInput):
                store.save_investigation("CASE-QA3", qid, "evidence-summary",
                                         self._validated(), "bogus-mode")
        finally:
            store.close()

    def test_unknown_template_raises_invalid_input(self):
        store, qid = self._seeded()
        try:
            with self.assertRaises(InvalidInput):
                store.save_investigation("CASE-QA3", qid, "no-such-template",
                                         self._validated(), "replay")
        finally:
            store.close()


class TestBrokerReviewPreservesPriorMeaning(unittest.TestCase):
    """Suspected defect QA-20 (Medium): re-reviewing a broker link overwrites
    its prior relation/applicability/rationale in place, destroying the basis
    that already-staled snapshots cited.

    Trace: CaseStore.review_broker_link (store.py lines 1893-1894) UPDATEs
    the link row, and neither the rights_events marker (lines 1895-1897,
    "re-reviewed" only) nor the broker_invalidated event (lines 1907-1909)
    records the previous values. Source amendments and evidence amendments
    both keep superseded rows; the broker module's own comment states prior
    rows are kept, never overwritten (lines 1607-1609). After a re-review,
    no query can reconstruct what a dependent stale draft was based on.
    """

    def test_original_rationale_survives_rereview(self):
        original = "Fictional QA ORIGINAL rationale ALPHA-7F3K9 for the broker link."
        revised = "Fictional QA revised rationale BETA-2Q8M4 for the broker link record."
        store = CaseStore(":memory:")
        try:
            sid, qid = _seed_case(store)
            rights = store.register_rights_source(
                "QA-SOURCE", "QA owner", "v1", "2026-01-01", {}, None, None)
            link = store.create_broker_link(
                "CASE-QA3", qid, int(rights["rights_source_id"]),
                "context", "limited", original, None, None)
            store.create_snapshot(
                "CASE-QA3", qid, "Fictional QA draft summary text here.", [sid],
                broker_link_ids=[int(link["broker_link_id"])])
            store.review_broker_link(
                "CASE-QA3", int(link["broker_link_id"]),
                "contradicts", "limited", revised)
            surviving_text = []
            surviving_text += [row["rationale"] for row in store.db.execute(
                "SELECT rationale FROM broker_links").fetchall()]
            surviving_text += [row["details"] for row in store.db.execute(
                "SELECT details FROM events").fetchall()]
            surviving_text += [row["reason"] for row in store.db.execute(
                "SELECT reason FROM rights_events").fetchall()]
            self.assertTrue(
                any(original in text for text in surviving_text),
                "original broker-link rationale is unrecoverable after re-review")
        finally:
            store.close()


class TestExportPathRejectsNonIntegerIds(unittest.TestCase):
    """Suspected defect QA-21 (Low): export_markdown accepts non-integer
    snapshot ids via SQLite type coercion (True binds as 1, "1" matches 1).

    Trace: CaseStore.export_markdown (store.py lines 2319-2328) passes
    snapshot_id to SQL with no type check. The QA-08 family names the
    snapshot/question/option-lookup/ack/source/investigation ids and QA-13
    added the task-status id; the export path is not listed in either. The
    POST/GET route is regex-safe (__main__.py line 182 uses ([0-9]+) plus
    int()), so this is a store-contract inconsistency, not a route crash.
    """

    def test_boolean_and_string_snapshot_ids_raise(self):
        store = CaseStore(":memory:")
        try:
            sid, qid = _seed_case(store)
            snap_id = store.create_snapshot(
                "CASE-QA3", qid, "Fictional QA draft summary text here.", [sid])
            control = store.export_markdown("CASE-QA3", snap_id)
            self.assertIn("CASE-QA3", control)  # control: integer id exports
            for bad in (True, "1"):
                with self.subTest(snapshot_id=bad):
                    with self.assertRaises(InvalidInput):
                        store.export_markdown("CASE-QA3", bad)
        finally:
            store.close()


class TestMalformedAbstentionsAreRecorded(unittest.TestCase):
    """Suspected defect QA-22 (Low): malformed model abstentions vanish
    silently instead of being recorded as dropped.

    Trace: validate_output (src/open_intelligence/investigation.py lines
    189-195) appends only well-formed abstentions and ignores the rest,
    while every rejected claim is recorded in dropped (lines 150-188) per
    the module contract "never silently repaired". A payload whose
    abstentions all carry an invalid reason additionally gains a synthetic
    fallback abstention (lines 194-195), masking the malformed output.
    """

    def test_invalid_abstention_reason_is_recorded_as_dropped(self):
        result = validate_output(
            {"claims": [],
             "abstentions": [{"topic": "Fictional QA topic",
                              "reason": "bogus_reason"}]},
            set(), set())
        self.assertEqual(len(result.dropped), 1)


class TestKeptCitationsStoreValidatedFieldsOnly(unittest.TestCase):
    """Suspected defect QA-23 (Low): kept claim citations are stored verbatim,
    so unvalidated extra model-supplied fields reach storage.

    Trace: validate_output (investigation.py lines 181-188) builds a
    normalized kept claim but stores the raw citations list unchanged (line
    185), including any extra keys the model attached beyond type/id. The
    module contract states every claim is validated before storage; only
    the type/id pair is ever checked.
    """

    def test_extra_citation_fields_are_not_stored(self):
        result = validate_output(
            {"claims": [{"text": "Fictional QA claim text.",
                         "support": "context",
                         "citations": [{"type": "source", "id": 1,
                                        "note": "Fictional QA injected note"}],
                         "uncertainty": "low"}],
             "abstentions": []},
            {1}, set())
        self.assertEqual(len(result.claims), 1)  # control: citation resolves
        self.assertLessEqual(set(result.claims[0]["citations"][0]), {"type", "id"})


class TestIncomingBoardRefreshesAfterWrites(unittest.TestCase):
    """Suspected defect QA-24 (Low): the incoming board is rendered once at
    startup and never refreshed, so its per-case counts and recency order go
    stale after any write.

    Trace: web/app.js calls renderIncomingBoard only from initialize (line
    60; definition line 82). The refresh path — refresh (lines 171-185) via
    render (lines 358-568) — rebuilds every other panel but never touches
    #incoming-list, so open-question and stale-draft counts disagree with
    the workspace until a full page reload.
    """

    def test_refresh_path_updates_incoming_board(self):
        app = (ROOT / "web" / "app.js").read_text(encoding="utf-8")
        refresh_src = app[app.index("async function refresh() {"):
                          app.index("function readyCase() {")]
        render_src = app[app.index("function render() {"):
                         app.index("function renderOriginalSource(")]
        self.assertIn("renderIncomingBoard", refresh_src + render_src,
                      "refresh/render never updates the incoming board")


class TestOptionSelectsResetOnCaseSwitch(unittest.TestCase):
    """Suspected defect QA-25 (Low): option-panel target selects preserve the
    prior case's selection across a case switch, unlike every other
    case-relative select.

    Trace: render() guards question-choice and the evidence selects with a
    sameCase check (web/app.js lines 360-366, 441-442), resetting them when
    the case changes. renderOptions' fill helper (lines 939-949) preserves
    select.value unconditionally, so a target id that exists in both cases
    stays selected after the switch and can be submitted with one click —
    compounding the unguarded narrative inputs in open QA-06/SEC-01.
    """

    def test_render_options_consults_case_guard(self):
        app = (ROOT / "web" / "app.js").read_text(encoding="utf-8")
        options_src = app[app.index("function renderOptions() {"):
                          app.index("function renderBibliography(")]
        self.assertTrue("sameCase" in options_src or "renderedCaseId" in options_src,
                        "option-panel selects preserve prior-case targets across switch")


class TestMissionEmptyCaseListLeavesNoLoadingPill(unittest.TestCase):
    """Suspected defect QA-26 (Low): with zero cases, the Patient Mission
    status pill is stuck on "Loading…" forever.

    Trace: web/mission.js refreshMission returns early when the case picker
    is empty (lines 181-182) without setting any status text, so the initial
    "Loading…" pill (line 184 default in markup flow) never resolves to an
    empty-state message, unlike every other mission container which has an
    explicit empty rendering (lines 78, 118, 127, 144).
    """

    def test_empty_picker_sets_status_text(self):
        mission = (ROOT / "web" / "mission.js").read_text(encoding="utf-8")
        start = mission.index("if (!caseId)")
        end = mission.index("const sequence", start)
        self.assertIn("textContent", mission[start:end],
                      "empty case list leaves the mission status pill loading")


class TestPointerLabelRejectsPathForms(unittest.TestCase):
    """Suspected defect QA-27 (Low): the biological-asset pointer-label guard
    rejects only "://" URLs and "/"-rooted paths, so Windows and UNC paths
    are stored as labels.

    Trace: CaseStore.add_biological_asset (store.py lines 1964-1970) accepts
    any 1-200 character label without "://" that does not start with "/",
    while the contract states the label "may not be a URL or filesystem
    path" and no file is ever stored. A Windows path label implies a
    retrievable file that cannot exist.
    """

    def _seed_asset_case(self, store: CaseStore) -> int:
        sid, _ = _seed_case(store)
        return sid

    def test_windows_and_unc_paths_raise(self):
        store = CaseStore(":memory:")
        try:
            sid = self._seed_asset_case(store)
            parent = store.add_biological_asset(
                "CASE-QA3", "QA-BLOCK", "ffpe_block", "QA-EPISODE",
                "2026-01-05", sid)
            slide = store.add_biological_asset(
                "CASE-QA3", "QA-SLIDE", "slide", "QA-EPISODE",
                "2026-01-06", sid, parent_asset_id=parent)
            control = store.add_biological_asset(
                "CASE-QA3", "QA-WSI-OK", "digital_wsi", "QA-EPISODE",
                "2026-01-07", sid, parent_asset_id=slide,
                pointer_label="Fictional QA pointer label")
            self.assertIsInstance(control, int)  # control: plain label passes
            with self.assertRaises(InvalidInput):  # control: URL rejected
                store.add_biological_asset(
                    "CASE-QA3", "QA-WSI-URL", "digital_wsi", "QA-EPISODE",
                    "2026-01-07", sid, parent_asset_id=slide,
                    pointer_label="https://example.com/qa-slide")
            for n, bad in enumerate(("C:\\slides\\qa-slide.svs",
                                     "\\\\QASERVER\\share\\qa-slide")):
                with self.subTest(pointer_label=bad):
                    with self.assertRaises(InvalidInput):
                        store.add_biological_asset(
                            "CASE-QA3", f"QA-WSI-BAD-{n}", "digital_wsi",
                            "QA-EPISODE", "2026-01-07", sid,
                            parent_asset_id=slide, pointer_label=bad)
        finally:
            store.close()


if __name__ == "__main__":
    unittest.main()
