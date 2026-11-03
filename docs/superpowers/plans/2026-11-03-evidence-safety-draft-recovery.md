# Connected evidence safety and draft recovery Implementation Plan

> For agentic workers: use superpowers:executing-plans for this bounded integration.

**Goal:** Preserve recoverable comparison drafts together with chronology validation and installed-dependency checks in the connected H1 workspace.

**Architecture:** Extend existing RegistrySession/QuestionEvidenceSession and React panel by exact donor reuse. Retain both source ancestries remotely; this isolated local repository begins from a verified source-tree checkpoint.

**Tech Stack:** Existing React/Vite/TypeScript and FastAPI/PostgreSQL 16.

**Spec:** `docs/superpowers/specs/2026-11-03-evidence-safety-draft-recovery.md`.

## Global constraints

- Independently authored synthetic inputs only; no new dependency or canonical owner.
- Preserve backend, migrations, grants, locks, notices and workflows byte-for-byte.
- Keep source amendment, rights denial, uncertain writes and historical report semantics intact.
- Draft PR only; no merge, deployment or external-service activation.

## Review focus

- Invalid evidence chronology must clear exposed draft fields even with a recomputed digest.
- Malformed reads must not erase an uncertain write's exact recovery identity.
- Valid recovery receipt must not reactivate a packet with invalid chronology.
- Independent metadata/task denial must preserve separately authorized comparison input.
- Shared patient/source denial and late responses must not resurrect cleared input.

## Task 1: Compose existing behavior and verify the connected workspace

**Files:** reuse #359's three production files in `apps/web/src` (authored-evidence-panel.tsx, authored-evidence-session.ts, registry-client.ts), four tests and `tools/authored_evidence_journey.py`; retain its historical design/plan records; add `tests/evidence-safety-draft-recovery.test.mjs`; append the existing evidence ledger and OI-008/009/010/013 acceptance fields.

**Interfaces:** existing comparison selection/edit/save/discard delegates; exact frozen EvidenceWriteIntent and current evidence packet decoders. No public API additions.

- [x] Verify all 409 base blobs/modes and baseline `npm test` (310 tests).
- [x] Apply donor tests and two composition tests first; compile and run to demonstrate missing behavior.
- [x] Reuse exact #359 production/browser files; verify no overwrite of #355 chronology/gate changes.
- [x] Run `npm test`, `npm run rights`, `npm run build`; syntax-check the browser helper and inspect protected-path diff.
- [ ] Review the complete delta independently; fix material findings with regression evidence.
- [ ] Publish a new draft integration PR with exact #355/#359 parents and record actual hosted results against its head.

## Execution record

Base recovered from GitHub artifact 13251782006; SHA-256 `72a11726d6ce336de6b8c55812108fed1a96c11203f4d9405be5b50e01677b3d`; all 409 source blobs/modes match tree `6ebb1ad511cad9da256564a04ae4fa8a637b4324`. Local commit identity differs from remote because it is a reconstructed checkpoint; no inherited hosted result is attributed to the composition. Exact locked dependencies were installed from the existing offline npm cache, without lifecycle scripts.

Local execution: 310 baseline client tests passed. Tests-first composition produced 50 failures / 322 passes, with absent draft APIs and incorrect receipt acceptance; no skips. Exact donor reuse passes all 372 client tests and all 13 filesystem regression tests, zero failures/skips. Installed-tree gate inspects 18 packages and explicitly leaves two optional packages uninspected, with zero errors and no whole-product clearance. TypeScript/Vite build and Python helper compilation passed. Temporarily bypassing calendar-day validation makes both new composition tests fail; restoring the unchanged validator makes both pass. Eight donor application/test/browser files retain exact Git blob IDs. Backend, migrations, locks, workflows, chronology and rights-gate files are unchanged. Hosted combined browser acceptance is pending publication.
