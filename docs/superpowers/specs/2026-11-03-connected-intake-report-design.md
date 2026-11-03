# Connected original intake and patient workflow

## Intent and accepted direction
Continue the founder-authorized connected patient workflow: make the existing
empty-workspace and inspected multi-file intake work with source-linked records,
rights-qualified evidence review and readable reports/follow-through. Preserve
all original domain owners. The accepted H1 React/Vite/TypeScript and
FastAPI/PostgreSQL target is not replaced by this reference integration.

## Inputs and approach
Use #210 at 9735414c947c211ab20154638179d0be8ff2db32 and the newer
#203/#196/#179 intake/rights lineage at f9ba8d66b56a7d6669ef0ffce902af6565e1b477.
Their common reviewed source owner is #175 at
1d5cd0502b5789371165539149dcecad8df5e551. Both source archive trees were
verified against published Git tree identities before editing.

Rebuilding intake would duplicate existing owners. A simultaneous H1/UX/PDF
migration would make this slice unbounded. The selected engineering approach is
an additive source reconciliation with original tests retained, plus regressions
for behavior crossing those owners. This is an implementation choice within the
accepted continuation, not a new founder-approved architecture.

## Required behavior
An empty workspace can be created; authored text originals are inspected before
any writes and imported sequentially under one case. Per-file imported, duplicate,
quarantined, rejected, unknown and unattempted outcomes stay distinct. Every write
participates in the existing pending-write/report-invalidation boundary. A slow
or ambiguous import cannot leave the old report downloadable. The existing protected drafts and follow-through input fields veto a scope
switch or new workspace; unresolved writes also block switching. Composer source actions use the existing exact-source inspector.

Source amendments retain originals and history, flag open follow-through work,
and invalidate affected reports; completed tasks do not become clinical approval.
Content-class-specific rights remain enforced by #203's existing domain services.

## Non-goals and boundaries
No new patient/source/evidence/task ledger, runtime dependency, schema, clinical
endpoint, real patient record, Sid data, external model, publisher right, clinical
signoff, production authentication, automatic main merge or deployment. H1, PDF,
post-save extraction correction and UX redesign remain separately owned work.
