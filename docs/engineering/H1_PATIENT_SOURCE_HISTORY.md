# Historical patient source context

Implements the receipt-time reconstruction increment under OI-004/OI-005 and the
existing PF-03 source / Patient World Model owners. This advances the supplied
master vision's longitudinal patient model and history requirements. The complete
shared foundation and human/veterinary clinical/scientific portfolio remain under
construction; this increment is not their completion.

## Connected baseline

Preserves both original parents: persisted permissions and browser isolation
(#611/#612, e0f4c447a38f719db80b6247da613c549fa78cef), and connected Labs/Imaging
(#608/#610, a5ac62a25b924f0edb6f8b2a77886d7b8467d466). Their common connected product
foundation is #602 at 2e37d7579f3d748dfe2918a1ec4d02872e0e625c. No donor branch or
main is changed. Combined acceptance must run on this candidate, independently
of donor evidence.

## Behavior and ownership

`GET /v1/patients/{patient_id}/cases/{case_id}/world-model/history?received_through=<ISO timestamp>`
returns `oi.pg-source-history/1`. The timestamp must be timezone-aware and cannot
be in the future. The boundary is inclusive and preserves microseconds.

The existing PostgreSQL source owner validates the entire original history,
selects versions received by the cutoff, and reconstructs reported assertions
from the validated originals. For each document the highest visible version is
current **at that cutoff**. An older clinical event received later is absent
from the earlier view. FHIR lab values, units, missingness, specimen references
and original provenance come from the same versioned laboratory owner. No units
are converted, trends inferred, or clinical conclusions produced.

The current model endpoint and fingerprint contract are unchanged. Historical
models use the same deterministic source fingerprint, allowing a pre-amendment
view to be reproduced after an amendment and restart. This is history of
structured reports received by the system, not a claim of what a clinician knew
or reviewed. Reviewed-document passages, encounter notes, investigations,
clinical beliefs, decisions and external literature are not reconstructed here.

Journey exposes receipt selection, a historical read, exact source versions,
reported statements, laboratory values and provenance. History is held separately
from current question/Composer context, has no write or export actions, and clears
when current context changes, on disconnect or denial. Out-of-order responses
cannot restore a dismissed or invalidated view. Unknown/corrupt responses produce
an explicit retry state.

## Authority, persistence and recovery

Each read requires current patient/source access, organization, actor, purpose,
active patient and active case binding. Persisted permission enforcement follows
the same configured registry authorizer as all other source reads. Past grants
are never restored. `source_original_read` is not implied: no original bytes are
returned, only the source-derived projection authorized by `source_read`.

Response encoding happens under existing patient/case transaction locks. A
reference-only `source.history_prepared` event records the requested cutoff and
shares the current source-read receipt ID. Final authority is refreshed before
and after the read event. Preparation, audit or authority failure rolls back both
events and withholds the response. The events are authorization/preparation
evidence, not proof of network delivery.

No schema migration, duplicate patient/source store, background job, model call,
new runtime package or external service is introduced. Persistence and restore
reuse the existing source, laboratory and event tables. Historical reads do not
change source states or the current case snapshot.

## Acceptance

New actual PostgreSQL/API scenarios cover exact pre-amendment reconstruction,
late-arriving older events, an empty cutoff, cross-case/organization denial,
revocation after response preparation, encoding-failure rollback, corrupt older
originals, invalid timestamps, API restart and historical FHIR observations.
The existing actual Chromium journey now reopens the first receipt after an
amendment, compares its fingerprint with the earlier observed fingerprint,
checks literal escaped text, confirms the current finding remains amended, and
retains 390px/1280px screenshots with overflow checks. Receipt ordering compares
exact instants, including microseconds and equivalent UTC offsets.

Local: 781 client tests pass with zero failures/skips, production build passes,
10 HTTP/contract checks pass, and compilation/data-boundary/whitespace checks
pass. Full local PostgreSQL acceptance cannot run: PostgreSQL is absent and the
system installer cannot change identities in this environment. Hosted exact-head
results belong in the dependent draft PR; these local checks are not a database,
backup/restore or real-browser pass. No new migration requires a new upgrade path;
the inherited full database/recovery suites remain required for the combined tree.

## Next construction dependencies

Connect the existing semantic evidence/belief proposal (#604/#606) to these
canonical PostgreSQL source/time/authority contracts after its owner review;
do not introduce a second Patient World Model. Then extend source-change review
and cross-modal comparison through existing question/evidence/review owners.
Qualified identity and delegated consent, species-aware clinical contracts,
orders/specimens, treatment, trials, research computation and operational recovery
remain part of the full build. Draft, unmerged, undeployed; fictional data only.
