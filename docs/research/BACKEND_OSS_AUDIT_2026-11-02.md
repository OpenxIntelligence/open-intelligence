# Backend open-source evidence batch — 2 November 2026

**Status: research / approval pending.** This is an addendum to the accepted Notion **OI-17 Open-Source & Commercial Freedom Policy**, the existing Notion Tier-1 catalog, and Google Sheets **OI Open-Source Technology & Licensing Registry** (tab: Backend Audit 2026-11-02). It is **not** an alternate architecture, production bill of materials, or dependency approval.

## Scoped evidence and outcomes

The companion JSON contains **9 candidate repositories with pinned commit SHA and root LICENSE blob SHA actually fetched from the official repositories**. The Python verifier only checks structural completeness, provenance consistency, non-duplication and that no candidate is accidentally marked cleared or adopted. It does not fetch code or grant commercial rights.

The wider Google Sheets audit tab contains **44 backend candidates** from repository-level GitHub metadata and selected primary-source license checks, across EHR/FHIR, LIS, PACS/viewers, pathology, imaging algorithms, genomics, AI/ML, workflow, database, search, authorization and synthetic data. Many entries have an API-reported SPDX or incomplete license check, **not full root-text verification**. A blank/NOASSERTION result means HOLD, not safe.

### Important differences in the current first pass

- **FHIR clinical core:** Medplum and HAPI FHIR root LICENSE texts are Apache-2.0; serious evaluation requires exact server packages, notices, Redis/JPA dependencies, tenant/authority scope, performance, and whether they are adapters versus a primary clinical source. No selection.
- **DICOM and imaging:** OHIF root MIT and highdicom root MIT; pydicom root MIT with additional BSD notice for GDCM-derived dictionary components; SimpleITK root Apache-2.0. These cover **different roles** (viewer, DICOM object/metadata, image computation), not a complete PACS.
- **Pathology:** TIAToolbox source code BSD-3; root LICENSE explicitly warns that model weights are separately licensed. Pretrained models are NOT cleared.
- **Held outside strict permissive inclusion:** dcm4che root MPL 1.1 and other GPL/LGPL source alternatives, and legacy OpenELIS root MPL-2.0 (historically end-of-life); legal exceptions and current project/release reviews required.
- **Orthanc:** official project says GPLv3+ core and some AGPLv3+ plugins. It was not imported into the pinned manifest. Keep only as research reference pending explicit exception.
- **Other candidates:** Keycloak, OpenFGA, OPA, Temporal, Nextflow, PostgreSQL, DuckDB, FastAPI/Pydantic and related packages require their own exact source/build+SBOM and benchmark before adoption. Github metadata alone does not establish their release suitability.

## Work package before any new dependency
1. Select one **synthetic-only interoperability vertical slice**: validate source-version-preserving FHIR mapping with one simple adapter and a loss receipt, without creating a second patient identity or source record.
2. Independently resolve exact released package/commit, root and component license, lockfile/BOM, native libraries and optional plugins, any model/dataset/terminology rights, maintenance/security history and commercial deployment terms.
3. Compare a simpler first-party Python solution with Medplum/HAPI/Google fhir-py. Include wrong-subject, wrong-specimen, corrected report and as-known-at controls, audit and no network patient-data egress.
4. Apply OI-17 and qualified human architecture/legal/clinical review. **Only then** make an approved and isolated integration PR. No automatic merge or real patient data.

## Verification caveats
- This research-only manifest is not an SBOM for an installed stack. No dependency is installed or selected.
- Snapshot is from 2 November 2026; upstream rights/versions may change after commit.
- Root LICENSE checks do not cover non-code or third-party rights. The validator cannot perform legal interpretation.
- Treat any future clinical use, PACS image interpretation, laboratory result release, genomic interpretation or medicine workflow as a separately qualified function.
