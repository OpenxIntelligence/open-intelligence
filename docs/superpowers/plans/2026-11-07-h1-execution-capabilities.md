# H1 execution capability catalog implementation plan

> For agentic workers: use superpowers:executing-plans. Keep checks tied to the exact source.

**Goal:** Make the existing Composer workload discoverable and exactly version-resolved without adding a competing execution, identity or source owner.

**Architecture:** The platform owns immutable capability metadata and exact-version lookup. The existing question/execution owner registers only its implemented `source-question-brief/1` workload and consults that registration before new execution and result validation. An offline worker CLI describes registrations; registration is not runtime readiness, permission, clinical qualification or arbitrary plugin execution.

**Tech stack:** Existing Python/FastAPI/PostgreSQL runtime; Python standard library for the catalog. No new dependency or migration.

**Spec:** The founder's one-platform/many-engines mandate, `docs/engineering/MODULAR_ENGINE_BOUNDARIES.md`, #103 L1, and OI-009/OI-013. Baseline #584 `37063baa4e93b8a48dad4e76fdabbdde438352b3`.

## Constraints and choices

Use a code-owned, immutable catalog rather than dynamic module imports, a new service/database or an external plugin marketplace. A future workload still needs its own executable adapter, schema qualification and review. Do not advertise the planned engines as implemented. Preserve every migration, source pin, grant, transaction, retry, lease, and human-review boundary. Keep #591 and the active relay work #625 untouched.

## Review focus

Unknown versions and aliases must never fall back to a nearby version. Duplicate registrations must fail before use. Mutable input or returned metadata must not modify a catalog. Catalog inspection must not read credentials or claim a healthy database. A manifest alone must not grant authority or change existing run wire contracts.

## Tasks

- [x] Write CLI regression showing catalog inspection fails on baseline, plus catalog identity/immutability and execution-kind rejection tests.
- [x] Implement `CapabilityDescriptor` and immutable `CapabilityCatalog` in `oi_api.execution_capabilities`; register the existing workload in `oi_api.composer_capabilities`.
- [x] Derive existing KIND/ACTIONS from registration. Reject unregistered/mismatched kinds before completion and before accepting an artifact, preserving existing source and authority checks.
- [x] Add mutually exclusive `--capabilities` and `--once`; keep patient/case mandatory for execution, and reject mixed discovery/execution arguments.
- [x] Extend the existing architecture manifest and focused execution CI test selection; run focused tests, architecture gate, full available suites and compilation. Record database/dependency limitations explicitly.
- [ ] Publish a dependent draft with exact parent/tree, tests and remaining review/acceptance. Do not merge or deploy.

## Execution ledger

CLI discovery was first run against the baseline and failed because execution
arguments were mandatory. The separate disabled-worker regression then failed
because it read a credential before checking registration. Both pass after the
implementation. No database write is mocked. Catalog replacement in retirement
tests represents trusted code configuration, not a public registration API.

Focused capability/worker/contract/access checks: 25 passed. Architecture: 31
passed; gate: 63 modules, 10 owners, 86 unchanged legacy symbol imports. Three
additional PostgreSQL tests reuse the canonical fictional run fixture and are
included by the existing `test_composer_run*.py` CI selection. They remain
unverified locally: `pydicom` is absent, as are PostgreSQL/Docker and its driver.

Full local API discovery was attempted, not silently omitted: its completed
run reported 393 tests, one failure, 88 errors and 27 skips. The named failure
was `test_independent_import_preserves_public_types_and_oncology_validation`,
whose child process could not import `pydicom`; import errors likewise retain
their tracebacks in the evidence bundle. This is not a passing full suite. An
earlier 90-second interrupted invocation is retained separately. No dependency
lock or assertion was relaxed. Exact-source hosted verification is mandatory.
