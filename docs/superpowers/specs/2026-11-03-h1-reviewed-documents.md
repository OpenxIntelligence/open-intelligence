# H1 reviewed document custody and passage history

Extend OI-006/007/010/013 on #315 (58bc5f7), retaining #307 and #304.
Port the source-owned preview/review validators and constrained PDF worker from
#249 af72cd6. Use the same clinical_source.source_versions original ledger,
patient registry, case binding and source grants. Add immutable source-owned
intake/rendition and annotation-revision children. No competing patient/source
store, no replacement architecture and no model execution.

Users explicitly preview an independently fictional .txt or supported PDF,
confirm case/metadata and exact selected passages, save original bytes, inspect
saved extraction, download an authorized original and append corrected selections
with an expected revision and reason. Preserve old originals, renditions and
selection history; reject stale corrections and altered duplicate intent.
PDF limits remain 64 KiB/20 pages/512 lines, no OCR; reuse exact pypdf 6.21.4
and its existing rights record/hash. Parser runs outside database transactions.

Manual selections are not source-authored assertions or clinical interpretations.
Existing structured-report source snapshots remain unchanged. The first port
exposes reviewed documents through Records and a source-owned document API;
manual selection propagation into World Model/question/report snapshots is the
next dependent stage, requiring its own provenance-bearing contract. Do not
silently inject user classifications into source_reported_assertions.

All responses including original binary bytes prepare under the patient/binding
locks, then refresh same-bearer identity and independent source permissions before
audit/commit. Preview authorizes before parsing and again before disclosure,
but persists no source or event. No production identity, clinical approval,
merge or deployment. Only independently authored fictional fixtures.

Choice: source-owned child records preserve originals and immutable revisions;
rewriting ordinary files as synthetic reports would lose their original identity.
A second document store would violate canonical ownership. The implementation
uses the existing FastAPI/PostgreSQL16 and React/Vite stack.
