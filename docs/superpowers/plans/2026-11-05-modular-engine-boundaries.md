# Modular engine boundaries implementation plan

> **For agentic workers:** use the executing-plans workflow and a fresh final
> review. The founder has explicitly requested implementation; routine reversible
> steps proceed without another permission cycle.

**Goal:** make existing H1 ownership and dependency boundaries enforceable while
preserving the connected application.

**Architecture:** a declarative owner/export/dependency catalog plus a standard
library Python AST checker, used by CI. Exact legacy exceptions retain observed
coupling without permitting it to expand silently.

**Tech stack:** existing Python, JSON and GitHub Actions. No new dependency.

**Spec:** `docs/engineering/MODULAR_ENGINE_BOUNDARIES.md`.

## Global constraints

- Use the canonical Open Intelligence patient/source/question/evidence/review owners.
- H1 remains Python/FastAPI/PostgreSQL and React/Vite/TypeScript; no Next.js.
- Synthetic data only. No model execution or external clinical service.
- No application/API/schema/authentication/authorization/clinical behavior change.
- Registration metadata does not grant execution, data access or clinical authority.
- Preserve existing acceptance gates and historical documentation.

## Review focus

- An undeclared new nested module must not escape package coverage.
- Relative imports, absolute imports, aliases and package imports must resolve consistently.
- Legacy exceptions must cover exact symbols and must disappear when no longer used.
- The scanner must never execute application code or follow source symlinks outside its tree.
- An invalid/ambiguous map must fail with a useful result rather than silently narrow enforcement.

### Task 1: executable boundary policy

**Files:** `tools/architecture/check_engine_boundaries.py`,
`tools/architecture/test_engine_boundaries.py`,
`docs/architecture/engine_boundaries.json`.

**Interface:** `check_repository(root: Path, manifest: dict) -> dict` returns a
JSON-serializable report with `ok`, `violations`, coverage and debt counts.
`load_manifest(path: Path) -> dict` rejects malformed/ambiguous JSON.
CLI: `python tools/architecture/check_engine_boundaries.py [--root PATH]
[--manifest PATH] [--json]`, exits zero only on a valid passing check.

- [x] Write temporary-repository tests for permitted exports, unknown/duplicate
  owners, missing/unassigned/nested modules, undeclared dependency/private symbol,
  exact/stale exceptions, dependency cycles, relative/absolute/package aliases,
  wildcard/dynamic imports, reference bridges, malformed JSON and symlink escape.
- [x] Run the tests before implementation; record their missing-behavior failure.
- [x] Implement syntax-only scanning and strict manifest validation; preserve
  multiple diagnostics and deterministic output without application imports.
- [x] Create the reviewed ownership catalog from the pinned baseline, with exact
  current-debt entries and reasons linked to OI-005/OI-018.
- [x] Run focused tests and the real-tree gate. Mutate a disposable copy of one
  actual source to prove a forbidden private dependency is caught.

### Task 2: CI and canonical documentation

**Files:** `.github/workflows/synthetic-tests.yml`,
`docs/FIRST_PRINCIPLES_PLAN.md`, `docs/EXECUTION_BACKLOG.csv`,
`docs/project-state/ARCHITECTURE_DECISIONS.md`, and the spec above.

**Consumes:** Task 1 CLI, same manifest and real package scope.

- [x] Add the gate and its tests to the existing synthetic workflow before the
  inherited regression suite; do not replace any existing checks.
- [x] Link the accepted direction from the existing plan/decision register and
  append this bounded acceptance evidence to OI-005/OI-018 without creating a
  competing roadmap or marking broader domain work complete.
- [x] Run focused tests, gate, existing synthetic suite with its pinned PDF
  dependency, and diff validation; distinguish environment failures from regressions.
- [x] Obtain fresh independent review, address material findings and record limits.

Publication sequence: commit and push only the isolated feature branch, open a
draft PR with exact scope/evidence, and inspect applicable hosted checks. Record
publication and hosted acceptance in that PR and the existing Notion/Drive owners
instead of making a new source revision solely to label its own CI result. Preserve
source history and separate plans, implementation and verification.

## Execution ledger

- Baseline: `4b13bc2e802bc785ea36f98d63478e51ee3a66a4`; clean isolated worktree.
- Ruling: build an offline gate before a runtime registry because the current
  composition has shared persistence and cyclic imports, and the supplied
  directive retains separate approval for consequential runtime contract changes.
  Cost: independent execution remains subsequent work rather than implied capability.
- No shared implementation interfaces between the gate and unchanged application;
  CI consumes the gate's documented CLI.
- Task 1 complete: 28 initial missing-implementation failures; 31 final checker
  methods pass after review regressions. Real-tree check covers 44 modules and
  81 retained legacy symbol imports; a new private import fails in a disposable copy.
- Task 2 implementation complete: CI and canonical references updated; inherited
  synthetic suite 772/772 passes with its existing PDF lock. Full-tree static gate,
  synthetic-data boundary audit and diff validation pass.
- Final review: package-attribute/submodule ambiguity and non-package parent
  resolution fixed with reproducing regressions; no outstanding findings.
  Runtime authorization, SQL, transitive bridge dependencies, reflection and
  deployment remain outside the documented static-check scope.
