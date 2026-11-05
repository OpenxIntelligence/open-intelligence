"""Deliver authorized H1 encounter changes to the local operations receiver."""
from __future__ import annotations

import argparse
from contextlib import closing
from datetime import datetime
import hashlib
from http.client import HTTPConnection, HTTPException
import json
import os
from pathlib import Path
import re
import sqlite3
import stat

from .encounter_event_contract import EncounterEvents

PAGE_SIZE = 25
MAX_BODY = 32768
MAX_ID = 2**63 - 1


class FeedUnavailable(RuntimeError):
    """No authorized page is available for this attempt."""


def read_page(port, patient, token, after_id):
    # Numeric loopback only. HTTPConnection neither follows redirects nor uses proxies.
    if not re.fullmatch(r"[A-Za-z0-9._~-]{32,256}", token):
        raise FeedUnavailable("Credential unavailable")
    path = f"/v1/patients/{patient}/encounters/events?limit={PAGE_SIZE}&after_id={after_id}"
    with closing(HTTPConnection("127.0.0.1", port, timeout=5)) as connection:
        connection.request("GET", path, headers={"Authorization": f"Bearer {token}", "Accept": "application/json"})
        response = connection.getresponse()
        if response.status != 200:
            raise FeedUnavailable("Encounter feed unavailable")
        if response.headers.get_content_type() != "application/json":
            raise ValueError("Unexpected feed representation")
        raw = response.read(MAX_BODY + 1)
        if len(raw) > MAX_BODY:
            raise ValueError("Encounter page exceeds its bound")
        return json.loads(raw)


def checked_events(document, patient, cursor):
    page = EncounterEvents.model_validate(document, strict=True)
    if (page.patient_id != patient or not re.fullmatch(r"ACCESS-[0-9A-F]{32}", page.access_receipt_id)
            or len(page.events) > PAGE_SIZE or (page.has_more and len(page.events) != PAGE_SIZE)):
        raise ValueError("Unexpected patient, authorization receipt or page size")
    # Re-read the last committed event. A reset/truncated upstream cannot silently
    # leave the consumer at a higher cursor and make subsequent work disappear.
    if cursor and (not page.events or page.events[0].id != cursor):
        raise ValueError("The producer no longer supplies the checkpoint event")
    previous = max(0, cursor - 1)
    for event in page.events:
        if not previous < event.id <= MAX_ID or not 0 < event.encounter_id <= MAX_ID:
            raise ValueError("Invalid encounter event order or identity")
        previous = event.id
        if datetime.fromisoformat(event.occurred_at).utcoffset() is None:
            raise ValueError("Occurrence time requires an offset")
        if event.event_type == "clinical_note_draft_saved":
            if (event.encounter_revision is not None or not re.fullmatch(r"[A-Z][A-Z0-9-]{1,39}", event.note_key or "")
                    or event.note_version is None or not 1 <= event.note_version < 2**31):
                raise ValueError("Invalid note version reference")
        else:
            if (event.note_key is not None or event.note_version is not None or event.encounter_revision is None
                    or not 1 <= event.encounter_revision <= MAX_ID
                    or (event.event_type == "clinical_encounter_scheduled") != (event.encounter_revision == 1)):
                raise ValueError("Invalid encounter revision reference")
    if page.resume_after_id != previous:
        raise ValueError("Producer cursor differs from the last event")
    return page


def bind_store(db, scope):
    # Caller holds BEGIN IMMEDIATE, including while initializing a fresh receiver.
    version = db.execute("PRAGMA user_version").fetchone()[0]
    if version == 0:
        if db.execute("SELECT 1 FROM sqlite_schema LIMIT 1").fetchone():
            raise ValueError("Use a dedicated receiver database")
        db.execute("CREATE TABLE activity_scope (scope_sha256 TEXT PRIMARY KEY)")
        db.execute("INSERT INTO activity_scope VALUES (?)", (scope,))
        db.execute("""CREATE TABLE activity_receipts (
            event_id INTEGER PRIMARY KEY, event_sha256 TEXT NOT NULL,
            event_type TEXT NOT NULL, access_receipt TEXT NOT NULL)""")
        db.execute("""CREATE TABLE activity_totals (event_type TEXT PRIMARY KEY,
                   total INTEGER NOT NULL CHECK (total >= 1))""")
        version = 1
    elif version not in (1, 2) or db.execute("SELECT scope_sha256 FROM activity_scope").fetchall() != [(scope,)]:
        raise ValueError("Receiver schema or source scope differs")

    if version == 1:
        # Old receipts omit note identity. Reconstruct the inbox only from
        # freshly authorized pages that match their retained event hashes.
        db.execute("CREATE TABLE draft_checkpoint (through_id INTEGER NOT NULL)")
        db.execute("INSERT INTO draft_checkpoint VALUES (0)")
        db.execute("""CREATE TABLE latest_drafts (
            encounter_id INTEGER NOT NULL, note_key_hash TEXT NOT NULL,
            note_version INTEGER NOT NULL, event_id INTEGER NOT NULL UNIQUE REFERENCES activity_receipts(event_id),
            PRIMARY KEY (encounter_id, note_key_hash))""")
        db.execute("""CREATE TABLE draft_acknowledgements (
            event_id INTEGER PRIMARY KEY REFERENCES activity_receipts(event_id), access_receipt TEXT NOT NULL)""")
        db.execute("PRAGMA user_version=2")


def project_draft(db, event):
    if event.event_type != "clinical_note_draft_saved":
        return
    note_hash = hashlib.sha256(event.note_key.encode("ascii")).hexdigest()
    previous = db.execute("SELECT note_version FROM latest_drafts WHERE encounter_id=? AND note_key_hash=?",
                          (event.encounter_id, note_hash)).fetchone()
    if event.note_version != (previous[0] + 1 if previous else 1):
        raise ValueError("Nonconsecutive draft version; reconcile producer history")
    db.execute("""INSERT INTO latest_drafts VALUES (?, ?, ?, ?)
                  ON CONFLICT(encounter_id, note_key_hash) DO UPDATE SET
                      note_version=excluded.note_version, event_id=excluded.event_id""",
               (event.encounter_id, note_hash, event.note_version, event.id))


def inbox_result(db, page, inbox_after, acknowledge):
    # Only disclose or acknowledge after a fresh, complete feed read.
    if page.has_more:
        return {"status": "catching_up"}
    if acknowledge is not None:
        if not db.execute("SELECT 1 FROM latest_drafts WHERE event_id=?", (acknowledge,)).fetchone():
            return {"status": "superseded_or_unknown"}
        db.execute("""INSERT INTO draft_acknowledgements VALUES (?, ?)
                      ON CONFLICT(event_id) DO NOTHING""", (acknowledge, page.access_receipt_id))
        return {"acknowledged_event": acknowledge}
    rows = db.execute("""SELECT d.event_id, d.encounter_id, d.note_version FROM latest_drafts d
                         LEFT JOIN draft_acknowledgements a ON d.event_id=a.event_id
                         WHERE a.event_id IS NULL AND d.event_id>? ORDER BY d.event_id LIMIT ?""",
                      (inbox_after, PAGE_SIZE + 1)).fetchall()
    return {"pending_drafts": [dict(event_id=e, encounter_id=c, note_version=v) for e, c, v in rows[:PAGE_SIZE]],
            "next_after_event": rows[PAGE_SIZE-1][0] if len(rows) > PAGE_SIZE else None}


def checkpoint(db):
    return db.execute("SELECT through_id FROM draft_checkpoint").fetchone()[0]


def receive_once(path: Path, port, patient, token_provider, *, inbox_after=None, acknowledge=None):
    if ((inbox_after is not None and (type(inbox_after) is not int or not 0 <= inbox_after <= MAX_ID))
            or (acknowledge is not None and (type(acknowledge) is not int or not 1 <= acknowledge <= MAX_ID))
            or (inbox_after is not None and acknowledge is not None)):
        raise ValueError("Invalid draft inbox operation")
    if not re.fullmatch(r"PAT-[0-9A-F]{32}", patient) or type(port) is not int or not 1 <= port <= 65535:
        raise ValueError("Expected a synthetic patient and a local API port")
    scope = hashlib.sha256(f"encounter-activity/1:127.0.0.1:{port}:{patient}".encode("ascii")).hexdigest()
    # A private operator directory is required for the database and SQLite journal.
    fd = os.open(path, os.O_CREAT | os.O_RDWR | os.O_NOFOLLOW | os.O_NONBLOCK, 0o600)
    try:
        info = os.fstat(fd)
        if not stat.S_ISREG(info.st_mode) or info.st_mode & 0o077 or info.st_uid != os.geteuid():
            raise ValueError("Receiver database must be private to its operator")
    finally:
        os.close(fd)
    with closing(sqlite3.connect(path)) as db:
        db.execute("PRAGMA foreign_keys=ON")
        with db:
            db.execute("BEGIN IMMEDIATE")
            bind_store(db, scope)
            cursor = checkpoint(db)
        document = read_page(port, patient, token_provider(), max(0, cursor - 1))
        page = checked_events(document, patient, cursor)
        with db:
            db.execute("BEGIN IMMEDIATE")
            current = checkpoint(db)
            if current < cursor or current > page.resume_after_id:
                raise ValueError("Checkpoint changed; retry from the current position")
            received = db.execute("SELECT COALESCE(MAX(event_id), 0) FROM activity_receipts").fetchone()[0]
            if not page.has_more and received > page.resume_after_id:
                raise ValueError("Producer ended before a retained receipt")
            prior_hashes = dict(db.execute(
                "SELECT event_id, event_sha256 FROM activity_receipts WHERE event_id BETWEEN ? AND ?",
                (cursor, page.resume_after_id),
            ))
            replayed = [event.id for event in page.events if event.id <= received]
            if set(replayed) != prior_hashes.keys():
                raise ValueError("Producer omitted a previously delivered event")
            applied = 0
            for event in page.events:
                canonical = json.dumps(event.model_dump(), sort_keys=True, separators=(",", ":")).encode("ascii")
                digest = hashlib.sha256(canonical).hexdigest()
                if event.id in prior_hashes:
                    if prior_hashes[event.id] != digest:
                        raise ValueError("Producer changed a previously delivered event")
                else:
                    db.execute("INSERT INTO activity_receipts VALUES (?, ?, ?, ?)",
                               (event.id, digest, event.event_type, page.access_receipt_id))
                    db.execute("""INSERT INTO activity_totals VALUES (?, 1)
                                  ON CONFLICT(event_type) DO UPDATE SET total=activity_totals.total+1""",
                               (event.event_type,))
                    applied += 1
                if event.id > current:
                    project_draft(db, event)
            db.execute("UPDATE draft_checkpoint SET through_id=?", (page.resume_after_id,))
            counts = dict(db.execute("SELECT event_type, total FROM activity_totals"))
            result = {"status": "ok", "applied": applied, "has_more": page.has_more, "counts": counts}
            if inbox_after is not None or acknowledge is not None:
                result.update(inbox_result(db, page, inbox_after, acknowledge))
        return result


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--patient", required=True)
    parser.add_argument("--port", type=int, default=8000)
    parser.add_argument("--database", type=Path, required=True)
    parser.add_argument("--token-file", type=Path, required=True)
    action = parser.add_mutually_exclusive_group()
    action.add_argument("--pending-drafts-after", type=int, metavar="EVENT_ID",
                        help="List pending local intake items; start at 0")
    action.add_argument("--acknowledge-draft-event", type=int, metavar="EVENT_ID",
                        help="Record local operations intake of the exact draft event")
    args = parser.parse_args(argv)

    def token():
        with args.token_file.open("rb") as handle:
            raw = handle.read(259)
        if len(raw) > 258:
            raise FeedUnavailable("Credential unavailable")
        return raw.decode("ascii").rstrip("\r\n")

    try:
        result = receive_once(args.database, args.port, args.patient, token,
                              inbox_after=args.pending_drafts_after, acknowledge=args.acknowledge_draft_event)
    except (OSError, sqlite3.Error, HTTPException, FeedUnavailable, ValueError, RecursionError):
        print(json.dumps({"status": "unavailable"}))
        return 2
    print(json.dumps(result, sort_keys=True))
    return 3 if result["status"] == "superseded_or_unknown" else 0


if __name__ == "__main__":
    raise SystemExit(main())
