# First-party canonical patient registry — initial operational contract

**Status:** reviewable implementation slice for the complete Open Intelligence platform, not a production-ready patient identity service.

## Why this belongs in the full system

EHR, oncology, LIS, pathology, RIS/PACS, genomics, medication, research and AI services must reference one authoritative patient identity. A source-adapter subject string or an existing synthetic CaseStore case ID is not a trusted person. This module establishes a separate first-party **identity-owner domain** with an opaque persistent patient ID and organization-qualified creation receipt; it does **not** replicate any clinical or source data.

## Implemented

- `PatientRegistry` owns `identity_patients`, immutable `identity_create_receipts`, and immutable `identity_domain_events` in one database connection. Patient IDs are non-identifying opaque UUID-based references, never a claim of verified human identity.
- `create_patient` is permitted only by an injected host authorization policy and commits patient, organization-scoped command receipt and origin event atomically. The same organization/request/actor/purpose returns the same patient; conflicting reuse fails.
- `get_patient` and organization-scoped `list_patients` fail closed without host policy. No unprotected HTTP endpoint is added.
- `suspend_patient` requires an expected version and an externally trusted policy decision. Suspension preserves history; it disables future `require_patient` resolution and never deletes a clinical record.
- `require_patient` and `append_event` are trusted **internal domain-host ports** compatible with the proposed first-party clinical encounter host protocol in [draft PR #74](https://github.com/OpenxIntelligence/open-intelligence/pull/74). The latter joins an owning domain transaction without committing it; the host cannot confer authority by itself.
- Unit tests cover transactional rollback, restart, immutable history, duplicate requests, scope denial and suspension.

## Explicitly not implemented

No legal identity verification, patient matching, demographic/PHI fields, consent lifecycle, verified practitioners, cross-organization federated patient identity, source-issuer registration, break-glass, proxy delegation, purpose-of-use evaluation, cryptographic auditing, database row-level security, encryption/key management, real-data authorization, clinical trust assessment or deployed API. The provided `authorizer` is a **contract requiring a trusted production service**, not the service itself. Internal host methods must never be exposed as public client methods. This is an operational foundation, **not a complete EHR or identity platform**.

## Alignment and next integrations

- Do not merge or replace the source identity gate from [draft PRs #51/#53](https://github.com/OpenxIntelligence/open-intelligence/pull/53). Their issuer/system/subject mappings must later resolve through reviewed authoritative patient/organization and source-reconciliation workflows.
- After the owner approves the host boundary, run the actual `ClinicalEncounters` domain from [draft PR #74](https://github.com/OpenxIntelligence/open-intelligence/pull/74) against this registry, verify permission denial, creation and encounter history across restart, and maintain one event journal/transaction owner.
- Add verified identity workflows and consent/authority services as distinct first-party domains. Real patient records must remain blocked until validated security/privacy and regulatory deployment requirements are satisfied.
- Integrate with transactional outbox/inbox from [draft PR #70](https://github.com/OpenxIntelligence/open-intelligence/pull/70) by using the same host connection at each domain transition, with issuer-qualified patient/source references and independent authorization checks.
- Public-facing UI must connect through authenticated APIs; patient creation is not an invitation to accept real PHI into today's synthetic-only application.

Canonical decisions: [Notion product direction](https://app.notion.com/p/40a3866f77ef81eb91a9c696198ed71b) and [domain contracts](https://github.com/OpenxIntelligence/open-intelligence/pull/49). No Next.js or third-party dependency was introduced.
