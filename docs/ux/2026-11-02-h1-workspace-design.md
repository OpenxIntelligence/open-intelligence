# H1 patient and clinical reading workspaces

Date: 2 November 2026 (America/New_York). Status: implementation decision within the founder-authorized frontend redesign. Not a new backend, account model, architecture or clinical release.

## Intent and source of truth

Advance the accepted React/Vite/TypeScript product from the exact PR #200 source `d8de9aaca352cc58b64e9e32440f4ea248b02cb8` (tree `f46b666e63dd1ae0d842f0480b5ab942dc16e8b9`). The attached Master Product Research, UX/UI Redesign & Frontend Engineering Directive authorizes ordinary frontend design choices and explicitly prohibits backend/API/authentication/authorization/business-rule changes. Current H1 behavior, not historical screen proposals, defines the implemented feature set.

The complete Python/SQLite reference workflow remains in `web/` and its existing branches. PRs #183/#192/#198/#202 contain related reference-lane UX work; this change does not duplicate or merge those branches. H1 still lacks the migrated investigation/review workflows. Existing independent source and patient owners remain authoritative.

## Approaches considered

| Direction | Benefit | Cost and reason for decision |
| --- | --- | --- |
| One dense dashboard with every source, identity form and planned domain | Few destinations; resembles the existing reference app | Competes for attention and cannot express audience priorities well. Rejected for the active H1 workspace. |
| Separate patient and clinical applications with independent routing/data state | Maximum freedom for each audience | Would duplicate the client, introduce unsupplied role assumptions, and increase context/permission regression risk. Rejected. |
| Shared source authority, two reading layouts, persistent identity and contextual chart navigation | Different patient/clinical task priorities while retaining one client and all existing actions | Selected. Reading preference has no authorization effect; unsupported account roles remain unsupported. |

## Selected design

- Retain the existing green/neutral design language, system-font stack, React/Vite/TypeScript, native controls and existing browser harness. Add no dependencies, fonts, remote assets or external services. Next.js remains excluded.
- Offer **Patient view** and **Clinical view** as explicitly named reading preferences. Neither is a login or a grant. Default to patient view. Patient home prioritizes opening the record and understanding source status; the clinical layout prioritizes exact identity and source provenance. Both expose all existing controls.
- Separate workspace navigation from a **Patient chart** navigation shown only after a successful authorized patient read. The selected opaque patient ID, originating organization and registry status remain visible across destinations. No invented names, DOB, clinician accounts, avatars or medication/allergy summaries.
- Keep Overview and Records connected. Preserve Journey, Investigations and Review as reachable, explicitly unconnected destinations, grouped below the working navigation. Do not add appointments, messages, medications or other absent workflows.
- Keep session connection, exact-patient open/recheck, fictional creation and same-key retry behavior. Display errors wherever the user is, including credential expiry from Records. Keep all existing clear-on-denial/selection/disconnect behavior in the unmodified client.
- Make records a dedicated patient chart with case selection, version history, current/superseded text labels, report dates, receipt dates, and source-reported statements adjacent to their source version. Preserve literal statements and reported-state wording.
- Use progressive disclosure for exact source IDs, hashes, specimen IDs and supersession links; all remain directly inspectable. Add local filtering of **already loaded** source versions, with all versions visible by default, a result count, a clear action, and a distinct no-matches state. Filtering is presentation only and does not fetch or reinterpret records.
- Reset local record filters when the loaded patient/case/source response changes. Navigation and reading preference do not trigger requests or abandon unsent credential/patient-ID input. A new read continues to clear prior patient/source state through the existing client.
- Use native buttons, selects, details, fieldsets, labels and live statuses; preserve a skip link and a logical focus order. Move focus to the main heading after explicit destination changes. Use 44px product touch targets, visible focus, responsive wrapping and reduced-motion support. Do not claim full WCAG conformance from automated checks.

## File boundaries

Permitted: `apps/web/src/main.tsx`, `apps/web/src/styles.css`, new presentation-only frontend components/helpers, frontend browser/unit tests and documentation. `registry-client.ts`, `source-contracts.ts`, `source-model.ts`, `apps/api/**`, `src/**`, databases/migrations, runtime dependency manifests and authentication/authorization stay byte-identical to the base. Test workflow wiring may change only if required to run existing frontend verification on the new branch.

## Acceptance and meaningful failure modes

1. Both reading layouts preserve creation/read/recheck/disconnect and all five existing destinations. Changing layout produces no network call, no grant, and no patient/source mutation.
2. Every connected chart view identifies the same exact currently authorized patient. Pending/refused reads, expired credentials and disconnect leave no former patient/source text in the rendered chart.
3. Current and superseded sources are both available; source quotations remain literal, show their actual reported states, and retain source/version/line references. A version filter cannot silently change clinical meaning.
4. Loading, a successful empty response, the existing client error messages, and no filter matches are distinct. The client intentionally groups some invalid-response/network/permission errors: preserve those combined explanations rather than inferring a more precise cause. Recovery controls invoke only the existing session methods.
5. Keyboard navigation, main-heading focus, native disclosure, 320/390/768/1440px reflow, long opaque identifiers and literal HTML-like source text are exercised in a real browser. Runtime errors are checked. Existing client isolation and real PostgreSQL browser journeys must remain green.

## Evidence and limits

Independent builder review clarified that the active `RegistrySession` consumes `source-contracts.ts`; the unused `source-model.ts` does not authorize adding original-document retrieval. It also confirmed that `source_reported_assertions` contains current-version quotations only. Historical-version rows must explicitly say that this response does not supply their quoted statements, never imply absence of historical observations. Persistent identity is rendered from `state.patient`, never the editable ID input. Source denial clears sources without claiming that patient identity itself was revoked.

Research is captured in the adjacent competitor/guidance reports. NHS App published navigation research supports task-oriented hubs with limited duplicated entry points; SAFER patient-identification guidance supports persistent identity; WCAG 2.2 supplies accessibility acceptance criteria. These are design inputs, not demonstrated outcomes for this implementation. Current-code screenshots and test results will be recorded separately after execution. No real patient/clinician usability study, medical interpretation, production identity, deployment or HIPAA/WCAG certification is claimed.
