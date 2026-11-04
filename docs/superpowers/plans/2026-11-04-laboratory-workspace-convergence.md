# Laboratory workspace convergence implementation plan

**Goal:** combine the existing laboratory/manual-task migration owner #471 with the laboratory workspace and keyboard reading owner #473, without rewriting either runtime.
**Architecture:** reuse #471 canonical backend and #473 UI (including #472); only backlog notes overlap. Source originals, patient/case identity, permissions, question/report/task owners and all published migrations stay with their current owners.
**Spec:** existing issue #428 and `docs/engineering/H1_LAB_MANUAL_CONVERGENCE.md`; donor `docs/engineering/H1_LABORATORY_WORKSPACE.md` and `docs/ux/2026-11-04-laboratory-reading-continuity.md`.
**Tech stack:** existing Python/FastAPI/PostgreSQL and React/TypeScript/Vite; no new dependency.

## Frozen inputs
- #469 common source: 8ff6e9e5a0389a1142ca479a6705c599cbda88e7
- #471 backend/convergence: 95bf73d23172c15bcf326183494030e6597ed449
- #473 workspace/reading: 9ea4560fc03be567e8383f9b145fc8eaef0cd140 (includes #472 at 2ccdfad6aeba3cb3378c4648f4dba3df604cc554)

## Constraints and rulings
- Independently fictional data only; no merge, deployment, clinical validation, real patient access or vendor adoption.
- Preserve #471's complete migration graph and seven recovery stages, and #473's keyboard and explicit-import behavior.
- Do not import #475 or claim exact observation-to-question binding; those remain separate.
- Downloaded source ZIPs do not encode executable modes. Reconstructed complete Git trees using mode 100644 match both published root tree hashes, verifying the complete path/blob/mode sets; this is not a reconstruction of their commit histories.
- Local environment lacks PostgreSQL/Docker and some pinned dependencies. Run available checks, attempt full suites, record limitations, and require new exact-head hosted acceptance.

## Tasks
- [x] Write a combined client regression using real RegistrySession and a fictional HTTP transport: lab import, explicit manual task provenance, stale completion refusal, task denial and late-response clearing. Run against both parents; retain expected failures.
- [x] Compose only the 19 nonoverlapping donor paths from #473, merging the existing backlog rows by field and preserving both histories. Runtime and tests are reused byte-for-byte.
- [x] Run combined client checks, parser/contract checks, syntax and source ownership verification; attempt complete frontend/API suites and retain dependency failures. Full reference execution and exact-head hosted gates remain separate receipts.
- [ ] Publish an isolated integration draft with both source parents, exact content manifest, new CI links and current limitations. Never substitute either parent's green checks for this tree.
- [ ] Update existing tracking and canonical documentation with the actual checkpoint.

## Additional verification ruling

The inherited API workflow does not trigger for frontend-only changes. Add only the new integration test path to its existing pull-request filter, after reproducing the absent trigger; all jobs, permissions, existing paths and seven recovery gates remain unchanged. This ensures the composed candidate requests fresh backend acceptance without an unavailable manual-dispatch tool.

## Review focus
- Laboratory writes do not create or silently attach a task/question or imply clinical review.
- Source-only tasks remain independent from explicitly bound manual revisions.
- Manual reassessment prevents completion after a fresh task read, even following a laboratory import.
- Denial and disconnect clear protected task projections; a late task reply cannot restore them.
- Both published 0016 histories and 0017 convergence remain unchanged; populated upgrade/recovery still require hosted execution.
