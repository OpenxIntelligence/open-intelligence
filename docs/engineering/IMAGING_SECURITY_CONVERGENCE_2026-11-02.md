# Imaging security convergence — existing-owner reconciliation

**Status:** bounded synthetic engineering integration, locally verified and independently reviewed.
Exact-head hosted verification is **pending**.
This work is unmerged; this increment has not changed `main` or approved deployment.
Owner references below were rechecked on 3 November 2026 for the 2 November workstream.

## Mission and scope

Open Intelligence is a first-party cancer-patient and biomedical intelligence
platform. The connected MVP joins canonical patient identity, preserved original
records, a source-linked Patient World Model, permitted scientific evidence,
investigation, sourced reports, human review and versioned reassessment. Imaging
must enrich that same patient/source authority. A successful synthetic PACS
roundtrip is one engineering result within that workflow, not a completed MVP,
clinical interpretation or backend-adoption decision.

This increment reconciles existing source-bound reads, the existing HOLD
classifier and the existing synthetic-only safety repair. It measures the gap
between an OI source-version guard and direct upstream access. It introduces no
parallel patient registry, consent system, source/evidence ledger or image-custody
authority.

## Exact inherited sources

| Existing owner | Pinned source used | Contribution and boundary |
|---|---|---|
| [PR #207](https://github.com/OpenxIntelligence/open-intelligence/pull/207) | `5d157f5c0cf3a57bbb021b30429b6e741b509db7` | Integration base: source-bound WADO reads and byte/pixel diagnostics; inherits #180 → #169 → #155 → #146. Its case/source checks are not caller authentication. |
| [PR #201](https://github.com/OpenxIntelligence/open-intelligence/pull/201) | `7c0edb8ab3c3d0afe67cfd56a43efc911de4108b` | Existing evidence classifier, synthetic receipt and adversarial tests. Extend this gate; retain `HOLD_NOT_APPROVED`. |
| [PR #137](https://github.com/OpenxIntelligence/open-intelligence/pull/137) | `533afd3ca6dd0c011e2e47397d3d5cae04e62512` | Existing retired-entrypoint policy, synthetic replacements, offline research workflows and bounded CI scanner. Selective source reuse; no wholesale branch merge. |
| [PACSNode upstream](https://github.com/knopkem/pacsnode/tree/e9b4334477a66967d290add9e0b9afa068f59dc0) | `e9b4334477a66967d290add9e0b9afa068f59dc0` | Isolated standalone research server; neither vendor adoption nor license/clinical clearance. |

The separate [RNA-only PR #168](https://github.com/OpenxIntelligence/open-intelligence/pull/168)
was compared at `f40f69d24cd4cd9e96c3013102d11b31d5a3c1fd`. The coherent #137 layer
also removes dormant personal-case defaults and retires local case-specific
analysis while retaining generic parser/statistics helpers. Original owners and
their histories remain intact. [The source-reuse receipt](RESEARCH_SAFETY_SOURCE_REUSE_2026-11-02.json)
verifies 11 byte-identical Python files and three inherited workflows changed only
to check out the exact pull-request head. [The dependency receipt](IMAGING_DEPENDENCY_RECEIPT_2026-11-02.json)
records the existing pinned pydicom license, including the dictionary BSD exception.
[The project inventory](PROJECT_STATE_RECONCILIATION_2026-11-02.json) is a selected-PR
snapshot, not an exhaustive repository/history/security audit.

## Active patient/source owners — do not duplicate

| Current draft owner | Observed head | Integration responsibility |
|---|---|---|
| [#209 — H1 React Records](https://github.com/OpenxIntelligence/open-intelligence/pull/209) | `aa44084866451ac106de9dc117c7e20224b77032` | Inspect-before-import and separately authorized current/historical originals over the canonical PostgreSQL source API. |
| [#213 — H1 Patient World Model/Journey](https://github.com/OpenxIntelligence/open-intelligence/pull/213) | `0855c36d86fed71d8806ae246804b36d2d872992` | Source-derived PostgreSQL projection and React Journey, directly stacked on #209. Its context fingerprint is freshness evidence, not permission to execute Composer. |
| [#214 — H1 source-read authority](https://github.com/OpenxIntelligence/open-intelligence/pull/214) | `35e132245b8294ca76af5e81a74a2dda886ffb59` | Reauthentication, patient/organization/purpose checks, original-context integrity and durable disclosure-authorization receipts in the existing #187 source owner. |
| [#215 — PDF/workflow reference](https://github.com/OpenxIntelligence/open-intelligence/pull/215) | `3be1106b5cd34523c4746e2df6f123048beb5659` | Separate SQLite behavioral-reference integration preserving PDF/manual provenance through patient record, questions, evidence and review. It is not the H1 PostgreSQL source owner. |

All four were open, draft and unmerged when checked. Their independent receipts
do not establish acceptance of this combined branch. #215 also identifies an
overlapping H1 World Model contract in [#216](https://github.com/OpenxIntelligence/open-intelligence/pull/216);
reconcile those source-owner response contracts before mounting another route.
Received-record reconciliation remains with #193. None of these owners is
silently replaced or claimed as integrated by this imaging increment.

## Bounded implementation and review

- Preserve #207's exact source/SOP/object/pixel checks and negative regressions.
- Observe direct anonymous WADO behavior after an OI report amendment; record
  bounded status/digest evidence without publishing response bodies or objects.
- Extend #201's classifier with source-bound receipt consistency and measured
  network-confinement evidence. Optimistic booleans cannot grant adoption.
- Run the pinned backend with fresh disposable storage in a **fresh Linux
  network namespace with loopback only**. Upstream HTTP and DIMSE wildcard
  listeners are confined by that namespace; they are not converted to loopback
  listeners through a purported bind-host setting. Final hosted confirmation of
  the confinement and direct-access observations remains pending.
- Reuse #137's disabled direct/CLI personal-data paths and fictional-only CI;
  retain an honest distinction between static scanning and runtime enforcement.

**Review checkpoint:** all five findings were corrected and independently re-reviewed.
Adversarial tests reproduced false authorization from anonymous denials, consistently
wrong source lineage, and lost observations on a late confinement failure before
the fixes. The module CLI invocation and configuration artifact name were corrected
and verified. No critical or important issue remains within those reviewed paths.

| Final acceptance evidence | Current state |
|---|---|
| Combined local application regressions | 316 run: 315 passed, one explicit process-namespace visibility skip; 33.860 seconds |
| Research under outer socket/HTTP denial traps | 204 run: 191 passed, 13 optional HDF5 skips (`h5py` absent); zero outer network attempts |
| Pinned isolated pydicom image/pixel/source integration | 8 passed; no optional codecs added |
| Source-dialog JavaScript regressions | 16 passed |
| Static CI boundary scan / all workflow YAML / shell syntax / whitespace | Passed / 8 parsed / passed / passed |
| Exact-head hosted synthetic suites and real pinned-PACS evaluation | **Pending** |
| Kernel-visible HTTP/DIMSE confinement and bounded direct-access receipt | **Pending final verification** |
| Independent closure of all five review findings | Complete; reviewer reran 16 gate and 6 wrapper tests, all passed |
| Merge, deployment, clinical validation and vendor/rights adoption | **Not approved or performed** |

## Limits that the receipt must preserve

The current receipt/fixture schema is **test-only**. It is not an authoritative
original-image ingestion record and cannot prove that an SOP belongs to an
authorized patient. Future original-object custody must join the existing H1
patient/case/source transaction and immutable source/version/hash authority,
with source-owner review; do not create an imaging-specific replacement ledger.

No actual actor/tenant/consent/purpose authorization is added to PACS here.
Namespace isolation confines the experiment; it does not authorize users or
enforce patient grants. An amended report can invalidate OI's binding while the
upstream object remains retrievable. Direct-access observations must retain
that distinction, including failures and unavailable evidence.

QIDO media-type compliance, full DICOMweb conformance, transcode/codec behavior,
durable operational recovery and complete source/dependency/asset rights remain
separate gates. The upstream remains **RESEARCH / HOLD**. There is no production
PACS, clinical image interpretation or medical efficacy claim.

Only independently authored fictional inputs are permitted. No real patient
records, genomics, images, named-person data or patient-derived synthetic cases
are used. This repair does not prove that historical commits, Actions artifacts,
caches, old result documents or external copies have been purged. The CI scanner
recognizes known source patterns; it is **not a firewall**, exhaustive data
detector or runtime authorization mechanism.

## Connected delivery next

The next product seam belongs to the existing H1 owners: reconcile #209/#213/#214
and overlapping projection contracts, then carry exact original provenance and
current permissions into the existing governed investigation/report/review
contracts. Use #215's PDF/manual provenance and amendment behavior as migration
evidence, not a competing store. Acceptance should include one fictional T0
source → question → permitted evidence → report/review, followed by amendment or
revocation → affected work withheld/stale → separate T1 reassessment with T0
history preserved. This increment does not claim that connected seam is complete.

## Canonical records and atlas owners

Update these existing records with the final commit, exact runs, correction
history and remaining HOLD conditions; do not publish a replacement architecture
or another component/adoption register:

- [Engineering Roadmap and Validation Evidence](https://app.notion.com/p/40a3866f77ef8197ae65e727c8907eb3)
  and [living Engineering Progress](https://docs.google.com/document/d/1Zbn-8Z5fABdGrJa5W0kSh4ojSVFvd1ddXdvW6pHr9gA/edit).
- [Technology and Component Architecture](https://app.notion.com/p/40a3866f77ef811c969fc38e95027ec2),
  [existing Master Research Atlas](https://docs.google.com/document/d/1rDcbE4BWOYFws-TAm1oGGQFb9gJVle1WxUHFn_2SnqM/edit)
  and the existing [backend rights owner #134](https://github.com/OpenxIntelligence/open-intelligence/pull/134)
  and [technology-atlas/bake-off owner #135](https://github.com/OpenxIntelligence/open-intelligence/pull/135).
- [OI-17 rights and release policy](https://app.notion.com/p/40a3866f77ef815a97d5e016ededf5b9),
  [Reusable Resources register](https://app.notion.com/p/52e843c6b0574713b66a5fb5d7f67ea3)
  and [existing Imaging Backend Decision Gate](https://docs.google.com/spreadsheets/d/1QnrvNBasHSzQa7goGfolIR-kt1gzMrmpO7__CYIzxT4/edit#gid=963927).
- [Integration Contracts and living research questions](https://app.notion.com/p/40a3866f77ef8122b08bcdc16de89876)
  and [Scientific Evidence/Molecular Intelligence](https://app.notion.com/p/40a3866f77ef81bd9b5de0234d9fbf7b).

The accepted H1 stack and Next.js exclusion remain unchanged. Technical test
evidence, source rights, actor authority, clinical review and release approval
remain distinct decisions.
