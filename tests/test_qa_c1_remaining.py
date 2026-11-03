"""Adversarial QA tests for Open Intelligence (inspection-derived, fictional data only).

Each test targets one suspected real defect traced to exact product lines
(see docs/qa-defect-register.md). Each test is written to FAIL on the current
code and PASS once the defect is fixed. Product code is not modified here.

Authorship note: these tests were authored by code-trace inspection only.
The author did not execute them. A reviewer runs the suite.

Run from the repository root (reviewer): PYTHONPATH=src python -m unittest
tests.test_qa_adversarial -v
"""

from __future__ import annotations

import http.client
import re
import sys
import tempfile
import threading
import unittest
from http.server import ThreadingHTTPServer
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "src"))

from open_intelligence import __main__ as oi_main  # noqa: E402
from open_intelligence.changes import changes_since_review  # noqa: E402
from open_intelligence.discovery import (  # noqa: E402
    DiscoveryInputError,
    parse_discovery,
)
from open_intelligence.investigation import (  # noqa: E402
    ValidatedInvestigation,
    validate_output,
)
from open_intelligence.store import CaseStore, InvalidInput  # noqa: E402

REPORT_V1 = (
    "OI-SYNTHETIC-REPORT/1\n"
    "Patient: CASE-QA1\n"
    "Document: QA-DOC\n"
    "Type: pathology\n"
    "Event-Date: 2026-01-05\n"
    "Issued-At: 2026-01-06\n"
    "Specimen: QA-SPECIMEN\n"
    "Finding: qa-finding|reported|Fictional QA note for adversarial testing only.\n"
).encode("utf-8")

EVIDENCE_V1 = (
    "OI-SYNTHETIC-EVIDENCE/1\n"
    "Evidence: QA-EVID\n"
    "Title: Fictional QA evidence example\n"
    "Issued-At: 2026-02-01\n"
    "Rights: original-synthetic\n"
    "Statement: This fictional QA statement is long enough to pass validation checks.\n"
).encode("utf-8")

EVIDENCE_V2 = (
    "OI-SYNTHETIC-EVIDENCE/1\n"
    "Evidence: QA-EVID\n"
    "Title: Fictional QA evidence example\n"
    "Issued-At: 2026-02-02\n"
    "Rights: original-synthetic\n"
    "Amends: QA-EVID@1\n"
    "Statement: This fictional QA statement replaces the earlier version for testing purposes.\n"
).encode("utf-8")

DISCOVERY_TRIAL = (
    "OI-SYNTHETIC-DISCOVERY/1\n"
    "Discovery: QA-DISC\n"
    "Kind: trial\n"
    "Title: Fictional QA trial listing\n"
    "Registry-Id: QA-REGISTRY\n"
    "Issued-At: {issued}\n"
    "Rights: original-synthetic\n"
    "Status: not-verified\n"
    "Summary: This fictional summary is long enough and neutral for QA validation.\n"
)

QUESTION = "Fictional QA question about the test source?"


def _seed_case(store: CaseStore, case_id: str = "CASE-QA1") -> tuple[int, int]:
    store.add_case(case_id, "Fictional QA case")
    report = store.import_report(case_id, REPORT_V1)
    qid = store.add_question(case_id, QUESTION)
    return int(report["source_id"]), int(qid)


def _seed_assessment(store: CaseStore, case_id: str, qid: int) -> tuple[int, int]:
    imported = store.import_synthetic_evidence(EVIDENCE_V1)
    aid = store.assess_synthetic_evidence(
        case_id, qid, int(imported["evidence_version_id"]),
        "context", "limited",
        "Fictional QA rationale for the assessment record.",
    )
    return int(imported["evidence_version_id"]), int(aid)


def _seed_broker_snapshot(store: CaseStore, case_id: str, qid: int, sid: int) -> tuple[int, int, int]:
    rights = store.register_rights_source(
        "QA-SOURCE", "QA owner", "v1", "2026-01-01", {}, None, None)
    link = store.create_broker_link(
        case_id, qid, int(rights["rights_source_id"]),
        "context", "limited",
        "Fictional QA rationale for the broker link record.", None, None)
    snap = store.create_snapshot(
        case_id, qid, "Fictional QA draft summary text here.", [sid],
        broker_link_ids=[int(link["broker_link_id"])])
    return int(rights["rights_source_id"]), int(link["broker_link_id"]), int(snap)



class TestBrokerRevocationReopensDependentOptions(unittest.TestCase):
    """Suspected defect QA-04 (Medium): broker-driven snapshot staleness does
    not reopen dependent options.

    Trace: revoke/correct/review_broker_link stale snapshots via
    _invalidate_broker_source (store.py lines 1642-1665) without calling
    _invalidate_options, unlike the evidence path (lines 1330-1332) and the
    source-amendment path (lines 657-663). An option whose basis snapshot went
    stale through revocation still displays review_state current.
    """

    def test_revoked_rights_reopen_option_on_staled_snapshot(self):
        store = CaseStore(":memory:")
        try:
            sid, qid = _seed_case(store)
            rsid, _, snap_id = _seed_broker_snapshot(store, "CASE-QA1", qid, sid)
            opt_id = store.create_option(
                "CASE-QA1", snap_id, "QA option label",
                "Fictional QA option description text.", "unknown")
            store.revoke_rights_source(rsid, "Fictional QA revocation reason text.")
            snap_state = next(
                s for s in store.state("CASE-QA1")["snapshots"] if s["id"] == snap_id)
            self.assertEqual(snap_state["state"], "stale")  # control: revoke stales
            opt_state = next(
                o for o in store.option_view("CASE-QA1")["options"] if o["id"] == opt_id)
            self.assertEqual(opt_state["review_state"], "needs_review")
        finally:
            store.close()



class TestChangesSinceReviewIncludesBrokerCauses(unittest.TestCase):
    """Suspected defect QA-05 (Medium): changes_since_review omits snapshots
    staled by broker-link review/revocation.

    Trace: changes_since_review (src/open_intelligence/changes.py lines 84-142)
    handles source_imported and evidence_invalidated events only, while
    review_broker_link and revocation emit broker_invalidated with
    invalidated_snapshots (store.py lines 1662, 1907-1909). A reviewer reading
    "what changed" never sees broker-caused staleness or its cause.
    """

    def test_broker_review_staleness_appears_with_cause(self):
        store = CaseStore(":memory:")
        try:
            sid, qid = _seed_case(store)
            _, lid, snap_id = _seed_broker_snapshot(store, "CASE-QA1", qid, sid)
            store.review_broker_link(
                "CASE-QA1", lid, "contradicts", "limited",
                "Fictional QA re-review rationale text here.")
            snap_state = next(
                s for s in store.state("CASE-QA1")["snapshots"] if s["id"] == snap_id)
            self.assertEqual(snap_state["state"], "stale")  # control: review stales
            projection = changes_since_review(store, "CASE-QA1")
            stale_ids = [s["snapshot_id"] for s in projection["stale_investigations"]]
            self.assertIn(snap_id, stale_ids)
        finally:
            store.close()



class TestCitationIdsRejectBooleans(unittest.TestCase):
    """Suspected defect QA-07 (Medium): model citations with boolean ids are
    accepted because isinstance(True, int) is True and True == 1 resolves.

    Trace: validate_output (src/open_intelligence/investigation.py lines
    172-175) checks isinstance(cite["id"], int), while the codebase's strict
    convention is type(x) is int (store.py lines 919-921; __main__.py line
    360). A citation {"type": "source", "id": true} is stored as a kept claim
    against source #1 instead of dropped as unresolved_citation.
    """

    def test_boolean_citation_id_is_dropped(self):
        for cite_type, valid_sources, valid_assessments in (
                ("source", {1}, set()), ("assessment", set(), {1})):
            with self.subTest(cite_type=cite_type):
                result = validate_output(
                    {"claims": [{"text": "Fictional QA claim text.",
                                 "support": "context",
                                 "citations": [{"type": cite_type, "id": True}],
                                 "uncertainty": "low"}],
                     "abstentions": []},
                    valid_sources, valid_assessments)
                self.assertEqual(len(result.claims), 0)
                self.assertEqual(result.dropped[0]["reason"], "unresolved_citation")



class TestSnapshotPathRejectsNonIntegerIds(unittest.TestCase):
    """Suspected defect QA-08 (Low): create_snapshot accepts non-integer
    question ids via SQLite type coercion (True binds as 1, "1" matches 1).

    Trace: create_snapshot (store.py lines 2097-2101) passes question_id to SQL
    with no type check, while sibling endpoints require strict int
    (assess_synthetic_evidence line 1411; link_discovery line 1520;
    investigation_facts lines 2159-2160; route line __main__.py 360). The same
    family covers create_option's snapshot_id (line 890), acknowledge (line
    2143), source_text (line 2313), and get_investigation (line 2203); this
    test pins the representative snapshot path.
    """

    def test_boolean_and_string_question_ids_raise(self):
        store = CaseStore(":memory:")
        try:
            sid, _ = _seed_case(store)
            for bad in (True, "1"):
                with self.subTest(question_id=bad):
                    with self.assertRaises(InvalidInput):
                        store.create_snapshot(
                            "CASE-QA1", bad,
                            "Fictional QA draft summary text here.", [sid])
        finally:
            store.close()



class TestDiscoveryRejectsImpossibleDates(unittest.TestCase):
    """Suspected defect QA-09 (Low): parse_discovery accepts impossible
    calendar dates such as month 13.

    Trace: parse_discovery (src/open_intelligence/discovery.py lines 112-114)
    validates Issued-At with a shape-only regex, while report and evidence
    parsers use valid_date, which rejects non-calendar dates (store.py lines
    41-48, 122-123, 201). Invalid dates are stored and displayed as if real.
    """

    def test_impossible_issued_at_raises(self):
        valid = DISCOVERY_TRIAL.format(issued="2026-01-15").encode("utf-8")
        parsed = parse_discovery(valid)
        self.assertEqual(parsed.issued_at, "2026-01-15")  # control: good date passes
        bad = DISCOVERY_TRIAL.format(issued="2026-13-40").encode("utf-8")
        with self.assertRaises(DiscoveryInputError):
            parse_discovery(bad)



class TestWithdrawSelectRequiresExplicitChoice(unittest.TestCase):
    """Suspected defect QA-10 (Medium): the evidence-withdraw select
    preselects the first current item on first paint, inviting a wrong-target
    global withdrawal.

    Trace: web/app.js populates evidence-withdraw-id with real items and no
    blank option (lines 454-470; select cleared at line 444), while the same
    file states the explicit-selection principle for this exact control after
    an amendment (lines 474-479) and uses an allowEmpty blank for the
    analogous review-snapshot choice (line 951). Withdrawal is global and
    invalidates drafts in every affected case, so an implicit default target
    is destructive. A fix may add a blank option in markup or in the populate
    loop, or default-clear the selection outside the stale-target branch.
    """

    def test_withdraw_select_has_no_implicit_default_target(self):
        html = (ROOT / "web" / "index.html").read_text(encoding="utf-8")
        app = (ROOT / "web" / "app.js").read_text(encoding="utf-8")
        html_blank = re.search(
            r'<select[^>]*id="evidence-withdraw-id"[^>]*>.*?<option\s+value=""',
            html, re.DOTALL) is not None
        loop_start = app.index("for (const item of evidence)")
        branch_start = app.index("if (priorWithdrawTarget)")
        loop = app[loop_start:branch_start]
        js_blank = ("evidence-withdraw-id" in loop
                    and re.search(r"\.value\s*=\s*(\"\"|'')", loop) is not None)
        branch_end = app.index("if (priorEvidenceSource", branch_start)
        outside = app[:branch_start] + app[branch_end:]
        js_clear = ("evidence-withdraw-id" in outside
                    and "selectedIndex = -1" in outside)
        self.assertTrue(html_blank or js_blank or js_clear,
                        "withdraw select preselects a real item on first paint")


if __name__ == "__main__":
    unittest.main()
