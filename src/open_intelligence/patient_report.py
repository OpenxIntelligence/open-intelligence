"""Deterministic plain-language patient/caregiver report projection.

The report renders recorded case data only: it assembles overview, timeline
highlights, open questions, option portfolio status, and goals from a
``CaseStore.state()`` snapshot plus the embedded option projection. It adds
no facts, performs no inference, calls no model, and writes nothing.

Language boundary: the report's own framing sentences are fixed templates
checked by ``REPORT_GUARDS`` at build time (fail closed). Recorded entries
(source quotes, question text, option labels) appear verbatim as attributed
quotations so provenance is preserved exactly; they are the case record
speaking, not the report interpreting it.
"""

from __future__ import annotations

import re

FICTIONAL_BANNER = (
    "Fictional demo report. This is not a real patient file, "
    "not clinical advice, and not reviewed by a clinician."
)

READING_NOTE = (
    "This report lists what the case record contains, in plain words. "
    "Where the record is silent, the report says so instead of guessing. "
    "Items marked pending or unknown are not settled."
)

NO_SOURCE_NOTE = "No source is recorded for this entry."

# Findings states from the ledger, in plain words. Pending and unknown
# states stay visibly pending/unknown; nothing is smoothed over.
CERTAINTY_PLAIN = {
    "reported": "reported",
    "negative": "reported as not found",
    "pending": "pending",
    "indeterminate": "not certain yet",
    "not-reported": "not reported",
    "not-assessed": "not assessed",
    "conflicting": "reports disagree",
}

EPISTEMIC_PLAIN = {
    "supported": "supported (human-labelled)",
    "contradicted": "contradicted (held back from use)",
    "unsupported": "unsupported",
    "unknown": "unknown",
}

OPERATIONAL_PLAIN = {
    "proposed": "proposed (under discussion)",
    "reviewed": "reviewed in demo (demo only, not clinical)",
    "held": "held (waiting)",
    "rejected": "rejected",
    "withdrawn": "withdrawn",
    "expired": "expired",
}

# Fixed detail skeletons. Recorded values fill the slots; the surrounding
# words are report voice and are scanned by test alongside the framing.
DETAIL_FINDING = "Finding {finding_key}; source states: {plain} ({certainty})."
TIMELINE_ENTRY_TEXT = (
    "On {event_date}, a {kind} report ({document_id}, version {version}) "
    "was recorded. It was finalized on {issued_at}."
)
TIMELINE_ENTRY_DETAIL = (
    "Specimen: {specimen}; received in the record on {received_at}."
)
TIMELINE_HISTORY_TEXT = (
    "An older version of {document_id} (version {version}, dated {event_date}) "
    "was replaced and is kept as history."
)
TIMELINE_HISTORY_DETAIL = "Older versions stay inspectable; they are not current."
QUESTION_DETAIL = "Open (pending). Recorded {created_at}."
OPTION_DETAIL = (
    "Recorded standing: {epistemic}; recorded review state: {operational}. "
    "Based on investigation snapshot #{snapshot_id} "
    "(snapshot state: {snapshot_state}). {counts} Listed for discussion only."
)

# Report-voice guard: fixed framing sentences must never carry clinical
# interpretation, recommendation, or directive language. Recorded case
# entries are quoted, never rewritten, so they are scanned separately.
REPORT_GUARDS = [
    re.compile(r"\brecommend\w*\b", re.IGNORECASE),
    re.compile(r"\bshould\b", re.IGNORECASE),
    re.compile(r"\bmust\b", re.IGNORECASE),
    re.compile(r"\bneed to\b", re.IGNORECASE),
    re.compile(r"\bprescri\w*\b", re.IGNORECASE),
    re.compile(r"\bdos(e|age)\b", re.IGNORECASE),
    re.compile(r"\bdiagnos\w*\b", re.IGNORECASE),
    re.compile(r"\bprognos\w*\b", re.IGNORECASE),
    re.compile(r"\befficac\w*\b", re.IGNORECASE),
    re.compile(r"\bbest (treatment|therapy|option|drug|choice)\b", re.IGNORECASE),
    re.compile(r"\btreatment\b", re.IGNORECASE),
    re.compile(r"\btherap\w*\b", re.IGNORECASE),
    re.compile(r"\beligib\w*\b", re.IGNORECASE),
    re.compile(r"\bclinical trial\b", re.IGNORECASE),
    re.compile(r"\bbenefit\b", re.IGNORECASE),
    re.compile(r"\brisk\b", re.IGNORECASE),
    re.compile(r"\bstag(e|ing)\b", re.IGNORECASE),
    re.compile(r"\byou\b", re.IGNORECASE),
]


def _plural(count: int, one: str, many: str) -> str:
    return f"{count} {one}" if count == 1 else f"{count} {many}"


def _order_key(source: dict) -> tuple:
    return (source["event_date"], source["issued_at"], source["received_at"],
            source["document_id"], source["version"], source["id"])


def _check_framing(text: str) -> None:
    for pattern in REPORT_GUARDS:
        if pattern.search(text):
            raise ValueError(f"Report framing failed language guard: {pattern.pattern}")


def _section(section_id: str, title: str, summary: str, items: list[dict],
             empty_text: str) -> dict:
    _check_framing(title)
    _check_framing(summary)
    _check_framing(empty_text)
    _check_framing(FICTIONAL_BANNER)
    cited = sum(1 for item in items if item.get("citation") != NO_SOURCE_NOTE)
    return {
        "id": section_id,
        "title": title,
        "fictional_note": FICTIONAL_BANNER,
        "summary": summary,
        "items": items,
        "empty_text": empty_text,
        "item_count": len(items),
        "cited_count": cited,
        "sources_note": (
            f"Every entry in this section names its source ({cited} of "
            f"{len(items)} cited)."
            if items else
            "This section has no entries, so it cites no sources."
        ),
    }


def _overview(state: dict, current: list[dict], stale: list[dict]) -> dict:
    case = state["case"]
    open_count = sum(1 for item in state.get("questions", []) if item.get("state") == "open")
    superseded = [item for item in state.get("sources", []) if item.get("state") != "current"]
    quarantined = list(state.get("quarantines", []))
    parts = [
        f"This is a plain-language listing for fictional case {case['case_id']} "
        f"({case['label']}). It repeats the case record only.",
        f"The record holds {_plural(len(current), 'current source document', 'current source documents')} "
        f"with {_plural(len(state.get('assertions', [])), 'reported statement', 'reported statements')}, "
        f"{_plural(open_count, 'open question', 'open questions')}, and "
        f"{_plural(len(state.get('options', [])), 'recorded option', 'recorded options')}.",
    ]
    if stale:
        parts.append(
            f"{_plural(len(stale), 'earlier draft', 'earlier drafts')} "
            "waiting for another look (pending) because a report changed "
            "after they were written."
        )
    else:
        parts.append("No earlier draft is waiting for another look.")
    if superseded:
        parts.append(
            f"{_plural(len(superseded), 'older report version', 'older report versions')} "
            "replaced by a newer version; the older versions are kept and can be inspected."
        )
    if quarantined:
        parts.append(
            f"{_plural(len(quarantined), 'delivery', 'deliveries')} set aside "
            "(quarantined) because the stated subject did not match this case; "
            "nothing was imported from them."
        )
    items = []
    for assertion in state.get("assertions", []):
        certainty = assertion.get("certainty", "unknown")
        plain = CERTAINTY_PLAIN.get(certainty, "unknown")
        items.append({
            "text": assertion.get("quote", ""),
            "detail": DETAIL_FINDING.format(
                finding_key=assertion.get("finding_key"), plain=plain,
                certainty=certainty),
            "citation": (
                f"Source version #{assertion.get('source_version_id')}, "
                f"line {assertion.get('source_line')}."
            ),
        })
    return _section(
        "overview",
        "Overview: what the record contains",
        " ".join(parts),
        items,
        "No reported statements are recorded for this case. Unknown — nothing to list yet.",
    )


def _timeline(current: list[dict], superseded: list[dict]) -> dict:
    items = []
    for source in sorted(current, key=_order_key):
        items.append({
            "text": TIMELINE_ENTRY_TEXT.format(
                event_date=source["event_date"], kind=source["kind"],
                document_id=source["document_id"], version=source["version"],
                issued_at=source["issued_at"]),
            "detail": TIMELINE_ENTRY_DETAIL.format(
                specimen=source["specimen_id"] or "not recorded",
                received_at=source["received_at"]),
            "citation": f"Source version #{source['id']} ({source['document_id']}@{source['version']}).",
        })
    for source in sorted(superseded, key=lambda row: (row["document_id"], row["version"], row["id"])):
        items.append({
            "text": TIMELINE_HISTORY_TEXT.format(
                document_id=source["document_id"], version=source["version"],
                event_date=source["event_date"]),
            "detail": TIMELINE_HISTORY_DETAIL,
            "citation": f"Source version #{source['id']} ({source['document_id']}@{source['version']}).",
        })
    summary = (
        f"The record lists {_plural(len(current), 'current report', 'current reports')} "
        f"in date order and {_plural(len(superseded), 'older version', 'older versions')} kept as history."
        if items else
        "The record lists no reports yet."
    )
    return _section(
        "timeline",
        "Timeline highlights: reports in date order",
        summary,
        items,
        "No reports are recorded for this case yet. Unknown — nothing to list yet.",
    )


def _questions(state: dict) -> dict:
    questions = state.get("questions", [])
    open_items = [item for item in questions if item.get("state") == "open"]
    addressed = sum(1 for item in questions if item.get("state") != "open")
    stale = sum(1 for item in state.get("snapshots", []) if item.get("state") == "stale")
    items = [{
        "text": item.get("question", ""),
        "detail": QUESTION_DETAIL.format(created_at=item.get("created_at")),
        "citation": f"Question record #{item.get('id')}.",
    } for item in sorted(open_items, key=lambda row: row.get("id", 0))]
    summary = (
        f"{_plural(len(open_items), 'question is', 'questions are')} open (pending); "
        f"{_plural(addressed, 'earlier question is', 'earlier questions are')} marked addressed; "
        f"{_plural(stale, 'draft is', 'drafts are')} marked stale (waiting for another look)."
    )
    return _section(
        "questions",
        "Open questions: what is still being asked",
        summary,
        items,
        "No open questions are recorded for this case.",
    )


def _options(state: dict) -> dict:
    items = []
    for option in state.get("options", []):
        epistemic = EPISTEMIC_PLAIN.get(option.get("derived_epistemic_status"), "unknown")
        operational = OPERATIONAL_PLAIN.get(option.get("display_operational_status"), "unknown")
        counts = (
            f"{_plural(len(option.get('dependencies', [])), 'linked item', 'linked items')}; "
            f"{_plural(len(option.get('preparation_tasks', [])), 'preparation task', 'preparation tasks')}; "
            f"{_plural(len(option.get('threats', [])), 'recorded concern', 'recorded concerns')}."
        )
        items.append({
            "text": f"{option.get('label')}: {option.get('description')}",
            "detail": OPTION_DETAIL.format(
                epistemic=epistemic, operational=operational,
                snapshot_id=option.get("snapshot_id"),
                snapshot_state=option.get("snapshot_state"), counts=counts),
            "citation": f"Option record #{option.get('id')}.",
        })
    summary = (
        f"The record lists {_plural(len(items), 'option under discussion', 'options under discussion')}. "
        "Options are discussion items only; the listing states no order of preference."
        if items else
        "The record lists no options under discussion."
    )
    return _section(
        "options",
        "Option portfolio: items under discussion",
        summary,
        items,
        "No options are recorded for this case. Unknown — nothing to list yet.",
    )


def _goals() -> dict:
    # The ledger has no goals entity; the report says so plainly instead of
    # inferring goals from other records.
    return _section(
        "goals",
        "Goals: what matters to the person",
        "No goals are recorded for this case. This demo does not track goals yet.",
        [],
        "No goals are recorded. Unknown — not stated in the record.",
    )


def build_patient_report(state: dict) -> dict:
    """Project a canonical case snapshot into a plain-language report."""
    case = state["case"]
    current = [item for item in state.get("sources", []) if item.get("state") == "current"]
    superseded = [item for item in state.get("sources", []) if item.get("state") != "current"]
    stale = [item for item in state.get("snapshots", []) if item.get("state") == "stale"]
    events = state.get("events", [])
    latest = events[0] if events else None
    sections = [
        _overview(state, current, stale),
        _timeline(current, superseded),
        _questions(state),
        _options(state),
        _goals(),
    ]
    _check_framing(READING_NOTE)
    return {
        "case_id": case["case_id"],
        "case_label": case["label"],
        "fictional": True,
        "demo_notice": FICTIONAL_BANNER,
        "reading_note": READING_NOTE,
        "generated_from": "recorded case data only; no new inference",
        "as_of": {
            "event_id": latest.get("id") if latest else None,
            "occurred_at": latest.get("occurred_at") if latest else None,
        },
        "section_ids": [section["id"] for section in sections],
        "sections": sections,
    }


def render_text(report: dict) -> str:
    """Render the report as printable plain text. Templates only, no inference."""
    lines = [
        "OPEN INTELLIGENCE — PLAIN-LANGUAGE CASE REPORT",
        report["demo_notice"],
        f"Fictional case {report['case_id']} ({report['case_label']}).",
        report["reading_note"],
        f"Made from: {report['generated_from']}.",
    ]
    as_of = report.get("as_of") or {}
    lines.append(f"Record position: event {as_of.get('event_id')} at {as_of.get('occurred_at')}.")
    lines.append("")
    for section in report["sections"]:
        lines.append("=" * 60)
        lines.append(section["title"].upper())
        lines.append(section["fictional_note"])
        lines.append(section["summary"])
        if section["items"]:
            for number, item in enumerate(section["items"], 1):
                lines.append("")
                lines.append(f"{number}. {item['text']}")
                lines.append(f"   {item['detail']}")
                lines.append(f"   Source: {item['citation']}")
            lines.append("")
            lines.append(section["sources_note"])
        else:
            lines.append(section["empty_text"])
            lines.append(section["sources_note"])
        lines.append("")
    lines.append("=" * 60)
    lines.append(report["demo_notice"])
    lines.append("End of report.")
    return "\n".join(lines) + "\n"
