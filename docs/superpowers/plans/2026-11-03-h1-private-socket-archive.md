# H1 private-socket archive implementation plan

> **For agentic workers:** Use superpowers:executing-plans to implement task by task.

**Goal:** Supply #277's existing archive port with a bounded, peer-verified reader.
**Architecture:** Operator-injected Linux pathname socket; existing source owner
retains all patient/source authorization, exact-byte comparison and receipt writes.
**Tech Stack:** Existing Python stack and standard-library sockets only.
**Spec:** `docs/superpowers/specs/2026-11-03-h1-private-socket-archive.md`.

## Global constraints
Fictional data only; exact #277 baseline; no dependency, schema, permission, UI,
workflow change or automatic activation. Preserve unrelated branches and main.

## Review focus
Reject identifier/path injection before connecting; reject malformed/multi-object
responses; enforce total deadlines despite trickle traffic; close every socket;
keep path/UID/upstream details out of public errors. Test each in task 1.

## Task 1 — transport and actual socket tests
- [x] Add `apps/api/tests/archive_socket_fixture.py` and
  `apps/api/tests/test_archive_socket.py`; run against absent implementation and
  record an explicit missing-feature assertion.
- [x] Implement `apps/api/src/oi_api/archive_socket.py`:
  `UnixSocketImageArchive(socket_path: str, *, expected_peer_uid: int,
  timeout_seconds: float = 5.0).read(study_uid, series_uid, sop_uid) -> bytes`.
- [x] Run `PYTHONPATH=apps/api/src:apps/api/tests:src python -m unittest
  discover -s apps/api/tests -p test_archive_socket.py -v` with real sockets.
- [x] Inspect failures, boundary cases, resource cleanup and exact-byte handling;
  add regressions before repairs. Record limitations, do not weaken assertions.

## Task 2 — existing owner integration and delivery
- [x] Add `apps/api/tests/test_archive_socket_custody.py` using existing PG/HTTP
  fixture and real Unix responder; no alternative stores or auth paths.
- [x] Run available inherited reference/source-integrity/data-boundary checks.
  Attempt exact-runtime acceptance; distinguish blocked/skipped tests from passes.
- [x] Update the existing private-PACS boundary document and backlog notes only
  within OI-006/OI-013. Preserve original broader acceptance requirements.
- [x] Verify patch application against the exact baseline tree; record hashes,
  tests, failures, unchanged paths and limits. Publish through available authorized
  tools or deliver a verified patch without claiming a push/hosted pass.

## Execution constraints observed before coding
The mounted #277 browser artifact SHA-256 matches its recorded digest, and the
extracted source Git tree equals the published #277 tree exactly. Current GitHub
discovery exposes reads but no commit/push action; plugin discovery confirms
GitHub is installed. Direct git fetch fails DNS. No publishing success is claimed.
Local Python is 3.13.5; the exact pinned pydicom/pg8000 and a PostgreSQL service
are absent. The transport suite is standard-library-only and can run locally.


## Executed evidence and remaining gates

- Baseline: 245 retained reference tests passed before implementation.
- Initial new-feature run: 29 explicit missing-reader assertion failures, no
  dependency/import errors. This demonstrates an absent feature, not an existing
  #277 patient disclosure defect.
- Initial implemented reader: all 29 actual-socket tests passed.
- Self-review added five checks. Two exposed real defects: an enormous integer
  timeout reached `math.isfinite` before bounds checking and raised OverflowError;
  kernel uid_t was decoded as signed and incorrectly rejected a high unsigned UID.
  Bounds now precede float conversion, and credentials use `=iII`. The original
  assertions were retained. The other three new checks already passed.
- Final transport suite: **34 tests passed, no skips**, in three fresh runs
  (4.327s, 4.679s, 4.469s) on local Python 3.13.5/Linux. Repeated runs are not
  additional distinct tests. The high-UID case injects kernel credential bytes;
  remaining request/response traffic uses real local sockets.
- Final inherited reference suite: **245 passed**, 27.698s.
- Final source-integrity suite: **15 passed**, 0.012s.
- Existing known-patient-download path guard passed. All four new Python files
  compiled. Git whitespace checks passed.
- Five real PostgreSQL/HTTP composition tests were authored and compiled but
  **not executed**. Exact pinned pydicom/pg8000 are absent; installed FastAPI is
  0.128.2 rather than 0.162.0; no PostgreSQL service is available. No alternate
  dependencies were installed to substitute for the accepted runtime.
- Whole-delta self-review completed. **No independent reviewer was available**;
  independent review remains an explicit gate, not a claimed approval.
- No main/parent/source branch change, merge, deployment, live PACS, patient data,
  external service credential, permission expansion or new dependency.

The delivery checkbox means a locally verified patch, not remote publication.
GitHub discovery supplied no commit/push operation; plugin discovery confirmed
GitHub installed; direct git fetch failed DNS. Hosted API/Compose/browser
acceptance remains **NOT RUN** for this patch. The verified #277 parent results
must not be attributed to it. Final patch application/tree verification and file
hashes are recorded in the accompanying local delivery receipt.

Ruling: execute this reversible continuation without another design approval —
AGENTS.md and the user's standing execution mandate explicitly direct bounded
engineering to proceed; the socket profile is an engineering choice, not a
production platform decision. A later gateway may require a separate wider
transport contract; do not weaken this profile silently.
