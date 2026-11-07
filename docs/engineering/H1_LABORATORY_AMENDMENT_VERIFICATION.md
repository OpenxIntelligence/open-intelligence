# Independent verification of amended laboratory transcription

This implements the next OI-009 handoff on connected candidate #624 at
`631c3e0cea30d4b859a2e428d200d352c97c6567`, preserving its permission,
historical World Model, diagnostic navigation, and Composer owners.

An authorized requester opens an existing laboratory follow-up task, compares
its immutable original Observation with the current report in the same lineage,
and records a verification request. A different authorized actor opens the
case's Review inbox and records either **Transcription checked** or **Needs
clarification**. The requester can reopen the task and read both attributed
entries. This does not complete or refresh a stale task or approve a clinical
interpretation. Missing Observations, reported absence, literal zero and decimal
precision remain distinct.

## Ownership and authority

- The original task, question and source owners retain their identities. One
  additive immutable history table records the request and response, their exact
  original/current source IDs and digest. Migration `0030_lab_amendment_reviews`
  follows the existing `0029_patient_access`. Every previously published migration
  is unchanged. Empty downgrade is permitted, populated downgrade is refused.
- Reads and writes require fresh patient, source, original, question and task
  read authority. Requesting additionally requires `followthrough_create`.
  Responding requires `review_queue_read` and `review_return`. The stored actor
  comes from the credential. Persisted patient grants also apply when enabled.
- The source owner validates originals and actual predecessor lineage under
  its existing lock. A second amendment cannot retarget a pending response.
  Previously committed exact retries retain their IDs after further amendment,
  but current permission is checked again. Same-actor responses are refused.
- The client clears comparisons on scope/access changes and suppresses late
  replies. An uncertain write exposes an explicit retry using the identical
  command, with no automatic replacement request.

## Verification at construction checkpoint

Local checks pass 829 client cases, the TypeScript/Vite build, 13 dependency-rights
checks, 1,038 reference tests, 10 API surface checks and 8 demo setup checks.
An integration regression reproduced loss of an uncertain amendment command
when opening permission management. The existing pending-write guard now
preserves it before permission management or patient suspension. Actual PostgreSQL acceptance and the live
browser/recovery journeys are pending on this combined candidate. Local database
skips are not passes. The executor lacks PostgreSQL 16 and rejects the inherited
Unix-socket archive tests. No runtime dependency was added.

The PostgreSQL tests cover both actors, request/response races, exact historical
retry, missing/absent/zero observations, source and scope tampering, permission
withdrawal, immutable history and populated upgrade/downgrade. The connected
browser journey checks an independently denied/restored response grant and
requester readback. The existing FHIR recovery probe now also checks attributed
entries through restart and backup/restore, a new amendment and response on the
restored database, preserved earlier retries and denied access after revocation.
Those are authored acceptance requirements until their hosted executions pass.

Run the persistent fictional demo with `--with-reviewer` to obtain a separate
reviewer credential. See [the demo guide](../H1_DEMO.md). The default remains a
single operator. No external notifications, real patient inputs, model execution,
merge or deployment occur in this increment.
