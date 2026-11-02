# Source-derived Patient World Model projection — synthetic engineering slice

Status: **Proposed / implemented on a draft branch; not merged or authorized for PHI**  
Tracker: [#116](https://github.com/OpenxIntelligence/open-intelligence/issues/116) (WS-04, patient world model)  
Source owners: existing `CaseStore.state(case_id)`, original source versions, assertions, questions and investigation snapshots  
Contract: `oi.synthetic-world-model/1`  
Local-only endpoint: `GET /api/cases/{CASE-ID}/world-model`

## Product purpose

This provides a narrow, actual API projection of a case's current observations, original document/version/hash/line, specimen identifier, the distinct event/issued/received times, source history, bounded within-specimen disagreement and the review-needed questions/snapshots. It is a starting point for an integrated patient-first workspace. It **does not add a canonical patient master or a source/fact ledger**. It reads exactly one existing `CaseStore.state()` transaction snapshot and returns no cross-case or globally pooled scientific evidence.

## Owner boundaries

1. **Facts**: `source_versions` and `assertions` remain the source authority. The output is explicitly a `source_report_only_unreviewed` projection. A finding is an authored statement, not a clinical diagnosis, negative assay result independently established by OI, or a clinician's decision.
2. **Identity**: `case_id` is a fictional demo identifier. `synthetic_world_model(state, expected_case_id)` denies a mismatched case. Real patient identity, validated source-system identities, consent and clinical authority remain with the corresponding first-party integration owners #85/#51/#53/#95.
3. **Time**: `event_date` (reported event), `issued_at` (document finalization), `received_at` (ingest) and current/superseded status are preserved separately. `as_of_ledger` reports the latest visible ledger receipt, not a historical as-of query or a bitemporal model.
4. **Specimens**: Same finding key is not an identity link. The narrow disagreement check requires the **same known specimen ID and same event date** plus explicitly opposing source-reported `reported` / `negative` states. Unknown specimens are never fused and longitudinal differences are not automatically classified as conflicts.
5. **Amendment**: Current assertions come from current source versions only. Older source refs remain in `history`; case-specific draft/stale snapshot references are surfaced from existing review ledger; no new clinical interpretation is promoted.
6. **Security and content rights**: Only the current loopback-only synthetic demo may serve this endpoint. It is unauthenticated and **must not** process PHI or be exposed as a production route. External evidence, restricted clinical guideline text, patient biographies and unverified model claims are deliberately absent.

## Test acceptance

`PYTHONPATH=src python -m unittest discover -s tests -p 'test_synthetic_world_model.py' -v`

Tests assert actual original fixture references and three time facets, uncertainty versus explicit negative, amendment-version preservation, no cross-specimen grouping, one intentionally conflicting same-specimen report, case isolation, no source writes, current review/stale states, malformed snapshot denial and a loopback HTTP route. All fixtures are independently authored fictional cases.

Run the complete repository Python/HTTP + Chromium source/keyboard checks at the **exact draft branch head** and record the run URL and SHA. This contribution is not complete until CI and independent review; local or hosted synthetic tests do not establish clinical readiness.

## Next workstream integration (still open)

The actual clinical operational workflow in #95, original patient registry, encounter/note, LIS order/accession/QC/release, source adapters, review receiver, and rights-qualified knowledge/Composer #130/#132 must be reconciled under **one signed patient/case/source and authorization contract**. Later PWM extensions must add assay, genome assembly, allele/variant identity, specimen/lesion lineage and as-known-at bitemporal queries from real source metadata; do not infer them from source text or create shadow operational tables.

No new dependencies, migrated database schema, unsupervised AI agents, medical recommendations, PHI, prohibited source, real-patient data or clinical action were added.

## Patient-record interface increment — 2 November 2026

**Stage:** implemented and verified in [draft PR #161](https://github.com/OpenxIntelligence/open-intelligence/pull/161); unmerged and not deployed. This extends the existing projection from #147 (`97f197c3472df785b68cfab8794c388e20c4b798`), with the existing question-lifecycle and cross-case storage corrections from #136/#142. The separately documented #153 authorized World Model/research-review composition remains a distinct backend integration to reconcile; this interface does not replace it or claim its permissions.

### User workflow and ownership

The existing Patient view now reads `GET /api/cases/{case}/world-model` and presents current source findings, their exact source lines, distinct negative/missing/pending/indeterminate/conflicting states, same-known-specimen disagreements, open questions, report review status, and inspectable earlier source versions. Choosing **Investigate question** selects that existing question in the evidence, human-draft and bounded-investigation controls. It does not create another question, run a model, approve a report, or create a new patient/source store.

A read is displayed only if the projection and loaded case state agree on case, synthetic scope, source identities/hashes/metadata, assertion text and anchors, questions/snapshots, and latest ledger event/time. Case changes and refreshes invalidate pending responses and detached controls. A failed or mismatched read clears old content and offers retry. Source-reader line boundaries now follow the parser's `str.splitlines()` semantics while preserving every original character, including Unicode separators.

The integration carries the existing storage corrections: an unreviewed completed, abstained, blocked or failed investigation leaves its question open; a question from another case or an invalid ID is rejected before storing the attempt. Only the existing explicit demo acknowledgment addresses a question. After a source amendment the existing owner marks dependent reports stale and reopens the question. Once a replacement is acknowledged, the patient view separates preserved historical stale versions from current reassessment work.

### Bounded implementation sequence

1. Preserve the #147 API and existing ledger; connect its read-only projection to the existing screen.
2. Carry #136/#142 source-owner fixes and prove their regressions before exposing the handoff.
3. Validate source/case/freshness boundaries and preserve question selection across refreshes.
4. Exercise the native browser journey: original record → question → fictional evidence → explicitly labeled replay → human-authored source-linked report → demo review → amendment → reassessment → restart.
5. Review the resulting patch and exact hosted revision before merging through the accepted workflow.

### Verification record

- Local complete application suite: **249 Python/HTTP tests passed**. The carried-forward lifecycle tests reproduced the old failures before the fixes, then all five passed.
- **66 Node tests passed** (19 patient record, 17 source readers, 15 line diff, 8 text-change properties, 7 investigation freshness). Tests cover response reordering, A→B→A, same-case refresh, cleared callbacks, rejected sources/anchors/case/cutoff, literal text, historical stale status and Unicode line anchors. The investigation-list guard also rejects late pre-amendment results and errors, including a same-case refresh and A→B→A.
- `tests/browser_patient_record.py` uses the existing Chromium/CDP helper, local server and independently authored fixtures. It records synthetic-only screenshots and a structured verification receipt. Local execution stops explicitly because Chromium is not installed; this is **not a local browser pass**. Hosted execution **passed**, as recorded below.
- Existing source/evidence browser, source-dialog concurrency and layout/keyboard journeys remain regression gates. Browser automation is not a full accessibility or usability study.

### Hosted verification and independent review

[Run 41528676636](https://github.com/OpenxIntelligence/open-intelligence/actions/runs/41528676636) **passed** on branch head `f115fb2335897d4d37307abd9aab62dcfdd636d1`. GitHub checked out its PR merge ref `7f9e821245722169b66d8624b9761038eae72146`. The saved source-under-test archive was downloaded and all **170 tracked files matched the locally inspected/tested checkout byte for byte**. The artifact ZIP SHA-256 is `e631360252b76d19c6f99f704b8b16dc16479287e7fb72b8cc84508a0d357429`.

The native patient-record journey, existing source/evidence journey, source-dialog race journey, and layout/keyboard checks all passed. The new journey verified the two-question handoff through evidence refresh, exact source inspection (including Unicode line boundaries), recorded replay remaining unreviewed, explicit simulation review, amended source/reopened question, preserved source bytes and stale report history, acknowledged replacement clearing current reassessment work, delayed case response rejection, mismatched-cutoff retry, 390px layout, and restart persistence. Desktop and narrow screenshots were actually inspected; the structured receipt explicitly records `live_model: false` and `external_evidence_retrieved: false`.

The first hosted run failed because the new test selected an existing fictional Beta marker with the same finding key as the imported Unicode fixture. The corrected test waits for and selects the exact `UNICODE-BETA` source and its original statement. No runtime code was changed to conceal that failure. The rerun completed every browser gate successfully.

Independent scoped review found four concrete defects during integration: historical stale versions counted as active reassessment, model-question selection resetting on refresh, Unicode source-line mismatch, and late model-investigation results reviving pre-amendment content. Each was corrected and regression tested. Final review found no remaining concrete blocking defect within this bounded synthetic scope; it is not a whole-platform or clinical-safety approval.

### Architecture, dependencies and limits

No runtime dependency, schema migration, new clinical API, external data acquisition, licensed guideline content, live-model invocation, identity service, or clinical action is introduced. The new static asset is served under the existing same-origin CSP. The server remains the unauthenticated loopback-only synthetic prototype. Text fixtures are explicitly structured source statements; PDF/OCR and general clinical extraction are absent. Replay is a recorded demonstration and never evidence that a live AI system completed the investigation.

The complete MVP still needs the accepted account/consent boundary, general original-byte document ingestion and extraction review, rights-qualified live evidence, governed model execution, and integration with the operational patient/clinical source owners. Preserve #95/#132/#140/#149/#153 and the PostgreSQL adapter work #145/#148 when reconciling those seams. Keep the historical-artifact audit #122 and the additional data-acquisition cleanup #137 visible; this UI patch does not claim to close them.

### Research implications already covered by existing registers

The technology review extends the existing #127/#134/#135 catalog; it does not select new package versions. A small born-digital PDF adapter is the next document-ingestion comparison, with OCR as an explicit separate state. Original bytes, immutable versions, page/line anchors, extraction receipts, warnings and human correction must share the current source contract. The verified root license alone does not clear parser extras, native OCR libraries, language data, model weights, or deployment images.

The knowledge review corroborates the existing #140 rights audit: distinguish metadata, abstracts, full text and API-curated content. NCCN remains a licensing/technical-access gate, and a public or third-party MCP claim does not establish an authorized connector. The next narrower source-rights change is explicit content-class permission in the existing knowledge-context owner, rather than treating every text item as full text.
