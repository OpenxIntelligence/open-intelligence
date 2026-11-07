# Connecting the full product and permissive accelerators

Construction companion to the existing [engine boundaries](MODULAR_ENGINE_BOUNDARIES.md),
[execution backlog](../EXECUTION_BACKLOG.csv), and issues
[#604](https://github.com/OpenxIntelligence/open-intelligence/issues/604),
[#100](https://github.com/OpenxIntelligence/open-intelligence/issues/100),
[#102](https://github.com/OpenxIntelligence/open-intelligence/issues/102) and
[#111](https://github.com/OpenxIntelligence/open-intelligence/issues/111).
This is an integration map, not a replacement architecture or a completed-platform claim.

Inspected connected baseline: `2e37d7579f3d748dfe2918a1ec4d02872e0e625c` (#602).
Semantic contract reused from #606 at `81238aab8ea581e68ef8c465ce9cdeff388ef4e2`.
The independent patient-access work in #611 and diagnostic work in #608/#610 remain
separate owners/branches to reconcile, not capabilities claimed by this increment.

## Where the work belongs

| Capability | First-party backend responsibility | Connected frontend responsibility | Accelerator and present status |
| --- | --- | --- | --- |
| Identity, consent, human/animal identity, organization and purpose | Existing registry, access and case-binding owners; distinguish guardian/owner authority from clinical consent | One selected subject/case across all screens; current grants and consent scope visible | Existing FastAPI/Pydantic/PostgreSQL stack; #611 grant persistence separate; complete consent remains unfinished |
| Records, labs, visits, pathology and molecular findings | Existing source versions, specimen/assay/date attribution and domain owners | Existing Visits/Labs/Imaging/Pathology/Molecular surfaces; source receipt and amendment history | Existing code-only pydicom, pypdf, bounded FHIR adapter; no general LIS/PACS/EHR completeness claim |
| Semantic context and Patient World Model | Versioned identifiers and source anchors, separate knowledge kinds and evidence states | Consistent classifications and source inspection | This increment connects a read-only semantic projection; editable ontology mappings and derived computation ownership still pending |
| Living Patient: Spatial / Clinical / Compare | Subject-specific geometry and spatial transforms; separate reference anatomy, measured patient information and hypotheses; species applicability | Shared time/source selection, linked views, explicit unsupported scales | Three.js (MIT) / vtk.js (BSD-3-Clause) are candidates; neither installed in the connected web package |
| Radiology and longitudinal imaging | Existing imaging owner; DICOM identities, frame/series geometry, exact pixels, measurements and review | Study/series selection; later qualified image and lesion comparison | OHIF root MIT; exact distribution, codecs, extensions, default remote data and dependency review remain HOLD |
| Pathology and spatial tissue | Specimen/block/slide coordinates, pyramid artifacts, annotation versions and review | Tiles, regions, source-linked annotations, cross-modal navigation | SpatialData (BSD-3-Clause) + Vitessce (MIT) are candidates where spatial omics is appropriate; routine whole-slide pathology viewer still needs a scoped selection |
| Genomics, transcriptomics and multi-omics | Native variant/build/assay identity, QC, reproducible jobs, rights-scoped references and outputs | Molecular findings and evidence panels; linked specimen/time selection | Existing framework remains first-party; pipeline packages and reference assets require task-specific pins; viewer installation does not create analysis capability |
| Proteins, structures and interactions | Exact structure/sequence versions, provenance, species, experimental vs predicted status | Linked molecular structure view and source explanation | Mol* (MIT) candidate, isolated viewer adapter; no implicit database download or prediction claim |
| Cells, organelles, metabolites, immune and other biological scales | Typed entities, scale/unit/spatial/time context, uncertainty and coverage | Same Living Patient navigation, explicit absent coverage instead of invented detail | Reference resources go through existing rights/evidence owners; all twelve discussed scales remain in scope, no candidate viewer proves all are supported |
| Investigations, calculations and scientific jobs | Existing question/run/event owners extended with exact input/method/environment/unit lineage, cancellation and amendment invalidation | Reviewable job inputs, progress, failure, results and comparison | Reuse existing durable worker first; no additional orchestration framework installed by this increment |
| Copilot, Composer and voice | Authorized retrieval, typed proposals, model adapters, tool scope and evaluation | Shared context, citations, proposed changes, review/approval; voice feeds same proposals | Model/runtime/STT package choice remains separate; code license does not clear weights or hosted-service terms |
| Literature, trials and therapeutic discovery | Evidence rights, retractions, applicability, hypotheses and human review | Evidence comparison, unknown criteria, research workspace and review | Prior resource catalog is input to qualified adapters; no blanket retrieval, eligibility or treatment authority |
| Care delivery, pharmacy and coordination | Separate orders, verification, administration, tasks, consent and accountable actions | Connected care workspace rather than disconnected tool dashboards | Existing coordination work can be extended; complete clinical workflows still require construction |
| Time machine, learning and evaluation | Event/receipt time versus known-at time; versioned snapshots; exact affected-output invalidation; reproducible evaluation | Available-then versus retrospective labels, comparison, review queue | No new graph database, broker, agent framework or auto-learning system required for this increment |
| Search and operational recovery | Enforce authorization before retrieval, artifacts and export; audit, backup/restore, quotas and observability | Search within current authority; explicit recovery/failure state | Reuse PostgreSQL and existing operational checks first; evaluate additions against measured gaps |

The runtime dependency files already pin React 19.3.1, React DOM 19.3.1,
Vite 7.3.7, TypeScript 5.9.3, FastAPI 0.162.0, Pydantic 2.14.1,
SQLAlchemy 2.0.55, Alembic 1.20.1 and pg8000 1.31.6. PostgreSQL 16 is the
required database major. Exact code-only pydicom 3.0.2 and pypdf 6.21.4 are
recorded in the API lock/inventory. These are inspected repository facts;
local synthetic-use dependency evidence is not blanket commercial-release clearance.

## Integration mechanism

1. Select a concrete capability and the existing domain owner; define source-bound input/output contracts and acceptance examples.
2. Pin the smallest useful tool distribution. Inspect shipped dependencies, native codecs, examples, assets and network defaults. Record license notices and hashes in the existing inventory. Treat code, data, model weights and API terms separately.
3. Put a replaceable adapter behind that domain's interface. The adapter receives an authorized artifact reference and a bounded task; it does not own patient identity, grants, clinical facts or review state.
4. Persist originals and derived outputs through their owners. Record source versions/digests, method/version, parameters, units, reference versions, species and uncertainty. Heavy computation runs outside the browser with bounded resources and the existing job lifecycle.
5. Embed the result into the existing clinical/research view. Keep selection and source navigation consistent. Lazy-load large viewers and prohibit unreviewed default demo downloads or implicit model acquisition.
6. Verify wrong subject/species, stale input, missing data, revoked access, retry/cancel, amendment, restart and restore. Measure startup, memory, latency, accuracy where relevant and user review burden. Only then advance that tool from candidate to an integrated capability.

Root license evidence checked 7 November 2026, without installing these candidates:
[Three.js MIT](https://github.com/mrdoob/three.js/blob/dev/LICENSE),
[vtk.js BSD-3-Clause](https://github.com/Kitware/vtk-js),
[Mol* MIT](https://github.com/molstar/molstar/blob/master/LICENSE),
[Vitessce MIT](https://github.com/vitessce/vitessce),
[SpatialData BSD-3-Clause](https://github.com/scverse/spatialdata/blob/main/LICENSE),
[OHIF MIT](https://github.com/OHIF/Viewers).
These moving upstream references support candidate selection only. Each adopted artifact needs
an immutable version/hash and the exact deployed package/asset audit. A permissive renderer does
not grant rights to an anatomical atlas, scan, reference dataset or model weights loaded into it.

## Concrete continuation in this branch

`GET /v1/patients/{patient_id}/cases/{case_id}/world-model/semantics` reuses the
existing source-read transaction, current permissions, final recheck and access receipt.
It builds `oi.source-semantics/1` from persisted, validated source versions. There
is no new ledger or migration and no change to the existing World Model fingerprint.
The current projection includes structured source statements and structured laboratory
observations; reviewed document selections and historical semantic queries are not covered yet.

The browser validates every semantic record against the displayed source fingerprint,
source digest, record anchor, concept version and original state. The World Model has
an on-demand evidence classification panel. A missing result remains distinct from a
negative result; masked, unknown, error and not-performed reasons remain recoverable.
`present` means a reported entry exists, not disease presence, normality or clinical truth.
Subject changes, disconnect and denied authority withhold the response.

This is a bounded first connection of #606 to the connected application. It does not
complete #604's persisted editable mappings, versioned calculations, dependency graph,
precise derived-output invalidation, replay, KL evaluation or all scientific viewers.
Next construction: extend the existing investigation owner with one reproducible
calculation's versioned input/output references and amendment-driven re-review.

## Verification

Local results and hosted status are reported in the associated draft PR. The
PostgreSQL HTTP regression exercises source amendment, process restart, cross-case
refusal and grant revocation when a disposable PostgreSQL 16 database is supplied.
Skipping that test locally must not be reported as database acceptance.

Local verification for this continuation (7 November 2026):

- Web TypeScript/Vite build passed; 747 client tests passed without skips.
- Five pure semantic-contract tests, three source-projection tests, ten API contract tests and 31 architecture-gate tests passed.
- API artifact hash/license gate passed for 26 packages; frontend rights gate passed for 18 installed packages, with two optional packages explicitly uninspected under the documented `--omit=optional` installation.
- Two new real-PostgreSQL tests were skipped locally because PostgreSQL 16 is unavailable. No database/restart/recovery pass is claimed from the local run.
- The initial broad API attempt ran 1,032 tests: 615 skipped, 75 Unix-socket permission errors and one outdated endpoint-list assertion. All 75 error tracebacks ended in `PermissionError: [Errno 1] Operation not permitted`. The endpoint assertion was corrected and its ten-test suite passed. The full suite was not represented as passing.
- Browser smoke was attempted, but no Chromium executable was installed and the browser download failed. No new browser/visual or accessibility pass is claimed.
- No model, dataset or candidate scientific viewer was installed; no deployment or merge performed.


## Connected historical continuation

The successor integration combines this source projection with the persisted
permission owner and historical patient context from #618. It also preserves the
Labs/Imaging improvements and reuses #619's Composer binding repair. See
[the resumable implementation checkpoint](H1_SEMANTIC_HISTORY_INTEGRATION.md)
for exact parents, current/historical API contracts, actual verification and the
next calculation dependency. Prior #616 results are not a combined-head pass.
