# Connected product foundation

## Construction mandate

Build the complete Open Intelligence infrastructure and product. Human and veterinary oncology share platform capabilities, with species-specific clinical rules and scoped patient, guardian and owner authority. Neither registration nor navigation is the overall delivery objective. Existing domain implementations remain their canonical owners. The PF-01–PF-10 foundations and PD-01–PD-16 domains remain unfinished construction work; this integration does not redefine them as complete.

## Implemented composition

This candidate combines diagnostic interface #568 (`9bdaa761f931900f8ac967077f9781a051fe5090`) with shared clinical/execution foundation #594 (`8ef436ee5b2d3835befd8c2783e4c0f94357789b`). The two Git parents and all published migration identities are retained. Neither donor branch nor main is changed.

| Product capability | Connected owner |
|---|---|
| Overview, Journey, Visits and original records | Existing patient registry, encounter/note history, scoped case bindings and source custody |
| Labs, Imaging, Pathology and Molecular | Existing diagnostic workspace, structured FHIR results, source versions and bounded non-diagnostic CT preview |
| Questions and preparation | Existing saved questions, laboratory citations and second-opinion preparation |
| Durable work | Existing Composer jobs, source-change delivery, retries, cancellation and result disclosure checks |
| Care follow-through | Existing task history and exact original reopening, including saved laboratory questions |
| Patient access | Shared request-scoped registry authority, independent grants, suspension and uncertain-command recovery |
| Operational recovery | Both existing registry/receiver/suspension and encounter/source-chart restore scenarios |

`0028_connected_product` is a no-DDL join of `0027_source_event_purpose` and `0022_encounter_sources`. The exact readiness contract points to the join. The shared registry adapter retains `encounter.source.link`; both HTTP capability inventories retain their owners. Source custody owns encounter/source links and imaging exports its existing bounded preview operation in the module manifest. No new runtime dependencies, patient ledger or scientific interpretation are introduced.

The UI retains direct patient lookup, diagnostic navigation, visit dirty-form protection and keyboard focus. Source-bound follow-through can reopen exact originals. Unknown suspension outcomes disable patient lookup in each workspace and preserve retry recovery in Overview. The browser scenario traverses all diagnostic sections and Visits while that outcome is unresolved.

## Verification

Local combined source: TypeScript/Vite build passed; 744 client tests passed with no skips; 13 dependency controls passed (18 installed packages, two absent optional packages explicitly uninspected); six focused migration-graph/recovery assertions passed. The 62-module, ten-owner static boundary check passes with the 86 existing explicit legacy symbol imports retained. Architecture and synthetic-boundary checks are recorded with the PR.

The initial local API discovery ran 1,024 methods: 75 socket-permission errors, 612 database skips and one obsolete hard-coded head assertion. The head assertion was updated to preserve the historical 0027 parent and check the new join; focused graph checks then passed. This is not a local full API or PostgreSQL pass. Local Playwright launch failed because its Chromium executable is absent. Hosted PostgreSQL and Chromium checks remain required on the combined source, not inferred from donor results.

Added populated-upgrade tests start from each published parent, retain existing owner rows, expose both encounter/source links and source-event storage, and check repeated upgrade. The hosted execution workflow runs these tests without skips. Full API CI retains both independent actual dump/restore scenarios; no assertion from either owner is dropped to simplify the composition.

## Next construction dependencies

1. Qualify this combined API, UI, migration, worker and recovery revision. Repair integration failures before extending its state.
2. Complete shared persisted consent and delegation enforcement through the existing registry/API/worker boundaries, with a connected permission-management interface. Production identity remains unqualified.
3. Connect the remaining clinical and scientific owners: specimens and diagnostic orders/results, therapy/medication workflows, trials, research pipelines and governed model execution. Preserve original/source versus interpretation boundaries.
4. Complete operational infrastructure: qualified external integrations, search with authorization before retrieval, observability, capacity, recovery and release controls.

The current connected API still uses its existing synthetic human-patient contract. This composition does not claim a species-aware clinical model, live provider connectivity, model execution, clinical validation, production readiness, or completion of the full core. Veterinary record semantics must be integrated into shared domain contracts rather than bypassed by relabeling a human record. The earlier isolated veterinary draft is not advanced here.
