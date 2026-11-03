# H1 converged evidence — merge-readiness gate

**Date:** 3 November 2026 · **Status:** staged review; no merge, release or production authorization. **Scope:** one existing H1 React application, canonical FastAPI/PostgreSQL patient/source/question/evidence services, and synthetic-only engineering proof.

## Decision value

The original redesign (#183) is an independently runnable synthetic reference. The React entry (#181) has already propagated through H1 source owners. Do not create a second patient/application model, transplant the original DOM controller, or merge those two original drafts together. The relevant H1 integration chain now covers original records → World Model → source-bound question → evidence metadata citation / independently authored evidence → preserved report / verification return → follow-through.

Current evidence supports **controlled staged review**, not unqualified release: separately verified parent commits and distinct PR merge dependencies still require explicit reconciliation, independent source/security review, and exact combined-head acceptance.

## Source and ownership ledger

| Source / head verified in current review | What it owns | Proposed disposition |
| --- | --- | --- |
| #298 `89f98824610e23a26d2904a845ed1d930207bd76` | Canonical saved questions, metadata-only citation link, follow-through and exact retry receipts | Preserve as parent owner in #307; citation metadata does **not** grant passage access or clinical evidence appraisal |
| #300 `818c67fcb742941fe1588c4ee130ce07e15a814d` | Separately authored fictional originals, literal comparison, versioned human report and content-specific rights | Composed into #307, not an additional patient or citation database |
| #307 `477f24826a8a102c7437c993d69877c1f250b951` | DDL-free migration merge, both evidence owners and same-question React workflow | **Green** API 414 tests, legacy 287 tests, seven restored/durable checks, real Chrome; React and UI checks green at this exact head |
| #310 `c5dc8ab90398d7a509c88ca8c3d926a0788e5419` | Records → exact source quotation → fresh World Model check → editable in-memory question | Original method + eight tests selectively reused in #314 without copying its older entry application |
| #314 `4bbd74c364983152c158a03a8efd8273ee323f10` | Source-to-question handoff composed on #307 | **Green** 274 client tests, typed build/rights, real React/FastAPI/PG16/Chrome; no API/schema/domain changes |
| #311 `8f7ad6a80dcb5312bc63480339d9142376883a4a` | Strict output timestamp validation for immutable evidence link history | Two original tests and exact source module imported into this child; no coercion of stored timestamp or new authority |
| This draft (#315) | Combine strict citation timestamp validation with already connected patient evidence workflow | Require exact-head **API and React** CI before readiness; keep draft and unmerged |

Do not substitute a green donor, a parent mergeability badge, or a passing artifact from another SHA for combined-head verification.

## Staged acceptance and retirement decisions

1. **Foundational identity and authorization:** Preserve original patient registry, case binding, actor/org/purpose and per-action grants. No second patient store, role-preview-as-auth, or implicit read rights from creation. Require current denial, expiry, cross-org/cross-case, revoke/reconnect and late-request regressions.
2. **Source fidelity and scientific separation:** Preserve original bytes, version/hash, specimen and line references, reported/missing/negative/conflicting distinction. A current source only opens a *draft* after a new authorized World Model read. Citation link ≠ authored passage ≠ assessed comparison ≠ clinical conclusion.
3. **Prepared disclosure boundaries:** Refresh/dismiss cached quote, source brief, citation metadata and authored evidence on navigation and rights loss. Immutable historical report bytes persist but can be withheld under current rights. Abandoned, uncertain and recovered writes must preserve exact original request keys and audit receipts.
4. **Database migrations:** Keep both published branches of 0009/0010 unmodified; verify single DDL-free `0011_evidence_convergence` Alembic head, upgrades from both populated histories, restart and pg_dump/restore. No naive migration stamping or destructive rewrite.
5. **Client navigation:** Use one canonical `RegistrySession` and one patient context across Overview, Records, Journey, Investigations, Review. Keep prior #183 behaviors that have corresponding backend contracts; retire duplicate DOM/SQLite adapters *only after* mirrored acceptance, not because the React screen looks similar.
6. **Source owner PR disposition:** #309/#310/#311 are targeted reviewed source candidates. Their confirmed behaviors should be included only once in the correct integrated stack, with credit and source links; do not merge all branches independently into main. #181/#183 remain separate reference/ownership reviews. #298/#300/#307 and current children require explicit parent-first merge or a reviewed integration strategy.
7. **Release boundary:** All checks use independently authored fictional materials. No real-person data, automatic biomedical or trial eligibility assessment, scientific model execution, professional identity/consent, clinical signoff, full modality parity, cross-browser/WCAG certification or deployed real-patient service. Product, clinical safety, privacy/security and licensing approvals remain separate gates.

## Exact-head verification receipts

- #307: [API/PG16 full workflow 41658525044](https://github.com/OpenxIntelligence/open-intelligence/actions/runs/41658525044) — completed success: 414 Python/API/PostgreSQL tests, 287 reference tests, existing real-browser journeys, patient/source/review/follow-through/evidence recovery against actual PostgreSQL and HTTP plus restart, restored grant checks and backup/restore. [React run 41658525265](https://github.com/OpenxIntelligence/open-intelligence/actions/runs/41658525265) and [UI run 41658525058](https://github.com/OpenxIntelligence/open-intelligence/actions/runs/41658525058) completed successfully.
- #314: [React/PG16/Chromium run 41659720068](https://github.com/OpenxIntelligence/open-intelligence/actions/runs/41659720068) completed success: 274/274 typed-client tests, Vite build, original source handoff and inherited citation/authored evidence/report/review/follow-through flows. Parent API check is **not** an exact #314 API head check; its backend tree is unchanged.
- #315: Tests-first SHA `b0f9c6f845d1a324f6569b152b4db5c745bd8d4f`, strict source copy SHA `6b6197bad8a4af7c03a9d0987fe314e5610c1622`. Track the exact final documentation head and independently record outcomes from both hosted API and React runs; test-first run may fail by design and must be retained.
- Red and recovered test history is evidence, not a reason to downgrade assertions. A non-successful hosted result remains a blocker until the same exact source head passes with the intended checks.

**Merge readiness:** HOLD pending #315 exact-head verification, external source/security review, and explicit parent-chain decision. Never auto-merge or deploy based on this document.
