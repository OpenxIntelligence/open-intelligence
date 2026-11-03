# PDF revision governed-report implementation plan

> **For agentic workers:** Use the executing-plans and test-driven-development workflows for the integrated backend task; independently review the full candidate. Parallel workers have disjoint clinical-note and readable-report files.

**Goal:** Corrected document selections retain exact revision identity through the existing report and review workflow.

**Architecture:** Compose verified #229 into #235 using their #215 source ancestor. Keep CaseStore as the annotation/history/receipt owner and the shared provenance module as the validation owner. Extend existing note references with a revision foreign key rather than duplicating history.

**Tech Stack:** Existing Python/SQLite/vanilla JavaScript; pinned pypdf 6.21.4; no new dependency.

**Spec:** `docs/superpowers/specs/2026-11-02-pdf-revision-governed-report.md`.

## Global constraints

- Independently authored fictional data only; no medical-source acquisition or live model.
- Preserve exact source and revision history, original bytes and permission checks.
- No competing ledger, H1 contract, model service, licensing change or clinical release.
- Local snapshot commit IDs are transport bookkeeping; published parents must be the actual #235/#229 GitHub heads.

## Review focus

- SQLite assertion ID reuse must not retarget a comparison or selected quote after A→B→A.
- Missing, boolean, out-of-range, cross-source and stale revision identities must fail before writes.
- A correction between preview and receipt commit must not create a misleading preparation event.
- Removing/changing a selected line must preserve old note links and report snapshots, including after restart.
- Existing pre-revision databases and authored-source inputs must retain truthful readable history.

### Task 1: Compose source owners and revision validators

Files: existing #229 changed paths, `source_provenance.py`, maintained engineering docs.

- [x] Verify #235's 250 local source blobs and complete Git tree against live GitHub; verify #229 tree.
- [x] Compose from the shared #215 tree, retaining #235's shared validator and offline workflows.
- [x] Run inherited `test_pdf_world_model` before changing shared validation. Observed 48 assertion failures and one missing revision-key error in 9 tests.
- [x] Move revision ID/number and initial review-hash validation from #229's old World Model helper into the shared owner; run inherited revision and PDF suites.

### Task 2: Bind governed comparisons, quotations, reports and receipts

Files: `knowledge_context.py`, `evidence_review_packet.py`, `evidence_review_report.py`, `store.py`, `tests/test_pdf_governed_report.py`, new `tests/test_annotation_governed_report.py`.

Interface: shared `PROVENANCE_FIELDS`; manual comparison/selected-quote inputs add `annotation_revision_id` and `annotation_revision`. Authored inputs remain unchanged.

- [x] Reproduce missing revision fields and stale/reused-ID input acceptance with real CaseStore corrections; assert report/receipt identity and zero writes on refusal.
- [x] Require exact manual revision inputs, propagate complete references, validate integer fields in receipt schema, and render revision plus initial/effective hashes.
- [x] Exercise A→B→A, stale quote with refreshed proposal, cross-source/invalid identities, correction during return, restart and retained earlier receipts. Run focused governed suites.

### Task 3: Bind existing clinical note source links

Files: `clinical_source_provenance.py`, minimal `clinical_continuity.py` consumer, `tests/test_clinical_annotation_provenance.py`.

- [x] Write regressions for changed/removed selections, A→B→A, restart and unbound legacy links; observe failure.
- [x] Add nullable annotation revision reference to existing note link; read captured immutable selection and mark corrected/unbound history for review.
- [x] Verify existing note/source/clinical continuity tests and new regressions.

### Task 4: Render and verify the connected workflow

Files: `patient_report.py`, `web/report.js`, readable-report tests, PDF annotation browser journey, connected CI and existing documentation/backlog.

- [x] Reproduce absent readable-report revision/initial-review attribution; implement strict readable projection and rendering.
- [x] Extend the real PDF correction journey to inspect readable report identity; retain original export/restart/narrow-screen checks.
- [x] Run full Python/HTTP, JavaScript and no-download checks; obtain independent full-diff review. Result: 871 Python tests / 193 JavaScript executions pass; independent focused 32-test review passes with no findings. Local browser executable is absent; hosted acceptance has a separate external receipt.
**Publication and hosted acceptance:** the draft PR receipt records the actual upstream parents, published commit/tree, exact-head runs, artifacts, failures/corrections and final status. It is the authority for subsequent hosted execution; earlier checked boxes report the local work only.

## Execution notes

The initial default-Python baseline failed because pypdf 6.21.4 was not installed in that interpreter. The existing `/tmp/oi-pdf-venv/bin/python` has Python 3.12.14 and the exact approved pin and is used for local PDF verification. This is an environment correction, not a change to parser limits or acceptance tests.

### Material integration decisions and evidence

- Bind manual proposals and quotation selections to explicit revision ID/number because assertion IDs can be reused; authored input shapes are unchanged. A stale manual caller now gets a refresh/reselection error.
- Preserve legacy manual note links as unbound and review-required rather than guessing a past selection. New notes can explicitly cite the current revision.
- Keep the verified #235 shared provenance owner; importing a second validator would let report and World Model identity diverge.
- Reuse the existing 13 browser journeys in hosted CI because no local Chrome executable is available. No browser success is inferred from domain tests.
- Early focused guard invocation used the singular module name and failed to import; the corrected `test_ci_data_boundaries` invocation passed all five tests. This was an invocation error, not a product failure.
- Final independent review made no Critical, Important or Minor finding. Unrelated H1/main behavior, clinical validity, real publisher grants and production/distributed authorization remain outside this synthetic slice.
