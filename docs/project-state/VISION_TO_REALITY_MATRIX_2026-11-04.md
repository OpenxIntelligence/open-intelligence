# Open Intelligence — Vision-to-Reality Master Matrix (live audit baseline)

**Assessment date:** 2026-11-04. **Status:** first-pass evidence inventory; not a clinical readiness or repository-wide completeness certification. **Source:** live GitHub repository and current Notion/Drive canonical product thesis. **Observed main:** [a5a5482f815ceb3c322cdfb32ab8b18c1c0e8709](https://github.com/OpenxIntelligence/open-intelligence/commit/a5a5482f815ceb3c322cdfb32ab8b18c1c0e8709). Recheck this SHA before using the matrix for a merge/release decision.

## Evaluation framework

**Vision:** Patient World Model plus Record, Intelligence, Action and Discovery systems, connected by **Acquire → reconstruct → understand → provenance → investigate → reason → review → decide → act → confirm → reassess → learn**.

A status describes the **highest directly observed or boundedly documented scope**, not completion of the whole future capability. “Implemented, incomplete” can mean a credible but deliberately synthetic subset. “Fragmented” means an implementation is distributed across lineages without a verified accepted combined product. “Documented only” means no runtime evidence found in this bounded check, not proof of absence in the entire repository. “Unverified” means insufficient evidence for a more definitive classification.

**Evidence tiers:** (1) source file inspected on current main; (2) exact merged main and PR #390 verification receipt; (3) still-open candidate #405/#413 or closed separate contributor #422 and other PR descriptions—**these are leads, not inherited combined acceptance**; (4) product specifications. Test counts in PR descriptions are author/connector-observed records and are not new executions by this audit. Source links below are trace pointers; verify exact head and CI before acceptance.

## Capability matrix — 50 assessed rows

| ID | Capability | Current classification | Observed source / owner | Demonstrated boundary or gap | Next priority |
|---|---|---|---|---|---|
| A01 | Patient registry and synthetic identity | Implemented, incomplete | `apps/api/src/oi_api/patients.py`; #390 | Synthetic case/identity boundaries exist; real proofing, delegated relationships and account recovery are not established. | P0 |
| A02 | Authorization, scopes and revocation | Implemented, incomplete | `apps/api/src/oi_api/access.py`; #390 | Synthetic scoped grants and revocation tests; production identity, consent and privacy operations not qualified. | P0 |
| A03 | Consent, caregiver and clinical authority | Fragmented | Main reference consent/identity modules; #405 | Reference UX and H1 grants coexist in integration work; production delegated authority and clinician credentials unproven. | P0 release gate |
| A04 | Canonical source original and version | Implemented, incomplete | `apps/api/src/oi_api/sources.py`; #390 | Source/version custody in bounded H1 scope; not every modality or institution, and no broad provider network. | P0 |
| A05 | Original text/PDF intake and correction | Fragmented | Closed #323; open #405; `src/open_intelligence/document_intake.py` | Verified reviewed-document donor and integrated candidate; not confirmed as accepted on live main. | P0 |
| A06 | Imaging original custody/DICOM | Fragmented | #381 → #405; `apps/api/src/oi_api/images.py` | Synthetic image custody and browser journeys in draft convergence; PACS/DICOMweb production integration not qualified. | P1 |
| A07 | Structured FHIR R4 laboratory preview | Backend only | Closed #422; `apps/api/src/oi_api/laboratory_fhir_r4.py` on #422 | Strict read-only authorized lab preview branch; no native persisted FHIR source, H1 World Model observation or timeline. | P1 |
| A08 | HL7 v2, C-CDA and provider exchange | Unverified | `docs/FIRST_PRINCIPLES_PLAN.md`; H1 source adapters | No end-to-end live external institutional interface verified in this audit. | P1 |
| A09 | Pharmacy/medication exchange | Unverified | Full platform mandate; project-state architecture | No independently verified live medication reconciliation/dispense/administration interoperability. | P1 |
| A10 | Claims/payer/financial imports | Unverified | Full platform mandate; patient support scope | No independently verified real payer import, EOB or adjudicated assistance flow. | P2 |
| B01 | Source-backed longitudinal World Model | Implemented, incomplete | `apps/api/src/oi_api/source_world_model.py` on main | Read-only projection over one H1 source owner; file explicitly excludes migrated clinical decisions/models/action ledger. | P0 |
| B02 | Temporal source and amendment history | Implemented, incomplete | H1 sources / #390; #405 | Source chronology/version events exist; complete event/issued/received semantics for every modality remain unproven. | P0 |
| B03 | Missing, pending and negative states | Implemented, incomplete | `source_world_model.py` on main | Known reported-state distinctions preserved; decision-specific expected-evidence/coverage model not established. | P0 |
| B04 | Conflicting source statements | Implemented, incomplete | `source_world_model.py` on main | Detects same-specimen/date reported-vs-negative source conflict; not general cross-modality causal/clinical contradiction reasoning. | P1 |
| B05 | Patient-source identity collision safeguards | Implemented, incomplete | H1 source/registry tests; #390 | Synthetic wrong-case/wrong-patient tests; real MPI, cross-institution matching and merge/unmerge not qualified. | P0 |
| B06 | Exact citation and original source anchors | Implemented, incomplete | #390 evidence continuity; #405 documents | Structured source linkage exists on main H1 lineage; passage/PDF/image integration remains candidate-dependent. | P0 |
| B07 | Source correction and targeted stale dependents | Implemented, incomplete | H1 amendment handling; #397 / #413 | Some freshness logic exists; fully scoped dependency graph across summaries/reviews/agents/actions not established. | P0 |
| B08 | Cross-system context compiler | Documented only | Updated Notion Intelligence Architecture (2026-11-04) | Explicit question/user/action-specific context manifest is product specification; no end-to-end runtime verified. | P2 |
| B09 | Full Evidence Graph | Implemented, incomplete | #390 question evidence; H1 evidence contracts | Source/citation relationships exist; general typed support/opposition/applicability graph is not shown as one finished feature. | P1 |
| B10 | Decision Graph and clinical rationale | Unverified | `docs/FIRST_PRINCIPLES_PLAN.md`; review contracts | Qualified decisions, alternatives and rationale pinned to all patient/evidence versions not verified in this audit. | P1 |
| B11 | Diagnostic Gap Engine | Documented only | New Medical Intelligence OS product thesis | Some unresolved projections exist; decision-specific expectation and evidence-coverage engine not demonstrated. | P1 |
| B12 | Change Intelligence Engine | Implemented, incomplete | H1 source freshness; #397/#413 | Source-driven stale handling exists; cross-domain dependency-selective invalidation remains incomplete/unverified. | P1 |
| C01 | Durable question from patient source | Implemented, incomplete | #390; H1 `source_questions.py` | Saved question/evidence path on merged main H1 lineage, bounded by source and synthetic context. | P0 |
| C02 | Rights-qualified research evidence | Implemented, incomplete | #390; H1 `evidence_catalog.py` | Governed synthetic metadata and citation continuity; live licensed biomedical content and broad literature retrieval not cleared. | P0 |
| C03 | Counterevidence and applicability assessment | Fragmented | Reference hypothesis/evidence code; H1 reviews | Sources/alternatives in partial components; full reproducible scientific applicability workflow unverified. | P1 |
| C04 | Governed evidence report | Implemented, incomplete | #390; H1 `evidence_report.py` | Question/evidence report continuity in synthetic acceptance; not validated clinical recommendations. | P0 |
| C05 | Qualified clinical review and dissent | Implemented, incomplete | #390 H1 review/return path | Versioned reviewer-return workflow exists; real credential verification/clinical-signoff and dissent workflow not qualified. | P0 release gate |
| C06 | Provider-neutral inference and agent tools | Fragmented | Reference bounded model tasks; #141; H1 preflight | No verified end-to-end clinical model execution integrated with all H1 evidence/review/authority gates. | P2 |
| C07 | Agent checkpoints, pause/resume and audit | Documented only | Long-term maturity-gated agent mandate | Durable runtime/harness control and multi-agent independent verification are not demonstrated as finished product. | P2 |
| C08 | Model evaluation and decision utility | Unverified | Evaluation protocols; H1 acceptance | Synthetic software tests are not prospective clinical validation; model utility metrics need measured baselines. | P1 |
| D01 | Patient overview and continuity workspace | Implemented, incomplete | #390 merged reference + H1; #405 broader merge | Patient-facing workflows and browser tests exist, but full integrated longitudinal multidisciplinary record not verified. | P1 |
| D02 | Clinician case preparation and review UI | Implemented, incomplete | #390; H1 React review queue | Synthetic review surfaces exist; complete specialty clinician workflow/regulated deployment unproven. | P1 |
| D03 | Caregiver delegated workspace | Unverified | Product mandate; synthetic access policies | Cannot claim operational real proxy identity, relationship or end-to-end caregiver lifecycle. | P1 |
| D04 | Researcher workspace with isolated projection | Documented only | 30-domain blueprint / governance | Research separation specified; clinical-to-governed-cohort working boundary not end-to-end verified. | P3 |
| D05 | Voice and ambient structured encounters | Documented only | New Medical Intelligence OS vision | No verified ambient capture → structured facts/questions/tasks → reviewed note pipeline. | P2 |
| D06 | Adaptive low-noise clinician UI | Implemented, incomplete | Reference patient interface; React H1 workspace | UI exists; specialty-adaptive command center and validated comprehension/workload gains are unproven. | P1 |
| E01 | Follow-through task ledger and status history | Implemented, incomplete | `apps/api/src/oi_api/question_followthrough.py` on main; #390 | Internal persisted task state is explicitly not clinical approval nor externally performed action. | P0 |
| E02 | Actual outbound record request and receipt | Unverified | H1 `record_requests.py`; documented false external sent flags | No end-to-end verified institutional delivery/acknowledgment; internal request recorded must not imply sent. | P1 |
| E03 | Referral, booking and external acknowledgment | Unverified | Care coordination mandate; #402 | No current proof of real third-party recipient confirmation or booking completion. | P1 |
| E04 | Automated execution with authority gate | Implemented, incomplete | H1 authorization/task actions; policy | Some governed internal commands exist; high-impact clinical actions/regulated orders not authorized. | P2 |
| E05 | End-to-end confirmed care outcome | Unverified | Full spine acceptance requirement | No real patient care handoff/completion confirmed; synthetic task closure is not external outcome. | P1 |
| F01 | Cancer disease/specimen/assay graph | Fragmented | `source_world_model.py`; #422 FHIR preview; oncology plans | Source/specimen context exists in bounded cases; integrated multimodal cancer trajectory remains unverified. | P1 |
| F02 | Clinical trial criterion-level prescreen | Documented only | #421 Opportunity Dossier product amendment | Evidence/unknown design exists; live site eligibility and licensed up-to-date registry integration not verified. | P2 |
| F03 | Therapeutic portfolio and option dossiers | Documented only | #421 product amendment | Structured opportunity hypothesis is defined; no clinically validated personalized option engine. | P2 |
| F04 | Population intelligence and cohort safety | Documented only | Discovery Fabric vision / 30-domain blueprint | No authorized clinical-to-research cohort pipeline or clinical dataset rights established. | P3 |
| F05 | Computational biology/scientific agents | Fragmented | Research workflows; NVIDIA experimental #451 | Discrete synthetic/experimental tools exist; not a validated patient-linked research/discovery system. | P3 |
| G01 | Software/license/asset rights gates | Implemented, incomplete | #339; `apps/web/tools/license-gate.mjs`; #390 | Installed-package checks and exact wheel inventory exist; full release BOM/models/content/service rights not cleared. | P0 release gate |
| G02 | Exact-head integrated CI and backup/restore | Implemented, incomplete | #390 merged verified; #405 pending API recovery; #413 pending | Accepted #390 exact-head software gates passed; larger integrated candidates need their own full-gate results. | P0 |
| G03 | Privacy lifecycle, PHI and clinical compliance | Unverified | `AGENTS.md`; H1 synthetic-only gates | Engineering privacy constraints do not equal production PHI compliance, BAAs, provider identity, consent or clinical approval. | P0 release gate |
| G04 | Real-world clinical and human-factors evidence | Unverified | Independent Validation program | No clinical efficacy or real-world workload/access impact can be inferred from synthetic CI. | P1 release gate |

## Highest-impact verified distinctions

1. The current H1 source-derived World Model is a **read-only projection** and explicitly excludes a full migrated model/clinical-decision/action ledger: [source_world_model.py](https://github.com/OpenxIntelligence/open-intelligence/blob/main/apps/api/src/oi_api/source_world_model.py).
2. H1 follow-through is an **internal recorded work history**, not external action or qualified clinical approval: [question_followthrough.py](https://github.com/OpenxIntelligence/open-intelligence/blob/main/apps/api/src/oi_api/question_followthrough.py).
3. The merged #390 brings an H1 evidence/continuity/follow-through lineage to main with successful *synthetic* exact-head CI; see [#390](https://github.com/OpenxIntelligence/open-intelligence/pull/390). It does not absorb every later document/image/manual-passage/FHIR branch.
4. [#405](https://github.com/OpenxIntelligence/open-intelligence/pull/405) is the broader full-stack candidate. Live inspection of [API/PG run 41790730476](https://github.com/OpenxIntelligence/open-intelligence/actions/runs/41790730476) found **CANCELLED** during PostgreSQL contract tests; downstream prototype/browser and six recovery probes were **SKIPPED**. Browser and reference successes do not close this combined API gate.
5. [#413](https://github.com/OpenxIntelligence/open-intelligence/pull/413) composes manual passage reporting and freshness. Live inspection of [API/PG run 41799154582](https://github.com/OpenxIntelligence/open-intelligence/actions/runs/41799154582) found **SUCCESS** at every major stage, including contracts, reference browser, source/image/review/follow-through, backup/restore and revocation probes. React/browser was already successful per the PR's recorded receipt. This is a **verified synthetic branch-level combined workflow**, still unmerged and not automatically reconciled with the now-moving main or #405.
6. [#422](https://github.com/OpenxIntelligence/open-intelligence/pull/422) contains a strict **read-only FHIR R4 laboratory preview**; live inspection of [API/PG run 41794564799](https://github.com/OpenxIntelligence/open-intelligence/actions/runs/41794564799) found **FAILURE** during PostgreSQL contracts, with downstream recovery probes skipped. Parser and React passes do not close this API acceptance gate. There is no native FHIR source persistence or Patient World Model/timeline publication.
7. Many foundational project-state Markdown documents still contain older 'main=SQLite-only' statements and dated inventories. Preserve those as historical evidence, but their claims are not a live main inventory; use the live commit and merge/CI records instead.

## P0 acceptance mission: prove one complete intelligence spine

On one integrated, reviewable synthetic source tree, run an independently authored fictional multi-institution oncology case through: source import and exact original custody; correct identity/specimen mapping; clinical/source assertions and timeline; explicit absent/negative/pending/conflicting states; a source-linked question and contrary evidence; version-pinned human review; a permissioned action with **truthful** requested/sent/acknowledged/completed status; amendment and rights revocation; targeted dependent-only stale outputs; restart, restore, retry and denied read/write controls. Source, assertion, interpretation, professional decision and observed external outcome must remain distinct. No real PHI, live EHR/PACS connection, licensed-content activation, autonomous treatment or deployment authorization.

**Release criteria:** exact combined head/tree; full API+PostgreSQL and React+browser+rights suites without relevant skips; migration and six recovery probes; independent source/security/rights review; case-level evidence receipts; explicit approval. The capability matrix must link every status promotion to this evidence.

## Evidence-management tasks

- #405: investigate cancelled combined API/PG workflow and rerun all gates at a current head. #413: confirm successful run belongs to the current exact head, then review/reconcile moving main and #405 before any merge. #422: diagnose failed API/PG contracts; do not promote preview to accepted endpoint.
- Resolve source-owner overlap among reviewed documents, image custody, manually selected passages, FHIR lab preview, and follow-through without creating a second ledger.
- Extend matrix to *all* 30 architecture domains, user journeys, 50 opportunity needs and proposed 50 agents/capabilities, but keep uninspected items 'unverified' rather than inventing completion percentages.
- Mirror the matrix and decision rules into existing Notion implementation/roadmap and the Google Drive engineering progress document. Preserve historical status receipts.
- Only then select the next code slice (native immutable FHIR custody→typed lab observation→Patient World Model→patient timeline is a strong candidate, dependent on integration-gate review).

## Links

- [Canonical first-principles plan](https://github.com/OpenxIntelligence/open-intelligence/blob/main/docs/FIRST_PRINCIPLES_PLAN.md)
- [Current main source-derived World Model](https://github.com/OpenxIntelligence/open-intelligence/blob/main/apps/api/src/oi_api/source_world_model.py)
- [Current main H1 follow-through](https://github.com/OpenxIntelligence/open-intelligence/blob/main/apps/api/src/oi_api/question_followthrough.py)
- [Merged H1 integration #390](https://github.com/OpenxIntelligence/open-intelligence/pull/390)
- [Full-stack integration #405](https://github.com/OpenxIntelligence/open-intelligence/pull/405)
- [Manual passage/freshness integration #413](https://github.com/OpenxIntelligence/open-intelligence/pull/413)
- [Laboratory FHIR preview #422](https://github.com/OpenxIntelligence/open-intelligence/pull/422)
- [Product opportunity dossier #421](https://github.com/OpenxIntelligence/open-intelligence/pull/421)


## Live CI state correction — 4 November 2026

This section is based on direct readout of the latest-attempt GitHub workflow **jobs and stage conclusions**, not a PR's earlier prose checkpoint:

| Candidate | Workflow | Directly observed job | Consequence |
|---|---|---|---|
| #405 | [41790730476](https://github.com/OpenxIntelligence/open-intelligence/actions/runs/41790730476) | **cancelled** at PostgreSQL contract test stage; all post-contract recovery probes skipped | Combined H1 API acceptance **not established** |
| #413 | [41799154582](https://github.com/OpenxIntelligence/open-intelligence/actions/runs/41799154582) | **success**, including PostgreSQL contracts, inherited regression/browser checks, six recovery-related stages and artifact upload | Positive exact-workflow evidence for this draft branch; still requires current-head/main reconciliation and owner review |
| #422 | [41794564799](https://github.com/OpenxIntelligence/open-intelligence/actions/runs/41794564799) | **failure** in PostgreSQL contract test stage; downstream recovery probes skipped | API preview acceptance failed; root cause requires logs and bounded repair |

The presence of a SUCCESS job is not clinical validity, production deployment or merge authorization. No model/clinical-use claims change.
