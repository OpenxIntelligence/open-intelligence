# H1 Socket/Report Continuity Implementation Plan

> **For agentic workers:** Use superpowers:executing-plans to implement task by task.

**Goal:** Bring the bounded socket reader into the connected image/report workflow and restored HTTP acceptance.
**Architecture:** Reuse #351 transport unchanged on #358. Adapt only test infrastructure to serve the existing fictional file archive over a Unix socket.
**Tech Stack:** Existing Python/FastAPI/PostgreSQL and stdlib sockets; no new dependencies.
**Spec:** `docs/superpowers/specs/2026-11-03-h1-socket-report-continuity.md`.

## Global constraints
Exact base/donor pins and synthetic-only limits in the spec apply. Preserve every
base runtime owner except the additive transport module, all migrations, public
API contracts, permissions, dependencies and frontend. No merge or deployment.

## Review focus
- Failed or overloaded socket reads leave report/task/citation business history unchanged.
- Source amendment/revocation during retrieval still prevents disclosure.
- Independent authored-evidence withdrawal does not revoke image access.
- Acceptance service failures are bounded, sanitized and cannot forward credentials.
- Listener and temporary directory cleanup survive application restart/failure.

## Task 1 — reuse bounded transport
- [x] Copy the five donor fixture/test modules to `apps/api/tests/` before runtime adoption.
- [x] Run the exact-original socket test on unchanged base; require an explicit missing-reader assertion.
- [x] Copy `apps/api/src/oi_api/archive_socket.py` unchanged; run both transport suites (48 methods).
- [x] Preserve donor PostgreSQL custody/capacity suites unchanged for hosted execution.

## Task 2 — socket-backed recovery fixture
- [x] Add failing stdlib-only tests in `apps/api/tests/test_socket_archive_acceptance.py` for exact bytes, rejected requests, bounded failures and service cleanup.
- [x] Implement `socket_archive_service(reader, socket_path)` and the existing `create_acceptance_app()` in `apps/api/tools/archive_acceptance_app.py`.
- [x] Extend only the already mounted acceptance factory with socket service lifecycle. Keep underlying AcceptanceArchive and the complete recovery driver unchanged.
- [x] Run fixture tests and AST/syntax checks; preserve exact base ownership.

## Task 3 — combined history and delivery
- [x] Add `apps/api/tests/test_socket_archive_report_continuity.py`: real socket/report amendment, independent content withdrawal, overload/revocation and retained identities. Select only new test methods.
- [x] Run reference regressions, syntax checks, donor-byte and base-ownership comparisons.
- [x] Record actual results/limits in this scoped execution record and append OI-006/OI-013 acceptance notes; preserve the base evidence-continuity record unchanged.
- [ ] Publish a new draft child of #358; leave prior branches untouched. Verify new exact-head hosted API, six recovery probes and web workflow; never substitute parent results.
- [x] Perform whole-delta self-review; independent review remains pending unless actually obtained.

## Local execution checkpoint — 3 November 2026

Recovered exact base Git tree `4ece40ad6183642f1c0b2fd2978b1bcac07d0e89`
from the SHA-256 verified #358 source artifact. Five donor test/fixture modules
and the transport runtime are byte-identical to #351. The missing-reader
regression failed explicitly on unchanged base before runtime adoption.

The socket-backed acceptance fixture first produced six missing-feature failures.
After implementation, 54 transport/fixture methods pass with zero skips; the
reference suite passes 287 tests. The oversized-request test initially expected
EOF after its complete error reply; actual 2048-byte input produced that reply
followed by a reset because the server did not drain excess input. The helper now
accepts reset only after the exact complete denial. No runtime bound was widened.

Three new joined-history PostgreSQL/HTTP methods and eight exact donor custody/
capacity methods are present and syntax checked. They are NOT locally executed:
this executor has no PostgreSQL/Docker or the pinned pg8000/code-only-pydicom
runtime. New exact-head hosted API, six recovery probes and browser acceptance
remain pending at this checkpoint. No parent run substitutes for them.

The original AcceptanceArchive class and complete recovery driver remain
unchanged. Only the already mounted test factory routes through the socket
client and manages its lifespan. The peer is same-process/same-UID, not a private
PACS deployment. All application owners, migrations, dependency locks, frontend
and workflows are retained. Whole-delta self-review is recorded; no independent
reviewer was available in this execution. Independent owner/security review,
parent-stack integration and all clinical/production gates remain open.

## Resumed hosted qualification — 3 November 2026

This continuation starts from published #361 commit
`6223346d0192f99e64bf74cb306fce5d624bf8f1`, tree
`56eb412025704ac4592ae95c352533b987a67e7b`. The downloaded web artifact
`13256760744` matched SHA-256
`a72a2f6cf518e8ccfc90eed4e08be49636c64fa919966f0ac8933a4b38a604a6`;
all 462 source blobs and executable classifications matched that exact tree.
Tasks 1, 2 and the implementation part of Task 3 are already present. Resume
the final hosted-verification and independent-review checkpoint only.

### Observed interruption

The first API [run 41687984400](https://github.com/OpenxIntelligence/open-intelligence/actions/runs/41687984400)
at that source head was cancelled, not successful. The observed job ran from
17:49:49 to 18:09:49 UTC. Its configured `timeout-minutes` was 20. The logs contain
615 API/PostgreSQL test executions passing in 724.370 seconds, 287 reference
tests passing in 11.981 seconds, the inherited browser checks and success markers
for all six recovery helpers. The last evidence-recovery PASS was printed at
18:09:49.010 UTC, immediately before cancellation at 18:09:49.052 UTC. GitHub
recorded that step as cancelled; the final container/package inventory was
skipped. Preserve those partial observations without promoting the run to a pass.

The separate [web run 41687984401](https://github.com/OpenxIntelligence/open-intelligence/actions/runs/41687984401)
completed successfully on the original head: 297 client tests, production build
and the actual PostgreSQL/FastAPI/Chromium journey. This is original-head evidence,
not a substitute for verification of the continuation.

### Bounded repair and completion contract

Ruling: raise the existing API job budget from 20 to 30 minutes because its
complete sequential acceptance exceeded the inherited budget. Keep every test,
no-skip rule, synthetic-data check, rights gate, recovery helper and final inventory
unchanged. If the diagnosis is wrong, a hung run can consume up to ten additional
runner minutes; the new complete run must establish success rather than assume it.
No application code, test implementation, public API, schema, grant, dependency,
container definition or frontend behavior changes in this repair.

- [x] Inspect the original exact-head job steps and complete log.
- [x] Recover and verify the original source tree and artifact identity.
- [x] Parse and compare the workflow; only the job budget changed semantically.
- [ ] Obtain independent whole-integration review and record concrete findings.
- [ ] Publish a separate draft child of #361 with an identical local/remote tree.
- [ ] Verify the new exact-head API, all six recovery helpers, final inventory,
      web build and actual browser; inspect the saved recovery evidence.
- [ ] Reconcile the existing canonical records and retain the cancelled history.

This remains independently authored synthetic engineering. The original #361
branch, other owners, deployment status and PACS HOLD remain unchanged.
