"""Operations' derived visit workload, stored alongside the existing delivery receipts."""
from __future__ import annotations

import sqlite3

from open_intelligence.clinical_encounters import TRANSITIONS

from .encounter_event_contract import VisitEvent


class VisitWorkload:
    def __init__(self, db: sqlite3.Connection):
        self.db = db
        if self.exists(db):
            return
        # Lazily add the projection to existing v1 receiver files. Keep the old
        # receipts in place so a legacy relay and a workload relay can alternate.
        db.execute("""CREATE TABLE workload_visits (
            encounter_id INTEGER PRIMARY KEY, revision INTEGER NOT NULL,
            status TEXT NOT NULL CHECK(status IN ('scheduled','in_progress','completed','cancelled')))""")
        db.execute("""CREATE TABLE workload_receipts (
            event_id INTEGER PRIMARY KEY REFERENCES activity_receipts(event_id),
            from_status TEXT, to_status TEXT, access_receipt TEXT NOT NULL)""")

    @staticmethod
    def exists(db: sqlite3.Connection) -> bool:
        tables = db.execute("""SELECT type FROM sqlite_schema
            WHERE name IN ('workload_visits', 'workload_receipts')""").fetchall()
        if tables and tables != [('table',), ('table',)]:
            raise ValueError("Incomplete or invalid visit workload schema")
        return bool(tables)

    @staticmethod
    def state(db: sqlite3.Connection):
        return db.execute("SELECT encounter_id, revision, status FROM workload_visits ORDER BY encounter_id").fetchall()

    @staticmethod
    def copy(source: sqlite3.Connection, target: sqlite3.Connection) -> None:
        VisitWorkload(target)
        target.executemany("INSERT INTO workload_visits VALUES (?, ?, ?)",
                           source.execute("SELECT encounter_id, revision, status FROM workload_visits"))
        target.executemany("INSERT INTO workload_receipts VALUES (?, ?, ?, ?)",
                           source.execute("SELECT event_id, from_status, to_status, access_receipt FROM workload_receipts"))

    def checkpoint(self) -> int:
        return self.db.execute("SELECT COALESCE(MAX(event_id), 0) FROM workload_receipts").fetchone()[0]

    def apply(self, event: VisitEvent, access_receipt: str) -> None:
        transition = (event.from_status, event.to_status)
        prior = self.db.execute("SELECT from_status, to_status FROM workload_receipts WHERE event_id=?",
                                (event.id,)).fetchone()
        if prior is not None:
            if prior != transition:
                raise ValueError("Producer changed a previously applied visit transition")
            return
        visit = self.db.execute("SELECT revision, status FROM workload_visits WHERE encounter_id=?",
                                (event.encounter_id,)).fetchone()
        if event.event_type == "clinical_encounter_scheduled":
            if visit is not None or transition != (None, "scheduled"):
                raise ValueError("Unexpected visit scheduling event")
            self.db.execute("INSERT INTO workload_visits VALUES (?, 1, 'scheduled')", (event.encounter_id,))
        elif event.event_type == "clinical_encounter_state_changed":
            if (visit is None or event.encounter_revision != visit[0] + 1 or event.from_status != visit[1]
                    or event.to_status not in TRANSITIONS[visit[1]]):
                raise ValueError("Visit transition conflicts with its workload history")
            self.db.execute("UPDATE workload_visits SET revision=?, status=? WHERE encounter_id=?",
                            (event.encounter_revision, event.to_status, event.encounter_id))
        elif visit is None or transition != (None, None):
            raise ValueError("Unexpected visit reference on a note event")

        self.db.execute("INSERT INTO workload_receipts VALUES (?, ?, ?, ?)",
                        (event.id, *transition, access_receipt))

    def totals(self) -> dict[str, int]:
        return dict(self.db.execute("SELECT status, count(*) FROM workload_visits GROUP BY status"))
