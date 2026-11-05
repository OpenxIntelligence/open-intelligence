# Open Intelligence master execution plan

Date: 2026-11-05. Authority: founder's Master Engineering Execution Mandate,
post-audit implementation, consolidation and platform development (2026-11-05).

## Goal and constraints

Deliver one recoverable H1 application, then extend its existing clinical source
owners into a typed oncology record. React/TypeScript/Vite and
FastAPI/Pydantic/SQLAlchemy/Alembic/PostgreSQL remain canonical. The SQLite
application is a reference, not another production clinical store. Use only
independently authored synthetic patients. Models produce proposals; existing
authorization and command boundaries own every clinical write. No merge,
production deployment, license selection or external data egress is authorized.

## Phase 0: one integration candidate

Accepted main was inspected at `f188aecc70f3415741dac0e7dd5bf3f2d9fd02a9`.
PR #481 is merged at `62e218e1e2bd6996bb126fcc1ea956fcf18199e6`; do not
reapply it. Current main already preserves source-reported cancer episodes.

The smallest consolidation is to join these existing first-party changes:

| Input | Frozen revision | Contribution |
|---|---|---|
| #536 | dd8d1ddc6846f6aa3960fa489118e18db7cb65fb | Laboratory workflow and accepted-main agent provenance |
| #537 | 1f92eb0aa426597052f528234a3a7e0a97dcf2ed | Encounter/note routes and joined EHR/lab migrations; preparation UI |
| #540 | 299cfb54df8259c6d72ddd88f3e0c08ca3dda3f4 | Database enforcement of full-case laboratory citation freshness |
| #539 | 917cc14bdc0f298bc33d06b09125cd4658205eec | Shared strict text/FHIR question-source identity |

### Task 1: preserve typed identity on the joined application

Files: `apps/api/src/oi_api/question_anchors.py`, `composer_preflight.py`,
`source_questions.py`, `question_followthrough.py`; donor tests
`test_question_anchors.py`, `test_question_anchor_integration.py`,
`question_anchor_fixtures.py`, `fixtures/question_anchor_compatibility.json`.

- [x] Run the donor regression tests against #540 before adding #539's owner
  code. Expect refusals of coerced source lines/versions to fail.
- [x] Merge the complete #539 history into an isolated branch based on #540;
  preserve both parent histories and all migration bytes. Resolve only actual
  conflicts, without rewriting either source owner.
- [x] Run the same tests; require all 25 methods and all 13 frozen compatibility
  outputs to pass. No API payload or request fingerprint may change.
- [ ] Run full available API/reference/client/build/rights checks. Run exact-head
  hosted PostgreSQL/migration/recovery and browser checks before acceptance.
- [ ] Obtain independent engineering review; fix material findings with a
  reproducing regression. Keep main and donor branches unchanged.

Interfaces: the shared immutable anchor validates identity only. The existing
source owner retains patient/case authorization, original-byte checks, freshness,
final authorization and audit receipts. Existing EHR note and laboratory owners
remain distinct. `0021_lab_citation_freshness` follows the no-DDL
`0020_ehr_lab_convergence` join of both published 0019 migrations.

Independent review found that 0021 counted reviewed documents excluded by the
canonical structured-source snapshot. The new populated PostgreSQL regression
failed with HTTP 503 in run 42096046609 (five other joined-core tests passed).
Additive `0022_lab_citation_source_scope` replaces only the guard function,
retains the trigger/locking/READ COMMITTED restrictions, and restores original
0021 semantics on downgrade. Its regression also verifies row/sequence
preservation, exact retry and the downgrade/reupgrade path. Fresh post-restore
laboratory writes and restored EHR note writes now exercise the actual API.

Review focus: coerced or mixed text/FHIR anchors; independent-source amendments;
transaction-wide stale snapshots; revoked permissions during a write; populated
upgrade/retry/recovery from both published migration parents.

### Task 2: establish delivery management and handoff

- [ ] Maintain all eight files in this directory as current evidence indexes.
  Preserve older checkpoint documents as historical evidence.
- [ ] Record exact local commands, failures, skips and hosted commit IDs in
  `RELEASE_ACCEPTANCE.md`; never inherit donor results as combined acceptance.
- [ ] Publish a separate reviewable draft candidate, without merging or deploying.

## Phase 1: typed oncology record, after consolidation acceptance

Existing source attribution (`ReportedOncologyContext`, immutable source versions,
World Model observations, Journey episode groups) remains the source evidence.
Do not infer a clinically confirmed episode from a source-local label.

| Increment | Exact existing owners to extend | Acceptance |
|---|---|---|
| Episode registry and source associations | `src/open_intelligence/postgres_registry.py`; `apps/api/src/oi_api/sources.py`, `patients.py`, `source_world_model.py`; new bounded `oncology_episodes.py` owner and next Alembic revision | Two primaries, suspected/confirmed spread, historical/new primary; preserve source version/line and patient/case identity |
| Episode API and workspace | Existing patient router/composition in `apps/api/src/oi_api/patients.py`, `app.py`; web `registry-client.ts`, `main.tsx`, `source-contracts.ts`, `source-world-model.ts`, `world-model-view.tsx`, `source-oncology-label.tsx` | Persist/reopen on one patient; independent grants; source inspection and amendment remain available |
| Reviewed assertions and correction lifecycle | Existing source, question, review, event and command receipt contracts | Extracted/proposed/reviewed/clinician-confirmed never collapse; immutable history and dependent proposal invalidation |
| Conditions, medications/allergies, observations | Same patient registry; separate bounded domain owners, reversible migrations, Pydantic and React contracts | Unknown/not tested/missing/negative distinct; versioned terminology and units; authorized reconciliation |

Before writing a new migration, recheck the current integration head and open PRs;
do not reserve a revision number against a moving repository. Model proposed
episode links separately from reviewed clinical reconciliation. Current synthetic
authorization does not establish clinician credentials, so clinician confirmation
must remain unavailable until its credential/attestation boundary is accepted.

Each Phase 1 increment needs domain/API/PostgreSQL/component/browser tests,
populated migration and restart/restore checks, wrong-patient isolation, revoked
reviewer/write rollback, amended pathology and conflicting biomarker cases.
The next implementation is episode identity plus source associations through one
end-to-end save/read/amend path, after Phase 0 exact-head review is accepted.

## Later phases

Proceed in mandate order: document/pathology proposals; chronology and licensed
staging; permission-filtered copilot with claim support evaluation; versioned FHIR
and terminology mappings; treatment; imaging; tumor board/trials/registry;
reproducible bioinformatics/discovery. Each is a separate tested increment. The
interoperability, AI and governance files here preserve the acceptance boundaries.
