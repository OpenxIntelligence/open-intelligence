"""Observe a disposable Linux network namespace used only for synthetic PACS tests.

Wildcard listeners remain wildcard listeners. These facts establish a bounded
network-namespace observation, never patient authorization, a process sandbox,
or protection from a privileged host process. The pure checker validates receipt
consistency; it cannot authenticate a JSON artifact supplied by another party.
"""
from __future__ import annotations

import ipaddress
import json
import os
from pathlib import Path
import re
import subprocess


_NAMESPACE = re.compile(r"net:\[[1-9][0-9]{0,19}\]\Z")
_SOCKET = re.compile(r"socket:\[([1-9][0-9]*)\]\Z")
_LIMIT = 131_072


class NetworkEvidenceError(ValueError):
    """Required kernel/process evidence was unavailable or inconsistent."""


def _positive(value: object, maximum: int = 2**63 - 1) -> bool:
    return type(value) is int and 0 < value <= maximum


def _namespace(value: object) -> bool:
    return isinstance(value, str) and _NAMESPACE.fullmatch(value) is not None


def network_evidence_is_confined(data: object) -> bool:
    """Recompute confinement from explicit facts, ignoring claimed booleans."""
    try:
        return _confined(data)
    except (KeyError, TypeError, ValueError, AttributeError):
        return False


def _confined(data: object) -> bool:
    if not isinstance(data, dict) or data.get("kind") != "oi.pacs-network-namespace/1":
        return False
    if not all(_namespace(data[key]) for key in (
            "parent_namespace", "probe_namespace", "server_namespace")):
        return False
    if not (data["probe_namespace"] == data["server_namespace"] != data["parent_namespace"]):
        return False
    pid = data["server_pid"]
    if not _positive(pid) or not _positive(data["server_start_ticks"]):
        return False
    ports = data["expected_ports"]
    if (not isinstance(ports, dict) or set(ports) != {"http", "dicom"}
            or not all(_positive(value, 65535) for value in ports.values())
            or ports["http"] == ports["dicom"]):
        return False
    inodes = data["server_socket_inodes"]
    if (not isinstance(inodes, list) or not 1 <= len(inodes) <= 4096
            or not all(_positive(inode) for inode in inodes)
            or len(set(inodes)) != len(inodes)):
        return False

    interfaces = data["interfaces"]
    if not isinstance(interfaces, list) or len(interfaces) != 1:
        return False
    interface = interfaces[0]
    if (not isinstance(interface, dict) or interface["name"] != "lo"
            or interface["operstate"] not in ("UNKNOWN", "UP")):
        return False
    flags = interface["flags"]
    if (not isinstance(flags, list) or not all(isinstance(flag, str) for flag in flags)
            or not {"UP", "LOOPBACK"}.issubset(flags)):
        return False

    addresses = data["addresses"]
    if not isinstance(addresses, list) or not 1 <= len(addresses) <= 32:
        return False
    ipv4_loopback = False
    for item in addresses:
        if not isinstance(item, dict) or item["interface"] != "lo" or item["scope"] != "host":
            return False
        if not isinstance(item["local"], str) or len(item["local"]) > 64:
            return False
        address = ipaddress.ip_address(item["local"])
        if not address.is_loopback or item["family"] != ("inet" if address.version == 4 else "inet6"):
            return False
        prefix = item["prefixlen"]
        if type(prefix) is not int or not 0 <= prefix <= address.max_prefixlen:
            return False
        subnet = ipaddress.ip_network(f"{address}/{prefix}", strict=False)
        if not subnet.network_address.is_loopback or not subnet.broadcast_address.is_loopback:
            return False
        ipv4_loopback |= str(address) == "127.0.0.1"
    if not ipv4_loopback:
        return False

    routes = data["routes"]
    if not isinstance(routes, list) or not 1 <= len(routes) <= 64:
        return False
    for item in routes:
        if (not isinstance(item, dict) or item["interface"] != "lo"
                or item["type"] not in ("local", "broadcast", "unicast")
                or not isinstance(item["table"], str) or not 1 <= len(item["table"]) <= 32):
            return False
        if not isinstance(item["destination"], str) or len(item["destination"]) > 64:
            return False
        route = ipaddress.ip_network(item["destination"], strict=False)
        if (not route.network_address.is_loopback or not route.broadcast_address.is_loopback
                or item["family"] != ("inet" if route.version == 4 else "inet6")):
            return False

    listeners = data["listeners"]
    if not isinstance(listeners, list) or not 2 <= len(listeners) <= 16:
        return False
    observed_ports, observed_inodes = set(), set()
    for item in listeners:
        if (not isinstance(item, dict) or type(item["pid"]) is not int or item["pid"] != pid
                or not _positive(item["inode"]) or item["inode"] not in inodes
                or item["inode"] in observed_inodes or not _positive(item["port"], 65535)
                or item["family"] not in ("inet", "inet6")):
            return False
        if not isinstance(item["address"], str) or len(item["address"]) > 64:
            return False
        if item["address"] != "*":
            address = ipaddress.ip_address(item["address"])
            if (not (address.is_loopback or address.is_unspecified)
                    or item["family"] != ("inet" if address.version == 4 else "inet6")):
                return False
        observed_ports.add(item["port"])
        observed_inodes.add(item["inode"])
    return observed_ports == set(ports.values())


def _command(arguments: list[str]) -> str:
    try:
        result = subprocess.run(arguments, check=True, stdout=subprocess.PIPE,
                                stderr=subprocess.DEVNULL, timeout=3, text=True)
        if len(result.stdout) > _LIMIT:
            raise NetworkEvidenceError("Network evidence exceeds its bounded size")
        return result.stdout
    except (OSError, subprocess.SubprocessError, UnicodeError):
        raise NetworkEvidenceError("Network evidence command unavailable") from None


def _json_command(arguments: list[str]) -> list[dict]:
    try:
        result = json.loads(_command(arguments))
    except ValueError:
        raise NetworkEvidenceError("Malformed network command evidence") from None
    if (not isinstance(result, list) or len(result) > 256
            or not all(isinstance(item, dict) for item in result)):
        raise NetworkEvidenceError("Unbounded or malformed network command evidence")
    return result


def _process_identity(pid: int) -> tuple[str, int]:
    try:
        with Path(f"/proc/{pid}/stat").open() as stream:
            raw = stream.read(4097)
        if len(raw) > 4096 or raw.split(" ", 1)[0] != str(pid):
            raise ValueError
        # Linux comm may contain spaces and parentheses; fields follow its last ')'.
        fields = raw.rsplit(")", 1)[1].split()
        if fields[0] in {"Z", "X", "x"}:
            raise ValueError
        start = int(fields[19])  # /proc/PID/stat field 22, relative to field 3.
        namespace = os.readlink(f"/proc/{pid}/ns/net")
        if not _positive(start) or not _namespace(namespace):
            raise ValueError
        return namespace, start
    except (OSError, ValueError, IndexError):
        raise NetworkEvidenceError("Live PACS process identity unavailable") from None


def _socket_inodes(pid: int) -> list[int]:
    try:
        descriptors = list(Path(f"/proc/{pid}/fd").iterdir())
        if len(descriptors) > 4096:
            raise ValueError
        inodes = set()
        for descriptor in descriptors:
            try:
                target = os.readlink(descriptor)
            except FileNotFoundError:
                continue  # A completed connection may close during observation.
            match = _SOCKET.fullmatch(target)
            if match:
                inodes.add(int(match[1]))
        return sorted(inodes)
    except (OSError, ValueError):
        raise NetworkEvidenceError("PACS socket ownership unavailable") from None


def _listeners(pid: int, inodes: list[int]) -> list[dict]:
    result = []
    for family, flag in (("inet", "-4"), ("inet6", "-6")):
        for line in _command(["ss", "-H", "-ltnpe", flag]).splitlines():
            fields = line.split(None, 5)
            if len(fields) < 6 or fields[0] != "LISTEN":
                raise NetworkEvidenceError("Malformed TCP listener evidence")
            detail = fields[5]
            owners = {int(value) for value in re.findall(r"\bpid=([0-9]+)", detail)}
            match = re.search(r"\bino:([0-9]+)\b", detail)
            inode = int(match[1]) if match else None
            if pid not in owners and inode not in inodes:
                continue
            if owners != {pid} or inode not in inodes:
                raise NetworkEvidenceError("Listener ownership could not be corroborated")
            address, separator, port = fields[3].rpartition(":")
            if not separator or not port.isdecimal():
                raise NetworkEvidenceError("Malformed TCP listener address")
            result.append({"family": family, "address": address.strip("[]"),
                           "port": int(port), "pid": pid, "inode": inode})
    return sorted(result, key=lambda item: (item["port"], item["family"], item["inode"]))


def capture_network_evidence(server_pid: int, parent_namespace: str, *,
                             http_port: int = 18042, dicom_port: int = 11112) -> dict:
    """Capture current kernel facts, including actual listener FD ownership.

    The operator-controlled runner supplies its parent namespace before unshare.
    No command is allowed to fetch external data. A reused/exited process or
    namespace change during capture raises instead of producing a positive claim.
    """
    if (not _positive(server_pid) or not _namespace(parent_namespace)
            or not _positive(http_port, 65535) or not _positive(dicom_port, 65535)
            or http_port == dicom_port):
        raise NetworkEvidenceError("Invalid expected network boundary")
    try:
        probe_namespace = os.readlink("/proc/self/ns/net")
        initial = _process_identity(server_pid)
        links = _json_command(["ip", "-j", "link", "show"])
        raw_addresses = _json_command(["ip", "-j", "address", "show"])
        routes = []
        for family, flag in (("inet", "-4"), ("inet6", "-6")):
            for row in _json_command(["ip", "-j", flag, "route", "show", "table", "all"]):
                routes.append({"family": family, "type": row.get("type", "unicast"),
                               "destination": row.get("dst", "default"),
                               "interface": row.get("dev"), "table": str(row.get("table", "main"))})
        inodes = _socket_inodes(server_pid)
        listeners = _listeners(server_pid, inodes)
        if (_process_identity(server_pid) != initial
                or os.readlink("/proc/self/ns/net") != probe_namespace):
            raise NetworkEvidenceError("Process or network namespace changed during observation")
        # Recheck the observed listener FDs after ss; transient connections are
        # irrelevant, while disappearing listener FDs invalidate the observation.
        if not {item["inode"] for item in listeners}.issubset(_socket_inodes(server_pid)):
            raise NetworkEvidenceError("Listener changed during observation")
        evidence = {
            "kind": "oi.pacs-network-namespace/1",
            "parent_namespace": parent_namespace, "probe_namespace": probe_namespace,
            "server_namespace": initial[0], "server_pid": server_pid,
            "server_start_ticks": initial[1], "server_socket_inodes": inodes,
            "expected_ports": {"http": http_port, "dicom": dicom_port},
            "interfaces": [{"name": row["ifname"], "flags": row["flags"],
                            "operstate": row["operstate"]} for row in links],
            "addresses": [{"interface": row["ifname"], "family": address["family"],
                           "local": address["local"], "prefixlen": address["prefixlen"],
                           "scope": address["scope"]}
                          for row in raw_addresses for address in row["addr_info"]],
            "routes": routes, "listeners": listeners,
        }
    except (OSError, KeyError, TypeError, ValueError) as error:
        if isinstance(error, NetworkEvidenceError):
            raise
        raise NetworkEvidenceError("Incomplete kernel network evidence") from None
    evidence["namespace_confined"] = network_evidence_is_confined(evidence)
    return evidence
