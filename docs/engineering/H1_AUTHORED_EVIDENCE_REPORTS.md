# H1 case evidence and question comparison

## Bounded decision and source ownership

This continues OI-004, OI-007, OI-008, OI-009 and OI-010 on the accepted
FastAPI/PostgreSQL and React/Vite/TypeScript stack. It attaches independently
authored fictional evidence to the canonical H1 patient case, records explicitly
human-authored comparisons against a saved source question, and preserves a
readable comparison report. No model, clinical conclusion, professional review,
publisher clearance, network acquisition or external delivery is added.

Base: PR #288 published `f09c21f919d546c6bbcfabdde64df3d00b5a8f07`, local
`ca95507ff67be6df36a1bb0a74c09c4ed3a0ce69`, identical tree
`b2dbd83e4acffd469635638be1f20ee3dbaa5591`.

Reference owner: PR #249 published `af72cd6ad5d4e934aa3168334b1592bfdce35e51`,
local `f69f9a254d6328fa26c425d9306477ccb4c58eb3`, identical tree
`97145fdd491624840719acb682c369ea63741f67`.
Reuse its pure `rights.py` (blob `c242afdb00675bf944fdc00744566f1d66497942`)
and `test_rights_content_types.py` (blob `96c8ca2e737c87cf5e919649c4a741ed4298ac61`).
The existing `parse_synthetic_evidence` is already identical and remains unchanged.
The reference `CaseStore` evidence lifecycle and governed report provide the
behavioral vocabulary, quotation and provenance requirements. Their concrete
SQLite clinical wrappers are not instantiated or represented as H1 adapters.

Evidence is **case owned**, not a shared cross-patient catalog. All evidence
mutations and disclosures hold the existing case-binding lock in the canonical
source-owner transaction. An operator's patient grant cannot mutate another
case's evidence. No parallel patient, case, question or source owner is created.
Question/source identities retain the canonical UUID and composite source anchor;
there are no invented integer aliases for the reference stack.

PR #293 owns `0009_question_followthrough`, independently based on #287. This
slice owns the distinct `0009_question_evidence`, based on
`0008_review_convergence`. Future convergence must preserve both migrations and
explicitly merge their heads. PRs #290, #291, #292, #294 and #279 retain their own
clinical, navigation, recovery and PDF consistency scopes.

Review adds `0010_authored_evidence_origin` after this slice's unchanged published
`0009_question_evidence`. It records append-only command origins for assessments
and reports. An exact retry must match that creating command, not merely another
record with identical content. Populated `0009` history is backfilled only when
each object has exactly one matching command; missing or ambiguous associations
require reconciliation. New report origins retain the inspected packet digest.
Older report origins retain the original full command-intent digest and explicitly
identify that provenance limitation rather than inventing a missing packet digest.
The old text renderer remains versioned for existing report bodies; new report
text includes the actual frozen permission values as well as their digest.

A subsequent live refresh found two newly published owners after the initial
audit: #296 (`09651d35fb2d495330026db78eb82debd936d7e4`) is a pure proposed
provenance bridge without persistence/API/UI. #298 initially published tests-first
metadata search and citation linkage at `9cdb89711228bcffde6476f9001626d645b6128c`;
the final owner refresh found its combined implementation candidate at
`f4750327537a5febf764d25f43873be50ac7265a`, with new combined hosted acceptance
still pending in that PR's receipt. It is based on #293's verified
`e44f225e3ce4953d754ad0e6e1409e22b696a29f`. #298 owns
`/evidence-search`, `/evidence-links` and its
metadata catalog, explicitly leaving literal appraisal/report work separate.
This slice owns case-scoped authored original bytes, human comparisons and reports;
its modules and read/write actions use `authored_evidence` to avoid expanding a
metadata-read grant into quotation access. Its existing parser/domain semantics
remain distinct from metadata catalog search. No #298 catalog is duplicated.
#296's coarse rights set and invented source-version string do not satisfy the
canonical H1 composite source anchor or per-item/per-use rights contract here.
Convergence must retain these distinctions rather than silently coerce identities.

## Persistence and rights semantics

Use append-only tables in `investigation` for evidence versions, withdrawal
receipts, authored assessments, report snapshots, exact command receipts and
their original object bindings. Preserve original UTF-8
bytes, parser fields, SHA-256, physical statement line, content item, normalized
permission map and its digest. Evidence version IDs are `EVIDENCE-` plus 32
uppercase hex characters; assessment IDs use `ASSESSMENT-`, reports `REPORT-`,
withdrawal IDs `WITHDRAWAL-`. The evidence key is the parser's existing identifier.
Version uniqueness and lineage are scoped to patient/case/organization/key.

Imports accept only the existing `OI-SYNTHETIC-EVIDENCE/1` grammar, including
`Rights: original-synthetic`. This label is not legal proof. Every fixture must
be independently authored and fictional. The content item is explicitly one of
`full_text`, `abstract`, `api_output`; permissions are normalized by the shared
rights owner. Storage requires explicit metadata/store and exact-item/store.
No display or redistribution permission follows from a source label.

Version and rights declarations are immutable. A corrected declaration requires
an explicit new evidence version with `Amends: KEY@latest_version`. Duplicate
bytes plus identical content item and normalized permissions recover the original
version. Duplicate bytes with conflicting rights are rejected. A withdrawn family
cannot be silently revived. Withdrawal targets the latest current version, records
a reason and preserves all originals. It prevents display/export of that family,
including historical report content. An amendment makes old assessments stale.

Display requires metadata/store+display and exact-item/store+display on both the
referenced version and current family version, using the *referenced* content
item in both gates. Export additionally requires metadata/redistribute and
exact-item/redistribute on both. A new abstract declaration cannot grant rights
to an earlier full-text quote. Unknown and denied fail closed. This human-only
contract does not require or imply `ml_use`; no model-eligible context is created.

Assessments are immutable human proposals: relation from the shared supports,
contradicts, context, unknown vocabulary; applicability from applicable, limited,
not_applicable, unknown. Reject supports + not_applicable. Rationale is one visible
10–600 character line. Quote is 1–400 characters, occurs exactly once in the
stored statement, and stores its Unicode code-point offset and statement line.
The quote remains literal and is not an inference or a source-authored status.
Assessment provenance includes the exact question/source snapshot/preflight,
evidence version/hash and rights digest. New assessment requires a current question
and evidence version. Reassessment appends a new assessment; it never rewrites
one. For a given question/evidence family, only the latest assessment is current;
prior proposals remain historical. Evidence/source amendments do not create a new
comparison automatically.

Reports store immutable body, body digest, snapshot and snapshot digest, selected
assessment IDs, preparer and time. A new report requires 1–20 distinct current
assessments and the exact inspected packet digest. The deterministic renderer
groups human proposals by supports, contradicts, context and unknown, includes
applicability/rationale, exact source/evidence references, rights declarations,
dates and literal escaped quotations. It states that selection is not an exhaustive
literature search and no clinical appraisal or model execution occurred.
Control/directional text is visibly escaped, following the reference renderer.

Old reports remain immutable after restart/amendment. Freshly reopening a report
checks current authority and current family rights: an obsolete report is explicitly
historical; denied content is withheld while its IDs/digests/preparation time remain
available. A stored hash or old successful response is never an access grant.

## Shared HTTP contract

All routes are under
`/v1/patients/{patient_id}/cases/{case_id}/questions/{question_id}`.
All require operations purpose and separate `patient_read`, `source_read`,
`question_read` and `authored_evidence_read`. New independent actions are
`authored_evidence_import`, `authored_evidence_assess`, `authored_evidence_withdraw`,
`authored_evidence_original_read`, `evidence_report_export`.
Source-only brief and source-review packet contracts keep their existing meaning.

Each write includes `synthetic: true` and an opaque `request_key`. Keys are scoped
to patient/case/operation, with exact normalized intent and actor identity. Exact
retries recover the original ID, including after amendment; changed intent conflicts.
Receipt recovery does not disclose a stale report body or authorize a new write.
Every successful route builds bounded complete JSON bytes inside the transaction,
refreshes the same bearer and every action, appends reference-only audit metadata,
then commits. Encoding, authority, audit or commit failure rolls back the command.

| Method/path | Request additions | Result | Extra action |
|---|---|---|---|
| GET `/evidence` | none | EvidencePacket | none |
| POST `/evidence` | original_text, content_item, permissions | `{evidence_id,version,duplicate}` | authored_evidence_import |
| POST `/evidence/{evidence_id}/withdraw` | reason | `{withdrawal_id,evidence_id,duplicate}` | authored_evidence_withdraw |
| GET `/evidence/{evidence_id}/original` | none | EvidenceOriginal | authored_evidence_original_read |
| POST `/evidence-assessments` | evidence_id, evidence_sha256, rights_sha256, expected_source_snapshot_sha256, expected_preflight_sha256, quote, relation, applicability, rationale | `{assessment_id,question_id,duplicate}` | authored_evidence_assess |
| POST `/evidence-reports` | expected_packet_sha256, assessment_ids | `{report_id,question_id,duplicate}` | evidence_report_export |
| GET `/evidence-reports/{report_id}` | none | EvidenceReport | evidence_report_export |

Strict exact object shapes below are the API/client agreement. Timestamps are
timezone-aware ISO strings, digests lowercase 64 hex, IDs exact uppercase forms.
All collection limits fail closed, never silently truncate: 100 evidence versions
per case, 200 assessments per question, 100 reports per question. Maximum complete
JSON response is 524288 UTF-8 bytes; report body at most 131072 bytes.

**EvidenceVersion** fields:
`evidence_id, evidence_key, version, sha256, statement_line, content_item,
rights_sha256, permissions, state, title, issued_at, statement, created_at`.
State is `current`, `superseded`, `withdrawn`. Title and statement are both strings
or both null; null means current display rights unavailable. The remaining values
identify provenance, not evidence content. Permission maps contain exactly the
shared six item keys and four use keys with allowed/denied/unknown values.

**EvidenceAssessment** fields:
`assessment_id, question_id, evidence_id, evidence_sha256, rights_sha256,
source_snapshot_sha256, preflight_sha256, relation, applicability, quote,
quote_start, rationale, actor_label, created_at, state`.
State is `current_unreviewed`, `reassessment_required`, `content_withheld`.
Quote, quote_start and rationale are all null when content is withheld; otherwise
quote_start is a nonnegative Unicode code-point offset. Relations remain human
labels even when text is withheld. Actor label is unverified fixture identity.

**ReportSummary** fields:
`report_id, question_id, prepared_at, body_sha256, snapshot_sha256, state`.
State is `current_unreviewed`, `historical_reassessment_required`, `content_withheld`.

**EvidencePacket** fields:
`contract, patient_id, case_id, question, source_snapshot_sha256, access_receipt_id,
evidence, assessments, reports, packet_sha256, synthetic, human_review_state,
clinical_approval, model_executed`.
Contract `oi.h1-question-evidence/1`; question is the existing SourceQuestion shape
(possibly stale). Snapshot is the current source-world fingerprint. Arrays use the
above three shapes. Flags: true, `not_performed`, false, false.
Packet digest is canonical JSON SHA-256 of the complete object excluding
`access_receipt_id`, `packet_sha256`, `reports` (report creation itself does not change
evidence context). Canonical JSON sorts object keys, uses literal UTF-8, no whitespace,
and disallows non-finite numbers.

**EvidenceOriginal** fields:
`contract, patient_id, case_id, evidence_id, sha256, original_text,
access_receipt_id, synthetic`.
Contract `oi.h1-evidence-original/1`, synthetic true. Digest must match actual
UTF-8 bytes. Retrieval rechecks current family display rights and source authority.

**ReportSnapshot** fields:
`question, selected_source, comparisons, prepared_at, actor_label`.
Question is the saved current SourceQuestion shape at preparation; selected_source
is the existing SelectedComposerSource shape. Comparisons are exact objects
`{assessment, evidence}`, using the two shapes above as they were prepared (current,
visible), preserving their original values forever. Actor label is not identity proof.
All patient/source/evidence/assessment anchors are cross-validated when reading a
stored snapshot; body and snapshot hashes are reconstructed and checked.

**EvidenceReport** fields:
`contract, patient_id, case_id, question_id, report_id, prepared_at, state,
body, body_sha256, snapshot, snapshot_sha256, access_receipt_id,
synthetic, human_review_state, clinical_approval, model_executed`.
Contract `oi.h1-evidence-report/1`; flags as packet. Body and snapshot both null
when content_withheld, otherwise immutable original string/object. A historical
state is displayed outside the unchanged body. Every download requests this report
again, checks scope, hashes, provenance and rights; it never downloads a cached body.
The #316 continuation below adds the fresh status and access receipt to a download
cover while retaining the original body as an exact, separately hashed section.

## React behavior and acceptance

Extend the existing saved-question panel with an explicit **Inspect evidence**
action and a focused evidence panel. Retain the existing navigation and question
workflow. The panel shows the question, source status, case-owned evidence versions,
readable permitted statements, proposed assessments and immutable report history.
Provide original-file upload with an explicit fictional acknowledgement and declared
content class; visible default permissions apply only to the chosen item and
metadata (store/display/redistribute allowed; ml_use unknown). A compact permission
fieldset permits withheld redistribution and unknown/denied display for meaningful
rights checks. Do not imply that choosing a class proves scientific validity.

An operator selects a current visible evidence version, copies/edits an exact quote,
chooses relation/applicability, and writes rationale. Display existing proposals as
human-authored and unreviewed. Select current assessments for report preparation;
supporting and contradictory evidence must remain distinguishable. Show stale and
withheld history without promoting it to current evidence. Include explicit latest
version withdrawal with a visible reason and preservation notice. Amendments use
the existing file grammar and upload control.

Use the existing RegistrySession bearer, request abort/generation boundaries and
same-patient/case question scope. Keep credentials and drafts in memory only. Clear
evidence/report disclosure on navigation, patient/case/credential change, source
refresh, mutation and failed fresh authorization. Late responses cannot restore it.
An uncertain write retains its exact request body/key and permits exact retry only;
changing/discarding the pending intent is blocked until resolution or disconnect.
Navigation clears disclosure but retains uncertain intent in the same patient scope.

Acceptance: actual PostgreSQL import of independently authored support and
contradiction records; exact source/quote/rights provenance; durable assessment and
report; actual downloaded report bytes; denied/missing actions and content rights;
forged anchors; stale expected packet; source/evidence amendment and withdrawal;
exact retry and conflicting reuse; final authorization/serialization/audit/commit
rollback; concurrent same-case mutation serialization; restart and backup restore;
late browser responses, fresh-download denial and 390 px layout. Retain all baseline
API/client/browser tests. Software results establish no medical or production claim.

## Implementation and verification receipt

Published as draft [#300](https://github.com/OpenxIntelligence/open-intelligence/pull/300).
Initial implementation head `3b3abd11c4a9998a1ec0af50596f132ba0588cb3` corresponds
to local `7ce75e99f3694c05be5ef1699b4a856cb656a4a5`, identical tree
`9327a480af596b3de8c4da282d925a310d3abf4d`. The first checkpoint passed 197 client
tests and the locked build, 250 reference tests, and 60 executable local API
checks; 277 database checks were explicitly skipped locally.

### Observed failures and corrections

The initial [hosted API run](https://github.com/OpenxIntelligence/open-intelligence/actions/runs/41637509292)
ran all 337 methods without skips and reported four failures and one error in five
exact-retry methods. The [hosted browser run](https://github.com/OpenxIntelligence/open-intelligence/actions/runs/41637509369)
passed the inherited World Model, question, source brief, verification-return and
Overview journeys, then failed the new post-commit lost-response recovery check.
The PostgreSQL driver returns rows as lists; two recovery checks compared those
rows to tuples and therefore refused equal values. The correction compares the
actual values while retaining the original failed assertions and retry identities.
The independent reference/UI workflow passed at that checkpoint; it does not
substitute for the failing new PostgreSQL/browser acceptance.

Three independent reviews separately examined backend, client and actual acceptance
harnesses. They found and reproduced:

- Uncertain writes could lose their request key after a refused retry or rechecking
  the same patient. Recovery now retains the exact pending intent until a valid
  receipt or an actual scope reset resolves it.
- Network, JSON or digest failure on a fresh read could retain earlier disclosure.
  All evidence readers now invalidate dependent requests and clear old content.
- Recovering question A while question B was selected could restore A's evidence
  beside B's source brief. Receipt recovery no longer implicitly changes selection.
- Valid field-leading U+FEFF text was rejected by a UTF-8 round-trip check, and
  coercible singleton arrays could pass enum validation and crash rendering.
  Exact Unicode values are preserved and enum values must be actual strings.
- A corrupted command receipt could point to another legitimate same-content
  assessment/report. The follow-up origin migration binds each record to its
  creating command while preserving historical records and renderer semantics.
- The downloadable text included a rights digest but omitted the declaration
  values. New text now includes metadata and exact-item permissions, including
  the explicitly unknown model-use permission.

The client repairs first reproduced eight failures in a 205-test run plus a ninth
focused question-selection regression. After correction, all **206 client tests**
and the locked build passed. An additional harness timing guard waits for the
withdrawal receipt and refreshed rendered state before navigating; response
observation alone did not establish that the client had processed the receipt.

The repaired local API suite discovers **347 tests: 64 pass and 283 PostgreSQL
tests skip**, with no failures or errors. The new database checks cover receipt
redirection, explicit packet binding, populated legacy upgrade, missing or
ambiguous backfill refusal, and rejection of originless writes by the retired
writer. The published 0009 migration remains byte-identical. Independent client
correction review passes its 28 focused checks and 13 additional probes.

Independent backend correction review found no remaining blocking finding at
local `4f34a719a880117bdf84b947a04bdb53590f7058`. Its 15 executable focused tests
passed (three database tests explicitly skipped locally). Independent list-row
recovery/redirection probes and old/new renderer comparisons passed. Acceptance
harness review found no new blocker after the withdrawal settling wait and full
sequence-state restore comparison.

### Repaired runtime verification

Repaired published candidate `e1170ddd69af5169027a35d1996163f959bbb503` corresponds
to local `4f34a719a880117bdf84b947a04bdb53590f7058`, identical tree
`be206c8b61a10d72662ca4d3c7b78fff90e4d8a1`.

The [React workflow](https://github.com/OpenxIntelligence/open-intelligence/actions/runs/41639707349)
passed all 206 client tests with no skips, the production build, dependency gates
and the complete actual PostgreSQL/FastAPI/React/Chromium journey. It preserved
all inherited connected checks and exercised original evidence download, two
human-proposed relations, a lost successful response and exact recovery, report
preparation/download, independent export revocation, actual API restart, amendment,
explicit reassessment, old-report preservation and withdrawal. The 390 px report
and Overview screenshots were inspected.

The [inherited UI workflow](https://github.com/OpenxIntelligence/open-intelligence/actions/runs/41639707324)
passed 250 reference tests, 16 client lineage/race checks, both browser journeys
and the source-first layout/keyboard checks. This workflow uses GitHub's proposed
merge commit `a5ac22dc9ac3188f0d9fd8e3e88b398d829a1a1e`; its tree was checked and
is identical to the repaired runtime tree above. These overlapping reference
checks are not additional distinct capabilities.

Downloaded browser artifact **13231842845**, SHA-256
`c8417d48fe63c42e65d3e87325db00bff1482bac59dd09262f8a273d41120722`, contains
**352 source files**, all byte-matched to the immutable local candidate. Fresh
extraction verified four retained source-only brief downloads, the exact authored
original, all three distinct evidence versions and assessments, and two distinct
downloaded reports (3,859 and 3,860 bytes). Scope, original/rights/body digests,
literal quotation offsets and clinical/model flags were checked. The original
and later report remain separate artifacts. Artifact retention expires on
10 November 2026.

The [API/PostgreSQL workflow](https://github.com/OpenxIntelligence/open-intelligence/actions/runs/41639707343)
passed **347 tests with zero failures, errors or skips**, followed by **250
reference tests**, both retained browser journeys and all four actual Compose
recovery probes. All six new origin/migration checks passed against PostgreSQL,
including populated upgrade and rejection of a retired originless writer. The
original failed exact-retry assertions passed unchanged.

The new recovery probe preserved four evidence versions, three assessments, two
reports, ten exact-command receipts, five creating-command origins and 59 canonical
events. Actual API/database restart preserved original report bodies and hashes.
Actual `pg_dump`/`pg_restore` matched complete rows across thirteen tables and all
four sequence states, including source history and schema revision. The probe
also rejected new stale assessments after source amendment while recovering the
exact earlier command, and withheld historical abstract content after an API-output
amendment lacking abstract permission. It does not claim to have served evidence
HTTP requests from the separately restored database; logical restored records and
sequence equality are the verified boundary.

Downloaded recovery artifact **13232497488**, SHA-256
`6a50a3f528fc8320b32fbdc0e6c8c8163f5e59222f71b91f397cd0fbfa78e354`, was checked
against its JSON receipt, distinct object counts, migration head, restart/restore
flags and explicit clinical/model exclusions.

All three hosted workflows pass on the repaired runtime. The final documentation
commit preserves that runtime and updates this receipt, project state, source
ownership, backlog and completed plan. Its automatic checks and exact published
head are recorded in draft #300. No local database skip or earlier parent gate is
substituted for the named candidate's acceptance. The draft remains unmerged and
undeployed; no professional review, publisher clearance, production authorization
or clinical validity follows from these software results.

### Final-head runner correction

The documentation-only candidate `75067f518341a4b53245b2b515d9bacb43028536`
preserved the passing runtime and passed its 206-test React/browser workflow.
Its legacy UI workflow, still using `ubuntu-latest`, failed before opening the
application in Chrome: the DevTools endpoint did not become available. One
unchanged-job retry reproduced that startup failure. Both attempts used Ubuntu
26.04 runner image `20261101.186.1`; the earlier passing legacy run used
`20261025.179.1`. The [first attempt](https://github.com/OpenxIntelligence/open-intelligence/actions/runs/41641347161/attempts/1)
and [unchanged retry](https://github.com/OpenxIntelligence/open-intelligence/actions/runs/41641347161/attempts/2)
remain recorded.

The exact same legacy browser journey already passes in the H1 API workflow on
its explicit `ubuntu-24.04` runner. Independent review confirmed that comparison
and recommended selecting that existing supported environment for the legacy UI
job. The correction changes only its runner selector; Python 3.13, browser
sandbox/flags, timeouts, steps and assertions remain unchanged. Logs discarded
Chrome's startup stderr, so the precise browser-exit or timing cause on the newer
26.04 image is not established. This does not claim to qualify that image.
Exact-head results for the pinned runner and both H1 gates are recorded in #300.


### Date and timestamp contract follow-up — draft #303

The report contract now requires an actual `YYYY-MM-DD` evidence issue date and a bounded, explicit-timezone timestamp with a literal `T` separator. Python's ISO parser alone accepts arbitrary single-character separators, including line breaks; the former plain issue-date string also admitted invalid calendar dates and extra report lines. The client already rejects those representations. Validation rejects invalid inputs rather than normalizing valid strings, preserving canonical hashes and the original report renderer's byte compatibility. This is an internal/report wire-contract hardening; it does not establish a route bypass of the existing original-evidence parser or clinical authority.

Three added regression methods exercise both renderer versions, every shared report timestamp location, valid leap days, timezone offsets, fractional seconds and unchanged input strings. The existing immutable legacy report checksum assertion remains unchanged. An isolated execution of the original production `aware` function reproduced newline acceptance; thirteen isolated repaired-function probes and Python compilation passed. Local full-suite loading was blocked by absent FastAPI and is not a test pass. Tests-first and final exact-head PostgreSQL/browser results are recorded in [draft #303](https://github.com/OpenxIntelligence/open-intelligence/pull/303). No migration, dependency, renderer format, stored-body rewrite or permission change is included. Related OI-008/OI-009/OI-010.

### Restored HTTP continuation — draft #302

The earlier logical-only recovery boundary above remains the historical result
for #300. [Draft child #302](https://github.com/OpenxIntelligence/open-intelligence/pull/302)
extends the existing `verify_evidence_compose.py` probe against the identical
application and schema. It recreates the actual API against disposable restored
copies, preserving the existing container configuration and credential mount.

The added acceptance covers four separately restored states:

1. Readable originals/report: exact Unicode original text, immutable report body,
   source snapshot and digests, and the original assessment/report retry IDs.
2. Content-class restriction before withdrawal: latest API-output original stays
   readable, while earlier abstract originals/reports remain withheld. This
   isolates rights enforcement from withdrawal.
3. Withdrawn evidence and amended patient source: the latest previously readable
   original is denied, withdrawn packet content is null, historical reports are
   withheld, exact retries recover IDs, and new stale assessments are rejected.
4. Persisted revoked binding: revoke through the restored API, dump that database,
   restore again, then deny reads and exact retries without durable effects.

Each recreated API checks `current_database()` through its existing settings and
engine factory. Positive reads must produce fresh returned access receipts only
in the restored database. Complete original-database rows and sequences remain
unchanged; restored immutable records, earlier events and non-access sequences
remain unchanged during reads/retries. This prevents a successful request to the
original database from being misreported as recovery acceptance.

Independent review identified withdrawal being masked by a prior rights change
and denial-only checks failing to establish the final database target. Both were
addressed in one verification-only follow-up; business-sequence comparison was
also tightened. No application, schema, migration, dependency, UI or permission
change. Local gate sanity accepted the valid comparison and rejected five
false-success mutations plus a mismatched API database target. These checks test
the verification harness; they do not substitute for PostgreSQL/HTTP execution.

Local verification: 250 reference tests passed; 64 API tests executed successfully
and 283 database-dependent cases skipped. Compilation, whitespace and the existing
patient-data boundary guard passed. Docker is unavailable in the local executor.
Hosted acceptance at **`c89b22df38a0ede3fff12ee65adb9c9ef1e347cc`**, tree
`b463dfd844f22869d5e727c7e1f0da346217de08`, completed successfully:

- [API/PostgreSQL run 41653217105](https://github.com/OpenxIntelligence/open-intelligence/actions/runs/41653217105):
  **347 API/database tests**, no failures/errors/skips (369.103 seconds); **250
  reference tests** (10.016 seconds); inherited browser journeys and all four
  Compose verification scripts passed. The evidence script additionally served
  all four restored checkpoints through actual HTTP. Checkout identity was
  explicitly verified in the log.
- [React/browser run 41653217136](https://github.com/OpenxIntelligence/open-intelligence/actions/runs/41653217136):
  **206 client tests**, no failures/skips, production build and actual
  PostgreSQL/FastAPI/built-React browser journey passed.
- Recovery artifact **13239876605**, SHA-256
  `d16510300894238882d8b30360d662cf67a5beab7fc70c973cdc3aaa334bc2e8`,
  was downloaded and checksum-verified. Its `oi.h1-evidence-recovery-acceptance/2`
  receipt confirms original-database preservation, actual target verification,
  exact retry identity, non-access sequence preservation, independently causal
  rights/withdrawal checks and restored revoked-binding denial. Readable,
  rights-only and withdrawn checkpoints produced **6, 3 and 10** fresh access
  events respectively, only in their restored copies. The unchanged original
  retained four evidence versions, three assessments, two reports, ten command
  receipts, five origins, 59 events, thirteen tables and four sequence states.
- Browser artifact **13238851838**, SHA-256
  `4a030fb39556435f0ea75229eabb1e6663a60287c0182e76d308c45609db30b9`,
  was downloaded and checksum-verified. Its recorded commit and **all 353 source
  files** match the exact local committed candidate. No visual redesign occurred.

Both artifacts expire on 10 November 2026; the executable assertions and this
receipt remain in Git. The first pre-review candidate was superseded; final
acceptance belongs only to the revision above. Repeated suites are not additive
clinical cases. The later documentation-only receipt does not alter the tested
script, application, schema or dependencies.

This closes #300's specifically recorded restored-evidence-HTTP verification gap.
It does not complete convergence with the separately owned metadata catalog,
follow-through, clinical domains or PDF/annotation workflows. Production identity,
consent, least-privilege operational recovery, independent clinical evaluation,
merge and deployment remain separate gates. Only independently authored fictional
inputs were used.

## Fresh status in downloaded reports — draft #316

[Draft #316](https://github.com/OpenxIntelligence/open-intelligence/pull/316)
addresses OI-009/OI-010/OI-013 on #307's combined question/evidence/report owner.
The API already projected an amended report as
`historical_reassessment_required`, but the download helper exported only its
immutable preparation. The general historical disclaimer in that body did not
convey that the latest authorized read already required reassessment.

The downloaded plain-text file now begins with the fresh response's current/
unreviewed or historical/reassessment-required state, exact patient/case/question/
report IDs, original preparation time and access receipt. It distinguishes the
original body and snapshot digests from the complete downloaded file. After the
fixed `--- BEGIN PRESERVED REPORT BODY ---` separator, the original body remains
byte-for-byte unchanged, including Unicode and final newline. The recorded body
length is UTF-8 bytes. The cover claims neither a new server timestamp nor a
signature, delivery receipt, continuing grant, scientific appraisal or clinical
approval. Already downloaded files cannot be recalled or updated.

The existing fresh authorized read and current-session object-identity guard
remain intact. Fresh denial, withholding or context change produces no Blob or
cover-only download. There is no API, schema, migration, report renderer,
dependency or grant change. Separate original evidence downloads remain exact
original bytes. This does not implement report-specific professional review.

Tests-first `596f9a808641c9966f9875b04fdc03acf1190525` (local equivalent
`328a0b5b416ffd4376e0e2b5ec5df8cd1dd60956`) produced two intended missing-cover
failures after valid fresh reads; withholding/denial and patient-switch negatives
passed. The initial fixture's mismatched body/summary digest was corrected before
recording these behavioral failures. All **270 client tests**, the TypeScript/
Vite production build and the installed dependency rights gate subsequently
passed locally. No new dependency was selected.

Independent review found an inherited continuity-browser assertion that still
equated the entire downloaded file with the prepared body. The first
[hosted run 41661244447](https://github.com/OpenxIntelligence/open-intelligence/actions/runs/41661244447)
independently failed at that exact assertion after its 270 client tests, build
and dependency gates passed. The repair verifies the cover and original body/
hash separately; it preserves the complete-file immutability check. Review also
requested a separate `download_access_receipt_id` alongside each inspection
receipt. Both findings are repaired in
`db8923e502bcf0e631fb31546f5319155d8026f0`, tree
`fe736251d6602dfbe799c56ac57ce0b95437e167` (local equivalent
`f668d8d70e3528f696e4de13a5106fd4510febac`). Independent follow-up found no
outstanding findings; focused verification accepted the valid Unicode file and
rejected missing cover, changed file/body and incorrect digest.

The existing real Chromium/PostgreSQL/FastAPI journey now downloads the same
report before and after amendment, then a newly prepared replacement. Its
version-2 receipts separately retain inspection and download access receipts,
complete-file hashes and original body hashes. Independent export withdrawal,
evidence withdrawal, API restart, same-question metadata continuity and earlier
file preservation remain part of the journey.

At that exact repaired head,
[hosted run 41661787497](https://github.com/OpenxIntelligence/open-intelligence/actions/runs/41661787497)
passed **270 client tests with zero skips**, the production build, dependency
gates and the complete actual PostgreSQL/FastAPI/built-React Chromium journey.
This change does not claim a newly run full API unit suite; the actual API is
exercised by the connected browser workflow, and the backend implementation is
unchanged from the verified #307 owner.

[Artifact 13243036730](https://github.com/OpenxIntelligence/open-intelligence/actions/runs/41661787497/artifacts/13243036730)
was downloaded and verified: archive SHA-256
`3e6d68e7de55b58d2f6979974727eb0b390c2a28568bbe1cb18ce0abe9426d97`;
recorded commit and all **400 archived source files** match the tested tree.
Independent inspection of the three actual downloaded text files confirmed:

| Download | Complete file bytes | Preserved body bytes | Result |
| --- | ---: | ---: | --- |
| Original report, current/unreviewed | 4,964 | 3,859 | Fresh read receipt and explicit unreviewed status |
| Same report after amendment | 4,977 | 3,859 | Historical/reassessment warning; exact same original body/hash |
| Newly authored replacement | 4,965 | 3,860 | New report identity; current/unreviewed and separate fresh receipt |

Each receipt's complete-file hash and download access receipt match its retained
file; body hashes match the exact suffix. The continuity receipt also keeps file
and body hashes distinct. Original and historical downloads remain unchanged
after withdrawal. The artifact expires on 10 November 2026; executable acceptance
and this receipt remain in Git.

The final evidence-only update also retains #307's four documentation updates at
`c35219dc5eb244874a7df6e9bf00cfbfda18251f`. No tested code changes in that update.
The work remains fictional-only, draft, unmerged and undeployed.

## Reproduce a returned report's literal evidence checks

When an operator returns a completed source brief and a current authored report to verification, the evidence owner reopens the preserved originals and checks the report under the case lock. Verifier `oi.h1-literal-evidence-verifier/1` then hashes each exact quoted range. The check concerns literal correspondence and declared rights at return time. Clinical and scientific appraisal stays with the reviewer.

The original review return, one `investigation.evidence.passage_verified` event per comparison and one `investigation.evidence.passages_verified` summary commit in the same transaction. All use the same return receipt ID. The summary binds the patient, case, question, source version/line, completed run and report digests. Individual records bind the assessment ID, evidence ID/version, original and rights digests, content item, statement line and UTF-8 SHA-256 of the passage. Range indexes are zero-based Unicode code points within the parsed statement, with an exclusive end. The journal retains references and digests only.

To reproduce `verification_sha256`, take the summary metadata, remove `receipt_id` and `verification_sha256`, and add the journal row's `patient_id` as `patient_id`. For each passage in ascending journal event ID order remove those same two metadata fields. Apply the existing canonical JSON hash to `{"inputs": summary, "passages": passages}`. Durable retries reuse the initial return and its original history, including returns created before this verifier existed. A new or repeated return requires the existing current authorization and evidence rights checks.
