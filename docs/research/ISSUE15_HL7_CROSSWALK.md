# Issue #15 — HL7 AI/ML lifecycle crosswalk against existing Open Intelligence entities

**Status:** RESEARCH / EVALUATE; not an adopted architecture decision, implementation, clinical validation, or vendor approval.
**Date:** 2026-11-02
**Tracker:** [Issue #15](https://github.com/OpenxIntelligence/open-intelligence/issues/15)
**Companion:** [HL7 / Nano / specialist-model addendum](HL7_NANO_MODEL_FABRIC_ADDENDUM.md) (2026-10-31)
**Boundary:** additive extensions only. This crosswalk never replaces canonical patient state, evidence, provenance, consent, or human authority. It supplements, and does not supersede, [the first-principles plan](../FIRST_PRINCIPLES_PLAN.md), the decided Meta-only investigation slice in [META_MODEL_API.md](../META_MODEL_API.md), or the deterministic timeline in [`timeline.py`](../../src/open_intelligence/timeline.py). All examples are independently authored fictional oncology demonstration data, labeled as such everywhere.

## 1. Evidence classes used in this document

Every claim about HL7 guidance below carries one of these labels. The labels are the point: nothing is presented as established that this agent could not verify from in-repo sources.

| Label | Meaning |
|---|---|
| IN-REPO-VERIFIED | Observed directly in a cited repository file (path given). |
| ADDENDUM-DESCRIBED | Restated from the 2026-10-31 addendum's account of the HL7 product brief; traceable to the in-repo pointer, but the underlying HL7 text was not re-read here. |
| UNVERIFIED | Cannot be verified from in-repo sources (HL7's site is unreachable from this environment). Stated with its source pointer, never as established fact. |

## 2. HL7 reference as described in-repo (all claims labeled)

- The referenced guidance is titled "HL7 Informative Document: AI/ML Data Lifecycle, Edition 1 — US Realm", with an HL7 status date of 2024-08-27 and product id 658. [ADDENDUM-DESCRIBED; source pointer: addendum §2 and its link to `https://www.hl7.org/implement/standards/product_brief.cfm?product_id=658`]
- It is *informative guidance*, not a mandatory normative implementation specification. [ADDENDUM-DESCRIBED; same pointer]
- Its Phase I focus is data used for predictive ML models, not all generative-AI output workflows. [ADDENDUM-DESCRIBED; same pointer]
- The product brief is described as emphasizing consistent annotation and processing, interoperability, data quality, provenance, accountability/audit, transparency, and appropriate use, and as mentioning 12 supplementary case studies. [ADDENDUM-DESCRIBED; same pointer]
- The product brief alone is described as not supplying the full clause mapping, a license grant, downloadable document contents, or an AI inference/run API. [ADDENDUM-DESCRIBED; same pointer]
- UNVERIFIED: the actual wording, scope, definitions, and any license or reuse terms of the full HL7 document and its 12 case studies. [Source pointer: the two HL7 URLs in the addendum References section; unreachable from here. Confirm licensing and inspect the full text under permitted access before claiming any clause-by-clause crosswalk or copying HL7 text.]
- UNVERIFIED: whether any statement in this crosswalk's HL7-concern column matches a specific HL7 clause number or normative requirement. [Source pointer: same. The concern labels below are the addendum's checklist paraphrase, not quoted HL7 clauses.]

Consequence: this crosswalk maps the addendum's *checklist paraphrase* of HL7 concerns against existing repository entities. It is not an HL7 compliance claim and must not be cited as one.

## 3. Entity crosswalk

"Existing owner" entries are IN-REPO-VERIFIED with file pointers. "Gap" entries are genuine only where the cited machinery demonstrably lacks the capability; §4 records each gap's evidence.

### 3.1 Acquisition, permitted purpose, source origin, consent

| Concern (ADDENDUM-DESCRIBED) | Existing owner (IN-REPO-VERIFIED) | Assessment |
|---|---|---|
| Acquisition with origin and receipt | `source_versions` row + sha256 + `received_at`, written only by `CaseStore.import_report` ([store.py](../../src/open_intelligence/store.py), schema and `import_report`) | Owned. No gap for synthetic-source receipt. |
| Wrong-subject protection | `quarantine` table + `patient_mismatch` path in `import_report`; adapter deliveries via `quarantine_adapter_delivery` | Owned. No gap for the quarantine mechanism itself. |
| Permitted purpose per input | `rights_sources` + `rights_permissions` with explicit allow/deny/unknown per item and use ([rights.py](../../src/open_intelligence/rights.py)) | Owned for broker/discovery-linked content. Partial for case sources (see G-1). |
| Usage purpose, privacy class, rights status per input | Not recorded per case-source input | **Genuine gap G-1** (see §4). |
| Consent as a first-class entity | Only `consent_state`/`consent_value` text fields on `biological_inventory_assertions` (`known`/`unknown`, free-text value); no grant scope, purpose, expiry, or revocation entity for case data | **Genuine gap G-2** (see §4). |
| Revocation stopping future use | `revoke_rights_source` invalidates dependent broker links and discovery links (`_invalidate_broker_source`, `_invalidate_discovery_source`) | Owned for broker/discovery scope. No equivalent for case sources or derived model artifacts (**G-2**). |

### 3.2 Annotation, normalization, data quality

| Concern (ADDENDUM-DESCRIBED) | Existing owner (IN-REPO-VERIFIED) | Assessment |
|---|---|---|
| Original bytes preserved | `source_versions.raw` immutable after insert; amendments add versions, never rewrite | Owned. |
| Source-linked assertions | `assertions` rows with `finding_key`, `certainty`, verbatim `quote`, `source_line` | Owned for the declared `OI-SYNTHETIC-REPORT/1` contract. |
| Missingness states kept distinct | `STATES` (`reported`, `negative`, `pending`, `indeterminate`, `not-reported`, `not-assessed`, `conflicting`) enforced by `parse_report` | Owned. |
| Transformation / tool version, normalization map, field-level QC | Not recorded; there is no transformation-receipt entity | **Genuine gap G-3** (see §4). The proposed [ModelRunReceipt](ISSUE15_MODEL_RUN_RECEIPT.md) covers it. |
| Abstention records | `abstentions_json` on `investigations` rows ([investigation.py](../../src/open_intelligence/investigation.py) `validate_output`) | Owned for the investigation path only; no generic derivation-abstention record (**G-3**). |

### 3.3 Temporal integrity

| Concern (ADDENDUM-DESCRIBED) | Existing owner (IN-REPO-VERIFIED) | Assessment |
|---|---|---|
| Effective / issued / ingestion / amendment times kept independently | `event_date`, `issued_at`, `received_at`, `supersedes_id` on `source_versions`; six-facet taxonomy documented in [TEMPORAL_REASONING.md](../TEMPORAL_REASONING.md) | Owned. |
| Deterministic timeline projection | `case_timeline` in [timeline.py](../../src/open_intelligence/timeline.py): read-only, no inference, gaps/conflicts stay `unknown` | Owned. |
| Partial / uncertain dates | `valid_date` requires full `YYYY-MM-DD`; partial dates have no representation | **Genuine gap G-4**, but pre-existing and out of issue-#15 scope (recorded, not solved here). |
| Model-derived timeline candidates as a distinct layer | No representation exists; the timeline admits only current ledger facts | **Genuine gap G-5**, addressed by the proposed [DerivedTimelineCandidate](ISSUE15_DERIVED_TIMELINE_CANDIDATE.md) spec. |

### 3.4 Provenance, audit, AI involvement

| Concern (ADDENDUM-DESCRIBED) | Existing owner (IN-REPO-VERIFIED) | Assessment |
|---|---|---|
| Append-only event audit | `events` table (`_event`), including adapter kinds in `ADAPTER_EVENT_KINDS` and `record_adapter_event` | Owned. |
| Assertion provenance | Every assertion row points at one exact `source_version_id` with line anchor | Owned. |
| Byte-integrity proof | sha256 recorded per source and evidence version; duplicate detection on `(case, document, sha256)` | Owned as byte-equality proof only. It proves nothing about authenticity or clinical correctness (addendum §3, restated). |
| Model-run receipt with provider/version/inputs/outputs/rights decision | `investigations` rows record `template`, `status`, `mode`, `model`, claims/abstentions/dropped JSON — but no model version/build, no input artifact versions, no output hash, no egress-mode or policy decision | **Genuine gap G-6**, addressed by the proposed [ModelRunReceipt](ISSUE15_MODEL_RUN_RECEIPT.md) spec. |
| Replay against frozen inputs | Replay mode exists for investigations (`recorded-replay` fixture); no generic receipt-replay contract | Partial; folded into **G-6**. |

### 3.5 Lifecycle transparency (derivation, invalidation, review)

| Concern (ADDENDUM-DESCRIBED) | Existing owner (IN-REPO-VERIFIED) | Assessment |
|---|---|---|
| Amendment-triggered selective invalidation | `import_report` supersedes the prior version and marks only dependent snapshots stale, reopens their questions, flags case investigations stale, and anchor-exactly stales options and inventory assertions — all in one transaction | Owned. The [amendment flow](ISSUE15_AMENDMENT_FLOW.md) builds on exactly this. |
| Change projection since review | `changes_since_review` in [changes.py](../../src/open_intelligence/changes.py) | Owned. |
| Scoped human review | `acknowledge_demo_review` (demo acknowledgment with `review_events` row; explicitly not clinical sign-off per [README](../../README.md)) and `review_option` with scoped actions | Owned as demo-scope review. No clinical-authority entity exists, by design at this stage. |
| Display-ready derived candidates that never self-authorize | No candidate layer exists | **Genuine gap G-5** (shared with §3.3). |

### 3.6 Model quality, fitness, capability governance

| Concern (ADDENDUM-DESCRIBED) | Existing owner (IN-REPO-VERIFIED) | Assessment |
|---|---|---|
| Task contract + language guard | `TEMPLATES`, `GUARD_PATTERNS`, `validate_output` in [investigation.py](../../src/open_intelligence/investigation.py); stored output always `kind=hypothesis`, `review_state=pending` | Owned for the Meta-only investigation path. |
| Provider boundary | Meta Model API exclusively, key from `META_API_KEY`, server-side only ([META_MODEL_API.md](../META_MODEL_API.md)) | Decided and owned. Issue #15 does not reopen it. |
| Capability registry (task/modality, schemas, QC, terms, cost, evaluation date) | `TEMPLATES` dict only; no per-capability terms, retention/training limits, QC metadata, or evaluation record | **Genuine gap G-7**, addressed by the proposed [ModelCapabilityRegistry](ISSUE15_MODEL_CAPABILITY_REGISTRY.md) spec. |
| Unknown-permissions-means-blocked for model calls | `rights.py` implements fail-closed gating, but nothing wires it to the model-call boundary | **Genuine gap G-8**; the [mock adapter](../../tools/mock_specialist_adapter.py) demonstrates the wiring pattern without touching the decided live path. |
| Versioned benchmark + failure thresholds | Evaluation packet / preflight tooling exists (`tools/evaluation_packet.py`, `tools/evaluation_preflight.py`); no specialist-model benchmark exists | Evaluation design drafted in [ISSUE15_EVALUATION_DESIGN.md](ISSUE15_EVALUATION_DESIGN.md); no results run or claimed. |
| Nano availability, license, API terms | No Nano dependency, runnable, license, or terms exist in-repo | UNVERIFIED in every respect; Nano remains a candidate name only (see §5). |

## 4. Genuine gaps (bounded, additive remedies only)

| ID | Gap | Evidence | Remedy in this issue (proposal/demo only) |
|---|---|---|---|
| G-1 | No per-input purpose / privacy class / rights status on case sources | `source_versions` schema has no such columns; `rights.py` gates only broker/discovery content | Specified as optional receipt extension in [ModelRunReceipt](ISSUE15_MODEL_RUN_RECEIPT.md); no schema change made here |
| G-2 | No first-class consent/authority-grant entity with scope and revocation | Only free-text `consent_state`/`consent_value` on inventory assertions; `revoke_rights_source` covers broker/discovery only | Recorded as a held requirement; consent design is explicitly out of issue-#15 scope and must not be improvised here |
| G-3 | No transformation-receipt / generic derivation-abstention record | No such table or contract outside `investigations.abstentions_json` | [ModelRunReceipt](ISSUE15_MODEL_RUN_RECEIPT.md) spec |
| G-4 | No partial/uncertain-date representation | `valid_date` rejects anything but full `YYYY-MM-DD` | Recorded only; out of scope |
| G-5 | No derived-timeline-candidate layer distinct from canonical timeline | `timeline.py` admits only current ledger facts by construction | [DerivedTimelineCandidate](ISSUE15_DERIVED_TIMELINE_CANDIDATE.md) spec |
| G-6 | Run receipts lack version/inputs/hash/egress-decision fields | `investigations` columns enumerated in §3.4 | [ModelRunReceipt](ISSUE15_MODEL_RUN_RECEIPT.md) spec |
| G-7 | No model-capability registry | Only `TEMPLATES`; no terms/QC/evaluation metadata | [ModelCapabilityRegistry](ISSUE15_MODEL_CAPABILITY_REGISTRY.md) spec |
| G-8 | Rights gate not wired to any model-call boundary | `permitted()` exists; no caller at the model boundary | Demonstrated by the branch-only [mock adapter](../../tools/mock_specialist_adapter.py); the decided live path is untouched |

Non-gaps confirmed: source versioning and receipts, byte-integrity hashing, wrong-subject quarantine, assertion anchors, missingness states, deterministic timeline, amendment supersession with anchor-exact invalidation, change projection, demo-scope review records, and fail-closed rights gating for broker/discovery content. None of these is duplicated by the issue-#15 proposals.

## 5. Nano and AlphaGenome: explicit non-claims

- Nano is referenced in-repo only as an optional, independently evaluated model candidate (addendum §1, §5). No Nano code, weights, runnable, license, terms, or evaluation result exists in this repository. Any statement about Nano's capabilities, availability, license, or fitness is UNVERIFIED and must stay labeled so.
- AlphaGenome is referenced in-repo only as an example of a third-party model that must not be assumed callable (addendum §5). No AlphaGenome integration exists or is proposed here.
- The [mock adapter](../../tools/mock_specialist_adapter.py) is a deterministic local harness with no Nano dependency and no network use. It proves the receipt/candidate/gating shapes, not any model behavior.

## 6. Decision section (adopt / evaluate / hold / reject)

Framed strictly as the four options. Each option names the evidence and rights review it still requires. Current decision: **EVALUATE** (unchanged from the addendum §7).

### Adopt

Adopt the three contract specs ([ModelRunReceipt](ISSUE15_MODEL_RUN_RECEIPT.md), [DerivedTimelineCandidate](ISSUE15_DERIVED_TIMELINE_CANDIDATE.md), [ModelCapabilityRegistry](ISSUE15_MODEL_CAPABILITY_REGISTRY.md)) as the shape for future specialist-model integration work, and keep the mock adapter as a branch-only harness.

- Still requires: reviewer acceptance of each spec; confirmation that no spec duplicates canonical authority (reviewer check against §3); a separately scoped proposal before any schema or live-path change; no HL7 compliance claim at any point.
- Rights review still required: none beyond the existing in-repo gates for the specs and mock themselves (original synthetic text, no third-party component, no new dependency). Any future live-model wiring re-triggers full per-provider clearance.
- Evidence still required: the specs are design artifacts; adoption as *design direction* needs reviewer sign-off only, not benchmark results.

### Evaluate (recommended, current state)

Continue evaluation: hold the specs as research proposals, run the mock-adapter tests once a working shell is available, author the frozen synthetic fixture set and adjudication labels from the [evaluation design](ISSUE15_EVALUATION_DESIGN.md), and measure the deterministic baseline before any model comparison.

- Still requires: fixture authorship independent of the adapter author; adjudication labels authored blind to adapter output; baseline measurements recorded with raw counts.
- Rights review still required: none new until a real model or dataset enters the comparison; the deterministic-baseline step uses only original synthetic text.
- Evidence still required: all of it — no evaluation result exists yet, and none is claimed.

### Hold

Hold the specialist-model direction (including Nano candidacy) while the first implementation milestone completes, keeping the specs on file as unaccepted research.

- Still requires: an explicit statement of what would re-open evaluation (e.g., milestone completion, a named investigation need per OI-016, or a runnable model with documented license).
- Rights review still required: only to confirm that held status imposes no new obligations; the hold itself needs no clearance.
- Evidence still required: none, but nothing is learned either; G-3/G-5/G-6/G-7/G-8 remain open.

### Reject

Reject one or more specs (or the specialist-model slice) as not worth pursuing.

- Still requires: a recorded reason per rejected item (e.g., "capability registry is premature before the first real model need"), author, and date; reversibility note.
- Rights review still required: none; rejection removes future review surface.
- Evidence still required: none. Note that rejection of the specs does not close the underlying gaps (G-1–G-8); it only declines these remedies. G-2 (consent) in particular survives any rejection here and needs its own scoped work.

## 7. What remains UNVERIFIED or reviewer-dependent

- UNVERIFIED: every statement about HL7 document contents, clause wording, case studies, and license terms (§2). Source pointers: the HL7 URLs in the addendum References.
- UNVERIFIED: Nano's existence as a runnable, its license, terms, capabilities, and fitness for any task (§5).
- Reviewer-dependent: whether the genuine gaps (§4) are correctly characterized against the full codebase and any in-flight PRs (this agent read the cited files only; a reviewer must confirm no other branch already closes a gap).
- Reviewer-dependent: acceptance of each spec and of the evaluate-vs-hold choice in §6.
- Not verifiable in this session: test execution. The mock-adapter tests are authored but were not run (sandboxed shell cannot mount proc; no shell verification was attempted). The run command for a reviewer is `PYTHONPATH=src python -m unittest tests.test_mock_specialist_adapter -v` from the repository root.
