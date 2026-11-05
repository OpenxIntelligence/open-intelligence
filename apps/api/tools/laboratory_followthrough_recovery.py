"""HTTP assertions used by the disposable FHIR laboratory Compose recovery gate."""
import json


V2 = "application/vnd.open-intelligence.followthrough.v2+json"


class LaboratoryTaskRecovery:
    """Record real write receipts; compare each served database with the original HTTP history."""

    def __init__(self, request, case_path):
        self.request = request
        self.case_path = case_path
        self.list_path = case_path + "/followthrough"
        self.tasks = {}

    def create(self, source, question, fields, key):
        qid = question["question_id"]
        path = self.case_path + "/questions/" + qid + "/followthrough"
        payload = {"synthetic": True, "request_key": key, "title": "Prepare the fictional lab discussion",
                   "owner_label": "Fictional coordinator", "review_trigger": "On source reassessment",
                   "reason": "Record the operational follow-up to this saved observation.",
                   "source_snapshot_contract": "oi.pg-source-world-model/1",
                   "expected_source_snapshot_sha256": fields["expected_source_snapshot_sha256"],
                   "expected_preflight_sha256": fields["expected_preflight_sha256"]}
        status, receipt = self.request(path, payload)
        assert status == 201 and not receipt["duplicate"] and receipt["revision"] == 1
        assert receipt["question_id"] == qid
        tid = receipt["task_id"]
        assert tid not in self.tasks
        self.tasks[tid] = {
            "anchor": {"source_id": source["source_id"], "source_version": source["version"],
                       "source_sha256": source["original_sha256"], "source_line": None,
                       "observation_reference": fields["observation_reference"], "question_id": qid,
                       "source_snapshot_sha256": fields["expected_source_snapshot_sha256"],
                       "preflight_sha256": fields["expected_preflight_sha256"]},
            "writes": [(path, payload, receipt)], "history": None,
        }
        return tid

    def transition(self, tid, state):
        row = self.tasks[tid]
        path = self.list_path + "/" + tid + "/transitions"
        rev = len(row["writes"])
        payload = self.transition_payload(tid, state, rev)
        status, receipt = self.request(path, payload)
        assert status == 201 and not receipt["duplicate"] and receipt["revision"] == rev + 1
        assert receipt["task_id"] == tid and receipt["question_id"] == row["anchor"]["question_id"]
        row["writes"].append((path, payload, receipt))
        row["history"] = None

    @staticmethod
    def transition_payload(tid, state, rev):
        return {"synthetic": True, "request_key": f"{tid}-{state.upper()}-{rev}",
                "expected_revision": rev, "status": state,
                "owner_label": "Fictional follow-up owner" if state == "assigned" else "",
                "reason": "Record the next agreed operational status."}

    def verify_history(self, stale):
        code, old = self.request(self.list_path)
        assert code == 200 and old["contract"] == "oi.pg-question-followthrough/1" and old["tasks"] == []
        code, listing = self.request(self.list_path, accept=V2)
        assert code == 200 and listing["contract"] == "oi.pg-question-followthrough/2"
        assert old["access_receipt_id"] != listing["access_receipt_id"]
        assert not listing["clinical_approval"] and not listing["external_notification_sent"]
        rows = {t["task_id"]: t for t in listing["tasks"]}
        assert len(rows) == len(listing["tasks"]) and rows.keys() == self.tasks.keys()
        for tid, expected in self.tasks.items():
            row = rows[tid]
            assert all(row[k] == v for k, v in expected["anchor"].items())
            assert row["source_context_state"] == (
                "source_reassessment_required" if tid in stale else "current_unreviewed_question")
            assert row["needs_recheck"] is (tid in stale and row["status"] in ("created", "assigned", "acknowledged"))
            assert row["clinical_approval"] is False
            writes = expected["writes"]
            assert row["status"] == writes[-1][1].get("status", "created") and row["revision"] == len(writes)
            events = [(e["event_id"], e["revision"], e["status"], e["reason"]) for e in row["history"]]
            assert events == [(r["event_id"], r["revision"], b.get("status", "created"), b["reason"])
                              for _, b, r in writes]
            assert all(e["actor_label"] == "ACTOR-FHIR-LAB-PROOF" for e in row["history"])
            if expected["history"] is not None:
                assert row["history"] == expected["history"]
            expected["history"] = row["history"]
        return listing["access_receipt_id"]

    def replay(self):
        for task in self.tasks.values():
            for path, payload, saved in task["writes"]:
                assert self.request(path, payload) == (200, {**saved, "duplicate": True})

    def reject_stale(self, tid):
        row = self.tasks[tid]
        path, payload, _ = row["writes"][0]
        assert self.request(path, {**payload, "request_key": "NEW-STALE-LAB-TASK"})[0] == 409
        last_path, last_payload, saved = row["writes"][-1]
        assert last_payload["status"] == "acknowledged"
        assert self.request(last_path, self.transition_payload(tid, "completed", saved["revision"]))[0] == 409

    def verify_storage(self, snapshot):
        expected = {r["event_id"] for task in self.tasks.values() for _, _, r in task["writes"]}
        assert len(snapshot["tasks"]) == len(self.tasks)
        for row in snapshot["tasks"]:
            assert all(row[k] == v for k, v in self.tasks[row["task_id"]]["anchor"].items())
        assert {r["event_id"] for r in snapshot["task_events"]} == expected
        assert len(snapshot["task_audit"]) == len(snapshot["task_events"]) == len(expected)
        assert {r["metadata_json"]["task_event_id"] for r in snapshot["task_audit"]} == expected

    def verify_revoked(self):
        responses = [self.request(self.list_path), self.request(self.list_path, accept=V2)]
        for task in self.tasks.values():
            responses.extend(self.request(path, payload) for path, payload, _ in task["writes"])
        for code, result in responses:
            assert code == 404 and set(result) == {"detail"}
            wire = json.dumps(result)
            for tid, task in self.tasks.items():
                assert all(secret not in wire for secret in (tid, task["anchor"]["question_id"],
                                                            task["anchor"]["observation_reference"]))
