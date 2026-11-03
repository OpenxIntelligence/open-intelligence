# Implementation slice 01 — source and investigation ledger

## PDF selection correction convergence — 2 November 2026 (America/New_York)

The current follow-on combines #190's versioned passage corrections with #215's
PDF intake, Patient World Model and question/report workflow, based on exact
#215 head `3be1106b5cd34523c4746e2df6f123048beb5659`.
Source bytes, source version and frozen extraction remain unchanged when a
manual selection changes. Current patient understanding uses the new revision;
older reports retain the revision and page anchors they captured. A correction
invalidates dependent work and reopens its question. Unreviewed model attempts
and manually transcribed numeric measurements retain #189's existing safeguards.

Implementation is present. Local checks passed all 146 JavaScript cases and
466 of 467 Python tests; an inherited PDF deadline failure passed alone on rerun.
Hosted full regression and browser verification are pending. See [the maintained revision contract](engineering/ANNOTATION_REVISIONS.md).
This is the synthetic behavioral reference, not a completed authenticated H1
migration, full MVP, clinical approval or deployment. Earlier checkpoints below
retain their original scope; their statements about absent annotation editing
are superseded by this follow-on.

## Source intake to patient record integration — 3 November 2026 UTC

Implemented and verified in [draft PR #215](https://github.com/OpenxIntelligence/open-intelligence/pull/215),
based on #189 at `ed20a68664289c8e539db34d645aa1d2f0f7a0e5` and selectively
reusing #161's read-only projection/patient-record view. Manual passage origin,
review hash, original/extraction identity and physical PDF page anchors now
survive the Patient World Model and its source/question handoffs. Wrong-case
state, incomplete provenance and omitted/duplicated disagreement groups fail
closed. The existing source, evidence, Composer v2 and human review owners remain.

Runtime head `284b9ac1be1e27ccc4863eaf60dfa7432e8d9d46` passed
[exact-head integration 41562716040](https://github.com/OpenxIntelligence/open-intelligence/actions/runs/41562716040)
and [UI 41562716468](https://github.com/OpenxIntelligence/open-intelligence/actions/runs/41562716468):
**420 Python/HTTP, 123 JavaScript, 80 offline checks with 18 optional skips,
all 5 integration Chromium journeys and all 4 UI journeys**. The PDF journey
includes evidence comparison, labeled recorded replay, explicit human report,
source amendment, real server restart and replacement review with preserved
stale history. Four HTTP/provider-boundary tests additionally check constructed
prompts and permission revocation, without a live model call.

The initial UI run caught a real Unicode source-highlight mismatch; the original
#161 renderer was restored with two red-to-green tests and the unchanged browser
assertion passed. All 223 archived source files matched; artifact checksums and
desktop/narrow screenshots were inspected. Five inherited SQLite resource warnings
remain in the Python 3.13 UI log. Full receipt and limits are in
[the maintained projection record](engineering/SYNTHETIC_WORLD_MODEL_PROJECTION.md).

No new dependency, migration or ledger. Synthetic-only, unauthenticated loopback
reference; draft/unmerged, not deployed or clinically validated. The separate
#175 authorized report library and accepted H1 FastAPI/PostgreSQL/React migration
remain open integration work. #190's text annotation revisions are not PDF
revision support. This increment does not claim completion of the whole MVP.

## Bounded PDF intake checkpoint — 3 November 2026 UTC

This unmerged extension starts from reviewed text intake PR #173, implementation
`fe8a6368245bb52944e6ebc7f3e6f5b43daf69d0`, and incorporates its documentation-only
follow-up `243bfec0fb36121868714dd36c6dd591243114da` as the branch parent. It adds a constrained born-digital
PDF adapter to the existing source owner, APIs, manual-review UI, Composer and
report path. Original bytes remain in `source_versions`; the source-owned
`source_text_renditions` child stores frozen per-page text, global extraction
lines, extractor/configuration provenance and hashes in the same transaction.
Preview and save bind both original and extraction identity. Reads and exports
never rerun the parser. The existing amendment transaction preserves earlier
originals and invalidates dependent work. Manual statuses remain explicit.

The inherited model-attempt lifecycle defect is corrected: generating or
abstaining from an unreviewed investigation does not address its question.
Explicit demo review remains a separate state transition.

PDF support uses the hash-pinned BSD-3-Clause pypdf 6.21.4 wheel, with its exact
notice retained and no optional extras. Extraction is bounded to 64 KiB input,
20 pages, 512 lines, 64 KiB extracted text, one concurrent worker, 5 CPU seconds,
10 elapsed seconds and 512 MiB address space. These are prototype limits, not
capacity benchmarks or production security certification. No OCR, automated
clinical interpretation, post-save annotation correction, real patient data,
trusted professional authority or clinical deployment is introduced.

Verification is recorded in the maintained [intake contract](engineering/DOCUMENT_INTAKE.md).
Combined local verification passed: **398 Python/domain/HTTP tests** in 112.609s,
**64 JavaScript tests**, compilation/syntax, the no-patient-data workflow guard,
and **80 offline research checks with 18 optional HDF5 checks skipped**.
The clean environment used Python 3.12.14 and pypdf 6.21.4. The 398 include
17 extractor, 12 PDF store, 8 PDF HTTP and 9 lifecycle tests.

**Hosted acceptance passed for draft [PR #189](https://github.com/OpenxIntelligence/open-intelligence/pull/189)**
at `afe89d390f665713acfca5cca58aae9d285ee1bb`:
[exact-head run 41553904095](https://github.com/OpenxIntelligence/open-intelligence/actions/runs/41553904095)
passed all 398 Python/HTTP, 64 JavaScript, 80 offline checks (18 optional skips)
and five Chromium journeys. The new PDF journey verifies page 2 selection,
source/Composer/report/review, amendment, preserved originals, 390 px layout,
accessible labels and an actual server restart. Its report is human-authored;
no live model is invoked. [UI run 41553903829](https://github.com/OpenxIntelligence/open-intelligence/actions/runs/41553903829)
also passed the existing integrated, source-dialog race, keyboard and layout
journeys on the generated merge. Artifact hashes were checked, PDF screenshots
inspected, and all 213 archived source files matched before this receipt update.
The initial invalid YAML failed before jobs; the block-scalar correction and
successful rerun are documented in the intake contract. These are engineering
results for an unmerged synthetic prototype, not deployment or clinical approval.

The prior #173 baseline has now been verified: exact-head
[run 41550282180](https://github.com/OpenxIntelligence/open-intelligence/actions/runs/41550282180)
passed 349 Python/HTTP tests, 80 offline data-boundary checks with 18 optional
dependency skips, 47 JavaScript tests,
the reviewed-text intake browser journey and four Composer browser journeys.
Its separate [UI run 41550282107](https://github.com/OpenxIntelligence/open-intelligence/actions/runs/41550282107)
also passed. The older pending statements below describe earlier checkpoints.

## Document intake checkpoint — 2 November 2026

**Hosted verification update — 3 November 2026:** PR #173 implementation
`fe8a6368245bb52944e6ebc7f3e6f5b43daf69d0` passed exact-head run 41550282180
and generated-merge UI run 41550282107. The final documentation follow-up
`243bfec0fb36121868714dd36c6dd591243114da` passed integration run 41550696219
and UI run 41550696421. The initial 14 px mobile overflow was fixed without
weakening the gate. Source/artifact receipts are retained in the intake contract.

The current feature adds ordinary UTF-8 `.txt` file upload, read-only preview,
manual exact-line passage selection, confirmed metadata, original-byte download,
and the existing timeline/question/Composer/report path. It extends the original
source/version/assertion/event owner; it does not create another patient or
record store. See [the intake contract](engineering/DOCUMENT_INTAKE.md).

Manual statuses retain `classification_origin=user_selected` and
`clinical_review=not_performed` in the patient views, Patient Mission, timeline,
change review, investigation prompt, Composer preview/fingerprint, and snapshot
export. The selected quote remains distinct from the operator's classification.
An amendment uses the existing atomic invalidation and review mechanism.

At this checkpoint, 349 Python/domain/HTTP tests passed locally, including 19
intake domain tests and 14 intake HTTP tests. Six direct JavaScript intake cases
passed. A subsequent 43-test projection-specific regression run verifies manual
origin in Patient Mission, timeline and change review. Local Chrome/Chromium is
unavailable; hosted browser acceptance is established by the executed runs above.

The feature is stacked on verified PR #140. It is unmerged synthetic-only code,
not an authenticated clinical release. Limits include no PDF/OCR, no trusted
patient identity/session, no clinical interpretation, and no post-save annotation
editing. Original-only uploads are allowed, but their passages cannot be added
later through this version. No new third-party dependency is introduced.

The earlier checkpoints below describe their respective source trees.

## Current additive checkpoint — 2 November 2026

The platform mandate is now explicit in `AGENTS.md`: build a complete first-party cancer-care ecosystem incrementally, with a useful integrated MVP before advanced custom models. Public patient narratives inform workflow discovery only; Sid's patient data is excluded from development, training, evaluation, testing and synthetic derivation.

The working change stacked on PR126 connects the existing persistent rights broker to Composer, bounded model input selection, broker citation validation and stored hypothesis receipts. It separates display and model-use permissions, includes supporting/contradicting evidence and applicability, captures server freshness even without a client token, and withholds all affected model-derived text after input or rights changes. The existing patient, source and evidence stores remain canonical.

Local verification at this checkpoint: baseline 301 Python tests; extended 316 Python unit/HTTP tests passed. Four JavaScript test files pass, including a deliberately delayed same-case response test that failed before the UI generation-token fix and passed afterward. The workflow static guard passes. A new real-browser broker journey is present; local Chromium is unavailable, so hosted exact-head results are the browser acceptance gate and must be recorded separately. A read-only independent review found the same-case UI race and a premature browser wait; both have been corrected.

Compatibility: `composer-context-v2` incorporates broker content, review and permissions into the hash. Old previews and queued work carrying v1 hashes require fresh context and may be rejected as stale. Existing investigation rows remain readable through additive receipt tables. Receipts preserve hashes and non-content provenance, not a full protected prompt archive. Recorded permissions are declarations rather than verified legal entitlements. Replay receipts describe a constructed prompt; they do not prove that a live model processed it.

The five exact PR123 CI safety files are reused, and a dedicated pinned workflow checks the stacked PR head. The static guard does not enforce network isolation or retire every historical developer research entrypoint. No new dependency, external model call, clinical validation, production authorization, merge or deployment is established by this checkpoint.

Follow-up: the first exact-head hosted run 41518643782 passed the 316 application/HTTP tests, JavaScript contracts and three existing Composer browser journeys, then exposed an import-path defect in the new browser test before its scenario started. The fixture now uses the existing seed CLI. The existing UI workflow 41518643336 passed. These initial results do not establish that the new browser scenario passed; its corrected head must be checked separately.

The same follow-up reuses PR133's RNA/single-cell retirement work and main's catalog guard, with additional cleanup of residual historical sample/target fixture labels, a refusal before RNA CLI file IO, and a compatible invented-URL catalog refusal test. Pure offline parsers remain. Local offline verification discovered 98 tests: 80 passed and 18 optional HDF5 tests skipped because their optional dependencies were unavailable. No package was installed. This retires the known named-case catalog/RNA/single-cell acquisition commands, not all historical data artifacts or arbitrary network entrypoints in the repository; issue 122's broader audit remains open.

Research evidence is maintained as additive audit appendices under `docs/research/`, linked from the existing canonical Notion/Drive workspaces. Earlier dated implementation statements below describe their particular commits and are not current blanket capability assertions.

**Stage:** local experimental synthetic-only code. **Not released for clinical use.**

**Backlog coverage:** Part of OI-003, OI-006, OI-007, OI-009 and OI-010. Does not complete the broader investigation/evidence stage (OI-008), identity/governance (OI-012–013), or clinical evaluation (OI-014 onward).

## Behaviors built

- Strict import of independently authored `OI-SYNTHETIC-REPORT/1` UTF-8 bytes; explicit report identifier, subject, event date, issued date, specimen, finding quotation, and status.
- SQLite persistence of original source bytes and SHA-256, per-document version history, source-line anchors, atomic amendment invalidation, and idempotent same-bytes import.
- Wrong-subject quarantine; no assertions created for the requested case or the declared other case.
- Persistent questions, source-version-bound human-authored investigation drafts, demo-only acknowledgment, stale-on-amendment, and Markdown export including full source versions.
- Deterministic, read-only Patient Mission projection over the canonical case state, exposed at `GET /api/cases/{CASE-ID}/mission` and rendered in the existing portal.
- Patient Mission workflow status, source-linked reported statements, unresolved source states/questions, amendment/invalidation/quarantine changes, and only those next actions supported by the current demo.
- Local browser UI, served on `127.0.0.1` only, with no external assets or network-based research integrations.
- Plain Python `unittest` coverage for evidence and case boundaries, amendments, duplicate bytes, source recovery, the local HTTP surface, the Patient Mission projection, and static UI contracts.
- Two dependency-free headless Chromium journeys: the full synthetic source/evidence workflow and the Patient Mission case-switch/amendment workflow.

## Important unproven areas

- No authenticated identity, consent, delegation, role controls, auditing suitable for real patients, access revocation, or full security assessment.
- No PDF/OCR, automated clinical assertion extraction, FHIR/mCODE exchange, biological or imaging analysis, medical literature appraisal, trial searching, model inference, or provider integration.
- No independent professional review; demo acknowledgments are explicitly labeled and do not establish clinical correctness.
- The Patient Mission panel is a workflow projection, not a patient summary, diagnostic assessment, treatment plan, safety monitor, trial matcher, care coordinator, or clinical decision-support system.
- The source format is deliberately artificial to make deterministic boundaries testable. It must not be described as a general clinical importer.
- The application has no user-selectable release license yet. Before licensing or distribution, select a license and audit dependencies/assets (none intentionally incorporated beyond the Python standard library in this slice).

## Next bounded work

1. Establish a reviewed real-world workflow contract without using real patient data, including identity, consent, authority, and correction semantics.
2. Add source-to-assertion extraction as explicitly reviewable proposals from a specified document type while maintaining exact spans and amendment propagation.
3. Expand the Patient Mission projection only through separately specified capabilities such as goals, medications, specimens, safety escalation, access, execution, and outcomes; do not turn the projection into a second ledger.
4. Implement an evidence item with true source content, permission metadata, applicability review, and immutable retrieval receipts. Keep publisher rights separate from discovery metadata.
5. Compare the local case-domain implementation with the candidate Medplum/FHIR boundary using the same amendment, quarantine, case-isolation, and stale-response tests.

No milestones should be marked complete solely because an interface displays the correct-looking data.

## Independent verification — 31 October 2026

This verification covers the local synthetic-only source-ledger slice, **not** clinical fitness, privacy compliance, external evidence, or a public deployment.

- Regression hardening: repeat wrong-case submissions are idempotent; Markdown source content remains contained in safe export fences; the HTTP server rejects non-loopback Host values to limit DNS-rebinding risk; the browser discards stale responses following case switches.
- Mobile layout: the navigation rail's intrinsic track size caused horizontal overflow at 390 px; constrained the outer grid and its rail/main children. This was a real defect caught by the browser test.
- [GitHub Actions run #41221419037](https://github.com/OpenxIntelligence/open-intelligence/actions/runs/41221419037), commit `17f249ec085a08769a3386c454de18e3442b7883`: **pass**, Python compile, 18 unit/HTTP tests, and dependency-free headless Chromium journey.
- Browser journey verified: fictional Alpha source drilldown, switch to independent Beta and back, create a question, save source-linked draft, demo-only review acknowledgment, import amended pathology, stale previous snapshot and reopened question, preserve original source in export, and 390 px responsive containment.
- Tooling: Python 3.13 standard library, Chromium on GitHub's Ubuntu runner; no new runtime packages, medical data, services, scripts from vendors, or AI model weights incorporated.

**Remaining open evidence:** keyboard-only focus/operation and assistive technology testing, actual mobile-device testing, robust source-review and concurrency adversarial review, realistic ingestion, authentication and patient permissions, legal/build artifact clearance, clinical adjudication. Headless Chromium is not a substitute for clinical validation or a formal security audit. PR #1 should remain unmerged until the tracked review requirements have been resolved.

## Patient Mission projection verification — 31 October 2026

This verification covers one complementary Patient Mission Portal slice. It does not establish the broader Open Intelligence patient portal, diagnostic system, therapeutic-development system, care-realization system, or clinical safety.

- Test-first proof: run `41269640207` failed because the projection module did not yet exist; run `41269841287` failed because the mission endpoint did not yet exist; run `41270022603` failed because the mission renderer did not yet exist.
- Pure projection verification: empty cases do not invent state; current synthetic assertions retain source version and line; unresolved source states remain explicit; malformed event JSON is ignored rather than guessed; amendment-driven staleness is limited to dependent investigations; Alpha data does not leak into Beta.
- HTTP verification: the case-scoped mission endpoint returns the deterministic projection, unknown cases follow the existing `422 Unknown case` boundary, and unexpected Host values are rejected before case access.
- Portal verification: the Patient Mission surface shows workflow status, counts, current source statements, unresolved items, material changes, bounded next actions, and guardrails without mutating the ledger.
- Browser verification: the panel follows Alpha → Beta → Alpha case selection, discards stale responses, avoids cross-case source text, and moves to `Review required` after an explicit source amendment invalidates a bound investigation.
- [GitHub Actions run #41270150297](https://github.com/OpenxIntelligence/open-intelligence/actions/runs/41270150297), commit `8f6d915c1e92c8250c3e236663aa329157fc258d`: **pass**, Python compile, JavaScript syntax for both renderers, 49 unit/HTTP tests, the original browser journey, and the Patient Mission browser journey.
- No new database table, third-party dependency, model provider, network service, real patient datum, clinical assertion, treatment recommendation, or autonomous side effect was added.

**Remaining open evidence:** real identity and consent, PHI-grade access controls, realistic clinical ingestion, professional adjudication, uncertainty calibration, medication and acute-safety workflows, care-team collaboration, trials and access, therapeutic development, longitudinal outcomes, causal learning, and regulatory evaluation. Draft PR #38 must remain unmerged until review is complete.

## Local UI redesign candidate — 31 October 2026

This is a local pull-request review candidate. The synthetic-only and non-clinical release status above is unchanged. Hallmark has no clinical-site template: its Console theme is for research and audit-trail interfaces; its Dose theme is a medication organizer, not a clinic. The app screen uses Console's light Paper colorway.

- Promoted the source-derived event timeline to the primary full-width view and grouped source review, investigation, evidence, bibliography, and import tools beneath it.
- Applied the user's 8 px spacing grid and 4 px type grid, visible surface boundaries, 44 px controls, explicit primary and secondary button states, selected section navigation, compact copy, and a collapsible narrow-screen menu.
- Kept all eight hash destinations, existing form IDs and handlers, source lineage, safety language, synthetic-only local case behavior, and the explicit opt-in for public DOI lookups. Named the two source/evidence checkbox groups with fieldset legends. Added exact-path local serving and HTTP coverage for the token/base stylesheets.
- Python suite: **38 tests pass**. Hallmark `sloplint`: **0 failures, 0 reflex issues, 0 warnings**; `--kept` confirms **8/8 links** retained (baseline 94 failures and 64 reflex issues).
- Reviewed the rendered page in the in-app browser at 390 px, the default 892 px, and 1440 px; at 390 px the document width remained 375 px with no horizontal overflow. Verified the mobile menu opens, closes after section selection, the current link is marked, and checkbox groups are exposed by name.
- Limits: the repository's headless browser journey could not run because Chrome/Chromium is unavailable here. Hallmark's render automation could not run because `puppeteer-core` is unavailable; the page was instead inspected directly in the in-app browser. No physical-device or screen-reader testing was done.

This interface work is supporting evidence for OI-010 only; it does not satisfy end-to-end workflow acceptance or complete any clinical, security, privacy, or release milestone. It has not been deployed and uses no real patient data.

## Patient-centered investigation workbench refinement — 31 October 2026

This second local iteration makes the question-driven case review the main workflow after the longitudinal timeline. It treats the larger patient intelligence environment as the direction while keeping the current app honest about its capabilities: the saved synthesis is human-authored and no model is called.

- Added a direct action from the case overview to the investigation workbench, a keyboard skip link, and clearer navigation names. The timeline remains the entry point for source history.
- Composed case questions and reviewable drafts side by side. The interface labels the synthesis as human-authored with no AI call. Draft content now stores separate headings for reported observations, a working hypothesis or mechanism, and assumptions, contradictions, and gaps, while preserving the existing server snapshot contract and source/evidence bindings.
- The hypothesis and uncertainty fields are optional; reported observations remain required. This allows an explicit lack of a supported hypothesis instead of forcing a speculative answer.
- Preserved all eight destinations and existing behavior. Updated the browser journey to cover the structured fields and their case-switch protection.
- Verification: all **38 Python tests pass**; JavaScript syntax and browser-journey Python syntax checks pass. Hallmark app-scope lint reports **0 FAIL, 0 REFLEX, 0 WARN**. The local preview accessibility tree confirms the skip link, all eight destinations, and named reasoning fields. Whitespace-only reported observations are rejected before submission.
- Limits: the browser journey itself could not run because Chrome/Chromium is unavailable. Hallmark's render tier is unavailable because `puppeteer-core` is absent. Responsive CSS stacks the workbench below 60rem, but this iteration has not had a new narrow-width visual review, physical-device test, or screen-reader test.

This remains a synthetic-only workflow refinement, not the AI research copilot or a clinically validated system. It does not call the model API or change provider configuration. No deployment or real-data use is part of this change.
