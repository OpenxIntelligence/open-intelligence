# Connected workspace entry and source intake

Goal: make the existing Open Intelligence source → question → investigation → report → review → amendment loop usable from an empty database without terminal seeding or a second application.

Architecture: extend PR #158's existing CaseStore, local HTTP routes and browser workspace. Preserve original source bytes, review/report provenance, literature/model egress gates, H1 FastAPI/PostgreSQL + React/Vite target, and all synthetic-only restrictions. This bounded reference-product increment is not that migration, nor the full oncology platform.

Inspected feature baseline: 1bb4ff06a5ab222d3561145e757226f671dbf3ea. Source archive from run 41527551989, merge checkout 56ba6eacbda02b6b4acfd145fea9d8198e9c7d9a; artifact SHA-256 7feb50b0fc6d749b2c92b4a8e9c4eb65dde9d33bc6ef2ace169766ccdb0e9cfd verified. Original parent #123 safety retirement preserved. Current main is not modified.

Design ruling: reuse the existing case-creation/import API, not duplicate patient identity or a new backend. A development case is not authenticated patient registration. The user has asked to build end to end, not restart architecture deliberation. Work on OI-006/007/008/009/010 against the existing UI.

- [ ] Failing tests: creation acknowledgement/validation, exact UTF-8 file bytes, size/format bounds, progress/status projection.
- [ ] Add first-party intake controller, empty-state/new-case form, local structured-text upload and source preview, canonical workflow checklist.
- [ ] Preserve unsaved drafts, case-switch request isolation and parent source/review behavior.
- [ ] Add one-command launcher with empty workspace by default; keep optional existing examples explicit.
- [ ] Real browser: empty database → case → disk file → source/timeline → question → recorded replay → generated report → explicit demo review → amended file → stale report/open question → refreshed report → reload persistence. No network/model calls.
- [ ] Run relevant Python/JS and inherited browser checks, inspect desktop/mobile rendering; record actual failures and limitations.
- [ ] Publish isolated stacked candidate, runnable bundle and documentation. No merge, deployment or PHI authorization.

Rights: only first-party code and authored fictional test text; no runtime dependencies, copied questionnaires, fonts, medical datasets, or model weights added. A user checkbox cannot prove data rights or consent. Standard record format only; no PDF/OCR or clinical extraction claim.


Implementation ruling: leave every existing production file byte-identical. Compose the new entry using a narrow Handler subclass and a static trusted first-party partial, plus a thin browser adapter. This avoids rewriting the source-owner's large app initializer and preserves the existing API, store and review ownership. Missing original template anchors fail explicitly. Development starts via `run_open_intelligence.py`; original entry points remain available.

Observed failures: new module absence produced the expected initial Node failure. A subsequent CRLF fixture caused import rejection because the canonical parser explicitly requires LF; the intake now rejects CRLF rather than altering original bytes. That check failed before the guard and passed after it. HTTP fixtures now use the documented LF contract. The local Chromium instance refuses loopback navigation by organization policy; no policy bypass was attempted and no local browser pass is claimed. Hosted CI is the browser verification gate.
