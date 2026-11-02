# OI-017 — Patient-directed access and lossless evidence boundaries (complementary research)

**Date:** 2026-10-31 (original); branch update 2026-11-02 (synthetic-only,
no live verification; external pointers re-listed, not freshly reverified).
**Status:** Complementary research + synthetic adapter contract. **Not** an adopted
architecture, vendor decision, implemented live integration, legal determination,
or clinical release. Every vendor/standard claim below that cannot be verified
from in-repo sources is labeled **UNVERIFIED (2026-11-02)** with a dated pointer.
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

| Pathway | Who acts | Purpose | Eligibility / role questions that must be answered before any real use | Commercial / legal obligations to verify | Status |
| --- | --- | --- | --- | --- | --- |
| TEFCA / QHIN Individual Access Services (IAS) | Patient-facing app via a QHIN / IAS provider | Individual access (patient-directed) | Is the app an eligible IAS participant? Which QHINs does the IAS provider connect? What identity proofing and patient matching does it perform? What scope and completeness does it actually return? | QHIN participation terms, IAS provider agreement, permitted-use and audit duties, pricing — UNVERIFIED (2026-11-02); pointer: RCE https://rce.sequoiaproject.org/ | EVALUATE |
| TEFCA / QHIN Treatment purpose | Provider organization via a QHIN | Treatment (provider-to-provider care) | Is Open Intelligence a provider organization for this purpose? It is not assumed to be one. What treatment relationship must exist? | Treatment-purpose participation terms, provider agreements — UNVERIFIED (2026-11-02); separate pathway, not used by this adapter | EVALUATE (out of scope for this adapter) |
| Epic IAS (TEFCA) | Patient-facing app via Epic's IAS offering | Individual access | App registration, SMART authorization, organization discovery for Epic-connected sites | Epic IAS terms and any commercial terms — UNVERIFIED (2026-11-02); pointer: https://open.epic.com/Home/Interoperate/TEFCA/IAS (carried forward, not reverified) | EVALUATE |
| InterSystems Health Gateway | Network-access aggregation for participating healthcare-network workflows | Depends on the workflow it serves; verify whether a patient-facing IAS application is a supported use at all | Applicability to a patient-facing IAS app, supported purposes, organization coverage — UNVERIFIED (2026-11-02) | Commercial terms for a patient-facing IAS application — UNVERIFIED (2026-11-02); pointer: https://www.intersystems.com/products/healthshare/health-gateway/; marketing descriptions are not terms. No selection of InterSystems is made or implied. | EVALUATE |
| InterSystems Health Connect / IRIS for Health / Unified Care Record | Integration, FHIR exchange, normalization, identity, provenance | Integration / exchange (not, by itself, a patient-access right) | Which role each product plays; do not conflate a gateway, an integration engine, and a record aggregator — UNVERIFIED (2026-11-02) | Licence / commercial terms per product — UNVERIFIED (2026-11-02); pointer: https://www.intersystems.com/products/healthshare/health-connect/ | EVALUATE |
| Health Gorilla (IAS use case) | Patient-facing app via Health Gorilla IAS | Individual access | IAS eligibility, matching, scope, completeness — UNVERIFIED (2026-11-02) | IAS agreement and pricing — UNVERIFIED (2026-11-02); pointer: https://www.healthgorilla.com/home/use-cases/ias | EVALUATE |
| b.well | Patient-facing access platform (exact product unidentified) | Individual access (verify per product — no product confirmed) | Exact product and purpose actually offered to this kind of app, matching and scope — unresolved, no primary pointer in-repo — UNVERIFIED (2026-11-02); the 2026-10-31 addendum names b.well without a link (see U10) | Commercial terms — UNVERIFIED (2026-11-02); no QHIN or vendor selected | EVALUATE |
| Direct SMART/FHIR + patient-directed records requests | Patient app directly with each institution | Individual access, institution by institution | Per-institution registration, supported scopes, specialty artifact variation, refresh behaviour — UNVERIFIED per site (2026-11-02) | Per-institution terms; no national completeness is implied by any single connection — UNVERIFIED per site (2026-11-02) | EVALUATE (comparison/fallback only) |

### 2.1 Evidence class per vendor/standard claim (2026-11-02)

Claim status vocabulary (from the 2026-10-31 research addendum): `source-stated`
(the vendor/standard publisher says so; not independently checked),
`independently-checked` (verified against dated primary evidence by this repo),
`hypothesis` (repo working assumption), `unresolved` (no evidence in this repo).
No claim below is `independently-checked` in this branch: no sandbox, no live
call, no agreement review was performed or authorized. Every status in the
table — `source-stated`, `hypothesis`, or `unresolved` — is therefore
**UNVERIFIED (2026-11-02)**: a `source-stated` claim repeats what the
publisher says without any in-repo check, and must never be read as
verification.

| # | Claim | Status (2026-11-02) | Pointer (carried forward, not reverified) | Falsification test |
| --- | --- | --- | --- | --- |
| C1 | A QHIN/IAS-provider path exists for eligible patient-facing apps | source-stated / unresolved for this app | RCE https://rce.sequoiaproject.org/ | Produce the applicable IAS participation agreement naming this app's role, or fail |
| C2 | Epic offers a TEFCA IAS path for patient-facing apps | source-stated / unresolved for this app | https://open.epic.com/Home/Interoperate/TEFCA/IAS | Register the app in the named sandbox and retrieve the documented scope, or fail |
| C3 | Health Gateway is applicable to a patient-facing IAS application | unresolved | https://www.intersystems.com/products/healthshare/health-gateway/ | Obtain exact product/purpose confirmation for a patient-facing IAS app, or fail |
| C4 | Health Connect / IRIS / UCR play integration/exchange roles distinct from network access | source-stated | https://www.intersystems.com/products/healthshare/health-connect/ | Map each product to its documented role; any conflation with IAS access fails |
| C5 | Health Gorilla offers an IAS use case for patient-facing apps | source-stated / unresolved for this app | https://www.healthgorilla.com/home/use-cases/ias | Produce the IAS agreement and sandbox evidence on identical fixture scopes, or fail |
| C6 | b.well offers a patient-facing access product usable by this app | unresolved | No primary pointer in-repo (see U10); first identify the exact product page | First identify the exact product page, then produce its purpose and terms, or fail |
| C7 | Per-institution SMART/FHIR supports the artifact classes in §3 | hypothesis, varies by site | Per-site registration and scope evidence (none collected) | Per-site scope retrieval against the §4 contract; any missing class is recorded known-missing, not imputed |
| C8 | Any candidate returns native DICOM, whole-slide, raw sequencing, or every payer event | unresolved (assumed absent until evidenced) | https://hl7.org/fhir/R4/imagingstudy.html (standard concept only, not a coverage claim) | Sandbox retrieval of the native artifact with source ids and time semantics, or record known-missing |

**Reading rule.** An ordinary API gateway (routing/policy) is not a
health-information-network access product, and exchange transport (FHIR/SMART,
C-CDA, HL7) is not source fidelity or permission to use data for every
purpose. Each row above stays **EVALUATE** until its exact product, purpose,
terms, and lawful access basis are confirmed with dated primary evidence.
The 2026-11-02 date records when the UNVERIFIED status was assessed, not a
verification event; a document edit date does not refresh its sources.

**Per-finding record (issue #17 evidence limits).** Decision status for every
claim C1–C8: **EVALUATE** — none accepted, none `independently-checked`,
no bounded change proposed. Existing-contract links: C1–C7 concern future
access products outside this repository (the §4 gate is product-agnostic
and connects to none of them); C8 maps to the §3 coverage vocabulary
enforced by `classify_coverage()`. Permissions for every claim: unresolved
(see the obligations column in §2 and §8). Missing behavior and failure
tests: the falsification test in each row above; contract-level failure
tests are listed in §10.1. Mapped to the issue's per-finding fields, each
claim C1–C8 records: existing module/contract (above — §4 gate or §3
vocabulary, product-agnostic); exact missing behavior (its falsification
test); source and date actually checked (pointer column — carried forward
from 2026-10-31, not reverified on 2026-11-02); permissions (obligations
column in §2 plus §8 — unresolved for every claim); proposed bounded
change (none); failure tests (falsification test plus the §10.1 contract
tests); decision status (**EVALUATE**).

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

**Marker-A reconciliation.** The manifest classifies marker-A as negative
only by virtue of `PATH-OI017-A@2`; the v1 report is `not-reported` and must
never be cited as a negative (pinned by the coverage test, which cites v2).

**Payer scope note.** No payer fixture bytes are authored in this set: the
payer classes are `known_missing` by design. The addendum's "payer event
without confirmation of administration" probe is represented by the present
medication list whose administration-confirmation finding is `not-reported`
(manifest step 7) — a list is not proof of administration — not by a payer
artifact. Issue #17 work package 3 requires no payer fixture, and none is
claimed.

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

An unknown target `case_id` raises `InvalidInput` on every path (the
ledger hooks validate the case before recording anything). On the import
path the first-wins binding slot is still consumed before that raise
(see §4.5, U9); rejection paths (revoked, undocumented loss, collision)
raise before reaching the binding step. Empty `adapter_id`,
`source_organization`, or `source_subject_ref`, an empty receipt scope,
and an expiry preceding the grant each raise before any import (tested).

### 4.2 Authorization receipt and revocation

* A receipt outside its window (`retrieved_at` outside
  `[granted_at, expires_at]`) is rejected; an expired receipt is rejected.
* A Treatment-purpose receipt is rejected for this adapter — different
  pathway, different eligibility and obligations (§2).
* A receipt carrying `revoked_at` rejects any retrieval at or after that
  date; a retrieval strictly before `revoked_at` still imports (tested).
  Separately, `revoke()` records an `adapter_authorization_revoked` event
  in the existing event ledger and blocks all future deliveries under that
  receipt id on that adapter instance. Neither form of revocation deletes
  history: previously imported source versions stay recoverable, exactly
  as an amendment supersedes rather than erases.
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
  dropped fields and requires the declared receipt's `dropped_fields` to
  match the computed set exactly (a mismatch raises and imports nothing —
  tested). A claim with only one field set raises `InvalidInput`
  (read-verified; no dedicated test pins this branch). A claimed
  transform with an empty computed dropped set and an absent or empty
  declared receipt is lossless: it imports with no
  `adapter_loss_receipt` event (read-verified; no dedicated test). A
  receipt declaring only truncation or cardinality changes still records
  a loss event, since the event follows the declared receipt.
  `truncated_fields` and `cardinality_changes` are carried on the
  receipt as declared; the module does not recompute them.
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
  (see §9, U8).

### 4.5 Identity: collision is quarantined, never merged

* First binding wins, per organization and per subject reference:
  `(source_organization -> source_subject_ref)` and
  `(source_subject_ref -> case_id)`. Bindings are **per adapter instance**
  (in-memory): two adapter objects sharing one store do not share
  bindings. A durable, shared binding store is part of the production
  authorization gap in §4.2, not a delivered behavior (see U9).
* A delivery whose organization is already bound to a different subject
  reference, or whose subject reference is already bound to a different
  case, is rejected with reason `identity_collision`, written to the
  existing `quarantine` table, and recorded as an
  `adapter_delivery_quarantined` event. It never becomes a source (tested
  with sequential real deliveries on one adapter instance, no
  private-state injection). A repeated identical collision delivery
  returns the same `quarantine_id` with a single quarantine row (existing
  store idempotency on case + bytes + reason); each repeat still records
  its own `adapter_delivery_quarantined` event (tested for the id, row,
  and source counts).
* The existing patient-mismatch quarantine (`import_report`, declared
  patient ≠ target case) is unchanged and complementary: it catches
  wrong-case bytes (tested through the adapter); the adapter binding
  check catches same-case-id collisions that the patient field alone
  cannot see. On the import-quarantine path the store's own
  `source_quarantined` event is the record; the adapter writes no
  separate adapter event there.
* Bindings are recorded **before** the import outcome is known, so a
  delivery that later quarantines (wrong-case bytes) or raises
  (unknown target case) still consumes its first-wins slot. That
  ordering is a documented limitation (see U9), not a claimed
  protection.
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
"Unknown" means unmeasured in this branch, i.e. **UNVERIFIED (2026-11-02)**,
not "poor". No candidate is selected, ranked, or rejected here.

| Criterion | TEFCA/QHIN IAS | Epic IAS | Health Gateway | Health Gorilla / b.well | Direct SMART/FHIR |
| --- | --- | --- | --- | --- | --- |
| Completeness (artifact classes actually returned) | Unknown — must be measured per source | Unknown — Epic-connected scope only, must be measured | Unknown — verify IAS applicability first | Unknown — must be measured | Expected to vary by institution (hypothesis — UNVERIFIED per site, 2026-11-02); no national completeness implied |
| Provenance (raw bytes, source ids, specimen/assay links, time semantics) | Unknown — must be tested against the contract in §4 | Unknown | Unknown | Unknown | Hypothesis: varies by institution (UNVERIFIED per site, 2026-11-02); test per site |
| False-match risk (identity collision handling) | Unknown — matching method and error handling must be evidenced | Unknown | Unknown | Unknown | Institution-local matching assumed (hypothesis — UNVERIFIED per site, 2026-11-02); collision handling per site |
| Loss (lossy transforms, field drops) | Unknown — loss receipts required by §4.4 | Unknown | Unknown | Unknown | Unknown per mapping |
| Amendment invalidation | Unknown — amendment semantics must be evidenced | Unknown | Unknown | Unknown | Hypothesis: varies by institution (UNVERIFIED per site, 2026-11-02) |
| Portability / exit path | Vendor switch must not change source/evidence contracts (§4) — untested against any live vendor | Same | Same | Same | Hypothesis: highest portability per connection, highest per-site burden (UNVERIFIED, 2026-11-02) |
| Reviewer burden | Unknown — depends on completeness and conflict rate | Unknown | Unknown | Unknown | Hypothesis: high (per-institution variation — UNVERIFIED, 2026-11-02) |
| Cost | Unknown — no pricing verified | Unknown | Unknown | Unknown | Hypothesis: per-institution effort; no vendor fee assumed (UNVERIFIED, 2026-11-02) |

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
contracts — implemented in this repository as `CaseStore` tables
`source_versions` (immutable versioned sources with SHA-256, specimen
anchoring, duplicate suppression, amendment supersession), `quarantine`
(wrong-subject and collision quarantine), and `events` (append-only event
ledger with amendment-driven invalidation of dependent snapshots) in
`src/open_intelligence/store.py` — already provide every behavior §4
requires. The adapter gate in this PR is an *input validation layer* on
those contracts, not a change to them: it adds no table, no canonical
state, and no authorization system (asserted by
`test_no_second_source_ledger_tables`). The existing design is sufficient
for the synthetic evaluation; no architectural change is proposed, and no
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

## 9. Uncertainty ledger (dated 2026-10-31; re-listed 2026-11-02 with no fresh verification)

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
| U9 | Durable, shared authorization/binding store (in-memory per-adapter bindings; slot consumed before import outcome) | Open production gap, documented in §4.2/§4.5 | Separately authorized durable authorization-store design and review; the test gate must never be mistaken for it |
| U10 | b.well exact product and purpose for a patient-facing app | Unresolved, no primary pointer in-repo | First identify the exact product page, then its purpose and terms (see C6) |

## 10. Fixtures and expected results

* Fixtures: `examples/patient-access/` (7 synthetic reports, all
  `OI-SYNTHETIC-REPORT/1`, all fictional, labeled everywhere; no PHI).
* Manifest: `examples/patient-access/EXPECTED_RESULTS.json` — per-file
  SHA-256, byte counts, the 11-step expected sequence, and the coverage
  classification. The manifest's coverage entry for marker-A is deliberately
  explicit: v1 `not-reported` is not a negative; only amended v2 is negative.
* Tests: `tests/test_patient_access.py` (22 tests) — verbatim hash,
  undocumented-loss rejection, receipted-loss original-bytes import,
  mismatched-loss-receipt rejection, identity collision quarantine,
  repeated-collision idempotency (same quarantine id), cross-case subject
  reuse rejection, contradictory-specimen coexistence, late-correction
  invalidation, unrelated-case isolation on amendment, duplicate
  suppression, revocation blocking with history preserved,
  Treatment-purpose and expiry rejection, retrieved-before-issued
  rejection, retrieval-before-grant rejection, revoked_at-window
  rejection, event-after-issue rejection, envelope validation (bad ids,
  empty scope, inverted window, unknown case), wrong-case-bytes
  quarantine, negative-vs-known-missing classification, manifest
  self-check, and no-second-ledger assertion. Tests were authored on the
  branch against the contract; this session could not execute them (hard
  limit: no shell/test runner), so no pass is claimed here — see the
  report. A loop review on 2026-11-02 re-checked every test body by
  reading only (no runner) against the contract in §4 and the manifest.

### 10.1 Work-package-3 coverage: every required scenario has a fixture and an expected result

Envelope-level scenarios (duplicate, lossy transform, revocation) reuse the
byte fixtures below with different envelopes; they need no separate bytes,
because the contract requires the original bytes in every case (§4.4). The
manifest records each as its own expected step.

| Required scenario | Fixture file(s) | Manifest step(s) | Test(s) |
| --- | --- | --- | --- |
| Multi-institution identity collision (same org, conflicting subject) | `oi017-encounter-inst-a.txt` then `oi017-collision-wrong-binding.txt` | Step 1 binds INST-A; step 6 rejects the collision (`identity_collision`, quarantined, no new source) | `test_identity_collision_is_quarantined_not_merged` |
| Multi-institution identity collision (same subject, second case) | `oi017-encounter-inst-a.txt` reused across `CASE-OI017` and `CASE-OI017-B` | Covered by the binding rule (subject→case first-wins, §4.5); no cross-subject leak | `test_cross_case_subject_reuse_is_rejected` |
| Contradictory specimen-linked pathology | `oi017-pathology-specimen-a.txt` (INST-A/SPEC-A) + `oi017-pathology-specimen-b.txt` (INST-B/SPEC-B) | Steps 2–3: both imported, conflict coexists, neither merged nor resolved | `test_contradictory_specimen_pathology_coexists_not_merged` |
| Late correction | `oi017-pathology-specimen-a-amended.txt` (`Amends: PATH-OI017-A@1`) | Step 4: v2 supersedes v1, dependents stale, history recoverable | `test_late_correction_supersedes_and_invalidates_snapshot` |
| Duplicate | `oi017-pathology-specimen-a.txt` delivered twice | Step 5: second delivery returns `duplicate`, no new version or event | `test_duplicate_delivery_creates_no_new_source` |
| Lossy transform, undocumented | `oi017-pathology-specimen-a.txt` with dropped fields and no receipt (envelope-level) | Step 9: rejected `transformation_loss_undocumented`, nothing imported | `test_lossy_transform_without_receipt_is_rejected_and_not_imported` |
| Lossy transform, receipted | Same bytes with a matching `TransformationReceipt` (envelope-level) | Step 10: original bytes imported; loss recorded as `adapter_loss_receipt` event, never as a replacement source | `test_lossy_transform_with_receipt_imports_original_not_normalized` |
| Revocation | Any delivery after `revoke(RCPT-OI017-1)` (envelope-level) | Step 11: rejected `revoked_authorization`; prior sources preserved | `test_revocation_blocks_future_delivery_but_preserves_history` |
| Report-only imaging (no DICOM pixels) | `oi017-imaging-report-only.txt` | Step 8: report present, pixels `known_missing` | `test_coverage_distinguishes_negative_from_known_missing` + manifest |
| Medication list without administration proof | `oi017-medications-inst-a.txt` | Step 7: list present, administration confirmation `known_missing` (a list is not proof of administration) | `test_coverage_distinguishes_negative_from_known_missing` + manifest |
| Loss receipt integrity (Pass-2 hardening) | `oi017-pathology-specimen-a.txt` with a mismatched declared receipt | Extension of step 9: declared ≠ computed raises, nothing imported | `test_declared_loss_receipt_mismatch_raises_and_imports_nothing` |
| Collision idempotency (Pass-2 hardening) | `oi017-collision-wrong-binding.txt` delivered twice | Extension of step 6: same quarantine id, one row, one source | `test_repeated_collision_returns_same_quarantine_id` |
| Verbatim import (bytes + hash + acceptance event) | `oi017-pathology-specimen-a.txt` | Stored text byte-identical to the fixture; stored SHA-256 equals the hash; the `adapter_delivery_accepted` event pins the same hash, receipt, and retrieval date | `test_verbatim_import_preserves_hash_and_original` |
| Unrelated-case isolation (Pass-2 hardening) | Inline second-case bytes (`CASE-OI017-B`) + `oi017-pathology-specimen-a-amended.txt` | Extension of step 4: A's amendment leaves B's source current and B's snapshot draft | `test_amendment_leaves_unrelated_case_unaffected` |
| Treatment-purpose rejection | `oi017-encounter-inst-a.txt` with `purpose=treatment` (envelope-level) | Raises `InvalidInput`; nothing imported (§4.2: different pathway) | `test_treatment_purpose_and_expired_receipt_rejected` (first half) |
| Retrieval after expiry | `oi017-encounter-inst-a.txt` with `retrieved_at=2027-01-05` past `expires_at=2026-12-31` (envelope-level) | Raises `InvalidInput`; nothing imported | `test_treatment_purpose_and_expired_receipt_rejected` (second half) |
| Retrieved-before-issued | `oi017-encounter-inst-a.txt` (issued 2026-01-13) with `retrieved_at=2026-01-10` (envelope-level) | Raises `InvalidInput`; nothing imported (§4.3) | `test_time_semantics_retrieved_before_issued_rejected` |
| Retrieval before grant (window start) | `oi017-encounter-inst-a.txt` with `retrieved_at=2026-01-15`, window opens `2026-02-01` (envelope-level) | Raises `InvalidInput`; nothing imported | `test_retrieval_before_grant_rejected` |
| Revoked_at receipt window | `oi017-encounter-inst-a.txt` with `revoked_at=2026-02-01` (envelope-level) | Retrieval on 2026-02-10 raises; retrieval on 2026-01-15 still imports (§4.2) | `test_revoked_at_receipt_rejected_after_revocation_only` |
| Event date after issue | Inline `TIME-OI017-X` bytes (`Event-Date: 2026-02-20`, `Issued-At: 2026-02-10`) | Raises `InvalidInput`; nothing imported (§4.3) | `test_event_date_after_issued_rejected` |
| Envelope validation (bad ids, scope, window, case) | `oi017-encounter-inst-a.txt` with blank ids, empty scope, inverted window, or `CASE-NOPE` (envelope-level) | Each raises `InvalidInput`; nothing imported; unknown case on the import path still consumes its binding slot (§4.1, §4.5, U9) | `test_envelope_validation_rejects_bad_ids_scope_window_and_case` |
| Wrong-case bytes quarantine | Inline `ENC-OI017-BX` bytes declaring `CASE-OI017-B`, delivered to `CASE-OI017` | Quarantined `patient_mismatch` via the store's own event; no source, no adapter event (§4.5) | `test_wrong_case_bytes_are_quarantined_not_imported` |
| Manifest self-check (meta) | `EXPECTED_RESULTS.json` + all 7 fixture files | Hashes, byte counts, steps 1–11, and coverage counts (6 present / 1 negative / 4 known_missing / 0 unknown) match disk | `test_expected_results_manifest_matches_fixtures` |
| No second ledger (meta) | Schema of the existing store | No `adapter_sources` or `patient_store` table; sources live only in `source_versions` | `test_no_second_source_ledger_tables` |

## 11. What is NOT proved

* No real adapter was connected; no vendor was selected; no real patient
  data was accessed; no live EHR, QHIN, or payer system was exercised.
* The contract is untested against any live EHR. Sandbox or real-data
  behaviour — coverage, matching, completeness, refresh, pricing, revocation
  latency — remains entirely unmeasured.
* Passing these tests is not clinical validation, release clearance, or
  authorization to handle real data. The in-memory binding/revocation state
  is not a production authorization system.
* This branch (2026-11-02) authored documentation and contract tests but
  executed no test runner, git, or shell verification in these sessions
  (hard limit), so no test pass is claimed here; the manifest's
  SHA-256/byte counts and all 22 tests must be re-run by a reviewer with
  a working shell. A loop review verified every test body and manifest
  parameter by reading only — that is a consistency check, not a run.

## Sources (carried-forward pointers, not fresh verification)

* TEFCA RCE — https://rce.sequoiaproject.org/
* Epic TEFCA IAS developer documentation — https://open.epic.com/Home/Interoperate/TEFCA/IAS
* InterSystems Health Gateway — https://www.intersystems.com/products/healthshare/health-gateway/
* InterSystems Health Connect — https://www.intersystems.com/products/healthshare/health-connect/
* Health Gorilla IAS — https://www.healthgorilla.com/home/use-cases/ias
* HL7 FHIR ImagingStudy — https://hl7.org/fhir/R4/imagingstudy.html
* b.well — no primary product pointer in-repo (unresolved, see U10/C6)
* Direct SMART/FHIR — per-institution terms and scopes; none collected (UNVERIFIED per site)
* Repo research addendum — `docs/research/INTEROPERABILITY_ACCESS_RESEARCH_2026-10-31.md`
* Existing contracts — `src/open_intelligence/store.py` (`source_versions`, `quarantine`, `events`); backlog rows OI-005, OI-006, OI-012, OI-013, OI-014.
