# Connected laboratory originals and patient Journey

4 November 2026. Bounded continuation of source owner #115 and FHIR workstream
#428 (workspace stage), extending draft #469 at
`8ff6e9e5a0389a1142ca479a6705c599cbda88e7`. Observed main was
`a5a5482f815ceb3c322cdfb32ab8b18c1c0e8709`; #463 remains the parent integration.
The separate preparation/navigation work in #470 and manual-task migration work
in #457/#462 is not silently included.

## Problem and user outcome

The backend already preserves bounded fictional FHIR R4 laboratory bundles in
the canonical source ledger. The client validates laboratory projections but
did not render them; its generic original reader also rejected valid laboratory
JSON as unsupported authored text. There was no dedicated file-import journey.

Records now offers an explicit laboratory JSON file selection. Selection and
inspection are local; the user confirms the independently fictional original
before import. The existing source-import endpoint remains authoritative for
patient/case mapping, supported FHIR profile, source versions and permissions.
An amendment requires a deliberately selected current predecessor. The client
never rewrites source JSON, converts units, fills missing values or interprets
results.

The same source appears in Journey with literal numeric values, UCUM unit codes,
LOINC codes, absent-result reasons and separate collection/effective/issued dates.
Collapsible provenance preserves source/version/hash and exact specimen,
report and observation locators. Records permits independently authorized
inspection of both current and historical JSON originals after byte-hash and
source-binding verification. Existing authored-text validation remains strict.

## State and authority

- One existing patient, case, source and World Model owner; no new data store,
  API, schema migration, runtime dependency or permission.
- One immutable pending command in memory holds original bytes, request key,
  predecessor and patient/case. An uncertain reply is explicitly unknown;
  manual retry reuses that exact command. A lost reply is not rollback evidence.
- Requests and late responses remain scoped to the current patient/session/case.
  Fresh authority is enforced by the backend; original-read and source-read
  grants remain separate. Confirmed denial clears protected views.
- This read view does not promote laboratory values to reviewed clinical facts
  or create new laboratory-linked investigation questions automatically.
- In-memory pending commands do not survive full browser reload. Durable
  backend custody and recovery remain the #469 owner, with separate evidence.

## Verification contract

Focused client checks cover exact bytes, strict receipt identity, explicit
confirmation, duplicate submissions, uncertain outcomes, exact retry,
patient/case/session changes, authority denial and original verification.
Rendered React checks distinguish zero, numeric negatives and absence while
preserving source chronology and literal markup.

The existing hosted H1 web workflow compiles the client and production UI,
checks installed dependency rights, and runs Chromium against the actual
PostgreSQL/FastAPI application. Its new dedicated laboratory journey imports
an independently authored file, loses a real successful response, recovers the
same receipt without duplicate sources, reads typed results, explicitly amends
the report, inspects exact historical/current originals and proves fresh-read
denial after grants are withdrawn. It saves a narrow-screen capture and a
bounded synthetic receipt. No mocked successful server responses qualify this
journey.

Local parser checks and source syntax are separate from hosted browser/build
proof. Exact execution results, failed attempts and the tested commit belong in
the draft PR and canonical engineering record. Do not inherit #469's successful
tests as a new result for this frontend change.

## Remaining scope

Synthetic development only. No external FHIR/SMART connection, real accounts or
consent, terminology expansion, general FHIR conformance, laboratory operations,
result interpretation, model execution, clinical approval or deployment.
Backend backup/restore is unchanged and not rerun solely for this frontend
increment. Migration convergence and integration of sibling UI branches remain
separate reviewed work.
