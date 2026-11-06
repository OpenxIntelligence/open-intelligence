# Animal identity and veterinary case registration

An operator can register an independently fictional dog or cat, obtain an animal ID, and open several oncology cases for the same animal. Each visit to a saved case checks the current clinic and animal grant. This first veterinary workflow needs no human patient, human case binding, diagnostic code or model. Species and clinic reference are synthetic registration assertions. Owner identity, consent, diagnosis and clinical review require separate evidence.

## Run the workflow

Use the existing local H1 environment in [the demo guide](../H1_DEMO.md). Apply the head migration and rebuild the web application. Open **Veterinary registry** from the patient workspace or visit `/veterinary`. Use a synthetic clinic credential. The operator must edit the trusted access fixture outside the application to assign actions and exact animal IDs.

| Action | Required fixture authority | Persistent result |
|---|---|---|
| Register an animal | `animal_register` in the clinic organization | Immutable animal ID, species, clinic-scoped source reference, command key, actor, purpose and creation time |
| Find an animal | `animal_read` and its exact ID in `animal_ids` | Species, organization and registration time |
| Create a case | `animal_read`, `veterinary_case_open` and the exact animal ID | Immutable case ID bound to the same animal and organization, with actor, purpose, request key and creation time |
| Find a case | `animal_read`, `veterinary_case_read` and the exact animal ID | Exact case ID, animal ID, species, organization and case opening time |

The API root is `/v1/veterinary/animals`. POST at the root registers an animal. GET at `/{animal_id}` reads it. POST at `/{animal_id}/cases` opens a case and GET at `/{animal_id}/cases/{case_id}` reopens it. Credentials and current results are held only in the tab. Keep the same request key and fields after an interrupted write. The API returns 201 on first creation, 200 on exact replay and 409 on conflicting registration. A repeated clinic reference under a different key requires reconciliation. This prevents a second local animal registration from being created silently.

The clinic provides a source system and opaque reference. The platform allocates both internal IDs. The database enforces unique clinic references and a composite foreign key on clinic and animal. A registration row is also its immutable command receipt. Human identity and source joins continue to address the existing human tables. Veterinary scope must be granted independently. The API checks the same bearer again after encoding the response, before committing the write or returning the record. Distributed revocation, read-access audit, external identity proofing, consent, demographic matching, owner transfers and reviewed corrections remain open.

## Acceptance and operation

- `apps/api/tests/test_veterinary_registry.py` exercises actual scoped HTTP, concurrent exact retry, conflicting clinic references and commands, separate grants, a second case, application restart, wrong-animal reads, immutable rows, revocation during a write and downgrade refusal. Database tests require a disposable PostgreSQL 16 database.
- `apps/web/tools/veterinary_registry_journey.py` runs inside the existing Chromium journey against the built React and real H1 API. The operator grants access only after recording the animal ID. The test reopens the case, removes the grant and checks the cleared view.
- `apps/api/tools/verify_registry_compose.py` checks both human and animal identities after application/database restart and PostgreSQL dump/restore. An additional case written only through the restored API verifies which copy served the request.
- Use H1 readiness for database and migration availability, the HTTP status for a refused/failed operation and the registration receipt for an uncertain write. Populated veterinary history blocks downgrade. No external telemetry, diagnostic ingest or clinical action is introduced.

## Construction order and stakeholders

This is a continuation of OI-005, OI-013 and GH-112 in the [execution backlog](../EXECUTION_BACKLOG.csv). This source review used main `16fa42781aa40e3899e36b5b441de8d920fced8e` and checked branch names and recent integration proposals for overlapping ownership. The [November 4 audit](../project-state/oncology-audit-20261104/README.md) remains the historical baseline. Its candidate #481 has since merged. The H1 application, Python/SQLite reference implementation and offline research tools have separate verification boundaries. The following gates describe unfinished delivery as well as the bounded work in this change.

| Priority and stakeholder | Existing integration point | Dependency and next observable outcome |
|---|---|---|
| P0 · Veterinary team and pet owner | Animal and case registration in this change | Verify an owner relationship and its allowed actions. A clinic can grant one owner access to one animal; an unrelated owner is denied and revocation also denies a subsequent read. Scope quality-of-life observations, cost estimates and goals to that animal. |
| P0 · Patient and caregiver | Human patient registry, case bindings and record requests | Establish verified persons and delegations with scope, purpose, expiry and durable revocation. A caregiver can coordinate an authorized request, then loses access after revocation. |
| P0 · Security team, administrators and auditors | H1 access fixture, identity events, source-access receipts and restore suite | Qualify identity provider, organization membership, read auditing and independent restore. An auditor can reconstruct a scoped decision; an operator can detect failure without logging record content. |
| P0/P1 · Laboratory, pathologist and surgeon | H1 laboratory FHIR custody, source versions and manual document selection; specimen chain in the reference application | Bind a veterinary source issuer to an animal and case before import. Verify species, specimen, dates and exact original on a synthetic amended report. A wrong-subject report must leave the case unchanged. Reuse this verified provenance for later operative/pathology review. |
| P1 · Radiologist and treating oncologist | H1 image custody, chronological source projection and patient questions | Establish study/series identity, longitudinal comparison and reviewed disease episodes per domain. A clinician can retrieve both study originals and see which interpretation awaits review. |
| P1 · Oncology nurse and pharmacist | H1 record requests and follow-through; compare the encounter/event integration work before extending it | Connect medication, order, administration, symptom and follow-up owners. Demonstrate an order without administration, a missed follow-up and an assigned handoff on fictional cases. |
| P1/P2 · Genetic counselor and clinical researcher | Source-backed questions, authored evidence, rights checks and offline genomics probes | Link specimen, assay, evidence rights and governed research use. Preserve somatic versus inherited assertions, review status and uncertainty. Reproduce a result from the same permitted input versions. |
| P2 · Trial coordinator and research institution | Offline trial screening, evidence catalog and reproducibility tests | Establish versioned eligibility criteria and research-specific consent before referral. An unknown criterion remains open; a withdrawn grant blocks reuse and referral. |
| P2/P3 · Model evaluators and discovery researchers | Reference investigation runs, extraction anchors and governed research probes | Bind evaluations and computational results to species, source version, model/workflow identity and permitted inputs. Require independent review before releasing a scientific or clinical claim. |
| Across layers · Developers and operations | Alembic migrations, API contracts, package locks, browser and recovery workflows | Keep a single migration head for the chosen integration, verify populated upgrade and replay on a restored copy, and check exact-revision CI before release. |

The next dependency for the pet owner journey is a revocable owner-to-animal relationship. The next dependency for a veterinary report is a source-issued subject mapping and immutable document intake for that animal. Both depend on the animal identity delivered here. Neither can inherit a human patient grant.
