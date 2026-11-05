# H1 document/image + accepted main convergence — 2026-11-04

**Status:** isolated implementation candidate, before combined exact-head acceptance; **draft, unmerged, undeployed**.

## Patient outcome and canonical owners

Bring accepted patient-record, clinical timeline, visit, investigations, case-search, goals, source-provenance and patient-attention behavior on the legacy first-party reference app **alongside** the H1 FastAPI 16/PostgreSQL/React patient workspace, reviewed text/PDF originals, independently authorized image custody, source-linked questions, governed evidence and reports, review and follow-through. Preserve both systems' existing owners and migration histories while verifying the H1 system is suitable for a future controlled transition. **This is not permission to run two competing clinical production ledgers.** The legacy app remains a reference/acceptance oracle; H1 owns the emerging production-intended implementation boundary.

## Pinned source composition

- Accepted main: `31509a6b83949f974e25b6913a6e30fc968be939`, source tree `04f93f8b49a8b9934c37a13204befcb32f746746`.
- Verified H1 document/image core #381: `e52898fa5661334ef5c149f6f3f73da0ac1955df`, tree `e9b18cf2e0dc103cfa859971b8f8276869ae302a`.
- Verified child #394: `924008266d741b2494df41112e2da446b526f920`, tree `05c5cf0df7a4073c1b1ac69cdecfe6cb64d33f26`. Its only two additions tighten original restored-selection JSON primitive types and immutable anchor digest verification in the existing source recovery oracle. Original H1 #381 remains an ancestor, not a replaced architecture.
- Common Git merge base of accepted main and #381: `c4798ae85004713593f83458abd2102be6729095`, tree `19293862e9b6b131794ba788bac31a8e39cf0b0b`.

**Entire recursive Git tree reconciliation, not PR-file-list heuristics:** 386 file paths changed exclusively on the H1 donor, 115 exclusively on main, 120 identical between main and donor, and only **two actual competing file paths**. Preserve every one-sided change by its original Git blob and mode, with no default branch's code silently replaced by stale donor text.

## Conflict 1: legacy document intake

`src/open_intelligence/document_intake.py` was independently added on both branches. The accepted main version implements explicit UTF-8 text/manual line selection (162 lines). H1 implements that contract and adds PDF extraction/review, source-bound correction and immutable provenance (320 lines). A line-by-line comparison found 153 verbatim common lines and nine structurally changed/removed original lines, including support for .pdf in the filename validator, delegation of original text to a shared review helper, and media-aware receipt fields. The H1 file is selected as the **expanded existing owner**, not copied into a new owner.

The bounded `tests/test_h1_main_document_intake_merge.py` checks accepted plain-text preview parity and byte identity, UTF-8/CRLF line anchors, original unreviewed classification, PDF/non-text exclusion from text-only paths, saved-rendition boundary and filename traversal denial. Existing main intake tests and all H1 reviewed-document/API/built-browser/restore tests must pass again at the exact combined tree; merely reviewing textual overlap is not proof of runtime compatibility.

## Conflict 2: canonical backlog CSV

`docs/EXECUTION_BACKLOG.csv` has one unchanged eight-column schema. The accepted main has 19 content rows and the H1 donor has 21 content rows, adding `GH-112` and `GH-323`. Preserve all unique IDs and the original column types, keep the richer H1 integration evidence in those cells, and append the **distinct accepted-main history** for conflicting acceptance-evidence cells in OI-006, OI-007, OI-009, and OI-010. Do not silently discard the main's text intake, source-amendment, manual transcription or browser evidence. The merged CSV must roundtrip under RFC-style CSV parsing with all eight cells per row and no duplicate IDs. Some H1 row histories are old and explicitly **not** current-head acceptance claims; new results belong to the actual candidate's hosted PR receipts.

## Data ownership, consent and recovery boundaries

- **H1**: preserve both 0012 histories joined by the existing no-DDL `0013_document_image_convergence`; do not edit already published Alembic migrations or expand clinical claims.
- Preserve patient/case/source/actor current authority at preparation, audit-tail and commit boundaries; independent grants for read/original/export/citation/task; deny wrong-patient, cross-case, altered/revoked or late-reader data.
- Keep literal source bytes/version/hash, PDF extraction/page/line/revision, source-authored assertions separate from human annotations and clinical approval; no OCR/diagnosis is inferred from a file.
- Preserve source corrections, selection revisions, report freeze and dependent stale/reassessment states, lost-response exact retry and database restart/dump/restore evidence.
- No live provider EHR/PACS, external research dataset, real patient files, unrestricted model/cloud execution, unlicensed content, professional treatment recommendation or downstream clinical action.

## Exact-tree acceptance gate before integration decision

This candidate **must not be merged or deployed** until it has independent source review and:
1. A complete new **H1 API/PostgreSQL16** workflow on the actual composed commit: all tests, migration heads/0013, six restart and backup/restore/revocation probes, strict restored JSON/digest checks, no relevant skips or failed fixtures.
2. A complete new **H1 React/Vite/rights/Chromium** workflow on that same source tree: client tests, production build, 13 dependency-rights controls, independent auth, records, originals, evidence, report, amendment, review and follow-through browser journeys.
3. The full **accepted-main** synthetic Python/HTTP, source-reader, Chromium, consent/safety, research and accessibility checks, including the four new text/PDF coexistence regressions.
4. Full reference Python tests, dependency manifests/third-party rights and synthetic-data access controls; separate parent green runs **are not** candidate acceptance.
5. Published exact SHA/tree, tested merge SHA (if GitHub generated one), run/job logs and independently checked artifacts, with contradictory failure history and uncertain limitations recorded.

## Explicit exclusions and next owner integrations

Parallel #398 manual passage → saved question/report link, #392 restoration controls, #402 second-opinion/task drafts, #403 current-main named-person data acquisition retirement and the clinical/H1 application migration are **not silently adopted or treated as qualified** by this composition. Reconcile their exact current-source owners as later bounded slices, and do not merge the older standalone implementations over a verified common owner.

**Decision:** do the real full-stack merge and tests first; product adoption/release remains held until clinical, security, legal, user and independent reviewer authority is established.
