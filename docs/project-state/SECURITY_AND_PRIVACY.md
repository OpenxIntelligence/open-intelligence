# Security and privacy — observed controls and qualification gaps

**Assessment:** 3 November 2026 (America/New_York).  
**Environment:** independently authored synthetic development.  
**Code baseline inspected:** H1 [#276](https://github.com/OpenxIntelligence/open-intelligence/pull/276), `c154bfbc5f99f76801d37903959943659c0b6a71`, plus named project documentation. This document does not certify production security, legal compliance or clinical safety.

## Data and authority boundary

Current engineering must use independently authored fictional patients. Do not acquire or use real patient records, public-person medical datasets, pseudonymized replicas, credentials or restricted clinical content. Public narrative research can inform general workflow requirements. Earlier personal-data opt-in proposals are superseded. [Repository rules](../../AGENTS.md), [founder precedence](https://app.notion.com/p/40a3866f77ef8154bf15c7bb53138c9f).

The H1 application is intentionally limited to a synthetic environment and loopback-facing development workflow. Its operator-issued fixture credentials exercise software authorization; they are not verified people, patient consent, caregiver eligibility, professional credentials, source authenticity or authorization for real-data processing.

A source statement, model interpretation, operator verification return and professional clinical decision are distinct objects with different authority. A successful source receipt attests authorized preparation within its stated boundary; it does not prove delivery or irrevocable authorization of a downloaded copy.

## Status vocabulary and evidence

Use the eight assessment categories defined in [PRODUCT_REQUIREMENTS.md](PRODUCT_REQUIREMENTS.md). “Fully implemented and tested” below refers only to the stated synthetic behavior on its named branch. For the new integrated candidate, [PROJECT_STATE.md](PROJECT_STATE.md) records actual test outcomes; prior branch results do not close newly changed risks.

## Observed controls in the selected base

| Concern | Observed implementation / evidence | State and limit |
|---|---|---|
| Default authority | `DenyAuthentication` unless an explicit provider or synthetic access file is configured | Fully implemented and tested for supported fixture environment; no production provider selected. |
| Request authentication | Exactly one Authorization header; bounded bearer syntax; typed Principal; timezone-aware expiry; unavailable provider yields sanitized 503 | Fully implemented and tested for supported HTTP contract. |
| Fixture credential handling | SHA-256 token digests, constant-time comparison, bounded file read, duplicate-digest rejection, reread on every authentication | Fully implemented and tested for fixture adapter; no password/account/MFA/recovery system. |
| Grants | Actor, organization, purpose, action set and exact patient IDs | Fully implemented and tested for supported operations; caregiver/clinical authority missing. |
| Qualified case bindings | Canonical patient FK, organization/system/subject reference, guarded immutable identity, explicit revocation | Fully implemented and tested within synthetic binding contract; operator review label is not identity proofing. |
| Source integrity | Exact original bytes/hash/line/context, immediate amendment edges and full current findings validation | Fully implemented and tested for declared fictional report format; broader clinical fidelity unqualified. |
| Final authority | Supported source/import/receipt/brief operations revalidate current credentials/grants during prepared-response transaction | Partially implemented platform-wide; every newly composed response boundary must be verified separately. |
| Atomic receipts | Business/source access events commit with their transaction; failure withholds response and rolls back new effects | Fully implemented and tested for covered routes, not distributed revocation/delivery. |
| Browser credential storage | RegistrySession token held in memory; disconnect clears state and aborts pending requests | Fully implemented and tested for current client; no cross-device/session account service. |
| Browser transport | Same-origin API path; `credentials:'omit'`, `redirect:'error'`, `cache:'no-store'`; bounded JSON reads | Fully implemented and tested for current client; not a general browser threat audit. |
| Context isolation | Patient/case/credential/source change invalidates dependent views; sequence checks discard late responses | Fully implemented and tested for covered flows; new authored-question/packet convergence needs its own race tests. |
| HTTP development surface | Loopback Host validation, no-store responses, disabled interactive API docs, sanitized validation errors | Fully implemented and tested for development contract. Host validation is not a network firewall or production perimeter. |
| Ingress and response bounds | Existing request limiter; bounded source/JSON contracts; prepared complete response where implemented | Fully implemented and tested for covered routes, not all possible future formats. |
| Database immutability | Published migrations, FKs, guarded state transitions and append-only records | Fully implemented and tested within H1 schema; no global tamper-proof ledger certification. |
| Recovery | Existing disposable PostgreSQL acceptance and restart/dump/restore checks | Partially implemented operational evidence; no production RPO/RTO, power-loss, disaster-recovery or backup-access qualification. |

Code evidence: [access.py](../../apps/api/src/oi_api/access.py), [app.py](../../apps/api/src/oi_api/app.py), [config.py](../../apps/api/src/oi_api/config.py), [registry-client.ts](../../apps/web/src/registry-client.ts), [API documentation](../../apps/api/README.md).

## Authorization is operation-specific

Reading a patient identifier does not grant source read. Source metadata, original bytes, question history, Composer context, review-return writes and export each require their supported independent permissions. Patient/case/organization/purpose binding is checked alongside action grants.

For exported source briefs and packets, the request must recheck current access and source currentness. A cached preview is not an export authorization. Integrity/encoding/audit/commit errors must withhold a prepared response. Downloaded copies cannot be recalled by the application; UI wording and receipt semantics must not promise that they can.

An uncertain mutation response can be retried only with the original captured intent and idempotency key. A context or permission change must not automatically submit a new action. Existing successful history stays immutable, while new stale actions are refused.

## Production identity and consent staging

| Stage | Current position | Required next evidence |
|---|---|---|
| Local fixture authority | Implemented; synthetic grants only | Preserve fail-closed behavior and action-specific regressions during integration. |
| Trusted identity-provider adapter | Protocol seam exists; production provider missing | Select/review exact provider; issuer/audience/session validation, account proofing/recovery, secure enrollment and revocation. |
| Patient and caregiver relationship | Designed but not implemented | Attribute patient permission, proxy eligibility, scope, expiry, revocation, contested access and transitions of responsibility. |
| Clinician/workforce authority | Missing for production | Verified professional/organizational role and appropriate action scope; separate source verification from clinical signoff. |
| Consent and data-use policy | Designed but not implemented for real data | Care/sharing/research/model-processing purposes, versioned grants, withdrawal and retention obligations. |
| Production deployment | Blocked by external dependencies and qualification | Hosting/data roles/contracts, network isolation, keys, logging, backups, incident ownership and tested operational plan. |
| Clinical operation | Blocked by qualified intended-use and evaluation work | Function-specific clinical/ethical/regulatory assessment, accountable reviewers and measured performance. |

Keycloak, Ory, policy engines and related alternatives are research candidates, not installed or approved identity infrastructure. [Identity technology register](https://app.notion.com/p/40c3866f77ef80f891e5e446289c0484), [security source](https://app.notion.com/p/40a3866f77ef81e9848ec0a14a97b53d).

## Open security findings and integration risks

1. **Private PACS isolation remains unresolved.** Notion records a bounded PACSNode experiment where native OIDC rejected anonymous requests yet a valid wrong-patient modality token retrieved the original fictional image. Adoption is HOLD. H1 source-owned reads and a controlled archive port do not prevent direct backend bypass by themselves. Relevant separate owners: [#220](https://github.com/OpenxIntelligence/open-intelligence/pull/220), [#261](https://github.com/OpenxIntelligence/open-intelligence/pull/261), [#277](https://github.com/OpenxIntelligence/open-intelligence/pull/277). This is synthetic test evidence, not a real-patient incident.
2. **Composed response boundaries require current tests.** Initial inspection found DTO-only preparation in #276 review queue/return and the #280 packet donor. Actual JSON encoding can then happen after the last authority check. #278 (`b72560ac0f5e5005040b0fc660ce1650343611cf`) supplies existing bounded JSONResponse and same-case uncertain-return recovery repairs for selective reuse without images or migrations. The candidate must prove actual response preparation, final grant refresh and atomic receipt semantics. Other source/question/preflight DTO boundaries remain open; no all-route repair is claimed.
3. **Historical data-origin cleanup is incomplete.** Current policy and CI guards do not prove all historical artifacts/caches or legacy pathways were purged. Existing [issue #122](https://github.com/OpenxIntelligence/open-intelligence/issues/122) owns that work.
4. **Production audit and secrets infrastructure are unqualified.** Append-only application events do not establish full key custody, signed audit checkpoints, retention/deletion enforcement, log redaction or operational access control.
5. **Large-history performance is unqualified.** Full source-history checks run under existing locks. Test practical bounds before broad deployment; do not weaken integrity to meet an assumed latency target.
6. **Accessibility and user understanding are partially tested.** Keyboard/responsive checks are valuable evidence; they do not establish full WCAG 2.2 AA or comprehension by patients/caregivers.
7. **Reference and H1 environments differ.** A reference demo's browser mode or review toggle must never be represented as production authorization.

## Software, content and model rights

The adopted policy prefers permissively licensed, independently maintainable core components and requires exact artifact/version/intended-use review. Code, transitive dependencies, assets, fonts, data, terminology, model weights and hosted-service terms are separate subjects.

Current Notion registry query found **125 entries: 124 Not cleared, one Review in progress, none Cleared** in [Reusable Resources — Licensing & Validation](https://app.notion.com/p/52e843c6b0574713b66a5fb5d7f67ea3). This is a registry state, not a finding that every development component is unlawful. Existing branch-scoped dependency/notice receipts must be read for their precise development scope; they do not imply whole-product commercial distribution clearance.

The [Tier 1 catalog](https://app.notion.com/p/40c3866f77ef80a6846bdb98161b34cb) contains “Adopt” recommendations with incomplete or unverified evidence. Those labels cannot authorize installation or deployment. No new dependency is required for the selected integration.

NCCN H1 remains metadata/version/links only. Source licenses do not authorize entering PHI into unapproved services. Current synthetic development does not establish agreements or acceptable data flows for a live patient deployment.

## Required tests for this increment

Map checks to OI-006/007/009/010/013; preserve established tests and add only meaningful missing failure coverage:

- Authored question → current original anchor → saved question → brief/packet → recorded verification return → source amendment and explicit reassessment.
- Wrong patient/case/organization/purpose and independent export/return permission denial.
- Revocation/expiry or actor change during actual response construction and before commit.
- Encoding, event and commit failure produce no disclosure or false new success receipt.
- Same-intent retries recover one receipt; changed/stale intent cannot create duplicates.
- Patient/case/session/source changes discard late responses and asynchronous digest results.
- Uncertain return recovery survives permitted same-case refresh/import without automatic resubmission.
- Published migration files remain unchanged and the expected head remains explicit.

Record actual local skips, environment limitations and hosted results separately. Do not describe an unexecuted PostgreSQL or browser test as passed.

## Qualified release work remains open

OI-012 and OI-013 require actual intended-use/data-flow decisions and accountable review. This assessment does not decide jurisdiction, HIPAA/business-associate status, medical-device classification, consent sufficiency or contract obligations. Those questions depend on actual product functions, relationships and deployment. The current engineering route can advance reversible synthetic work while retaining these explicit limits.

