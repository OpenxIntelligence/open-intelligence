# H1 question evidence and patient follow-through convergence

**Status:** implemented and verified at the exact runtime below; draft #307, unmerged and undeployed.
**Scope:** independently authored fictional engineering inputs only.
**Product job:** keep one saved patient question, its citation discovery, separately
authored comparisons/reports and follow-up work in the same governed application.
This is an integration of existing owners, not a new patient or evidence ledger.

## Source ownership and current truth

The live audit on 3 November 2026 found `main` at
`24519839aa8ac1ea3aff88a956349ba72798a72a`. The owners below remained draft and
unmerged. At initial inspection, the existing Notion/Drive progress records stopped at
#298, so their proposed next passage/report implementation was already overtaken
by #300. A fresh read before publication found the later #302 restored-HTTP
receipt; this integration retains that contribution and extends its same-question
metadata/task coverage. Accepted product,
rights, source, identity and clinical-authority constraints remain applicable.

| Input | Pinned commit | Responsibility retained |
|---|---|---|
| #298 (base, including #293) | `89f98824610e23a26d2904a845ed1d930207bd76` | Canonical questions, metadata discovery/citation links and durable follow-through |
| #300 (including #288) | `818c67fcb742941fe1588c4ee130ce07e15a814d` | Patient Overview, authored original evidence, literal human comparisons and preserved reports |
| #302 | `1041b5db00f231a5ede6373a398ea3b9c765d1d7` | Actual HTTP against restored authored-evidence databases; preserves the evidence-only follow-up to tested runtime `c89b22df38a0ede3fff12ee65adb9c9ef1e347cc` |
| #303 | `5400be11f07c5efc4b4b2f60422a279bcb5faeb6` | Evidence/report date and timestamp wire-format correction |
| #304 | `6532e394411f66272c88bce63002dcd40ffbcd37` | Validate and encode original-source disclosure inside the final authority/receipt transaction |

The common patient/source/question owner is #287 at
`247705700080052705817fee9e8f7b54afa8ffaa`. The source, saved-question and source
preflight implementations are identical between the two main input branches.
The newer #304 correction deliberately extends the original-source read boundary
without replacing its owner, schema, grant or receipt semantics.
No original PR is merged, closed or rewritten by this integration.

## Integration contract

- Preserve both published `0009`/`0010` migration lineages byte for byte. Add one
  DDL-free `0011_evidence_convergence` with parents `0010_question_evidence` and
  `0010_authored_evidence_origin`. The application must require that exact single
  head. Test populated upgrades from each old head rather than stamping them.
- Register both metadata and authored-content routes with distinct names. Keep
  follow-through, metadata read/link, authored content read/import/assessment and
  report export grants independent. Preserve their original request-size limits.
- Keep metadata citation identifiers distinct from authored evidence/assessment/
  report identifiers. A citation link neither imports content nor changes content
  rights, report provenance, claim support or human review state.
- Compose both interfaces on the existing canonical question. Distinguish their
  labels, selectors and browser helpers. Preserve each uncertain write's original
  request bytes/key and independent recovery across permitted same-case refreshes.
- Keep source amendment, evidence amendment/withdrawal and access revocation
  distinct. Old report bytes remain historical; current rights still govern
  disclosure. Metadata cannot restore a withheld original or report.
- Retain both actual browser journeys and both evidence recovery probes. The
  metadata/task restore proof and authored-report restore proof cover different
  tables and permissions; neither alone proves complete combined recovery.

## Rights, safety and environment boundary

No dependency, model, content source, asset or hosted service is introduced.
The original locked API/web dependency inventories and notices remain the
selection boundary; their automated checks are not whole-product legal approval.
No project distribution license is changed. The complete platform ambition,
no-Next.js/no-vector H1 constraints and fictional-data restriction remain intact.

The inherited current-workflow patient-data entrypoint scan and its nine offline
regressions passed at the #298 base. This is a bounded static check, not an
exhaustive egress, credential or privacy audit. No identifiable patient records
were acquired or used. Local PostgreSQL and browser capability are not assumed;
actual database and rendered-application acceptance runs on the existing hosted
disposable PostgreSQL/Chromium workflow.

## Tests-first evidence

Tests-only commit `bd3f25846951b6614e5694d8ccdc27826675a6db` adds a combined API/
migration contract and same-question client/composition regressions.

- The two local API contract methods fail for the expected missing authored
  routes and absence of the merged migration head; no import/setup error is
  counted as behavioral evidence.
- [React run 41655157461](https://github.com/OpenxIntelligence/open-intelligence/actions/runs/41655157461)
  compiled the existing client and executed 223 tests: 219 inherited passes,
  four intended integration failures, zero skips. Its browser step did not run
  after the expected client-test failure.
- [API/PostgreSQL run 41655157685](https://github.com/OpenxIntelligence/open-intelligence/actions/runs/41655157685)
  ran 357 methods: all 354 inherited methods passed, while the three new methods
  produced seven expected failure assertions for missing routes/migration
  convergence. There were no errors/skips. Later browser/recovery steps were
  skipped after this intentional suite failure.
- Independent review also reproduced noncanonical timezone offset minutes accepted
  by Python's parser after the #303 fix. One new renderer regression failed in 32
  subcases before bounding offset hours/minutes. All 16 pure contract methods then
  passed, including unchanged legacy report hashes and valid timestamp bytes.
  This is a focused extension of #303, not normalization of stored timestamps.
- The final combined candidate is independently verified below. Donor success is
  not substituted for a combined-head result. #303's first API attempt passed its
  database/reference suites but failed inherited Chrome startup; its unchanged
  rerun subsequently passed. That failure remains part of the donor record.

Independent client review reproduced protected uncertain-write payload retention
after common authority denial. Four case/source/question/binding-removal
regressions and two same-patient 403/404 regressions failed before the bounded
reset corrections. The transient 503 case still retains exact recovery intent
without authorizing a retry before renewed access. No unauthorized server write
was demonstrated. The corrected local Node runtime suite passes 258 non-render
tests; it uses Node's type stripping and is not a TypeScript/React build claim.
All 287 reference tests also pass locally. The subsequent hosted acceptance below
provides the actual combined database/browser result.

## Published code and browser verification

The combined runtime is `477f24826a8a102c7437c993d69877c1f250b951`, tree
`cd8d909ad2844e7fbd37ae30a9a10b9123374666`, in
[draft PR #307](https://github.com/OpenxIntelligence/open-intelligence/pull/307).

[React/browser run 41658525265](https://github.com/OpenxIntelligence/open-intelligence/actions/runs/41658525265)
checks out that exact feature commit. It passed **266 client tests, zero skips**,
TypeScript checking, the production Vite build and the actual React/FastAPI/
PostgreSQL 16 journey. Both original evidence journeys, source custody, questions,
review returns, Overview, follow-through and cross-case clearing remain present.

The new browser receipt records the same canonical patient, case, question,
original source snapshot and preflight for a saved fictional citation and an
immutable authored comparison report. Independent metadata-read and report-export
denials returned 404; denied export created no Blob and did not change an earlier
download. Metadata does not authorize content, and a report does not appraise a
catalog entry. This browser callback does **not** establish a task on that same
question; that belongs to the combined API/recovery acceptance.

Downloaded browser artifact **13241475582** was verified against archive SHA-256
`abe9604cb4adabfd542d3c9a7590adffb95ed5076fc4f24d83636a79264f0053`.
All **398 tracked source files** in its source archive match the published commit
byte for byte. Its actual original evidence download is 301 bytes, and its two
report downloads are 3,859 and 3,860 bytes. The files' SHA-256 values match their
respective stored receipts, including unchanged historical report bytes and
literal Unicode quotation anchors. The archived receipt explicitly records
`synthetic: true`, `model_executed: false` and `clinical_approval: false`.

Desktop and 390 px screenshots were visually inspected. No blocking overlap or
horizontal overflow was observed in the inspected captures. The narrow report
uses nested vertical scrolling; those captures do not establish a complete
accessibility or user study. Narrow-browser verification introduces no mobile-app
commitment. Artifacts expire on **10 November 2026**; this receipt and the pinned
source/tests retain the durable engineering evidence.

[Inherited UI run 41658525058](https://github.com/OpenxIntelligence/open-intelligence/actions/runs/41658525058)
passed **287 reference Python/HTTP tests**, **16 Node tests** and the original
browser/layout/race journeys. Its actual checkout is temporary PR merge
`5510bb874c323cb7177db7f14620c2725ef2b361`, whose Git tree was independently verified
to equal `cd8d909ad2844e7fbd37ae30a9a10b9123374666`. It is not misreported as a direct
feature-head checkout.

The retained frontend dependency inventory has no scanner errors and records
exact installed package notices. Its scope remains local fictional development;
`commercial_release_cleared` and `native_object_linkage_reviewed` are false. The
two uninstalled optional platform packages remain explicitly uninspected. This
is a bounded inherited dependency gate, not a newly cleared production stack.

## Actual PostgreSQL and complete recovery acceptance

[API/PostgreSQL run 41658525044](https://github.com/OpenxIntelligence/open-intelligence/actions/runs/41658525044),
job **125995235121**, attempt 1, completed successfully on the exact published
runtime `477f24826a8a102c7437c993d69877c1f250b951`:

- **414 API/PostgreSQL tests passed, zero skips**, in 466.419 seconds. Both
  populated old evidence heads upgrade through the actual migrations while
  preserving complete prior rows, sequences, report bytes and exact retries.
  A genuine two-head state remains unready until the explicit merge.
- **287 reference tests passed** in 12.186 seconds; inherited browser journeys
  also passed. These are repeated regression checks, not independent clinical
  cases or additional patient outcomes.
- **All five recovery probes passed:** patient registry, original sources,
  canonical review returns, follow-through with metadata, and authored evidence
  with the combined same-question citation/report/task extension.
- No timeout or deadlock occurred. A longer-than-base unit step was inspected;
  no code, timeout or assertion was weakened in response.

Downloaded recovery artifact **13240724729** matches ZIP SHA-256
`8fc0c6b6e5baff42e2a821c40ac82e39efcc39909fe01170ac352d04ff1cd51c`.
Its `oi.h1-evidence-recovery-acceptance/3` receipt records the exact merged schema,
**18 tables and four sequence states**, with one patient, one canonical question,
two source versions, four evidence versions, three assessments, two immutable
reports, one metadata citation and one follow-through task. The record also
retains their exact identifiers and report hashes.

Actual HTTP is served against four independently restored checkpoints: readable
originals/report; content-class restriction before withdrawal; withdrawn evidence
plus amended patient source; and a revoked binding backed up from a recovered
copy and restored again. `current_database()` verifies the serving target. The
same citation, report and task survive restart/restore on their canonical
question. Original report/retry identities remain intact; open work requires
recheck after source amendment. Content withholding neither grants nor revokes
independent metadata access.

The receipt records **11 / 8 / 15** fresh access events in the readable,
rights-restricted and withheld restored copies. The added citation read requires
exactly one correctly scoped metadata-read event alongside source-read receipts;
new business writes, changed business sequences, unexpected audit events and
mutations to the original database remain rejected. A subsequently restored
revoked binding denies originals, reports, citation/task reads and exact retries
without durable effects. Both `clinical_approval` and `model_executed` are false.

## Current-truth and next integration

The final live branch recheck still found main at
`24519839aa8ac1ea3aff88a956349ba72798a72a`; #307 is an open draft based on #298 and
has not changed main. This cycle deeply inspected the selected API/web owners,
published migrations, affected authorization boundaries, tests, workflows and
artifact source. It is not a complete audit of every open branch or every
technology category. No new patient-journey case research, publisher license,
model evaluation or commercial technology clearance is claimed in this cycle.

The next integration task is to reconcile the existing connected source-reading
owners #305/#308/#309/#310 with this same canonical question/evidence path, after
checking their then-current heads and conflicts. Preserve their ownership rather
than recreating their UI. Separately qualify one real biomedical connector and
its allowed operations before replacing fictional catalog retrieval. Production
identity/delegation, clinical/PDF/annotation parity and professional review
remain distinct backlog items; #306's fictional grant editor does not close
production identity. Existing OI-004/007/008/009/010/013 remain open.

## Acceptance and remaining boundary

The combined candidate passed the bounded one-patient/source/question scenario
through metadata search/link, independently imported authored originals, literal
comparison, immutable reports, follow-through, source amendment, historical
reopening, independent permission denial and exact retry. Populated upgrade paths,
actual restart/restored HTTP, current rights, case-switch clearing and both
browser paths also passed. These results apply to the pinned runtime and stated
fictional contracts; later source changes require their own relevant acceptance.

This remains deterministic, human-authored software verification. It does not
establish live biomedical retrieval, model execution, scientific applicability,
professional signoff, production accounts/consent, full clinical/PDF/annotation
parity, real-patient readiness or deployment. An explicit catalog-to-passage link
would require its own provenance and rights contract; this increment does not
invent that relationship.
