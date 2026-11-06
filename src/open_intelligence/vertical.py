"""The vertical interface: what a domain registers, and how the core resolves it.

Program plan slice V1. A vertical is a domain: its own domain rules
(disease-scope predicates, line-of-therapy ruleset version, terminology
bindings), its own scope patterns, its own evidence kinds and link
templates. All verticals share the same coordination core and the same
ledger. A vertical registers with the core; it does not fork it.

The core never imports a vertical definition module (``vertical_oncology``,
``vertical_cardiology``) by name. It resolves verticals only through this
registry: ``get_vertical(name)`` (which lazy-loads the built-in definition
module for the name) or ``register_vertical(vertical)`` (for a vertical
defined at runtime, as in tests). ``tests/test_vertical_boundary.py`` is
the tripwire: it scans the core modules' imports and fails the suite if
any of them imports a vertical definition module.

``default_vertical()`` is the pre-V2 default: every case is an oncology
case until cases carry a vertical of their own. That default is
configuration held in this one place, not oncology knowledge spread
through the core; V2's addability proof is that a second vertical lands
without touching it, and a case-vertical field is the follow-up that
retires the default.

What the interface deliberately does NOT own yet: the model prompt
(``investigation.build_prompt`` still names the synthetic oncology case —
prompt templating per vertical is future work) and the synthetic report
parser's oncology format (``store.parse_report`` — a data-format concern).
Both are recorded in the V1 section of ``docs/IMPLEMENTATION_STATUS.md``.
"""
from __future__ import annotations

import importlib
import importlib.util
import re
from dataclasses import dataclass, field

_NAME_RE = re.compile(r"[a-z][a-z0-9_]*\Z")

#: The vertical every case runs under until cases carry a vertical of
#: their own. See the module docstring: a default, not a leak.
DEFAULT_VERTICAL_NAME = "oncology"


class VerticalError(ValueError):
    """A vertical name is unknown, invalid, or already registered."""


@dataclass
class Vertical:
    """Everything the core needs from one domain, as data.

    The core reads these fields; it never interprets them. ``synonyms``
    maps value paraphrases to the case's own canonical certainty words
    (K2 slot matching). ``condition_terms`` names the vertical's
    conditions, for the K6 "you have" scope pattern. ``scope_patterns``
    are the vertical's extra scope patterns beyond the structural
    language guard (K6). ``lot_ruleset`` is the vertical's current
    line-of-therapy (or equivalent) ruleset version label — an opaque
    string the K5 check compares, never guideline content.
    ``evidence_kinds`` and ``link_templates`` are the vertical's
    evidence bindings (the CIViC/ClinVar bindings for oncology).
    ``toolsets`` names the domain toolsets the vertical provides (empty
    until a dimension slice needs one). ``substance_names`` is the
    vertical's named-substance vocabulary for K7 (empty until substance
    data exists in the runtime).
    """

    name: str
    synonyms: dict[str, str] = field(default_factory=dict)
    condition_terms: tuple[str, ...] = ()
    scope_patterns: tuple = ()
    lot_ruleset: str | None = None
    evidence_kinds: frozenset = frozenset()
    link_templates: dict[str, str] = field(default_factory=dict)
    toolsets: tuple[str, ...] = ()
    substance_names: tuple[str, ...] = ()


_REGISTRY: dict[str, Vertical] = {}


def register_vertical(vertical: Vertical) -> Vertical:
    """Register a vertical under its name. Duplicate names are rejected."""
    if not isinstance(vertical, Vertical):
        raise VerticalError("register_vertical requires a Vertical")
    if not _NAME_RE.fullmatch(vertical.name):
        raise VerticalError(
            f"invalid vertical name: {vertical.name!r} "
            "(lowercase letters, digits, underscores, starting with a letter)"
        )
    if vertical.name in _REGISTRY:
        raise VerticalError(f"vertical already registered: {vertical.name!r}")
    _REGISTRY[vertical.name] = vertical
    return vertical


def get_vertical(name: str) -> Vertical:
    """Resolve a vertical by name, lazy-loading its built-in definition.

    A name that matches no built-in definition module raises
    ``VerticalError``; a definition module with a genuine import error
    lets that error propagate instead of masquerading as unknown.
    """
    if type(name) is not str or not _NAME_RE.fullmatch(name):
        raise VerticalError(f"unknown vertical: {name!r}")
    vertical = _REGISTRY.get(name)
    if vertical is not None:
        return vertical
    module_name = f"open_intelligence.vertical_{name}"
    if importlib.util.find_spec(module_name) is None:
        raise VerticalError(f"unknown vertical: {name!r}")
    importlib.import_module(module_name)
    vertical = _REGISTRY.get(name)
    if vertical is None:
        raise VerticalError(
            f"vertical module {module_name!r} did not register a vertical"
        )
    return vertical


def default_vertical() -> Vertical:
    """The vertical cases run under until they carry one of their own."""
    return get_vertical(DEFAULT_VERTICAL_NAME)


def list_verticals() -> list[str]:
    """Names of the verticals registered so far, sorted."""
    return sorted(_REGISTRY)


def build_scope_patterns(condition_terms) -> list:
    """The K6 scope patterns for a vertical, from its condition terms.

    The generic patterns are domain-free structure: advice, dosing,
    eligibility, trial matching, prognosis, ranking. Only the "you
    have" pattern carries vertical content, built from the vertical's
    own condition terms. This is the one place the pattern list is
    assembled, so every vertical's guard has the same shape and the
    oncology list is byte-identical to the pre-V1 list.
    """
    terms = list(condition_terms)
    return [
        re.compile(r"\bfirst[- ]line (choice|option|treatment|therapy)\b", re.IGNORECASE),
        re.compile(r"\bdose of\b", re.IGNORECASE),
        re.compile(r"\bmg\s*/", re.IGNORECASE),
        re.compile(r"\beligible for\b", re.IGNORECASE),
        re.compile(
            r"(?:\b(trial|study|NCT[0-9]*)\b.{0,40}\bmatches\b"
            r"|\bmatches\b.{0,40}\b(trial|study|NCT[0-9]*)\b)",
            re.IGNORECASE | re.DOTALL,
        ),
        re.compile(r"\bprognosis\b", re.IGNORECASE),
        re.compile(
            r"\byou have\b.{0,40}\b(" + "|".join(terms) + r")\b",
            re.IGNORECASE | re.DOTALL,
        ),
        re.compile(r"\bshould (consider|choose|select)\b", re.IGNORECASE),
        re.compile(
            r"\brank\w*\b.{0,40}\b(options|treatments|therapies|drugs)\b",
            re.IGNORECASE | re.DOTALL,
        ),
    ]
