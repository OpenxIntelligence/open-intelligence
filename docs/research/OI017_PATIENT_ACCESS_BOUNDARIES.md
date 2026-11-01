# OI-017 — Patient-directed access and lossless evidence boundaries (complementary research)

**Date:** 2026-10-31
**Status:** Complementary research + synthetic adapter contract. **Not** an adopted
architecture, vendor decision, implemented live integration, legal determination,
or clinical release.
**Project:** Open Intelligence (the former name is historical only).
**Issue:** [#17](https://github.com/OpenxIntelligence/open-intelligence/issues/17) —
validate patient-directed access and lossless evidence boundaries.
**Related existing work:** OI-005 (interoperability boundary), OI-006 (source
fidelity), OI-012 (authorization / intended use), OI-013 (isolation), OI-014
(evaluation). This document maps to those items; it creates no new backlog
item, no second patient store, no second source ledger, no canonical model,
and no authorization system.

**What this PR adds, in one paragraph.** A deterministic, synthetic-only
adapter gate (`src/open_intelligence/patient_access.py`) in front of the
*existing* `CaseStore` source ledger, plus fictional fixtures and failure-mode
tests. The gate validates an adapter envelope, enforces loss receipts,
quarantines identity collisions instead of merging them, records revocation
in the existing event ledger without deleting history, and rejects
Treatment-purpose receipts for this patient-directed adapter. No real adapter
was connected, no vendor was selected, no real patient data was accessed.

## 1. Evidence tiers — what this document can and cannot claim

| Tier | Permitted claim | Not established |
| --- | --- | --- |
| Synthetic contract evidence (this PR) | Behaviour of the adapter gate and the existing source/evidence contracts for the specified fictional cases | Real institutional coverage, live identity proofing, representative matching error rates |
| Separately authorized vendor sandbox | Compatibility with the named sandbox version and documented payloads | Production access rights, nationwide availability, real-patient completeness |
| Separately authorized real-data evaluation | Observed results for the specified population, sites, dates, artifact classes, permitted protocol | Universal coverage, efficacy, clinical release approval |

Synthetic success does not establish any real-world outcome. A fictional
patient must never be submitted to a live clinical exchange as though it were
a real authorized individual. No live clinical use, vendor contracting,
external outreach, or patient data access is authorized by issue #17 or by
this document.

## 2. Pathway map: patient-facing Individual Access Services (IAS) vs provider Treatment purpose

The distinction that matters is **purpose and role**, not merely transport.
Both pathways can move FHIR, but eligibility, identity proofing, permitted
use, and commercial/legal obligations differ, and a receipt valid for one
purpose is not valid for the other. The adapter in this PR accepts only
`individual-access` purpose; a Treatment-purpose receipt is rejected at the
gate (tested), because silently accepting it would misrepresent the basis
on which bytes arrived.

| Pathway | Who acts | Purpose | Eligibility / role questions that must be answered before any real use | Commercial / legal obligations to verify (unresolved) |
| --- | --- | --- | --- | --- |
| TEFCA / QHIN Individual Access Services (IAS) | Patient-facing app via a QHIN / IAS provider | Individual access (patient-directed) | Is the app an eligible IAS participant? Which QHINs does the IAS provider connect? What identity proofing and patient matching does it perform? What scope and completeness does it actually return? | QHIN participation terms, IAS provider agreement, permitted-use and audit duties, pricing — none verified in this PR |
| TEFCA / QHIN Treatment purpose | Provider organization via a QHIN | Treatment (provider-to-provider care) | Is Open Intelligence a provider organization for this purpose? It is not assumed to be one. What treatment relationship must exist? | Treatment-purpose participation terms, provider agreements — separate pathway, not used by this adapter |
| Epic IAS (TEFCA) | Patient-facing app via Epic's IAS offering | Individual access | App registration, SMART authorization, organization discovery for Epic-connected sites | Epic IAS terms and any commercial terms — carried-forward pointer only, not reverified here |
| InterSystems Health Gateway | Network-access aggregation for participating healthcare-network workflows | Depends on the workflow it serves; verify whether a patient-facing IAS application is a supported use at all | Applicability to a patient-facing IAS app, supported purposes, organization coverage | Commercial terms for a patient-facing IAS application — explicitly unverified; marketing descriptions are not terms |
| InterSystems Health Connect / IRIS for Health / Unified Care Record | Integration, FHIR exchange, normalization, identity, provenance | Integration / exchange (not, by itself, a patient-access right) | Which role each product plays; do not conflate a gateway, an integration engine, and a record aggregator | Licence / commercial terms per product — unverified here |
| Health Gorilla (IAS use case) | Patient-facing app via Health Gorilla IAS | Individual access | IAS eligibility, matching, scope, completeness | IAS agreement and pricing — unverified here |
| b.well | Patient-facing access platform | Individual access (verify per product) | Product and purpose actually offered to this kind of app, matching and scope | Commercial terms — unverified here |
| Direct SMART/FHIR + patient-directed records requests | Patient app directly with each institution | Individual access, institution by institution | Per-institution registration, supported scopes, specialty artifact variation, refresh behaviour | Per-institution terms; no national completeness is implied by any single connection |

**Reading rule.** An ordinary API gateway (routing/policy) is not a
health-information-network access product, and exchange transport (FHIR/SMART,
C-CDA, HL7) is not source fidelity or permission to use data for every
purpose. Each row above stays **EVALUATE** until its exact product, purpose,
terms, and lawful access basis are confirmed with dated primary evidence.

## 3. Artifact coverage matrix: known-missing is not negative

`classify_coverage()` in `patient_access.py` enforces the vocabulary below.
A **negative** is evidence: a delivered source explicitly reports a finding
as negative, and it must cite its `source_document`. A **known-missing** is a
gap with a stated reason: the class is known not to be exposed by the source.
An **unknown** is neither — availability is not established. Conflating any
two of these would silently convert "we did not receive it" into "it was
ruled out", which is exactly the failure this boundary exists to prevent.

| Artifact class | Fixture status | Basis |
| --- | --- | --- |
| Encounter | present | `ENC-OI017-A` (Institution A) |
| Pathology | present, conflicting across specimens | `PATH-OI017-A` (specimen A) vs `PATH-OI017-B` (specimen B) — both current, conflict preserved |
| Molecular | known_missing | No molecular artifact delivered by either fictional institution; reason recorded in the manifest |
| Imaging report | present | `IMG-OI017-A` (report text only) |
| DICOM pixels / native imaging | known_missing | Report-only delivery; native pixels not exposed — not a negative imaging finding |
| Medications list | present | `MEDS-OI017-A` |
| Payer events | known_missing | No payer artifact delivered in this fixture set |
| Payer administration confirmation | known_missing | Medication list contains no administration confirmation; a list is not proof of administration |
| Original documents | present | Every fixture stored byte-identical with SHA-256 (see `EXPECTED_RESULTS.json`) |
| Amendments | present | `PATH-OI017-A@2` late correction; v1 superseded, history recoverable |
| Marker-A on specimen A, original report | not-reported, not negative | v1 says `not-reported`; only the amended v2 reports marker-A negative. The manifest records this explicitly so a reader cannot backdate the negative. |

**Source-specific missingness rule (for any later real evaluation).** Define
the reference inventory, retrieval window, denominator, adjudication method,
and source-specific missingness *before* comparison. Report unknown source
availability separately from retrieval failure and from data not exposed by
the source. Compare identical evaluation scopes, never unqualified vendor
totals.

## 4. Adapter contract (against the existing store — no second ledger)

Implementation: `src/open_intelligence/patient_access.py` +
two narrow hooks in `store.py` (`record_adapter_event`,
`quarantine_adapter_delivery`) that write only to the existing `events`
ledger and the existing `quarantine` table. Source bytes enter only via the
existing `import_report`; there is no `adapter_sources` or `patient_store`
table (asserted by test).

### 4.1 Envelope (required for every delivery)

| Field | Rule |
| --- | --- |
| `adapter_id`, `source_organization`, `source_system` | Nonempty; recorded on the acceptance event, never as a source |
| `case_id` | Target synthetic case; must already exist |
| `source_subject_ref` | Institution-local subject binding for this delivery (synthetic placeholder, never a real identifier) |
| `authorization.receipt_id`, `purpose`, `scope`, `granted_at`, `expires_at`, `revoked_at` | `purpose` must be `individual-access`; scope nonempty; `expires_at >= granted_at`; see §4.2 |
| `retrieved_at` | Retrieval date; see time semantics §4.3 |
| Raw bytes + SHA-256 | Original bytes are hashed (`hashlib.sha256`) and stored verbatim; the hash on the acceptance event must equal the stored source hash |
| `transformation` (optional) | Loss receipt, required when a transform is claimed and lossy (§4.4) |

### 4.2 Authorization receipt and revocation

* A receipt outside its window (`retrieved_at` outside
  `[granted_at, expires_at]`) is rejected; an expired receipt is rejected.
* A Treatment-purpose receipt is rejected for this adapter — different
  pathway, different eligibility and obligations (§2).
* Revocation is recorded as an `adapter_authorization_revoked` event in the
  existing event ledger. It blocks all future deliveries under that receipt.
  It does **not** delete history: previously imported source versions stay
  recoverable, exactly as an amendment supersedes rather than erases.
* This module builds **no durable authorization system**. A production
  deployment would need a separately authorized, durable authorization store;
  the in-memory binding/revocation state in this module is a test gate, not
  that system. That gap is stated here so it cannot be mistaken for a
  delivered auth system.

### 4.3 Time semantics (four distinct times, never collapsed)

| Time | Meaning | Rule |
| --- | --- | --- |
| `event_date` | When the clinical event occurred (source field) | `event_date <= issued_at` |
| `issued_at` | When the source issued this version (source field) | `issued_at <= retrieved_at` |
| `retrieved_at` | When the adapter retrieved the bytes (envelope field) | Inside the authorization window; `>= issued_at` |
| Authorization window | `[granted_at, expires_at]`, plus `revoked_at` | Retrieval must fall inside it and before any revocation |

Collapsing these — e.g. stamping retrieval as the event date, or an
amendment's issue date as the original event date — would corrupt
chronology and as-known-at replay. Amendments keep the original `event_date`
(the existing store already enforces this: an amendment cannot change report
type, event date, or specimen).

### 4.4 Transformation and loss receipts

* **Verbatim is the default.** The adapter imports the original bytes. A
  normalized projection is never stored as a source.
* A claimed transform supplies both field sets; the module computes the
  dropped fields and requires the declared receipt to match exactly.
* A lossy transform **without** a loss receipt is rejected and imports
  nothing (tested). A lossy transform **with** a receipt still imports the
  original bytes, and the receipt is recorded as an `adapter_loss_receipt`
  event listing `dropped_fields`, `truncated_fields`, and
  `cardinality_changes` (tested: the stored text is byte-identical to the
  original, not to any normalized form).
* Cardinality, negative/unknown, conflict, and duplicate behaviour must be
  preserved by any transform; a transform that merges two specimens, resolves
  a conflict, or converts `not-reported` into `negative` fails this contract
  even if it carries a receipt, because the receipt would describe a loss the
  ledger then hides. The current implementation enforces the receipt and the
  original-bytes rules; semantic merge detection remains a reviewer check
  (see §7, open items).

### 4.5 Identity: collision is quarantined, never merged

* First binding wins, per organization and per subject reference:
  `(source_organization -> source_subject_ref)` and
  `(source_subject_ref -> case_id)`.
* A delivery whose organization is already bound to a different subject
  reference, or whose subject reference is already bound to a different
  case, is rejected with reason `identity_collision`, written to the
  existing `quarantine` table, and recorded as an
  `adapter_delivery_quarantined` event. It never becomes a source (tested).
* The existing patient-mismatch quarantine (`import_report`, declared
  patient ≠ target case) is unchanged and complementary: it catches
  wrong-case bytes; the adapter binding check catches same-case-id
  collisions that the patient field alone cannot see.
* Duplicate byte-identical deliveries return `duplicate` with no new source
  version and no new event (existing store behaviour, tested through the
  adapter).

### 4.6 Amendments and invalidation

* An amendment must name the same document at its latest version
  (`Amends: DOCUMENT@VERSION`), keep type/event-date/specimen, and supersede
  the prior version; prior versions remain recoverable.
* Receipt of an amendment invalidates dependent snapshots (state `stale`)
  and reopens their questions, via the existing store mechanism — scoped to
  snapshots citing the superseded version only. A different specimen or assay
  does **not** supersede an earlier result; it is a distinct document whose
  conflict is preserved (tested with specimens A vs B).
* The same rule applies to the adapter path: the late correction fixture
  (`PATH-OI017-A@2`) supersedes v1 and stales a snapshot built on v1
  (tested).

## 5. Candidate comparison (comparison only — no selection)

All candidates remain **EVALUATE**. Scores below are qualitative contract
criteria for a future, separately authorized evaluation — not measurements.
"Unknown" means unmeasured in this PR, not "poor".

| Criterion | TEFCA/QHIN IAS | Epic IAS | Health Gateway | Health Gorilla / b.well | Direct SMART/FHIR |
| --- | --- | --- | --- | --- | --- |
| Completeness (artifact classes actually returned) | Unknown — must be measured per source | Unknown — Epic-connected scope only, must be measured | Unknown — verify IAS applicability first | Unknown — must be measured | Known to vary by institution; no national completeness implied |
| Provenance (raw bytes, source ids, specimen/assay links, time semantics) | Unknown — must be tested against the contract in §4 | Unknown | Unknown | Unknown | Varies by institution; test per site |
| False-match risk (identity collision handling) | Unknown — matching method and error handling must be evidenced | Unknown | Unknown | Unknown | Institution-local matching; collision handling per site |
| Loss (lossy transforms, field drops) | Unknown — loss receipts required by §4.4 | Unknown | Unknown | Unknown | Unknown per mapping |
| Amendment invalidation | Unknown — amendment semantics must be evidenced | Unknown | Unknown | Unknown | Varies by institution |
| Portability / exit path | Vendor switch must not change source/evidence contracts (§4) — untested against any live vendor | Same | Same | Same | Highest portability per connection, highest per-site burden |
| Reviewer burden | Unknown — depends on completeness and conflict rate | Unknown | Unknown | Unknown | High (per-institution variation) |
| Cost | Unknown — no pricing verified | Unknown | Unknown | Unknown | Per-institution effort, no vendor fee assumed |

**No candidate is recommended or rejected here.** A future selection would
need, per candidate: exact product and purpose, dated primary terms,
sandbox evidence against the §4 contract on identical fixture scopes, and a
scoped ADR. Until then, every candidate stays EVALUATE.

## 6. Recommendation (buy / build / partner)

**Hold: evaluate, do not buy, build, or partner yet.**

* **Build (done in this PR, synthetic only):** the adapter gate, loss
  receipts, collision quarantine, and revocation recording — against the
  existing ledger, with no live integration. This is the bounded build the
  issue authorizes.
* **Do not buy or partner yet:** no vendor product, purpose, terms, pricing,
  coverage, or matching performance has been verified to the standard in §1.
  Procurement on marketing material would violate the house rules on
  unresolved permissions.
* **Next step if real access is ever pursued:** a separately authorized
  evaluation — sandbox first, identical fixture scopes, per-source missingness
  defined in advance, reviewer-burden measured — followed by a scoped ADR.
  That evaluation is not authorized by this PR.

## 7. ADR decision: no ADR is warranted by this evaluation

Per issue #17, a bounded ADR is drafted only if evaluation warrants a
change. It does not: the existing `SourceArtifactStore`/`EventLedger`
contracts already provide immutable versioned sources, specimen anchoring,
quarantine, duplicate suppression, amendment-driven invalidation, and an
event ledger. The adapter gate in this PR is an *input validation layer* on
those contracts, not a change to them. The existing design is sufficient for
the synthetic evaluation; no architectural change is proposed, and no
existing module, backlog order, or decision is altered by this document.

## 8. Rights, terms, and operational restrictions

* All fixtures are independently authored synthetic text in the existing
  `OI-SYNTHETIC-REPORT/1` format. No licensed content is included: no NCCN
  text, no OncoKB content, no copied vendor demonstration, no real record.
* No third-party component is integrated by this PR, so no new dependency,
  licence, or asset obligation is introduced. The two store hooks are
  first-party code.
* Operational restrictions carried forward: no outreach, no real-data
  acquisition, no external service commitments, no clinical deployment, no
  EHR writeback (retrieval and writeback are separate pathways; writeback is
  not in scope), no licensing change.
* The source pointers below are carried forward from the 2026-10-31 research
  addendum; they were **not** freshly reverified in this PR and must be
  checked at their published version and effective date before any legal,
  regulatory, vendor-access, or licensing reliance.

## 9. Uncertainty ledger (dated 2026-10-31)

| # | Uncertainty | Status on 2026-10-31 | Evidence still needed |
| --- | --- | --- | --- |
| U1 | Actual institution coverage per candidate | Unknown | Dated primary evidence per candidate and site |
| U2 | Real-world patient matching performance / false-match rates | Unknown | Separately authorized representative study |
| U3 | Commercial pricing, rate limits, latency, liability, audit duties | Unknown | Applicable agreements; never infer from marketing |
| U4 | Whether Health Gateway supports a patient-facing IAS application | Unknown | Exact product/purpose confirmation from the vendor |
| U5 | Per-institution SMART/FHIR scopes and specialty artifact support | Unknown | Per-site registration and scope evidence |
| U6 | Amendment and refresh semantics per live source | Unknown | Sandbox evidence against §4.6 on identical scopes |
| U7 | Revocation propagation latency in any live system | Unknown | Vendor evidence; the synthetic gate records revocation instantly, which is not a live-system claim |
| U8 | Semantic merge detection for transforms (beyond receipt matching) | Open implementation gap | Reviewer check today; a future transform validator if transforms are ever built |

## 10. Fixtures and expected results

* Fixtures: `examples/patient-access/` (7 synthetic reports).
* Manifest: `examples/patient-access/EXPECTED_RESULTS.json` — per-file
  SHA-256, byte counts, the 11-step expected sequence, and the coverage
  classification. The manifest's coverage entry for marker-A is deliberately
  explicit: v1 `not-reported` is not a negative; only amended v2 is negative.
* Tests: `tests/test_patient_access.py` (13 tests) — verbatim hash,
  undocumented-loss rejection, receipted-loss original-bytes import,
  identity collision quarantine, cross-case subject reuse rejection,
  contradictory-specimen coexistence, late-correction invalidation,
  duplicate suppression, revocation blocking with history preserved,
  Treatment-purpose and expiry rejection, time-semantics rejection,
  negative-vs-known-missing classification, and no-second-ledger assertion.

## 11. What is NOT proved

* No real adapter was connected; no vendor was selected; no real patient
  data was accessed; no live EHR, QHIN, or payer system was exercised.
* The contract is untested against any live EHR. Sandbox or real-data
  behaviour — coverage, matching, completeness, refresh, pricing, revocation
  latency — remains entirely unmeasured.
* Passing these tests is not clinical validation, release clearance, or
  authorization to handle real data. The in-memory binding/revocation state
  is not a production authorization system.

## Sources (carried-forward pointers, not fresh verification)

* TEFCA RCE — https://rce.sequoiaproject.org/
* Epic TEFCA IAS developer documentation — https://open.epic.com/Home/Interoperate/TEFCA/IAS
* InterSystems Health Gateway — https://www.intersystems.com/products/healthshare/health-gateway/
* InterSystems Health Connect — https://www.intersystems.com/products/healthshare/health-connect/
* Health Gorilla IAS — https://www.healthgorilla.com/home/use-cases/ias
* HL7 FHIR ImagingStudy — https://hl7.org/fhir/R4/imagingstudy.html
* Repo research addendum — `docs/research/INTEROPERABILITY_ACCESS_RESEARCH_2026-10-31.md`
* Existing contracts — `src/open_intelligence/store.py` (`source_versions`, `quarantine`, `events`); backlog rows OI-005, OI-006, OI-012, OI-013, OI-014.
