"""Use real child processes to verify orderly retained-directory restarts."""
from __future__ import annotations

import json
import os
from pathlib import Path
import signal
import subprocess
import sys
import tempfile
import time
import unittest
from unittest.mock import Mock, patch

from open_intelligence.store import InvalidInput
from tools.imaging.pacsnode_lifecycle_evaluation import acceptance_exit_code

try:
    from tools.imaging import pacsnode_lifecycle_process as process_owner
except ImportError:
    process_owner = None


CHILD_PROGRAM = r'''
import json
import os
from pathlib import Path
import signal
import sys
import time

pid = os.getpid()
mode = Path("mode.txt").read_text().strip()
prior_alive = False
prior = Path("previous-pid.txt")
if prior.exists():
    try:
        os.kill(int(prior.read_text()), 0)
        prior_alive = True
    except ProcessLookupError:
        pass
counter = Path("start-count.txt")
count = int(counter.read_text()) + 1 if counter.exists() else 1
counter.write_text(str(count))
prior.write_text(str(pid))

def record(event, **details):
    with Path("child-events.jsonl").open("a") as stream:
        stream.write(json.dumps(dict(event=event, pid=pid, cwd=str(Path.cwd()),
                                     **details)) + "\n")

def interrupted(signum, frame):
    code = 7 if mode == "nonzero" else 0
    record("sigint", exit_code=code)
    raise SystemExit(code)

signal.signal(signal.SIGINT, signal.SIG_IGN if mode == "ignore" else interrupted)
record("started", count=count, prior_alive=prior_alive)
# The runtime can hide another process's numeric /proc path while exposing
# /proc/self. Publish this child's actual identity only after handlers are ready.
stat = Path("/proc/self/stat").read_text()
start_ticks = int(stat.rsplit(")", 1)[1].split()[19])
ready = Path(f"ready-{pid}.tmp")
ready.write_text(json.dumps({"pid": pid, "start_ticks": start_ticks}))
ready.replace(f"ready-{pid}")
while True:
    time.sleep(0.02)
'''


class PacsProcessTests(unittest.TestCase):
    def setUp(self):
        self.assertIsNotNone(process_owner, "The lifecycle process owner must be implemented")
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.run_directory = self.root / "retained-store"
        self.run_directory.mkdir()
        self.log_directory = self.root / "logs"
        self.log_directory.mkdir()
        self.binary = self.root / "fictional-child"
        self.binary.write_text("#!" + sys.executable + "\n" + CHILD_PROGRAM)
        self.binary.chmod(0o755)
        self.config = b"[server]\nhttp_port = 18042\n# preserve these exact fixture bytes\n"
        (self.run_directory / "config.toml").write_bytes(self.config)
        (self.run_directory / "mode.txt").write_text("normal")
        self.children = []
        self.addCleanup(self.cleanup_children)
        self.wait_patch = patch.object(process_owner, "wait_for_confined_backend",
                                       side_effect=self.wait_for_test_child)
        self.wait_patch.start()
        self.addCleanup(self.wait_patch.stop)

    def cleanup_children(self):
        for child in self.children:
            if child.poll() is None:
                child.kill()
            child.wait(timeout=3)

    def wait_for_test_child(self, process, parent_namespace):
        self.children.append(process)
        deadline = time.monotonic() + 4
        ready = self.run_directory / f"ready-{process.pid}"
        while not ready.is_file():
            if process.poll() is not None:
                raise InvalidInput("Fictional child ended before readiness")
            if time.monotonic() >= deadline:
                raise InvalidInput("Fictional child did not become ready")
            time.sleep(0.01)
        identity = json.loads(ready.read_text())
        if (type(identity.get("pid")) is not int or identity["pid"] != process.pid
                or type(identity.get("start_ticks")) is not int
                or identity["start_ticks"] <= 0):
            raise InvalidInput("Child readiness does not identify the owned process")
        start_ticks = identity["start_ticks"]
        # Explicit test evidence returned by the one allowed readiness boundary.
        # These fabricated network facts are never production confinement proof.
        return {
            "kind": "oi.pacs-network-namespace/1",
            "parent_namespace": parent_namespace,
            "probe_namespace": "net:[202]", "server_namespace": "net:[202]",
            "server_pid": process.pid, "server_start_ticks": start_ticks,
            "server_socket_inodes": [10101, 10102],
            "expected_ports": {"http": 18042, "dicom": 11112},
            "interfaces": [{"name": "lo", "flags": ["UP", "LOOPBACK"],
                            "operstate": "UNKNOWN"}],
            "addresses": [{"interface": "lo", "family": "inet", "local": "127.0.0.1",
                           "prefixlen": 8, "scope": "host"}],
            "routes": [{"interface": "lo", "family": "inet", "type": "local",
                        "destination": "127.0.0.0/8", "table": "local"}],
            "listeners": [{"family": "inet", "address": "0.0.0.0", "port": port,
                           "pid": process.pid, "inode": inode}
                          for port, inode in ((18042, 10101), (11112, 10102))],
        }

    def owner(self, *, mode="normal", stop_timeout=0.25):
        (self.run_directory / "mode.txt").write_text(mode)
        result = process_owner.PacsProcess(
            self.binary, self.run_directory, "net:[101]", self.log_directory,
            stop_timeout=stop_timeout)
        self.addCleanup(result.close)
        return result

    def events(self):
        return [json.loads(line) for line in
                (self.run_directory / "child-events.jsonl").read_text().splitlines()]

    def test_restart_reaps_old_child_before_starting_new_in_retained_directory(self):
        owner = self.owner()
        owner.start()
        original = owner.process
        marker = self.run_directory / "persisted-object.marker"
        marker.write_bytes(b"independently authored retained object")
        receipt = owner.restart()
        replacement = owner.process
        self.assertEqual(original.returncode, 0)
        with self.assertRaises(ChildProcessError):
            os.waitpid(original.pid, os.WNOHANG)
        self.assertIsNone(replacement.poll())
        self.assertNotEqual(replacement.pid, original.pid)
        self.assertTrue(receipt["restart_verified"])
        self.assertEqual(owner.last_evidence["server_pid"], replacement.pid)
        self.assertEqual((self.run_directory / "start-count.txt").read_text(), "2")
        self.assertEqual((self.run_directory / "config.toml").read_bytes(), self.config)
        self.assertEqual(marker.read_bytes(), b"independently authored retained object")
        events = self.events()
        self.assertEqual([event["event"] for event in events], ["started", "sigint", "started"])
        self.assertFalse(events[-1]["prior_alive"])
        self.assertEqual({event["cwd"] for event in events}, {str(self.run_directory)})

    def test_ignored_sigint_times_out_kills_child_and_never_starts_replacement(self):
        owner = self.owner(mode="ignore", stop_timeout=0.15)
        owner.start()
        original = owner.process
        with self.assertRaises(InvalidInput):
            owner.restart()
        self.assertIsNotNone(original.poll())
        self.assertNotEqual(original.returncode, 0)
        self.assertEqual((self.run_directory / "start-count.txt").read_text(), "1")
        self.assertEqual([event["event"] for event in self.events()], ["started"])

    def test_nonzero_sigint_exit_refuses_a_replacement(self):
        owner = self.owner(mode="nonzero")
        owner.start()
        original = owner.process
        with self.assertRaises(InvalidInput):
            owner.restart()
        self.assertEqual(original.returncode, 7)
        self.assertEqual((self.run_directory / "start-count.txt").read_text(), "1")
        self.assertEqual([event["event"] for event in self.events()], ["started", "sigint"])

    def test_changed_config_refuses_restart_without_overwriting_user_change(self):
        owner = self.owner()
        owner.start()
        changed = self.config + b"# deliberately changed after first start\n"
        (self.run_directory / "config.toml").write_bytes(changed)
        with self.assertRaises(InvalidInput):
            owner.restart()
        self.assertEqual((self.run_directory / "start-count.txt").read_text(), "1")
        self.assertEqual((self.run_directory / "config.toml").read_bytes(), changed)

    def test_close_reaps_a_child_that_ignores_sigint(self):
        owner = self.owner(mode="ignore", stop_timeout=0.15)
        owner.start()
        original = owner.process
        owner.close()
        self.assertIsNotNone(original.returncode)
        with self.assertRaises(ChildProcessError):
            os.waitpid(original.pid, os.WNOHANG)
        owner.close()
        self.assertEqual((self.run_directory / "start-count.txt").read_text(), "1")

    def test_readiness_failure_cleans_up_the_spawned_child(self):
        owner = self.owner(mode="ignore", stop_timeout=0.15)

        def fail_after_child_is_running(process, parent_namespace):
            self.wait_for_test_child(process, parent_namespace)
            raise InvalidInput("Readiness observation intentionally unavailable")

        with patch.object(process_owner, "wait_for_confined_backend",
                          side_effect=fail_after_child_is_running):
            with self.assertRaises(InvalidInput):
                owner.start()
        self.assertEqual(len(self.children), 1)
        original = self.children[0]
        self.assertIsNotNone(original.returncode)
        with self.assertRaises(ChildProcessError):
            os.waitpid(original.pid, os.WNOHANG)

    def test_post_kill_wait_timeout_keeps_child_owned_until_cleanup_can_reap(self):
        owner = self.owner(mode="ignore", stop_timeout=0.15)
        owner.start()
        original = owner.process
        # Keep the real child, signals, kill, and final reap. Inject only the
        # bounded wait failure that otherwise cannot be reproduced reliably.
        with patch.object(original, "wait", side_effect=subprocess.TimeoutExpired(
                str(self.binary), 0.15)) as interrupted_wait:
            with self.assertRaises(subprocess.TimeoutExpired):
                owner.restart()
        self.assertEqual(interrupted_wait.call_count, 2)
        self.assertIs(owner.process, original,
                      "A failed reap must not discard the owned process handle")
        self.assertEqual((self.run_directory / "start-count.txt").read_text(), "1")
        owner.close()
        self.assertIsNone(owner.process)
        self.assertIsNotNone(original.returncode)
        with self.assertRaises(ChildProcessError):
            os.waitpid(original.pid, os.WNOHANG)

    def test_corrective_cli_requires_three_restart_receipts_before_accepting(self):
        live_owner = self.owner()
        evidence = live_owner.start()
        for restart_count, expected_exit in ((2, 1), (3, 0)):
            with self.subTest(restart_count=restart_count):
                run_directory = self.root / f"corrective-cli-{restart_count}"
                run_directory.mkdir()
                (run_directory / "config.toml").write_bytes(self.config)
                output = self.root / f"corrective-{restart_count}.json"
                owner = Mock(spec=process_owner.PacsProcess)
                owner.start.return_value = evidence
                owner.process = live_owner.process
                owner.binary_sha256 = "0" * 64
                owner.config_sha256 = "1" * 64
                restart = {
                    "restart_verified": True, "stop_exit_code": 0,
                    "stop_signal": "SIGINT", "old_process_reaped_before_start": True,
                    "old_listeners_absent": True, "binary_sha256": "0" * 64,
                    "config_sha256": "1" * 64, "before": evidence, "after": evidence,
                }
                protocol = {
                    "evaluation_completed": True, "lifecycle_acceptance_passed": True,
                    "immutable_write_checks_required": True,
                    "immutable_write_checks_passed": True,
                    "phases": {}, "acceptance_blockers": [],
                    "restart_observations": [dict(restart) for _ in range(restart_count)],
                }
                argv = ["lifecycle", "--binary", str(self.binary), "--run-directory",
                        str(run_directory), "--parent-namespace", "net:[101]",
                        "--output", str(output), "--immutable-write-checks"]
                # Protocol and network facts are test doubles here; real child
                # ownership is covered separately above. This exercises the
                # CLI's refusal to accept a missing post-conflict restart.
                with patch.object(process_owner, "PacsProcess", return_value=owner), \
                        patch.object(process_owner, "run_lifecycle_evaluation", return_value=protocol), \
                        patch.object(sys, "argv", argv):
                    exit_code = process_owner.main()
                self.assertEqual(exit_code, expected_exit)
                saved = json.loads(output.read_text())
                self.assertEqual(saved["process_restarts_verified"], restart_count == 3)
                self.assertEqual(saved["evaluation_completed"], restart_count == 3)
                owner.close.assert_called_once_with()

    def test_cli_cleanup_failure_saves_partial_receipt_without_losing_primary_failure(self):
        run_directory = self.root / "fresh-cli-directory"
        run_directory.mkdir()
        (run_directory / "config.toml").write_bytes(self.config)
        output = self.root / "lifecycle-receipt.json"
        sentinel = "private_cleanup_error_must_not_escape_in_receipt"
        primary_phases = {"baseline": {"inventory_matches": True,
                                        "objects": {"synthetic-sop": {
                                            "original_bytes_match": True}}}}
        partial = {
            "kind": "oi.pacs-lifecycle/1", "classification": "HOLD_NOT_APPROVED",
            "evaluation_completed": False, "lifecycle_acceptance_passed": False,
            "phases": primary_phases, "restart_observations": [],
            "failure_stage": "after_restart", "failure_type": "InvalidInput",
            "acceptance_blockers": ["lifecycle_evaluation_incomplete"],
        }
        owner = Mock(spec=process_owner.PacsProcess)
        owner.start.return_value = {}
        owner.process = object()
        owner.binary_sha256 = "0" * 64
        owner.config_sha256 = "1" * 64
        owner.close.side_effect = OSError(sentinel)
        argv = ["lifecycle", "--binary", str(self.binary), "--run-directory",
                str(run_directory), "--parent-namespace", "net:[101]",
                "--output", str(output)]
        # This is CLI failure serialization, separate from the real-child
        # process checks above. No positive confinement evidence is claimed.
        with patch.object(process_owner, "PacsProcess", return_value=owner), \
                patch.object(process_owner, "run_lifecycle_evaluation", return_value=partial), \
                patch.object(process_owner, "wait_for_confined_backend", return_value={}), \
                patch.object(sys, "argv", argv):
            exit_code = process_owner.main()
        self.assertEqual(exit_code, 1)
        self.assertTrue(output.is_file())
        saved_text = output.read_text()
        saved = json.loads(saved_text)
        self.assertFalse(saved["evaluation_completed"])
        self.assertFalse(saved["lifecycle_acceptance_passed"])
        self.assertEqual(saved["phases"], primary_phases)
        self.assertEqual(saved["failure_stage"], "after_restart")
        self.assertEqual(saved["failure_type"], "InvalidInput")
        self.assertEqual(saved["cleanup_failure_type"], "OSError")
        self.assertNotIn(sentinel, saved_text)
        owner.close.assert_called_once_with()


class LifecycleExitCodeTests(unittest.TestCase):
    def test_exit_code_distinguishes_accepted_negative_and_incomplete_evidence(self):
        cases = [
            ({"evaluation_completed": True, "lifecycle_acceptance_passed": True}, 0),
            ({"evaluation_completed": True, "lifecycle_acceptance_passed": False}, 2),
            ({"evaluation_completed": False, "lifecycle_acceptance_passed": True}, 1),
            ({"evaluation_completed": False, "lifecycle_acceptance_passed": False}, 1),
            ({"evaluation_completed": 1, "lifecycle_acceptance_passed": True}, 1),
            ({"evaluation_completed": True, "lifecycle_acceptance_passed": "yes"}, 2),
            ({}, 1),
        ]
        for receipt, expected in cases:
            with self.subTest(receipt=receipt):
                self.assertEqual(acceptance_exit_code(receipt), expected)


if __name__ == "__main__":
    unittest.main()
