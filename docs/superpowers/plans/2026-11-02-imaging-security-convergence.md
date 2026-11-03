# Imaging security convergence implementation plan

**Goal:** Reconcile source-bound imaging reads (#207), the existing release gate
(#201), and the existing no-personal-data safety owner (#137), then measure the
remaining direct-backend access boundary against the exact pinned PACSNode.

**Architecture:** Preserve the existing CaseStore and H1 patient/source/permission
owners. The existing PACSNode evaluator remains an isolated research tool. A new
security wrapper records direct anonymous access after an OI report amendment and
kernel-visible confinement of the evaluation. The existing classifier consumes
those observations and the exact source-bound read receipts; it never approves
deployment. No parallel patient, consent, source, or imaging custody ledger.

**Tech stack:** Existing Python standard library; isolated existing pydicom 3.0.2
pin for fictional image generation; unchanged PACSNode upstream commit
`e9b4334477a66967d290add9e0b9afa068f59dc0`; Linux network namespace in hosted CI.

**Spec:** User's 2 November master directive (especially parts XI, XIII, XV-XVI)
and `docs/engineering/PACSNODE_SOURCE_BOUND_READ_GATE_2026-11-02.md`.

## Constraints and decisions

- Base #207 at `5d157f5c0cf3a57bbb021b30429b6e741b509db7`; reuse #201 at
  `7c0edb8ab3c3d0afe67cfd56a43efc911de4108b` and safety owner #137 at
  `533afd3ca6dd0c011e2e47397d3d5cae04e62512` by inspected source, not wholesale merge.
- Only independently authored fictional inputs; no old personal-case fetchers.
- Preserve original SOP/pixel diagnostics, negative evidence, and HOLD decisions.
- Upstream hard-codes HTTP and DIMSE wildcard listeners. Configure fresh isolated
  storage and an isolated network namespace with loopback only. Do not invent a
  bind-host option or label namespace confinement as authenticated service access.
- Existing H1 #187/#214 owns source custody/read authorization; #213 owns the PG
  World Model projection. Integrating these remains the next product seam.
- A failed evaluation is retained as a bounded failure receipt, never silent success.
- Work stays on this isolated integration branch; no merge or production deployment.

## Alternatives considered

1. Implement a separate imaging identity/custody layer on the old SQLite branch:
   rejected because it would compete with the active canonical H1 owners.
2. Stop at a written security checklist: insufficient; the remaining backend
   access boundary and current safety regression can be measured and repaired now.
3. Reconcile existing owners and add executable confinement/bypass evidence:
   selected as a reversible integration increment within the authorized mandate.

## Review focus

Unscoped real-data fetch; wildcard listeners mistaken for loopback binding;
anonymous response content leaking into logs; forged success booleans overriding
per-object evidence; a report amendment mistaken for upstream object revocation.

## Tasks and verification

- [x] Reproduce blocked-entrypoint gaps with network traps, then reuse #137's
  coherent synthetic-only parser/workflow layer. Preserve historical cleanup gaps.
- [x] Reuse the exact four #201 files and run its nine existing tests.
- [x] Add failing tests for direct anonymous WADO observation, access-denied and
  malformed responses, no data in receipts, and strict namespace evidence.
- [x] Implement the wrapper and confined runner; keep #207's evaluator and its
  mutation tests intact. Observe both HTTP and DIMSE listener scope.
- [x] Add failing gate tests for missing/mismatched source-bound receipts and
  contradictory direct-access evidence; extend the existing gate minimally.
- [x] Run safe offline application/research tests and the isolated pydicom suite.
- [ ] Independently review the patch; publish an isolated draft with exact-head
  hosted full-suite and real-PACS evidence, and update canonical roadmap records.

## Execution evidence

- Baseline #207 imaging metadata tests and six source-bound WADO tests passed.
- Baseline imported #201 classifier: nine tests passed before extension.
- Audit found retained RNA acquisition in both pinned main `24519839` and #207;
  this is pre-existing and must be reconciled, not described as an imaging regression.

- Final local application run: 316 tests, 315 passed, one process-namespace visibility skip.
- Guarded research run: 204 tests, 191 passed, 13 HDF5 skips; zero outer network attempts.
- Isolated pinned pydicom integration: 8 passed; JavaScript source dialogs: 16 passed.
- Independent review found five issues; all reproduced/corrected and re-reviewed.
- Hosted exact-head real-PACS and browser verification remain pending at this commit.
