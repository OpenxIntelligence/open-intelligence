# H1 canonical question → governed evidence metadata

## Bounded implementation plan — 3 November 2026

**Goal:** let an authorized person discover independently authored fictional
research-source metadata, inspect its exact version and rights state, and retain
a citation beside an existing H1 question. Citation identity verification does
not establish that a source supports a claim.

**Spec:** the founder's unified execution directive; existing OI-004/007/008/009/013,
[WS-06 #117](https://github.com/OpenxIntelligence/open-intelligence/issues/117),
and [#224's catalog/citation contract](https://github.com/OpenxIntelligence/open-intelligence/pull/224).
This is an integration increment, not another master architecture.

**Base:** published #293 `635f357048eb27e52e6ec5c3d7b6714215070127`, exact tree
`74c4a2ab65bf54a0908246199bb67c300ae2662b`. It preserves #287's canonical
source/question/review-return/brief workflow and durable follow-through.

**Architecture:** reuse #224's typed metadata and citation validation contracts,
with explicit stored scope and version checks; adapt persistence to the existing
H1 PostgreSQL transaction. Canonical sources, questions, identity, events,
review returns and tasks remain their current owners. The SQLite catalog is an
isolated reference fixture, never a second patient chart. No new dependency,
network fetch, provider, model, clinical authority, or content license is adopted.

## Tasks and acceptance

- [x] Reproduce and fix the inherited catalog's scope, version-search and malformed
  rights-flag defects before reusing its pure contracts.
- [x] Add immutable versioned metadata, append-only rights decisions and immutable
  question/citation links in the existing `investigation` schema. Preserve all
  prior migrations; reject incompatible pre-existing objects. The new migration
  follows `0009_question_followthrough`, without rewriting earlier revisions.
- [x] Expose independently authorized metadata search, citation linking and history
  on the existing patient/question router. Prepare actual JSON under source and
  evidence locks; check grants and evidence rights before committing access events.
- [x] Connect the saved-question UI. Show current/restricted/superseded and source
  reassessment states, clear obsolete results after context changes, and recover
  uncertain link writes with the same request key.
- [x] Verify actual API persistence, wrong-patient/tenant denial, unknown/revoked
  rights, exact versions and metadata hashes, malformed input, concurrent retry,
  failed serialization/audit rollback, amendments, restart and backup/restore.
- [x] Run inherited API/reference/client/build gates and a real built-browser
  journey, inspect the result, publish a draft for independent review, and update
  the existing GitHub/Notion/Drive receipts with exact evidence.

## Review focus

Metadata rights must permit both storage and display before searchable fields
leave the server. Search must not use an unauthorized title to reveal a matching
record. A valid identifier cannot grant authority or prove claim support. A
case-bound record must match its stored organization and case, even when a caller
supplies a different scope map. A version-specific result cannot borrow another
version's terms. Revocation hides previously visible metadata on the next read;
the immutable link identity/history remains inspectable under patient access.
An amendment preserves old links and flags their original question context stale.

## Current evidence and limits

Implementation checkmarks record the bounded work; verified combined acceptance
is recorded below. They do not establish deployment or clinical acceptance. The draft is [PR #298](https://github.com/OpenxIntelligence/open-intelligence/pull/298),
stacked on the explicitly identified #293 commit. No contributor branch is
rewritten and no PR is merged.

Tests-first commit `9cdb89711228bcffde6476f9001626d645b6128c` produced
[API run 41636114987](https://github.com/OpenxIntelligence/open-intelligence/actions/runs/41636114987):
336 tests, seven failed endpoint/body-boundary assertions and eight missing
adapter errors. These negative results are preserved. Backend candidate
`100512e734361153d70bd4cd3da272b8bb49cf01` has the exact tree
`d3bf2f09ec4b5ce9b866fc0559c8b2a828771e73`; its initial hosted PostgreSQL acceptance passed
339 API/database tests and 282 reference tests with zero skips, plus the inherited
browser and recovery probes, in [run 41638165761](https://github.com/OpenxIntelligence/open-intelligence/actions/runs/41638165761).

Local integration checks include 13 HTTP/OpenAPI/migration graph tests. The
source-owner catalog regression has 37 focused checks and 282 reference tests.
An independent review identified the different-case patient-wide request-key
race and a rights change during the audit tail. The former now uses a conflict
receipt; the latter was reproduced with an explicitly doubled source lookup
and connection, then fixed by a final authorization/rights check after the
source receipt. Actual PostgreSQL versions of these failure paths are included
in the combined acceptance suite. A unit double is not database evidence.
The frontend has 219 passing local tests (195 inherited, 17 client and seven
rendering) and a successful production build. At that local checkpoint, new
browser and evidence restore probes were still pending. Their subsequent
combined-head results are recorded below.

The retained dependency locks are unchanged. The donor pure modules and authored
fixture are attributed to #224 at `57fb58bab63a931874e5e768858d741459aeb7fa`.
No claim is made that the entire inherited application/container distribution
has commercial clearance; existing native/runtime and content holds remain.

The 334 tracked files of the base were compared to their published Git blobs;
the complete tree and published commit were reconstructed exactly. Baseline
client tests: 195 passed, zero skipped. The local executor contains PostgreSQL
16.15 binaries but cannot change to an unprivileged database account (`setresuid`
returns `Invalid argument`), so PostgreSQL acceptance must run on the existing
hosted disposable-database workflow. Local skipped cases are never counted as
database passes. No real-patient input or third-party clinical content is used.

This increment intentionally remains metadata discovery and citation linkage.
Clinical evidence appraisal, scientific/model execution, evidence-rich reports,
professional review, ordinary medical uploads and real identity/consent remain
separate integration and validation work. Existing #249/#250/#272 report and
clinical evidence owners are preserved for that next adapter.

## Verified combined acceptance — 3 November 2026

**Runtime revision:** [f4750327537a5febf764d25f43873be50ac7265a](https://github.com/OpenxIntelligence/open-intelligence/commit/f4750327537a5febf764d25f43873be50ac7265a).
**Tree:** `69f24319f8aa75b707ae33474f7fab8254a83773`.
**Delivery:** [draft PR #298](https://github.com/OpenxIntelligence/open-intelligence/pull/298),
branch `integration/h1-question-evidence-20261103`. Unmerged, undeployed and
not clinically validated. Later documentation-only receipts do not change the
runtime, migration, dependency or test content identified here.

| Verification | Exact evidence | Observed result |
|---|---|---|
| API contracts, migrations and real PostgreSQL 16.15 | [run 41639678827](https://github.com/OpenxIntelligence/open-intelligence/actions/runs/41639678827), job 125929702981 | 354 tests passed in 358.210s; zero skipped. CI checks out and verifies the proposed head. |
| Original Python reference regression | Same API run; `PYTHONPATH=src python -m unittest discover -s tests -v` | 282 tests passed in 13.034s; zero skipped. |
| Real reference browser journeys | Same API run; `tests/browser_journey.py`, `tests/patient_mission_browser_journey.py` | Both completed successfully. |
| Actual API/DB restart and PostgreSQL dump/restore | Same API run; `verify_registry_compose.py`, `verify_sources_compose.py`, `verify_reviews_compose.py`, `verify_followthrough_compose.py` | All four passed. The final probe includes immutable evidence metadata, citation identity and append-only rights history, restored HTTP access and denial. |
| Frontend unit/rendering and production build | [run 41639678872](https://github.com/OpenxIntelligence/open-intelligence/actions/runs/41639678872), job 125929703047; `npm test`, `npm run build` | 219 tests passed: 195 inherited, 17 evidence client and 7 rendering; zero skipped. Production build passed. |
| Built React→FastAPI→PostgreSQL evidence workflow | Same React run; `python apps/web/tools/browser_journey.py` | Actual metadata search/save; committed 201 response loss; identical 200 retry and one link; amendment; rights revocation; stale-response suppression; independent read denial; desktop/mobile capture. |
| Separate legacy UI workflow | [run 41639678834](https://github.com/OpenxIntelligence/open-intelligence/actions/runs/41639678834) | Completed with success. |

The evidence restore probe records two fictional metadata records, one citation
and three rights decisions (including revocation). API and database restarts,
actual `pg_dump`/`pg_restore`, and an API pointed at the restored database retain
those originals and the original retry receipt. A fresh read returns
`rights_restricted` with `record:null`; no cached title or URL is restored.
Revoking the restored patient/case binding denies reads and retries without a
new effect. This is software recovery evidence, not clinical validation.

The browser artifact is [13232471263](https://github.com/OpenxIntelligence/open-intelligence/actions/runs/41639678872/artifacts/13232471263),
`h1-web-verification-41639678872-1`, SHA-256
`eef7adf6136c505179310360f5a1a986064e50ddaf647a82ab0612bb0e9c0827`.
The archive was downloaded, its digest and `commit.txt` verified, its synthetic
receipt inspected and its desktop/mobile captures reviewed. The workflow sets
seven-day artifact retention; source, tests, hashes and this durable receipt
remain in Git. Captures support inspection; the actual browser/API assertions
establish behavior. This does not establish complete WCAG conformance.

Independent review verified all 50 changed paths against their published Git
blobs, retained donor attribution, and confirmed unchanged dependency manifests,
locks, license inventories/notices, container definitions and workflows. Review
found no remaining blocking issue in this bounded slice. External maintainer
review remains open; no agent self-approved a PR merge or commercial clearance.

### Canonical record updates

All six existing records below received one scoped receipt for runtime
`f4750327537a5febf764d25f43873be50ac7265a` and were read back on 3 November
2026. Prior content was preserved; no replacement master, assignee change or
rights-clearance promotion was created.

| Existing record | Verified update |
|---|---|
| [Notion Engineering 12](https://app.notion.com/p/40a3866f77ef8197ae65e727c8907eb3) | Edited at 13:07:39.339 UTC; exact runtime/tree, test counts, run links, recovery and artifact digest present. |
| [Notion Contracts 14](https://app.notion.com/p/40a3866f77ef8122b08bcdc16de89876) | Edited at 13:07:33.495 UTC; migration, canonical ownership, rights, retry and amendment boundaries recorded. |
| [Notion Technology 04](https://app.notion.com/p/40a3866f77ef811c969fc38e95027ec2) | Edited at 13:07:34.706 UTC; unchanged retained stack, research holds and unresolved catalog discrepancies recorded. |
| [Notion Rights 11](https://app.notion.com/p/40a3866f77ef815a97d5e016ededf5b9) | Edited at 13:07:35.619 UTC; fictional metadata, operation-specific rights and remaining holds recorded. |
| [Drive Current Truth](https://docs.google.com/document/d/1rDcbE4BWOYFws-TAm1oGGQFb9gJVle1WxUHFn_2SnqM) | Revision-guarded append; read-back equals the previous document plus the intended receipt, with native heading and linked sources. |
| [Drive Engineering Progress](https://docs.google.com/document/d/1Zbn-8Z5fABdGrJa5W0kSh4ojSVFvd1ddXdvW6pHr9gA) | Revision-guarded append; read-back equals the previous document plus the intended receipt, with native heading and linked sources. |

The Drive read-back revisions are respectively
`AHj4eMRiQfhXBTMZvHxRQwdWMECWXitVnRThFyqzHSMQdRKIZATMPq12emxDaY2pxSAvH5OIIDKEDiG5aolvoX_qReeFTylxL1g2Tv0L4n0`
and
`AHj4eMQdDO3ZFEIsHGJtTMXhwOmPKyDemi25SHxJQ1rycrjCwD7Zj5DqsEfsZExHURG2DNnwaYXfb2SSJdFyl4dKM3WalFO_trZMASMTnxM`.
Engineering 12 received a concurrent unrelated #301/B-01c prepend; its prior
content and this receipt were both preserved. That other work is not claimed as
integrated into #298. No canonical write or read-back remained blocked.

### Regressions preserved

- The tests-first remote revision has seven endpoint/body-boundary failures and
  eight missing-adapter errors, linked above.
- Inherited catalog scope, exact-version search and malformed-rights regressions
  were reproduced before correction; 37 focused catalog/citation tests pass.
- Contradictory or unsafe response DTOs produced 58 failing subcases across 10
  methods before correction. The corrected contract rejects mismatched IDs,
  hashes, disclosure state and unsafe links.
- The audit-tail unit regression failed before the final rights recheck. Actual
  PostgreSQL tests now also verify rollback after same-transaction rights change
  and catalog locks through response encoding.
- Client regressions cover independent read denial, temporarily absent question
  projections and denial of an already-uncertain retry. None may turn an unknown
  original commit into permission to create a replacement write.

### Exact continuation

Next owned evidence work is an explicit PostgreSQL adapter for the existing
permitted-source and investigation/report contracts, beginning with one bounded
live metadata connector and recorded source/version/operation rights. Reuse the
existing Crossref metadata reference and WS-06/#224 owner; reconcile #249/#250/#272
report owners before porting appraisal or scientific execution. Do not copy H1
patients into a separate SQLite chart or treat a catalog citation as claim support.

Acceptance for that next slice: a genuinely retrieved permitted record resolves
from its stored identifier/version; retrieval/rights/freshness receipts survive
restart; unavailable service, changed terms, withdrawn permission and wrong
patient/tenant fail closed; material report claims have independently reviewable
support/applicability; no model execution is claimed without an actual run.
Production identity/consent, ordinary medical uploads, EHR/LIS convergence,
clinically qualified review and the full oncology MVP remain open and have their
existing owners. No clinical release or real-patient processing is authorized.
