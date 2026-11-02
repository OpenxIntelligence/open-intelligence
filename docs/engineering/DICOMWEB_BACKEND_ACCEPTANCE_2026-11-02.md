# Open Intelligence — DICOMweb Backend Acceptance Contract

**Status:** Executable *synthetic-only* contract candidate. **Not** a DICOMweb service, installed viewer, image decoder, clinical imaging result, or vendor decision. This work supplements existing OI-17 licensing and [backend candidate evaluation #135](https://github.com/OpenxIntelligence/open-intelligence/pull/135), [pinned rights evidence #134](https://github.com/OpenxIntelligence/open-intelligence/pull/134), and [dependency declaration inventory #127](https://github.com/OpenxIntelligence/open-intelligence/pull/127). It does not duplicate their inventories.

## What an imaging backend must do

A viewer is **not** a PACS. The eventual first-party imaging domain needs actual DICOM object acquisition/ingest, study/series/instance identity, QIDO-RS query, WADO-RS retrieval, STOW-RS storage, authentication and patient/case binding, original bytes and metadata provenance, radiology reports and amendments, legal and technical audit, and validated pixel processing where appropriate. Never silently equate a radiology text report with raw image access.

## Executed boundary in this PR

`src/open_intelligence/imaging_backend_contract.py` accepts **independently authored fictional QIDO-style metadata objects** and a case identifier. Each row supplies an *out-of-band fictional binding* to a current imaging report source version in the **existing** `CaseStore` ledger. It validates typed DICOM tag structures, Study/Series/SOP UIDs, modality, calendar StudyDate, report-source event date consistency, case isolation, study-to-series consistency, no duplicate instances, and superseded source refusal.

A successful result records original source ID, version, SHA-256 and dates, and explicit flags stating that **no network QIDO, WADO retrieval, STOW storage or image processing occurred**. An empty candidate response is `not_provided`, not 'no disease'. No identifier from DICOM PatientName/PatientID acts as authorization. The case binding is not production patient reconciliation; discordant real report/study dates need review rather than forced equality.

Tests: `tests/test_imaging_backend_contract.py` (9 tests) cover exact study/series/instance inventory, original source anchors, cross-case refusal, report amendment, duplicate SOPs, conflicting series/study identity, invalid UIDs, incompatible dates/modalities, unknown vs negative and no write to the canonical ledger.

## Shortlist — strictly research, not adopted

| Component | Source-level evidence | Functional use | Decision |
| --- | --- | --- | --- |
| OHIF Viewers | [MIT declared upstream](https://github.com/OHIF/Viewers) | Viewer, lesion exploration and review UI; **not** backend storage | EVALUATE (bundle/asset/license and clinical tests outstanding) |
| Cornerstone3D | [MIT license](https://github.com/cornerstonejs/cornerstone3D/blob/main/LICENSE) | Rendering and viewport tools | EVALUATE, not auto-PACS |
| SimpleITK | [Apache-2.0 official statement](https://simpleitk.org/about.html) | Image processing/registration | EVALUATE; no raw pixels in this test |
| ITK | [ITK upstream source](https://github.com/InsightSoftwareConsortium/ITK) | Native image algorithms | EVALUATE; binary and third-party utilities review |
| dcm4che | [MPL/GPL/LGPL choices in official parent POM](https://github.com/dcm4che/dcm4che/blob/master/pom.xml) | Comparative DICOM toolkit | HOLD under strict permissive policy |
| Orthanc | GPL/AGPL plugin concerns recorded in canonical OI-17 | Comparative PACS reference | HOLD without explicit exception |
| OpenELIS | MPL-2.0 indicated in OI-17 | Separate **clinical LIS**, not imaging storage | HOLD; accredited clinical validation distinct |

**A permissive root license is not adoption clearance.** Verify exact release/commit, license file, module-specific code, codecs, model weights, DICOM image data rights, transitive dependency SBOM, security and production distribution before selection.

## Next real backend bake-off (not yet implemented)

Run the same acceptance inventory through one version-pinned commercially cleared candidate provider using **independently authored synthetic DICOM objects**. Require:

1. QIDO query yields correct patient-bound study, series and SOP identities; cross-case / multi-tenant requests are denied.
2. WADO returns the exact original, authorized SOP object and digest; unavailable raw pixels must be explicit.
3. STOW writes and retrieves an authorized object with receipt; duplicate and amendment rules are idempotent, never inferred from demographics.
4. Report-to-study linkage remains anchored to original source version and correct episode; an amendment invalidates affected derived results without erasing history.
5. Viewer opens authorized images and handles loss/error; measurement/annotation pipelines store coordinate frames, methods, versions and limits, and are clinically qualified separately.
6. Record exact license+dependency+codec/media notices, SBOM, logs without PHI, encryption and resource limits, performance/failure recovery, and regulatory intended-use assessment.

Keep the platform architecture modular and first-party, retain the current H1 synthetic-only clinical restrictions and no-Next.js decision. No vendor has been chosen by this contract; never claim it handles real patients.