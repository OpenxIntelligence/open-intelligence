"""Independent synthetic receiving store and replay checks."""
from concurrent.futures import ThreadPoolExecutor
from contextlib import closing
from pathlib import Path
import json
import os
import signal
import sqlite3
import subprocess
import sys
import tempfile
import threading
import unittest
from unittest.mock import patch

from oi_api import encounter_relay as relay

PATIENT = "PAT-" + "A" * 32
SCHEDULED = "clinical_encounter_scheduled"
CHANGED = "clinical_encounter_state_changed"
NOTE = "clinical_note_draft_saved"
RECEIPT = "ACCESS-" + "B" * 32


def event(index, kind=SCHEDULED):
    return dict(id=index, event_type=kind, occurred_at="2026-11-05T16:00:00+00:00",
                encounter_id=3, encounter_revision=None if kind == NOTE else (1 if kind == SCHEDULED else 2),
                note_key="NOTE-ONE" if kind == NOTE else None, note_version=1 if kind == NOTE else None)


def page(*events, **overrides):
    return dict(dict(patient_id=PATIENT, events=list(events), has_more=False,
                     resume_after_id=events[-1]["id"] if events else 0, access_receipt_id=RECEIPT), **overrides)


class ReceiverTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.db = Path(self.temp.name) / "activity.sqlite"

    def deliver(self, response, **options):
        with patch.object(relay, "read_page", return_value=response) as read:
            result = relay.receive_once(self.db, options.get("port", 8000), options.get("patient", PATIENT),
                                        lambda: "t" * 32)
        return result, read.call_args.args[-1]

    def test_page_restart_overlap_and_idle(self):
        first = self.deliver(page(event(3), event(7, CHANGED)))[0]
        self.assertEqual((first["applied"], first["counts"]), (2, {SCHEDULED: 1, CHANGED: 1}))
        later, requested_after = self.deliver(page(event(7, CHANGED), event(11, NOTE)))
        self.assertEqual((later["applied"], requested_after), (1, 6))
        idle = self.deliver(page(event(11, NOTE)))[0]
        self.assertEqual((idle["applied"], idle["counts"]), (0, {SCHEDULED: 1, CHANGED: 1, NOTE: 1}))
        self.assertEqual(os.stat(self.db).st_mode & 0o777, 0o600)
        with closing(sqlite3.connect(self.db)) as db:
            self.assertEqual(db.execute("SELECT DISTINCT access_receipt FROM activity_receipts").fetchall(), [(RECEIPT,)])
        self.assertNotIn(b"NOTE-ONE", self.db.read_bytes())

    def test_wrong_scope_and_malformed_pages_leave_receipts_intact(self):
        self.deliver(page(event(3)))
        for invalid in [page(), page(event(7)), page(event(3), event(3)), page(event(3), event(2)),
                        page(event(3), patient_id="PAT-" + "F"*32), page(event(3), resume_after_id=4),
                        page(event(3), access_receipt_id="unverified"), page(event(3), has_more=True),
                        page(event(3, CHANGED)), page(event(3), dict(event(7), body="private")),
                        page(event(3), dict(event(7), id=True)), page(event(3), dict(event(7), encounter_revision=None)),
                        page(event(3), dict(event(7), occurred_at="yesterday")),
                        page(event(3), dict(event(7, NOTE), note_key=None))]:
            with self.subTest(invalid=invalid), self.assertRaises(ValueError):
                self.deliver(invalid)
        for options in [{"port":8001}, {"patient":"PAT-" + "F"*32}]:
            with self.subTest(options=options), self.assertRaises(ValueError):
                self.deliver(page(), **options)
        self.assertEqual(self.deliver(page(event(3)))[0]["counts"], {SCHEDULED: 1})

    def test_repeat_delivery_from_two_process_connections(self):
        barrier = threading.Barrier(2)
        def fetch(*_):
            barrier.wait(timeout=5)
            return page(event(1), event(2, NOTE))
        # Scope already exists; both callers fetch the same starting position.
        self.deliver(page())
        with patch.object(relay, "read_page", side_effect=fetch), ThreadPoolExecutor(max_workers=2) as pool:
            results = list(pool.map(lambda _: relay.receive_once(self.db, 8000, PATIENT, lambda:"t"*32), range(2)))
        self.assertEqual(sorted(r["applied"] for r in results), [0, 2])
        self.assertEqual(self.deliver(page(event(2, NOTE)))[0]["counts"], {SCHEDULED: 1, NOTE: 1})

    def test_concurrent_divergent_page_cannot_omit_an_already_received_event(self):
        self.deliver(page(event(3)))
        waiting, release = threading.Event(), threading.Event()
        def fetch(*_):
            if threading.current_thread() is threading.main_thread():
                return page(event(3), event(6, NOTE))
            waiting.set()
            if not release.wait(5):
                raise TimeoutError()
            return page(event(3), event(8))
        with patch.object(relay, "read_page", side_effect=fetch), ThreadPoolExecutor(max_workers=1) as pool:
            task = pool.submit(relay.receive_once, self.db, 8000, PATIENT, lambda: "t"*32)
            try:
                self.assertTrue(waiting.wait(5))
                relay.receive_once(self.db, 8000, PATIENT, lambda: "t"*32)
            finally:
                release.set()
            with self.assertRaisesRegex(ValueError, "omitted"):
                task.result()
        self.assertEqual(self.deliver(page(event(6, NOTE)))[0]["counts"], {SCHEDULED: 1, NOTE: 1})

    def test_pages_with_journal_gaps_advance_at_the_25_item_limit(self):
        changes = [event(i * 3) for i in range(1, 31)]
        first = self.deliver(page(*changes[:25], has_more=True))[0]
        last, requested_after = self.deliver(page(*changes[24:]))
        self.assertTrue(first["has_more"])
        self.assertEqual((requested_after, last["applied"], last["counts"]), (74, 5, {SCHEDULED: 30}))

    def test_restore_replays_from_saved_position_and_detects_a_rewound_source(self):
        self.deliver(page(event(3)))
        restored = Path(self.temp.name) / "restored.sqlite"
        restored.touch(mode=0o600)
        with closing(sqlite3.connect(self.db)) as source, closing(sqlite3.connect(restored)) as target:
            source.backup(target)
        later = page(event(3), event(7, NOTE))
        expected = self.deliver(later)[0]
        self.db = restored
        self.assertEqual(self.deliver(later)[0], expected)
        with self.assertRaisesRegex(ValueError, "checkpoint"):
            self.deliver(page(resume_after_id=6))
        self.assertEqual(self.deliver(page(event(7, NOTE)))[0]["applied"], 0)


def interrupt_receiver(database, patient, port, token_file):
    """Kill the real command before its second new receipt, inside the page transaction."""
    env = dict(os.environ, PYTHONPATH=os.pathsep.join(sys.path))
    return subprocess.run(
        [sys.executable, __file__, "--patient", patient, "--port", str(port),
         "--database", str(database), "--token-file", str(token_file)],
        env=env, timeout=15, capture_output=True,
    )


class RelayHTTPTests(unittest.TestCase):
    def setUp(self):
        from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.token = Path(self.temp.name) / "token"
        self.token.write_text("t" * 32)
        self.db = Path(self.temp.name) / "activity.sqlite"
        self.document = page(event(5))
        self.status = 200
        self.requests = []
        fixture = self

        class Handler(BaseHTTPRequestHandler):
            def do_GET(self):
                fixture.requests.append((self.path, self.headers.get("Authorization")))
                self.send_response(fixture.status)
                self.send_header("Content-Type", "application/json")
                if fixture.status == 302:
                    self.send_header("Location", "/redirect-target")
                self.end_headers()
                self.wfile.write(json.dumps(fixture.document).encode())

            def log_message(self, *_):
                pass

        server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        self.addCleanup(server.server_close)
        self.port = server.server_port
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        self.addCleanup(thread.join, 5)
        self.addCleanup(server.shutdown)

    def run_cli(self, *args):
        return subprocess.run(
            [sys.executable, "-m", "oi_api.encounter_relay", "--patient", PATIENT, "--port", str(self.port),
             "--database", str(self.db), "--token-file", str(self.token), *args],
            text=True, capture_output=True, timeout=10,
        )

    def test_operational_inbox_cli_acknowledges_an_exact_draft_only_with_current_access(self):
        self.document = page(event(5, NOTE))
        result = self.run_cli("--pending-drafts-after", "0")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(json.loads(result.stdout)["pending_drafts"][0]["event_id"], 5)
        self.status = 403
        denied = self.run_cli("--acknowledge-draft-event", "5")
        self.assertEqual((denied.returncode, json.loads(denied.stdout)), (2, {"status": "unavailable"}))
        self.status = 200
        self.assertEqual(json.loads(self.run_cli("--pending-drafts-after", "0").stdout)["pending_drafts"][0]["event_id"], 5)
        self.assertEqual(json.loads(self.run_cli("--acknowledge-draft-event", "5").stdout)["acknowledged_event"], 5)
        self.assertEqual(json.loads(self.run_cli("--pending-drafts-after", "0").stdout)["pending_drafts"], [])
        self.document = page(event(5, NOTE), dict(event(9, NOTE), note_version=2))
        stale = self.run_cli("--acknowledge-draft-event", "5")
        self.assertEqual((stale.returncode, json.loads(stale.stdout)["status"]), (3, "superseded_or_unknown"))

    def test_mid_page_process_kill_replays_once(self):
        self.assertEqual(self.run_cli().returncode, 0)
        self.document = page(event(5), event(6, CHANGED), event(9, NOTE))
        killed = interrupt_receiver(self.db, PATIENT, self.port, self.token)
        self.assertEqual(killed.returncode, -signal.SIGKILL, killed.stderr)
        with closing(sqlite3.connect(self.db)) as db:
            self.assertEqual(db.execute("SELECT count(*) FROM activity_receipts").fetchone(), (1,))
            self.assertEqual(db.execute("SELECT sum(total) FROM activity_totals").fetchone(), (1,))
        recovered = json.loads(self.run_cli().stdout)
        self.assertEqual((recovered["applied"], sum(recovered["counts"].values())), (2, 3))
        self.assertTrue(self.requests[-1][0].endswith("after_id=4"))

    def test_cli_uses_authorized_loopback_page_and_withholds_totals_after_denial(self):
        for status, expected_code in ((200, 0), (302, 2), (403, 2), (200, 0)):
            self.status = status
            process = self.run_cli()
            self.assertEqual(process.returncode, expected_code, process.stderr)
            body = json.loads(process.stdout)
            if status == 200:
                self.assertEqual(body["counts"], {SCHEDULED: 1})
            else:
                self.assertEqual(body, {"status": "unavailable"})
        self.assertEqual(len(self.requests), 4)
        self.assertTrue(all(path.startswith("/v1/patients/" + PATIENT + "/encounters/events?")
                            and auth == "Bearer " + "t"*32 for path, auth in self.requests))
        self.assertNotIn(b"t"*32, self.db.read_bytes())


if __name__ == "__main__":
    connect = sqlite3.connect

    def interrupting_connection(*args, **kwargs):
        db = connect(*args, **kwargs)
        inserts = 0

        def interrupt_second_insert():
            nonlocal inserts
            inserts += 1
            if inserts == 2:
                os.kill(os.getpid(), signal.SIGKILL)
            return 0

        db.create_function("interrupt_second_insert", 0, interrupt_second_insert)
        db.execute("""CREATE TEMP TRIGGER interrupt BEFORE INSERT ON activity_receipts
                      BEGIN SELECT interrupt_second_insert(); END""")
        return db

    with patch.object(relay.sqlite3, "connect", interrupting_connection):
        raise SystemExit(relay.main())
