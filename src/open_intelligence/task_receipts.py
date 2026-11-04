"""Task completion receipts and derived dependency-loss flags (B-09, closes G-09).

Synthetic-only, descriptive-only helpers over the EXISTING OI-021 option /
preparation-task ledger in ``store.py``. This module creates no second
ledger: receipts are append-only rows pinned to the basis the task acted
on, and dependency-loss flags are a read-only derivation recomputed on
every ``option_view`` read.

Builder choices (documented per the brief):

* Receipts are ledger rows in ``task_completion_receipts`` (not structured
  event details), following the ``AuthorizationReceipt`` field discipline
  read in ``patient_access.py``: id, scope (case + option + task),
  window (recorded timestamp + pinned basis), actor (owner + acting
  labels). One receipt per task, never edited or deleted.
* Completion against a superseded basis is REJECTED (not flagged):
  ``done`` raises ``InvalidInput`` when the option's basis snapshot is
  stale or any source/evidence premise is not current, using the same
  currentness semantics as ``_require_current_option_dependencies`` for
  source/evidence premises. Prerequisite option review state does not
  block task bookkeeping; the derived flag surfaces it instead.
* First completion wins: if a task leaves ``done`` and re-enters it, the
  original receipt is preserved and no second row is written.
* The acting label defaults to the task owner's label when omitted, so
  existing callers keep working. Authorized-actor binding waits on B-01;
  acting labels stay fictional free text until then.
* Open tasks are ``not_started`` / ``in_progress`` / ``blocked`` tasks
  without a receipt. ``cancelled`` tasks carry the ``no receipt`` marker
  but are not listed as open (terminal, nothing to do). A ``done`` task
  without a receipt can only predate this slice and is labeled
  ``receipt_predates_slice``; it is never backfilled.
* Nothing here auto-completes a task, auto-approves an option, or
  auto-creates ``optionality_threats`` rows (those stay human-entered).
  The ``historical_replay_supported: False`` boundary is untouched.

A completion receipt records that a human-driven status change to done
was stored against a pinned basis. It is a ledger record, not proof of
real-world completion.
"""

from __future__ import annotations

import json
import sqlite3

RECEIPT_DISCLAIMER = (
    "Task completion receipts record that a human-driven status change to "
    "done was stored against a pinned case basis. A receipt is a ledger "
    "record, not proof of real-world completion."
)

RECEIPT_SCHEMA = """
CREATE TABLE IF NOT EXISTS task_completion_receipts (
  id INTEGER PRIMARY KEY,
  case_id TEXT NOT NULL REFERENCES cases(case_id),
  task_id INTEGER NOT NULL REFERENCES preparation_tasks(id),
  option_id INTEGER NOT NULL REFERENCES options(id),
  owner_label TEXT NOT NULL,
  acting_label TEXT NOT NULL,
  snapshot_id INTEGER NOT NULL REFERENCES snapshots(id),
  source_version_ids TEXT NOT NULL,
  evidence_version_ids TEXT NOT NULL,
  recorded_at TEXT NOT NULL,
  UNIQUE(task_id)
);
CREATE INDEX IF NOT EXISTS idx_task_receipts_case ON task_completion_receipts(case_id);
CREATE INDEX IF NOT EXISTS idx_task_receipts_option ON task_completion_receipts(option_id);
"""

# Tasks that still need human attention and have no receipt.
OPEN_TASK_STATUSES = frozenset({"not_started", "in_progress", "blocked"})
# Task states that flag a dependent option through a preparation_task edge.
STALE_TASK_STATUSES = frozenset({"blocked", "cancelled"})
# Prerequisite option states that flag a dependent option (needs_review is
# checked separately on review_state, per the brief's cause list).
TERMINAL_PREREQUISITE_STATUSES = frozenset({"rejected", "withdrawn", "expired"})


def valid_acting_label(value: object) -> str:
    """Fictional free-text acting label (2-80 chars, owner-label precedent)."""
    from .store import InvalidInput

    if not isinstance(value, str) or not 2 <= len(value.strip()) <= 80:
        raise InvalidInput("Task completion requires an acting label of 2-80 characters")
    return value.strip()


def current_basis_problems(db: sqlite3.Connection, case_id: str, option_id: int) -> list[str]:
    """List why an option's basis is superseded; empty means current.

    Checks the basis snapshot plus source/evidence premises only, with the
    same currentness semantics ``_require_current_option_dependencies``
    uses for those premise kinds. Deterministic order: snapshot first,
    then dependencies by id.
    """
    from .store import InvalidInput

    option = db.execute(
        "SELECT snapshot_id FROM options WHERE id=? AND case_id=?",
        (option_id, case_id)).fetchone()
    if not option:
        raise InvalidInput("Option not in this case")
    problems: list[str] = []
    snapshot = db.execute(
        "SELECT state FROM snapshots WHERE id=?", (option["snapshot_id"],)).fetchone()
    if not snapshot or snapshot["state"] == "stale":
        problems.append(f"basis snapshot #{option['snapshot_id']} is stale")
    deps = db.execute(
        """SELECT * FROM option_dependencies
        WHERE option_id=? AND kind IN ('source','evidence_assessment') ORDER BY id""",
        (option_id,)).fetchall()
    for dep in deps:
        if dep["kind"] == "source":
            src = db.execute(
                "SELECT document_id,version,state FROM source_versions WHERE id=? AND case_id=?",
                (dep["source_version_id"], case_id)).fetchone()
            if not src:
                problems.append(f"source dependency #{dep['id']} has no source in this case")
            elif src["state"] != "current":
                problems.append(
                    f"source dependency #{dep['id']} "
                    f"({src['document_id']}@{src['version']}) is {src['state']}")
        else:
            asm = db.execute(
                """SELECT v.evidence_key,v.version,v.state FROM evidence_assessments a
                JOIN evidence_versions v ON v.id=a.evidence_version_id
                WHERE a.id=? AND a.case_id=?""",
                (dep["evidence_assessment_id"], case_id)).fetchone()
            if not asm:
                problems.append(f"evidence dependency #{dep['id']} has no assessment in this case")
            elif asm["state"] != "current":
                problems.append(
                    f"evidence dependency #{dep['id']} "
                    f"({asm['evidence_key']}@{asm['version']}) is {asm['state']}")
    return problems


def pin_basis(db: sqlite3.Connection, case_id: str, option_id: int) -> dict:
    """Pin the direct basis an option acted on: snapshot + premise ids.

    Source ids come from direct source edges; evidence version ids are
    resolved through direct evidence-assessment edges. Sorted and
    deduplicated so two pins of the same basis are identical.
    """
    from .store import InvalidInput

    option = db.execute(
        "SELECT snapshot_id FROM options WHERE id=? AND case_id=?",
        (option_id, case_id)).fetchone()
    if not option:
        raise InvalidInput("Option not in this case")
    source_ids = sorted({row[0] for row in db.execute(
        """SELECT source_version_id FROM option_dependencies
        WHERE option_id=? AND kind='source' AND source_version_id IS NOT NULL""",
        (option_id,)).fetchall()})
    evidence_ids = sorted({row[0] for row in db.execute(
        """SELECT a.evidence_version_id FROM option_dependencies d
        JOIN evidence_assessments a ON a.id=d.evidence_assessment_id
        WHERE d.option_id=? AND d.kind='evidence_assessment'""",
        (option_id,)).fetchall()})
    return {
        "snapshot_id": int(option["snapshot_id"]),
        "source_version_ids": [int(v) for v in source_ids],
        "evidence_version_ids": [int(v) for v in evidence_ids],
    }


def write_completion_receipt(db: sqlite3.Connection, *, case_id: str, task_id: int,
                             option_id: int, owner_label: str, acting_label: str,
                             recorded_at: str) -> dict:
    """Write one immutable receipt; preserve the original on re-completion.

    The caller owns the write transaction and emits the ledger events.
    Returns ``{"receipt_id", "created", "basis"}`` where ``created`` is
    False when a receipt already existed for the task (first completion
    wins; the original row is never rewritten).
    """
    existing = db.execute(
        "SELECT id FROM task_completion_receipts WHERE task_id=?", (task_id,)).fetchone()
    basis = pin_basis(db, case_id, option_id)
    if existing:
        return {"receipt_id": int(existing["id"]), "created": False, "basis": basis}
    cur = db.execute(
        """INSERT INTO task_completion_receipts
        (case_id,task_id,option_id,owner_label,acting_label,snapshot_id,
         source_version_ids,evidence_version_ids,recorded_at)
        VALUES (?,?,?,?,?,?,?,?,?)""",
        (case_id, task_id, option_id, owner_label, acting_label,
         basis["snapshot_id"], json.dumps(basis["source_version_ids"]),
         json.dumps(basis["evidence_version_ids"]), recorded_at))
    return {"receipt_id": int(cur.lastrowid), "created": True, "basis": basis}


def get_receipt(db: sqlite3.Connection, case_id: str, task_id: int) -> dict | None:
    """Read one receipt with parsed basis lists, or None when absent."""
    row = db.execute(
        "SELECT * FROM task_completion_receipts WHERE task_id=? AND case_id=?",
        (task_id, case_id)).fetchone()
    if not row:
        return None
    receipt = dict(row)
    receipt["source_version_ids"] = json.loads(receipt["source_version_ids"])
    receipt["evidence_version_ids"] = json.loads(receipt["evidence_version_ids"])
    return receipt


def _is_contradicted(db: sqlite3.Connection, option_id: int) -> bool:
    """Mirror of CaseStore._option_contradicted for derived-flag reads."""
    direct = db.execute(
        "SELECT epistemic_status FROM options WHERE id=?", (option_id,)).fetchone()
    if direct and direct["epistemic_status"] == "contradicted":
        return True
    row = db.execute(
        """SELECT 1 FROM option_dependencies d
        JOIN evidence_assessments a ON a.id=d.evidence_assessment_id
        WHERE d.option_id=? AND a.relation='contradicts' LIMIT 1""",
        (option_id,)).fetchone()
    return row is not None


def derive_dependency_loss(db: sqlite3.Connection, case_id: str, option_id: int) -> dict:
    """Derive the dependency-loss flag for one option (read-only).

    Every cause names the dependency edge and the current state of its
    target. Causes are ordered by dependency id. This writes nothing:
    no ``optionality_threats`` rows are created, and the existing
    ``review_state`` / ``display_operational_status`` meanings are
    untouched. Recomputation after the next change reflects the new
    state; history stays in the events ledger.
    """
    causes: list[str] = []
    deps = db.execute(
        "SELECT * FROM option_dependencies WHERE option_id=? ORDER BY id",
        (option_id,)).fetchall()
    for dep in deps:
        dep_id = int(dep["id"])
        if dep["kind"] == "source":
            src = db.execute(
                "SELECT document_id,version,state FROM source_versions WHERE id=?",
                (dep["source_version_id"],)).fetchone()
            if not src:
                causes.append(f"dependency #{dep_id} (source): target is missing")
            elif src["state"] != "current":
                causes.append(
                    f"dependency #{dep_id} (source): "
                    f"{src['document_id']}@{src['version']} is {src['state']}")
        elif dep["kind"] == "evidence_assessment":
            asm = db.execute(
                """SELECT v.evidence_key,v.version,v.state FROM evidence_assessments a
                JOIN evidence_versions v ON v.id=a.evidence_version_id WHERE a.id=?""",
                (dep["evidence_assessment_id"],)).fetchone()
            if not asm:
                causes.append(f"dependency #{dep_id} (evidence): target is missing")
            elif asm["state"] != "current":
                causes.append(
                    f"dependency #{dep_id} (evidence): "
                    f"{asm['evidence_key']}@{asm['version']} is {asm['state']}")
        elif dep["kind"] == "preparation_task":
            task = db.execute(
                "SELECT status FROM preparation_tasks WHERE id=? AND case_id=?",
                (dep["preparation_task_id"], case_id)).fetchone()
            if not task:
                causes.append(f"dependency #{dep_id} (preparation task): target is missing")
            elif task["status"] in STALE_TASK_STATUSES:
                causes.append(
                    f"dependency #{dep_id} (preparation task): "
                    f"task #{int(dep['preparation_task_id'])} is {task['status']}")
        elif dep["kind"] == "option":
            target = db.execute(
                "SELECT operational_status,review_state FROM options WHERE id=? AND case_id=?",
                (dep["depends_on_option_id"], case_id)).fetchone()
            if not target:
                causes.append(f"dependency #{dep_id} (option): target is missing")
            elif target["operational_status"] in TERMINAL_PREREQUISITE_STATUSES:
                causes.append(
                    f"dependency #{dep_id} (option): "
                    f"option #{int(dep['depends_on_option_id'])} "
                    f"is {target['operational_status']}")
            elif _is_contradicted(db, int(dep["depends_on_option_id"])):
                causes.append(
                    f"dependency #{dep_id} (option): "
                    f"option #{int(dep['depends_on_option_id'])} is held (contradicted)")
            elif target["review_state"] != "current":
                causes.append(
                    f"dependency #{dep_id} (option): "
                    f"option #{int(dep['depends_on_option_id'])} needs review")
    return {"derived": True, "present": bool(causes), "causes": causes}


def annotate_tasks_with_receipts(db: sqlite3.Connection,
                                 tasks: list[dict]) -> tuple[list[dict], dict]:
    """Attach receipt markers to task dicts and group open vs receipted.

    Each task gains ``receipt_id`` (int or None) and ``receipt_marker``:
    ``receipted``, ``no_receipt``, or ``receipt_predates_slice`` (done
    without a receipt, possible only for rows written before this slice;
    never backfilled). The summary lists ``open_task_ids`` (awaiting
    human attention, no receipt) and ``receipted_task_ids`` separately.
    Task order is preserved.
    """
    if not tasks:
        return [], {"open_task_ids": [], "receipted_task_ids": []}
    ids = [int(task["id"]) for task in tasks]
    marks = ",".join("?" for _ in ids)
    receipt_by_task = {int(row["task_id"]): int(row["id"]) for row in db.execute(
        f"SELECT id,task_id FROM task_completion_receipts WHERE task_id IN ({marks})",
        ids).fetchall()}
    open_ids: list[int] = []
    receipted_ids: list[int] = []
    for task in tasks:
        receipt_id = receipt_by_task.get(int(task["id"]))
        if receipt_id is not None:
            task["receipt_id"] = receipt_id
            task["receipt_marker"] = "receipted"
            receipted_ids.append(int(task["id"]))
        elif task["status"] == "done":
            task["receipt_id"] = None
            task["receipt_marker"] = "receipt_predates_slice"
        else:
            task["receipt_id"] = None
            task["receipt_marker"] = "no_receipt"
            if task["status"] in OPEN_TASK_STATUSES:
                open_ids.append(int(task["id"]))
    return tasks, {"open_task_ids": open_ids, "receipted_task_ids": receipted_ids}
