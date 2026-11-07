"""Code-owned capability declarations; not authorization or a plugin loader.

Only trusted application code constructs a catalog. Each workload still needs
its own reviewed implementation, storage contracts, and current access checks.
"""
from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
import hashlib
import json
import re

_KIND = re.compile(r"[a-z][a-z0-9]*(?:-[a-z0-9]+)*/[1-9][0-9]{0,5}")
_CONTRACT = re.compile(r"oi\.[a-z][a-z0-9.-]*/[1-9][0-9]{0,5}")
_OWNER = re.compile(r"[a-z][a-z0-9-]{0,63}")
_ACTION = re.compile(r"[a-z][a-z0-9_]{0,63}")


def _matches(value: object, pattern: re.Pattern, limit: int) -> bool:
    return type(value) is str and len(value) <= limit and pattern.fullmatch(value) is not None


@dataclass(frozen=True)
class CapabilityDescriptor:
    kind: str
    owner: str
    input_contract: str
    output_contract: str
    required_actions: tuple[str, ...]
    enabled: bool = True

    def __post_init__(self):
        if (not _matches(self.kind, _KIND, 96)
                or not _matches(self.owner, _OWNER, 64)
                or not _matches(self.input_contract, _CONTRACT, 128)
                or not _matches(self.output_contract, _CONTRACT, 128)):
            raise ValueError("Capability identity and contracts require explicit valid versions")
        if (type(self.required_actions) is not tuple or not 1 <= len(self.required_actions) <= 32
                or any(not _matches(action, _ACTION, 64) for action in self.required_actions)
                or len(set(self.required_actions)) != len(self.required_actions)):
            raise ValueError("Capability actions must be an immutable nonempty unique tuple")
        if type(self.enabled) is not bool:
            raise ValueError("Capability enabled state must be a boolean")

    def describe(self) -> dict:
        return {"kind": self.kind, "owner": self.owner,
                "input_contract": self.input_contract, "output_contract": self.output_contract,
                "required_actions": list(self.required_actions), "enabled": self.enabled}


@dataclass(frozen=True, init=False)
class CapabilityCatalog:
    _entries: tuple[CapabilityDescriptor, ...]

    def __init__(self, entries: Iterable[CapabilityDescriptor]):
        captured = []
        for entry in entries:
            if type(entry) is not CapabilityDescriptor:
                raise TypeError("A catalog requires validated capability descriptors")
            if len(captured) >= 128:
                raise ValueError("Capability catalog exceeds its registration limit")
            captured.append(entry)
        if len({entry.kind for entry in captured}) != len(captured):
            raise ValueError("Duplicate execution capability version")
        object.__setattr__(self, "_entries", tuple(sorted(captured, key=lambda entry: entry.kind)))

    def get(self, kind: str) -> CapabilityDescriptor:
        """Resolve exact identity, including a disabled entry for historical inspection."""
        if type(kind) is str:
            for entry in self._entries:
                if entry.kind == kind:
                    return entry
        raise ValueError("Execution capability unavailable")

    def require(self, kind: str) -> CapabilityDescriptor:
        """Resolve a registered enabled version; never infer latest or authorize work."""
        entry = self.get(kind)
        if not entry.enabled:
            raise ValueError("Execution capability unavailable")
        return entry

    def describe(self) -> dict:
        entries = [entry.describe() for entry in self._entries]
        encoded = json.dumps(entries, sort_keys=True, ensure_ascii=False,
                             separators=(",", ":"), allow_nan=False).encode("utf-8")
        return {"contract": "oi.execution-capability-catalog/1", "synthetic_only": True,
                "runtime_readiness": "not_checked", "authorizes_execution": False,
                "catalog_sha256": hashlib.sha256(encoded).hexdigest(), "capabilities": entries}
