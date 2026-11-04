"""Read-only consolidated case packet, composed from existing projections.

The packet assembles one printable, downloadable view from builders already
in the codebase. It never re-derives workflow state, timeline ordering,
change diffs, option deadlines, or investigation validation: it calls the
existing callables and assembles their outputs.

Composition (all case-scoped, all read-only):
- ``CaseStore.state()`` for the canonical ledger snapshot (sources,
  assertions, questions, snapshots, evidence assessments, broker links,
  biological assets, quarantines, events, options via ``option_view``).
- ``build_patient_mission(state)`` for journey stage, reported findings,
  unresolved items, material changes, next actions, and guardrails. The
  mission is derived from the same ``state()`` snapshot, so citations are
  identical to the individual mission view.
- ``case_timeline(store, case_id)`` for journey chronology, gaps,
  conflicts, history, and the ledger position (``as_of``).
- ``changes_since_review(store, case_id)`` for review receipts: anchor,
  new sources, amendments with mechanical diffs, stale investigations
  with cause, and new questions.
- ``list_investigations`` + ``get_investigation`` for model hypotheses,
  each labeled ``kind=hypothesis`` and ``review_state=pending``,
  kept visibly separate from human drafts and reported facts.
- ``case_discovery_links`` for case-scoped discovery applicability.

Requested slice names map to existing builders without new derivation:
patient report sections use the mission's ``what_we_know`` (source
statements with version and line anchors); goals use durable
``questions``; follow-ups use the mission's ``next_actions`` plus
unresolved items and material changes; review receipts use snapshots
with review states plus the changes projection; journey stage uses
the mission's ``workflow_status``/``where_am_i`` plus the timeline's
``as_of`` chronology.

Global catalogs (``evidence_versions``, ``rights_sources``,
``discovery_items``) are shared across cases and are not case data, so
the packet excludes them to preserve strict case isolation. Case-scoped
links to them (assessments, broker links, discovery links) are included
with their anchors.

Every record carries its existing source anchor and review state.
Amendments supersede, never delete: superseded versions appear in
timeline history, stale dependents stay flagged. Unknowns stay unknown;
pending stays pending. Fictional/demo marking appears on every
page-equivalent block in both JSON and text forms.

Each section is individually consistent from its own builder; a
concurrent amendment may advance the ledger between section reads.
The cover reports the timeline's ``as_of`` ledger position so the
packet's position is explicit.
"""

from __future__ import annotations

from .changes import changes_since_review
from .mission import build_patient_mission
from .timeline import case_timeline

FICTIONAL_MARKING = "FICTIONAL DEMO DATA — not a real patient"

GENERATED_FROM = (
    "Composed from CaseStore.state(), Patient Mission, Timeline, "
    "Changes-since-review, Options, Investigations; no re-derivation. "
    "Each section reuses its existing builder's citations."
)

LIMITATIONS = [
    "Unknowns stay unknown: gaps, conflicts, and missing records are reported, never filled by inference.",
    "Pending stays pending: pending, indeterminate, not-reported, and not-assessed states remain distinct.",
    "Hypotheses are separate from facts: model investigations are labeled kind=hypothesis, review_state=pending.",
    "Demo review is not clinical review: acknowledgments do not establish clinician identity or approval.",
    "Amendments supersede, never delete: superseded versions remain in history with stale dependents flagged.",
    "Fictional synthetic data only: no real patient, no treatment recommendation, physician authority preserved.",
]


def build_case_packet(store, case_id: str) -> dict:
    """Build one case packet by composing existing projections.

    Reads only; writes nothing. Raises ``InvalidInput("Unknown case")``
    for unknown cases via the existing store boundary.
    """
    state = store.state(case_id)
    mission = build_patient_mission(state)
    timeline = case_timeline(store, case_id)
    changes = changes_since_review(store, case_id)
    investigations = [
        store.get_investigation(case_id, row["id"])
        for row in store.list_investigations(case_id)
    ]
    discovery_links = store.case_discovery_links(case_id)

    as_of = timeline.get("as_of", {})
    cover = {
        "case_id": state["case"]["case_id"],
        "label": state["case"]["label"],
        "fictional_marking": FICTIONAL_MARKING,
        "synthetic": True,
        "scope": "synthetic_workflow_only",
        "generated_from": GENERATED_FROM,
        "report_position": {
            "as_of_event_id": as_of.get("event_id"),
            "as_of_occurred_at": as_of.get("occurred_at"),
            "source_count": len(state.get("sources", [])),
            "assertion_count": len(state.get("assertions", [])),
            "question_count": len(state.get("questions", [])),
            "snapshot_count": len(state.get("snapshots", [])),
        },
    }
    return {
        "synthetic": True,
        "fictional_marking": FICTIONAL_MARKING,
        "cover": cover,
        "journey_stage": {
            "fictional_marking": FICTIONAL_MARKING,
            "workflow_status": mission["workflow_status"],
            "where_am_i": mission["where_am_i"],
            "as_of": timeline.get("as_of"),
        },
        "reported_findings": {
            "fictional_marking": FICTIONAL_MARKING,
            "items": mission["what_we_know"],
            "count": len(mission["what_we_know"]),
        },
        "timeline": {
            "fictional_marking": FICTIONAL_MARKING,
            "entries": timeline["entries"],
            "gaps": timeline["gaps"],
            "conflicts": timeline["conflicts"],
            "history": timeline["history"],
            "counts": timeline["counts"],
            "disclaimer": timeline["disclaimer"],
            "as_of": timeline["as_of"],
        },
        "questions": {
            "fictional_marking": FICTIONAL_MARKING,
            "items": state.get("questions", []),
        },
        "investigations": {
            "fictional_marking": FICTIONAL_MARKING,
            "snapshots": state.get("snapshots", []),
            "model_investigations": investigations,
            "note": (
                "Human drafts and model hypotheses are separate. "
                "Hypotheses are unreviewed, fictional-data based, "
                "and not medical advice."
            ),
        },
        "evidence": {
            "fictional_marking": FICTIONAL_MARKING,
            "assessments": state.get("evidence_assessments", []),
            "broker_links": state.get("broker_links", []),
            "discovery_links": discovery_links,
        },
        "sources": {
            "fictional_marking": FICTIONAL_MARKING,
            "items": state.get("sources", []),
            "quarantines": state.get("quarantines", []),
        },
        "activity": {
            "fictional_marking": FICTIONAL_MARKING,
            "items": state.get("events", []),
        },
        "changes_since_review": {
            "fictional_marking": FICTIONAL_MARKING,
            "anchor": changes["anchor"],
            "counts": changes["counts"],
            "new_sources": changes["new_sources"],
            "amendments": changes["amendments"],
            "stale_investigations": changes["stale_investigations"],
            "new_questions": changes["new_questions"],
            "disclaimer": changes["disclaimer"],
        },
        "options": {
            "fictional_marking": FICTIONAL_MARKING,
            "items": state.get("options", []),
            "disclaimer": state.get("option_disclaimer", ""),
        },
        "follow_ups": {
            "fictional_marking": FICTIONAL_MARKING,
            "next_actions": mission["next_actions"],
            "unresolved": mission["what_remains_unresolved"],
            "material_changes": mission["material_changes"],
        },
        "biological_assets": {
            "fictional_marking": FICTIONAL_MARKING,
            "assets": state.get("biological_assets", []),
            "inventory_assertions": state.get(
                "biological_inventory_assertions", []
            ),
        },
        "limitations": {
            "fictional_marking": FICTIONAL_MARKING,
            "items": list(LIMITATIONS),
            "guardrails": mission["guardrails"],
        },
    }


def _lines_for(label: str, lines: list[str]) -> list[str]:
    """One page-equivalent block, always headed by the fictional marking."""
    return [FICTIONAL_MARKING, label, *lines, ""]


def render_packet_text(packet: dict) -> str:
    """Render a packet as clean plain text with no markup.

    Every block starts with the fictional/demo marking. Empty sections
    state their emptiness in plain words; nothing is invented. Source
    quotations appear verbatim as plain lines. The formatter itself
    emits no angle brackets, fences, or emphasis characters.
    """
    out: list[str] = []
    cover = packet.get("cover", {})
    position = cover.get("report_position", {})
    out.extend(_lines_for(
        "CASE PACKET",
        [
            "Case: " + str(cover.get("case_id", "unknown"))
            + " (" + str(cover.get("label", "")) + ")",
            "Scope: " + str(cover.get("scope", "synthetic_workflow_only")),
            "Generated from: " + str(cover.get("generated_from", GENERATED_FROM)),
            "Report position: event "
            + str(position.get("as_of_event_id"))
            + " at " + str(position.get("as_of_occurred_at"))
            + " | sources: " + str(position.get("source_count"))
            + ", statements: " + str(position.get("assertion_count"))
            + ", questions: " + str(position.get("question_count"))
            + ", drafts: " + str(position.get("snapshot_count")),
        ],
    ))

    journey = packet.get("journey_stage", {})
    where = journey.get("where_am_i", {})
    out.extend(_lines_for(
        "JOURNEY STAGE",
        [
            "Workflow status: " + str(journey.get("workflow_status", "unknown")),
            "Current source documents: " + str(where.get("current_source_documents", 0)),
            "Source-reported statements: " + str(where.get("reported_statements", 0)),
            "Open questions: " + str(where.get("open_questions", 0)),
            "Stale investigations: " + str(where.get("stale_investigations", 0)),
            "Quarantined deliveries: " + str(where.get("quarantined_deliveries", 0)),
            "Latest source event date: " + str(where.get("latest_source_event_date")),
        ],
    ))

    findings = packet.get("reported_findings", {}).get("items", [])
    if not findings:
        finding_lines = ["No reported findings yet in this fictional case."]
    else:
        finding_lines = []
        for item in findings:
            finding_lines.append(
                str(item.get("finding_key", ""))
                + " (" + str(item.get("state", "")) + "): "
                + str(item.get("statement", ""))
                + " [source version "
                + str(item.get("source_version_id"))
                + ", line " + str(item.get("source_line")) + "]"
            )
    out.extend(_lines_for("REPORTED FINDINGS", finding_lines))

    timeline = packet.get("timeline", {})
    entries = timeline.get("entries", [])
    if not entries:
        timeline_lines = ["No source events in this fictional case."]
    else:
        timeline_lines = []
        for entry in entries:
            timeline_lines.append(
                str(entry.get("occurred", "")) + " " + str(entry.get("document_id", ""))
                + " version " + str(entry.get("version", ""))
                + ", " + str(entry.get("kind", ""))
                + " [source " + str(entry.get("source_id")) + "]"
            )
    for gap in timeline.get("gaps", []):
        timeline_lines.append(
            "Gap with unknown coverage: " + str(gap.get("start_date", ""))
            + " to " + str(gap.get("end_date", ""))
        )
    for conflict in timeline.get("conflicts", []):
        timeline_lines.append(
            "Conflict stays unknown: " + str(conflict.get("conflict_key", ""))
            + " asserts " + ", ".join(str(x) for x in conflict.get("asserted_occurred_dates", []))
        )
    for historic in timeline.get("history", []):
        timeline_lines.append(
            "Superseded history, kept: " + str(historic.get("document_id", ""))
            + " version " + str(historic.get("version", ""))
            + " [source " + str(historic.get("source_id")) + "]"
        )
    out.extend(_lines_for("TIMELINE", timeline_lines))

    questions = packet.get("questions", {}).get("items", [])
    if not questions:
        question_lines = ["No questions recorded in this fictional case."]
    else:
        question_lines = [
            "Q" + str(item.get("id", "")) + " (" + str(item.get("state", "")) + "): "
            + str(item.get("question", ""))
            for item in questions
        ]
    out.extend(_lines_for("QUESTIONS", question_lines))

    investigations = packet.get("investigations", {})
    snapshots = investigations.get("snapshots", [])
    models = investigations.get("model_investigations", [])
    if not snapshots and not models:
        investigation_lines = ["No investigation drafts or hypotheses in this fictional case."]
    else:
        investigation_lines = []
        for snap in snapshots:
            investigation_lines.append(
                "Draft " + str(snap.get("id", "")) + " (" + str(snap.get("state", "")) + "): "
                + str(snap.get("summary", ""))
                + " [question " + str(snap.get("question_id")) + "]"
            )
        for model in models:
            stale_note = ", stale" if model.get("stale") else ""
            investigation_lines.append(
                "Hypothesis " + str(model.get("id", ""))
                + ", pending review, " + str(model.get("template", ""))
                + ", " + str(model.get("status", ""))
                + ", mode " + str(model.get("mode", ""))
                + stale_note
                + " [question " + str(model.get("question_id")) + "]"
            )
            for claim in model.get("claims", []):
                cites = ", ".join(
                    str(c.get("type", "")) + " " + str(c.get("id", ""))
                    for c in claim.get("citations", [])
                )
                investigation_lines.append(
                    "  Claim (" + str(claim.get("uncertainty", "")) + " uncertainty, cited: "
                    + cites + "): " + str(claim.get("text", ""))
                )
            for abstention in model.get("abstentions", []):
                investigation_lines.append(
                    "  Abstained on " + str(abstention.get("topic", ""))
                    + " because " + str(abstention.get("reason", ""))
                )
    out.extend(_lines_for("INVESTIGATIONS, DRAFTS AND HYPOTHESES", investigation_lines))

    evidence = packet.get("evidence", {})
    assessments = evidence.get("assessments", [])
    evidence_lines: list[str] = []
    if not assessments:
        evidence_lines.append("No fictional evidence assessments linked to this case.")
    else:
        for item in assessments:
            evidence_lines.append(
                str(item.get("evidence_key", "")) + " version "
                + str(item.get("version", "")) + " (" + str(item.get("evidence_state", "")) + ")"
                + ", Q" + str(item.get("question_id", ""))
                + ", " + str(item.get("relation", "")) + ", " + str(item.get("applicability", ""))
                + " [assessment " + str(item.get("id")) + "]"
            )
    for link in evidence.get("broker_links", []):
        evidence_lines.append(
            "Broker link " + str(link.get("id", ""))
            + ", Q" + str(link.get("question_id", ""))
            + ", " + str(link.get("relation", ""))
            + ", " + str(link.get("applicability", ""))
            + ", mode " + str(link.get("mode", ""))
            + ", rights " + str(link.get("rights_state", ""))
        )
    for link in evidence.get("discovery_links", []):
        item = link.get("item", {}) if isinstance(link.get("item"), dict) else {}
        evidence_lines.append(
            "Discovery link " + str(link.get("link_id", ""))
            + ", Q" + str(link.get("question_id", ""))
            + ", " + str(item.get("discovery_key", ""))
            + ", " + str(link.get("applicability", ""))
            + " (" + str(link.get("state", "")) + ")"
        )
    out.extend(_lines_for("EVIDENCE ASSESSMENTS", evidence_lines))

    sources = packet.get("sources", {})
    source_items = sources.get("items", [])
    if not source_items:
        source_lines = ["No source documents in this fictional case."]
    else:
        source_lines = [
            str(item.get("document_id", "")) + " version "
            + str(item.get("version", "")) + " (" + str(item.get("state", "")) + ")"
            + ", event " + str(item.get("event_date", ""))
            + " [source " + str(item.get("id")) + "]"
            for item in source_items
        ]
    for quarantine in sources.get("quarantines", []):
        source_lines.append(
            "Quarantined delivery " + str(quarantine.get("id", ""))
            + " for " + str(quarantine.get("reason", ""))
            + ": no assertions imported."
        )
    out.extend(_lines_for("SOURCES AND QUARANTINE", source_lines))

    changes = packet.get("changes_since_review", {})
    anchor = changes.get("anchor", {})
    change_lines = [
        "Anchor: event " + str(anchor.get("event_id", ""))
        + " (" + str(anchor.get("kind", "")) + ") at "
        + str(anchor.get("occurred_at", "")),
    ]
    if not changes.get("new_sources") and not changes.get("amendments") \
            and not changes.get("stale_investigations") and not changes.get("new_questions"):
        change_lines.append("No ledger changes recorded after the anchor event.")
    for item in changes.get("new_sources", []):
        change_lines.append(
            "New source: " + str(item.get("document_id", ""))
            + " version " + str(item.get("version", ""))
            + " [source " + str(item.get("source_id")) + "]"
        )
    for item in changes.get("amendments", []):
        change_lines.append(
            "Amendment: " + str(item.get("document_id", ""))
            + " version " + str(item.get("superseded_version", ""))
            + " to " + str(item.get("version", ""))
            + " [source " + str(item.get("source_id")) + "]"
        )
    for item in changes.get("stale_investigations", []):
        change_lines.append(
            "Stale investigation " + str(item.get("snapshot_id", ""))
            + " (" + str(item.get("current_state", "")) + ")"
        )
    for item in changes.get("new_questions", []):
        change_lines.append(
            "New question Q" + str(item.get("question_id", ""))
            + ": " + str(item.get("question", ""))
        )
    out.extend(_lines_for("CHANGES SINCE REVIEW", change_lines))

    options = packet.get("options", {}).get("items", [])
    if not options:
        option_lines = ["No options proposed for this case yet."]
    else:
        option_lines = [
            "Option " + str(item.get("id", "")) + ": " + str(item.get("label", ""))
            + " (" + str(item.get("derived_epistemic_status", ""))
            + ", " + str(item.get("display_operational_status", ""))
            + ", review " + str(item.get("review_state", "")) + ")"
            for item in options
        ]
    out.extend(_lines_for("OPTIONS AND DEPENDENCIES", option_lines))

    follow = packet.get("follow_ups", {})
    actions = follow.get("next_actions", [])
    if not actions:
        follow_lines = ["No bounded workflow action is available."]
    else:
        follow_lines = [
            str(item.get("label", "")) + ": " + str(item.get("reason", ""))
            for item in actions
        ]
    out.extend(_lines_for("FOLLOW UPS", follow_lines))

    bio = packet.get("biological_assets", {})
    assets = bio.get("assets", [])
    assertions = bio.get("inventory_assertions", [])
    if not assets and not assertions:
        bio_lines = ["No biological assets recorded for this case."]
    else:
        bio_lines = []
        for asset in assets:
            bio_lines.append(
                str(asset.get("asset_id", "")) + " (" + str(asset.get("kind", "")) + ")"
                + ", episode " + str(asset.get("episode_id", ""))
                + " [asset " + str(asset.get("id")) + "]"
            )
        for assertion in assertions:
            bio_lines.append(
                "Inventory assertion " + str(assertion.get("id", ""))
                + " (" + str(assertion.get("state", "")) + ")"
                + " by " + str(assertion.get("asserted_by", ""))
                + " [asset " + str(assertion.get("asset_id"))
                + ", source " + str(assertion.get("source_version_id")) + "]"
            )
    out.extend(_lines_for("BIOLOGICAL ASSETS", bio_lines))

    activity = packet.get("activity", {}).get("items", [])
    if not activity:
        activity_lines = ["No ledger activity recorded for this case."]
    else:
        activity_lines = [
            str(item.get("kind", "")).replace("_", " ")
            + " at " + str(item.get("occurred_at", ""))
            + " [event " + str(item.get("id")) + "]"
            for item in activity
        ]
    out.extend(_lines_for("RECENT ACTIVITY", activity_lines))

    limitations = packet.get("limitations", {})
    limitation_lines = [str(item) for item in limitations.get("items", [])]
    for guardrail in limitations.get("guardrails", []):
        limitation_lines.append(str(guardrail))
    if not limitation_lines:
        limitation_lines = ["No limitations recorded."]
    out.extend(_lines_for("LIMITATIONS", limitation_lines))

    text = "\n".join(out).strip() + "\n"
    return text
