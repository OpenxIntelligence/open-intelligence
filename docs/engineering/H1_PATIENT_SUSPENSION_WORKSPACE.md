# Patient suspension from the operator workspace

This dependent increment advances WS-02 / #98 and OI-013 on the canonical
patient suspension owner [#588](https://github.com/OpenxIntelligence/open-intelligence/pull/588),
source `bb9f7b2383ce4b11d329baf696bcd7af4c6d8831`. It retains the governed
foundation and workspace composition in #565/#584. It does not merge those drafts
or include every change subsequently accepted on main.

## Connected behavior

Open an authorized fictional patient in Overview, expand the operator suspension
panel and explicitly confirm the displayed patient. The client sends the existing
`POST /v1/patients/{patient_id}/suspensions` command with a random request key,
the exact read revision and `synthetic: true`. The API independently enforces
patient-read and suspension grants, persisted organization and operations purpose.

Before sending, the session clears its patient content and unsaved drafts, aborts
outstanding readers and invalidates their callbacks. Known unresolved writes block
a new suspension so their recovery requests are not silently replaced. The client
does not create a patient state store, cancel server jobs or invent an approval.

A valid receipt must identify the same patient, `suspended` status and exactly the
next revision. Lost, malformed or server-error responses retain the exact command
in tab memory. Repeated clicks cannot send competing commands. The operator can
retry that unchanged command; a refusal after an ambiguous attempt does not prove
the first attempt failed. Patient switching and creation remain blocked until
recovery completes or the operator explicitly leaves recovery. Leaving, disconnect
and reload discard local recovery, not the server operation.

## Verification

- `cd apps/web && npm test`: 716 tests passed, zero failures/skips at the initial
  implementation checkpoint, including ten focused suspension methods and two manual-passage recovery regressions.
- `npm run build`: TypeScript and Vite production build passed.
- `npm run rights`: 13 controls passed; 18 installed packages inspected, two absent
  optional packages explicitly uninspected; no dependency or lockfile changed.
- Python compilation of the browser helpers, synthetic-data boundary audit and
  `git diff --check` passed.
- `patient_suspension_journey.py` extends the existing hosted browser gate with
  real PostgreSQL/API permission denial, a committed response lost in transit,
  API restart, exact retry, one immutable journal event, cleared views, denied
  source access and an unaffected independently fictional control patient. Local
  PostgreSQL/Chromium were unavailable; this scenario is not a local pass.

The draft pull request records the exact published revision and hosted results.
Parent receipts retain their original source scope. No published migration or
backend implementation changes in this increment. Readiness remains
`0027_source_event_purpose`.

## Remaining dependencies

Production identity, caregiver delegation, enforceable consent and reactivation
remain separate missing capabilities. This is an administrative synthetic-data
operation, not consent withdrawal, deletion, clinical approval or deployment.
The complete PF-01–PF-10 / PD-01–PD-16 construction objective remains open.
