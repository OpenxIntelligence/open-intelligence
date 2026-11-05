"""Deterministic, offline evaluation harness (program plan slice C5,
Notion OI-09 section 9).

Verification quality is measured by code, not asserted in prose.
The harness runs the planted-defect fixtures from slices C2/C4
(temporal, contradiction, staleness, scope, hypothesis-support)
through the real pipeline code — structural validation, the
deterministic K-checks, the Skeptic wiring, T6 grouping, and the
replay check — and computes the M-metrics of OI-09 section 9.2 that
are measurable offline (M5, M6, M7, M8, M10, M16, M27, M28),
reporting pass/fail per metric against the Proposed targets.

No live model call is made anywhere in this module: ``model_calls``
in every report is 0. The Skeptic probe drives ``run_verification``
with an injected stub verdict, which proves the wiring, not the
model — a live run proving the real model catches the planted
misstatement is pending the Meta billing fix (HTTP 402) and is
recorded as a note, never faked. Model-dependent metrics (M25
model-judged entailment, M26 Skeptic challenge precision, M29
citation precision) are listed under ``not_measured`` with their
reason; they need live runs and, for M25, human labels.

"Never gates" (OI-09 section 9): the harness measures and reports.
A metric's ``pass`` is its value against the Proposed target, and
failures are listed as limits, never hidden (OI-09 section 9.9 rule
7). Nothing in this module decides whether a run, claim, or
hypothesis is accepted.

Fixtures are written from the Notion spec, in the same shapes the
C2/C4 tests proved (same version ids, dates, quotes, and slot
values), not from the implementation. The vertical wiring
(synonyms, scope patterns, condition terms, substance names) arrives
as parameters to ``fixture_context`` — the check logic itself holds
no vertical knowledge; the oncology wiring is the default fixture
only, and is the seam the V1 vertical interface will use.

M-metric readings used here (OI-09 section 9.2; the section's
definitions are written for live runs, so the harness scores the
same check as judgment accuracy over planted supported/unsupported
probes — the planted-defect reading M5/M6 already use):

- M5 planted temporal-defect recall: planted date-order violations
  caught / planted; target 100%.
- M6 contradiction recall / precision: planted cross-doc
  contradictions caught and surfaced (K4 drop + T6 group +
  AB-CONFLICT origin agent_divergence — the codebase has no literal
  ``SOURCES_DISAGREE`` label; the T6 group plus the typed
  abstention is its surfacing) / planted; false contradictions on
  clean docs; target recall 100%, FP 0.
- M7 staleness recall: claims citing a superseded or out-of-snapshot
  version marked stale, plus snapshot/ruleset-change findings /
  affected; target 100%.
- M8 advice-language leakage: kept claims matching scope patterns;
  target 0.
- M10 hypothesis support: hypothesis probes with the expected
  keep/drop outcome / total; target 100%.
- M16 replay determinism: identical replays / 3; target 100%.
- M27 routing record completeness: runs with exactly one
  ``route.decided`` before agent events / runs; target 100%.
- M28 hypothesis citation recall: probe sentences whose every
  checkable unit (numbers, named substances, temporal words,
  relation verbs, hyphenated entities) is present in the slots of
  the claims they cite, judged correctly / total; target 100% of
  kept sentences, plus a response-level rate.

The human spot-check (>=30 items, OI-09 section 9.9 rule 5) remains
a manual protocol: the harness records the spot-check set built from
its own probe items, it does not perform it.
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

from .agent_writes import (
    build_investigation_contract,
    build_route_id,
    check_replay,
)
from .investigation import (
    CONDITION_TERMS,
    K6_SCOPE_PATTERNS,
    ONCOLOGY_SYNONYMS,
    validate_output,
)
from .kchecks import (
    TIER_LIMITS_PHRASE,
    KCheckContext,
    Slot,
    SourceVersionInfo,
)
from .orchestrator import decide_route
from .skeptic import run_verification
from .store import CaseStore
from .synthesis import group_run_contradictions

HARNESS_VERSION = "evaluation:1"
SPOT_CHECK_MINIMUM = 30

# Checkable-unit classes for M28 (OI-09 section 9.2): numbers,
# named substances (from the fixture's substance vocabulary),
# temporal words, relation verbs, and hyphenated entities (slot
# fields such as "marker-a"). A unit is present when it appears in
# the cited evidence text after normalisation.
_TEMPORAL_WORDS = (
    "before", "after", "during", "prior", "previous", "following",
    "earlier", "later", "since", "until",
)
_RELATION_VERBS = (
    "increased", "decreased", "rose", "fell", "grew", "shrank",
    "improved", "worsened", "changed", "remained", "remains",
)
_NUMBER_RE = re.compile(r"\d+(?:\.\d+)?")
_ENTITY_RE = re.compile(r"[a-z]+(?:-[a-z]+)+")

# The synthetic case the harness runs against (OI-09 section 9.9
# protocol step 2: demo questions; the fixture case is the same
# small synthetic case the C2/C4 tests proved the checks on).
_FIXTURE_CASE = "CASE-X"
_VALID_SOURCES = {1, 2, 3, 4, 5}
_VALID_ASSESSMENTS = {1}


def _words(text: str) -> list[str]:
    """Normalise text to word tokens (mirrors kchecks normalisation)."""
    return re.sub(r"[^a-z0-9]+", " ", text.lower()).strip().split()


def _version(version_id, *, state="current", specimen="SPEC-A",
             specimen_date="2026-05-03", report_date="2026-05-05",
             received_date="2026-05-06T10:00:00Z", supersedes_id=None):
    return SourceVersionInfo(
        id=version_id, specimen_date=specimen_date, report_date=report_date,
        received_date=received_date, state=state, supersedes_id=supersedes_id,
        sha256=f"digest-{version_id}", specimen_id=specimen)


def fixture_context(*, synonyms=None, scope_patterns=None,
                    condition_terms=None, substance_names=None,
                    **overrides):
    """A small synthetic case, in the C2/C4 fixture shape: v1
    pathology (SPEC-A), v2 imaging (SPEC-B), v3 the superseded
    pathology reading v1 replaces, v4 a second current SPEC-A
    document that disagrees with v1 on marker-a, v5 a current SPEC-B
    document that agrees with v4. Slots are the assertions of those
    versions; v4 also carries a margin reading, so a second
    contradiction pair exists. Vertical knowledge arrives as
    parameters; the oncology wiring is the default fixture only."""
    versions = {
        1: _version(1, supersedes_id=3),
        2: _version(2, specimen="SPEC-B", specimen_date="2026-05-17",
                    report_date="2026-05-18", received_date="2026-05-19T10:00:00Z"),
        3: _version(3, state="superseded", specimen_date="2026-05-01",
                    report_date="2026-05-02", received_date="2026-05-03T10:00:00Z"),
        4: _version(4),
        5: _version(5, specimen="SPEC-B", specimen_date="2026-05-17",
                    report_date="2026-05-18", received_date="2026-05-19T10:00:00Z"),
    }
    slots = [
        Slot(subject=_FIXTURE_CASE, field="marker-a", value="not-reported",
             source_version_id=1, specimen="SPEC-A",
             quote="Marker A was not tested in this specimen."),
        Slot(subject=_FIXTURE_CASE, field="histology", value="reported",
             source_version_id=1, specimen="SPEC-A",
             quote="The examination identified a finding."),
        Slot(subject=_FIXTURE_CASE, field="margin", value="indeterminate",
             source_version_id=1, specimen="SPEC-A",
             quote="The margin cannot be assessed from this small specimen."),
        Slot(subject=_FIXTURE_CASE, field="lesion-size", value="reported",
             source_version_id=2, specimen="SPEC-B",
             quote="The lesion was measured as 31 mm."),
        Slot(subject=_FIXTURE_CASE, field="comparison", value="pending",
             source_version_id=2, specimen="SPEC-B",
             quote="Prior images are unavailable for reliable comparative measurement."),
        Slot(subject=_FIXTURE_CASE, field="marker-a", value="reported",
             source_version_id=3, specimen="SPEC-A",
             quote="Marker A was reported."),
        Slot(subject=_FIXTURE_CASE, field="marker-a", value="reported",
             source_version_id=4, specimen="SPEC-A",
             quote="Marker A was reported."),
        Slot(subject=_FIXTURE_CASE, field="margin", value="reported",
             source_version_id=4, specimen="SPEC-A",
             quote="The margin was reported."),
        Slot(subject=_FIXTURE_CASE, field="marker-a", value="reported",
             source_version_id=5, specimen="SPEC-B",
             quote="Marker A was reported."),
    ]
    context = KCheckContext(
        subject=_FIXTURE_CASE, source_versions=versions, derived_slots=slots,
        assessment_statements={
            1: "This independently authored note describes an assay limitation; "
               "it is not evidence of efficacy.",
        },
        snapshot_as_of="2026-06-01T00:00:00Z",
        snapshot_source_ids={1, 2, 4, 5},
        synonyms=dict(synonyms if synonyms is not None else ONCOLOGY_SYNONYMS),
        scope_patterns=list(scope_patterns if scope_patterns is not None else K6_SCOPE_PATTERNS),
        condition_terms=list(condition_terms if condition_terms is not None else CONDITION_TERMS),
        substance_names=list(substance_names if substance_names is not None
                             else ["fictional-substance-x", "fictional-substance-y"]),
    )
    for key, value in overrides.items():
        setattr(context, key, value)
    return context


def _claim(text, source_id=1, assessment_id=None, limits="Synthetic only.",
           kind=None):
    citations = [{"type": "source", "id": source_id}]
    if assessment_id is not None:
        citations.append({"type": "assessment", "id": assessment_id})
    claim = {"text": text, "support": "context",
             "citations": citations, "uncertainty": "moderate", "limits": limits}
    if kind is not None:
        claim["kind"] = kind
    return claim


def _validate(claims, context, validate_fn, *, valid_sources=None,
              valid_assessments=None):
    """Run claims through the real path: structural validation, then
    the deterministic K-checks (applied inside validate_output when a
    context is given). ``validate_fn`` is injectable so the
    sensitivity test can weaken a check and prove the harness fails."""
    payload = {"claims": list(claims), "abstentions": []}
    return validate_fn(
        payload,
        set(valid_sources) if valid_sources is not None else set(_VALID_SOURCES),
        set(valid_assessments) if valid_assessments is not None else set(_VALID_ASSESSMENTS),
        context)


def _probe(family, name, expected, outcome, passed, detail=None):
    return {"family": family, "name": name, "expected": expected,
            "outcome": outcome, "pass": bool(passed),
            "detail": detail or {}}


# --- M5: planted temporal-defect recall -------------------------------


def probe_temporal(validate_fn=validate_output):
    """M5: five planted temporal defects (three date-order
    violations, one range-order violation, one partial-date
    violation at coarser precision) plus the as-of probe, and two
    negative controls that must not fire. Caught means the defect
    produced the expected drop or run-level finding."""
    planted = []
    # T1: cite a version recorded after the snapshot.
    context = fixture_context()
    context.source_versions[8] = _version(
        8, specimen_date="2026-06-10", report_date="2026-06-12",
        received_date="2026-06-15T10:00:00Z")
    context.snapshot_source_ids = {1, 2, 4, 5, 8}
    result = _validate(
        [_claim("The sources report a finding.", source_id=8)], context,
        validate_fn, valid_sources={1, 2, 3, 4, 5, 8})
    drop = next((d for d in result.dropped if d.get("reason") == "k3_cite_after_snapshot"), None)
    planted.append(_probe("M5", "cite-after-snapshot", "drop k3_cite_after_snapshot",
                          drop["reason"] if drop else "kept", drop is not None,
                          {"source_version_id": 8}))
    # T2: specimen date after the report date.
    context = fixture_context()
    context.source_versions[6] = _version(
        6, specimen_date="2026-05-10", report_date="2026-05-05",
        received_date="2026-05-11T10:00:00Z")
    result = _validate([_claim("The sources report a finding.")], context, validate_fn)
    finding = next((f for f in result.findings
                    if f.get("reason") == "k3_temporal_order"
                    and f.get("detail", {}).get("source_version_id") == 6), None)
    planted.append(_probe("M5", "specimen-after-report", "finding k3_temporal_order",
                          "finding k3_temporal_order" if finding else "no finding",
                          finding is not None, {"source_version_id": 6}))
    # T3: report date after the received date.
    context = fixture_context()
    context.source_versions[7] = _version(
        7, specimen_date="2026-05-01", report_date="2026-05-20",
        received_date="2026-05-10T10:00:00Z")
    result = _validate([_claim("The sources report a finding.")], context, validate_fn)
    finding = next((f for f in result.findings
                    if f.get("reason") == "k3_temporal_order"
                    and f.get("detail", {}).get("source_version_id") == 7), None)
    planted.append(_probe("M5", "report-after-received", "finding k3_temporal_order",
                          "finding k3_temporal_order" if finding else "no finding",
                          finding is not None, {"source_version_id": 7}))
    # T4: slot range start after end (the as-of probe).
    context = fixture_context()
    context.derived_slots.append(Slot(
        subject=_FIXTURE_CASE, field="lesion-size", value="reported",
        source_version_id=2, specimen="SPEC-B",
        valid_from="2026-06-01", valid_to="2026-05-01",
        quote="The lesion was measured as 31 mm."))
    result = _validate([_claim("The sources report a finding.")], context, validate_fn)
    finding = next((f for f in result.findings if f.get("reason") == "k3_range_order"), None)
    planted.append(_probe("M5", "range-start-after-end", "finding k3_range_order",
                          "finding k3_range_order" if finding else "no finding",
                          finding is not None, {}))
    # T5: partial-date violation at coarser (month) precision.
    context = fixture_context()
    context.source_versions[6] = _version(
        6, specimen_date="2026-06", report_date="2026-05-03",
        received_date="2026-06-04T10:00:00Z")
    result = _validate([_claim("The sources report a finding.")], context, validate_fn)
    finding = next((f for f in result.findings
                    if f.get("reason") == "k3_temporal_order"
                    and f.get("detail", {}).get("source_version_id") == 6), None)
    planted.append(_probe("M5", "partial-date-violation", "finding k3_temporal_order",
                          "finding k3_temporal_order" if finding else "no finding",
                          finding is not None, {"source_version_id": 6}))
    # Negative controls: partial dates that agree at coarser
    # precision are indeterminate, never a violation; a clean claim
    # on the base context produces no finding.
    controls = []
    context = fixture_context()
    context.source_versions[6] = _version(
        6, specimen_date="2026-05", report_date="2026-05-03",
        received_date="2026-05-04T10:00:00Z")
    result = _validate([_claim("The sources report a finding.")], context, validate_fn)
    fired = [f for f in result.findings if f.get("reason") == "k3_temporal_order"]
    controls.append(_probe("M5", "partial-date-agreement", "no finding",
                           "finding k3_temporal_order" if fired else "no finding",
                           not fired, {"source_version_id": 6}))
    result = _validate([_claim("The sources report a finding.")], fixture_context(), validate_fn)
    fired = [f for f in result.findings if f.get("reason", "").startswith("k3_")]
    controls.append(_probe("M5", "clean-claim", "no finding",
                           "finding" if fired else "no finding",
                           not fired, {}))
    caught = sum(1 for item in planted if item["pass"])
    false_positives = sum(1 for item in controls if not item["pass"])
    return {"probes": planted + controls,
            "metric": {"value": caught / len(planted), "caught": caught,
                       "planted": len(planted),
                       "false_positives": false_positives,
                       "target": 1.0,
                       "pass": caught == len(planted) and false_positives == 0}}


# --- M6: contradiction recall / precision ------------------------------


def _k4_pair(claims, context, validate_fn):
    """Run one contradiction pair; return (dropped_k4, t6_groups)."""
    result = _validate(claims, context, validate_fn)
    dropped = [d for d in result.dropped if d.get("reason") == "k4_contradiction"]
    groups = group_run_contradictions(result.dropped)
    return dropped, groups


def probe_contradiction(validate_fn=validate_output):
    """M6: two planted contradictions (same subject and field,
    different normalised value, overlapping valid time, no
    supersession) and five negative controls that must not
    contradict. Caught means the later claim drops with
    k4_contradiction AND the contradiction is surfaced as a T6
    group. The run-verification replay check must also surface it
    as AB-CONFLICT with origin agent_divergence."""
    planted = []
    # C1: same specimen, marker-a (v1 not tested vs v4 reported).
    context = fixture_context()
    dropped, groups = _k4_pair(
        [_claim("Marker A was not tested.", source_id=1),
         _claim("Marker A was reported.", source_id=4)],
        context, validate_fn)
    surfaced = bool(groups)
    record = None
    if dropped:
        validated = _validate(
            [_claim("Marker A was not tested.", source_id=1),
             _claim("Marker A was reported.", source_id=4)],
            fixture_context(), validate_fn)
        record = run_verification(
            validated, fixture_context(),
            {"valid_sources": set(_VALID_SOURCES),
             "valid_assessments": set(_VALID_ASSESSMENTS)}, mode="replay")
        surfaced = surfaced and any(
            code.get("code") == "AB-CONFLICT"
            and code.get("origin") == "agent_divergence"
            for code in record.get("abstention_codes", []))
    planted.append(_probe(
        "M6", "same-specimen-marker", "drop k4_contradiction + T6 group + AB-CONFLICT",
        "drop k4_contradiction" if dropped else "kept",
        bool(dropped) and surfaced,
        {"field": "marker-a", "t6_groups": len(groups),
         "ab_conflict": bool(record) and any(
             code.get("origin") == "agent_divergence"
             for code in record.get("abstention_codes", [])) if record else False}))
    # C2: same specimen, margin (v1 indeterminate vs v4 reported).
    dropped, groups = _k4_pair(
        [_claim("The margin is indeterminate.", source_id=1),
         _claim("The margin was reported.", source_id=4)],
        fixture_context(), validate_fn)
    planted.append(_probe(
        "M6", "same-specimen-margin", "drop k4_contradiction + T6 group",
        "drop k4_contradiction" if dropped else "kept",
        bool(dropped) and bool(groups),
        {"field": "margin", "t6_groups": len(groups)}))
    # Negative controls: each must keep both claims.
    controls = []
    dropped, _ = _k4_pair(
        [_claim("Marker A was not tested.", source_id=1),
         _claim("Marker A was reported.", source_id=5)],
        fixture_context(), validate_fn)
    controls.append(_probe("M6", "different-specimens", "both kept",
                           "drop k4_contradiction" if dropped else "both kept",
                           not dropped, {}))
    context = fixture_context()
    context.derived_slots = [
        Slot(subject=_FIXTURE_CASE, field="marker-a", value="not-reported",
             source_version_id=1, specimen="SPEC-A", assay="assay-one",
             quote="Marker A was not tested in this specimen."),
        Slot(subject=_FIXTURE_CASE, field="marker-a", value="reported",
             source_version_id=4, specimen="SPEC-A", assay="assay-two",
             quote="Marker A was reported."),
    ]
    dropped, _ = _k4_pair(
        [_claim("Marker A was not tested.", source_id=1),
         _claim("Marker A was reported.", source_id=4)],
        context, validate_fn)
    controls.append(_probe("M6", "different-assays", "both kept",
                           "drop k4_contradiction" if dropped else "both kept",
                           not dropped, {}))
    context = fixture_context(snapshot_source_ids={1, 2, 3, 4, 5})
    dropped, _ = _k4_pair(
        [_claim("Marker A was reported.", source_id=3),
         _claim("Marker A was not tested.", source_id=1)],
        context, validate_fn)
    controls.append(_probe("M6", "supersession-defeats-contradiction", "both kept",
                           "drop k4_contradiction" if dropped else "both kept",
                           not dropped, {}))
    context = fixture_context()
    context.derived_slots = [
        Slot(subject=_FIXTURE_CASE, field="marker-a", value="not-reported",
             source_version_id=1, specimen="SPEC-A",
             valid_from="2026-01-01", valid_to="2026-02-01",
             quote="Marker A was not tested in this specimen."),
        Slot(subject=_FIXTURE_CASE, field="marker-a", value="reported",
             source_version_id=4, specimen="SPEC-A",
             valid_from="2026-03-01", valid_to="2026-04-01",
             quote="Marker A was reported."),
    ]
    dropped, _ = _k4_pair(
        [_claim("Marker A was not tested.", source_id=1),
         _claim("Marker A was reported.", source_id=4)],
        context, validate_fn)
    controls.append(_probe("M6", "non-overlapping-valid-time", "both kept",
                           "drop k4_contradiction" if dropped else "both kept",
                           not dropped, {}))
    dropped, _ = _k4_pair(
        [_claim("Marker A was not tested.", source_id=1),
         _claim("Marker A was not tested.", source_id=1)],
        fixture_context(), validate_fn)
    controls.append(_probe("M6", "same-value", "both kept",
                           "drop k4_contradiction" if dropped else "both kept",
                           not dropped, {}))
    caught = sum(1 for item in planted if item["pass"])
    false_positives = sum(1 for item in controls if not item["pass"])
    return {"probes": planted + controls,
            "metric": {"value": caught / len(planted), "caught": caught,
                       "planted": len(planted),
                       "false_positives": false_positives,
                       "target": 1.0,
                       "pass": caught == len(planted) and false_positives == 0}}


# --- M7: staleness recall ------------------------------------------------


def probe_staleness(validate_fn=validate_output):
    """M7: four planted staleness defects — a superseded citation, a
    version outside the snapshot, a changed snapshot hash, and a
    changed line-of-therapy ruleset — plus one negative control.
    Marked means the claim drops with k5_stale or the run carries
    the expected K5 finding."""
    planted = []
    # S1: citing a superseded version is marked stale.
    result = _validate(
        [_claim("Marker A was reported.", source_id=3)], fixture_context(),
        validate_fn)
    drop = next((d for d in result.dropped if d.get("reason") == "k5_stale"), None)
    planted.append(_probe("M7", "superseded-citation", "drop k5_stale",
                          drop["reason"] if drop else "kept", drop is not None,
                          {"source_version_id": 3}))
    # S2: a version outside the snapshot is marked stale.
    context = fixture_context()
    context.source_versions[9] = _version(
        9, specimen="SPEC-C", specimen_date="2026-05-20",
        report_date="2026-05-21", received_date="2026-05-22T10:00:00Z")
    result = _validate(
        [_claim("The sources report a finding.", source_id=9)], context,
        validate_fn, valid_sources={1, 2, 3, 4, 5, 9})
    drop = next((d for d in result.dropped if d.get("reason") == "k5_stale"), None)
    planted.append(_probe("M7", "version-outside-snapshot", "drop k5_stale",
                          drop["reason"] if drop else "kept", drop is not None,
                          {"source_version_id": 9}))
    # S3: a changed snapshot hash is a run-level finding.
    context = fixture_context(expected_snapshot_hash="aaa", current_snapshot_hash="bbb")
    result = _validate([_claim("Marker A was not tested.")], context, validate_fn)
    finding = next((f for f in result.findings
                    if f.get("reason") == "k5_snapshot_changed"), None)
    planted.append(_probe("M7", "snapshot-hash-changed", "finding k5_snapshot_changed",
                          "finding k5_snapshot_changed" if finding else "no finding",
                          finding is not None, {}))
    # S4: a changed ruleset is a run-level finding.
    context = fixture_context(lot_ruleset="rules-1", current_lot_ruleset="rules-2")
    result = _validate([_claim("Marker A was not tested.")], context, validate_fn)
    finding = next((f for f in result.findings
                    if f.get("reason") == "k5_lot_ruleset_changed"), None)
    planted.append(_probe("M7", "ruleset-changed", "finding k5_lot_ruleset_changed",
                          "finding k5_lot_ruleset_changed" if finding else "no finding",
                          finding is not None, {}))
    controls = []
    context = fixture_context(expected_snapshot_hash="aaa", current_snapshot_hash="aaa")
    result = _validate([_claim("Marker A was not tested.")], context, validate_fn)
    fired = [f for f in result.findings if f.get("check") == "K5"]
    controls.append(_probe("M7", "unchanged-snapshot-hash", "no finding",
                           "finding" if fired else "no finding",
                           not fired, {}))
    caught = sum(1 for item in planted if item["pass"])
    false_positives = sum(1 for item in controls if not item["pass"])
    return {"probes": planted + controls,
            "metric": {"value": caught / len(planted), "caught": caught,
                       "planted": len(planted),
                       "false_positives": false_positives,
                       "target": 1.0,
                       "pass": caught == len(planted) and false_positives == 0}}


# --- M8: advice-language leakage -----------------------------------------


def probe_scope(validate_fn=validate_output):
    """M8: eight planted scope violations (patterns the structural
    language guard does not cover) must drop with k6_scope; three
    benign controls must pass. Leaked is the count of planted
    violations the checks kept; target 0."""
    violations = [
        ("first-line-choice", "The first-line choice should be discussed."),
        ("dosing-unit", "The amount was 50 mg/day."),
        ("eligibility", "She is eligible for the study."),
        ("registry-match", "This matches NCT12345678."),
        ("prognosis", "What is her prognosis?"),
        ("you-have-condition", "You have cancer and should know."),
        ("should-consider", "We should consider the options."),
        ("ranking-options", "Rank the options by benefit."),
    ]
    planted = []
    for name, text in violations:
        result = _validate([_claim(text)], fixture_context(), validate_fn)
        drop = next((d for d in result.dropped if d.get("reason") == "k6_scope"), None)
        planted.append(_probe("M8", name, "drop k6_scope",
                              drop["reason"] if drop else "kept", drop is not None, {}))
    controls = []
    for name, text in [
            ("benign-match", "The scan matches the prior scan."),
            ("you-have-report", "You have the report in hand."),
            ("clean-claim", "The sources report a finding.")]:
        result = _validate([_claim(text)], fixture_context(), validate_fn)
        dropped = [d for d in result.dropped if d.get("reason") == "k6_scope"]
        controls.append(_probe("M8", name, "kept",
                               "drop k6_scope" if dropped else "kept",
                               not dropped, {}))
    caught = sum(1 for item in planted if item["pass"])
    leaked = len(planted) - caught
    false_positives = sum(1 for item in controls if not item["pass"])
    return {"probes": planted + controls,
            "metric": {"value": leaked, "leaked": leaked,
                       "planted": len(planted), "caught": caught,
                       "false_positives": false_positives,
                       "target": 0,
                       "pass": leaked == 0 and false_positives == 0}}


# --- M10: hypothesis support ---------------------------------------------


def probe_hypothesis(validate_fn=validate_output):
    """M10: six hypothesis probes — invented number, invented
    registry id, invented substance, low tier without the limits
    phrase must drop; a supported hypothesis and a low-tier
    hypothesis carrying the limits phrase must be kept."""
    cases = [
        ("invented-number", "The lesion measured 45 mm.", {"source_id": 2},
         "drop k7_unsupported_token", False),
        ("invented-registry-id", "See NCT12345678 for details.", {"source_id": 1},
         "drop k7_unsupported_token", False),
        ("invented-substance", "The note mentions fictional-substance-x.",
         {"source_id": 1}, "drop k7_unsupported_token", False),
        ("supported-number", "The lesion measured 31 mm.", {"source_id": 2},
         "kept", True),
        ("low-tier-without-phrase", "Marker A was not tested.", {"source_id": 1},
         "drop k7_tier_limits", False),
        ("low-tier-with-phrase", "Marker A was not tested.", {"source_id": 1},
         "kept", True),
    ]
    probes = []
    for name, text, claim_kwargs, expected, should_keep in cases:
        if name == "low-tier-without-phrase":
            context = fixture_context(evidence_tiers={1: "D"})
            claim = _claim(text, kind="hypothesis", **claim_kwargs)
        elif name == "low-tier-with-phrase":
            context = fixture_context(evidence_tiers={1: "D"})
            claim = _claim(text, kind="hypothesis",
                           limits="Synthetic only. " + TIER_LIMITS_PHRASE,
                           **claim_kwargs)
        else:
            context = fixture_context()
            claim = _claim(text, kind="hypothesis", **claim_kwargs)
        result = _validate([claim], context, validate_fn)
        if should_keep:
            outcome = "kept" if result.claims else (
                "drop " + result.dropped[0]["reason"] if result.dropped else "dropped")
            passed = bool(result.claims)
        else:
            reason = expected.split(" ", 1)[1]
            drop = next((d for d in result.dropped if d.get("reason") == reason), None)
            outcome = drop["reason"] if drop else (
                "kept" if result.claims else "drop " + (
                    result.dropped[0]["reason"] if result.dropped else "?"))
            passed = drop is not None
        probes.append(_probe("M10", name, expected, outcome, passed, {}))
    correct = sum(1 for item in probes if item["pass"])
    return {"probes": probes,
            "metric": {"value": correct / len(probes), "correct": correct,
                       "total": len(probes), "target": 1.0,
                       "pass": correct == len(probes)}}


# --- M28: hypothesis citation recall (prose attribution) -----------------


def check_prose_attribution(sentence: str, context, *, cited_sources,
                            cited_assessments=None):
    """M28: every checkable unit in a hypothesis sentence must be
    present in the slots of the claims it cites. Units: numbers,
    named substances (from the context vocabulary), temporal words,
    relation verbs, and hyphenated entities (which must name a slot
    field of a cited source). Returns the units found, the ones
    missing from the cited evidence, and the verdict. Deterministic,
    so gateable (OI-09 section 9.2); this is the check K7 cannot do —
    a sentence can carry a supported number and still say more than
    its claim (an unsupported relation verb or temporal word)."""
    cited = set(cited_sources or [])
    evidence_parts = []
    for slot in context.derived_slots:
        if slot.source_version_id in cited:
            evidence_parts.append(slot.quote)
            evidence_parts.append(slot.value)
            evidence_parts.append(slot.field)
    for assessment_id in (cited_assessments or []):
        evidence_parts.append(context.assessment_statements.get(assessment_id, ""))
    evidence_words = set(_words(" ".join(evidence_parts)))
    evidence_text = " ".join(evidence_parts)
    sentence_words = _words(sentence)
    units = []
    missing = []
    for number in _NUMBER_RE.findall(sentence):
        units.append({"kind": "number", "unit": number})
        if number not in evidence_words:
            missing.append({"kind": "number", "unit": number})
    for substance in context.substance_names:
        if substance.lower() in sentence.lower():
            units.append({"kind": "substance", "unit": substance})
            if substance.lower() not in evidence_text.lower():
                missing.append({"kind": "substance", "unit": substance})
    for word in _TEMPORAL_WORDS:
        if word in sentence_words:
            units.append({"kind": "temporal", "unit": word})
            if word not in evidence_words:
                missing.append({"kind": "temporal", "unit": word})
    for verb in _RELATION_VERBS:
        if verb in sentence_words:
            units.append({"kind": "relation", "unit": verb})
            if verb not in evidence_words:
                missing.append({"kind": "relation", "unit": verb})
    known_fields = {slot.field for slot in context.derived_slots}
    for entity in _ENTITY_RE.findall(sentence.lower()):
        units.append({"kind": "entity", "unit": entity})
        cited_fields = {slot.field for slot in context.derived_slots
                        if slot.source_version_id in cited}
        if entity not in known_fields or entity not in cited_fields:
            missing.append({"kind": "entity", "unit": entity})
    return {"pass": not missing, "units": units, "missing": missing}


def probe_prose_attribution(validate_fn=validate_output):
    """M28: six probe sentences that the K-checks keep, judged by
    the attribution check. Two are fully attributed; three carry a
    unit the cited evidence does not support (a relation verb, a
    temporal word, an unknown entity) — the units K7 cannot see. The
    check must judge all six correctly; the response-level rate is
    the share of probe responses (one response here) whose sentences
    are all judged correctly."""
    sentences = [
        ("supported-measurement", "The lesion was measured as 31 mm.",
         {"sources": {2}}, True),
        ("unsupported-relation-verb", "The lesion increased to 31 mm.",
         {"sources": {2}}, False),
        ("supported-marker", "Marker A was not tested.",
         {"sources": {1}}, True),
        ("unsupported-temporal", "The lesion was measured as 31 mm after treatment.",
         {"sources": {2}}, False),
        ("unknown-entity", "The marker-b value was reported.",
         {"sources": {1}}, False),
        ("no-checkable-units", "The examination identified a finding.",
         {"sources": {1}}, True),
    ]
    probes = []
    for name, text, cited, should_pass in sentences:
        context = fixture_context()
        source_id = next(iter(cited["sources"]))
        validated = _validate(
            [_claim(text, kind="hypothesis", source_id=source_id)],
            context, validate_fn)
        if not validated.claims:
            probes.append(_probe(
                "M28", name, "kept, then judged",
                "dropped by K-checks: " + (
                    validated.dropped[0]["reason"] if validated.dropped else "?"),
                False, {"cited": sorted(cited["sources"])}))
            continue
        checked = check_prose_attribution(
            text, context, cited_sources=cited["sources"])
        outcome = "attributed" if checked["pass"] else (
            "missing " + ", ".join(
                item["unit"] for item in checked["missing"]))
        probes.append(_probe(
            "M28", name,
            "attributed" if should_pass else "not attributed",
            outcome, checked["pass"] == should_pass,
            {"cited": sorted(cited["sources"]),
             "units": [item["unit"] for item in checked["units"]],
             "missing": [item["unit"] for item in checked["missing"]]}))
    correct = sum(1 for item in probes if item["pass"])
    return {"probes": probes,
            "metric": {"value": correct / len(probes), "correct": correct,
                       "total": len(probes),
                       "response_level": 1.0 if correct == len(probes) else 0.0,
                       "target": 1.0,
                       "pass": correct == len(probes)}}


# --- Skeptic wiring probe (C4 fixture, stub verdict) ---------------------


def _stub_call(payload):
    """A stub model call returning one canned verdict per claim."""
    def call(prompt):
        return {"reviews": [
            {"claim_index": index, "verdict": verdict,
             "reason": f"stub review {index}: {verdict}"}
            for index, verdict in enumerate(payload)]}
    return call


def probe_skeptic_wiring(validate_fn=validate_output):
    """The C4 planted misstatement, end to end through the
    verification wiring: "31 cm" against evidence "31 mm" passes
    K1–K7 by construction, and a stub Skeptic verdict of
    "challenged" must hold it with AB-CONFLICT origin
    skeptic_challenge; a stub "supported" on the true "31 mm" claim
    must keep it. This proves the wiring, not the model — the
    verdicts are injected, so no live call runs and ``model_calls``
    stays 0."""
    probes = []
    facts = {"valid_sources": set(_VALID_SOURCES),
             "valid_assessments": set(_VALID_ASSESSMENTS)}
    context = fixture_context()
    validated = _validate(
        [_claim("The lesion was measured as 31 cm.", source_id=2)],
        context, validate_fn)
    premise = len(validated.claims) == 1 and not validated.dropped
    probes.append(_probe(
        "skeptic", "misstatement-passes-kchecks",
        "kept by K1-K7 (1 claim, 0 dropped)",
        f"{len(validated.claims)} kept, {len(validated.dropped)} dropped",
        premise, {}))
    record = run_verification(
        validated, context, facts, mode="live",
        skeptic_call=_stub_call(["challenged"]),
        repair_call=_stub_call([]))
    held = next((d for d in validated.dropped
                 if d.get("reason") == "skeptic_challenged"), None)
    codes = [code for code in record.get("abstention_codes", [])
             if code.get("code") == "AB-CONFLICT"]
    probes.append(_probe(
        "skeptic", "challenged-claim-held",
        "dropped skeptic_challenged + AB-CONFLICT origin skeptic_challenge",
        "held" if held else "kept",
        held is not None and [c.get("origin") for c in codes] == ["skeptic_challenge"],
        {"abstention_codes": codes,
         "skeptic_status": record.get("skeptic", {}).get("status")}))
    context = fixture_context()
    validated = _validate(
        [_claim("The lesion was measured as 31 mm.", source_id=2)],
        context, validate_fn)
    record = run_verification(
        validated, context, facts, mode="live",
        skeptic_call=_stub_call(["supported"]),
        repair_call=_stub_call([]))
    probes.append(_probe(
        "skeptic", "supported-claim-kept", "kept, no abstention codes",
        f"{len(validated.claims)} kept",
        len(validated.claims) == 1 and not record.get("abstention_codes"),
        {"abstention_codes": record.get("abstention_codes", [])}))
    return {"probes": probes}


# --- M16 / M27: replay determinism + routing completeness ---------------


def _seed_store():
    """A real in-memory store with one fictional case, one imported
    source, and one question — the same seeding the C1 replay tests
    use."""
    store = CaseStore(":memory:")
    store.add_case("CASE-ALPHA", "Fictional case CASE-ALPHA")
    synthetic = Path(__file__).resolve().parents[2] / "examples" / "synthetic"
    source_id = store.import_report(
        "CASE-ALPHA", (synthetic / "alpha-pathology-original.txt").read_bytes()
    )["source_id"]
    question_id = store.add_question("CASE-ALPHA", "What does the source report?")
    return store, source_id, question_id


def _save_replay_run(store, case_id, question_id, source_id, *, route=True):
    """Save one completed replay investigation with its write
    contract. The route is decided first (program plan C3): a run
    without a route.decided record is not reproducible."""
    if route:
        decide_route(store, case_id, "evidence-summary", question_id, "clinician")
    facts = store.investigation_facts(case_id, question_id)
    validated = validate_output(
        {"claims": [_claim("The sources report a finding.", source_id=source_id)],
         "abstentions": []},
        facts["valid_sources"], facts["valid_assessments"])
    validated.model = "recorded-replay"
    validated.mode = "replay"
    contract = build_investigation_contract(
        store, case_id, question_id, "evidence-summary", "recorded-replay",
        facts=facts)
    run_id = store.save_investigation(
        case_id, question_id, "evidence-summary", validated, "replay",
        write_contract=contract)
    return run_id, contract


def _route_decisions_before_run(store, case_id, route_id, investigation_id):
    """Count route.decided events for a route that precede the run's
    investigation_created event. Exactly one is the M27 bar."""
    rows = store.db.execute(
        "SELECT id, kind, details FROM events WHERE case_id=? ORDER BY id",
        (case_id,)).fetchall()
    run_event_id = None
    decisions = 0
    for row in rows:
        details = json.loads(row[2])
        if row[1] == "investigation_created" and details.get("investigation_id") == investigation_id:
            run_event_id = int(row[0])
    for row in rows:
        if run_event_id is None or int(row[0]) >= run_event_id:
            continue
        if row[1] != "route.decided":
            continue
        details = json.loads(row[2])
        if details.get("routeId") == route_id:
            decisions += 1
    return decisions


def probe_route_replay():
    """M16 + M27, against real stores. M16: one intact run replayed
    three times must return identical results; three tamper probes
    (missing route, amended source, tampered assertion) must each
    fail replay with a typed reason. M27: the intact run's route
    must have exactly one route.decided before its agent events;
    the missing-route run is the negative control (0 decisions)."""
    probes = []
    store, source_id, question_id = _seed_store()
    try:
        run_id, contract = _save_replay_run(store, "CASE-ALPHA", question_id, source_id)
        results = [check_replay(store, "CASE-ALPHA", run_id) for _ in range(3)]
        identical = sum(1 for result in results if result == results[0])
        probes.append(_probe(
            "M16", "identical-replays", "3 identical replays",
            f"{identical}/3 identical, reproducible={results[0].get('reproducible')}",
            identical == 3 and results[0].get("reproducible") is True,
            {"writeId": results[0].get("writeId"),
             "routeId": results[0].get("routeId"),
             "checked_inputs": results[0].get("checked_inputs")}))
        decisions = _route_decisions_before_run(
            store, "CASE-ALPHA", contract["routeId"], run_id)
        probes.append(_probe(
            "M27", "one-route-decided", "exactly 1 route.decided before the run",
            f"{decisions} route.decided", decisions == 1,
            {"routeId": contract["routeId"]}))
    finally:
        store.close()
    # Tamper probes, each on its own store so they cannot interfere.
    store, source_id, question_id = _seed_store()
    try:
        run_id, _ = _save_replay_run(
            store, "CASE-ALPHA", question_id, source_id, route=False)
        result = check_replay(store, "CASE-ALPHA", run_id)
        probes.append(_probe(
            "M16", "missing-route-fails-replay", "not reproducible, missing_route",
            f"reproducible={result.get('reproducible')}, reason={result.get('reason')}",
            result.get("reproducible") is False and result.get("reason") == "missing_route",
            {}))
        decisions = _route_decisions_before_run(
            store, "CASE-ALPHA",
            build_route_id("CASE-ALPHA", "evidence-summary", question_id), run_id)
        probes.append(_probe(
            "M27", "missing-route-control", "0 route.decided (negative control)",
            f"{decisions} route.decided", decisions == 0, {}))
    finally:
        store.close()
    store, source_id, question_id = _seed_store()
    try:
        run_id, _ = _save_replay_run(store, "CASE-ALPHA", question_id, source_id)
        synthetic = Path(__file__).resolve().parents[2] / "examples" / "synthetic"
        store.import_report(
            "CASE-ALPHA", (synthetic / "alpha-pathology-amended.txt").read_bytes())
        result = check_replay(store, "CASE-ALPHA", run_id)
        probes.append(_probe(
            "M16", "amended-source-fails-replay", "not reproducible, stale_snapshot",
            f"reproducible={result.get('reproducible')}, reason={result.get('reason')}",
            result.get("reproducible") is False and result.get("reason") == "stale_snapshot",
            {}))
    finally:
        store.close()
    store, source_id, question_id = _seed_store()
    try:
        run_id, _ = _save_replay_run(store, "CASE-ALPHA", question_id, source_id)
        store.db.execute(
            "UPDATE assertions SET quote='Tampered quotation.' WHERE id IN "
            "(SELECT id FROM assertions WHERE case_id=?)", ("CASE-ALPHA",))
        store.db.commit()
        result = check_replay(store, "CASE-ALPHA", run_id)
        probes.append(_probe(
            "M16", "tampered-input-fails-replay", "not reproducible, inputs_changed",
            f"reproducible={result.get('reproducible')}, reason={result.get('reason')}",
            result.get("reproducible") is False and result.get("reason") == "inputs_changed",
            {}))
    finally:
        store.close()
    m16 = [item for item in probes if item["family"] == "M16"]
    m27 = [item for item in probes if item["family"] == "M27"]
    identical_probe = next(item for item in m16 if item["name"] == "identical-replays")
    # M16 value is the identical-replay count over 3 replays.
    identical_count = 3 if identical_probe["pass"] else 0
    m27_good = next(item for item in m27 if item["name"] == "one-route-decided")
    return {
        "probes": probes,
        "m16": {"value": identical_count / 3, "identical": identical_count,
                "replays": 3, "target": 1.0,
                "pass": identical_count == 3 and all(
                    item["pass"] for item in m16)},
        "m27": {"value": 1.0 if m27_good["pass"] else 0.0, "complete": 1 if m27_good["pass"] else 0,
                "runs": 1, "target": 1.0, "pass": m27_good["pass"]},
    }


# --- Spot-check set --------------------------------------------------------


def record_spot_check_set(items):
    """Record a human spot-check set (OI-09 section 9.9 rule 5).
    The harness records the set; it does not perform it. Items carry
    an id and an optional human label; unlabelled items are pending.
    A set is complete at >=30 items. Returns the recorded set."""
    recorded = []
    for item in items:
        recorded.append({
            "id": item.get("id"),
            "kind": item.get("kind", "probe"),
            "label": item.get("label", "pending"),
        })
    labelled = sum(1 for item in recorded if item["label"] != "pending")
    return {
        "items": recorded,
        "count": len(recorded),
        "labelled": labelled,
        "labels_pending": len(recorded) - labelled,
        "complete": len(recorded) >= SPOT_CHECK_MINIMUM,
        "minimum": SPOT_CHECK_MINIMUM,
    }


# --- Suite runner ----------------------------------------------------------


def run_evaluation_suite(validate_fn=validate_output):
    """Run every probe family and compute the M-metrics. Returns a
    JSON-ready report: metric, value, n, target, pass/fail per metric
    (OI-09 section 9.9 rule 7), the probe items, the spot-check set,
    and failures listed as limits, never hidden. No live model call
    is made; ``model_calls`` is always 0. ``validate_fn`` is
    injectable so the sensitivity test can weaken a check and prove
    the harness fails."""
    temporal = probe_temporal(validate_fn)
    contradiction = probe_contradiction(validate_fn)
    staleness = probe_staleness(validate_fn)
    scope = probe_scope(validate_fn)
    hypothesis = probe_hypothesis(validate_fn)
    prose = probe_prose_attribution(validate_fn)
    skeptic = probe_skeptic_wiring(validate_fn)
    route_replay = probe_route_replay()
    probes = (temporal["probes"] + contradiction["probes"]
              + staleness["probes"] + scope["probes"]
              + hypothesis["probes"] + prose["probes"]
              + skeptic["probes"] + route_replay["probes"])
    metrics = {
        "M5": temporal["metric"],
        "M6": contradiction["metric"],
        "M7": staleness["metric"],
        "M8": scope["metric"],
        "M10": hypothesis["metric"],
        "M16": route_replay["m16"],
        "M27": route_replay["m27"],
        "M28": prose["metric"],
    }
    spot_check = record_spot_check_set([
        {"id": f"{item['family']}/{item['name']}", "kind": item["family"]}
        for item in probes])
    failures = [
        {"metric": metric_id, "value": metric["value"],
         "target": metric["target"],
         "detail": f"{metric_id} did not meet its Proposed target"}
        for metric_id, metric in metrics.items() if not metric["pass"]]
    wiring_failed = [item for item in skeptic["probes"] if not item["pass"]]
    if wiring_failed:
        failures.append({
            "metric": "skeptic-wiring",
            "value": f"{len(skeptic['probes']) - len(wiring_failed)}/{len(skeptic['probes'])} probes",
            "target": "all wiring probes pass",
            "detail": "Skeptic verification wiring failed: "
                      + ", ".join(item["name"] for item in wiring_failed)})
    return {
        "harness": HARNESS_VERSION,
        "mode": "offline-deterministic",
        "model_calls": 0,
        "metrics": metrics,
        "probes": probes,
        "spot_check": spot_check,
        "not_measured": [
            {"metric": "M25", "reason": "model-judged entailment; needs live runs and human labels"},
            {"metric": "M26", "reason": "Skeptic challenge precision; needs live Skeptic challenges confirmed by K-checks"},
            {"metric": "M29", "reason": "citation precision; needs live model output"},
        ],
        "passed": not failures,
        "failures": failures,
        "notes": [
            "The Skeptic probe uses injected stub verdicts (wiring proof only); a live-model run proving the real model catches the planted misstatement is pending the Meta billing fix (HTTP 402).",
            "SOURCES_DISAGREE (Notion) is surfaced here as a T6 contradiction group plus AB-CONFLICT with origin agent_divergence; the literal label does not exist in the codebase.",
            "The harness measures; it never gates (OI-09 section 9).",
        ],
    }


def main(argv=None):
    """Run the suite and print the JSON report. Exit 0 when every
    metric meets its Proposed target, 1 otherwise."""
    report = run_evaluation_suite()
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0 if report["passed"] else 1


if __name__ == "__main__":
    sys.exit(main())
