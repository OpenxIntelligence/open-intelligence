# Manual passages and explicit comparison recovery

## Scope and source ownership

Continue OI-008, OI-009, OI-010 and OI-013 by combining verified #408
(`07cd593430d837dac5e097d15487ce99ac2c4108`) with verified #411
(`d217487d79460d25d4ac947009388a8df31c6e2b`). Their shared #402
baseline is `547039fb3ea3e2d520cbbc4e2318c5b97d99ceae`.

Keep #408's backend, migrations, dependencies, rights controls, manual document
selection and immutable passage/report ownership unchanged. Carry #411's
comparison field feedback and fresh historical-report invalidation into that
workspace. No new canonical ledger, grant or dependency is introduced.

## Acceptance

- Rejected quote/rationale edits cannot silently submit earlier accepted text.
  Correction or explicit acknowledgement is required for every rejected field.
- A fresh historical report, including frozen manual text/PDF context, hides
  earlier comparison controls. Its exact authorized historical download remains
  available; retained text alone never authorizes comparison submission.
- Manual-context access denial clears comparison text and rejection markers;
  reauthorization cannot resurrect either. Existing exact uncertain passage-save
  recovery remains independently owned by the session.
- Independent unsent follow-up creation/transition drafts survive evidence-only
  reassessment; navigation and evidence refresh make no implicit task writes.
- The actual combined PostgreSQL/FastAPI/built React browser journey must pass,
  including passage correction, original-read denial and preserved report bytes.

## Implementation and verification checkpoint

The three-way source composition preserves both runtime owners. Only the browser
helper signature and historical backlog prose required conflict resolution:
the helper accepts both the external amendment operator and manual-document
fixture, and backlog entries retain the manual-passage history with this scope
appended. Existing report/field-feedback browser assertions run alongside the
manual text/PDF journey.

497 inherited client tests passed before four composition checks were added.
All 18 manual-passage tests now pass, including the new frozen-report and three
denial checks. Initial test-fixture errors (missing imported evidence identifier
and mismatched report summary hash) were corrected; these were not product
regressions. Full final suite, production build, rights gate, independent review
and exact-head hosted browser evidence remain pending at this source checkpoint.
The final draft PR receipt must identify the reviewed head and actual results.

## Limits

Independently authored fictional data only. No clinical approval, model execution,
real-patient workflow, merge to main or deployment. Retained drafts are session
memory, not durable autosave. The unchanged backend's complete standalone
migration/recovery suite is not replaced by the frontend composition checks.
