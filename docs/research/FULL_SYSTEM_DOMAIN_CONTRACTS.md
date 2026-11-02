# Open Intelligence — Full-system domain contracts and implementation map

**Status:** technical contract proposal and code-grounded implementation map, 2 November 2026. Complements `FIRST_PRINCIPLES_PLAN.md` and the founder mandate in PR #49; does not replace the existing patient world model, source ledger or roadmap. Full first-party healthcare scope and **no Next.js** are adopted requirements. The detailed interfaces below remain proposed except where explicitly implemented and tested.

**Inspected implementation:** base `3f718174dcceb8f311a476d1cbccb093b3f66286`; patient-access baseline blob `d288aa36d9dd45a021381d363066452c86cd3080`. Work uses independently authored synthetic inputs. Code correctness, clinical validation, commercial rights and operational authorization are separate decisions.

## 1. Responsibility map: first-party products, not independent silos

The 22 capability families in the founder's mandate are mapped here to operational owners. Owners are roles, not assigned collaborators. A logical domain is not automatically a new microservice, database server, frontend framework or agent.

| Domain and mandate coverage | Authoritative records/operations | Example commands and resulting events — proposed | Cross-domain responsibilities |
|---|---|---|---|
| Identity, organizations, consent and security (22) | Issuing namespaces, source-to-patient bindings, practitioners, facilities, delegated authority, access decisions | ProposeMatch / BindingReviewed; RevokeGrant / GrantRevoked | No name-only merging; purpose-bound access; identity corrections propagated without erasing history |
| Clinical EHR/EMR and physician workspace (1, 13) | Encounters, signed documentation, clinical orders, longitudinal clinical record | CreateOrder / OrderRecorded; AmendNote / NoteVersionAdded | An order is not a completed procedure; clinical authorization is not an AI output |
| Oncology and precision medicine (2, 10) | Disease episodes, lesions, staging assessments, tumor boards, reviewed molecular interpretations | RecordAssessment / AssessmentVersionAdded; ConveneReview / ReviewRequested | Preserve cancer/episode/lesion and time context; source evidence is separate from interpretation |
| LIS/LIMS and diagnostic operations (3, 4, 6) | Accessioning, specimen custody, instrument worklists, assay executions, QC and reported results | AccessionSpecimen / SpecimenAccessioned; ReleaseResult / ResultReleased | Specimen-to-assay lineage, QC status, result amendment; non-release cannot become a negative result |
| Pathology and digital pathology (5) | Case preparation, blocks/slides, annotations, reports and diagnostic review | RegisterSlide / SlideRegistered; AmendReport / ReportAmended | Report, image, annotation and interpretation versions are distinct; amendment is not necessarily new disease |
| Radiology/RIS/PACS (7, 8) | Imaging orders/worklists, study/series/instance assets, archive, measurements and reports | StoreStudy / StudyStored; FinalizeReport / ReportFinalized | DICOM identity and acquisition time; report-only access must not imply image availability |
| Genomics and bioinformatics (9) | Assay/pipeline runs, reference assemblies/transcripts, variant calls and reviewed annotations | CompletePipeline / PipelineResultAvailable; ReviewVariant / VariantAssessmentRecorded | Sample, pipeline/model/reference versions and quality controls; research calls are not confirmed clinical conclusions |
| Treatment, medication and pharmacy (11) | Regimens, prescriptions, preparation, dispense, administration, reconciliation and safety workflow | RecordAdministration / AdministrationRecorded; CorrectAdministration / AdministrationCorrected | Distinguish plan, request, supply, reported use and observed delivery; preserve actual history |
| Patient, caregiver and longitudinal care (12) | Attributed goals, symptoms, preferences, communication, delegated participation, supportive/survivorship tasks | SubmitReport / PatientReportReceived; AcceptTask / TaskOwnershipAccepted | Missing answer is not a negative symptom; receipt is not monitoring or resolution; role-appropriate source access |
| Hospital administration (14) | Scheduling, resource/workforce/inventory, finance, claims and authorizations | ReserveResource / ResourceReserved; SubmitClaim / ClaimSubmitted | A bill is not proof of care delivered; no uncontrolled overwrite of clinical records |
| Trials, research and scientific analytics (15, 21) | Studies, protocols, biosamples, consented cohorts, experimental runs and population analyses | CreateStudySnapshot / ResearchSnapshotCreated; RegisterEvidence / EvidenceVersionAdded | Research-use grants, source-rights, current protocol/site context; candidate screening is not enrollment authorization |
| Native intelligence, AI/ML, foundation models and agents (16–20) | Model/pipeline registry, evidence and claim graph, longitudinal patient projection, investigations and assessments | ProposeHypothesis / HypothesisProposed; EvaluateClaim / AssessmentCompleted | Bounded capabilities, independent review, model/source/version receipts; no direct ungoverned writes into clinical systems |

The patient world model is a source-linked longitudinal projection and reasoning substrate. It is not a competing operational authority. A single synthetic SQLite process may establish contracts; it does not select the deployment topology for the full product.

## 2. Shared contract requirements

### DC-01 — Qualified identity and explicit reconciliation

A source's identifier is meaningful in its issuing namespace. FHIR describes `Identifier.system` as the namespace for an identifier value [S1]. For this synthetic adapter, the proposed implementation key is `(source_organization, source_system, source_subject_ref)`; this is an OI convention, **not a FHIR conformance claim**.

A source namespace may contain many people. The same local string in another namespace is not evidence of the same person. A known qualified subject cannot silently move to another case. Within a case/namespace, changing the subject requires an explicit reconciliation decision. Actual trusted issuer registration, patient matching, alias lifecycle and signed authorization remain to be engineered.

A rejected, quarantined or failed import cannot reserve a new successful binding. Identifiers are not case-folded or whitespace-normalized into aliases. Accepted receipt metadata records issuer/system/subject for inspection; a declared label is not proof of issuer authenticity.

**Implemented proposal in PR #51:** correct the adapter's two in-memory key shapes; bind only after `imported` or `duplicate`; validate nonempty namespace strings; add receipt fields. **Not implemented:** durable binding/revocation, verified person matching, concurrent reconciliation, global consent or authentication.

### DC-02 — Source custody, versions and multiple time axes

Original bytes belong to the source/version record. An extraction, normalization, summary, image-derived measurement or interpretation cannot replace them. Keep issuer identity and object ID separate from an internal database row ID. A content hash establishes byte identity, not authenticity or clinical correctness.

Retain occurred/collected/acquired time, report-issued time, received/known time and effective time where applicable, including precision, calendar/timezone and uncertainty. The existing fixture format requires exact dates; that is a bounded parser contract, not a complete temporal model for all clinical records. Do not enforce an identical event-before-report ordering for every future command type: planned operations and retrospective reports require different semantics.

**Acceptance:** v1 remains inspectable after a declared amendment; current projections resolve to v2; late information is not backdated into what was previously known; export identifies its exact snapshot and freshness.

### DC-03 — Specimen, assay, image and molecular lineage

Every domain records the relevant patient, episode, specimen/aliquot, assay, study, lesion and pipeline references. Not all records need all identifiers; absence is explicitly represented. A new sample is not automatically an amendment of an earlier sample. A pathology report, digital slide, sequencing file and derived variant interpretation remain independently versioned assets.

Cross-domain reference resolution must reject wrong-case or incompatible specimen lineage. A processing tool cannot infer missing pixels, sequences, chain of custody or sample quality from the existence of a text report. Native DICOM transfer is a separate imaging interface contract [S3].

### DC-04 — Commands, execution and epistemic state

A proposed action, authorized order, actual execution, observed outcome and review are different records. FHIR's medication resources distinguish request, dispensing, administration and reported use [S2]; our first-party medication domain must preserve at least those distinctions, rather than infer delivery from an order or claim.

Clinical observations, model extraction proposals, calculations, interpretations, hypotheses and clinical decisions remain separately typed. Workflow completion does not make uncertain clinical content true. An autonomous agent may select permitted computational work; consequential clinical action requires its declared authority and intended-use controls.

**Current test boundary:** report ingestion preserves authored statuses and wording. It does not execute an order, assay, image analysis or medication action.

### DC-05 — Authority is checked, never inherited from narrative

Resolve actor identity, role, organization, purpose, grant/version and source permissions through trusted server-side services. Model output, tool arguments, a reviewer label, or a client-supplied `approved` field cannot create authority. Publication/release of an interpretation is distinct from source-record access and actual clinical sign-off.

Check authorization again at execution, retrieval and export. Revocation must affect derived excerpts and cached artifacts consistently. Historical metadata may be retained only under the applicable policy; retention is not universal permission to display content. No new clinical or legal determination is made by this specification.

### DC-06 — Amendments and derived-result invalidation

Record explicit dependencies at source, assertion, specimen, evidence, model, policy and applicability versions. A material change invalidates affected derived results and opens a review task, not an automatically approved replacement. Scope the invalidation to the actual dependent records; unrelated patients and valid history survive.

A report-wide source dependency may conservatively invalidate the whole report until finer-grained dependency evidence exists. Do not claim atomic-claim precision merely because a table has claim IDs. A historical assessment stays attached to its original snapshot and cannot certify a new one.

### DC-07 — Delivery, recovery and event consistency

Proposed delivery guarantee is **at least once plus idempotent accepted effects**, not a blanket exactly-once claim. The domain owner must atomically persist its state and an outbox record, or document a durable reconciliation path. Consumers deduplicate on event/operation IDs, check expected aggregate versions and source namespaces, and persist their checkpoint with the accepted effect.

Validate replay, retries, out-of-order arrivals, conflicting idempotency payloads, poison events, bounded retry and dead-letter visibility. Source import, identity binding and acceptance receipt must not diverge after a crash. The current adapter performs separate operations and stores its bindings in memory; this is a **known open contract**, not solved by the namespace correction.

### DC-08 — APIs, read models and data boundaries

Domain commands enforce ownership and expected revision; other domains do not update the owner's tables. Prefer purpose-built query projections over unowned shared mutable records. Derived indexes may be rebuilt, while authoritative clinical records and source custody cannot be recreated from a lossy summary.

Version API/event schemas and test compatibility. Separate interface completeness from full deployment: a generated endpoint or empty service does not establish a capable clinical product. No Next.js dependency or new framework is introduced by this specification.

### DC-09 — Source and model commercial freedom

One component identifier references exact code, transitive dependencies, binary/container artifacts, weights, terminology, datasets, asset licenses and obligations. Distinguish candidate discovery, license inspection, technical evaluation and authorized use-specific clearance. An open-weight model is not automatically redistributable; a permissive SDK does not grant rights to the service or its training material.

The existing rights register remains authoritative. This work adds no adopted technology or licensed medical content and makes no project-license decision.

### DC-10 — Independent assessment and durable operator control

Required checks are selected by a versioned task policy; the investigator cannot weaken that policy. Each result declares scope, inputs, method/version, outcome and freshness. Passed, failed, unavailable, not-run and stale states must remain truthful through UI, CLI and export. A human decision binds the exact artifact/action and trusted actor context.

Operator guidance, pause, cancellation, budgets and review decisions need durable receipts and safe application boundaries. Correction is closed only when its resolution condition is assessed; budget exhaustion, an evaluator outage or deletion of a difficult question cannot count as validation.

## 3. Proposed event envelope — not installed middleware

```json
{
  "schema": "oi.domain-event/1",
  "event_id": "EV-FICTIONAL-001",
  "event_type": "pathology.report.amended",
  "owner_domain": "pathology",
  "issuer_namespace": "urn:oi:fixture:lab-a:pathology",
  "aggregate": {"type": "report", "id": "PATH-XA", "revision": 2},
  "subject_binding_id": "BINDING-FICTIONAL-001",
  "source_version_ref": "SOURCE-FICTIONAL-V2",
  "supersedes_source_ref": "SOURCE-FICTIONAL-V1",
  "occurred_at": {"value": "2026-01-01", "precision": "day"},
  "issued_at": "2026-01-02T12:00:00Z",
  "recorded_at": "2026-01-03T10:00:00Z",
  "correlation_id": "WORKFLOW-FICTIONAL-001",
  "causation_id": "CMD-FICTIONAL-002",
  "authorization_decision_ref": "AUTH-FICTIONAL-001",
  "payload_ref": "ARTIFACT-FICTIONAL-002"
}
```

No personal data belongs in topic names or diagnostic logs. Payload references still require authorization and appropriate encryption. `authorization_decision_ref` must resolve to a trusted decision; accepting arbitrary strings is not enforcement. An envelope is not proof of a broker, outbox, authentication service or complete schema validator.

## 4. Data topology and synchronization

| Data class | Owning authority | Integration strategy |
|---|---|---|
| Operational EHR, LIS, pharmacy and administration | Respective domain transactions and versions | API commands plus versioned events; no direct cross-domain writes |
| Source reports and clinical image/genomic assets | Original artifact custody with metadata/rights | Access-controlled immutable object references and explicit amendments |
| Patient world model, claims and uncertainty | OI longitudinal domain with traced input dependencies | Rebuildable projections where lossless inputs exist; accountable interpretations remain versioned |
| Terminology/clinical knowledge | Named, licensed publisher/version and institutional policy | Controlled normalization, version-bound mappings; no equivalence inferred from similar labels |
| Analytical/research datasets | Purpose-limited research snapshot | Consent and source-rights checks, temporal cutoffs, independent evaluation |
| Search/graph/vector projections | Derived indexes, never clinical authority | Authorization-aware queries, coverage/refresh records and deletion/restriction propagation |
| Model artifacts and runs | Model registry and scoped execution service | Exact weights/code/data rights and source/policy/model provenance |
| Audit/operational events | Authoritative action trail with retention policy | Tamper evidence, access controls, recovery proof and explicit incomplete histories |

Specific databases, brokers, model runtimes and cloud services remain unselected. Sharing a physical database during early development does not waive logical data ownership; deploying multiple databases does not automatically establish consistency.

## 5. Current implementation versus complete-system requirements

| Capability | Evidence in the inspected repository / new proposal | Remaining requirement |
|---|---|---|
| Original text source/version custody | `CaseStore.import_report`, `source_text`, existing amendment machinery | General clinical formats, verified source identity, native object store controls |
| Report-level cross-domain projection | Synthetic clinical/lab/pathology/molecular/imaging inputs use one existing ledger | First-party operational commands, accessioning, instrument QC, PACS, genomics pipelines |
| Qualified subject bindings | PR #51 namespace correction and focused regressions | Durable trusted binding/consent service, multi-worker atomicity, explicit aliases and reconciliation |
| Review and invalidation | Existing snapshots and demo acknowledgment; new actual-ledger regression journey | Verified professional identity, intended-use-specific review and clinical authorization |
| Restore/replay | New test reopens canonical source/snapshot database | End-to-end binding/revocation recovery, domain outbox/inbox, distributed replay |
| Scientific/model integration | Existing bounded Meta investigation and replay paths | Qualified multimodal pipelines, independent model quality, rights and monitoring |
| No Next.js | No added dependency in this implementation; exclusion documented in PR #49 | Repo-wide policy enforcement and final chosen application/service architecture |

The full product mandate is unchanged. This table avoids calling report exchange a complete EHR/LIS/PACS implementation. The uploaded 21-domain technology survey, five-alternative comparisons where available, security studies and all 12 final deliverables are **not completed by this contract note**.

## 6. Testable build sequence and parallel work boundaries

| Work package | Dependency and concrete deliverable | Completion evidence |
|---|---|---|
| Identity/source integrity | Existing source ledger; qualify bindings, preserve originals and rejected-import behavior | Focused regressions plus actual CaseStore integration |
| Durable authority and namespace registry | Reviewed DC-01/DC-05/DC-07; map trusted issuer/subject to patient with revisioned decisions | Restart/revocation/concurrent-conflict tests; no actor self-authorization |
| First-party EHR/LIS operational spine | Identity and source contracts; commands for encounter/order/accession/specimen/result | Order→accession→result states and QC/error paths, not report-only simulation |
| Pathology/imaging/genomic assets | Specimen and order spine; original assets and derived object lineage | Source version and asset access tests, cross-patient/specimen rejection |
| Intelligence and clinical review | Qualified inputs and exact dependencies; preserve existing investigation framework | Counterevidence, missingness, stale-result, bounded-repair and human review tests |
| Cross-domain product workspace | Above APIs; independent UI without Next.js, one case context | Actual browser source inspection, corrections, review, refresh, replay and export |
| Technology/licensing evaluation | Workload contracts and existing rights register | Primary-source version-specific shortlist and compatibility experiments, no package approval from labels |

These are engineering work packages, not named-person assignments or promised dates. They should be mapped into existing backlog rows OI-005/006/007/009/013/016 and ongoing PRs. Shared contract changes require an integration owner; independent domains can proceed in isolated branches against the same contracts. No new routine meeting, external commitment, deployment or real-data access is authorized.

## 7. Verification receipt and limitations

The original adapter blob was copied byte-for-byte and matched with `git hash-object`. Fourteen focused tests produced **eight baseline failures** and then **14 passes** against the corrected adapter. Parsing and storage were explicit test doubles; this was not the complete application suite.

Hosted run [41470132341](https://github.com/OpenxIntelligence/open-intelligence/actions/runs/41470132341) subsequently passed **207 tests, no reported skips**, including the seven new actual-CaseStore tests and all 14 focused regressions, plus the existing synthetic Chromium and Patient Mission browser journeys. The test log identifies merge checkout `0cfe6447130507c30052d5c32188fa33b5007337` combining feature `5e427515f88f2fcb714474d10ec51bac2ea7964a` with base `3f718174dcceb8f311a476d1cbccb093b3f66286`. This is engineering evidence, not clinical validation. The log includes SQLite unclosed-connection ResourceWarnings in the broader suite; their attribution is not established by this check and they are retained as follow-up work.

No clinical interpretation or source-license approval follows from these tests. No operational LIS/PACS/EHR, FHIR endpoint, new database engine, clinician credentials, security certification, model-accuracy improvement or complete production identity service is claimed. The browser results cover existing scripted journeys, not a new visual design or manual accessibility evaluation.

## Sources and decision provenance

- **Founder requirements:** full-system/no-Next.js mandate and uploaded Master Open-Source Technology Research and Architecture Discovery; repository decision PR [#49](https://github.com/OpenxIntelligence/open-intelligence/pull/49).
- **Inspected source:** [patient_access.py at the base](https://github.com/OpenxIntelligence/open-intelligence/blob/3f718174dcceb8f311a476d1cbccb093b3f66286/src/open_intelligence/patient_access.py), [CaseStore](https://github.com/OpenxIntelligence/open-intelligence/blob/3f718174dcceb8f311a476d1cbccb093b3f66286/src/open_intelligence/store.py), [existing tests](https://github.com/OpenxIntelligence/open-intelligence/blob/3f718174dcceb8f311a476d1cbccb093b3f66286/tests/test_patient_access.py).
- **S1:** [HL7 FHIR R4 data types — Identifier](https://hl7.org/fhir/R4/datatypes.html#Identifier). Namespace/value semantics, not adoption of a FHIR server or a claim of conformance.
- **S2:** [HL7 FHIR R4 MedicationAdministration](https://hl7.org/fhir/R4/medicationadministration.html). Request/dispense/administration/statement distinctions.
- **S3:** [DICOM PS3.18 2026a Web Services](https://dicom.nema.org/medical/dicom/2026a/output/chtml/part18/PS3.18.html). Imaging exchange mechanisms, not full first-party radiology workflow or permission infrastructure.
- **Policy owner:** [existing Notion rights/governance record](https://app.notion.com/p/40a3866f77ef815a97d5e016ededf5b9). No new third-party license inspection is claimed in this increment.

All field names, proposed events and ownership decompositions in this note are engineering proposals unless explicitly attributed to an existing implementation or standard. Preserve this distinction in future documentation and software.
