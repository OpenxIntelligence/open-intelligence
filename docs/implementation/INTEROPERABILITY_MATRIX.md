# Interoperability implementation matrix

Current repair: additive `0022_lab_citation_source_scope` now aligns the database
guard with the existing structured-source snapshot and preserves published 0021.
The reviewed-document mismatch was reproduced in hosted PostgreSQL run
42096046609 before repair. The earlier source inspection below records the
pre-repair boundary; final repaired-head PostgreSQL/browser/recovery acceptance
is tracked in draft [#542](https://github.com/OpenxIntelligence/open-intelligence/pull/542).

Updated 2026-11-05. Scope: accepted main
`f188aecc70f3415741dac0e7dd5bf3f2d9fd02a9` and candidate code
`3dd9811738e222274aa2c9e03edeff8104d64d53`. “Implemented” below means a
bounded synthetic software contract, not clinical interoperability qualification.
The candidate still needs the [release acceptance](RELEASE_ACCEPTANCE.md) gates.

## Implemented boundaries and later work

| Surface | Accepted main | Candidate / reusable owner | Later work and acceptance evidence |
|---|---|---|---|
| Patient and external subject identity | Canonical PostgreSQL patient registry and qualified patient/case binding | Preserved; `postgres_registry.py`, `case_bindings.py`, `sources.py` | Verified external organizations/people and reviewed patient matching; reject wrong patient, issuer/system collision and revoked binding without demographic auto-merge |
| Source custody and amendments | Exact originals, digests, versions, predecessor links and current-source checks | Preserved in `sources.py`, `source_integrity.py`, `laboratory_fhir_store.py` | Every new adapter must retain original bytes and a bounded transformation/loss receipt; prove duplicate, delayed, conflicting and amendment handling |
| FHIR R4 laboratory preview | Bounded JSON collection Bundle: one Patient, one Specimen, 1–16 final Observations, optional final DiagnosticReport | `laboratory_fhir_r4.py`; local `urn:uuid` references resolved inside the bundle | Broader resource forms/statuses/extensions need an explicit profile and refusal/loss tests; no silent dropping of clinically meaningful fields |
| FHIR laboratory persistence | Same source owner; persistence requires a final DiagnosticReport and qualified subject mapping | `laboratory_fhir_store.py`, `laboratory_fhir_routes.py`; immutable source identity and explicit latest-predecessor amendment | Prove exact bytes/hash, specimen/time identity, idempotent retry, final authority and restoration for each extension; this is not a general FHIR REST server |
| Laboratory values/missingness | Preserves reported numeric decimal text plus declared unit, or explicit supported data-absence reason | Existing laboratory source projection and `laboratory-fhir-view.tsx` | Never infer absent as negative/zero. Expand value types only with source fidelity and clinically reviewed semantics |
| LOINC/UCUM | Declared systems and bounded code syntax; no code-set lookup or unit conversion | Same parser; records source codes and units | Acquire/version permitted terminology artifacts, validate code membership and value sets, record mappings and uncertainty; qualify any conversion separately |
| Question-source identity | Text questions and resource-based laboratory questions have existing owners | Candidate `question_anchors.py` makes the variants explicit and strict, preserving external payloads/hashes | Keep patient/case/source/version/digest plus exact line or Observation/Specimen/Report references; exercise coercion, mixed variants and frozen compatibility outputs |
| Laboratory question citations | Durable questions on main | Candidate preserves citation metadata links/reports and adds transaction-wide freshness guard `0021_lab_citation_freshness`; source review found its reviewed-document scope mismatch | Repair with a follow-up migration; prove reviewed-document import permits a new link/retry while independent structured import refuses it, then run concurrency/history/rights tests; bibliographic metadata is not claim appraisal |
| Generic FHIR metadata/admission kernel | Not present in inspected main | #427 merged into a separate integration lineage; its `fhir_kernel.py` and `/v1/fhir/metadata` route are absent from candidate | Reconcile source-only Patient/Observation/DiagnosticReport/Provenance/AuditEvent admission with existing custody and authorization; generate claims only for actually mounted/verified behavior |
| US Core / mCODE | No general package/profile validator established by these owners | #427 declares US Core 9.0.0 / R4 as not loaded; this branch is not integrated | Select exact release, acquire permitted artifacts, record hashes, validate profiles/terminology and loss, test mappings against typed oncology sources; no present conformance claim |
| SMART/OIDC/external FHIR API | Synthetic local bearer fixture, not SMART authorization | No new external authorization or FHIR resource CRUD in this consolidation | Qualified identity/delegation/consent, issuer/audience/scope checks, source entitlements, refresh/revocation and protected endpoint evaluation before connecting a real service |
| Encounters and notes | Connected route owner absent from pinned main | Candidate `encounter_routes.py`, shared `clinical_encounters.py`, PostgreSQL adapter and `0019_ehr_encounters` | External Encounter/DocumentReference/Composition mappings need explicit provenance and version policy. Draft-note save is not a medical signature or credential verification |
| Oncology episode exchange | Source-reported oncology labels and grouping | Preserved; typed episode registry remains Phase 1 work | Separate primaries, metastases, uncertainty, recurrence and later new primaries; link each reported/reviewed assertion to versioned sources. Qualify mCODE mapping after the domain increment |
| Ordinary text/PDF | Existing reviewed-document originals, extraction rendition and manual selections | Preserve `reviewed_documents.py` and reference document/PDF owners | #466 harness is unintegrated; qualify reading order, scans/OCR, rotation, tables and associations against originals before claiming extraction accuracy |
| DICOM/image custody | Source-owned bounded CT original custody and archive interface | Preserve `images.py`, `dicom_integrity.py`, `archive_socket.py` | Current parser is one explicit-VR little-endian, 16-bit MONOCHROME2 CT frame. General DICOMweb/PACS, other modalities and diagnostic interpretation require separate qualification |
| Conditions, medications, pathology, genomics and analytics | Some source/report context is representable; complete typed clinical exchange is not established | Extend current patient/source owners in mandate order | Versioned domain contracts and terminology, specimen/assay context, corrections, output provenance and authorized export; OMOP/analytics stays a derived projection rather than another operational record |

API module paths above are under `apps/api/src/oi_api`; PostgreSQL registry,
clinical domain/adapter and document/PDF reference modules are under
`src/open_intelligence`; web paths are under `apps/web/src`.

## Adapter completion contract

For each new exchange increment, record:

1. Exact standard/package/profile and terminology versions, permitted artifacts,
   local hashes and supported resource/status/extension subset. FHIR R4 is the
   existing lab exchange contract, not a permanent internal clinical domain model.
2. Qualified source organization/system/issuer, logical and version identities,
   patient/case binding, specimen/assay and event/issued/received times. A source
   Patient resource cannot choose or authorize its destination patient.
3. Original bytes, normalized projection, omissions/rejections and transformation
   provenance. Preserve unknown, pending, not performed, indeterminate, conflicting
   and negative states independently.
4. Authorization for import/read/original/export, actual response preparation,
   final current-grant checks, deterministic retry and audit rollback. A format
   validator does not provide these controls.
5. Domain/API/database/component/browser checks, populated migration/restart/
   restore evidence, and independent review on the final combined revision.

#427's observed merged status, older donor green checks and standards terminology
in documentation do not establish support in accepted main. No profile package,
terminology service, external clinical connection or runtime dependency is adopted
by this matrix. No independent clinical validation is established.
