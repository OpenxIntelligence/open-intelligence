"""Actual two-actor HTTP recovery checks for synthetic amendment review."""
import re


class LaboratoryAmendmentRecovery:
    def __init__(self, request, case_path, task_id, question_id, original, reference):
        self.request = request
        self.task_id = task_id
        self.question_id = question_id
        self.original = original
        self.reference = reference
        self.detail = case_path + "/followthrough/" + task_id + "/laboratory-amendment-review"
        self.inbox = case_path + "/laboratory-amendment-requests"
        self.writes = []
        self.last = None

    def read(self):
        status, detail = self.request(self.detail)
        assert status == 200 and detail["contract"] == "oi.laboratory-amendment-review/1"
        assert (detail["task_id"], detail["question_id"], detail["observation_reference"],
                detail["clinical_approval"]) == (self.task_id, self.question_id, self.reference, False)
        assert self.request(self.detail, reviewer=True) == (200, detail)
        original = detail["original"]
        assert (original["source_id"], original["version"], original["sha256"]) == (
            self.original["source_id"], 1, self.original["original_sha256"])
        assert original["observation"]["value_text"] == "4.20"
        return detail

    def exchange(self, latest, value, key):
        detail = self.read()
        assert detail["entries"] == (self.last["entries"] if self.last else [])
        current = detail["latest"]
        assert (current["source_id"], current["version"], current["sha256"], current["document_id"]) == (
            latest["source_id"], latest["version"], latest["original_sha256"], detail["original"]["document_id"])
        assert current["observation"]["value_text"] == value
        ask = {"synthetic": True, "request_key": "ASK-" + key, "action": "request",
               "reason": "Check the saved fictional transcription against its amendment.",
               "expected_latest_source_id": latest["source_id"], "expected_latest_sha256": latest["original_sha256"]}
        assert self.request(self.detail, ask, reviewer=True)[0] == 404
        code, asked = self.request(self.detail, ask)
        assert code == 201 and not asked["duplicate"] and asked["entry_id"] == asked["request_id"]
        rid = asked["request_id"]
        assert re.fullmatch(r"VERIFY-[0-9A-F]{32}", rid)
        assert self.request(self.inbox)[0] == 404
        status, inbox = self.request(self.inbox, reviewer=True)
        assert status == 200 and inbox["contract"] == "oi.laboratory-amendment-inbox/1"
        assert inbox["clinical_approval"] is False and inbox["requests"] == [{
            "request_id": rid, "task_id": self.task_id, "question_id": self.question_id,
            "latest_source_id": latest["source_id"]}]
        reply = {**ask, "request_key": "RESPOND-" + key, "action": "respond", "request_id": rid,
                 "disposition": "transcription_checked", "reason": "I checked these two fictional source versions."}
        assert self.request(self.detail, reply)[0] == 404
        code, answered = self.request(self.detail, reply, reviewer=True)
        assert code == 201 and not answered["duplicate"] and answered["request_id"] == rid
        assert re.fullmatch(r"VERIFY-[0-9A-F]{32}", answered["entry_id"]) and answered["entry_id"] != rid
        after = self.read()
        assert after["original"] == detail["original"] and after["latest"] == current
        assert after["entries"][:-2] == detail["entries"]
        for entry, cmd, receipt, actor in zip(after["entries"][-2:], (ask, reply), (asked, answered),
                ("ACTOR-FHIR-LAB-PROOF", "ACTOR-LAB-INDEPENDENT-REVIEWER"), strict=True):
            assert entry["entry_id"] == receipt["entry_id"] and entry["request_id"] == rid
            assert entry["recorded_at"] and (entry["action"], entry["reason"], entry["disposition"],
                    entry["original_source_id"], entry["latest_source_id"], entry["latest_sha256"], entry["actor"]) == (
                cmd["action"], cmd["reason"], cmd.get("disposition"), self.original["source_id"],
                latest["source_id"], latest["original_sha256"], actor)
        self.writes.extend(((ask, False, asked), (reply, True, answered)))
        self.last = after
        self.verify()

    def verify(self):
        assert self.read() == self.last
        code, inbox = self.request(self.inbox, reviewer=True)
        assert code == 200 and inbox["requests"] == []
        for body, reviewer, saved in self.writes:
            assert self.request(self.detail, body, reviewer=reviewer) == (200, {**saved, "duplicate": True})

    def revoked(self):
        operations = [(self.detail, None, False), (self.inbox, None, True), (self.detail, None, True)]
        operations.extend((self.detail, body, role) for body, role, _ in self.writes)
        for path, payload, reviewer in operations:
            code, response = self.request(path, payload, reviewer=reviewer)
            assert code == 404 and set(response) == {"detail"}

    def receipt(self, original_state, restored):
        rows = restored["amendment_reviews"]
        assert {r["entry_id"] for r in rows} == {r["entry_id"] for _, _, r in self.writes}
        assert len(original_state["amendment_reviews"]) == len(original_state["amendment_review_audit"]) == 2
        assert len(rows) == len(restored["amendment_review_audit"]) == 4
        # Emit source and event identities only. No tokens, original bytes or free-form reasons.
        return {
            "contract": "oi.laboratory-amendment-review-recovery/1",
            "task_id": self.task_id, "question_id": self.question_id,
            "observation_reference": self.reference, "original_source_id": self.original["source_id"],
            "original_source_sha256": self.original["original_sha256"], "clinical_approval": False,
            "original_database_entry_count": len(original_state["amendment_reviews"]),
            "revoked_restore_entry_count": len(rows), "revoked_binding_status": restored["bindings"][0]["status"],
            "entries": [{key: entry[key] for key in ("entry_id", "request_id", "action", "actor",
                        "latest_source_id", "latest_sha256", "disposition")} for entry in self.last["entries"]],
        }
