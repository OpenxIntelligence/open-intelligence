# Security and governance execution plan

Current repair: additive `0022_lab_citation_source_scope` now aligns the database
guard with the existing structured-source snapshot and preserves published 0021.
The reviewed-document mismatch was reproduced in hosted PostgreSQL run
42096046609 before repair. The earlier source inspection below records the
pre-repair boundary; final repaired-head PostgreSQL/browser/recovery acceptance
is tracked in draft [#542](https://github.com/OpenxIntelligence/open-intelligence/pull/542).

Updated 2026-11-05. This continues OI-004/OI-012/OI-013 in the
[existing backlog](../EXECUTION_BACKLOG.csv). It distinguishes implemented
synthetic controls from production obligations that still need an accountable
owner, evidence and a separately accepted intended use.

## Current authority and data boundary

Accepted main was inspected at `f188aecc70f3415741dac0e7dd5bf3f2d9fd02a9`;
candidate code at `3dd9811738e222274aa2c9e03edeff8104d64d53`. Development,
tests, demonstrations and evaluation use independently authored fictional
patients. Public patient narratives may inform abstract workflow requirements;
they do not authorize medical-data acquisition, ingestion, embedding, analysis,
training or evaluation. Do not create pseudonymized replicas of a real case.

The application currently provides local synthetic authentication/authorization,
not verified patient/clinician identities or consent. No production merge,
deployment, clinical release, external data egress, license selection or real-data
access is authorized by this consolidation. No independent clinical validation
is established.

## Controls and gaps

| Concern | Current implementation to preserve | Evidence/work still required |
|---|---|---|
| Authentication | `app.py` defaults to deny; optional `SyntheticFileAuthentication` reads bounded operator fixture credentials afresh; expiry and ambiguous/duplicate JSON members fail closed | Verified identity provider/account lifecycle, secure credential/session management, recovery and workforce/patient identity proofing |
| Scope and purpose | `access.py` principal carries actor, organization, patient IDs, explicit actions and operations/research purpose; registry and binding owners enforce actual scope | Delegation/caregiver relationships, institutional authority, consent/access basis, purpose policy and revocation responsibilities; a caller-supplied label is not proof |
| Request/disclosure boundary | Local loopback Host restriction, request limits, `no-store`, sanitized validation errors and per-owner prepared-response/final-authority checks | Supported production ingress/TLS/session/CSRF configuration, sensitive logging review and threat assessment for the actual deployment; loopback is a development boundary |
| Patient/source identity | One canonical registry and qualified immutable patient/case binding; same source/version owner for text and FHIR originals | Qualified external issuer/subject resolution and correction protocol; broader tenant access tests for every new path |
| Typed anchors | Candidate `question_anchors.py` rejects numeric/string coercion and mixed variants | Preserve original-byte, relationship, access and freshness checks in source owners; an immutable anchor grants no permissions |
| Transactions and history | Existing command/event receipts and source versions; shared encounter integrity checks; immutable note history and exact retries | Combined-head PostgreSQL concurrency, rollback and populated-upgrade/recovery evidence; production least-privilege DB roles and policy evaluation |
| Laboratory citation freshness | Candidate `0021_lab_citation_freshness` adds an insert guard and refuses unsupported transaction-wide snapshots; source review found it includes reviewed-document sources excluded by canonical snapshots | Follow-up migration must align source scope, then run PostgreSQL reviewed-document acceptance, independent structured-source refusal, isolation and restoration checks; donor results are not combined acceptance |
| Clinical sign-off | H1 encounter API exposes draft notes; no `note.attest` grant or attestation route. Domain test states/author labels do not establish credentials | Verified professional scope, attestation/signature evidence, correction/supersession and reviewer revocation protocol before enabling clinician confirmation |
| Evidence rights | Existing metadata and authored-content owners enforce per-use/current-family permissions and withdrawal | Exact permissions for external content, terminology, assets, models, services and redistribution; citation metadata alone does not clear full text or model processing |
| Model/tool access | H1 source/evidence preparation is bounded; reference model code/write contracts are separate | Qualified permission-filtered H1 copilot, provider/egress policy, per-tool grants, source-rights filtering and current authorization before every effect |
| Recovery | Existing migration/readiness and recovery probes; immutable originals, receipts and source identities must survive | Final-candidate restart/restore/browser evidence; production RPO/RTO, backups, restore isolation, deletion/retention and incident exercise |
| Audit | Existing identity/domain events and command/read receipts under canonical owners | Production access/egress audit design, minimum sensitive content, retention, tamper resistance, monitoring and incident responsibilities; hashes alone do not prove authenticity |

API module paths refer to `apps/api/src/oi_api`; shared domains and the
PostgreSQL registry are in `src/open_intelligence`. Existing source rights and
privacy context remain in [RIGHTS_BROKER.md](../RIGHTS_BROKER.md),
[project-state security/privacy](../project-state/SECURITY_AND_PRIVACY.md) and
the [patient-data CI boundary](../engineering/PATIENT_DATA_CI_BOUNDARY_2026-11-02.md).

## Preservation and combined acceptance

The candidate joins #539 strict identity with #540 freshness enforcement while
retaining #536/#537 encounter/laboratory work. Keep both published 0019 migration
parents unchanged, the no-DDL `0020_ehr_lab_convergence` join, and the following
`0021` enforcement revision. Record actual final checks and limitations in
[RELEASE_ACCEPTANCE.md](RELEASE_ACCEPTANCE.md).

At the inspected `3dd9811` code, the `0021` source-scope mismatch is an acceptance
blocker. Preserve that published migration and correct it in a following revision;
do not change the question's snapshot semantics to conceal the discrepancy.

Required adversarial scenarios include wrong patient/organization/subject,
revoked/expired/ambiguous grants, revocation after response preparation, changed
independent case sources, altered original hashes, mixed text/FHIR anchors,
reused keys with changed intent, lost responses/retries, concurrent amendments,
commit/encoding failure, and restored revoked bindings. Failure must withhold
disclosure or roll back the affected state/event/receipt together, as applicable.
Preserve unaffected patients and immutable historical records.

The earlier #301 research migration is not the application's migration owner:
candidate `0019_ehr_encounters` already includes nullable note provenance.
Legacy unknown facility/department/kind stays unknown. Supporting an older
populated SQLite note store separately requires an explicit upgrade test and
migration; do not erase history or infer provenance.

#152's historical clinical/Composer gate remains useful as a review checklist:
same patient/source owner, current purpose/binding checks, before/after source
consistency and final access validation. Its unintegrated adapter does not
provide an atomic snapshot across separate clinical/laboratory databases or an
authenticated H1 clinical execution route. Reconcile requirements into current
owners rather than wholesale importing its historical store changes.

## Gates before real records or clinical operation

| Gate | Accountable function | Concrete deliverable |
|---|---|---|
| Intended use and clinical authority | Clinical product lead plus independent domain reviewers | Named functions/users/outputs; proposal versus review/confirmation semantics; failure escalation and actual reviewer availability |
| Privacy/data roles | Privacy/security owner with appropriate legal review | Actual data-flow map, access basis, organizational roles, required agreements, retention/deletion, secondary-use and jurisdiction decisions |
| Identity and delegation | Security/identity owner | Verified person/workforce/caregiver bindings, scoped grants, revocation, recovery, least privilege and adversarial lifecycle tests |
| Provider and egress | Security/operations plus rights owner | Per-provider allowed data classes, endpoints/regions, logging/retention/training terms, credential handling, network controls and measured provenance; deny by default |
| Dependencies/content | Engineering inventory owner plus rights reviewer | Exact version/hash/intended-use register for direct/transitive code, data, models, terminology, images and services; obligations and unresolved holds; no new project-license decision |
| Operations and incidents | Operations/security owner | Tested deployment/runbooks, monitored failure handling, recovery targets, restoration exercise, incident reporting and access/audit review |
| Evaluation/release | Evaluation lead, independent clinical reviewers and release owner | Prespecified consequential errors and burden protocol, representative authorized inputs, independent adjudication and accepted final software evidence |

These are required roles and deliverables, not claims that people, contracts or
production infrastructure have already been assigned. Regulatory/privacy
classification follows the actual function and data flow; this engineering plan
does not make a legal classification or certification.

For future model experiments preserve the #141/#476 task restrictions and
unsigned-provenance warnings in [AI_EVALUATION_PLAN.md](AI_EVALUATION_PLAN.md).
An isolated synthetic runner, a research label, a correct source hash or a human
UI toggle cannot supply professional authority or permission for patient data.

Advance one bounded capability after its preceding gates pass. Until production
governance is established, keep clinician confirmation, real-patient use,
external clinical integrations and autonomous clinical effects unavailable.


### Source acquisition under operations and research grants (PF-01, PF-02, PF-03, PF-10)

Draft [#547](https://github.com/OpenxIntelligence/open-intelligence/pull/547) extends
the existing patient, case-binding and record-request owners on the clinical candidate.
For the same fictional patient and actor, case mappings and acquisition requests are
scoped to the credential's current purpose. Receiving an original requires both its
case binding and the request to match that purpose. Before returning a successful
list or command receipt, the API serializes the response and checks the actor,
organization, purpose, patient and relevant grants inside the owner's transaction.
In Records, list and create include the open case as a server-enforced precondition.
The case is locked and rechecked before commit. A scoped create retry binds the
same case into its intent fingerprint. Patient-wide v1 callers retain their existing
API contract. Refresh also rereads the case's authorized source versions.

Older mixed-purpose receipts remain in the immutable journal. The v1 list omits
the affected request because its status vocabulary cannot safely describe an
out-of-purpose source. Other same-purpose requests remain visible. The recovery
and browser checks in this PR exercise restored binding scope and the disappearance
of an already-open original on a purpose refresh. The pull request tracks exact
execution results. Production issuer identity, delegation and clinical consent
remain separate qualification gates.
