# H1 socket acceptance lifespan follow-up

**Goal:** Preserve the wrapped application's lifecycle contract while exercising
socket-backed image/report recovery. This closes a gap in the existing
socket/report plan's cleanup and lifecycle review focus; it is not a new gateway.

**Base:** PR #370 at `cc624fe3b258e39a3b833a0053ed9e9f2ced57be`, tree
`0ce8c9c7de0b3e776a7fbd07f825be1c95fb5926`.
**Existing spec:** `docs/superpowers/specs/2026-11-03-h1-socket-report-continuity.md`.
**Scope:** OI-006/OI-013 synthetic engineering; three files, no production owner,
permission, migration, dependency, workflow or frontend change.

## Reconciliation and decision

The earlier local-only socket/report bundle was not published wholesale. Live
inspection found that #361 already implemented that composition and #370 was
running its bounded-budget CI continuation. Preserve those owners and their
complete recovery driver. Reuse only the useful lifecycle test coverage missing
from the published fixture. No older source tree replaces newer work.

The wrapper entered the original lifespan but yielded `None` unconditionally.
Forward its yielded value unchanged; keep the socket available through wrapped
startup and teardown and retain existing cleanup/error behavior. The current
base application itself yields `None`, so this is a wrapper-composition defect,
not evidence of failed patient routes or a real-data incident.

## Execution checkpoint

- [x] Recover the SHA-256-verified #370 source artifact and reproduce its Git tree.
- [x] Run the original 54 socket/capacity/fixture tests: all pass, no skips.
- [x] Add seven stdlib-only lifecycle methods before changing the fixture.
- [x] Observe two failing subcases: populated and empty mappings become `None`.
      The `None` case and all cleanup cases already pass.
- [x] Bind the original context's yielded state and yield that exact object.
- [x] Run all 61 focused tests: pass, no skips.
- [ ] Publish a separate draft child and obtain new exact-head hosted acceptance.
- [ ] Obtain independent review; no independent reviewer result is asserted here.

## Test boundaries

The existing factory, async context managers, transport and Unix sockets are
real. Only app construction and manifest loading use small injected doubles so
these tests do not require PostgreSQL or unpinned third-party packages. They
verify state identity (populated mapping, empty mapping and `None`), startup/
shutdown ordering, original exception identity, cancellation propagation, and
socket/directory cleanup after app construction, parent startup/teardown, service
startup or worker-start failure. Successful socket reads occur in wrapped startup,
serving and teardown. A refused listener must never start the wrapped application.

These are lifecycle tests, not PostgreSQL acceptance. All inherited database,
report, no-skip, recovery, rights and browser gates remain unchanged and must run
against the new candidate. Parent passes are not new-head evidence. The saved
local bundle remains historical evidence, not a competing published owner.

## Remaining limits

No merge, deployment, real-patient input, model execution or clinical conclusion.
The fixture is same-process/same-UID and absent from the normal application
image. It does not establish private-PACS deployment, independent service
identity, direct-network bypass denial or external-archive recovery. Existing
PACS HOLD and production identity/consent gates remain. Local Python is 3.13.5;
the pinned full runtime, PostgreSQL and Docker are unavailable locally.
