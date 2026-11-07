"""Deliver and reconcile authorized H1 encounter changes for the local operations receiver."""
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

from .encounter_event_contract import EncounterEvents, VisitEvents
from .encounter_workload import VisitWorkload

PAGE_SIZE = 25
MAX_BODY = 32768
MAX_ID = 2**63 - 1
ACCESS_RECEIPT = re.compile(r"ACCESS-[0-9A-F]{32}")


class FeedUnavailable(RuntimeError):
    """No authorized page is available for this attempt."""


def read_page(port, patient, token, after_id, *, visit_workload=False):
    # Numeric loopback only. HTTPConnection neither follows redirects nor uses proxies.
    if not re.fullmatch(r"[A-Za-z0-9._~-]{32,256}", token):
        raise FeedUnavailable("Credential unavailable")
    path = f"/v1/patients/{patient}/encounters/events?limit={PAGE_SIZE}&after_id={after_id}"
    if visit_workload:
        path += "&include_visit_state=true"
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


def checked_events(document, patient, cursor, *, visit_workload=False):
    contract = VisitEvents if visit_workload else EncounterEvents
    page = contract.model_validate(document, strict=True)
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


def bind_store(db, scope, *, initialize=True, target_version=2):
    # Caller holds BEGIN IMMEDIATE, including while initializing a fresh receiver.
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
        version = 1
    elif version not in (1, 2) or db.execute("SELECT scope_sha256 FROM activity_scope").fetchall() != [(scope,)]:
        raise ValueError("Receiver schema or source scope differs")

    if version == 1 and db.execute(
        "SELECT 1 FROM sqlite_schema WHERE lower(name) IN "
        "('draft_checkpoint','latest_drafts','draft_acknowledgements') LIMIT 1"
    ).fetchone():
        raise ValueError("Inconsistent receiver version; refusing to discard draft state")

    if version == 1 and initialize and target_version == 2:
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
        version = 2
    return version


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
        db.execute("PRAGMA foreign_keys=ON")
        yield db


def event_digest(event):
    canonical = json.dumps(event.model_dump(exclude={"from_status", "to_status"}),
                           sort_keys=True, separators=(",", ":")).encode("ascii")
    return hashlib.sha256(canonical).hexdigest()


def receive_once(path: Path, port, patient, token_provider, *, inbox_after=None, acknowledge=None, visit_workload=False):
    if ((inbox_after is not None and (type(inbox_after) is not int or not 0 <= inbox_after <= MAX_ID))
            or (acknowledge is not None and (type(acknowledge) is not int or not 1 <= acknowledge <= MAX_ID))
            or (inbox_after is not None and acknowledge is not None)):
        raise ValueError("Invalid draft inbox operation")
    scope = source_scope(port, patient)
    with open_receiver(path) as db:
        with db:
            db.execute("BEGIN IMMEDIATE")
            bind_store(db, scope)
            workload = VisitWorkload(db) if visit_workload else None
            draft_through = checkpoint(db)
            cursor = min(workload.checkpoint(), draft_through) if workload else draft_through
        options = {"visit_workload": True} if workload else {}
        document = read_page(port, patient, token_provider(), max(0, cursor - 1), **options)
        page = checked_events(document, patient, cursor, **options)
        with db:
            db.execute("BEGIN IMMEDIATE")
            draft_through = checkpoint(db)
            current = min(workload.checkpoint(), draft_through) if workload else draft_through
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
                digest = event_digest(event)
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
                if event.id > draft_through:
                    project_draft(db, event)
                if workload:
                    workload.apply(event, page.access_receipt_id)
            if page.resume_after_id > draft_through:
                db.execute("UPDATE draft_checkpoint SET through_id=?", (page.resume_after_id,))
            counts = dict(db.execute("SELECT event_type, total FROM activity_totals"))
            result = {"status": "ok", "applied": applied, "has_more": page.has_more, "counts": counts}
            if workload:
                result["visit_workload"] = None if page.has_more else workload.totals()
            if inbox_after is not None or acknowledge is not None:
                result.update(inbox_result(db, page, inbox_after, acknowledge))
        return result



def draft_fingerprint(db):
    # Stream in primary-key order; replay state may be larger than one feed page.
    digest = hashlib.sha256()
    for row in db.execute("""SELECT encounter_id,note_key_hash,note_version,event_id
                             FROM latest_drafts ORDER BY encounter_id,note_key_hash"""):
        digest.update(json.dumps(row, separators=(",", ":")).encode("ascii") + b"\n")
    return digest.digest()


def local_acknowledgements(db, draft_through):
    """Identify receiver-owned actions separately from replayable EHR events."""
    digest = hashlib.sha256()
    count = 0
    rows = db.execute("""SELECT a.event_id,a.access_receipt,r.event_type
        FROM draft_acknowledgements a LEFT JOIN activity_receipts r ON r.event_id=a.event_id
        ORDER BY a.event_id""")
    for event_id, receipt, category in rows:
        if (category != "clinical_note_draft_saved" or not 0 < event_id <= draft_through
                or not isinstance(receipt, str) or not ACCESS_RECEIPT.fullmatch(receipt)):
            raise ValueError("Local acknowledgement has an invalid note or access reference")
        digest.update(json.dumps([event_id, receipt], separators=(",", ":")).encode("ascii") + b"\n")
        count += 1
    return {"count": count, "sha256": digest.hexdigest(), "source": "local_operations_receiver"}


def verify_history(path: Path, port, patient, token_provider, *, expected_ack_sha256=None):
    """Reconcile all deliveries through a captured checkpoint without applying any events."""
    scope = source_scope(port, patient)
    with open_receiver(path, read_only=True) as db, closing(sqlite3.connect("")) as replay:
        # Capture the receiver's checkpoint and effects together. Leave no SQLite
        # transaction open across network I/O: normal delivery may append later IDs.
        with db:
            db.execute("BEGIN")
            version = bind_store(db, scope, initialize=False)
            through = db.execute("SELECT COALESCE(MAX(event_id),0) FROM activity_receipts").fetchone()[0]
            if expected_ack_sha256 is not None and (
                version != 2 or not re.fullmatch(r"[0-9a-f]{64}", expected_ack_sha256)
            ):
                raise ValueError("Expected a v2 receiver and its saved acknowledgement digest")
            if version == 2:
                checkpoints = db.execute("SELECT through_id FROM draft_checkpoint").fetchmany(2)
                if len(checkpoints) != 1 or not 0 <= checkpoints[0][0] <= through:
                    raise ValueError("Invalid draft inbox checkpoint")
                draft_through = checkpoints[0][0]
                if draft_through and not db.execute("SELECT 1 FROM activity_receipts WHERE event_id=?",
                                                    (draft_through,)).fetchone():
                    raise ValueError("Missing draft inbox checkpoint receipt")
                drafts = draft_fingerprint(db)
                acknowledgements = local_acknowledgements(db, draft_through)
                if expected_ack_sha256 is not None and expected_ack_sha256 != acknowledgements["sha256"]:
                    raise ValueError("Local acknowledgements differ from the saved backup receipt")
                # The scratch database contains derived references only. No writes to the running receiver.
                bind_store(replay, scope)
            if db.execute("SELECT 1 FROM activity_receipts WHERE event_id <= 0 LIMIT 1").fetchone():
                raise ValueError("Invalid receiver event identity")
            totals = dict(db.execute("SELECT event_type, total FROM activity_totals"))
            workload = None
            if VisitWorkload.exists(db):
                workload = VisitWorkload(replay)
                workload_through = db.execute("SELECT COALESCE(MAX(event_id), 0) FROM workload_receipts").fetchone()[0]
                if workload_through > through or db.execute(
                    "SELECT 1 FROM workload_receipts WHERE event_id <= 0 LIMIT 1"
                ).fetchone():
                    raise ValueError("Invalid workload checkpoint")
                saved_visits = VisitWorkload.state(db)
        options = {"visit_workload": True} if workload else {}
        cursor = 0
        verified = {}
        while True:
            document = read_page(port, patient, token_provider(), max(0, cursor - 1), **options)
            page = checked_events(document, patient, cursor, **options)
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
            if workload:
                projected = [e for e in events if e.id <= workload_through]
                receipts = db.execute("""SELECT event_id, from_status, to_status, access_receipt FROM workload_receipts
                    WHERE event_id BETWEEN ? AND ? ORDER BY event_id LIMIT ?""",
                    (cursor, min(end, workload_through), PAGE_SIZE + 1)).fetchall()
                if ([r[:3] for r in receipts] != [(e.id, e.from_status, e.to_status) for e in projected]
                        or any(not isinstance(r[3], str) or not ACCESS_RECEIPT.fullmatch(r[3]) for r in receipts)):
                    raise ValueError("Visit workload receipts differ from the authorized history")
                for event in projected:
                    workload.apply(event, page.access_receipt_id)
            for event in events:
                if event.id > cursor:
                    if version == 2 and event.id <= draft_through:
                        project_draft(replay, event)
                    verified[event.event_type] = verified.get(event.event_type, 0) + 1
            if end == through:
                if verified != totals:
                    raise ValueError("Receiver activity totals differ from replay")
                if version == 2:
                    if draft_fingerprint(replay) != drafts:
                        raise ValueError("Receiver draft inbox differs from authorized replay")
                result = {"status": "verified", "through_event_id": through,
                          "verified_events": sum(verified.values())}
                if version == 2:
                    if draft_through != through:
                        result["draft_through_event_id"] = draft_through
                    if acknowledgements["count"]:
                        result["local_acknowledgements"] = acknowledgements
                if workload:
                    if VisitWorkload.state(replay) != saved_visits:
                        raise ValueError("Visit workload state differs from authorized history")
                    result["workload_through_event_id"] = workload_through
                return result
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
    # Copy only receiver-owned columns, from one read transaction. Do
    # not export unused pages, triggers or unrelated objects from the source.
    with tempfile.TemporaryDirectory(prefix=".encounter-backup-", dir=directory) as working:
        temporary = Path(working) / "activity.sqlite"
        with open_receiver(path, read_only=True) as original, open_receiver(temporary) as copied:
            with original, copied:
                original.execute("BEGIN")
                copied.execute("BEGIN IMMEDIATE")
                version = bind_store(original, scope, initialize=False)
                bind_store(copied, scope, target_version=version)
                copied.executemany("INSERT INTO activity_receipts VALUES (?,?,?,?)",
                    original.execute("SELECT event_id,event_sha256,event_type,access_receipt FROM activity_receipts"))
                copied.executemany("INSERT INTO activity_totals VALUES (?,?)",
                    original.execute("SELECT event_type,total FROM activity_totals"))
                if version == 2:
                    copied.execute("DELETE FROM draft_checkpoint")
                    copied.executemany("INSERT INTO draft_checkpoint VALUES (?)",
                        original.execute("SELECT through_id FROM draft_checkpoint"))
                    copied.executemany("INSERT INTO latest_drafts VALUES (?,?,?,?)",
                        original.execute("SELECT encounter_id,note_key_hash,note_version,event_id FROM latest_drafts"))
                    copied.executemany("INSERT INTO draft_acknowledgements VALUES (?,?)",
                        original.execute("SELECT event_id,access_receipt FROM draft_acknowledgements"))
                    original_actions = local_acknowledgements(original, checkpoint(original))
                    if local_acknowledgements(copied, checkpoint(copied)) != original_actions:
                        raise ValueError("Backup changed locally recorded acknowledgements")
                if VisitWorkload.exists(original):
                    VisitWorkload.copy(original, copied)
        verified = verify_history(temporary, port, patient, token_provider)
        if verified["verified_events"] == 0:
            raise ValueError("Refusing to publish an empty receiver backup")
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
    action = parser.add_mutually_exclusive_group()
    action.add_argument("--visit-workload", action="store_true", help="Project the current visit workload")
    action.add_argument("--pending-drafts-after", type=int, metavar="EVENT_ID",
                        help="List pending local intake items; start at 0")
    action.add_argument("--acknowledge-draft-event", type=int, metavar="EVENT_ID",
                        help="Record local operations intake of the exact draft event")
    action.add_argument("--backup-to", type=Path, help="Publish a verified receiver copy at a new private path")
    action.add_argument("--verify-history", action="store_true", help="Reconcile the restored receiver with the feed")
    parser.add_argument("--expect-ack-sha256", help="Compare restored local actions with the digest on the backup receipt")
    args = parser.parse_args(argv)
    if args.expect_ack_sha256 is not None and not args.verify_history:
        parser.error("--expect-ack-sha256 requires --verify-history")

    def token():
        with args.token_file.open("rb") as handle:
            raw = handle.read(259)
        if len(raw) > 258:
            raise FeedUnavailable("Credential unavailable")
        return raw.decode("ascii").rstrip("\r\n")

    try:
        if args.backup_to is not None:
            result = backup_receiver(args.database, args.backup_to, args.port, args.patient, token)
        elif args.verify_history:
            result = verify_history(args.database, args.port, args.patient, token, expected_ack_sha256=args.expect_ack_sha256)
        else:
            result = receive_once(args.database, args.port, args.patient, token,
                                  inbox_after=args.pending_drafts_after, acknowledge=args.acknowledge_draft_event,
                                  visit_workload=args.visit_workload)
    except (OSError, sqlite3.Error, HTTPException, FeedUnavailable, ValueError, RecursionError):
        print(json.dumps({"status": "unavailable"}))
        return 2
    print(json.dumps(result, sort_keys=True))
    return 3 if result["status"] == "superseded_or_unknown" else 0


if __name__ == "__main__":
    raise SystemExit(main())
