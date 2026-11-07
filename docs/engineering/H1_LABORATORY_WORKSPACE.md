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

## Report format and amendment history

The generic text and FHIR laboratory importers share a source version table.
A matching report ID, case, specimen and date can identify a collision between
the two formats. The structured writer checks the whole document history under
the existing case lock before accepting an amendment or duplicate. Records
shows a version conflict so the operator can reopen the original and choose
the appropriate intake. An accompanying note requires its own document ID.

For previously stored mixed histories, the source index and World Model withhold
the affected case projection. The original reader can still open an authorized
version before the first mixed edge. A later text retry cannot extend the mixed
history. There is no automatic choice of a correct version. An operator can
inventory the number of affected document histories in a synthetic restore
without printing source content:

```sql
SELECT count(*) AS mixed_document_histories FROM (
    SELECT s.case_id, s.document_id
    FROM clinical_source.source_versions AS s
    LEFT JOIN clinical_source.fhir_laboratory_sources AS f USING (source_id)
    GROUP BY s.case_id, s.document_id
    HAVING count(f.source_id) BETWEEN 1 AND count(*) - 1
) AS mixed;
```

Preserve originals, receipts and dependent question/report references for
review before any repair. [PR #572](https://github.com/OpenxIntelligence/open-intelligence/pull/572)
tracks HTTP, browser and restored-database verification on the proposed revision.

## Remaining scope

Synthetic development only. No external FHIR/SMART connection, real accounts or
consent, terminology expansion, general FHIR conformance, laboratory operations,
result interpretation, model execution, clinical approval or deployment.
Backend backup/restore is unchanged and not rerun solely for this frontend
increment. Migration convergence and integration of sibling UI branches remain
separate reviewed work.

## Journey-to-Records navigation — 4 November 2026

Each laboratory result's provenance disclosure now offers **Open report versions in Records**. The action navigates to Records and requests fresh source metadata for the exact case in the displayed World Model. The user then selects the immutable report version to inspect its original under the existing independent original-read permission and byte checks. Loading or busy context disables the action. No laboratory-to-question binding or clinical interpretation is added.

Local verification: 512 client/rendered tests passed, including two new cases that fail on the parent implementation; TypeScript and the Vite production build passed. All 13 dependency-rights control tests passed, but installed-package inspection failed: optional `@napi-rs/lzma-linux-x64-gnu` has no actual LICENSE/NOTICE file (19 installed, one optional entry uninspected). The gate was not weakened; resolve this before merge/deployment. The inherited chunk-size warning remains. This increment has not run a real PostgreSQL/browser journey, and the parent's hosted results are not substituted for new execution.
