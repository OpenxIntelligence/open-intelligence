# Clinical data model

## First operational episode draft

On the #556 clinical-core line, `clinical_source.episode_drafts` stores a new opaque episode identity, its immutable source assertion key, the source snapshot hash, author, time and creation event. Patient, case, source version, dates, digest and quote resolve from the existing owners. Creating two drafts requires two explicit user commands. Matching source labels across documents never joins episodes. A draft can begin only from a current explicitly attributed primary line whose state is reported.

Journey calls GET and POST `/v1/patients/{patient_id}/cases/{case_id}/episode-drafts`. Both require operations purpose, current patient and source access, an active case binding and draft-read authority. POST additionally requires draft-create authority. The case lock serializes imports, concurrent saves and binding withdrawal. The same actor can recover an exact prior command, even after amendment. A changed basis conflicts and a later version of the same document/finding cannot create another identity. An amendment or independent structured import marks the saved basis for reassessment. The previous quote, source state, version and digest remain inspectable. The bounded case limit is 64 drafts.

The application encodes the response inside the source transaction and reauthenticates after event persistence. A populated downgrade refuses data loss. The PostgreSQL, browser and Compose suites exercise author revocation, wrong-patient denial, concurrent retry, two primary drafts, amended origins and read/retry after backup restore. These tests use synthetic sources. Relating several sources to the same draft, adjudicating origin, clinical status and professional attestation require subsequent commands.


Current repair: additive `0022_lab_citation_source_scope` now aligns the database
guard with the existing structured-source snapshot and preserves published 0021.
The reviewed-document mismatch was reproduced in hosted PostgreSQL run
42096046609 before repair. The earlier source inspection below records the
pre-repair boundary; final repaired-head PostgreSQL/browser/recovery acceptance
is tracked in draft [#542](https://github.com/OpenxIntelligence/open-intelligence/pull/542).

Date: 2026-11-05. Implementation basis: the Phase 0 candidate preserving #540
and #539 described in [MASTER_EXECUTION_PLAN.md](MASTER_EXECUTION_PLAN.md).
This document inventories its actual owners and specifies the next Phase 1
episode increment. Proposed fields and states below are requirements for review,
not claims of an installed schema or completed clinical workflow. Acceptance of
the combined candidate belongs in `RELEASE_ACCEPTANCE.md`.

## Existing canonical state

The connected H1 application uses FastAPI/Pydantic, PostgreSQL and
React/Vite/TypeScript. PostgreSQL holds the canonical patient, source, question,
encounter and note state. The Python/SQLite application remains a behavioral
reference. A module under `src/open_intelligence` can be a shared contract or a
PostgreSQL adapter; its location alone does not establish which persistence is
connected.

| Domain | Installed tables and important fields | Current owner |
|---|---|---|
| Patient identity | `identity.identity_patients`: `patient_id`, `origin_org`, creation attribution/time, `status` (`active`, `suspended`), monotonic `revision` | `src/open_intelligence/postgres_registry.py`; `src/open_intelligence/sql/patient_registry_postgres.sql`; migration `0002_patient_registry.py`; HTTP contracts in `apps/api/src/oi_api/patients.py` |
| Identity receipts/events | `identity.identity_create_receipts`: organization/request key, request digest, patient reference; `identity.identity_domain_events`: patient, event type, metadata, occurrence time | The same registry owner; immutable receipts and event rows |
| Case/subject binding | `coordination.patient_case_bindings`: case/patient/organization, qualified source organization/system/subject reference, purpose, review reference, creation and revocation attribution, `active`/`revoked`, revision | `apps/api/src/oi_api/case_bindings.py`; `0004_case_binding.py`; a report header cannot create or reassign this binding |
| Original source version | `clinical_source.source_versions`: source/case/document identity, version, original `raw` bytes and SHA-256, kind, event/issued/received dates, specimen, `current`/`superseded`, predecessor | `apps/api/src/oi_api/sources.py`; `0005_source_versions.py`; shared structured-report parser in `src/open_intelligence/store.py` |
| Literal source assertion | `clinical_source.assertions`: assertion ID, source ID, finding key, certainty, quotation, exact physical source line; unique source/key and source/line | The source owner above; assertion rows are immutable and source-reported |
| Quarantined wrong-case input | `clinical_source.quarantine`: target case, declared case, original bytes/hash, reason and received time | The same source owner; quarantined bytes create no patient observations |
| Reviewed document custody | `clinical_source.document_intakes`, `clinical_source.annotation_revisions`: modality/intake attribution and immutable manual passage revisions | `reviewed_documents.py`, `document_contracts.py`, `document_routes.py`; `0012_reviewed_documents.py`; manual selections remain separately attributed |
| FHIR laboratory source context | `clinical_source.fhir_laboratory_sources`: source FK, qualified subject/system, specimen and collection context, report identity/times, FHIR/profile contract; `fhir_laboratory_observations`: source-local Observation reference, code, effective/issued times, value/unit or absent reason; `fhir_laboratory_commands`: exact import intent | `laboratory_fhir_r4.py`, `laboratory_fhir_store.py`, `laboratory_fhir_routes.py`; `0016_fhir_laboratory_sources.py`; exact original bytes remain in `source_versions` |
| Saved question | `investigation.source_questions`: immutable question ID, patient/case/org, request intent/key, actor/purpose, question text, source ID/version/hash, source snapshot contract/hash, preflight hash, created time; `source_line` is present for text questions | `source_questions.py`; `0006_source_questions.py`, `0007_question_snapshot_contract.py`; source preparation remains inside the canonical source transaction |
| Laboratory question identity | `investigation.laboratory_question_anchors`: question ID, source ID, Observation reference; its parent question has a null source line | `laboratory_questions.py`; `0018_laboratory_questions.py`; one question ledger with a typed modality child |
| Question verification and coordination | `investigation.question_review_receipts`; `coordination.question_followthrough_tasks` and append-only task events | `question_review_returns.py`, `question_followthrough.py`; verification return, operational completion and clinical endorsement have distinct meanings |
| Laboratory metadata citation | Existing `investigation.question_evidence_links` plus `laboratory_citation_anchors`: exact question/Observation/link pair and write-time rights decision | `question_evidence.py`, `laboratory_citation_report.py`; `0019_laboratory_citations.py`, `0021_lab_citation_freshness.py`; metadata linking/inspection is separate from clinical evidence appraisal |
| Encounter | `ehr.clinical_encounters`: patient FK, external key, kind, service date, `scheduled`/`in_progress`/`completed`/`cancelled`, revision and times | `src/open_intelligence/clinical_encounters.py`, `src/open_intelligence/postgres_encounters.py`, `apps/api/src/oi_api/encounter_routes.py`; `0019_ehr_encounters.py` |
| Note identity and versions | `ehr.clinical_note_headers`: encounter, note key, latest version; `ehr.clinical_note_versions`: body/hash, version/status, author/time, predecessor, amendment reason, optional facility/department/note kind | The encounter owner above; versions are immutable; the database constrains each predecessor to the same note and immediate previous version |
| Encounter command receipt | `ehr.clinical_encounter_commands`: patient/request key, request hash, operation, result and occurrence time | The encounter owner; state, receipt and domain event share the command transaction |

The migration graph retains both published `0019_ehr_encounters` and
`0019_laboratory_citations` parents. `0020_ehr_lab_convergence` joins them without
DDL, and `0021_lab_citation_freshness` follows that join. A Phase 1 migration must
extend the then-current accepted graph; this document reserves no revision.

## Existing oncology attribution and authority

H1 already accepts deliberately authored `OI-SYNTHETIC-REPORT/2` inputs. The
shared parser's `OncologyAttribution` and `Finding` types retain each explicit
`Oncology-Finding: key|role|episode|state|quotation`. Allowed roles are `primary`
and `metastasis`; the episode token is a case-local `EP-*` label or `?` for
unassigned. Ordinary findings have no oncology attribution. This is structured
input authored in the original, not a diagnosis extractor.

`sources.py` enables that parser and stores the same canonical original/assertion
rows. `source_integrity.py` checks original hashes, metadata, complete version
chains and assertion tuples, then derives oncology attribution from exact
current source lines. There is no separate persisted oncology attribution table.
`ReportedOncologyContext`, `SourceFinding` and `WorldObservation` in `patients.py`
expose that context. `source_world_model.py` produces a read-only projection;
`source_anchor.py`, source briefs, quotation packets and preserved evidence
reports retain the selected attribution.

The actual web owners are `apps/web/src/registry-client.ts`, `main.tsx`,
`source-contracts.ts`, `source-world-model.ts`, `world-model-view.tsx` and
`source-oncology-label.tsx`. Journey already groups current findings by the
original episode label and displays each statement's state, quotation, document
version and line. `EP-A` is not a canonical clinical episode ID, and an authored
`metastasis` role is not clinician-confirmed spread. There is currently no H1
episode registry, independent tumor/lesion identity, clinical reconciliation
ledger, recurrence/progression model or oncology confirmation API.

| Dimension | Implemented meaning | Phase 1 rule |
|---|---|---|
| Source reported state | `reported`, `negative`, `pending`, `indeterminate`, `not-reported`, `not-assessed`, `conflicting` | Retain the exact source state; absence of a row is not a negative result |
| Laboratory result state | `reported_value` or `reported_absent`, with explicit absent reason; clinical review is `not_performed` | Preserve value/unit/specimen/assay context and missingness; do not infer interpretation from a reference range |
| Source custody state | `current` or `superseded` original | Version availability does not express clinical certainty or review |
| Question freshness | `current_unreviewed_question` or `source_reassessment_required` | Reuse the current snapshot contract; freshness is independent of review |
| Question/human review | `not_submitted`; verification returns explicitly carry `clinical_approval=false` | A return, transcription check or task completion cannot confirm a clinical assertion |
| Note state | Schema/domain vocabulary includes `draft`, `attested`, `draft_correction`, `attested_correction` | H1 exposes draft write/history operations only; its grants have no `note.attest` and its routes expose no attestation action |
| Clinician authority | Synthetic operator grants and actor labels; no qualified clinician credential/attestation boundary | Clinician confirmation remains unavailable until that boundary is accepted and implemented |

The shared encounter domain has an internal `attest_note` method. Its presence
and the schema's attestation vocabulary do not qualify credentials or make it an
H1 action. H1 note creation also does not publish a `clinical_source` version or
turn note text into source-authored assertions. Any future note-to-source or
note-to-episode link needs an explicit immutable note-version anchor and scoped
write contract.

SQLite `scoped_review.py` separates extraction acceptance, interpretation
endorsement and left-open notes on reference snapshots. Reference biological
asset/explanation rows also contain episode strings. These are useful semantics,
not an implemented H1 episode registry or a second source of patient truth.

## Proposed Phase 1: episode identity and source associations

After Phase 0 acceptance, the first increment establishes one save/read/amend
path for a patient-scoped episode identity and a separately attributed source
association proposal. It extends the existing registry, source, question, event
and command boundaries. A bounded `apps/api/src/oi_api/oncology_episodes.py` owner
and additive Alembic migration are proposed; neither exists in the inspected
candidate. Physical schema/table names and exact enums require the scoped
implementation review before migration authoring.

| Proposed record | Required fields and invariants |
|---|---|
| Episode identity | Server-assigned opaque `episode_id`, canonical `patient_id` FK, originating organization, creator and creation time. Identity is immutable, unique and independent of a diagnosis label, source-local `EP-*` token or encounter. Never reassign it to another patient |
| Episode descriptive revision | `episode_id`, revision ID/number, predecessor revision, bounded human label, actor/time, reason, origin (`human_proposal` initially), and explicit record lifecycle (`draft`, `retired`). A retirement means the record was retired, not that a cancer resolved. Append revisions rather than rewriting history |
| Source association revision | Association ID/revision/predecessor, patient/case/org, target canonical episode or explicit unassigned target, exact source ID/version/hash, typed anchor, actor/time/reason, source snapshot contract/hash and proposed relationship. Resolve all source attribution and quotations from the existing source owner rather than storing another source ledger |
| Relationship proposal | Distinguish an independent primary from spread attributed to another episode, recurrence within an episode, historical episode and unresolved origin. Link to the other canonical episode explicitly when proposing spread. Two labels, a shared organ or a shared biomarker cannot establish this relationship. The initial slice implements only the reviewed subset of these proposed relationship kinds |
| Review event | Immutable target revision, action, reviewer actor/time, scope, reason and pinned source basis. Proposed initial actions: transcription checked, disputed or left open. These record the review performed; they do not confer clinical authority |
| Command receipt | Patient/org/request key, operation, canonical request digest, expected revision/source snapshot, immutable result and time. Exact retries recover the original result; key reuse with changed intent conflicts. Write, event, receipt and prepared response must succeed or roll back together |

The first association endpoint should support the existing text-line variant
used by authored oncology findings. Reuse the strict source identity pattern in
`question_anchors.py`: patient, case, source ID, strict positive version, SHA-256
and a strict source line. Future FHIR support must use an explicit resource
anchor with Observation/specimen/report references; it cannot invent a line or
coerce a resource identity into a legacy text anchor. Manual document passages
and encounter notes retain their own versioned anchor types when introduced.

Source-local labels remain scoped by case and original source version. An
operator may propose that two source labels refer to one canonical episode, but
that association must be explicit, attributable and reviewable. A coincident
`EP-A` in another case creates no automatic mapping. Cross-case association
requires the same canonical patient and separately authorized source bindings;
the first slice may refuse it rather than infer it.

Proposed records need orthogonal state dimensions:

- **Provenance:** source-reported content, human association proposal and future
  model extraction proposal remain distinguishable. No model origin is emitted
  without an actual model run and its existing provenance contract.
- **Relationship certainty:** suspected, reported-confirmed, indeterminate,
  conflicting or unspecified can describe what a future typed source explicitly
  states. `reported-confirmed` must display as a source claim; current v2 role
  plus `reported` cannot be silently upgraded into it.
- **Review:** unreviewed, transcription checked, disputed or left open. Clinical
  interpretation and clinician confirmation require their own scoped authority.
- **Freshness:** current basis or source reassessment required, derived from the
  preserved basis and current source owner. A stale proposal retains its prior
  review history and cannot silently inherit approval from a replacement.
- **Record lifecycle:** live draft revision, superseded revision or retired
  record. This is separate from disease activity, source certainty and freshness.

No initial API, fixture, UI toggle or model may write `clinician_confirmed`.
Future clinical confirmation requires verified actor credentials, the accepted
attestation contract, independent grants, the exact interpretation/source basis,
explicit scope and immutable correction/revocation history.

## Conflicts, amendments and historical reconstruction

1. Preserve event date, report-issued time, receipt time and review/recording time
   separately. Receipt order does not prove the clinical order of events.
2. An exact duplicate original retains the existing identity and creates no new
   source-import event. Changed bytes require an explicit amendment of the latest
   same-document version. Existing text-source amendments cannot change the
   original kind, event date or specimen identity; a different event/specimen is
   a separate source, not a convenient replacement.
3. Preserve all original bytes, versions, assertions, association revisions and
   review events. A correction appends a successor with its reason and exact
   predecessor. Never overwrite a prior episode link or silently move an
   association to a different patient, source line or episode.
4. The current source-disagreement detector compares matching specimen, event
   date, finding key, episode and role, and flags coexisting reported/negative
   states. Missing specimens or unassigned oncology episodes are not assumed
   comparable. This narrow detector is not general clinical adjudication; assay,
   method, tissue and time differences require explicit future comparison rules.
5. Missing, not reported, not assessed, pending, negative, indeterminate and
   conflicting remain distinct. A disputed relationship preserves both claims
   and their source/reviewer attribution; a later receipt cannot choose a winner.
6. Existing text and laboratory questions use **whole-source-snapshot freshness**.
   Their owners require both the exact selected source anchor and the saved
   World Model fingerprint. An independent source added to the same case can
   therefore require reassessment even when the selected original is unchanged.
   Phase 1 must preserve this behavior and must not claim anchor-only H1
   invalidation. More selective dependency invalidation needs a separate reviewed
   contract and regression evidence.
7. `0021_lab_citation_freshness` additionally refuses new laboratory citation
   inserts if any source version lacks a prior import event before the saved
   question event. It requires READ COMMITTED and shares the import binding-lock
   discipline. Historical reads/exact receipt retries do not create a new link.
   Episode writes must resolve current sources under the source owner's locks;
   they cannot treat a typed anchor or a cached browser snapshot as authority.
8. On amendment, show the changed original beside the prior association/review
   basis and append a proposed update. Fresh source receipt never automatically
   changes clinical confirmation, resolves uncertainty or endorses interpretation.
   Historical views distinguish the basis known then from the current source set.
9. Reuse independent patient/source/read/write grants, qualified case binding,
   final authorization and audit/command transaction boundaries. Denied reads
   disclose no prepared content; failed/revoked writes commit no partial domain
   row, revision, receipt or success event. Patient/case/credential changes clear
   scoped browser views.

## Acceptance scenarios and ownership

This file adds no runtime behavior and records no new test pass. Existing suites
below identify behavior to preserve; proposed episode tests must exercise actual
domain, HTTP/PostgreSQL, client/component, built browser and recovery paths.

| Scenario | Expected evidence | Existing owner/tests to retain; Phase 1 extension |
|---|---|---|
| Two independent primaries | Distinct canonical episode IDs and explicit source associations; no merge from patient, organ or label similarity | `test_oncology_findings.py`, `test_source_world_model.py`; add episode save/read isolation |
| Unassigned or suspected spread | Unassigned origin and indeterminate state survive save, reopen and review; source-claimed confirmation stays separate from clinician authority | `examples/synthetic/oncology-episodes-v1.txt`, `oncology-episodes-v2.txt`; `apps/web/tools/oncology_episode_journey.py`; add typed relationship proposal coverage |
| Amended pathology changes attribution | New source/version/line and new association proposal; old original and old reviewed basis remain recoverable; uncertainty is preserved | `test_source_world_model.py`, `test_selected_oncology_sources.py`, `test_authored_evidence_postgres.py`; add association revision and history checks |
| Independent source added after save | Whole-snapshot reassessment; no new current citation or episode write from stale context | `test_durable_laboratory_questions.py`, `test_laboratory_metadata_citations.py`; add text and episode stale-basis cases |
| Conflicting biomarker reports | Preserve both states/anchors and assay/specimen context; no automatic negative/positive adjudication or tumor pooling | `test_oncology_findings.py`, `test_source_integrity.py`; add clinical comparison refusal and disputed review cases |
| Malformed or mixed anchors | Refuse boolean/string source lines, coerced versions, cross-variant fields and fake text anchors for FHIR resources | `test_question_anchors.py`, `test_question_anchor_integration.py`; reuse strict identity validation in episode commands |
| Wrong patient, organization or revoked case | Refuse association/read/write without revealing source or episode content; wrong-case originals remain quarantined | Source intake/authority suites; add episode scope and cross-case label collision tests |
| Repeated/lost-response command | Exact retry recovers one result; changed intent or concurrent wrong revision conflicts; no duplicate identity or history | Encounter/source/question retry suites; add episode command-origin recovery |
| Revocation/encoding/event/commit failure | No partial state or success receipt and no prepared disclosure escapes the protected operation | `test_encounter_http.py`, source/evidence authority suites; add episode final-authorization and rollback probes |
| Encounter draft versus source assertion | Draft-note edits preserve immutable note history and never become clinician confirmation or source assertion automatically | `test_encounter_http.py`, `tests/test_clinical_encounters.py`; add explicit refusal of unsupported note/episode promotion |
| Populated upgrade and restore | Preserve both published 0019 histories, join and 0021 guards; episode identities, source refs, notes, questions, receipts and sequence states survive restart/restore | `test_ehr_laboratory_convergence.py`, laboratory/encounter migration and recovery owners; add populated episode upgrade and restored HTTP checks |
| Patient explanation and history | UI shows exact origin, uncertainty, fresh/stale basis and review scope; source amendment offers a proposal rather than a confirmed replacement | Existing Journey/source-question/browser owners; add one save/read/amend episode browser journey |

Backlog mapping remains OI-006 (sources and typed assertions), OI-007 (questions
and scoped review), OI-009 (second time point), OI-010 (connected workflow), and
OI-013 (isolation, authorization and recovery). Subsequent conditions,
medications/allergies, observations, staging and treatments extend the same
patient and source boundaries as separate reviewed increments. This design does
not establish clinical validity, real-data permission or production readiness.
