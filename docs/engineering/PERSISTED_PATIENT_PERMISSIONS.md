# Persisted patient permissions

This continues the shared foundation on connected product PR #602. Visits, Labs,
Imaging, Pathology, Molecular and the existing clinical/scientific owners remain
intact. The complete Open Intelligence infrastructure remains under construction.

## Delivered code

`0029_patient_access` extends the existing identity owner with immutable grant and
revocation records. Each grant identifies the patient, recipient actor, purpose,
allowed actions, expiry, declared relationship, authority reference and issuing
actor. Supported relationship declarations include patient, guardian, animal owner,
care team and research delegate. These labels do not verify identity or authority.

Management uses independent `patient_permissions_read` and
`patient_permissions_manage` capabilities. Administrative capabilities and patient
creation cannot be delegated. Grants cannot exceed the operator credential's
action ceiling or expiry. Management requires the same organization and explicit
patient scope. No token is stored in a grant or domain event.

Grant and revoke commands use exact request fingerprints, serialize through the
existing patient row, and append events in the same transaction. Preparing the
actual response and refreshing operator authority precede commit. Repeated keys
with different intent are refused. Revocation remains possible after patient
suspension. Populated downgrade is refused rather than deleting policy history.

The existing registry authorizer checks persisted grants for patient operations.
The API, Composer worker and source-event worker select the same policy mode.
Existing owners retain their final authority checks. Expired or revoked grants,
wrong actor/purpose/patient/organization, unavailable policy storage and absent
credential capabilities do not authorize clinical-data access.

## Configuration and interface

Set `OI_API_REQUIRE_PERSISTED_GRANTS=1` in the API and worker environments to require
stored grants in addition to the trusted credential ceiling. Compose exposes the
same setting to its shared service configuration. Invalid values fail startup.
The default `0` preserves the explicitly synthetic fixture demonstration; it is
not an implicit consent migration. The API manifest and permission console report
which mode the server selected. No grants are inferred from existing records.

An operator credential needs both management capabilities and the patient's ID
to bootstrap a grant, independently of patient-read permission. The operator can
open the console from Overview using that ID even before a clinical read grant
exists. The console clears clinical records before managing policy, lists paged
history, records an explicit declaration and revokes individual grants. Another
active overlapping grant may still authorize an action.

Unknown command outcomes retain an exact, memory-only retry across workspace
navigation. Patient switching and duplicate changes are blocked until recovery.
Disconnect/reload clears the transient console. Authority references are opaque
references to independently fictional declarations; they are not uploaded legal
documents, verified caregiver relationships or clinical consent attestations.

## Verification

The initial local continuation passed 13 contract/HTTP/configuration/graph tests,
seven permission-client scenarios, the React production build, and module-boundary
checks. Hosted PostgreSQL and Chromium results must be recorded on the dependent
PR for the actual proposed source. The previous #602 results do not validate this
new policy layer.

New acceptance covers scope intersection, concurrent exact retries, final provider
revocation, response-encoding rollback, expiry, both worker entry points,
immutable history, populated downgrade refusal and actual pg_dump/pg_restore.
The browser scenario uses the real API/database: grant through the UI, lose the
committed response, navigate diagnostics, recover exactly once, read under the
grant, revoke it and verify denial after API restart.

## Remaining foundation

Production authentication, organization membership and role administration,
verification of consent and delegated legal authority, broader species-aware
clinical contracts, and policy activation/rollout controls remain unfinished.
This code implements bounded synthetic authorization declarations, not those
larger capabilities. There is no transitive delegation, automatic model unlearning,
or claim of globally atomic revocation of already disclosed data. Current owner
transactions and their existing final checks define the disclosure boundary.

No real patient data, merge, deployment, clinical effects or new runtime dependency
is introduced. Next construction continues verified authority and consent through
these shared owners and interfaces, followed by the remaining clinical/scientific
domains and operational infrastructure.
