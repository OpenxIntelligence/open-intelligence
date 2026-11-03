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
provenance bridge without persistence/API/UI, and #298
(`9cdb89711228bcffde6476f9001626d645b6128c`) is tests-first metadata search and
citation linkage on #293. #298 owns `/evidence-search`, `/evidence-links` and its
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

Final exact-head PostgreSQL/browser/recovery acceptance and independent correction
review remain pending at this checkpoint. The PR receipt records the final tested
commit, actual gate outcomes, artifact hashes and any further correction. No local
database skip or earlier passing parent gate is represented as that final result.
