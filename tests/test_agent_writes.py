"""Tests for the per-agent write contract (program plan section 5.4).

No live model call is made here: contracts are built from the ledger
state of synthetic cases, and replay is checked against that ledger.
A write missing any contract field is rejected with a typed reason;
a stored investigation carries the full contract; a replay either
reproduces the run from {routeId, snapshotAt, toolCall cache} or fails
with a typed reason.
"""

import json
import tempfile
import threading
import unittest
from http.server import ThreadingHTTPServer
from pathlib import Path
from urllib.error import HTTPError
from urllib.request import Request, urlopen

from open_intelligence.__main__ import Handler, seed
from open_intelligence.agent_writes import (
    AGENT_ROLES,
    CONTRACT_FIELDS,
    WriteContractRejected,
    build_investigation_contract,
    build_route_id,
    build_write_contract,
    check_replay,
    parse_route_id,
    validate_write_contract,
)
from open_intelligence.investigation import ValidatedInvestigation, validate_output
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


def save_run(store, case_id, question_id, source_id, *, model="recorded-replay"):
    """Save one completed replay investigation with its contract."""
    facts = store.investigation_facts(case_id, question_id)
    validated = validate_output(
        {"claims": [claim(source_id=source_id)], "abstentions": []},
        facts["valid_sources"], facts["valid_assessments"])
    validated.model = model
    validated.mode = "replay"
    contract = build_investigation_contract(
        store, case_id, question_id, "evidence-summary", model, facts=facts)
    run_id = store.save_investigation(
        case_id, question_id, "evidence-summary", validated, "replay",
        write_contract=contract)
    return run_id, contract


class ContractValidationTests(unittest.TestCase):
    def setUp(self):
        self.store = CaseStore(":memory:")
        self.source_id, self.question_id = seed_case(self.store)
        self.contract = build_investigation_contract(
            self.store, "CASE-ALPHA", self.question_id, "evidence-summary",
            "recorded-replay")

    def tearDown(self):
        self.store.close()

    def test_every_missing_field_is_rejected_with_typed_reason(self):
        for field in CONTRACT_FIELDS:
            broken = {key: value for key, value in self.contract.items() if key != field}
            with self.assertRaises(WriteContractRejected) as caught:
                validate_write_contract(broken)
            self.assertEqual(caught.exception.reason, "missing_field")
            self.assertEqual(caught.exception.field, field)
            # A contract rejection is invalid input at the HTTP layer too.
            self.assertIsInstance(caught.exception, InvalidInput)

    def test_non_object_contract_rejected(self):
        with self.assertRaises(WriteContractRejected) as caught:
            validate_write_contract(["not", "a", "contract"])
        self.assertEqual(caught.exception.reason, "invalid_contract")

    def test_invalid_role_rejected(self):
        broken = dict(self.contract, agentRole="A9")
        with self.assertRaises(WriteContractRejected) as caught:
            validate_write_contract(broken)
        self.assertEqual(caught.exception.reason, "invalid_role")
        self.assertEqual(caught.exception.field, "agentRole")

    def test_every_role_accepts(self):
        for role in sorted(AGENT_ROLES):
            variant = dict(self.contract, agentRole=role, agentId=f"agent-{role}")
            self.assertEqual(validate_write_contract(variant)["agentRole"], role)

    def test_inputs_entry_needs_exactly_one_id_plus_hash(self):
        for bad_inputs in (
            [{"contentHash": "0" * 64}],
            [{"sourceVersionId": 1, "assertionId": 2, "contentHash": "0" * 64}],
            [{"sourceVersionId": "1", "contentHash": "0" * 64}],
            [{"sourceVersionId": 1}],
            [{"sourceVersionId": 1, "contentHash": "not-a-hash"}],
            ["not-a-dict"],
        ):
            broken = dict(self.contract, inputs=bad_inputs)
            with self.assertRaises(WriteContractRejected) as caught:
                validate_write_contract(broken)
            self.assertEqual(caught.exception.reason, "invalid_inputs")

    def test_inputs_may_be_empty_for_an_empty_record(self):
        empty = dict(self.contract, inputs=[])
        self.assertEqual(validate_write_contract(empty)["inputs"], [])

    def test_tool_calls_entry_shape_enforced(self):
        for bad_calls in (
            [{"tool": "t1", "arguments": {}}],
            [{"tool": "", "arguments": {}, "resultHash": "0" * 64}],
            [{"tool": "t1", "arguments": [], "resultHash": "0" * 64}],
            [{"tool": "t1", "arguments": {}, "resultHash": "not-a-hash"}],
            "not-a-list",
        ):
            broken = dict(self.contract, toolCalls=bad_calls)
            with self.assertRaises(WriteContractRejected) as caught:
                validate_write_contract(broken)
            self.assertEqual(caught.exception.reason, "invalid_tool_calls")

    def test_snapshot_must_carry_an_iso_as_of_and_event_anchor(self):
        for bad_snapshot in (
            "2026-11-05",
            {"as_of": "not-a-date", "event_id": None},
            {"as_of": "2026-11-05T10:00:00+00:00", "event_id": "7"},
            {"event_id": None},
        ):
            broken = dict(self.contract, snapshotAt=bad_snapshot)
            with self.assertRaises(WriteContractRejected) as caught:
                validate_write_contract(broken)
            self.assertEqual(caught.exception.reason, "invalid_snapshot")

    def test_normalized_contract_holds_exactly_the_contract_fields(self):
        padded = dict(self.contract, futureField="must not leak through")
        normalized = validate_write_contract(padded)
        self.assertEqual(set(normalized), set(CONTRACT_FIELDS))

    def test_route_id_round_trips(self):
        route_id = build_route_id("CASE-ALPHA", "evidence-summary", self.question_id)
        self.assertEqual(parse_route_id(route_id),
                         ("CASE-ALPHA", "evidence-summary", self.question_id))
        with self.assertRaises(WriteContractRejected):
            parse_route_id("route:CASE-ALPHA:evidence-summary:not-a-number")
        with self.assertRaises(WriteContractRejected):
            parse_route_id("not-a-route")

    def test_write_and_run_ids_are_generated_and_distinct(self):
        first = build_write_contract(
            agent_role="A1", model_id="recorded-replay",
            route_id=build_route_id("CASE-ALPHA", "evidence-summary", self.question_id),
            snapshot_at={"as_of": now_utc(), "event_id": None},
            inputs=[], prompt_version="evidence-summary:1")
        second = build_write_contract(
            agent_role="A1", model_id="recorded-replay",
            route_id=build_route_id("CASE-ALPHA", "evidence-summary", self.question_id),
            snapshot_at={"as_of": now_utc(), "event_id": None},
            inputs=[], prompt_version="evidence-summary:1")
        self.assertNotEqual(first["writeId"], second["writeId"])
        self.assertNotEqual(first["runId"], second["runId"])
        self.assertEqual(first["agentId"], "agent-A1")
        self.assertEqual(first["agentRole"], "A1")


class ContractStorageTests(unittest.TestCase):
    def setUp(self):
        self.store = CaseStore(":memory:")
        self.source_id, self.question_id = seed_case(self.store)

    def tearDown(self):
        self.store.close()

    def test_save_without_contract_is_rejected(self):
        facts = self.store.investigation_facts("CASE-ALPHA", self.question_id)
        validated = validate_output(
            {"claims": [claim(source_id=self.source_id)], "abstentions": []},
            facts["valid_sources"], facts["valid_assessments"])
        validated.model = "recorded-replay"
        validated.mode = "replay"
        with self.assertRaises(WriteContractRejected) as caught:
            self.store.save_investigation(
                "CASE-ALPHA", self.question_id, "evidence-summary", validated, "replay")
        self.assertEqual(caught.exception.reason, "missing_write_contract")

    def test_full_contract_stored_and_returned(self):
        run_id, contract = save_run(
            self.store, "CASE-ALPHA", self.question_id, self.source_id)
        stored = self.store.get_investigation("CASE-ALPHA", run_id)
        self.assertEqual(stored["write_contract"], contract)
        for field in CONTRACT_FIELDS:
            self.assertIn(field, stored["write_contract"])
        self.assertEqual(stored["write_contract"]["agentRole"], "A1")
        self.assertEqual(stored["write_contract"]["modelId"], "recorded-replay")
        self.assertEqual(
            stored["write_contract"]["routeId"],
            build_route_id("CASE-ALPHA", "evidence-summary", self.question_id))
        self.assertEqual(stored["kind"], "hypothesis")
        self.assertEqual(stored["review_state"], "pending")

    def test_list_carries_attribution(self):
        run_id, contract = save_run(
            self.store, "CASE-ALPHA", self.question_id, self.source_id)
        rows = {row["id"]: row for row in self.store.list_investigations("CASE-ALPHA")}
        self.assertEqual(rows[run_id]["write_id"], contract["writeId"])
        self.assertEqual(rows[run_id]["agent_role"], "A1")
        self.assertEqual(rows[run_id]["route_id"], contract["routeId"])

    def test_contract_bound_to_another_route_is_rejected(self):
        other_question = self.store.add_question("CASE-ALPHA", "Another question?")
        facts = self.store.investigation_facts("CASE-ALPHA", self.question_id)
        validated = validate_output(
            {"claims": [claim(source_id=self.source_id)], "abstentions": []},
            facts["valid_sources"], facts["valid_assessments"])
        validated.model = "recorded-replay"
        validated.mode = "replay"
        wrong_route = build_investigation_contract(
            self.store, "CASE-ALPHA", other_question, "evidence-summary",
            "recorded-replay")
        with self.assertRaises(WriteContractRejected) as caught:
            self.store.save_investigation(
                "CASE-ALPHA", self.question_id, "evidence-summary", validated,
                "replay", write_contract=wrong_route)
        self.assertEqual(caught.exception.reason, "route_mismatch")

    def test_contract_with_another_model_is_rejected(self):
        facts = self.store.investigation_facts("CASE-ALPHA", self.question_id)
        validated = validate_output(
            {"claims": [claim(source_id=self.source_id)], "abstentions": []},
            facts["valid_sources"], facts["valid_assessments"])
        validated.model = "recorded-replay"
        validated.mode = "replay"
        wrong_model = build_investigation_contract(
            self.store, "CASE-ALPHA", self.question_id, "evidence-summary",
            "some-other-model")
        with self.assertRaises(WriteContractRejected) as caught:
            self.store.save_investigation(
                "CASE-ALPHA", self.question_id, "evidence-summary", validated,
                "replay", write_contract=wrong_model)
        self.assertEqual(caught.exception.reason, "contract_mismatch")

    def test_legacy_row_without_a_contract_still_reads(self):
        # A pre-slice investigation row, inserted as the old code wrote
        # it (no agent_writes row), must keep reading with a null contract.
        facts = self.store.investigation_facts("CASE-ALPHA", self.question_id)
        validated = validate_output(
            {"claims": [claim(source_id=self.source_id)], "abstentions": []},
            facts["valid_sources"], facts["valid_assessments"])
        validated.model = "recorded-replay"
        validated.mode = "replay"
        with self.store.db:
            self.store.db.execute("BEGIN IMMEDIATE")
            cursor = self.store.db.execute(
                """INSERT INTO investigations
                (case_id,question_id,template,status,mode,model,claims_json,
                abstentions_json,dropped_json,created_at)
                VALUES (?,?,?,?,?,?,?,?,?,?)""",
                ("CASE-ALPHA", self.question_id, "evidence-summary",
                 validated.status, "replay", validated.model,
                 json.dumps(validated.claims), json.dumps(validated.abstentions),
                 json.dumps(validated.dropped), now_utc()))
            legacy_id = int(cursor.lastrowid)
        stored = self.store.get_investigation("CASE-ALPHA", legacy_id)
        self.assertIsNone(stored["write_contract"])
        rows = {row["id"]: row for row in self.store.list_investigations("CASE-ALPHA")}
        self.assertIsNone(rows[legacy_id]["write_id"])
        self.assertIsNone(rows[legacy_id]["agent_role"])
        self.assertIsNone(rows[legacy_id]["route_id"])


class ReplayTests(unittest.TestCase):
    def setUp(self):
        self.store = CaseStore(":memory:")
        self.source_id, self.question_id = seed_case(self.store)
        self.synthetic = Path(__file__).resolve().parents[1] / "examples" / "synthetic"

    def tearDown(self):
        self.store.close()

    def test_replay_reproduces_the_run(self):
        run_id, contract = save_run(
            self.store, "CASE-ALPHA", self.question_id, self.source_id)
        result = check_replay(self.store, "CASE-ALPHA", run_id)
        self.assertTrue(result["reproducible"], result)
        self.assertIsNone(result["reason"])
        self.assertEqual(result["writeId"], contract["writeId"])
        self.assertEqual(result["routeId"], contract["routeId"])
        facts = self.store.investigation_facts("CASE-ALPHA", self.question_id)
        expected_inputs = (
            len({item["source_version_id"] for item in facts["assertions"]})
            + len(facts["assertions"]) + len(facts["assessments"]))
        self.assertEqual(result["checked_inputs"], expected_inputs)
        self.assertEqual(result["claims"], 1)

    def test_stale_snapshot_invalidates_the_replay(self):
        run_id, _ = save_run(
            self.store, "CASE-ALPHA", self.question_id, self.source_id)
        self.assertTrue(check_replay(self.store, "CASE-ALPHA", run_id)["reproducible"])
        self.store.import_report(
            "CASE-ALPHA", (self.synthetic / "alpha-pathology-amended.txt").read_bytes())
        result = check_replay(self.store, "CASE-ALPHA", run_id)
        self.assertFalse(result["reproducible"])
        self.assertEqual(result["reason"], "stale_snapshot")

    def test_new_source_leaves_the_snapshot_replayable_but_marks_it_stale(self):
        # Replay checks the recorded snapshot, not current freshness:
        # a new source does not change the recorded inputs, so the run
        # still reproduces -- while the ledger still marks it stale.
        run_id, _ = save_run(
            self.store, "CASE-ALPHA", self.question_id, self.source_id)
        self.store.import_report(
            "CASE-ALPHA", (self.synthetic / "alpha-imaging.txt").read_bytes())
        result = check_replay(self.store, "CASE-ALPHA", run_id)
        self.assertTrue(result["reproducible"], result)
        self.assertEqual(self.store.get_investigation("CASE-ALPHA", run_id)["stale"], 1)

    def test_tampered_input_hash_invalidates_the_replay(self):
        run_id, _ = save_run(
            self.store, "CASE-ALPHA", self.question_id, self.source_id)
        self.store.db.execute(
            "UPDATE assertions SET quote='Tampered quotation.' WHERE id IN "
            "(SELECT id FROM assertions WHERE case_id=?)", ("CASE-ALPHA",))
        self.store.db.commit()
        result = check_replay(self.store, "CASE-ALPHA", run_id)
        self.assertFalse(result["reproducible"])
        self.assertEqual(result["reason"], "inputs_changed")

    def test_tampered_route_invalidates_the_replay(self):
        run_id, contract = save_run(
            self.store, "CASE-ALPHA", self.question_id, self.source_id)
        other_question = self.store.add_question("CASE-ALPHA", "Another question?")
        tampered = dict(contract, routeId=build_route_id(
            "CASE-ALPHA", "evidence-summary", other_question))
        self.store.db.execute(
            "UPDATE agent_writes SET contract_json=? WHERE investigation_id=?",
            (json.dumps(tampered, sort_keys=True), run_id))
        self.store.db.commit()
        result = check_replay(self.store, "CASE-ALPHA", run_id)
        self.assertFalse(result["reproducible"])
        self.assertEqual(result["reason"], "route_mismatch")

    def test_missing_contract_invalidates_the_replay(self):
        facts = self.store.investigation_facts("CASE-ALPHA", self.question_id)
        validated = validate_output(
            {"claims": [claim(source_id=self.source_id)], "abstentions": []},
            facts["valid_sources"], facts["valid_assessments"])
        validated.model = "recorded-replay"
        validated.mode = "replay"
        with self.store.db:
            self.store.db.execute("BEGIN IMMEDIATE")
            cursor = self.store.db.execute(
                """INSERT INTO investigations
                (case_id,question_id,template,status,mode,model,claims_json,
                abstentions_json,dropped_json,created_at)
                VALUES (?,?,?,?,?,?,?,?,?,?)""",
                ("CASE-ALPHA", self.question_id, "evidence-summary",
                 validated.status, "replay", validated.model,
                 json.dumps(validated.claims), json.dumps(validated.abstentions),
                 json.dumps(validated.dropped), now_utc()))
            legacy_id = int(cursor.lastrowid)
        result = check_replay(self.store, "CASE-ALPHA", legacy_id)
        self.assertFalse(result["reproducible"])
        self.assertEqual(result["reason"], "missing_write_contract")


class HttpWriteContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        cls.path = str(Path(cls.tmp.name) / "server.sqlite")
        seed(cls.path)
        bound_handler = type("BoundHandlerForAgentWrites", (Handler,), {"db_path": cls.path})
        cls.server = ThreadingHTTPServer(("127.0.0.1", 0), bound_handler)
        cls.port = cls.server.server_address[1]
        cls.thread = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.thread.start()

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.server.server_close()
        cls.thread.join(timeout=5)
        cls.tmp.cleanup()

    def request(self, path, data=None):
        values = {"Content-Type": "application/json"} if data is not None else {}
        values["X-Fictional-Actor"] = "FICTIONAL-NAVIGATOR-A"
        request = Request(f"http://127.0.0.1:{self.port}{path}",
                          data=None if data is None else json.dumps(data).encode(),
                          headers=values)
        try:
            with urlopen(request, timeout=10) as response:
                return response.status, json.loads(response.read())
        except HTTPError as err:
            return err.code, json.loads(err.read())

    def test_replay_investigation_carries_the_full_contract(self):
        status, data = self.request("/api/cases/CASE-ALPHA/questions",
                                    {"question": "What do the sources report about this case?"})
        self.assertEqual(status, 201)
        status, data = self.request("/api/cases/CASE-ALPHA/investigations",
                                    {"question_id": data["question_id"],
                                     "template": "evidence-summary", "mode": "replay"})
        self.assertEqual(status, 201, data)
        contract = data["write_contract"]
        for field in CONTRACT_FIELDS:
            self.assertIn(field, contract)
        self.assertEqual(contract["agentRole"], "A1")
        self.assertEqual(contract["modelId"], "recorded-replay")
        self.assertTrue(contract["inputs"])
        self.assertEqual(contract["toolCalls"], [])
        status, listed = self.request("/api/cases/CASE-ALPHA/investigations")
        self.assertEqual(status, 200)
        row = next(item for item in listed["investigations"] if item["id"] == data["id"])
        self.assertEqual(row["write_id"], contract["writeId"])
        self.assertEqual(row["agent_role"], "A1")
        self.assertEqual(row["route_id"], contract["routeId"])


if __name__ == "__main__":
    unittest.main()
