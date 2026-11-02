# First-party patient → evidence → durable computation → review handoff

**Status:** synthetic-only integration candidate, draft and unmerged. An addition to the existing Open Intelligence architecture, not a replacement of the Patient World Model, canonical patient registry, EHR, LIS, evidence owner, investigation engine or main application.

## Exact upstream ownership

- Base: [#132](https://github.com/OpenxIntelligence/open-intelligence/pull/132), itself on [#130](https://github.com/OpenxIntelligence/open-intelligence/pull/130) and [#95](https://github.com/OpenxIntelligence/open-intelligence/pull/95). The existing authorizers, rights-qualified knowledge compiler, EHR encounter/note and LIS/identity/source operations remain upstream owned.
- Adopted unchanged as a **stacked test composition**, *not a new approved application dependency*: original first-party Python source blobs `lab_trends.py` (SHA `fce508636fe46f076531b62c5d2378f0c1bb9462`), `composer_lab.py` (SHA `376e7505b000f65614ca1b2f1f68c5f9b01acb4a`), `durable_runs.py` (SHA `8c7cdc760f4e779907e8d349a649d9e35f163488`) from the [#126](https://github.com/OpenxIntelligence/open-intelligence/pull/126) Composer/durable-run owner stack. No changes to these original implementations.
- New `patient_research_review.py` **reads** an already durable calculation through the original journal. It creates no tables, question states, machine-learning model, medical inference, clinical sign-off or new data records.
- New `test_patient_research_run_review.py` exercises real first-party canonical patient/EHR/LIS/Composer/knowledge/SQL store and original durable calculation.

## Executed synthetic workflow

1. The accepted canonical patient/source-case and clinical source context are checked via `AuthorizedClinicalKnowledge.snapshot`, including the exact native Composer question and rights-aware fictional knowledge source.
2. Two **independently authored** laboratory sources contain literal `OI-LAB-VALUE/1` numeric values and declared synthetic QC (not analyzer-verified laboratory measurements).
3. The original `DurableComposerRuns` queues and synchronously executes a deterministic numeric calculation; its own tables own the result, event history and persisted context fingerprint.
4. `PatientResearchReview.snapshot` enforces authorization and rights context before reading the run; checks original case, question, every point's document/version/hash/line and exact numeric quotation against the original source tables.
5. It rechecks the patient/knowledge context, original run receipt and authorization after assembly, rejecting wrong patient/case/actor/purpose, source forgery and source mutation during the review.
6. It presents a **pending human review** of a current computation, or an explicitly **historical reassessment-required** view if the source has changed. It does not turn a numeric delta into a medical statement.
7. `export_markdown` produces a source-linked fictional numerical methods handoff using the durable run ID/context fingerprint and original source hashes. It deliberately **excludes** external biomedical article titles/full text and clinical note narrative because display and ML rights do not automatically grant redistribution permission.

## Relevant test cases

- Current original numeric sources and original durable result in a single authorized patient/clinical/evidence context.
- Correction to one source version → original value preserved; run marked stale; review flagged for reassessment.
- Wrong patient/case/actor/purpose and wrong-question scope rejected.
- Revoked patient-to-source-case binding denies even access to historical output.
- Revoked external content source removes that content from current knowledge but preserves a separately permitted patient numeric receipt, without granting model execution.
- Tampered persisted source hash rejected against authoritative source rows.
- Source mutation during review rejected; previously returned packet cannot be treated as current.
- Markdown handoff includes only source identifiers, hashes and fictional numeric values; no unlicensed external scientific text or note body.

## Explicit nonclaims and limitations

The original `DurableComposerRuns` is **not an authenticated production command endpoint**, distributed agent worker or model execution service. This PR introduces a read-only authorization gate for **review**, not a new authorization service for queue/execute. New reports are derived exports, not independently stored/signature-authenticated clinical reports. Source-level QC is a synthetic declaration; the verified LIS release for a different source is not proof these extra numerical inputs were clinically reviewed. The original patient and knowledge case mapping is fictional and not a legitimate patient identity proof. A source comparison is an unreviewed proposal, not accepted literature or confirmed clinical applicability.

The separate lab-review receiver has no atomic distributed snapshot with the original source database; rechecking narrows but does not eliminate races. The existing journal lazily persists staleness on read; it can leave an incomplete running state after crash, without worker/lease recovery. Authentic identity, consent, trusted rights, PHI security, model use, human reviewer signatures and clinical/regulatory validation remain external release gates. No Next.js, real patient data, guideline content, third-party packages or external network calls have been introduced.

## Required follow-on after review

- Reconcile [#126](https://github.com/OpenxIntelligence/open-intelligence/pull/126) source-owner commits and [#132](https://github.com/OpenxIntelligence/open-intelligence/pull/132) stack exactly once, including [#136](https://github.com/OpenxIntelligence/open-intelligence/pull/136) investigation-question lifecycle and [#138](https://github.com/OpenxIntelligence/open-intelligence/pull/138) first connected local HTTP acceptance.
- Bind future tool **commands** to actual verified actor/purpose/consent, tokenized current source/rights and fail-closed atomicity, not a read-only preview or manually asserted permission receipt.
- Connect the original model/recorded-replay investigation and versioned evidence comparisons to a reviewed report; preserve source amendments, literature revocations and dependent-only invalidation.
- Add real authenticated application API and accessible task-first patient/clinician UI only after security policy; run full workflow acceptance against final integrated branch.
