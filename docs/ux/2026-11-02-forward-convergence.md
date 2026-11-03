# Open Intelligence — UX convergence and next implementation gates

**Decision record:** 2 November 2026 (local project date; repository UTC activity may show 3 November)  
**Reconciled:** 3 November 2026 (America/New_York), using live PR metadata, source files and hosted workflow records. This update supersedes the earlier capability-status statements; the adopted architecture and ownership boundaries are unchanged.  
**Scope:** design and implementation planning only. No backend, database, API, authentication, authorization, or business-logic change is authorized by this document.

## Decision

Keep **PR #183** as the tested, frontend-only information-architecture and interaction improvement to the **connected synthetic reference workspace** in PR #166. Do **not** misrepresent it as an authenticated, real-patient product or the future React application.

**PR #181** is the historical React/Vite/TypeScript patient-entry foundation on the separately owned FastAPI/PostgreSQL H1 path. Later H1 candidates now connect source reading, questions, verification returns, authored evidence, preserved reports and follow-through. Do not describe the whole H1 path as patient-entry-only, or rebuild those existing owners. Carry forward validated **experience contracts and patterns** from #183 while retaining H1's existing canonical session and server contracts.

Open Intelligence is an oncology-intelligence platform, not merely a replacement EHR. The overall UX must ultimately integrate patient records, longitudinal understanding, investigations, evidence, clinical collaboration, and appropriately authorized care coordination. This is a future product direction; it is not a claim those services already exist.

## Observed branch state and supported claims

This is a bounded UX ownership snapshot, not an exhaustive repository inventory or a declaration that one combined H1 release exists. Every candidate below was open, draft and unmerged when inspected. PR descriptions describe implementation scope; hosted records establish the named run outcome, not clinical validation or aggregate acceptance across branches.

| Candidate and exact inspected head | Existing contribution | Boundary / evidence checked in this reconciliation |
|---|---|---|
| [#166](https://github.com/OpenxIntelligence/open-intelligence/pull/166), `334d863b2206b290c02cd2606dcb93c93afe3a68` | Connected synthetic reference workspace; parent of #183 | Existing local source → question → investigation → demo-review journey; no authenticated professional or patient accounts |
| [#183](https://github.com/OpenxIntelligence/open-intelligence/pull/183), `94af20d811eee9fb0ea9aab7852e57928f12caf3` | Patient presentation, worklist, dedicated chart, worklist currentness **and first-start recovery** | [Run 41575641766](https://github.com/OpenxIntelligence/open-intelligence/actions/runs/41575641766) completed successfully; job steps and logs inspected. The first-start gap from the preceding handoff is closed in this candidate |
| [#181](https://github.com/OpenxIntelligence/open-intelligence/pull/181), `c8be412e66bca14c884298b01ae6238f59857376` | Historical H1 patient-entry foundation | Its limited initial scope does not describe newer H1 descendants |
| [#326](https://github.com/OpenxIntelligence/open-intelligence/pull/326), `25ac0c545035aa47c4946733695511d16af9151f` | Source-reading/evidence candidate on #319; strict citation history, status-bearing report downloads, browser-startup diagnostics | Hosted API, React and inherited UI runs all report success at this head: [41668981828](https://github.com/OpenxIntelligence/open-intelligence/actions/runs/41668981828), [41668981976](https://github.com/OpenxIntelligence/open-intelligence/actions/runs/41668981976), [41668981853](https://github.com/OpenxIntelligence/open-intelligence/actions/runs/41668981853). Not a union of #328/#329/#330 |
| [#328](https://github.com/OpenxIntelligence/open-intelligence/pull/328), `5a188d4e18e4d80bc2ba1d662c966abc3096301f` | Follow-up attention and retained transition drafts on #322 | React [run 41666427184](https://github.com/OpenxIntelligence/open-intelligence/actions/runs/41666427184) reports success. This is not a child of #326 |
| [#329](https://github.com/OpenxIntelligence/open-intelligence/pull/329), `6cdea5713ba11fcdfa2ccb4c68a29fc89bb14c19` | Source-adjacent reading, source-to-question handoff and session-boundary checks on #315 | React [run 41669272613](https://github.com/OpenxIntelligence/open-intelligence/actions/runs/41669272613) reports success. Its actual main and SourceReading components were inspected; they reuse the existing RegistrySession |
| [#330](https://github.com/OpenxIntelligence/open-intelligence/pull/330), `312ad9379311901f8a69a7c20d4ea09f98027481` | Calendar/date validation in evidence clients on #322 | Changed-file inventory and parent checked; its hosted outcomes were not independently checked in this reconciliation |
| [#331](https://github.com/OpenxIntelligence/open-intelligence/pull/331), `55ea8f96868125ee802d840e779a76f1b8c8e3b3`, and [#332](https://github.com/OpenxIntelligence/open-intelligence/pull/332), `f7136bbc5ef7c7224bf5ed7172c82ddab83dc49d` | Separate archive/image/question/task/citation integration candidates on #313 | Parent/head metadata checked only; no source equivalence, combined acceptance or merge preference is established here. Preserve their owners and keep backend work outside #183 |

### Verified overlap that changes the implementation order

[#322](https://github.com/OpenxIntelligence/open-intelligence/pull/322) at `19b75317701ae01fc93844077ac94c351fd982bd` and #326 carry the same six citation/report source and test blobs. Both exact revisions were fetched through GitHub; their returned blob identities match:

| Path | Identical Git blob SHA in #322 and #326 |
|---|---|
| `apps/api/src/oi_api/evidence_contracts.py` | `30f215155508914f7b1c0de83e7632c03baf4c98` |
| `apps/api/tests/test_question_evidence_contracts.py` | `8a0506bb4da62ac1bab390a92cdfc7ec77d194fe` |
| `apps/web/src/authored-evidence.ts` | `b0b03d22fc45cd0ad068a4d4014ab0e29d7b53b3` |
| `apps/web/tests/evidence-report-download.test.mjs` | `85b7e894524d5e088bfa5f4a871ab6ec7e9814b3` |
| `apps/web/tools/authored_evidence_journey.py` | `6fe7d22b278d32938c84f5f16d2606690d52b922` |
| `apps/web/tools/evidence_continuity_journey.py` | `a0db93b5b9a7755fad18713678d50cdc42a600a9` |

This proves equality of these six files, not equivalence of the whole branches. #322 starts from #318; #326 starts from #319 and also contains startup diagnostics. Preserve the newer import disclosure/file-preview behavior when selecting a composition. #328 and #330 are sibling children of #322; their distinct features are not automatically present together. #330 changes `authored-evidence.ts` and the report-download test already represented above, so blindly restoring the donor versions could erase its date validation.

The next H1 integration must choose one explicit parent, retain the existing owners, reconcile the selected deltas, and test that exact combined tree. No merge order is approved by this documentation update.

### Evidence limits

The #183 hosted logs directly show 347 Python/HTTP tests, 792 navigation/form assertions, 387 worklist assertions and 295 startup assertions passing. Every named job step completed successfully. The existing source report records the more detailed scenario counts and preserved earlier failures. This reconciliation inspected the live hosted records and logs; it did not rerun the application, download/re-hash hosted artifacts, conduct a fresh visual audit, or perform clinical/usability validation. The H1 outcomes above were read from commit-associated workflow records; no assertion is made that every workflow or every retry succeeded.

## Architecture: three navigation levels, not a giant sidebar

1. **Global product context:** patient portal or authorized professional workspace, with only server-authorized resources. Personal workspace / patient roster / appropriately public research area; never use a local role toggle as a permission boundary.
2. **Selected patient chart:** stable patient identity, source-aware summary and clearly scoped sections. The header is persistent, but contains only actually available data, provenance and relevant actions.
3. **Within-chart task context:** record detail; source/version reader; current question; investigation/review; evidence and options. Sub-navigation follows a real task, not a permanent third-level menu.

For future oncology functionality, group by *user outcomes* rather than by independent engines. Patient: Understand my situation, My records, Questions & updates, Care coordination (only when genuinely implemented). Professional: Worklist, Patient chart, Investigations and review. Research: shared evidence tools only where allowed. Do not introduce empty “Appointments,” “Medications,” “Messages,” or “AI Diagnosis” destinations merely because competitors have them.

## Portability contract: #183 → the existing H1 React workflow

| UX contract proven or proposed in #183 | React integration requirement | Gate |
|---|---|---|
| Separate patient home and professional worklist | Introduce only after backend identity, scopes, and authorization support these experiences | Server-scoped role and ownership tests |
| Selected chart and contained chart navigation | Bind to H1's canonical patient reference, not synthetic CASE-* identity; use the one existing data owner | Cross-tenant/cross-patient denial and reload tests |
| Exact original-source citation reader | Reuse H1's existing SourceReading and canonical source owner; reconcile the selected branch's filters, original-byte access and source-to-question callback | Provenance, correction, separately authorized original access and revoked-session clearing on the combined tree |
| Questions, verification returns, authored evidence and reports | Preserve the already connected H1 contracts and immutable history; model-assisted research remains a separate capability and is not implied by authored reports | Source → question → verification → evidence/report → amendment → explicit replacement/review, with independent permissions |
| Same-case draft preservation and cross-case veto | Preserve editing intent across route changes; fail closed when changing authorized identity | Unsaved-input and delayed-response race tests |
| Responsive navigation, focus, mobile containment | Transfer tokens, semantics, interaction behavior; not brittle DOM selectors from vanilla JS | 320/390/768/1024/1440 widths, keyboard and screen-reader QA |
| Patient-safe language, unknown/negative/pending distinctions | Reflect source assertions without generating diagnosis or clinical certainty | Fixture-backed assertion-to-source validation |

Do not transfer the local preview audience selector to production as if it were authentication. Do not merge application record IDs with synthetic case IDs or reuse the demo's host composition. Do not change backend contracts to accommodate a cosmetic screen.

## Immediate execution sequence

### Gate 0 — Protect the published draft work

- Keep #183 stacked on #166 while both remain draft; confirm #183's exact-head hosted verification and base SHA before changing it.
- Preserve its research, complete feature inventory, 16 form contracts, tests and screenshots as the reference baseline.
- No silent merge, deployment or role/clinical-ready claim.

### Gate 1 — Validate information architecture with real tasks

For fictional examples, independently walk through:

- Patient locates latest original record, learns what remains unknown, reads a linked report, and sees why a prior report became stale.
- Clinician locates a patient, identifies one sourced finding, opens the exact version, reviews a correction and reaches the affected draft without losing context.
- Reviewer finds an evidence contradiction and an option dependency without confusing a discussion or demo acknowledgment with a clinical decision.
Measure task success, first meaningful action, wrong-route hops, source traceability, back-navigation, and reading/keyboard burden. Keep observed timings distinct from estimates.

### Gate 2 — Close #183 UX-specific deficiencies without touching backend

- **Implemented in #183; retain as regression coverage:** worklist state stays consistent with accepted chart responses through its **existing** refresh owner. The [currentness increment](2026-11-02-worklist-currentness.md) adds keyed projections, explicit refresh and delayed-read protection; its exact published verification status is recorded in #183. It adds no competing fetch cache or push events.
- **Implemented and hosted-verified at #183 `94af20d`; retain as regression coverage:** first-roster recovery uses the existing initializer. The [startup continuation](2026-11-02-workspace-startup-recovery.md) distinguishes loading, unavailable and proven empty states, keeps a global retry reachable, and preserves saved creation without another POST. Accepted worklist completion resumes pending activation through the original picker; a later accepted case choice cancels that intent. Eighteen focused scenarios and 295 assertions pass. Exact published integration results remain recorded in #183.
- Audit the patient overview for repeated numbers, excessive warnings and unclear wording while preserving source provenance.
- Test 200%/400% zoom, keyboard focus through disclosures and dialogs, Safari/Firefox when available, and real assistive technology with testers. Record unsupported cases.
- Keep professional authoring and demo-review controls scoped to their intended presentation while preserving supported patient actions; explicitly communicate that the underlying demo lacks authorization.

### Gate 3 — Reconcile and verify the existing H1 experiences

The following extends OI-007, OI-009, OI-010 and OI-013 in the existing execution backlog; it does not create a parallel roadmap or mark those packages complete.

1. Pin the intended parent and inspect the current heads again. Compare #326's #319-based reading/import path with the #322/#328/#330 chain and #329's reading/session checks. Reuse matching source blobs; reconcile changed contracts rather than rebuilding patient entry, source reading or authored-evidence owners.
2. Run one synthetic journey on the selected composition: authorized patient → Overview continuation → original source → exact quotation → unfinished/saved question → verification return → authored evidence/report → follow-up attention → source amendment → historical report and reassessment → explicit recovery.
3. Include denied/expired access, disconnect, A → B → A selection, late responses, unsaved text, selected original files, exact uncertain-write retry and malformed evidence dates. Missing/unavailable history must remain different from a checked empty result. Reading modes do not grant authority.
4. Compare the same task with the reference workspace only where both support it. Record missing capabilities and measured navigation/focus behavior; do not demand matching DOM or infer parity from screenshots. Keep backend or archive integration with its separate owners.
5. Publish the changed-file/owner map and exact combined-head CI receipt in the existing H1 continuity record. Keep original PRs intact until their integration disposition is explicitly resolved.

**Completion condition:** one pinned candidate demonstrates the selected contracts together, with no new patient/source/evidence state owner, no silent lost capability and no unsupported clinical or model claim. Individually green parent/sibling PRs do not meet this condition.

### Gate 4 — Expand toward the oncology intelligence platform

Only after relevant services are real, authorized and independently assessed: meaningful longitudinal health view, source-linked AI investigation, disease-specific evidence exploration, care-team collaboration, actionable care navigation, and supervised scientific workflows. Every AI artifact must expose source provenance, uncertainty, currentness, rights status, human review status and a clear path back to the record. Safety-critical actions remain explicitly gated.

## Non-negotiable regression and release gates

- **Data isolation:** no cross-patient or cross-tenant data after an A → B → A navigation, late request, stale token or revoked permission.
- **Source fidelity:** original bytes, document/version/line, amendment lineage and historical reports remain reachable; missing is never automatically negative.
- **No artificial clinical certainty:** exploratory hypothesis ≠ reviewed medical fact; review acknowledgment ≠ verified clinician authorization; registry metadata ≠ patient trial eligibility.
- **Completeness:** no existing action silently disappears when moved; each form, error, empty state, history link, PDF/text limitation and import quarantine remains discoverable.
- **Usability:** primary task works with keyboard and mobile viewport, no page overflow, no loss of in-progress work.
- **Scope:** #183 changes frontend and its verification/docs only. H1 product expansion belongs to separately reviewed work, never concealed in this presentation PR.

## Decision on immediate merge/readiness

#183's existing hosted CI passed for its exact head when recorded, but the parent #166 remains unmerged and the target production architecture is different. Therefore **keep #183 draft until its parent and intended integration order are explicitly resolved**. A green synthetic demo run does not authorize real patient deployment. The next engineering increment should be the smallest evidence-backed UX/interaction improvement on the correct owner—not a speculative full frontend rewrite.

## References

- [PR #183: healthcare UX](https://github.com/OpenxIntelligence/open-intelligence/pull/183)
- [PR #166: connected synthetic workspace](https://github.com/OpenxIntelligence/open-intelligence/pull/166)
- [PR #181: H1 typed React patient entry](https://github.com/OpenxIntelligence/open-intelligence/pull/181)
- [Existing UX research and design](2026-11-02-research-and-design.md)
- [Frontend feature mapping](2026-11-02-frontend-audit.md)
- [Recorded verification](2026-11-03-verification.md)
