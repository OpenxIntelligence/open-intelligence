# H1 — saved-question source brief and authorized download

**Status:** Draft integration candidate, independently fictional inputs only.
This is a readable source-context export for an existing saved question. It
does not execute a model, retrieve biomedical evidence, submit human review,
approve a clinical conclusion or complete the evidence-investigation MVP.

## Product purpose and ownership

The React Investigations workspace already connects a canonical patient and
case to source-reported observations, an exact-source Composer preflight and
a durable question. This package makes that saved question and its source
context readable and downloadable without creating another patient, source,
question, report or review store.

The implementation base is [#244](https://github.com/OpenxIntelligence/open-intelligence/pull/244)
at `3b6c466950852c20f99d57a70dd196fd2862571a`, above canonical source/UI
convergence [#234](https://github.com/OpenxIntelligence/open-intelligence/pull/234)
at `65eafebd9fda221dc79789619133c78c6d01dc60`. Both exact-base H1 gates passed:
[API/PostgreSQL](https://github.com/OpenxIntelligence/open-intelligence/actions/runs/41570757438)
and [built React/browser](https://github.com/OpenxIntelligence/open-intelligence/actions/runs/41570757419).
All 275 source files in the base's verification archive matched its Git tree.
Those results establish the base, not this candidate.

The readable-text and fresh-download concepts are selectively adapted from
[#241](https://github.com/OpenxIntelligence/open-intelligence/pull/241) at
`5c3653cadb797901e65bb0fabf7660fc3b2b73d1`. Its competing World Model reader,
whole frontend, source aliases and two-read preparation sequence are not
imported. `PostgresSourceQuestions`, `PostgresSourceVersions` and their existing
transaction/event owner remain authoritative. No dependency or migration is
added. The fingerprint remains `oi.pg-source-world-model/1.snapshot_fingerprint`.

## API contract

`POST /v1/patients/{patient_id}/cases/{case_id}/questions/{question_id}/brief`
has operation ID `prepare_source_question_brief_v2`.

The exact request is:

```json
{
  "synthetic": true,
  "source_snapshot_contract": "oi.pg-source-world-model/1",
  "expected_source_snapshot_sha256": "<64 lowercase hexadecimal characters>",
  "expected_preflight_sha256": "<64 lowercase hexadecimal characters>"
}
```

Question text, quotations, patient projections, clinical status and source
metadata are reconstructed from their existing server-side owners. Caller
substitutes are not accepted. Independent exact-patient grants are required
for `patient_read`, `question_read`, `source_read` and `source_brief_export`,
under the same actor, organization and `operations` purpose. A Composer grant
is not required to read and export a previously saved question.

The response declares `oi.synthetic-source-brief/2` and includes the canonical
patient/case, snapshot contract/hash, fresh `access_receipt_id`, complete current
question state, exact selected source anchor, preparation time, literal text,
`text/plain;charset=utf-8`, and SHA-256 of the UTF-8 text. The three flags
`clinical_approval`, `model_executed` and `biomedical_evidence_included` are
always false. Unknown fields and incompatible nested contracts are rejected.

Preparation proceeds inside the existing source-owner transaction:

1. Resolve the saved question under the exact patient, case and organization.
2. Lock and validate the active canonical patient/case binding, immutable source
   bytes, version lineage and literal source-reported assertions.
3. Require the question's canonical fingerprint contract and current source
   ID, hash, version and line. Recompute the existing Composer preflight using
   the saved question text. Require both stored and requested preflight hashes
   and the requested current snapshot to match.
4. Render and validate the complete typed response under those same locks.
   Check the actual serialized JSON envelope against 65,536 UTF-8 bytes. An
   oversized response is refused intact; evidence is never truncated.
5. Reauthenticate the same request credential and recheck actor, organization,
   purpose and every independent action. Append the source-access receipt and
   commit before returning the prepared response.

Missing or unauthorized scope is withheld. Stale, legacy or mismatched source
context requires reassessment with HTTP 409. Preparation, typed validation or
receipt failure rolls back the read receipt and withholds the brief. Preparing
a brief does not modify the saved question or introduce a clinical-review
transition.

The access receipt records authorized preparation, not proof that a network
client received the bytes. The external fixture authority can change after
the last check; this is not a distributed revocation transaction. A downloaded
copy cannot later be recalled by this application.

## Connected user experience

The existing Investigations question history offers preparation only for a
current, canonical saved question. The preview puts the question, exact source
statement and source-reported uncertainty ahead of technical identifiers.
Historical source versions remain explicitly distinct from current statements.
Hashes and preparation details are inspectable without becoming a new workflow.

Download always sends a new authorized request. The client validates the newly
returned contract, saved-question identity, source anchor and text hash before
creating the file. It does not download the earlier preview from a cache.
Patient, case, credential, source or question-context changes invalidate pending
brief work, including delayed responses and asynchronous hash verification.
Denied or obsolete requests produce no download.

After a source amendment, the original question remains in durable history
with `source_reassessment_required`. The old fingerprint cannot prepare a new
brief. The user refreshes source context and deliberately saves a new question
after reassessment. Earlier source bytes and question fields are preserved.

## Acceptance and verification record

The new tests first reproduced missing behavior: the new API route returned
404 instead of its required authentication refusal; ten new client cases failed
on the absent preparation workflow while the 21 existing source-question cases
passed. This was an observed implementation failure, not a dependency/setup
failure.

Pre-publication local execution: **49 API tests passed and 163 PostgreSQL cases
were explicitly skipped** (212 discovered). The 13 new PostgreSQL acceptance
cases are included among those skips; none is claimed as locally validated.
All **85 client tests passed**, including 11 new brief cases, executing the
actual TypeScript with Node 24's built-in type transform and a temporary source
resolver. This does not replace `tsc`, Vite or the real browser gate. The pinned
Vite/TypeScript install was unavailable from the local offline cache. The
static CI data-boundary guard and browser-helper syntax check passed.

Independent review prompted actual JSON-byte preparation before the final
authority check and receipt, with new serializer-failure and wire-size rollback
cases. A client regression reproduced a deadline during digest verification
that left preparation loading; context and deadline checks now produce a bounded
error while continuing to discard obsolete responses. The browser's unexecuted
denial expectation was also aligned with the established opaque HTTP 404
authorization contract before publication; its no-download assertions remain.

The candidate must establish:

- Actual PostgreSQL source → preflight → saved question → readable brief, with
  stable content identity and a new authorized read receipt for each preparation.
- Independent export permission, purpose and patient/case/organization isolation;
  final credential/grant changes during rendering must withhold the response.
- Source amendment denial, unchanged earlier question/source history, explicit
  new-question preparation and persistence after reopening the store.
- Literal Unicode, dates, uncertainty and conflicting source labels; exact
  text digest; malformed envelopes and oversized complete responses refused.
- DTO/render/event failures leave no false successful-access receipt; source
  locks remain held through response preparation.
- Client contract/anchor/digest checks and response/digest race invalidation.
- Built React over the real API/PostgreSQL: prepare, read, download and compare
  actual file bytes, revoke export, amend source, retain history and reassess.

Focused commands (from the repository root):

```sh
PYTHONPATH=apps/api/src:src python -m unittest discover -s apps/api/tests -p 'test_question_source_brief*.py' -v
PYTHONPATH=apps/api/src:src python -m unittest discover -s apps/api/tests -v
python tools/audit_ci_data_boundaries.py
```

The database suite requires the existing explicit test flag and disposable
`oi_api_test_*` database URLs. Local skips are reported as skips. The inherited
H1 API gate requires zero database skips and also retains the actual container,
restart and backup/restore acceptance. The H1 web gate runs the locked install,
rights checks, TypeScript compilation, client tests, Vite build and the actual
PostgreSQL/API/Chromium journey. Inspect its source-under-test artifact against
the exact candidate Git tree; parent CI does not validate a new patch.

Final counts, run links, reviewed screenshots and remaining failures belong in
the candidate PR and the existing engineering tracker. No successful final CI
result is asserted by this pre-verification implementation record.

## Requirements and next dependency

This package advances OI-007 (durable questions), OI-009 (reassessment), OI-010
(connected export) and OI-013 (authorization). OI-008's evidence-linked scientific
investigation remains incomplete in H1. The API is still a synthetic operator
fixture environment, without production accounts, patient consent or verified
professional authority.

The next contract to reconcile is the existing rights-aware evidence and human
review owner. A source brief cannot substitute for either. Reference report
work already exists in #235/#249; future H1 transport must preserve its source
provenance and independent rights without copying a second review ledger.
Question review #245 also needs canonical fingerprint/migration reconciliation
and final authority refresh before adoption. Keep all branches in their review
workflow; this package does not merge or deploy them.

Only independently authored fictional records are used. No Sid medical data,
real-patient-derived fixture, external publication, model weight or licensed
guideline is acquired by this workflow. The candidate's offline data guard is
separate from still-open repository-wide historical data/workflow cleanup.

## Connected authored-question integration (2 November ET / 3 November 2026 UTC)

This isolated candidate extends #264 at `e042f753eca85cca97e08fdbb3e07ea8263aae69`
with #266's exact original-source quotation packet
(`f793e1e53949b39ee4560344e9d28ca4eac8e12d`) and #268's custom-question editor
(`503e1b89deecf11403dadcf3d8468a90d93abd33`). Three-way reconciliation uses their
shared #244 source/question owner at `3b6c466950852c20f99d57a70dd196fd2862571a`.
The old #216/#241 World Model is not imported. All original branches stay intact.

A user can now deliberately author one source-linked question, prepare exact
source context, save through the existing durable question API, inspect its
literal current source quotation, and request a freshly authorized text download
in the same React workspace. The independent `review_packet_read` and
`source_brief_export` grants do not imply each other. These are source-context
operations, not biomedical evidence appraisal or professional review.

### Convergence defect and repair

A naïve union of the siblings left two independent preview selections: a late
quotation for question A could reappear beside question B's brief, or a late
brief for A could become a download after switching to B's quote. Three new
client assertions reproduced this on the combined tree. A single in-memory
saved-question selection now invalidates both pending readers before switching;
completed previews for the same question can coexist. Navigation clears both
previews while retaining the original same-patient unsaved question draft.
No new server record, identity, permission or persistence owner was created.

### Observed local checks, before hosted acceptance

- Test-first on unchanged #264: donor tests had 13 expected missing-method
  failures, and all six new convergence tests failed. After importing the
  owners, three convergence assertions exposed the mixed-question race.
- After the repair, **104 client tests passed**, no skips/failures. Local
  compilation uses globally installed TypeScript 5.8.3 and Node 22.16.0;
  the locked TypeScript 5.9.3/React/Vite build still requires hosted acceptance.
- **245 inherited reference tests passed** across 30 isolated test-module
  subprocesses. A preceding one-process run exceeded the local 120-second
  invocation deadline and is not counted as a full pass.
- API discovery: **256 executions; 48 passed, 207 explicitly skipped for absent
  PostgreSQL, one environment error because pg8000 is unavailable**. No local
  PostgreSQL/API full-suite or browser pass is claimed.
- Python compilation, current static CI patient-data-download guard and Git
  whitespace checks passed. The guard is not an exhaustive historical-data audit.
- The source/question/brief server owners, all migrations, dependency locks and
  both existing CI workflow files remain byte-identical to #264. #266's added
  focused workflow step is unnecessary here: the inherited full API discovery
  executes the packet tests and the web journey exercises the actual endpoint.
  No tests, fixture boundaries, permission assertions or inherited gates were removed.

The actual browser journey now checks the literal custom third question through
canonical persistence, current source inspection, exact downloaded UTF-8 bytes,
independent packet/export revocation, historical quote withholding, original-file
preservation and explicit saved-question selection. Controlled delayed-response
races are client tests, not falsely attributed to that browser journey.

### Required review and uncompleted boundaries

Exact-head hosted API/PG16, locked build and Chromium checks are **pending at
source publication**. Their results must be recorded separately; parent greens
are not this candidate's acceptance. Inline implementation review is complete;
there is no fresh-context reviewer tool in the authoring session, so independent
source-owner/security review remains required before merge.

The packet transport retains #266's typed-response preparation contract; unlike
the brief, it does not establish a test of actual JSON serialization rollback
inside the source transaction. #265 source-intake/received-receipt final-authority
repairs, #262/#267 nonterminal return workflow, #271 header presentation and
image-custody migration work remain separate and must be reconciled explicitly.
No production identity, consent, professional review, live model, licensed
scientific content, clinical validity, deployment or real-patient authorization
is supplied. Hashes are content identifiers, not signatures; access receipts are
not delivery proof and downloaded files cannot be recalled. Keep draft/unmerged.
