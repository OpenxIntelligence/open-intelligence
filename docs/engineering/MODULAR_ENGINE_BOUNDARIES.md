# One platform, independently evolving engines

**Decision date:** 5 November 2026 (America/New_York).  
**Authority:** the founder's explicit modular-ecosystem directive, reconciled with
[the first-principles plan](../FIRST_PRINCIPLES_PLAN.md),
[existing decisions](../project-state/ARCHITECTURE_DECISIONS.md) and
[repository instructions](../../AGENTS.md).  
**Inspected baseline:** `4b13bc2e802bc785ea36f98d63478e51ee3a66a4`.

## Accepted direction and bounded implementation

Open Intelligence is one patient-centered product with shared identity,
authorization, provenance, clinical governance and navigation. Specialized
engines may evolve and execute independently behind governed contracts. An
engine is a logical responsibility before it is a service, deployment, database
or autonomous agent. The existing patient/source/evidence/question/review owners
remain authoritative; this decision does not introduce another Patient World
Model or another patient master.

This increment implements an **offline architecture gate**, consumed by CI. It
assigns existing H1 Python modules to logical owners, declares approved import
interfaces, and rejects unregistered modules or new undeclared cross-owner
imports. An explicit ledger retains existing coupling as debt. It does not
install a runtime plugin loader or change application APIs, authentication,
authorization, clinical behavior, database schemas or dependencies.

The supplied master directive reserves those consequential changes for their
own scoped approval. Ordinary reversible engineering and documentation are
authorized. Runtime registration, workers, event delivery and service extraction
are subsequent implementation proposals, not capabilities supplied by this gate.

## Why this first increment

The connected application already separates source custody, questions, evidence,
review, follow-through, imaging and laboratory functions into files. They still
share in-process persistence and import implementation details. `patients.py`
contains composition, routes and response contracts; several domains import
those contracts back from that file. `composer_preflight.py` combines source and
laboratory access. A dynamic registry added now would hide these dependencies
without making them independent.

Three approaches were considered:

| Approach | Consequence | Decision |
| --- | --- | --- |
| Split every named engine into a service now | Introduces distributed authority, transaction, recovery and deployment problems before contracts are isolated | Defer until a measured operational need and migration evidence exist |
| Add a general runtime plugin loader first | Adds executable registration before a qualified consumer and capability policy exist | Defer; metadata discovery must never grant execution rights |
| Declare and enforce existing boundaries, then extract one contract at a time | Makes coupling measurable while retaining the working application and its acceptance suite | Selected implementation approach for this increment |

This is an implementation choice under the founder's direction, not a claim
that every future engine is built or that the founder selected a particular
broker, workflow framework, cloud provider or database per engine.

## Platform and engine responsibilities

The shared platform owns subject identity and bindings, current grants and
purpose, source custody and versions, review/publication authority, rights,
audit, contract policy and coordinated navigation. Domain engines own their
qualified computations and domain-specific state. Common policy can be enforced
at each boundary; central governance does not require every computation or
every data byte to pass through one process.

The Patient World Model remains a versioned projection of authorized source
state and reviewed interpretations. Search, derived representations, embeddings,
model context, jobs, exports and caches inherit those restrictions. Domain
storage is allowed where justified, but another engine may not write it through
shared tables or bypass its owning interface.

| Proposed engine | Existing foundation to reuse | Next qualification; not delivered by this increment |
| --- | --- | --- |
| Oncology EHR | Patient/case registry, immutable originals, questions and longitudinal projections | Encounters, independently attributed cancer episodes, documentation and clinical workflows |
| Clinical AI and copilot | Authorized source preflight, saved questions, evidence and review boundaries | Bounded model/task contracts, source-grounded outputs, abstention and independent evaluation |
| Pathology and biomarker intelligence | Source/document custody and exact source anchors | Specimen/assay-aware extraction and reviewed biomarker interpretation |
| Radiology and imaging | Image-original custody and DICOM validation adapters | Qualified viewing/analysis, lesion context and modality-specific validation |
| Oncology treatment management | Operational follow-through only | Separate orders, verification, administration, changes and accountable clinical approval |
| Bioinformatics research | Biological research ambition and isolated research probes | Durable runs, QC, reproducible environments and governed artifact references |
| Genomic analysis | Existing source and biological-context contracts | Native variants, reference builds, assay context, QC and task evaluation |
| Single-cell and transcriptomic analysis | Isolated research probes, not a connected qualified engine | Reproducible preprocessing/analysis with dataset and method rights |
| Multi-omics integration | Source identity, specimen/time context and provenance | Qualified cross-assay alignment and explicit uncertainty propagation |
| Therapeutic target discovery | Question/evidence/hypothesis separation | Reproducible research hypotheses and independent expert assessment |
| Drug discovery research | Governed research architecture | Qualified research pipelines; no clinical efficacy or treatment authority inferred |
| mRNA vaccine research | Separately governed translational research ambition | Independent scientific, clinical and intended-use review before a scoped computational function |
| Clinical trials intelligence | Existing evidence/question contracts and research probes | Criterion-level supported/unknown evidence and human screening; no inferred eligibility |
| Scientific literature intelligence | Metadata citations, authored evidence, rights and report owners | Authorized retrieval, claim support, applicability and retraction handling |
| Interoperability and data integration | Reviewed document intake and bounded FHIR R4 laboratory import | Versioned partner-specific FHIR/mCODE, DICOMweb and native scientific adapters |

These engines can support the six proposed product verticals—Oncology
Intelligence, Precision Medicine, Bioinformatics, Therapeutic Discovery,
Clinical Intelligence and Research Intelligence—through one patient-centered
experience. A product vertical is not another authority database or a requirement
to create fifteen navigation tabs.

## Rules for future executable capabilities

Every proposed capability must identify its owner and immutable version, intended
use, input/output schemas, accepted data classes, patient/case/specimen scope,
source versions and digests, required current permissions and purpose, model/tool
and reference versions, provenance, rights, resource/egress limits, review
requirements and validation evidence. Registration is discovery metadata;
execution needs a separate policy decision against the actual request.

Every run needs an idempotent intent, durable lifecycle, input snapshot, cancellation
and resume semantics, bounded retries, output lineage and failure states. Resume,
artifact retrieval and publication recheck current authority and source freshness.
An amended source or revoked grant may invalidate use without erasing historical
provenance. A worker may propose an output; it cannot promote its own result to
a clinical fact, sign a note or authorize treatment.

Events should describe durable changes with identity, schema version, correlation,
causation and source references. Use the existing transactional domain event owner
first; qualify an outbox and at-least-once delivery/idempotent consumers before
adding an external broker. Source event time, receipt time and processing time
remain distinct. Do not promise exactly-once delivery or instantaneous distributed
revocation.

FHIR/mCODE are exchange contracts, not a replacement for the first-party domain
model. mCODE 4.0.0 is based on FHIR R4 and does not require every possible oncology
field to be collected. [HL7 mCODE](https://hl7.org/fhir/us/mcode/STU4/).
FHIR supplies security/privacy building blocks rather than choosing or enforcing
the application's complete policy. [HL7 security module](https://www.hl7.org/fhir/secpriv-module.html).
DICOMweb defines imaging web services; its PS3.18 security scope refers elsewhere
for authorization and audit. [DICOM PS3.18](https://dicom.nema.org/Medical/dicom/current/output/html/part18.html).
These references do not change H1's accepted versions or clear content rights.

## Architecture gate and its limits

The machine-readable map lives in `docs/architecture/engine_boundaries.json`.
`tools/architecture/check_engine_boundaries.py` reads Python syntax without
importing or executing application modules. Its scope is the H1 API package at
`apps/api/src/oi_api`; existing `open_intelligence` references are declared bridges.
Frontend modules, SQL access, runtime object calls, transitive reference-package
dependencies and external-service traffic are outside this first check.

Each existing module has exactly one owner. Cross-owner imports require a
declared dependency and exported symbol, or an exact existing-debt entry with a
reason and backlog owner. New files require ownership. Duplicate/ambiguous
registrations, unknown owners or modules, new private imports, stale debt entries
and unsupported dynamic-import forms fail the check. Approved dependency edges
must be acyclic; observed legacy coupling can remain cyclic and is reported as
debt rather than hidden. This is an architectural maintenance check, not a
security sandbox, runtime permission check or proof of independent deployment.

Changes to the map are ordinary reviewed code changes. A developer who can edit
the map can propose a new dependency; CI is not a substitute for that review.
The gate never automatically records new exceptions.

## Development sequence and acceptance

1. **This increment — OI-005/OI-018:** inspect owners, add the gate and mutation
   tests, wire CI, and record actual source/check evidence. Preserve current runtime.
2. **Contract extraction:** move shared response/selection types out of
   `patients.py` through a focused compatibility-preserving refactor, remove the
   corresponding debt entries, and compare OpenAPI plus full API/browser behavior.
3. **One worker contract — OI-009/OI-013/OI-016:** propose a bounded synthetic
   research job with durable state, source/authority rechecks and governed output.
   Obtain the applicable API/schema approval before implementing those changes.
4. **First independent execution:** measure recovery, latency, memory/compute,
   fault isolation and operational burden for that worker. Separate deployment
   only if the evidence warrants it; preserve the in-process contract consumer.
5. **Repeat by engine:** qualify one capability and its complete patient workflow
   before expanding autonomous scope or declaring a product vertical complete.

Run `python tools/architecture/check_engine_boundaries.py` and
`python -m unittest discover -s tools/architecture -p 'test_*.py' -v`.
Verification results and exact revision are recorded with the implementation PR.
Synthetic software evidence does not establish clinical performance, production
identity/consent, distribution clearance or deployment.

## Local acceptance recorded for this increment

- The actual H1 tree passes: **44 Python modules, 10 logical owners, 58 exact
  consumer/provider debt groups covering 81 imported symbols**. Eight canonical
  reference bridges declare 33 permitted symbols. These are implementation
  dependencies to manage, not a count of independently deployed engines.
- **31 checker test methods pass.** The initial 28 failed before implementation.
  Independent review then exposed package-attribute versus child-module
  ambiguity; class, conditional, dynamic package attribute and pattern-capture
  regressions were reproduced before the resolver repair. A regular module
  masquerading as a package parent is also rejected.
- A disposable copy of the real tree passed before mutation and rejected a new
  `source_world_model` import of the private authored-evidence store after
  mutation. The working application's sources were not modified by this probe.
- **772 inherited synthetic unit/HTTP tests pass** using the repository's
  existing hash-locked PDF parser. The first local baseline had 9 failures and
  8 errors in PDF tests because that dependency was absent; installing the
  existing lock resolved them without changing application code or requirements.
- The existing synthetic-data CI boundary audit, Python compilation, backlog
  parsing and `git diff --check` pass. Application, migration, reference runtime,
  frontend and existing test source paths are unchanged in this increment.
- Fresh independent code review has no outstanding material or minor finding.
  It covers this static gate and catalog, not runtime authorization, cross-domain
  SQL, transitive bridge dependencies, clinical validation or deployment.

The implementation PR carries the exact commit and hosted checks. A local pass
is not a hosted result; the CI report records source-file and manifest hashes
for the actual checkout it examines.

## Continuation — governed H1 execution, 5 November 2026

The founder's instruction to continue infrastructure implementation advances
steps 2–3 above. The [durable execution candidate](H1_DURABLE_EXECUTION.md) extracts
shared source/question contracts and implements one actor-bound PostgreSQL
Composer run with a separately invoked worker for `source-question-brief/1`.
It retains existing patient/source/question authority and the four existing
scope grants; historical #90/#126 are contract lineage, not installed H1 code.
Human follow-through remains a separate owner.

The worker, migration and process-kill/populated-restore tests are implemented;
final combined hosted acceptance was pending at this source-publication checkpoint.
[PR #529](https://github.com/OpenxIntelligence/open-intelligence/pull/529) maintains
current exact-source receipts. An intermediate PostgreSQL
run reproduced an accepted-intent retry failure after source amendment, now
corrected with a regression. The [execution plan](../superpowers/plans/2026-11-05-governed-execution-foundation.md)
and durable guide track this continuation separately from the original static
gate receipts above. This does not qualify other engines or independent deployment.


## Clinical and Composer migration join

The combined source declares 60 H1 modules across 11 logical owners. The
clinical EHR owner includes the existing encounter route, event contract, and
activity relay. The patient-context owner retains the shared question anchor;
the evidence owner retains laboratory citation reporting. Three existing anchor
imports have explicit debt entries (case identifier, laboratory reference
parser, laboratory validation error). The existing review-return owner is public
to composition and governed consumers, retiring one prior exception. The resulting
ledger contains 79 exact cross-owner symbol imports; it grants no runtime access.
