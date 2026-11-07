"""Tests for the deterministic orchestrator (program plan C3).

No live model call is made here: routes are decided against the
ledger state of synthetic cases, writes are stored through the store,
and the roster is read back from the same ledger. A route is decided
before any agent event; a write from a role the route did not assign
is rejected; a write after the assignment's lease has expired is
rejected; a run whose route was never decided is not reproducible.
"""

import json
import unittest
from pathlib import Path

from open_intelligence.agent_writes import (
    WriteContractRejected,
    build_investigation_contract,
    build_route_id,
    check_replay,
)
from open_intelligence.investigation import validate_output
from open_intelligence.orchestrator import (
    AGENT_SCOPE,
    ROUTE_POLICY_VERSION,
    check_assignment,
    decide_route,
    get_route,
    roster,
    route_agents_for_template,
    validate_route_record,
)
from open_intelligence.store import CaseStore, InvalidInput, now_utc


def claim(text="The sources report a finding.", source_id=1):
    return {"text": text, "support": "context",
            "citations": [{"type": "source", "id": source_id}],
            "uncertainty": "moderate", "limits": "Synthetic only."}


def seed_case(store, case_id="CASE-ALPHA"):
    """A fictional case with one imported source and one question."""
    store.add_case(case_id, f"Fictional case {case_id}")
    synthetic = Path(__file__).resolve().parents[1] / "examples" / "synthetic"
    source_id = store.import_report(
        case_id, (synthetic / "alpha-pathology-original.txt").read_bytes()
    )["source_id"]
    question_id = store.add_question(case_id, "What does the source report?")
    return source_id, question_id


def save_run(store, case_id, question_id, source_id, *, model="recorded-replay",
             agent_role="A1", route=True):
    """Save one completed replay investigation, deciding its route first."""
    if route:
        decide_route(store, case_id, "evidence-summary", question_id, "clinician")
    facts = store.investigation_facts(case_id, question_id)
    validated = validate_output(
        {"claims": [claim(source_id=source_id)], "abstentions": []},
        facts["valid_sources"], facts["valid_assessments"])
    validated.model = model
    validated.mode = "replay"
    contract = build_investigation_contract(
        store, case_id, question_id, "evidence-summary", model, facts=facts)
    if agent_role != "A1":
        contract = dict(contract, agentRole=agent_role, agentId=f"agent-{agent_role}")
    run_id = store.save_investigation(
        case_id, question_id, "evidence-summary", validated, "replay",
        write_contract=contract)
    return run_id, contract


def event_ids(store, case_id):
    """(kind -> [event ids]) for a case, in ledger order."""
    rows = store.db.execute(
        "SELECT id, kind FROM events WHERE case_id=? ORDER BY id",
        (case_id,)).fetchall()
    by_kind: dict[str, list[int]] = {}
    for row in rows:
        by_kind.setdefault(str(row[1]), []).append(int(row[0]))
    return by_kind


class RouteDecisionTests(unittest.TestCase):
    def setUp(self):
        self.store = CaseStore(":memory:")
        self.source_id, self.question_id = seed_case(self.store)

    def tearDown(self):
        self.store.close()

    def test_decide_route_records_route_decided_before_any_agent_event(self):
        route = decide_route(self.store, "CASE-ALPHA", "evidence-summary",
                             self.question_id, "clinician")
        self.assertEqual(route["routeId"], build_route_id(
            "CASE-ALPHA", "evidence-summary", self.question_id))
        self.assertEqual(route["templateId"], "evidence-summary")
        self.assertEqual(route["questionId"], self.question_id)
        self.assertEqual(route["agents"], ["A1"])
        self.assertEqual(route["authority"], "clinician")
        self.assertEqual(route["scope"], ["data-integration"])
        self.assertEqual(route["budget"], {"maxModelCalls": 1})
        self.assertEqual(route["policyVersion"], ROUTE_POLICY_VERSION)
        self.assertEqual(route["agents"], route_agents_for_template("evidence-summary"))
        self.assertIsNotNone(route["eventId"])
        stored = get_route(self.store, "CASE-ALPHA", route["routeId"])
        self.assertEqual(stored, route)
        self.assertEqual(
            stored["routeId"], route["routeId"])

    def test_route_policy_assigns_a1_for_every_template(self):
        for template in ("evidence-summary", "timeline-gaps",
                         "evidence-applicability"):
            self.assertEqual(route_agents_for_template(template), ["A1"])

    def test_unknown_template_is_rejected(self):
        with self.assertRaises(InvalidInput):
            decide_route(self.store, "CASE-ALPHA", "no-such-template",
                         self.question_id, "clinician")

    def test_patient_and_auditor_may_not_authorize_a_run(self):
        for authority in ("patient", "auditor"):
            with self.assertRaises(WriteContractRejected) as caught:
                decide_route(self.store, "CASE-ALPHA", "evidence-summary",
                             self.question_id, authority)
            self.assertEqual(caught.exception.reason, "invalid_authority")
        for authority in ("clinician", "operator"):
            route = decide_route(self.store, "CASE-ALPHA", "evidence-summary",
                                 self.question_id, authority)
            self.assertEqual(route["authority"], authority)

    def test_lease_must_be_positive(self):
        for bad_lease in (0, -5, "3600"):
            with self.assertRaises(WriteContractRejected) as caught:
                decide_route(self.store, "CASE-ALPHA", "evidence-summary",
                             self.question_id, "clinician", lease_seconds=bad_lease)
            self.assertEqual(caught.exception.reason, "invalid_route")

    def test_lease_until_is_decided_at_plus_lease(self):
        route = decide_route(self.store, "CASE-ALPHA", "evidence-summary",
                             self.question_id, "clinician",
                             lease_seconds=600, now="2026-11-05T10:00:00+00:00")
        self.assertEqual(route["decidedAt"], "2026-11-05T10:00:00+00:00")
        self.assertEqual(route["leaseUntil"], "2026-11-05T10:10:00+00:00")

    def test_redeciding_supersedes_the_earlier_decision(self):
        first = decide_route(self.store, "CASE-ALPHA", "evidence-summary",
                             self.question_id, "clinician",
                             now="2026-11-05T10:00:00+00:00")
        second = decide_route(self.store, "CASE-ALPHA", "evidence-summary",
                              self.question_id, "operator",
                              now="2026-11-05T10:30:00+00:00")
        self.assertNotEqual(first["eventId"], second["eventId"])
        self.assertEqual(second["authority"], "operator")
        self.assertEqual(
            get_route(self.store, "CASE-ALPHA", first["routeId"]), second)

    def test_route_record_rejects_a_scope_that_is_not_the_roles_dimensions(self):
        route = decide_route(self.store, "CASE-ALPHA", "evidence-summary",
                             self.question_id, "clinician")
        broken = dict(route, scope=["analysis"])
        with self.assertRaises(WriteContractRejected) as caught:
            validate_route_record(broken)
        self.assertEqual(caught.exception.reason, "invalid_route")
        self.assertEqual(caught.exception.field, "scope")

    def test_every_role_has_exactly_one_dimension(self):
        for role, scope in AGENT_SCOPE.items():
            self.assertEqual(len(scope), 1, role)


class AssignmentEnforcementTests(unittest.TestCase):
    def setUp(self):
        self.store = CaseStore(":memory:")
        self.source_id, self.question_id = seed_case(self.store)

    def tearDown(self):
        self.store.close()

    def test_assigned_role_write_is_accepted(self):
        run_id, contract = save_run(
            self.store, "CASE-ALPHA", self.question_id, self.source_id)
        stored = self.store.get_investigation("CASE-ALPHA", run_id)
        self.assertEqual(stored["write_contract"]["agentRole"], "A1")

    def test_unassigned_agent_write_is_rejected(self):
        decide_route(self.store, "CASE-ALPHA", "evidence-summary",
                     self.question_id, "clinician")
        facts = self.store.investigation_facts("CASE-ALPHA", self.question_id)
        validated = validate_output(
            {"claims": [claim(source_id=self.source_id)], "abstentions": []},
            facts["valid_sources"], facts["valid_assessments"])
        validated.model = "recorded-replay"
        validated.mode = "replay"
        contract = build_investigation_contract(
            self.store, "CASE-ALPHA", self.question_id, "evidence-summary",
            "recorded-replay", facts=facts)
        wrong_role = dict(contract, agentRole="A2", agentId="agent-A2")
        with self.assertRaises(WriteContractRejected) as caught:
            self.store.save_investigation(
                "CASE-ALPHA", self.question_id, "evidence-summary", validated,
                "replay", write_contract=wrong_role)
        self.assertEqual(caught.exception.reason, "unassigned_agent")
        self.assertEqual(caught.exception.field, "agentRole")

    def test_write_after_lease_expiry_is_rejected(self):
        # Decided long ago with a one-hour lease: expired by real now.
        decide_route(self.store, "CASE-ALPHA", "evidence-summary",
                     self.question_id, "clinician", lease_seconds=3600,
                     now="2026-01-01T00:00:00+00:00")
        facts = self.store.investigation_facts("CASE-ALPHA", self.question_id)
        validated = validate_output(
            {"claims": [claim(source_id=self.source_id)], "abstentions": []},
            facts["valid_sources"], facts["valid_assessments"])
        validated.model = "recorded-replay"
        validated.mode = "replay"
        contract = build_investigation_contract(
            self.store, "CASE-ALPHA", self.question_id, "evidence-summary",
            "recorded-replay", facts=facts)
        with self.assertRaises(WriteContractRejected) as caught:
            self.store.save_investigation(
                "CASE-ALPHA", self.question_id, "evidence-summary", validated,
                "replay", write_contract=contract)
        self.assertEqual(caught.exception.reason, "lease_expired")

    def test_write_without_any_route_is_allowed_at_save_time(self):
        # Pre-C3 rows: the save does not reject a missing route. The
        # replay is the check that catches it (see ReplayTests below).
        run_id, _ = save_run(
            self.store, "CASE-ALPHA", self.question_id, self.source_id,
            route=False)
        stored = self.store.get_investigation("CASE-ALPHA", run_id)
        self.assertEqual(stored["write_contract"]["agentRole"], "A1")

    def test_route_decided_precedes_the_investigation_event(self):
        run_id, _ = save_run(
            self.store, "CASE-ALPHA", self.question_id, self.source_id)
        ids = event_ids(self.store, "CASE-ALPHA")
        self.assertIn("route.decided", ids)
        self.assertIn("investigation_created", ids)
        self.assertLess(ids["route.decided"][0], ids["investigation_created"][0])

    def test_check_assignment_reports_missing_route(self):
        route_id = build_route_id(
            "CASE-ALPHA", "evidence-summary", self.question_id)
        with self.assertRaises(WriteContractRejected) as caught:
            check_assignment(self.store, "CASE-ALPHA", route_id, "A1")
        self.assertEqual(caught.exception.reason, "missing_route")


class ReplayTests(unittest.TestCase):
    def setUp(self):
        self.store = CaseStore(":memory:")
        self.source_id, self.question_id = seed_case(self.store)

    def tearDown(self):
        self.store.close()

    def test_replay_with_a_decided_route_reproduces_the_run(self):
        run_id, contract = save_run(
            self.store, "CASE-ALPHA", self.question_id, self.source_id)
        result = check_replay(self.store, "CASE-ALPHA", run_id)
        self.assertTrue(result["reproducible"], result)
        self.assertIsNone(result["reason"])
        self.assertEqual(result["routeId"], contract["routeId"])

    def test_replay_without_a_route_decision_fails(self):
        run_id, _ = save_run(
            self.store, "CASE-ALPHA", self.question_id, self.source_id,
            route=False)
        result = check_replay(self.store, "CASE-ALPHA", run_id)
        self.assertFalse(result["reproducible"])
        self.assertEqual(result["reason"], "missing_route")

    def test_replay_with_a_tampered_role_fails(self):
        run_id, contract = save_run(
            self.store, "CASE-ALPHA", self.question_id, self.source_id)
        tampered = dict(contract, agentRole="A3", agentId="agent-A3")
        self.store.db.execute(
            "UPDATE agent_writes SET contract_json=? WHERE investigation_id=?",
            (json.dumps(tampered, sort_keys=True), run_id))
        self.store.db.commit()
        result = check_replay(self.store, "CASE-ALPHA", run_id)
        self.assertFalse(result["reproducible"])
        self.assertEqual(result["reason"], "unassigned_agent")

    def test_replay_does_not_fail_on_an_expired_lease(self):
        # The lease bounds the run's execution window, not the
        # historical record: a run saved under a live lease still
        # replays after the lease lapses. The lapse is simulated by
        # re-deciding the route with an old timestamp, which supersedes
        # the live decision with an expired lease.
        run_id, _ = save_run(
            self.store, "CASE-ALPHA", self.question_id, self.source_id)
        self.assertTrue(check_replay(self.store, "CASE-ALPHA", run_id)["reproducible"])
        decide_route(self.store, "CASE-ALPHA", "evidence-summary",
                     self.question_id, "clinician", lease_seconds=3600,
                     now="2026-01-01T00:00:00+00:00")
        result = check_replay(self.store, "CASE-ALPHA", run_id)
        self.assertTrue(result["reproducible"], result)


class RosterTests(unittest.TestCase):
    def setUp(self):
        self.store = CaseStore(":memory:")
        self.source_id, self.question_id = seed_case(self.store)

    def tearDown(self):
        self.store.close()

    def test_empty_roster_is_all_idle(self):
        result = roster(self.store, "CASE-ALPHA")
        self.assertEqual(result["caseId"], "CASE-ALPHA")
        for role, entry in result["agents"].items():
            self.assertEqual(entry["status"], "idle", role)
            self.assertEqual(entry["assignments"], [])

    def test_decided_route_makes_the_agent_busy(self):
        route = decide_route(self.store, "CASE-ALPHA", "evidence-summary",
                             self.question_id, "clinician")
        result = roster(self.store, "CASE-ALPHA")
        a1 = result["agents"]["A1"]
        self.assertEqual(a1["status"], "busy")
        self.assertEqual(len(a1["assignments"]), 1)
        assignment = a1["assignments"][0]
        self.assertEqual(assignment["routeId"], route["routeId"])
        self.assertEqual(assignment["templateId"], "evidence-summary")
        self.assertEqual(assignment["scope"], ["data-integration"])
        self.assertEqual(assignment["authority"], "clinician")
        for role in ("A2", "A3", "A4", "A5", "A6"):
            self.assertEqual(result["agents"][role]["status"], "idle", role)

    def test_completed_run_makes_the_agent_idle_again(self):
        decide_route(self.store, "CASE-ALPHA", "evidence-summary",
                     self.question_id, "clinician")
        self.assertEqual(roster(self.store, "CASE-ALPHA")["agents"]["A1"]["status"], "busy")
        save_run(self.store, "CASE-ALPHA", self.question_id, self.source_id,
                 route=False)
        self.assertEqual(roster(self.store, "CASE-ALPHA")["agents"]["A1"]["status"], "idle")

    def test_expired_lease_makes_the_agent_idle(self):
        decide_route(self.store, "CASE-ALPHA", "evidence-summary",
                     self.question_id, "clinician", lease_seconds=3600,
                     now="2026-01-01T00:00:00+00:00")
        result = roster(self.store, "CASE-ALPHA")
        self.assertEqual(result["agents"]["A1"]["status"], "idle")

    def test_redeciding_a_completed_route_makes_the_agent_busy_again(self):
        decide_route(self.store, "CASE-ALPHA", "evidence-summary",
                     self.question_id, "clinician")
        save_run(self.store, "CASE-ALPHA", self.question_id, self.source_id,
                 route=False)
        self.assertEqual(roster(self.store, "CASE-ALPHA")["agents"]["A1"]["status"], "idle")
        decide_route(self.store, "CASE-ALPHA", "evidence-summary",
                     self.question_id, "clinician")
        result = roster(self.store, "CASE-ALPHA")
        self.assertEqual(result["agents"]["A1"]["status"], "busy")
        self.assertEqual(len(result["agents"]["A1"]["assignments"]), 1)

    def test_two_routes_keep_the_agent_busy_on_both(self):
        second_question = self.store.add_question("CASE-ALPHA", "Second question?")
        decide_route(self.store, "CASE-ALPHA", "evidence-summary",
                     self.question_id, "clinician")
        decide_route(self.store, "CASE-ALPHA", "timeline-gaps",
                     second_question, "operator")
        result = roster(self.store, "CASE-ALPHA")
        self.assertEqual(result["agents"]["A1"]["status"], "busy")
        self.assertEqual(len(result["agents"]["A1"]["assignments"]), 2)


if __name__ == "__main__":
    unittest.main()
