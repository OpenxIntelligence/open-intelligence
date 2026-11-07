# Connected consent decisions

Continues #98 / OI-013 / PF-02 on the single connected product. Composition retains
#624 at `631c3e0cea30d4b859a2e428d200d352c97c6567` (permissions, historical World
Model, diagnostic workspaces, Imaging chronology and Composer snapshot binding)
and #629 at `0b3f554cf32c177df02ef043550de130827d74eb` (purpose restrictions).
It does not overwrite their branches or import unrelated pending candidates.

## Operational contract

The existing identity journal now records `identity.consent.decided` events.
No new patient ledger, migration, dependency, model or clinical action is added.
Recipient actor, purpose, explicit allowed actions, validity interval, declared
decision-maker/basis, opaque declaration reference and actual recording operator
are preserved. All inputs must declare independently fictional data. Self,
guardian, animal owner and representative are declarations, not verified identities
or legal conclusions. Scope is the current patient's record and the named actions;
per-source segmentation and external disclosure reconciliation remain unfinished.

POST `/v1/patients/{patient_id}/consent-decisions` requires independent
`consent_read` and `consent_manage` capabilities, same organization, explicit
patient scope and operations purpose. These administrative capabilities cannot be
delegated through patient permission grants. Allowed uses and expiry cannot exceed
the recording operator's credential ceiling. The declared decision-maker may be a
different fictional actor; no relationship is inferred from that identifier.

The patient row serializes writes. Each recipient/purpose pair has a strict
revision. Exact actor-bound request retries return the historical receipt without
reapplying it. Changing intent under an old key or writing against a stale revision
is refused. Actual response preparation and final fresh authority precede commit;
failure rolls back the journal event. Withdrawal remains possible after suspension.

The newest recorded decision replaces the prior decision immediately. A scheduled
decision holds access until its start; expiry, withdrawal, omitted actions and
unknown states deny. Historical World Model views still require current authority;
an old consent version does not authorize a retrospective disclosure.

GET on the same route lists bounded, descending event history with an opaque
numeric `before` cursor, current/superseded state and actual operator attribution.
Validity is evaluated by PostgreSQL time. Reads prepare their complete response
before rechecking authority. No bearer credential enters the event or response.

## Shared enforcement

The shared registry adapter intersects the trusted credential, persisted-grant
policy, purpose restriction and latest consent decision. Purpose restrictions
remain subtractive; lifting one does not create consent or a permission grant.
API, Composer worker and source-event worker use this same adapter. Management
capabilities remain independent so missing/withdrawn clinical authority does not
prevent inspecting or removing a declaration.

`OI_API_REQUIRE_CONSENT_DECISIONS=1` requires a current positive decision for every
protected use, including patient reading. The default `0` retains legacy synthetic
behavior only when no decision exists; once recorded, a decision always constrains
its recipient/purpose. This is separately visible in the API manifest and UI.
Compose supplies the same setting to its shared API/worker configuration. The
credential cannot override the server's chosen mode. Existing permission mode
remains an independent setting; no old grant or display-only consent note is
silently promoted into a new consent event.

## Connected experience

Overview adds a consent console next to permissions. It can be opened by patient
ID without a clinical read grant. Opening clears patient records but refuses to
erase an unresolved clinical or policy write. The console shows history, declared
authority, validity, action scope and revision, and supports recording/withdrawal.
Unknown outcomes preserve the exact in-memory request through diagnostic navigation
and refused retries. Another patient, permission console or new command cannot
replace that pending intent. Credentials/session replacement clears transient
state and fences late responses. Reload/disconnect does not persist unsent intent.

The stored receipt is historical; the UI explicitly asks for fresh history after
recovery. It does not present a recovered old grant as the current decision.
Already downloaded files and already displayed data in another session cannot be
recalled by this implementation. Owner transactions retain their existing final
authorization boundaries; there is no distributed atomic-revocation claim.

## Verification and remaining work

Local contract checks, the complete client suite, production build, static owner
boundaries and synthetic-data gate are run for this candidate. Exact counts and
failures belong in the dependent PR. Actual PostgreSQL, real-browser and complete
cross-domain recovery acceptance must pass on the published source; donor passes
are not combined acceptance.

New acceptance exercises scope intersection, revisions, concurrent exact retries,
rollback, recipient/purpose/tenant boundaries, validity windows, both worker entry
points, queued/claimed/completed runs, pagination, suspended-patient withdrawal,
actual backup/restore and immutable history. The browser uses actual React/API/PG:
lost committed response, refused retry, identical recovery, grant-plus-consent read,
withdrawal while the access grant remains active, and restart denial.

The complete platform remains under construction. Qualified authentication,
organization membership, verified representative authority, legal-consent evidence,
source/data-class segmentation, rollout controls, downstream acknowledgments and
the remaining clinical/scientific domains are not completed by this increment.
Draft, unmerged, undeployed; independently fictional data only.
