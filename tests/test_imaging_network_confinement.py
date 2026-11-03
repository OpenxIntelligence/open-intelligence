"""Network-boundary evidence tests; fictional socket processes and no patient data."""
from __future__ import annotations

import importlib
import json
import os
from pathlib import Path
import shutil
import signal
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[1]


def fictional_evidence():
    """Hand-authored facts for an isolated namespace, not a live-run receipt."""
    return {
        "kind": "oi.pacs-network-namespace/1",
        "parent_namespace": "net:[101]",
        "probe_namespace": "net:[202]",
        "server_namespace": "net:[202]",
        "server_pid": 500,
        "server_start_ticks": 12345,
        "server_socket_inodes": [7001, 7002],
        "expected_ports": {"http": 18042, "dicom": 11112},
        "interfaces": [{"name": "lo", "flags": ["LOOPBACK", "UP", "LOWER_UP"],
                        "operstate": "UNKNOWN"}],
        "addresses": [
            {"interface": "lo", "family": "inet", "local": "127.0.0.1",
             "prefixlen": 8, "scope": "host"},
            {"interface": "lo", "family": "inet6", "local": "::1",
             "prefixlen": 128, "scope": "host"},
        ],
        "routes": [
            {"family": "inet", "type": "local", "destination": "127.0.0.0/8",
             "interface": "lo", "table": "local"},
            {"family": "inet", "type": "broadcast", "destination": "127.255.255.255",
             "interface": "lo", "table": "local"},
            {"family": "inet6", "type": "local", "destination": "::1",
             "interface": "lo", "table": "local"},
        ],
        "listeners": [
            {"family": "inet", "address": "0.0.0.0", "port": 18042,
             "pid": 500, "inode": 7001},
            {"family": "inet", "address": "0.0.0.0", "port": 11112,
             "pid": 500, "inode": 7002},
        ],
        "namespace_confined": False,
    }


class NetworkConfinementTests(unittest.TestCase):
    def setUp(self):
        try:
            self.module = importlib.import_module("tools.imaging.network_confinement")
        except ModuleNotFoundError:
            self.fail("The network-confinement boundary has not been implemented")

    def check(self, data):
        return self.module.network_evidence_is_confined(data)

    def test_wildcard_sockets_are_confined_by_namespace_facts(self):
        self.assertTrue(self.check(fictional_evidence()))

    def test_claimed_boolean_cannot_replace_missing_facts(self):
        self.assertFalse(self.check({"namespace_confined": True}))
        for field in fictional_evidence():
            if field == "namespace_confined":
                continue
            candidate = fictional_evidence()
            del candidate[field]
            candidate["namespace_confined"] = True
            with self.subTest(field=field):
                self.assertFalse(self.check(candidate))

    def test_reused_parent_or_different_server_namespace_is_not_confined(self):
        for field, value in (
            ("parent_namespace", "net:[202]"),
            ("server_namespace", "net:[303]"),
            ("probe_namespace", "net:[0]"),
            ("server_namespace", "net:[202]\n"),
            ("parent_namespace", None),
        ):
            candidate = fictional_evidence()
            candidate[field] = value
            with self.subTest(field=field, value=value):
                self.assertFalse(self.check(candidate))

    def test_foreign_interface_or_down_loopback_fails_closed(self):
        for interfaces in (
            [],
            [{"name": "eth0", "flags": ["UP"], "operstate": "UP"}],
            [{"name": "lo", "flags": ["LOOPBACK"], "operstate": "DOWN"}],
            [{"name": "lo", "flags": "LOOPBACK UP", "operstate": "UNKNOWN"}],
            fictional_evidence()["interfaces"] * 2,
        ):
            candidate = fictional_evidence()
            candidate["interfaces"] = interfaces
            with self.subTest(interfaces=interfaces):
                self.assertFalse(self.check(candidate))

    def test_nonloopback_address_or_route_is_not_hidden_by_other_valid_facts(self):
        changes = [
            ("addresses", []),
            ("addresses", [{"interface": "lo", "family": "inet", "local": "10.0.0.1",
                            "prefixlen": 24, "scope": "host"}]),
            ("routes", [{"family": "inet", "type": "unicast", "destination": "default",
                         "interface": "lo", "table": "main"}]),
            ("routes", [{"family": "inet6", "type": "unicast", "destination": "fe80::/64",
                         "interface": "lo", "table": "main"}]),
            ("routes", [{"family": "inet", "type": "local", "destination": "127.0.0.0/8",
                         "interface": "eth0", "table": "local"}]),
            ("routes", [{"family": "inet", "type": "unreachable", "destination": "default",
                         "interface": None, "table": "main"}]),
        ]
        for field, value in changes:
            candidate = fictional_evidence()
            candidate[field] = value
            with self.subTest(field=field, value=value):
                self.assertFalse(self.check(candidate))

    def test_both_listeners_must_belong_to_same_live_process_sockets(self):
        mutations = (
            lambda d: d.update(listeners=d["listeners"][:1]),
            lambda d: d["listeners"][0].update(pid=501),
            lambda d: d["listeners"][0].update(inode=9999),
            lambda d: d["listeners"][0].update(port=11112),
            lambda d: d["listeners"][0].update(address="10.0.0.2"),
            lambda d: d.update(server_socket_inodes=[]),
            lambda d: d.update(server_start_ticks=0),
            lambda d: d.update(server_pid=True),
            lambda d: d["expected_ports"].update(http=True),
            lambda d: d["expected_ports"].update(http=65536),
            lambda d: d["expected_ports"].update(http=11112),
        )
        for number, mutate in enumerate(mutations):
            candidate = fictional_evidence()
            mutate(candidate)
            candidate["namespace_confined"] = True
            with self.subTest(mutation=number):
                self.assertFalse(self.check(candidate))

    def test_malformed_facts_never_raise_or_authorize(self):
        for value in (None, [], True, 7, "receipt", {}, {"kind": []}):
            with self.subTest(value=value):
                self.assertFalse(self.check(value))
        for field in ("interfaces", "addresses", "routes", "listeners", "server_socket_inodes"):
            candidate = fictional_evidence()
            candidate[field] = [None]
            with self.subTest(field=field):
                self.assertFalse(self.check(candidate))

    def test_address_facts_require_readable_strings(self):
        for collection, field, number in (
            ("addresses", "local", 2130706433),
            ("routes", "destination", 2130706433),
            ("listeners", "address", 0),
        ):
            candidate = fictional_evidence()
            candidate[collection][0][field] = number
            with self.subTest(collection=collection):
                self.assertFalse(self.check(candidate))

    def kernel_command(self, arguments):
        """Complete bounded ip/ss fixtures for hosts without /proc PID visibility."""
        outputs = {
            ("ip", "-j", "link", "show"): json.dumps([
                {"ifindex": 1, "ifname": "lo", "flags": ["LOOPBACK", "UP", "LOWER_UP"],
                 "mtu": 65536, "qdisc": "noqueue", "operstate": "UNKNOWN", "linkmode": "DEFAULT",
                 "group": "default", "txqlen": 1000, "link_type": "loopback",
                 "address": "00:00:00:00:00:00", "broadcast": "00:00:00:00:00:00"}]),
            ("ip", "-j", "address", "show"): json.dumps([
                {"ifindex": 1, "ifname": "lo", "flags": ["LOOPBACK", "UP", "LOWER_UP"],
                 "mtu": 65536, "qdisc": "noqueue", "operstate": "UNKNOWN", "group": "default",
                 "txqlen": 1000, "link_type": "loopback", "address": "00:00:00:00:00:00",
                 "broadcast": "00:00:00:00:00:00", "addr_info": [
                     {"family": "inet", "local": "127.0.0.1", "prefixlen": 8, "scope": "host",
                      "label": "lo", "valid_life_time": 4294967295, "preferred_life_time": 4294967295}]}]),
            ("ip", "-j", "-4", "route", "show", "table", "all"): json.dumps([
                {"type": "local", "dst": "127.0.0.0/8", "dev": "lo", "table": "local",
                 "protocol": "kernel", "scope": "host", "prefsrc": "127.0.0.1", "flags": []}]),
            ("ip", "-j", "-6", "route", "show", "table", "all"): "[]",
            ("ss", "-H", "-ltnpe", "-4"):
                'LISTEN 0 4096 0.0.0.0:18042 0.0.0.0:* users:(("pacsnode",pid=500,fd=8)) ino:7001 sk:1\n'
                'LISTEN 0 4096 0.0.0.0:11112 0.0.0.0:* users:(("pacsnode",pid=500,fd=9)) ino:7002 sk:2\n',
            ("ss", "-H", "-ltnpe", "-6"): "",
        }
        return outputs[tuple(arguments)]

    def test_collector_normalizes_kernel_facts_and_keeps_socket_ownership(self):
        with patch.object(self.module, "_command", side_effect=self.kernel_command), \
                patch.object(self.module, "_process_identity", return_value=("net:[202]", 12345)), \
                patch.object(self.module, "_socket_inodes", return_value=[7001, 7002]), \
                patch.object(self.module.os, "readlink", return_value="net:[202]"):
            evidence = self.module.capture_network_evidence(500, "net:[101]")
        self.assertTrue(evidence["namespace_confined"])
        self.assertEqual(evidence["listeners"], [
            {"family": "inet", "address": "0.0.0.0", "port": 11112, "pid": 500, "inode": 7002},
            {"family": "inet", "address": "0.0.0.0", "port": 18042, "pid": 500, "inode": 7001},
        ])

    def test_reused_process_identity_during_capture_is_not_accepted(self):
        with patch.object(self.module, "_command", side_effect=self.kernel_command), \
                patch.object(self.module, "_process_identity", side_effect=[
                    ("net:[202]", 12345), ("net:[202]", 12346)]), \
                patch.object(self.module, "_socket_inodes", return_value=[7001, 7002]), \
                patch.object(self.module.os, "readlink", return_value="net:[202]"):
            with self.assertRaises(self.module.NetworkEvidenceError):
                self.module.capture_network_evidence(500, "net:[101]")

    def test_ss_claimed_pid_must_agree_with_kernel_owned_socket_inodes(self):
        with patch.object(self.module, "_command", side_effect=self.kernel_command), \
                patch.object(self.module, "_process_identity", return_value=("net:[202]", 12345)), \
                patch.object(self.module, "_socket_inodes", return_value=[8001, 8002]), \
                patch.object(self.module.os, "readlink", return_value="net:[202]"):
            with self.assertRaises(self.module.NetworkEvidenceError):
                self.module.capture_network_evidence(500, "net:[101]")

    def test_unavailable_process_identity_fails_closed(self):
        with self.assertRaises(self.module.NetworkEvidenceError):
            self.module.capture_network_evidence(2147483647, "net:[101]")

    @unittest.skipUnless(shutil.which("ip") and shutil.which("ss"), "Linux ip/ss tools required")
    def test_collector_observes_real_process_socket_ownership_without_confined_claim(self):
        code = """import json,socket,sys
sockets=[socket.socket(),socket.socket()]
for sock in sockets:
    sock.bind(('127.0.0.1',0)); sock.listen()
print(json.dumps([sock.getsockname()[1] for sock in sockets]),flush=True)
sys.stdin.readline()
"""
        with subprocess.Popen([sys.executable, "-c", code], stdin=subprocess.PIPE,
                              stdout=subprocess.PIPE, text=True) as process:
            try:
                ports = json.loads(process.stdout.readline())
                current = os.readlink("/proc/self/ns/net")
                try:
                    os.readlink(f"/proc/{process.pid}/ns/net")
                except (PermissionError, FileNotFoundError):
                    self.assertIsNone(process.poll(), "The test socket process unexpectedly exited")
                    self.skipTest("This sandbox hides numeric process network namespaces; hosted Linux required")
                evidence = self.module.capture_network_evidence(
                    process.pid, current, http_port=ports[0], dicom_port=ports[1])
                self.assertEqual(evidence["probe_namespace"], current)
                self.assertEqual(evidence["server_namespace"], current)
                self.assertEqual({item["port"] for item in evidence["listeners"]}, set(ports))
                self.assertTrue(all(item["pid"] == process.pid for item in evidence["listeners"]))
                self.assertTrue(all(item["inode"] in evidence["server_socket_inodes"]
                                    for item in evidence["listeners"]))
                self.assertFalse(evidence["namespace_confined"])
            finally:
                process.communicate("\n", timeout=5)


class ConfinedRunnerRefusalTests(unittest.TestCase):
    def test_runner_refuses_parent_namespace_before_starting_vendor_or_writing_config(self):
        script = ROOT / "tools/imaging/run_confined_pacsnode.sh"
        self.assertTrue(script.is_file(), "The confined runner is not implemented")
        with tempfile.TemporaryDirectory() as directory:
            run = Path(directory) / "run"
            run.mkdir()
            result = subprocess.run(
                ["bash", str(script), shutil.which("true"), str(ROOT), str(run),
                 os.readlink("/proc/self/ns/net"), sys.executable],
                capture_output=True, text=True, timeout=5)
            self.assertNotEqual(result.returncode, 0)
            self.assertFalse(list(run.iterdir()))

    def test_failed_readiness_terminates_and_reaps_a_server_that_ignores_term(self):
        """Controlled command doubles test process cleanup, not namespace proof."""
        script = ROOT / "tools/imaging/run_confined_pacsnode.sh"
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            fakebin = root / "bin"
            fakebin.mkdir()
            repo = root / "repo"
            (repo / "tools/imaging").mkdir(parents=True)
            run = root / "run"
            run.mkdir()
            pidfile = root / "child.pid"
            programs = {
                "readlink": '#!/bin/sh\nprintf "net:[202]\\n"\n',
                "ip": '#!/bin/sh\nexit 0\n',
                "vendor": '''#!/bin/sh
if [ "${1-}" = generate-config ]; then
  printf '[plugins]\\nenabled = []\\n' > config.toml
  exit 0
fi
trap '' TERM
printf '%s\\n' "$$" > "$TEST_CHILD_PIDFILE"
exec sleep 60
''',
                "python": '''#!/bin/sh
if [ "$#" -eq 3 ]; then
  for attempt in $(seq 1 50); do
    if [ -s "$TEST_CHILD_PIDFILE" ]; then exit 1; fi
    sleep 0.01
  done
  exit 1
fi
exit 0
''',
            }
            for name, text in programs.items():
                path = fakebin / name
                path.write_text(text)
                path.chmod(0o700)
            environment = dict(os.environ, PATH=str(fakebin) + os.pathsep + os.environ["PATH"],
                               TEST_CHILD_PIDFILE=str(pidfile))
            try:
                try:
                    result = subprocess.run(
                        ["bash", str(script), str(fakebin / "vendor"), str(repo), str(run),
                         "net:[101]", str(fakebin / "python")], env=environment,
                        capture_output=True, text=True, timeout=8)
                except subprocess.TimeoutExpired:
                    self.fail("The failed evaluation did not terminate its server within the cleanup bound")
                self.assertNotEqual(result.returncode, 0)
                child_pid = int(pidfile.read_text())
                with self.assertRaises(ProcessLookupError):
                    os.kill(child_pid, 0)
            finally:
                if pidfile.exists():
                    try:
                        os.kill(int(pidfile.read_text()), signal.SIGKILL)
                    except ProcessLookupError:
                        pass


if __name__ == "__main__":
    unittest.main()
