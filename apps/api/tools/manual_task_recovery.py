"""Populated manual-task dependency acceptance on real restored PostgreSQL.

Called by the existing source Compose gate with its actual HTTP, complete-row
snapshot and dump/restore functions. All fixtures are independently fictional.
No model, external service, mock database or second task owner is introduced.
"""
import base64
import hashlib
import json


CASE = "CASE-MANUAL-RECOVERY"
DEPENDENCIES = "coordination.question_followthrough_manual_dependencies"
RAW = b"Independently fictional recovery document.\nMarker pending.\n"
ORIGINAL = (
    "OI-SYNTHETIC-REPORT/1\nPatient: CASE-MANUAL-RECOVERY\nDocument: DOC-TASK-RECOVERY\n"
    "Type: pathology\nEvent-Date: 2026-01-10\nIssued-At: 2026-01-11\n"
    "Specimen: SPECIMEN-TASK-RECOVERY\n"
    "Finding: marker|pending|Independently fictional task source marker.\n"
)


def verify_manual_task_restore(*, request, snapshot, restore, command, ready,
                               credential, save_access, source_database):
    """Prove readable, corrected and revoked dependency states across recovery."""
    credential["actions"] = list(dict.fromkeys(credential["actions"] + [
        "composer_context_read", "question_create", "question_read",
        "followthrough_create", "followthrough_read", "followthrough_update",
    ]))
    save_access()

    def expect(path, body=None, status=200):
        code, value = request(path, body)
        assert code == status, (path, code, value)
        return value

    patient = expect("/v1/patients", {
        "synthetic": True, "request_key": "CREATE-MANUAL-TASK-RECOVERY"}, 201)["patient_id"]
    credential["patient_ids"].append(patient)
    save_access()
    patient_path = "/v1/patients/" + patient
    expect(patient_path + "/case-bindings", {
        "synthetic": True, "case_id": CASE, "source_organization": "ORG-MANUAL-RECOVERY",
        "source_system": "SYS-MANUAL-RECOVERY", "source_subject_ref": "SUBJECT-MANUAL-RECOVERY",
        "review_ref": "REVIEW-MANUAL-RECOVERY"}, 201)
    prefix = patient_path + "/cases/" + CASE
    docs = prefix + "/documents"
    document = expect(docs, {
        "synthetic": True, "filename": "fictional-task-recovery.txt",
        "original_base64": base64.b64encode(RAW).decode(),
        "confirmed_case_id": CASE, "expected_sha256": hashlib.sha256(RAW).hexdigest(),
        "metadata": {"document_id": "DOC-MANUAL-TASK-RECOVERY", "kind": "pathology",
                     "event_date": "2026-01-10", "issued_at": "2026-01-11",
                     "manual_transcription_confirmed": True},
        "findings": [{"key": "marker", "state": "pending", "quote": "Marker pending.", "line": 2}],
    }, 201)
    source = expect(prefix + "/sources", {"synthetic": True, "original_text": ORIGINAL}, 201)
    world = expect(prefix + "/world-model")
    proposal = {
        "synthetic": True, "source_id": source["source_id"], "source_line": 8,
        "question": "Which fictional record details need a new verification discussion?",
        "expected_source_snapshot_sha256": world["snapshot_fingerprint"],
    }
    preflight = expect(prefix + "/composer/source-preflight", proposal)
    question = expect(prefix + "/questions", {
        **proposal, "request_key": "MANUAL-RECOVERY-QUESTION",
        "expected_preflight_sha256": preflight["preflight_sha256"]}, 201)["question_id"]
    question_path = prefix + "/questions/" + question
    selection = expect(docs + "/" + document["source_id"] + "/selections/"
                       + document["annotation_revision_id"] + "/marker")
    reference = {"source_id": document["source_id"],
                 "annotation_revision_id": document["annotation_revision_id"],
                 "selection_key": "marker", "anchor_sha256": selection["anchor_sha256"]}
    context = expect(question_path + "/manual-passages")
    passage_body = {"synthetic": True, "request_key": "MANUAL-RECOVERY-PASSAGES",
                    "expected_context_sha256": context["context_sha256"], "references": [reference]}
    passage = expect(question_path + "/manual-passages", passage_body, 201)
    references_hash = hashlib.sha256(json.dumps(
        [reference], sort_keys=True, ensure_ascii=False, separators=(",", ":")).encode()).hexdigest()
    dependency = {"patient_id": patient, "case_id": CASE, "question_id": question,
                  "revision_id": passage["revision_id"], "references_sha256": references_hash}
    task_bodies, task_ids = {}, {}
    retries = [(question_path + "/manual-passages", passage_body, passage)]
    for label in ("source", "manual"):
        body = {"synthetic": True, "request_key": "MANUAL-RECOVERY-TASK-" + label.upper(),
                "title": "Prepare the fictional " + label + " discussion", "detail": "",
                "owner_label": "", "due_date": None, "review_trigger": "When the source basis changes",
                "reason": "Preserve this independently fictional task basis.",
                "source_snapshot_contract": preflight["source_snapshot_contract"],
                "expected_source_snapshot_sha256": preflight["source_snapshot_sha256"],
                "expected_preflight_sha256": preflight["preflight_sha256"]}
        if label == "manual":
            body["manual_dependency"] = dependency
        receipt = expect(question_path + "/followthrough", body, 201)
        task_ids[label] = receipt["task_id"]
        task_bodies[label] = body
        retries.append((question_path + "/followthrough", body, receipt))
        for revision, state in ((2, "assigned"), (3, "acknowledged")):
            transition_path = prefix + "/followthrough/" + receipt["task_id"] + "/transitions"
            transition = {"synthetic": True, "request_key": label.upper() + "-RECOVERY-" + state.upper(),
                          "expected_revision": revision - 1, "status": state,
                          "owner_label": "Fictional coordinator" if state == "assigned" else "",
                          "reason": "Recorded fictional preparation status."}
            changed = expect(transition_path, transition, 201)
            assert changed["revision"] == revision
            retries.append((transition_path, transition, changed))

    def listing(stale, source_completed=False):
        value = expect(prefix + "/followthrough")
        assert value["synthetic"] is True and value["clinical_approval"] is False
        assert value["external_notification_sent"] is False
        rows = {item["task_id"]: item for item in value["tasks"]}
        assert set(rows) == set(task_ids.values())
        for label, task_id in task_ids.items():
            task = rows[task_id]
            assert task["question_id"] == question
            assert task["source_context_state"] == "current_unreviewed_question", \
                "A stale source would confound the manual-correction acceptance"
            assert task["manual_dependency_revision_id"] == (passage["revision_id"] if label == "manual" else None)
            assert task["manual_context_state"] == (
                ("reassessment_required" if stale else "current_unreviewed") if label == "manual" else None)
            assert task["needs_recheck"] is (stale and label == "manual")
            completed = source_completed and label == "source"
            assert task["status"] == ("completed" if completed else "acknowledged")
            assert task["revision"] == (4 if completed else 3)
            assert [event["status"] for event in task["history"]] == (
                ["created", "assigned", "acknowledged"] + (["completed"] if completed else []))
            assert task["clinical_approval"] is False
        assert "Marker pending." not in json.dumps(value), "Task view disclosed the manual quotation"
        return rows

    def exact_retries(database):
        before = snapshot(database)
        for path, body, receipt in retries:
            assert expect(path, body) == {**receipt, "duplicate": True}, "Recovered command identity changed"
        assert snapshot(database) == before, "Exact retry created a receipt, event or dependency"

    def manual_context(stale):
        packet = expect(question_path + "/manual-passages")
        assert packet["revision_id"] == passage["revision_id"]
        assert packet["state"] == ("reassessment_required" if stale else "current_unreviewed")
        selected, = packet["passages"]
        assert selected["anchor"] == selection["anchor"], "Recovery or correction rewrote the saved anchor"
        assert selected["anchor_sha256"] == reference["anchor_sha256"]
        assert selected["source_state"] == "current"

    original_tasks = listing(False)
    populated = snapshot(source_database)
    dependency_rows = populated["tables"][DEPENDENCIES]
    assert len(dependency_rows) == 1, "Restore fixture needs one explicit, populated dependency"
    stored = dependency_rows[0]
    assert {key: stored[key] for key in dependency} == dependency
    assert stored["task_id"] == task_ids["manual"]
    assert stored["origin_org"] == credential["organization"]

    readable_database = "oi_api_test_manual_tasks_current"
    restored_before = restore(source_database, readable_database)
    assert restored_before == populated
    assert listing(False) == original_tasks, "Restore changed task anchors, timestamps or history"
    manual_context(False)
    exact_retries(readable_database)
    for service in ("api", "db"):
        before = snapshot(readable_database)
        command(["restart", service])
        ready()
        assert snapshot(readable_database) == before
        assert listing(False) == original_tasks
        exact_retries(readable_database)
    assert snapshot(source_database) == populated, "Restored HTTP modified the original database"

    annotation_path = docs + "/" + document["source_id"] + "/annotations"
    correction = {"synthetic": True, "request_key": "MANUAL-RECOVERY-CORRECTION",
                  "confirmed_case_id": CASE, "expected_sha256": hashlib.sha256(RAW).hexdigest(),
                  "expected_revision_id": document["annotation_revision_id"],
                  "reason": "Narrow the independently fictional quotation.",
                  "findings": [{"key": "marker", "state": "indeterminate", "quote": "pending.", "line": 2}]}
    corrected = expect(annotation_path, correction, 201)
    retries.append((annotation_path, correction, corrected))
    corrected_tasks = listing(True)
    for task_id, row in corrected_tasks.items():
        for key in row.keys() - {"manual_context_state", "needs_recheck"}:
            assert row[key] == original_tasks[task_id][key], "Correction rewrote task field " + key
    manual_context(True)

    def completion(label):
        return prefix + "/followthrough/" + task_ids[label] + "/transitions", {
            "synthetic": True, "request_key": label.upper() + "-RECOVERY-COMPLETE",
            "expected_revision": 3, "status": "completed", "owner_label": "",
            "reason": "Attempt to finish the fictional preparation."}

    def stale_denial(database):
        before = snapshot(database)
        path, body = completion("manual")
        denied = expect(path, body, 409)
        assert set(denied) == {"detail"}
        assert snapshot(database) == before, "Rejected stale completion changed durable state"

    stale_denial(readable_database)
    path, body = completion("source")
    completed = expect(path, body, 201)
    retries.append((path, body, completed))
    stale_tasks = listing(True, True)
    stale_database = "oi_api_test_manual_tasks_stale"
    stale_before = restore(readable_database, stale_database)
    assert stale_before["tables"][DEPENDENCIES] == dependency_rows, "Correction rewrote the original dependency"
    assert listing(True, True) == stale_tasks
    manual_context(True)
    stale_denial(stale_database)
    exact_retries(stale_database)
    assert snapshot(source_database) == populated

    # Read/update grants are independent after recovery, including exact retries.
    all_actions = credential["actions"][:]
    for missing, path, body in (
        ("followthrough_read", prefix + "/followthrough", None),
        ("followthrough_update", *completion("manual")),
        ("followthrough_create", question_path + "/followthrough", task_bodies["manual"]),
    ):
        credential["actions"] = [action for action in all_actions if action != missing]
        save_access()
        before = snapshot(stale_database)
        assert set(expect(path, body, 404)) == {"detail"}
        assert snapshot(stale_database) == before
    credential["actions"] = all_actions
    save_access()
    # Quote-free task freshness remains available without original-read access.
    credential["actions"] = [action for action in all_actions if action != "source_original_read"]
    save_access()
    assert listing(True, True) == stale_tasks
    credential["actions"] = all_actions
    save_access()
    revoked = expect(patient_path + "/case-bindings/" + CASE + "/revoke", {
        "synthetic": True, "reason": "Withdraw the fictional recovered task binding."})
    assert revoked["duplicate"] is False
    revoked_database = "oi_api_test_manual_tasks_revoked"
    revoked_before = restore(stale_database, revoked_database)
    assert revoked_before["tables"][DEPENDENCIES] == dependency_rows
    for path, body in ((prefix + "/followthrough", None),
                       (question_path + "/followthrough", task_bodies["manual"]),
                       completion("manual"), (question_path + "/manual-passages", None)):
        assert set(expect(path, body, 404)) == {"detail"}
    assert snapshot(revoked_database) == revoked_before, "Restored revoked binding permitted effects"
    assert snapshot(source_database) == populated
    print("PASS MANUAL TASK RECOVERY: populated exact dependency and source-only control; "
          "readable restore and API/DB restart; correction after restore selectively blocks completion; "
          "stale restore, exact retries, independent grants and revoked-binding restore; no clinical approval.")
    return {"contract": "oi.manual-task-recovery/1", "synthetic": True,
            "patient_id": patient, "case_id": CASE, "question_id": question,
            "task_ids": task_ids, "manual_revision_id": passage["revision_id"],
            "references_sha256": references_hash, "dependency_rows": 1,
            "readable_restore": True, "restored_api_db_restart": True,
            "post_restore_correction": True, "unrelated_source_task_completed": True,
            "stale_completion_denied_without_effects": True, "stale_restore": True,
            "exact_retry_commands": len(retries), "independent_grant_denials": 3,
            "revoked_binding_restore": True, "original_database_unchanged": True,
            "clinical_approval": False}
