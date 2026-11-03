# Open Intelligence — UX convergence and next implementation gates

**Decision record:** 2 November 2026 (local project date; repository UTC activity may show 3 November)  
**Scope:** design and implementation planning only. No backend, database, API, authentication, authorization, or business-logic change is authorized by this document.

## Decision

Keep **PR #183** as the tested, frontend-only information-architecture and interaction improvement to the **connected synthetic reference workspace** in PR #166. Do **not** misrepresent it as an authenticated, real-patient product or the future React application.

In parallel, **PR #181** starts a distinct React/Vite/TypeScript patient entry on the separately owned FastAPI/PostgreSQL H1 path. That product target should inherit validated **experience contracts and patterns** from #183, not an unreviewed copy of its monolithic DOM controller, static-role preview logic, or synthetic ledger adapters.

Open Intelligence is an oncology-intelligence platform, not merely a replacement EHR. The overall UX must ultimately integrate patient records, longitudinal understanding, investigations, evidence, clinical collaboration, and appropriately authorized care coordination. This is a future product direction; it is not a claim those services already exist.

## Observed branch state and supported claims

| Candidate | Role | Current boundary |
|---|---|---|
| #166 connected workspace | Local synthetic source → question → investigation → human demo review journey | No real patient authorization or general file extraction |
| #183 healthcare UX | Patient presentation; searchable worklist; distinct case chart; 21 focused destinations | Presentation-only audience selector; no security role model |
| #181 H1 React entry | Typed frontend wired to H1 patient registry; explicit temporary synthetic permission exercise | Patient entry/identity only; record, investigation, review and clinical collaboration not connected |

The above are separate draft proposals at the time of this record. Any subsequent integration must re-check exact heads and CI; never assume draft status implies merged capability.

## Architecture: three navigation levels, not a giant sidebar

1. **Global product context:** patient portal or authorized professional workspace, with only server-authorized resources. Personal workspace / patient roster / appropriately public research area; never use a local role toggle as a permission boundary.
2. **Selected patient chart:** stable patient identity, source-aware summary and clearly scoped sections. The header is persistent, but contains only actually available data, provenance and relevant actions.
3. **Within-chart task context:** record detail; source/version reader; current question; investigation/review; evidence and options. Sub-navigation follows a real task, not a permanent third-level menu.

For future oncology functionality, group by *user outcomes* rather than by independent engines. Patient: Understand my situation, My records, Questions & updates, Care coordination (only when genuinely implemented). Professional: Worklist, Patient chart, Investigations and review. Research: shared evidence tools only where allowed. Do not introduce empty “Appointments,” “Medications,” “Messages,” or “AI Diagnosis” destinations merely because competitors have them.

## Portability contract: #183 → H1 React (future work, not part of #183)

| UX contract proven or proposed in #183 | React integration requirement | Gate |
|---|---|---|
| Separate patient home and professional worklist | Introduce only after backend identity, scopes, and authorization support these experiences | Server-scoped role and ownership tests |
| Selected chart and contained chart navigation | Bind to H1's canonical patient reference, not synthetic CASE-* identity; use the one existing data owner | Cross-tenant/cross-patient denial and reload tests |
| Exact original-source citation reader | Reimplement once H1 can retrieve a rights-permitted source with stable source/version/line anchors | Provenance, correction, and revoked-access tests |
| Questions, draft review and model-assisted research | Integrate only when matching accepted H1 API contracts exist; do not create a shadow client ledger | End-to-end source → question → review → amendment |
| Same-case draft preservation and cross-case veto | Preserve editing intent across route changes; fail closed when changing authorized identity | Unsaved-input and delayed-response race tests |
| Responsive navigation, focus, mobile containment | Transfer tokens, semantics, interaction behavior; not brittle DOM selectors from vanilla JS | 320/390/768/1024/1440 widths, keyboard and screen-reader QA |
| Patient-safe language, unknown/negative/pending distinctions | Reflect source assertions without generating diagnosis or clinical certainty | Fixture-backed assertion-to-source validation |

Do not transfer the local preview audience selector to production as if it were authentication. Do not merge application record IDs with synthetic case IDs or reuse the demo's host composition. Do not change backend contracts to accommodate a cosmetic screen.

## Immediate execution sequence

### Gate 0 — Protect the shipped work
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
- Verify whether worklist state refresh can be presented more truthfully using its **existing** refresh owner; do not add a competing fetch cache or invent push events.
- Audit the patient overview for repeated numbers, excessive warnings and unclear wording while preserving source provenance.
- Test 200%/400% zoom, keyboard focus through disclosures and dialogs, Safari/Firefox when available, and real assistive technology with testers. Record unsupported cases.
- Ensure all dynamic controls remain hidden in patient **presentation** only; explicitly communicate that the underlying demo lacks authorization.

### Gate 3 — Bring patterns to the new H1 app incrementally
- First complete H1 patient entry and server permission/identity contracts.
- Add a patient home reading only existing H1 projections.
- Add the dedicated chart shell only when an authorized H1 chart source exists.
- Add original-record, investigation, review and evidence surfaces in supported vertical slices.
- Run mirrored task acceptance tests in both reference UX and H1 rather than claiming parity from matching screenshots.

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
