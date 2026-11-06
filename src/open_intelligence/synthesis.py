"""Read-only contradiction synthesis and bounded source-linked reports (B-08).

This module groups the human-entered relation labels that already exist on
``evidence_assessments`` and ``broker_links`` so supporting and contradicting
items sit side by side per question. It is a projection with the same
contract as ``mission.py`` and ``changes.py``: it reads only, writes nothing,
and is deterministic for a fixed ledger state.

Granularity (documented choice): one item per human-entered assessment or
broker link, grouped by its human-entered relation label. No claim-splitting
is attempted; an assessment or link is never divided into smaller claims.

What this module never does:

- It never computes a quality number and never merges dissent into one
  verdict. Supporting and contradicting items stay listed together.
- It never re-labels a human-entered relation or applicability value.
- It never presents a stale-basis report as current: a report whose basis
  changed carries REVIEW-PENDING and reads as history.

Every report carries its cutoff: the snapshot id plus the latest case event
id at render time. Two renders at the same cutoff are byte-identical,
because every volatile value is read from the stored cutoff event row.
"""

from __future__ import annotations

import re
from typing import TYPE_CHECKING

from .store import InvalidInput

if TYPE_CHECKING:
    from .store import CaseStore

DISCLAIMER = (
    "Fictional synthetic data only. This synthesis lists human-entered "
    "relation labels side by side; it adds no new finding, writes nothing, "
    "and computes no quality number. Dissent stays visible: supporting and "
    "contradicting items are listed together, never merged into one verdict."
)

PATIENT_DISCLAIMER = (
    "This is the same fictional record as the workspace report, written more "
    "plainly. Nothing here is a medical recommendation, and nothing is hidden "
    "by making it plain: where records disagree, say little, or changed after "
    "this report was written, that is stated. This fictional demo is not a "
    "real medical record. For a real result, talk to your care team."
)

GRANULARITY = (
    "one item per human-entered evidence assessment or broker link, "
    "grouped by its human-entered relation label; no claim-splitting"
)

GROUP_ORDER = ("supporting", "contradicting", "context", "unknown_limited")

RELATION_TO_GROUP = {
    "supports": "supporting",
    "contradicts": "contradicting",
    "context": "context",
    "unknown": "unknown_limited",
}

GROUP_TITLES = {
    "supporting": "Supporting items",
    "contradicting": "Contradicting items",
    "context": "Context items",
    "unknown_limited": "Unknown or limited items",
}

PATIENT_GROUP_TITLES = {
    "supporting": "Records marked as agreeing",
    "contradicting": "Records marked as disagreeing",
    "context": "Background records",
    "unknown_limited": "Records that are unclear or only partly apply",
}

NO_ITEMS_LINES = {
    "supporting": "None included; no supporting item is linked at this cutoff.",
    "contradicting": "None included; no contradicting item is linked at this cutoff.",
    "context": "None included; no context item is linked at this cutoff.",
    "unknown_limited": "None included; no unknown or limited item is linked at this cutoff.",
}

PATIENT_NO_ITEMS_LINES = {
    "supporting": "None listed here: no record was marked as agreeing at this time.",
    "contradicting": "None listed here: no record was marked as disagreeing at this time.",
    "context": "None listed here: no background record was linked at this time.",
    "unknown_limited": (
        "None listed here: no record was unclear or only partly applying at this time."
    ),
}

# Plain-words labels translate only this module's fixed vocabulary. Reviewer
# text (questions, drafts, rationales, notes) is quoted verbatim, never
# paraphrased, so the patient rendering cannot add certainty of its own.
PLAIN_RELATION = {
    "supports": "marked as agreeing with the question",
    "contradicts": "marked as disagreeing with the question",
    "context": "marked as background for the question",
    "unknown": "marked as unclear for the question",
}

PLAIN_APPLICABILITY = {
    "applicable": "marked as applying (a reviewer label, not a checked fact)",
    "limited": "marked as only partly applying",
    "not_applicable": "marked as not applying",
    "unknown": "not yet marked as applying or not",
}

PLAIN_REVIEW_STATE = {
    "current": "still the latest record",
    "needs_review": "needs another look because the record changed",
}

REVIEW_PENDING_BANNER = (
    "> REVIEW-PENDING: the record changed after this report's cutoff. "
    "What follows is history, not a current conclusion. "
    "A new review is needed before reuse."
)

REVIEW_PENDING_PATIENT = (
    "> This report needs another look: the record changed after it was "
    "written. What follows describes the record at that earlier time, "
    "not the latest record."
)


def _fence(text: str) -> str:
    """Return a Markdown fence that quoted text cannot escape."""
    longest = max((len(run) for run in re.findall(r"`+", text)), default=0)
    return "`" * max(3, longest + 1)


def _latest_event(db, case_id: str) -> tuple[int, str]:
    row = db.execute(
        "SELECT id, occurred_at FROM events WHERE case_id=? ORDER BY id DESC LIMIT 1",
        (case_id,),
    ).fetchone()
    if not row:
        raise InvalidInput("Case has no events to anchor on")
    return int(row["id"]), str(row["occurred_at"])


def _question_row(db, case_id: str, question_id: int) -> dict:
    if type(question_id) is not int:
        raise InvalidInput("Question id must be an integer")
    row = db.execute(
        "SELECT * FROM questions WHERE id=? AND case_id=?", (question_id, case_id)
    ).fetchone()
    if not row:
        raise InvalidInput("Question not in this case")
    return dict(row)


def _notes_by_target(db, case_id: str, question_id: int) -> dict:
    grouped: dict = {"assessment": {}, "broker_link": {}}
    rows = db.execute(
        """SELECT id, assessment_id, broker_link_id, note, author_label, created_at
        FROM limitation_notes WHERE case_id=? AND question_id=? ORDER BY id""",
        (case_id, question_id),
    ).fetchall()
    for row in rows:
        entry = {
            "id": int(row["id"]),
            "note": row["note"],
            "author_label": row["author_label"],
            "created_at": row["created_at"],
        }
        if row["assessment_id"] is not None:
            grouped["assessment"].setdefault(int(row["assessment_id"]), []).append(entry)
        else:
            grouped["broker_link"].setdefault(int(row["broker_link_id"]), []).append(entry)
    return grouped


def _assessment_item(row: dict, notes: list[dict], cutoff_event_id: int) -> dict:
    currency = str(row["evidence_state"])
    return {
        "kind": "evidence_assessment",
        "id": int(row["id"]),
        "relation": row["relation"],
        "group": RELATION_TO_GROUP[str(row["relation"])],
        "applicability": row["applicability"],
        "review_state": "current" if currency == "current" else "needs_review",
        "currency": currency,
        "anchor": {
            "evidence_key": row["evidence_key"],
            "version": int(row["version"]),
            "evidence_version_id": int(row["evidence_version_id"]),
            "statement_line": int(row["statement_line"]),
            "sha256": row["sha256"],
            "title": row["title"],
        },
        "rationale": row["rationale"],
        "statement": row["statement"],
        "limitation_notes": notes,
        "cutoff_event_id": cutoff_event_id,
    }


def _broker_item(row: dict, notes: list[dict], cutoff_event_id: int) -> dict:
    rights_state = str(row["rights_state"])
    active = rights_state == "active"
    mode = str(row["mode"])
    if not active:
        content = {
            "citation_title": None,
            "excerpt": None,
            "content_withheld": True,
            "withheld_reason": "rights row is not active; the link record stays visible",
        }
    elif mode == "citation_only":
        content = {
            "citation_title": None,
            "excerpt": None,
            "content_withheld": False,
            "withheld_reason": "citation identity only under recorded permissions",
        }
    elif mode == "metadata_only":
        content = {
            "citation_title": row["citation_title"],
            "excerpt": None,
            "content_withheld": False,
            "withheld_reason": None,
        }
    else:
        content = {
            "citation_title": row["citation_title"],
            "excerpt": row["excerpt"],
            "content_withheld": False,
            "withheld_reason": None,
        }
    return {
        "kind": "broker_link",
        "id": int(row["id"]),
        "relation": row["relation"],
        "group": RELATION_TO_GROUP[str(row["relation"])],
        "applicability": row["applicability"],
        "review_state": "current" if active else "needs_review",
        "currency": rights_state,
        "anchor": {
            "source_key": row["source_key"],
            "version_label": row["version_label"],
            "rights_source_id": int(row["rights_source_id"]),
            "mode": mode,
        },
        "rationale": row["rationale"],
        "content": content,
        "limitation_notes": notes,
        "cutoff_event_id": cutoff_event_id,
    }


def _grouped(items: list[dict]) -> dict:
    groups = {name: [] for name in GROUP_ORDER}
    for item in items:
        groups[item["group"]].append(item)
    for name in GROUP_ORDER:
        groups[name].sort(key=lambda entry: (entry["kind"], entry["id"]))
    return groups


def question_synthesis(store: CaseStore, case_id: str, question_id: int) -> dict:
    """Group every linked item for one question. Reads only; writes nothing."""
    store._case(case_id)
    with store.db:
        store.db.execute("BEGIN")
        question = _question_row(store.db, case_id, question_id)
        event_id, occurred_at = _latest_event(store.db, case_id)
        notes = _notes_by_target(store.db, case_id, question_id)
        assessments = [
            dict(row)
            for row in store.db.execute(
                """SELECT a.*, v.evidence_key, v.version, v.state AS evidence_state,
                v.title, v.statement, v.statement_line, v.sha256
                FROM evidence_assessments a
                JOIN evidence_versions v ON v.id=a.evidence_version_id
                WHERE a.case_id=? AND a.question_id=? ORDER BY a.id""",
                (case_id, question_id),
            ).fetchall()
        ]
        links = [
            dict(row)
            for row in store.db.execute(
                """SELECT bl.*, rs.source_key, rs.version_label,
                rs.state AS rights_state FROM broker_links bl
                JOIN rights_sources rs ON rs.id=bl.rights_source_id
                WHERE bl.case_id=? AND bl.question_id=? ORDER BY bl.id""",
                (case_id, question_id),
            ).fetchall()
        ]
    items = [_assessment_item(row, notes["assessment"].get(int(row["id"]), []), event_id)
             for row in assessments]
    items += [_broker_item(row, notes["broker_link"].get(int(row["id"]), []), event_id)
              for row in links]
    groups = _grouped(items)
    return {
        "case_id": case_id,
        "question_id": int(question["id"]),
        "question": question["question"],
        "question_state": question["state"],
        "snapshot_id": None,
        "cutoff": {"snapshot_id": None, "event_id": event_id, "occurred_at": occurred_at},
        "granularity": GRANULARITY,
        "groups": groups,
        "counts": {
            "total": len(items),
            **{name: len(groups[name]) for name in GROUP_ORDER},
        },
        "basis": {"snapshot_state": None, "stale_basis": False, "reasons": []},
        "disclaimer": DISCLAIMER,
        "synthetic": True,
    }


def _snapshot_rows(store: CaseStore, case_id: str, snapshot_id: int) -> tuple[dict, dict]:
    if type(snapshot_id) is not int:
        raise InvalidInput("Snapshot id must be an integer")
    snapshot = store.db.execute(
        """SELECT s.*, q.question, q.state AS question_state FROM snapshots s
        JOIN questions q ON q.id=s.question_id
        WHERE s.case_id=? AND s.id=?""",
        (case_id, snapshot_id),
    ).fetchone()
    if not snapshot:
        raise InvalidInput("Investigation not in this case")
    return dict(snapshot), _question_row(store.db, case_id, int(snapshot["question_id"]))


def _basis_status(db, case_id: str, snapshot: dict) -> dict:
    reasons: list[str] = []
    snapshot_id = int(snapshot["id"])
    if snapshot["state"] == "stale":
        reasons.append(f"snapshot #{snapshot_id} is marked stale")
    sources = [
        dict(row)
        for row in db.execute(
            """SELECT v.id, v.document_id, v.version, v.state, v.event_date, v.issued_at
            FROM source_versions v JOIN snapshot_sources ss ON ss.source_version_id=v.id
            WHERE ss.snapshot_id=? ORDER BY v.document_id, v.version""",
            (snapshot_id,),
        ).fetchall()
    ]
    for source in sources:
        if source["state"] != "current":
            reasons.append(
                f"source {source['document_id']}@{source['version']} "
                f"(version #{source['id']}) is {source['state']}"
            )
    evidence = [
        dict(row)
        for row in db.execute(
            """SELECT v.id, v.evidence_key, v.version, v.state
            FROM snapshot_evidence se
            JOIN evidence_assessments a ON a.id=se.assessment_id
            JOIN evidence_versions v ON v.id=a.evidence_version_id
            WHERE se.snapshot_id=? ORDER BY a.id""",
            (snapshot_id,),
        ).fetchall()
    ]
    for item in evidence:
        if item["state"] != "current":
            reasons.append(
                f"evidence {item['evidence_key']}@{item['version']} "
                f"(version #{item['id']}) is {item['state']}"
            )
    rights = [
        dict(row)
        for row in db.execute(
            """SELECT rs.id, rs.source_key, rs.version_label, rs.state
            FROM snapshot_broker_links sbl
            JOIN broker_links bl ON bl.id=sbl.broker_link_id
            JOIN rights_sources rs ON rs.id=bl.rights_source_id
            WHERE sbl.snapshot_id=? ORDER BY bl.id""",
            (snapshot_id,),
        ).fetchall()
    ]
    for row in rights:
        if row["state"] != "active":
            reasons.append(
                f"rights row {row['source_key']} {row['version_label']} "
                f"(row #{row['id']}) is {row['state']}"
            )
    return {
        "snapshot_state": snapshot["state"],
        "stale_basis": bool(reasons),
        "reasons": reasons,
        "sources": sources,
        "evidence": evidence,
        "rights": rights,
    }


def snapshot_synthesis(store: CaseStore, case_id: str, snapshot_id: int) -> dict:
    """Group the items bound to one snapshot, history included.

    Reads only; writes nothing. Bound items stay listed even after the
    underlying source, evidence, or rights row changed; their review state
    then reads ``needs_review`` instead of ``current``.
    """
    store._case(case_id)
    with store.db:
        store.db.execute("BEGIN")
        snapshot, question = _snapshot_rows(store, case_id, snapshot_id)
        event_id, occurred_at = _latest_event(store.db, case_id)
        notes = _notes_by_target(store.db, case_id, int(question["id"]))
        assessments = [
            dict(row)
            for row in store.db.execute(
                """SELECT a.*, v.evidence_key, v.version, v.state AS evidence_state,
                v.title, v.statement, v.statement_line, v.sha256
                FROM snapshot_evidence se
                JOIN evidence_assessments a ON a.id=se.assessment_id
                JOIN evidence_versions v ON v.id=a.evidence_version_id
                WHERE se.snapshot_id=? ORDER BY a.id""",
                (snapshot_id,),
            ).fetchall()
        ]
        links = [
            dict(row)
            for row in store.db.execute(
                """SELECT bl.*, rs.source_key, rs.version_label,
                rs.state AS rights_state FROM snapshot_broker_links sbl
                JOIN broker_links bl ON bl.id=sbl.broker_link_id
                JOIN rights_sources rs ON rs.id=bl.rights_source_id
                WHERE sbl.snapshot_id=? ORDER BY bl.id""",
                (snapshot_id,),
            ).fetchall()
        ]
        basis = _basis_status(store.db, case_id, snapshot)
        sources = [
            {
                "document_id": row["document_id"],
                "version": int(row["version"]),
                "label": "%s@%s" % (row["document_id"], row["version"]),
            }
            for row in store.db.execute(
                """SELECT v.document_id, v.version
                FROM snapshot_sources ss
                JOIN source_versions v ON v.id=ss.source_version_id
                WHERE ss.snapshot_id=? ORDER BY v.id""",
                (snapshot_id,),
            ).fetchall()
        ]
    items = [_assessment_item(row, notes["assessment"].get(int(row["id"]), []), event_id)
             for row in assessments]
    items += [_broker_item(row, notes["broker_link"].get(int(row["id"]), []), event_id)
              for row in links]
    groups = _grouped(items)
    return {
        "case_id": case_id,
        "question_id": int(question["id"]),
        "question": question["question"],
        "question_state": question["state"],
        "snapshot_id": int(snapshot["id"]),
        "snapshot": {
            "id": int(snapshot["id"]),
            "summary": snapshot["summary"],
            "state": snapshot["state"],
            "created_at": snapshot["created_at"],
            "reviewed_at": snapshot["reviewed_at"],
            "reviewer_label": snapshot["reviewer_label"],
        },
        "cutoff": {
            "snapshot_id": int(snapshot["id"]),
            "event_id": event_id,
            "occurred_at": occurred_at,
        },
        "granularity": GRANULARITY,
        "sources": sources,
        "groups": groups,
        "counts": {
            "total": len(items),
            **{name: len(groups[name]) for name in GROUP_ORDER},
        },
        "basis": basis,
        "disclaimer": DISCLAIMER,
        "synthetic": True,
    }


def _render_item_lines(item: dict) -> list[str]:
    lines: list[str] = []
    if item["kind"] == "evidence_assessment":
        anchor = item["anchor"]
        lines.append(
            f"### [assessment #{item['id']}] "
            f"{anchor['evidence_key']}@{anchor['version']}: {anchor['title']}"
        )
        lines.append("")
        lines.append(
            f"Evidence state: {item['currency']} | Review state: {item['review_state']} | "
            f"Statement line: {anchor['statement_line']}"
        )
        lines.append(f"SHA-256: `{anchor['sha256']}`")
        lines.append(
            f"Human-entered relation: {item['relation']} | "
            f"Applicability: {item['applicability']} | Cutoff event: #{item['cutoff_event_id']}"
        )
        lines.append("")
        lines.append(f"Rationale (human-entered): {item['rationale']}")
        lines.append("")
        fence = _fence(item["statement"])
        lines.extend([fence + "text", item["statement"], fence, ""])
    else:
        anchor = item["anchor"]
        lines.append(
            f"### [link #{item['id']}] "
            f"{anchor['source_key']} {anchor['version_label']} ({anchor['mode']})"
        )
        lines.append("")
        lines.append(
            f"Rights state: {item['currency']} | Review state: {item['review_state']} | "
            f"Rights row: #{anchor['rights_source_id']}"
        )
        lines.append(
            f"Human-entered relation: {item['relation']} | "
            f"Applicability: {item['applicability']} | Cutoff event: #{item['cutoff_event_id']}"
        )
        lines.append("")
        lines.append(f"Rationale (human-entered): {item['rationale']}")
        lines.append("")
        content = item["content"]
        if content["content_withheld"]:
            lines.append(f"Stored title and excerpt withheld: {content['withheld_reason']}.")
            lines.append("")
        elif content["citation_title"] is None:
            lines.append("Citation identity only under recorded permissions; no title stored.")
            lines.append("")
        else:
            lines.append(f"Citation title: {content['citation_title']}")
            if content["excerpt"] is not None:
                fence = _fence(content["excerpt"])
                lines.extend(["", fence + "text", content["excerpt"], fence, ""])
            else:
                lines.append("")
    notes = item["limitation_notes"]
    if notes:
        lines.append("Reviewer limitation notes (human-entered, earliest first):")
        for note in notes:
            lines.append(f"- #{note['id']} by {note['author_label']} at {note['created_at']}:")
            fence = _fence(note["note"])
            lines.extend([fence + "text", note["note"], fence])
        lines.append("")
    return lines


def _render_patient_item_lines(item: dict) -> list[str]:
    lines: list[str] = []
    anchor_text = (
        f"assessment #{item['id']}, "
        f"{item['anchor'].get('evidence_key', '')}@{item['anchor'].get('version', '')}"
        if item["kind"] == "evidence_assessment"
        else f"link #{item['id']}, "
        f"{item['anchor'].get('source_key', '')} {item['anchor'].get('version_label', '')}"
    )
    lines.append(f"Record {anchor_text.strip()} was {PLAIN_RELATION[item['relation']]}.")
    lines.append(
        f"It was {PLAIN_APPLICABILITY[item['applicability']]}. "
        f"Record state: {PLAIN_REVIEW_STATE[item['review_state']]}."
    )
    lines.append(f"The reviewer wrote: {item['rationale']}")
    for note in item["limitation_notes"]:
        lines.append(f"A reviewer also noted ({note['author_label']}): {note['note']}")
    lines.append("")
    return lines


def render_bounded_report(store: CaseStore, case_id: str, snapshot_id: int) -> str:
    """Render the workspace bounded report for one snapshot (Markdown)."""
    payload = snapshot_synthesis(store, case_id, snapshot_id)
    cutoff = payload["cutoff"]
    basis = payload["basis"]
    stale = basis["stale_basis"]
    snapshot = payload["snapshot"]
    lines = ["# Open Intelligence — bounded synthesis report", ""]
    lines.append("> FICTIONAL DEMO DATA — not a real patient.")
    lines.append("> Research demonstration only. No clinical review.")
    if stale:
        lines.append(REVIEW_PENDING_BANNER)
    lines.append("")
    lines.append(
        f"Case: `{case_id}` | Question: Q{payload['question_id']} | "
        f"Snapshot: #{snapshot['id']} | State: **{snapshot['state']}**"
    )
    lines.append(
        f"Cutoff: snapshot #{cutoff['snapshot_id']}, "
        f"event #{cutoff['event_id']} at {cutoff['occurred_at']}"
    )
    lines.append("")
    lines.append("## Question")
    lines.append("")
    lines.append(payload["question"])
    lines.append("")
    if stale:
        lines.append("## Draft at cutoff (history — the record changed after this cutoff)")
    else:
        lines.append("## Draft at cutoff (human-authored)")
    lines.append("")
    lines.append(snapshot["summary"])
    lines.append("")
    lines.append("## Sources at cutoff")
    lines.append("")
    if payload["sources"]:
        for source in payload["sources"]:
            lines.append(f"- {source['label']}")
    else:
        lines.append("None listed here: no source was bound at this cutoff.")
    lines.append("")
    counts = payload["counts"]
    lines.append("## Linked items side by side")
    lines.append("")
    lines.append(
        f"Linked items: {counts['total']} "
        f"(supporting {counts['supporting']} · contradicting {counts['contradicting']} · "
        f"context {counts['context']} · unknown/limited {counts['unknown_limited']})"
    )
    lines.append("")
    for name in GROUP_ORDER:
        lines.append(f"## {GROUP_TITLES[name]} ({len(payload['groups'][name])})")
        lines.append("")
        if not payload["groups"][name]:
            lines.append(NO_ITEMS_LINES[name])
            lines.append("")
        for item in payload["groups"][name]:
            lines.extend(_render_item_lines(item))
    lines.append("## Basis and cutoff")
    lines.append("")
    lines.append(f"- Snapshot #{snapshot['id']}: state {snapshot['state']}, "
                 f"created {snapshot['created_at']}, "
                 f"demo acknowledgment: {snapshot['reviewed_at'] or 'None'}")
    lines.append(
        f"- Cutoff event #{cutoff['event_id']} at {cutoff['occurred_at']}"
    )
    if basis["sources"]:
        for source in basis["sources"]:
            lines.append(
                f"- Source {source['document_id']}@{source['version']} "
                f"(version #{source['id']}, {source['state']}, "
                f"event {source['event_date']}, issued {source['issued_at']})"
            )
    else:
        lines.append("- No source versions bound to this snapshot.")
    if basis["evidence"]:
        for item in basis["evidence"]:
            lines.append(
                f"- Evidence {item['evidence_key']}@{item['version']} "
                f"(version #{item['id']}, {item['state']})"
            )
    else:
        lines.append("- No evidence versions bound to this snapshot.")
    if basis["rights"]:
        for row in basis["rights"]:
            lines.append(
                f"- Rights row {row['source_key']} {row['version_label']} "
                f"(row #{row['id']}, {row['state']})"
            )
    else:
        lines.append("- No rights rows bound to this snapshot.")
    if stale:
        lines.append("- Basis changes since the cutoff:")
        for reason in basis["reasons"]:
            lines.append(f"  - {reason}")
    else:
        lines.append("- No basis change is recorded at this cutoff.")
    lines.append("")
    lines.append("## Limitations")
    lines.append("")
    lines.append("- This synthesis lists what the record says; it adds no new finding.")
    lines.append("- Relation and applicability labels are human-entered; they are not checked facts.")
    lines.append("- Limitation notes are human-entered; this report computes no quality number.")
    lines.append("- Evidence items are fictional, independently authored examples; no real publication was appraised.")
    lines.append("- An acknowledgment in this demo is not clinician credential verification or a clinical sign-off.")
    lines.append("- Amendments can make a report stale; see the basis section above.")
    lines.append("")
    return "\n".join(lines)


def render_patient_report(store: CaseStore, case_id: str, snapshot_id: int) -> str:
    """Render the plain-words bounded report for one snapshot (Markdown).

    The patient rendering covers the same cutoff, the same items, and the
    same reviewer text as the workspace report. Only this module's fixed
    labels are translated into plain words; reviewer text is quoted
    verbatim, so the rendering cannot add certainty of its own.
    """
    payload = snapshot_synthesis(store, case_id, snapshot_id)
    cutoff = payload["cutoff"]
    basis = payload["basis"]
    stale = basis["stale_basis"]
    snapshot = payload["snapshot"]
    lines = ["# Your case report in plain words", ""]
    lines.append("> FICTIONAL DEMO DATA — not a real patient.")
    lines.append(f"> {PATIENT_DISCLAIMER}")
    if stale:
        lines.append(REVIEW_PENDING_PATIENT)
    lines.append("")
    lines.append(
        f"This report covers question Q{payload['question_id']} and draft #{snapshot['id']}. "
        f"Draft state: {snapshot['state']}. "
        f"Cutoff: draft #{cutoff['snapshot_id']}, record event #{cutoff['event_id']} "
        f"at {cutoff['occurred_at']}."
    )
    lines.append("")
    lines.append("## The question, in plain words")
    lines.append("")
    lines.append(payload["question"])
    lines.append("")
    if stale:
        lines.append("## What the draft said at that earlier time")
        lines.append("")
        lines.append(
            "The record changed after this draft was written, so this is history, "
            "not the latest record."
        )
    else:
        lines.append("## What the draft says")
    lines.append("")
    lines.append(snapshot["summary"])
    lines.append("")
    lines.append("## Records this draft is based on")
    lines.append("")
    if payload["sources"]:
        for source in payload["sources"]:
            lines.append(f"- {source['label']}")
    else:
        lines.append("None listed here: no record was bound at this cutoff.")
    lines.append("")
    counts = payload["counts"]
    lines.append("## Records for and against, side by side")
    lines.append("")
    lines.append(
        f"Linked records: {counts['total']} "
        f"(agreeing {counts['supporting']} · disagreeing {counts['contradicting']} · "
        f"background {counts['context']} · unclear or partly applying {counts['unknown_limited']})"
    )
    lines.append("")
    for name in GROUP_ORDER:
        lines.append(f"## {PATIENT_GROUP_TITLES[name]} ({len(payload['groups'][name])})")
        lines.append("")
        if not payload["groups"][name]:
            lines.append(PATIENT_NO_ITEMS_LINES[name])
            lines.append("")
        for item in payload["groups"][name]:
            lines.extend(_render_patient_item_lines(item))
    lines.append("## Why this report may need another look")
    lines.append("")
    if stale:
        for reason in basis["reasons"]:
            lines.append(f"- {reason}.")
    else:
        lines.append("- Nothing in the record has changed since this report was written.")
    lines.append("")
    lines.append("## Limits of this report")
    lines.append("")
    lines.append("- This report lists what the fictional record says; it adds no new finding.")
    lines.append("- The agreeing and disagreeing labels were entered by a reviewer; they are not checked facts.")
    lines.append("- The notes about limits were entered by a reviewer; this report computes no quality number.")
    lines.append("- The example records are fictional; no real publication was checked.")
    lines.append("- A demo acknowledgment is not a clinician sign-off.")
    lines.append("")
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# T6: deterministic contradiction & gap grouping (program plan C4).
#
# The reconciliation primitive. These functions group what disagrees and
# what is missing; they never merge dissent, never re-label a value, and
# never pick a winner. A group lists both sides and states what evidence
# would resolve it ("evidence_needed"). Conflicts become typed, visible,
# blocking records through the verification record's abstention codes
# (see skeptic.compute_abstention_codes); the grouping itself decides
# nothing. Deterministic for a fixed ledger state, like the rest of this
# module: no model call, no writes.
#
# The contradiction rule mirrors the K4 rule (Notion OI-09 C9, kchecks
# module): same subject and field, different normalised values,
# overlapping valid time, and no supersession between the versions.
# At the source level, "overlapping valid time" is read as both versions
# being current: a superseded version's disagreement is resolved by
# supersession (the K5 story), and different specimens may legitimately
# differ (the K4 specimen guard).
# ---------------------------------------------------------------------------

def group_run_contradictions(dropped: list[dict]) -> list[dict]:
    """Reformat a run's K4 contradiction drops as T6 groups.

    Each group carries the K4 detail (subject, field, values, claim
    indices, source version ids) plus the evidence that would resolve
    it. The claims stay dropped; the group is the visible record of
    why. A run with no K4 drop yields no group.
    """
    groups: list[dict] = []
    for entry in dropped:
        if entry.get("reason") != "k4_contradiction":
            continue
        detail = entry.get("detail") or {}
        field = detail.get("field", "")
        subject = detail.get("subject", "")
        groups.append({
            "kind": "contradiction",
            "origin": "agent_divergence",
            "subject": subject,
            "field": field,
            "values": list(detail.get("values", [])),
            "claim_indices": list(detail.get("claim_indices", [])),
            "source_version_ids": list(detail.get("source_version_ids", [])),
            "evidence_needed": (
                f"a current source version stating {field} for {subject} "
                "that resolves which claim holds"
            ),
        })
    return groups


def _supersedes(versions: dict, first_id: int, second_id: int) -> bool:
    """True when the version chain from `first_id` reaches `second_id`
    through supersedes_id links (direct or transitive)."""
    seen: set[int] = set()
    current = versions.get(first_id)
    while current is not None and current.id not in seen:
        seen.add(current.id)
        if current.supersedes_id == second_id:
            return True
        current = versions.get(current.supersedes_id) if current.supersedes_id is not None else None
    return False


def group_source_contradictions(kcheck_context) -> list[dict]:
    """T6 source-vs-source grouping over the case's assertion slots.

    Two current source versions that assert different normalised values
    for the same subject and field, with neither superseding the other
    and the same specimen (or no specimen recorded), disagree. The
    group lists both values, the disagreeing source versions, and the
    quoted evidence on each side. A superseded version never joins a
    group: its disagreement is resolved by supersession. Different
    specimens never join a group: they may legitimately differ.
    """
    from .kchecks import normalise_value

    slots = kcheck_context.derived_slots
    versions = kcheck_context.source_versions
    synonyms = kcheck_context.synonyms
    by_key: dict[tuple[str, str], list] = {}
    for slot in slots:
        by_key.setdefault((slot.subject, slot.field), []).append(slot)
    groups: list[dict] = []
    for (subject, field), members in sorted(by_key.items()):
        current = [
            slot for slot in members
            if (versions.get(slot.source_version_id) is None
                or versions[slot.source_version_id].state == "current")
        ]
        values: dict[str, list] = {}
        for slot in current:
            values.setdefault(normalise_value(slot.value, synonyms), []).append(slot)
        if len(values) < 2:
            continue
        for first_value in sorted(values):
            for second_value in sorted(values):
                if second_value <= first_value:
                    continue
                first_slots = values[first_value]
                second_slots = values[second_value]
                pairs = []
                for first in first_slots:
                    for second in second_slots:
                        if (_supersedes(versions, first.source_version_id, second.source_version_id)
                                or _supersedes(versions, second.source_version_id, first.source_version_id)):
                            continue
                        first_specimen = first.specimen
                        second_specimen = second.specimen
                        if (first_specimen is not None and second_specimen is not None
                                and first_specimen != second_specimen):
                            continue
                        pairs.append((first, second))
                if not pairs:
                    continue
                source_ids = sorted({slot.source_version_id for pair in pairs for slot in pair})
                groups.append({
                    "kind": "contradiction",
                    "origin": "source_disagreement",
                    "subject": subject,
                    "field": field,
                    "values": [first_value, second_value],
                    "source_version_ids": source_ids,
                    "quotes": sorted({slot.quote for pair in pairs for slot in pair if slot.quote}),
                    "evidence_needed": (
                        f"a current source version stating {field} for {subject} "
                        "that resolves which assertion holds"
                    ),
                })
    return groups


def group_timeline_gaps(timeline: dict | None) -> list[dict]:
    """T6 gap grouping over a `timeline.case_timeline` projection.

    Two kinds of gap: interior calendar days with no source coverage
    (the timeline's own gaps), and current entries with no occurred
    date (the occurred facet is unknown, never filled by inference).
    Each group states what evidence would close it.
    """
    if not isinstance(timeline, dict):
        return []
    gaps: list[dict] = []
    for gap in timeline.get("gaps", []) if isinstance(timeline.get("gaps"), list) else []:
        if not isinstance(gap, dict):
            continue
        start = gap.get("start_date", "")
        end = gap.get("end_date", "")
        gaps.append({
            "kind": "gap",
            "what": f"no source coverage {start} to {end}",
            "start_date": start,
            "end_date": end,
            "before": gap.get("before", {}),
            "after": gap.get("after", {}),
            "evidence_needed": f"a source covering {start} to {end}",
        })
    for entry in timeline.get("entries", []) if isinstance(timeline.get("entries"), list) else []:
        if not isinstance(entry, dict):
            continue
        if entry.get("occurred") is None:
            gaps.append({
                "kind": "gap",
                "what": f"source {entry.get('source_id')} has no occurred date",
                "source_version_id": entry.get("source_id"),
                "document_id": entry.get("document_id"),
                "evidence_needed": (
                    f"a dated source version for document {entry.get('document_id')}"
                ),
            })
    return gaps


def group_timeline_conflicts(timeline: dict | None) -> list[dict]:
    """T6 contradiction grouping over a timeline projection's conflicts.

    Same specimen, different occurred dates, or same document,
    different occurred dates across versions: the timeline flags the
    disagreement as unknown rather than guessing. The group restates
    it with the evidence that would settle it.
    """
    if not isinstance(timeline, dict):
        return []
    groups: list[dict] = []
    for conflict in timeline.get("conflicts", []) if isinstance(timeline.get("conflicts"), list) else []:
        if not isinstance(conflict, dict):
            continue
        key = conflict.get("conflict_key", "")
        groups.append({
            "kind": "contradiction",
            "origin": "source_disagreement",
            "conflict_key": key,
            "conflict_kind": conflict.get("kind", ""),
            "asserted_occurred_dates": list(conflict.get("asserted_occurred_dates", [])),
            "sources": list(conflict.get("sources", [])),
            "evidence_needed": (
                f"a source version that settles the occurred date for {key}"
            ),
        })
    return groups
