# Private archive read capacity implementation plan

> **For agentic workers:** Use superpowers:executing-plans inline; run tests before claiming completion.

**Goal:** Refuse excess archive transport work before opening another socket,
without weakening canonical custody or current authority.

**Architecture:** Add a shared, process-local admission object to the existing
transport module. Default each adapter to four slots; operators can share one
object across adapters. Do not queue, retry or enable an archive automatically.

**Tech Stack:** Existing Python standard library and inherited H1 test stack.

**Spec:** `docs/superpowers/specs/2026-11-03-h1-archive-read-capacity-design.md`.

## Global constraints
Capacity: exact integer 1..16, default 4; keyword-only reader argument.
No changes to existing owner, API, migrations, dependencies, workflows or UI.
Fictional inputs only; no production/clinical or distributed-limit claim.

## Review focus
- Many simultaneous refusals must not return slots owned by active reads.
- A closed upstream socket does not release capacity before parsing completes.
- Exceptions, including BaseException unwinding, must release admitted capacity.
- Shared capacity must span two distinct adapter objects without sharing data.
- HTTP authority withdrawal must still withhold an active response after overload.

## Task 1: transport admission and lifetime
Files: modify `apps/api/src/oi_api/archive_socket.py`; create
`apps/api/tests/test_archive_socket_capacity.py`.

- [x] Recover source artifact, reproduce exact parent tree; run existing 34 tests.
- [x] Write behavioral tests using event-controlled real sockets. Reproduce
  default excess admission on unchanged #320; record red output.
- [x] Add `ArchiveReadCapacity(max_in_flight: int = 4)` and keyword-only
  `capacity: ArchiveReadCapacity` to `UnixSocketImageArchive`.
- [x] Acquire nonblocking before socket creation; release in finally after socket
  exit and complete parsing. Preserve existing error sanitization/deadline.
- [x] Run new tests and unchanged transport suite, then repeated contention runs.
- [x] Commit tested implementation and tests locally.

## Task 2: actual custody composition and delivery
Files: create `apps/api/tests/test_archive_capacity_custody.py`; extend existing
`docs/engineering/H1_PRIVATE_PACS_READS.md` and OI-006/OI-013 backlog rows.

- [x] Author (database execution pending) tests for overload sanitized 503/no receipt/no fallback, successful later read,
  and active-read revocation using the real adapter with PostgreSQL/HTTP fixture.
  Use load_tests to exclude inherited duplicate tests.
- [x] Run available reference/data-boundary and focused tests; distinguish
  unavailable database execution from a pass.
- [x] Self-review the whole delta; explicitly record whether independent review ran.
- [ ] Publish a new draft child of #320; do not mutate existing owner branches.
- [ ] Inspect exact-head unchanged API/PostgreSQL/recovery and web workflows;
  record actual outcomes and any failed attempt without weakening assertions.

## Execution ledger
- Recovered parent artifact SHA-256:
  `7782759d4e2b86ab2baca6e09d3f521b5eda368eab430c535b66fa39e8715323`.
  Commit marker and Git tree match #320 exactly. Isolated local feature branch.
- Baseline: `PYTHONPATH=apps/api/src:src:apps/api/tests python -m unittest test_archive_socket -q`
  ran 34 tests, all passed, no skips.
- Parent hosted acceptance remains in #320; its historical local-only record
  is not erased or silently restated as this continuation's verification.

- Local tests-first checkpoint `1719c4ddc0acb7e33c7032326ee289ea376f5a63` recorded both new test modules before
  production changes. The default reader genuinely admitted the fifth held-peer
  request; the targeted test failed with `ArchiveTransportError not raised`.
- Final local transport suite: 48 passed (14 new + unchanged 34), zero skips.
  Reference suite: 245 passed. Data-boundary static scanner: passed within its
  existing coverage. Syntax checks passed; original transport tests unchanged.
- Five complete repeated cycles of the initial 14-test capacity suite passed.
  The separate-default-capacity test was then strengthened to saturate four
  default slots; final combined 48-test run passed. A preceding combined shell
  command timed out at 45 seconds after the reference suite and seven capacity
  cycles; it is not a completed ten-cycle run or a product timeout.
- Local database/runtime unavailable (no PostgreSQL/Docker executable; pg8000
  and approved code-only-pydicom absent). Three new composition methods NOT RUN
  locally; do not substitute syntax/reference results for PostgreSQL acceptance.
- Whole-delta self-review found no remaining issue in the bounded contract.
  Independent review was not performed; no fresh reviewer tool was available.
- Ruling: preserve the exact #320 transport parent rather than repeat concurrent
  #331/#332 history convergence — separate ownership and smaller acceptance scope.
