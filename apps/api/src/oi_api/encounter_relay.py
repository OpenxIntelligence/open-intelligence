"""Relay one authorized H1 encounter change page to a fictional activity counter."""
from __future__ import annotations

import argparse
from contextlib import closing, contextmanager
from datetime import datetime
import hashlib
from http.client import HTTPConnection, HTTPException
import json
import os
from pathlib import Path
import re
import sqlite3
import stat
import tempfile

from .encounter_event_contract import EncounterEvents

PAGE_SIZE = 25
MAX_BODY = 32768
MAX_ID = 2**63 - 1
ACCESS_RECEIPT = re.compile(r"ACCESS-[0-9A-F]{32}")


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
    if (page.patient_id != patient or not ACCESS_RECEIPT.fullmatch(page.access_receipt_id)
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


def bind_store(db, scope, *, initialize=True):
    # Caller holds a transaction; fresh receivers require BEGIN IMMEDIATE.
    version = db.execute("PRAGMA user_version").fetchone()[0]
    if version == 0 and initialize:
        if db.execute("SELECT 1 FROM sqlite_schema LIMIT 1").fetchone():
            raise ValueError("Use a dedicated receiver database")
        db.execute("CREATE TABLE activity_scope (scope_sha256 TEXT PRIMARY KEY)")
        db.execute("INSERT INTO activity_scope VALUES (?)", (scope,))
        db.execute("""CREATE TABLE activity_receipts (
            event_id INTEGER PRIMARY KEY, event_sha256 TEXT NOT NULL,
            event_type TEXT NOT NULL, access_receipt TEXT NOT NULL)""")
        db.execute("""CREATE TABLE activity_totals (event_type TEXT PRIMARY KEY,
                   total INTEGER NOT NULL CHECK (total >= 1))""")
        db.execute("PRAGMA user_version=1")
    elif version != 1 or db.execute("SELECT scope_sha256 FROM activity_scope").fetchall() != [(scope,)]:
        raise ValueError("Receiver schema or source scope differs")


def checkpoint(db):
    return db.execute("SELECT COALESCE(MAX(event_id), 0) FROM activity_receipts").fetchone()[0]


def source_scope(port, patient):
    if not re.fullmatch(r"PAT-[0-9A-F]{32}", patient) or type(port) is not int or not 1 <= port <= 65535:
        raise ValueError("Expected a synthetic patient and a local API port")
    return hashlib.sha256(f"encounter-activity/1:127.0.0.1:{port}:{patient}".encode("ascii")).hexdigest()


@contextmanager
def open_receiver(path: Path, *, read_only=False):
    # A private operator directory is required for the database and SQLite journal.
    mode = os.O_RDONLY if read_only else os.O_CREAT | os.O_RDWR
    fd = os.open(path, mode | os.O_NOFOLLOW | os.O_NONBLOCK, 0o600)
    try:
        info = os.fstat(fd)
        if not stat.S_ISREG(info.st_mode) or info.st_mode & 0o077 or info.st_uid != os.geteuid():
            raise ValueError("Receiver database must be private to its operator")
    finally:
        os.close(fd)
    uri = path.absolute().as_uri() + ("?mode=ro" if read_only else "?mode=rw")
    with closing(sqlite3.connect(uri, uri=True)) as db:
        yield db


def event_digest(event):
    canonical = json.dumps(event.model_dump(), sort_keys=True, separators=(",", ":")).encode("ascii")
    return hashlib.sha256(canonical).hexdigest()


def receive_once(path: Path, port, patient, token_provider):
    scope = source_scope(port, patient)
    with open_receiver(path) as db:
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
            prior_hashes = dict(db.execute(
                "SELECT event_id, event_sha256 FROM activity_receipts WHERE event_id BETWEEN ? AND ?",
                (cursor, current),
            ))
            replayed = [event.id for event in page.events if event.id <= current]
            if set(replayed) != prior_hashes.keys():
                raise ValueError("Producer omitted a previously delivered event")
            applied = 0
            for event in page.events:
                digest = event_digest(event)
                if event.id in prior_hashes:
                    if prior_hashes[event.id] != digest:
                        raise ValueError("Producer changed a previously delivered event")
                    continue
                db.execute("INSERT INTO activity_receipts VALUES (?, ?, ?, ?)",
                           (event.id, digest, event.event_type, page.access_receipt_id))
                db.execute("""INSERT INTO activity_totals VALUES (?, 1)
                              ON CONFLICT(event_type) DO UPDATE SET total=activity_totals.total+1""",
                           (event.event_type,))
                applied += 1
            counts = dict(db.execute("SELECT event_type, total FROM activity_totals"))
        return {"status": "ok", "applied": applied, "has_more": page.has_more, "counts": counts}


def verify_history(path: Path, port, patient, token_provider):
    """Reconcile all deliveries through a captured checkpoint without applying any events."""
    scope = source_scope(port, patient)
    with open_receiver(path, read_only=True) as db:
        # Capture the receiver's checkpoint and effects together. Leave no SQLite
        # transaction open across network I/O: normal delivery may append later IDs.
        with db:
            db.execute("BEGIN")
            bind_store(db, scope, initialize=False)
            through = checkpoint(db)
            if db.execute("SELECT 1 FROM activity_receipts WHERE event_id <= 0 LIMIT 1").fetchone():
                raise ValueError("Invalid receiver event identity")
            totals = dict(db.execute("SELECT event_type, total FROM activity_totals"))
        cursor = 0
        verified = {}
        while True:
            document = read_page(port, patient, token_provider(), max(0, cursor - 1))
            page = checked_events(document, patient, cursor)
            end = min(page.resume_after_id, through)
            # Repeat the page boundary to verify continuity across HTTP reads.
            events = [e for e in page.events if e.id <= through]
            received = db.execute("""SELECT event_id, event_sha256, event_type, access_receipt FROM activity_receipts
                WHERE event_id BETWEEN ? AND ? ORDER BY event_id LIMIT ?""",
                (cursor, end, PAGE_SIZE + 1)).fetchall()
            expected = [(e.id, event_digest(e), e.event_type) for e in events]
            if (any(not isinstance(r[3], str) or not ACCESS_RECEIPT.fullmatch(r[3]) for r in received)
                    or [row[:3] for row in received] != expected):
                raise ValueError("Producer history and receiver receipts differ")
            for event in events:
                if event.id > cursor:
                    verified[event.event_type] = verified.get(event.event_type, 0) + 1
            if end == through:
                if verified != totals:
                    raise ValueError("Receiver activity totals differ from replay")
                return {"status": "verified", "through_event_id": through,
                        "verified_events": sum(verified.values())}
            if not page.has_more or end <= cursor:
                raise ValueError("Producer history ends before the receiver checkpoint")
            cursor = end


def backup_receiver(path: Path, destination: Path, port, patient, token_provider):
    """Publish one consistent, independently verified receiver snapshot without replacing a file."""
    scope = source_scope(port, patient)
    directory = destination.parent
    info = directory.lstat()
    if not stat.S_ISDIR(info.st_mode) or info.st_uid != os.geteuid() or info.st_mode & 0o077:
        raise ValueError("Use an operator-private backup directory")
    if os.path.lexists(destination):
        raise FileExistsError("Choose an unused backup path")
    # Require current feed access both before staging private records and while
    # verifying the copied prefix immediately before publication.
    checked_events(read_page(port, patient, token_provider(), 0), patient, 0)
    # Copy only the three receiver-owned tables, from one read transaction. Do
    # not export unused pages, triggers or unrelated objects from the source.
    with tempfile.TemporaryDirectory(prefix=".encounter-backup-", dir=directory) as working:
        temporary = Path(working) / "activity.sqlite"
        with open_receiver(path, read_only=True) as original, open_receiver(temporary) as copied:
            with original, copied:
                original.execute("BEGIN")
                copied.execute("BEGIN IMMEDIATE")
                bind_store(original, scope, initialize=False)
                bind_store(copied, scope)
                copied.executemany("INSERT INTO activity_receipts VALUES (?,?,?,?)",
                    original.execute("SELECT event_id,event_sha256,event_type,access_receipt FROM activity_receipts"))
                copied.executemany("INSERT INTO activity_totals VALUES (?,?)",
                    original.execute("SELECT event_type,total FROM activity_totals"))
        verified = verify_history(temporary, port, patient, token_provider)
        # A same-filesystem hard link exposes the checked bytes atomically and
        # fails if another process published to this name in the meantime.
        os.link(temporary, destination)
        fd = os.open(directory, os.O_RDONLY | os.O_DIRECTORY)
        try:
            os.fsync(fd)
        finally:
            os.close(fd)
        return {**verified, "status": "backup_verified"}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--patient", required=True)
    parser.add_argument("--port", type=int, default=8000)
    parser.add_argument("--database", type=Path, required=True)
    parser.add_argument("--token-file", type=Path, required=True)
    recovery = parser.add_mutually_exclusive_group()
    recovery.add_argument("--backup-to", type=Path, help="Publish a verified copy at a new private path")
    recovery.add_argument("--verify-history", action="store_true",
                        help="Recheck all delivered events and totals without applying new events")
    args = parser.parse_args(argv)

    def token():
        with args.token_file.open("rb") as handle:
            raw = handle.read(259)
        if len(raw) > 258:
            raise FeedUnavailable("Credential unavailable")
        return raw.decode("ascii").rstrip("\r\n")

    try:
        if args.backup_to is not None:
            result = backup_receiver(args.database, args.backup_to, args.port, args.patient, token)
        else:
            operation = verify_history if args.verify_history else receive_once
            result = operation(args.database, args.port, args.patient, token)
    except (OSError, sqlite3.Error, HTTPException, FeedUnavailable, ValueError, RecursionError):
        print(json.dumps({"status": "unavailable"}))
        return 2
    print(json.dumps(result, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
