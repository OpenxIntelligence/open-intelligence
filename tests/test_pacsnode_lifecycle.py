"""Lifecycle acceptance with real source persistence and a bounded HTTP double.

Only the external HTTP boundary is patched. The fictional DICOM parser, MIME
handling, source ledger, restart callback, and source-bound read guard are real.
"""
from __future__ import annotations

from contextlib import redirect_stderr, redirect_stdout
from hashlib import sha256
from io import StringIO
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
from pathlib import Path
import tempfile
from threading import Barrier, Lock, Thread
import unittest
from unittest.mock import patch
from urllib.parse import parse_qs, urlsplit

from open_intelligence.store import CaseStore
from open_intelligence.synthetic_dicom_roundtrip import _unpack, synthetic_dicom_bytes
from tools.imaging import pacsnode_live_probe as pacs

try:
    from tools.imaging import pacsnode_lifecycle_evaluation as lifecycle
except ImportError:
    lifecycle = None


ORIGIN = "http://127.0.0.1:18042"
PRIVATE_ERROR = "PRIVATE_LIFECYCLE_BACKEND_DETAIL_MUST_NOT_ESCAPE"
AMENDMENT = (
    "OI-SYNTHETIC-REPORT/1\nPatient: CASE-ALPHA\n"
    "Document: IMG-ALPHA\nType: imaging\n"
    "Event-Date: 2026-05-17\nIssued-At: 2026-05-19\n"
    "Amends: IMG-ALPHA@1\n"
    "Finding: corrected|reported|Independent fictional restart amendment.\n"
).encode("utf-8")


class StatefulDicomBoundary:
    """Model persistent bytes, duplicate conflicts, and restart failures only."""

    def __init__(self, work_dir, originals, *, conflict="reject", lose_on_restart=False,
                 duplicate_inventory=False, change_source=False, restart_error=False,
                 retrieve_error=False):
        self.work_dir = work_dir
        self.originals = originals
        self.conflict = conflict
        self.lose_on_restart = lose_on_restart
        self.duplicate_inventory = duplicate_inventory
        self.change_source = change_source
        self.restart_error = restart_error
        self.retrieve_error = retrieve_error
        self.stored = {}
        self.posts = []
        self.events = []
        self.restarts = 0
        self.source_snapshots = []

    @staticmethod
    def json_response(value):
        return 200, "application/dicom+json", json.dumps(value).encode("utf-8")

    def request(self, url, *, method="GET", content=None, accept=None,
                content_type=None):
        parsed_url = urlsplit(url)
        if parsed_url.scheme != "http" or parsed_url.netloc != "127.0.0.1:18042":
            raise AssertionError("Offline lifecycle escaped its one explicit origin")
        self.events.append({"method": method, "path": parsed_url.path,
                            "restarts": self.restarts, "post_count": len(self.posts)})
        if self.restarts >= 2:
            raise AssertionError("A superseded source caused HTTP after the second restart")
        if method == "POST" and parsed_url.path == "/wado/studies":
            if not isinstance(content, bytes) or len(content) > 20_000:
                raise AssertionError("Unexpected unbounded STOW fixture")
            incoming = {}
            for data in pacs.multipart_dicom_parts(content_type, content):
                uid = _unpack(data)["sop"]
                if uid in incoming:
                    raise AssertionError("STOW fixture repeats a SOP within one batch")
                incoming[uid] = data
            index = len(self.posts)
            if index >= 3:
                raise AssertionError("Unexpected reseed or extra STOW")
            if index in (0, 1) and incoming != self.originals:
                raise AssertionError("Seed/replay did not use both exact original objects")
            if index == 2:
                first = pacs.SOP_UIDS[0]
                if set(incoming) != {first}:
                    raise AssertionError("Conflict must target only the first original SOP")
                if _unpack(incoming[first])["pixel_sha256"] == _unpack(
                        self.originals[first])["pixel_sha256"]:
                    raise AssertionError("Conflict fixture must actually change pixel bytes")
            self.posts.append(incoming)
            if index == 2 and self.conflict == "reject":
                raise pacs.BackendHTTPError(409)
            self.stored.update(incoming)
            if index == 2 and self.conflict == "write_then_reject":
                raise pacs.BackendHTTPError(409)
            referenced = [{
                "00081150": {"vr": "UI", "Value": ["1.2.840.10008.5.1.4.1.1.2"]},
                "00081155": {"vr": "UI", "Value": [uid]},
            } for uid in incoming]
            return self.json_response({"00081199": {"vr": "SQ", "Value": referenced}})
        if method != "GET" or not self.posts:
            raise AssertionError("Unexpected request before the one initial seed")
        if parsed_url.path == "/wado/studies":
            if parse_qs(parsed_url.query) != {"StudyInstanceUID": [pacs.IMAGE_STUDY_UID]}:
                raise AssertionError("Study query lost its known synthetic scope")
            return self.json_response([
                {"0020000D": {"vr": "UI", "Value": [pacs.IMAGE_STUDY_UID]}}
            ] if self.stored else [])
        prefix = (f"/wado/studies/{pacs.IMAGE_STUDY_UID}/series/"
                  f"{pacs.IMAGE_SERIES_UID}/instances")
        if parsed_url.path == prefix:
            rows = [{
                "0020000D": {"vr": "UI", "Value": [pacs.IMAGE_STUDY_UID]},
                "0020000E": {"vr": "UI", "Value": [pacs.IMAGE_SERIES_UID]},
                "00080018": {"vr": "UI", "Value": [uid]},
            } for uid in self.stored]
            if self.duplicate_inventory and self.restarts == 1 and len(self.posts) == 1:
                rows.append(dict(rows[0]))
            return self.json_response(rows)
        if parsed_url.path.startswith(prefix + "/"):
            if accept != pacs.WADO_ACCEPT:
                raise AssertionError("Lifecycle retrieval omitted explicit transfer syntax")
            uid = parsed_url.path[len(prefix) + 1:]
            if uid not in self.originals:
                raise AssertionError("Unknown SOP requested from fictional boundary")
            if self.retrieve_error and self.restarts == 1:
                raise RuntimeError(PRIVATE_ERROR)
            if uid not in self.stored:
                raise pacs.BackendHTTPError(404)
            media, body = pacs.multipart_body([self.stored[uid]])
            return 200, media, body
        raise AssertionError("Unexpected path in bounded lifecycle protocol")

    def restart(self):
        self.restarts += 1
        self.events.append({"method": "RESTART", "restarts": self.restarts,
                            "post_count": len(self.posts)})
        source_path = self.work_dir / "source.sqlite"
        if not source_path.is_file():
            raise AssertionError("Restart did not preserve the real first-party source database")
        store = CaseStore(source_path)
        try:
            self.source_snapshots.append(store.state("CASE-ALPHA"))
            if self.restarts == 1 and self.change_source:
                store.import_report("CASE-ALPHA", AMENDMENT)
        finally:
            store.close()
        if self.restarts == 1 and self.lose_on_restart:
            self.stored.clear()
        if self.restarts == 1 and self.restart_error:
            raise RuntimeError(PRIVATE_ERROR)
        return {"restart_number": self.restarts, "restart_verified": True}


class ConcurrentDicomServer:
    """Real loopback HTTP boundary with an atomic, controlled test store.

    The barrier is in the HTTP server, proving that both uploads reached it
    before either writer is allowed to decide the winner. This is a test
    oracle only; Rust storage and real-process behavior are verified in CI.
    """
    RACE_UID = "2.25.110026110201000000000000000006"
    IDENTICAL_UID = "2.25.110026110201000000000000000007"

    def __init__(self, work_dir, originals, *, overwrite_race=False,
                 write_then_reject_race=False, lose_after_second_restart=False,
                 duplicate_identical_inventory=False):
        self.work_dir, self.originals = work_dir, originals
        self.stored = {}
        self.restarts = 0
        self.events = []
        self.posts = []
        self.lock = Lock()
        self.barriers = {uid: Barrier(2) for uid in (self.RACE_UID, self.IDENTICAL_UID)}
        self.arrivals = {uid: 0 for uid in self.barriers}
        self.overwrite_race = overwrite_race
        self.write_then_reject_race = write_then_reject_race
        self.lose_after_second_restart = lose_after_second_restart
        self.duplicate_identical_inventory = duplicate_identical_inventory
        owner = self

        class Handler(BaseHTTPRequestHandler):
            def log_message(self, *args):
                pass

            def send_payload(self, status, media, data):
                self.send_response(status)
                self.send_header("Content-Type", media)
                self.send_header("Content-Length", str(len(data)))
                self.end_headers()
                self.wfile.write(data)

            def do_POST(self):
                count = int(self.headers.get("Content-Length", "0"))
                if not 0 < count < 20_000 or self.path != "/wado/studies":
                    self.send_payload(400, "text/plain", b"bounded input required")
                    return
                incoming = {_unpack(data)["sop"]: data for data in
                            pacs.multipart_dicom_parts(self.headers["Content-Type"],
                                                       self.rfile.read(count))}
                with owner.lock:
                    owner.events.append(("POST", self.path, owner.restarts))
                    owner.posts.append(dict(incoming))
                    uid = next(iter(incoming))
                    if len(incoming) == 1 and uid in owner.arrivals:
                        owner.arrivals[uid] += 1
                        barrier = (owner.barriers[uid] if owner.arrivals[uid] <= 2
                                   else None)
                    else:
                        barrier = None
                if barrier is not None:
                    barrier.wait(timeout=5)
                status = 200
                with owner.lock:
                    for uid, data in incoming.items():
                        existing = owner.stored.get(uid)
                        if existing is not None and existing != data:
                            status = 409
                            if uid == owner.RACE_UID and owner.overwrite_race:
                                owner.stored[uid] = data
                                status = 200
                            elif uid == owner.RACE_UID and owner.write_then_reject_race:
                                owner.stored[uid] = data
                            break
                    if status == 200:
                        owner.stored.update(incoming)
                self.send_payload(status, "application/dicom+json", b"{}")

            def do_GET(self):
                parsed = urlsplit(self.path)
                with owner.lock:
                    owner.events.append(("GET", parsed.path, owner.restarts))
                    stored = dict(owner.stored)
                prefix = (f"/wado/studies/{pacs.IMAGE_STUDY_UID}/series/"
                          f"{pacs.IMAGE_SERIES_UID}/instances")
                if parsed.path == "/wado/studies":
                    reply = [{"0020000D": {"vr": "UI", "Value": [pacs.IMAGE_STUDY_UID]}}]
                elif parsed.path == prefix:
                    ids = list(stored)
                    if owner.duplicate_identical_inventory and owner.IDENTICAL_UID in stored:
                        ids.append(owner.IDENTICAL_UID)
                    reply = [{"0020000D": {"vr": "UI", "Value": [pacs.IMAGE_STUDY_UID]},
                              "0020000E": {"vr": "UI", "Value": [pacs.IMAGE_SERIES_UID]},
                              "00080018": {"vr": "UI", "Value": [uid]}} for uid in ids]
                elif parsed.path.startswith(prefix + "/"):
                    uid = parsed.path[len(prefix) + 1:]
                    if uid not in stored:
                        self.send_payload(404, "text/plain", b"missing")
                        return
                    media, body = pacs.multipart_body([stored[uid]])
                    self.send_payload(200, media, body)
                    return
                else:
                    self.send_payload(404, "text/plain", b"unknown")
                    return
                self.send_payload(200, "application/dicom+json", json.dumps(reply).encode())

        self.server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        self.thread = Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        self.origin = f"http://127.0.0.1:{self.server.server_port}"

    def close(self):
        self.server.shutdown()
        self.server.server_close()
        self.thread.join(timeout=5)

    def restart(self):
        self.restarts += 1
        if self.lose_after_second_restart and self.restarts == 2:
            self.stored.pop(self.RACE_UID, None)
        if not (self.work_dir / "source.sqlite").is_file():
            raise AssertionError("Real source ledger was lost")
        return {"restart_number": self.restarts, "restart_verified": True}


class PacsnodeLifecycleTests(unittest.TestCase):
    def setUp(self):
        self.assertIsNotNone(lifecycle, "The lifecycle evaluator must be implemented")
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.work_dir = Path(self.temporary.name)
        self.originals = {
            uid: synthetic_dicom_bytes(study_uid=pacs.IMAGE_STUDY_UID,
                                       series_uid=pacs.IMAGE_SERIES_UID, sop_uid=uid)
            for uid in pacs.SOP_UIDS
        }

    def evaluate(self, *, request_wrapper=None, **options):
        boundary = StatefulDicomBoundary(self.work_dir, self.originals, **options)
        request = boundary.request if request_wrapper is None else request_wrapper(boundary)
        output = StringIO()
        with patch.object(pacs, "_request", side_effect=request), \
                redirect_stdout(output), redirect_stderr(output):
            receipt = lifecycle.run_lifecycle_evaluation(
                ORIGIN, self.work_dir, boundary.restart, originals=self.originals)
        self.assertEqual(receipt["kind"], "oi.pacs-lifecycle/1")
        self.assertEqual(receipt["classification"], "HOLD_NOT_APPROVED")
        self.assertNotIn(PRIVATE_ERROR, json.dumps(receipt) + output.getvalue())
        self.assertNotIn("DICM", json.dumps(receipt))
        return receipt, boundary

    def assert_failed_early_without_reseed(self, receipt, boundary):
        self.assertFalse(receipt["evaluation_completed"])
        self.assertFalse(receipt["lifecycle_acceptance_passed"])
        self.assertEqual(len(boundary.posts), 1)
        self.assertEqual(boundary.restarts, 1)
        self.assertTrue(receipt.get("failure_stage"))
        self.assertTrue(receipt.get("failure_type"))
        self.assertTrue(receipt["phases"]["baseline"]["inventory_matches"])

    def test_restart_is_retrieve_only_before_identical_replay(self):
        receipt, boundary = self.evaluate()
        self.assertTrue(receipt["evaluation_completed"])
        self.assertTrue(receipt["lifecycle_acceptance_passed"])
        self.assertEqual([len(batch) for batch in boundary.posts], [2, 2, 1])
        self.assertEqual(boundary.posts[0], boundary.posts[1])
        self.assertEqual(len(receipt["restart_observations"]), 2)
        between = [event for event in boundary.events
                   if event["restarts"] == 1 and event["post_count"] == 1]
        fetched = {event["path"].rsplit("/", 1)[-1] for event in between
                   if event["method"] == "GET"}
        self.assertTrue(set(pacs.SOP_UIDS).issubset(fetched))
        for phase in ("baseline", "after_restart", "identical_replay"):
            with self.subTest(phase=phase):
                observed = receipt["phases"][phase]
                self.assertTrue(observed["inventory_matches"])
                self.assertEqual(set(observed["objects"]), set(pacs.SOP_UIDS))
                for uid, entry in observed["objects"].items():
                    self.assertTrue(entry["original_bytes_match"])
                    self.assertTrue(entry["pixel_bytes_match"])
                    self.assertTrue(entry["source_bound_read_accepted"])
                    self.assertEqual(entry["returned_dicom_sha256"],
                                     sha256(self.originals[uid]).hexdigest())


    def test_non_conflict_400_does_not_satisfy_explicit_409_contract(self):
        def wrap(boundary):
            def request(url, **kwargs):
                try:
                    return boundary.request(url, **kwargs)
                except pacs.BackendHTTPError as error:
                    if error.status == 409:
                        raise pacs.BackendHTTPError(400) from None
                    raise
            return request

        receipt, _ = self.evaluate(request_wrapper=wrap)
        self.assertFalse(receipt["lifecycle_acceptance_passed"])
        self.assertFalse(receipt["conflicting_sop_rejected_and_original_preserved"])
        self.assertIn("conflicting_sop_not_explicitly_rejected", receipt["acceptance_blockers"])

    def immutable_evaluate(self, **options):
        backend = ConcurrentDicomServer(self.work_dir, self.originals, **options)
        self.addCleanup(backend.close)
        receipt = lifecycle.run_lifecycle_evaluation(
            backend.origin, self.work_dir, backend.restart, originals=self.originals,
            immutable_write_checks=True)
        self.assertNotIn(PRIVATE_ERROR, json.dumps(receipt))
        self.assertNotIn("DICM", json.dumps(receipt))
        self.assertEqual(receipt["classification"], "HOLD_NOT_APPROVED")
        return receipt, backend

    def test_concurrent_immutable_winner_replays_and_post_conflict_restart(self):
        receipt, backend = self.immutable_evaluate()
        self.assertTrue(receipt["evaluation_completed"], receipt)
        self.assertTrue(receipt["lifecycle_acceptance_passed"], receipt)
        self.assertTrue(receipt["immutable_write_checks_required"])
        self.assertTrue(receipt["immutable_write_checks_passed"])
        self.assertTrue(receipt["concurrent_conflicting_uploads_preserved_winner"])
        self.assertTrue(receipt["concurrent_identical_uploads_preserved_inventory"])
        self.assertTrue(receipt["post_conflict_restart_preserved_originals"])
        self.assertEqual(len(receipt["restart_observations"]), 3)
        race = receipt["concurrency"]["new_sop_conflict"]
        self.assertEqual(sorted(r["http_status"] for r in race["uploads"]), [200, 409])
        winner = race["winner_submission_index"]
        self.assertEqual(race["uploads"][winner]["http_status"], 200)
        self.assertEqual(sha256(backend.stored[backend.RACE_UID]).hexdigest(),
                         race["submission_dicom_sha256"][winner])
        self.assertTrue(race["winner_preserved_after_rejection"])
        self.assertTrue(receipt["concurrency"]["conflict_retry"]["originals_preserved_after_rejection"])
        self.assertEqual(receipt["concurrency"]["conflict_retry"]["upload"]["http_status"], 409)
        for group in ("identical_new_sop", "identical_replay"):
            self.assertEqual([r["http_status"] for r in receipt["concurrency"][group]["uploads"]],
                             [200, 200])
        for phase_name in ("after_conflict_retry", "after_concurrent_identical",
                           "after_concurrent_identical_replay", "after_conflicts_restart"):
            phase = receipt["phases"][phase_name]
            self.assertTrue(phase["inventory_matches"])
            for uid, data in self.originals.items():
                self.assertEqual(phase["objects"][uid]["returned_dicom_sha256"],
                                 sha256(data).hexdigest())
            self.assertTrue(all(entry["original_bytes_match"] and entry["pixel_bytes_match"]
                                and entry["source_bound_read_accepted"]
                                for entry in phase["objects"].values()))
        final = receipt["phases"]["after_conflicts_restart"]
        self.assertEqual(final["qido_instance_rows"], 4)
        self.assertEqual(set(final["qido_sop_multiplicity"].values()), {1})
        self.assertTrue(receipt["amendment_refused_after_restart"])
        self.assertEqual(receipt["amendment_http_calls_after_restart"], 0)
        self.assertEqual([e for e in backend.events if e[2] >= 3], [])
        self.assertEqual(backend.arrivals[backend.IDENTICAL_UID], 2)
        self.assertEqual(backend.arrivals[backend.RACE_UID], 5)

    def test_concurrent_double_success_is_not_immutable_acceptance(self):
        receipt, _ = self.immutable_evaluate(overwrite_race=True)
        self.assertFalse(receipt["evaluation_completed"])
        self.assertFalse(receipt["lifecycle_acceptance_passed"])
        self.assertFalse(receipt["immutable_write_checks_passed"])
        self.assertEqual([r["http_status"] for r in
                          receipt["concurrency"]["new_sop_conflict"]["uploads"]], [200, 200])

    def test_concurrent_409_cannot_hide_replaced_winner(self):
        receipt, _ = self.immutable_evaluate(write_then_reject_race=True)
        self.assertFalse(receipt["lifecycle_acceptance_passed"])
        self.assertFalse(receipt["immutable_write_checks_passed"])
        self.assertFalse(receipt["concurrency"]["new_sop_conflict"]["winner_preserved_after_rejection"])
        observed = receipt["phases"]["after_concurrent_conflict"]["objects"][ConcurrentDicomServer.RACE_UID]
        self.assertFalse(observed["original_bytes_match"])
        self.assertFalse(observed["source_bound_read_accepted"])

    def test_conflict_restart_loss_is_not_hidden_by_reupload(self):
        receipt, backend = self.immutable_evaluate(lose_after_second_restart=True)
        self.assertFalse(receipt["evaluation_completed"])
        self.assertFalse(receipt["lifecycle_acceptance_passed"])
        self.assertFalse(receipt["post_conflict_restart_preserved_originals"])
        self.assertEqual(receipt["failure_stage"], "after_conflicts_restart")
        self.assertEqual(backend.restarts, 2)
        self.assertEqual(receipt["phases"]["after_conflicts_restart"]["objects"]
                         [backend.RACE_UID]["http_status"], 404)
        self.assertFalse(any(event[0] == "POST" and event[2] >= 2 for event in backend.events))

    def test_concurrent_identical_duplicate_inventory_fails(self):
        receipt, _ = self.immutable_evaluate(duplicate_identical_inventory=True)
        self.assertFalse(receipt["lifecycle_acceptance_passed"])
        self.assertFalse(receipt["concurrent_identical_uploads_preserved_inventory"])
        self.assertEqual(receipt["phases"]["after_concurrent_identical"]["qido_sop_multiplicity"]
                         [ConcurrentDicomServer.IDENTICAL_UID], 2)

    def test_lost_backend_storage_fails_without_reuploading_originals(self):
        receipt, boundary = self.evaluate(lose_on_restart=True)
        self.assert_failed_early_without_reseed(receipt, boundary)
        self.assertFalse(receipt["phases"]["after_restart"]["inventory_matches"])
        self.assertEqual(boundary.stored, {})

    def test_duplicate_qido_row_cannot_masquerade_as_exact_inventory(self):
        receipt, boundary = self.evaluate(duplicate_inventory=True)
        self.assert_failed_early_without_reseed(receipt, boundary)
        self.assertFalse(receipt["phases"]["after_restart"]["inventory_matches"])
        self.assertEqual(boundary.stored, self.originals)

    def test_source_ledger_change_across_restart_aborts_before_replay(self):
        receipt, boundary = self.evaluate(change_source=True)
        self.assert_failed_early_without_reseed(receipt, boundary)
        self.assertFalse(receipt["source_ledger_unchanged_after_restart"])
        store = CaseStore(self.work_dir / "source.sqlite")
        try:
            sources = store.state("CASE-ALPHA")["sources"]
        finally:
            store.close()
        self.assertEqual([source["state"] for source in sources], ["superseded", "current"])

    def assert_conflict_replaced_and_guard_refused(self, receipt, boundary):
        self.assertTrue(receipt["evaluation_completed"])
        self.assertFalse(receipt["lifecycle_acceptance_passed"])
        self.assertFalse(receipt["conflicting_sop_rejected_and_original_preserved"])
        self.assertIn("conflicting_sop_original_replaced", receipt["acceptance_blockers"])
        first, sibling = pacs.SOP_UIDS
        observations = receipt["phases"]["conflicting_replay"]["objects"]
        self.assertEqual(set(observations), {first, sibling})
        self.assertFalse(observations[first]["original_bytes_match"])
        self.assertFalse(observations[first]["pixel_bytes_match"])
        self.assertFalse(observations[first]["source_bound_read_accepted"])
        self.assertEqual(observations[first]["http_status"], 200)
        self.assertEqual(observations[first]["returned_dicom_sha256"],
                         sha256(boundary.stored[first]).hexdigest())
        self.assertTrue(observations[sibling]["original_bytes_match"])
        self.assertTrue(observations[sibling]["pixel_bytes_match"])
        self.assertTrue(observations[sibling]["source_bound_read_accepted"])
        self.assertEqual(observations[sibling]["returned_dicom_sha256"],
                         sha256(self.originals[sibling]).hexdigest())

    def test_conflicting_overwrite_is_completed_but_not_accepted(self):
        receipt, boundary = self.evaluate(conflict="overwrite")
        self.assert_conflict_replaced_and_guard_refused(receipt, boundary)

    def test_conflict_409_with_originals_preserved_passes_only_lifecycle_gate(self):
        receipt, boundary = self.evaluate(conflict="reject")
        self.assertTrue(receipt["evaluation_completed"])
        self.assertTrue(receipt["lifecycle_acceptance_passed"])
        self.assertTrue(receipt["conflicting_sop_rejected_and_original_preserved"])
        self.assertEqual(receipt["acceptance_blockers"], [])
        self.assertEqual(boundary.stored, self.originals)
        for entry in receipt["phases"]["conflicting_replay"]["objects"].values():
            self.assertTrue(entry["original_bytes_match"])
            self.assertTrue(entry["source_bound_read_accepted"])
        self.assertEqual(receipt["classification"], "HOLD_NOT_APPROVED")

    def test_conflict_409_after_replacement_cannot_hide_lost_original(self):
        receipt, boundary = self.evaluate(conflict="write_then_reject")
        self.assert_conflict_replaced_and_guard_refused(receipt, boundary)

    def test_wrong_case_and_persisted_amendment_refuse_before_http(self):
        receipt, boundary = self.evaluate()
        self.assertTrue(receipt["wrong_case_refused"])
        self.assertEqual(receipt["wrong_case_http_calls"], 0)
        self.assertTrue(receipt["source_ledger_unchanged_after_restart"])
        self.assertTrue(receipt["amendment_refused_after_restart"])
        self.assertEqual(receipt["amendment_http_calls_after_restart"], 0)
        self.assertEqual([event for event in boundary.events
                          if event["restarts"] >= 2 and event["method"] != "RESTART"], [])
        original_sources = boundary.source_snapshots[0]["sources"]
        amended_sources = boundary.source_snapshots[1]["sources"]
        self.assertEqual(len(original_sources), 1)
        self.assertEqual([source["state"] for source in amended_sources],
                         ["superseded", "current"])
        self.assertEqual(amended_sources[0]["id"], original_sources[0]["id"])
        self.assertEqual(amended_sources[0]["sha256"], original_sources[0]["sha256"])

    def test_restart_failure_retains_baseline_without_sensitive_exception_text(self):
        receipt, boundary = self.evaluate(restart_error=True)
        self.assert_failed_early_without_reseed(receipt, boundary)
        self.assertEqual(receipt["failure_type"], "RuntimeError")
        for uid, entry in receipt["phases"]["baseline"]["objects"].items():
            self.assertEqual(entry["returned_dicom_sha256"],
                             sha256(self.originals[uid]).hexdigest())

    def test_retrieval_failure_retains_baseline_and_stops_without_reseed(self):
        receipt, boundary = self.evaluate(retrieve_error=True)
        self.assert_failed_early_without_reseed(receipt, boundary)
        self.assertEqual(receipt["failure_type"], "RuntimeError")

    def test_untrusted_stow_media_type_is_not_copied_into_receipt(self):
        sentinel = "private_lifecycle_media_value_must_not_escape"

        def wrap(boundary):
            def request(url, **kwargs):
                status, media, body = boundary.request(url, **kwargs)
                if kwargs.get("method") == "POST":
                    media = sentinel
                return status, media, body
            return request

        receipt, _ = self.evaluate(request_wrapper=wrap)
        self.assertNotIn(sentinel, json.dumps(receipt))

    def test_unknown_qido_sop_value_is_not_copied_into_failed_receipt(self):
        sentinel = "private_lifecycle_unknown_sop_must_not_escape"

        def wrap(boundary):
            def request(url, **kwargs):
                status, media, body = boundary.request(url, **kwargs)
                if (boundary.restarts == 1 and len(boundary.posts) == 1
                        and urlsplit(url).path.endswith("/instances")):
                    rows = json.loads(body)
                    rows.append({"00080018": {"vr": "UI", "Value": [sentinel]}})
                    body = json.dumps(rows).encode("utf-8")
                return status, media, body
            return request

        receipt, boundary = self.evaluate(request_wrapper=wrap)
        self.assert_failed_early_without_reseed(receipt, boundary)
        self.assertFalse(receipt["phases"]["after_restart"]["inventory_matches"])
        self.assertNotIn(sentinel, json.dumps(receipt))

    def test_qido_failure_after_conflict_retains_both_known_object_observations(self):
        def wrap(boundary):
            def request(url, **kwargs):
                response = boundary.request(url, **kwargs)
                if (len(boundary.posts) == 3
                        and urlsplit(url).path.endswith("/instances")):
                    raise RuntimeError(PRIVATE_ERROR)
                return response
            return request

        receipt, boundary = self.evaluate(conflict="overwrite", request_wrapper=wrap)
        self.assertFalse(receipt["evaluation_completed"])
        self.assertFalse(receipt["lifecycle_acceptance_passed"])
        self.assertEqual(receipt["failure_stage"], "conflicting_replay")
        self.assertEqual(len(boundary.posts), 3)
        self.assertEqual(boundary.restarts, 1)
        first, sibling = pacs.SOP_UIDS
        observed = receipt["phases"]["conflicting_replay"]["objects"]
        self.assertEqual(set(observed), {first, sibling})
        self.assertEqual(observed[first]["http_status"], 200)
        self.assertEqual(observed[first]["returned_dicom_sha256"],
                         sha256(boundary.stored[first]).hexdigest())
        self.assertFalse(observed[first]["original_bytes_match"])
        self.assertFalse(observed[first]["source_bound_read_accepted"])
        self.assertEqual(observed[sibling]["http_status"], 200)
        self.assertEqual(observed[sibling]["returned_dicom_sha256"],
                         sha256(self.originals[sibling]).hexdigest())
        self.assertTrue(observed[sibling]["original_bytes_match"])
        self.assertTrue(observed[sibling]["source_bound_read_accepted"])
        reads = [event for event in boundary.events
                 if event["method"] == "GET" and event.get("post_count") == 3
                 and any(event["path"].endswith("/" + uid) for uid in pacs.SOP_UIDS)]
        self.assertEqual(len(reads), 2)

    def test_conflict_503_after_write_retains_changed_target_and_intact_sibling(self):
        def wrap(boundary):
            def request(url, **kwargs):
                response = boundary.request(url, **kwargs)
                if kwargs.get("method") == "POST" and len(boundary.posts) == 3:
                    raise pacs.BackendHTTPError(503)
                return response
            return request

        receipt, boundary = self.evaluate(conflict="overwrite", request_wrapper=wrap)
        self.assertFalse(receipt["lifecycle_acceptance_passed"])
        self.assertFalse(receipt["conflicting_sop_rejected_and_original_preserved"])
        self.assertEqual(receipt["uploads"]["conflicting_replay"]["http_status"], 503)
        first, sibling = pacs.SOP_UIDS
        observed = receipt["phases"]["conflicting_replay"]["objects"]
        self.assertEqual(set(observed), {first, sibling})
        self.assertEqual(observed[first]["returned_dicom_sha256"],
                         sha256(boundary.stored[first]).hexdigest())
        self.assertFalse(observed[first]["original_bytes_match"])
        self.assertFalse(observed[first]["source_bound_read_accepted"])
        self.assertEqual(observed[sibling]["returned_dicom_sha256"],
                         sha256(self.originals[sibling]).hexdigest())
        self.assertTrue(observed[sibling]["original_bytes_match"])
        self.assertTrue(observed[sibling]["source_bound_read_accepted"])


if __name__ == "__main__":
    unittest.main()
