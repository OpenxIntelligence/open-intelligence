# H1 React original record intake and inspection

Goal: extend the source-owned Records screen with explicit original-file import and separately authorized original-text inspection over existing PostgreSQL APIs.
Spec: existing #119, canonical source #187/#193; UI #181 and active integration/h1-react-source-records-20261102. No architecture replacement, second patient/source store, API or schema change.

Baseline read-only Records head 9582c23523f5aca3d9abc79124d86646d0ead9b1; own compatibility head 26eca3f94883bff815ae6dd0ab38b848cc6ae551; downloaded artifact 13194218278 SHA-256 4c16124fd7cc1b10bb44f506bc6ecf319344badc80e4ebd58d73026511e3b033 verified. Original owner work not overwritten. An initial alternative composition was left unattached after discovering this active Records owner; not another competing implementation.

## Design and boundaries
One authored fictional UTF-8/LF .txt (1–65536 bytes) with original source marker, no BOM/NUL. Local literal preview precedes explicit submit. API JSON envelope <=72000 bytes per existing server. No source normalization or case rewriting. Server's immutable version/duplicate/quarantine receipt is the authority. Lost/malformed/5xx response is unknown, no retry or rollback claim. Original reads require source_original_read separately from source_read; verify original bytes/hash/case/document/version against the selected metadata. All statements remain unreviewed, not clinical meaning.

## Tasks and proof
- [x] New test module fails before helper/client implementation (missing module).
- [x] 16 client behavior tests pass after implementation; two extra tests reproduce encoded surrogate normalization and excessive JSON envelope, then pass after rejection guards.
- [x] 35 total local client tests pass (17 original and 18 new), available TS 5.8.3; no full TSX/local PostgreSQL/browser pass implied.
- [x] Add focused React file component to existing Records, no new dependency; clear preview on context/unmount, preserve scoped client generation handling.
- [x] Extend actual hosted browser journey: zero automatic upload, disk-file import, exact hash/original, duplicate, amendment/history, wrong-case quarantine, independent original-read denial, metadata revocation and mobile containment.
- [ ] Execute pinned TSX/dependency gates and actual PG/HTTP/browser on exact pushed head; inspect evidence/screenshots.
- [ ] Publish child draft and update existing docs with observed results. Independent owner/security/clinical review before merge.

Remaining: no general PDF/OCR (separate prototype #189), real identities, consent, caregiver authority, clinical validation, source-to-research invalidation, model execution, commercial-distribution clearance or deployment. Existing source backend and dependency locks unchanged; source permissions may change after a completed read. Generated credentials stay temporary and artifacts never contain them.
