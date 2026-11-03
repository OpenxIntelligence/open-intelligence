# Connected reviewed intake: existing dependency-rights safeguards

## Current candidate — reviewed-document convergence in #354

**Checkpoint: 3 November 2026. Local composition verified; exact combined
hosted acceptance pending.** Continue the existing [draft #354](https://github.com/OpenxIntelligence/open-intelligence/pull/354)
from `d9b81f08a97998e8f95d2a1cc7c43b4165e99862`. Main was separately observed at
[`c4798ae85004713593f83458abd2102be6729095`](https://github.com/OpenxIntelligence/open-intelligence/commit/c4798ae85004713593f83458abd2102be6729095)
and remains the Python/SQLite reference; this H1 composition is unmerged and
undeployed. Earlier receipts below retain their original heads and scope.

| Included owner | Frozen input | Contribution to the existing candidate |
| --- | --- | --- |
| #354 | `d9b81f08a97998e8f95d2a1cc7c43b4165e99862` | Reviewed text/PDF originals, immutable selections, comparison drafts, exact receipt recovery, document-denial reset and dependency identity checks |
| #368 | `2d62b05357ad64524d561c2e05c903674cd4e54c` | Evidence chronology, truthful recovery status and memory-only verification-return drafts; includes the #324 repair through its connected lineage |
| #369 | `3c028ddfb4b408571b36140a5e5b52115c7bd790` | Strict task/history timestamps and withholding actionable controls after a malformed response |
| #362 | `c7fd1bd865f4a8f42da1e515a2599431d14f0a8d` | Existing source-recovery probe extended to reviewed-document HTTP, exact retries, independent grants and revoked binding on restored PostgreSQL copies |
| #367 | `bbf56762e73f50fbe6432768deb605ed03edf09b` | Shared H1 acceptance-input triggers, the existing data-boundary audit and reconciled documentation |

The [bounded execution plan](../superpowers/plans/2026-11-03-reviewed-document-convergence.md)
defines the source reconciliation, tests and publication sequence. Preserve
#354's document-aware RegistrySession, published `0012_reviewed_documents`
migration, exact dependency set, PDF controls and existing authority owners.
No new backend contract, state owner, dependency, model or clinical function is
introduced. The accepted H1 stack, source/current-rights checks and synthetic-only
development boundary remain controlling.

Combined acceptance must exercise the complete document/evidence/review/task
journey on one exact head. In particular, a current document denial must clear
an unsent Review reason and prevent its resurrection after fresh access, while
temporary or stale failures preserve independently authorized newer work.
The two-case Review journey precedes the document journey that creates a third
case. Actual restored-document HTTP must run in the full combined API/recovery
gate; the donor's successful run does not qualify this new composition.

### Observed local verification at this integration checkpoint

| Check | Result |
| --- | --- |
| Donor chronology/task regressions against the old runtime | 24 failed and 27 passed before composition |
| Complete client suite after composition | 415 passed; zero skips |
| TypeScript and Vite production build | Passed |
| Existing rights controls and installed-artifact gate | 13 controls passed; 18 installed entries inspected, two absent optional entries explicitly uninspected, zero gate errors |
| Restored-document recovery assertion tests | Nine passed |
| Existing synthetic data-boundary audit | Passed; a bounded source-pattern audit, not runtime egress proof |
| New Review-draft/document-denial browser interaction | Added and syntax-checked; not executed locally |

These are local source and fixture checks. Exact combined hosted
API/PostgreSQL/recovery and React/Chromium acceptance is **pending at this source
checkpoint**. Final independent-review disposition, published identity and hosted
results are recorded in the existing [PR #354 verification receipt](https://github.com/OpenxIntelligence/open-intelligence/pull/354)
as they complete. That receipt must identify this composition; historical donor
successes are not substituted.

Manual document selections remain explicitly manual and excluded from structured
World Model/question/report snapshots. Connecting that provenance is subsequent
work. Separate DOI, imaging/archive and clinical-domain candidates are not
included by reference. Independent user/clinical validation, production
identity/delegation/consent, permitted biomedical/model activation, release-wide
rights, merge and deployment remain separate gates.

## Historical rights-only scope and ownership

Bounded implementation of OI-004 and OI-010, linked to #59 and #121.
This carries the existing #339 frontend rights fix into the reviewed-document
workspace #349. It creates no new patient/source/evidence owner, dependency,
clinical function, architecture decision or release clearance.

Initial input: #349 at `51cdc6fd6281d0361c371a25cb00cef0167b880f`.
Reused donor: #339 at `d694db4ca12206e815d6045b73baa9b6f7394290`.
The API, database, migrations and source owners are unchanged by this rights
increment. After the initial web pass, #349 advanced to
`03ccca85026c5d437a288f62c5b48f4a74054bfa`. That parent's seven changed files were
merged byte-for-byte: document denial/reauthorization and file-discard behavior,
associated tests/browser acceptance, the reference-UI YAML repair and receipts.
These are parent-owned corrections, not another implementation. The final PR
records the new combined head and its separate verification.

## Why this change

The pinned workspace's earlier frontend license gate accepted a different
installed package with the same version/license and followed linked package
or evidence paths. A permitted license label alone did not establish that the
evidence belonged to the locked package. #339 already corrects this behavior;
the connected reviewed-document candidate did not include it.

Reuse the reviewed four-file implementation rather than write another gate.
The alternative of adopting another scanner or changing dependencies does
not address this narrower identity/evidence integration gap.

## Exact source reuse

| Path | Reused Git blob from #339 |
| --- | --- |
| `apps/web/package.json` | `21297facf25f310d34b5e2b7dda28989adf4877e` |
| `apps/web/tools/license-gate.mjs` | `89a971105a7835d3e637ded7d381fd037d1a2f90` |
| `apps/web/tools/license-gate.test.mjs` | `3c27d2d6e7a9d12bc58adf9598d24bb0cfe920f4` |
| `.github/workflows/h1-web.yml` | `364cf6d900161ac8a12aa819f76cc9d6f2bb9129` |

The workflow differs from the input only by running the existing `npm run rights`
command with retained test output (and a trailing blank line). Its actual
PostgreSQL/FastAPI/React browser journey is preserved.

## Behavior and acceptance

- Require installed package name, version and license declaration to match
  the lock, including npm aliases, scopes and nested packages.
- Reject unsafe lock paths, linked package ancestors and linked evidence files.
- Do not include out-of-package evidence bytes in the generated inventory.
- Record absent optional dependencies as uninspected; reject an installed
  optional package with a missing manifest.
- Execute the existing 13 rights regressions before inspecting installed
  dependencies and before compiling the UI.
- Preserve `commercial_release_cleared: false` and all existing scope limits.

## Execution plan and evidence

1. Run the unchanged donor regression suite against the pinned old gate.
2. Import the four donor blobs without alteration.
3. Repeat the same tests and verify blob identities.
4. Publish a draft child of #349 and inspect its own hosted web acceptance.
5. Retain the parent API/recovery receipt separately; no API or migration
   file changes are made here. Parent evidence must not be relabelled as
   execution at the child commit.

Local execution on 3 November 2026: donor regressions reproduced failures on
the old gate; after source reuse all 13 passed with zero skips. The final PR
records the exact published head and hosted results. No installed-package,
React-build, browser or database pass is inferred from the local fixture suite.

## Remaining boundaries

This is a dependency-evidence check in a controlled build workspace, not
malicious-concurrent-filesystem confinement, full binary provenance, legal
approval or whole-product supply-chain clearance. Optional native artifacts,
models, datasets, content and deployment services need separate exact-artifact
review. The initial rights-only import excluded comparison and verification
drafts. The continuation below explicitly includes #348/#359 comparison drafts;
#324/#345 verification-draft continuity was separate at that checkpoint. The
current composition above carries #324 through #368. No merge or deployment.

## Historical #354 checkpoint: reviewed documents and recoverable comparisons

That #354 continuation composed the existing document/rights workspace at
`306c6d90cb77b87debe5858baeb244fd038d5748` with the comparison/receipt owner
#359 at `e2c888cf5b9065c8b6a60284666e6f35fe2c1e63`. That donor includes #348
at `d15aa208adcb13b3c0621cc44a384a8fa37affb3`. Both ancestries are preserved.
OI-008/009/010/013 join the existing OI-004 scope; there is no new state owner.

The donor session, panel, draft/receipt regressions and authored-evidence browser
journey are reused byte-for-byte. Registry integration adds only its type import
and four delegates to the current document-aware session. Both appended owner
receipts are retained in `H1_EVIDENCE_CONTINUITY.md`. Backend, migrations,
dependencies, rights gate and document browser code remain unchanged.

Unfinished comparisons retain quote, relation, applicability and rationale in
memory through evidence refresh and navigation. Fresh matching authority is
required to reveal or submit them. Contradictory HTTP status/duplicate receipts
retain the frozen request and lock editing/discard until explicit exact recovery.
The visible copy distinguishes an unknown submission from an unsent draft.

Eight added composition checks exercise document list/original denial (401, 403,
404), delayed evidence responses, empty reauthorization, temporary 503, and stale
denial after a newly authorized comparison. They protect the existing shared
document-denial reset; no second authorization mechanism is introduced.

### Evidence and execution sequence

1. Restore and compare every base source blob with Git: all 429 matched.
2. Install the locked local toolchain from cache without lifecycle scripts.
3. Run donor tests before reuse: 327 passed, 48 failed for absent draft methods
   or accepted contradictory receipts; the eight new composition cases also
   failed against the original runtime. Compilation succeeded.
4. Merge the existing owner code and retain both appended documentation sections.
5. Removing only the shared document-denial reset makes four 403/404 cases fail;
   the two credential-expiry and two temporary/stale-denial controls still pass.
   Restoring the owner reset passes all eight composition cases.
6. Full local client suite: **383 passed, zero failures/skips**. Production
   TypeScript/Vite build passed. The exact published head requires its own hosted
   dependency and actual PostgreSQL/API/React browser verification; the PR carries
   that receipt after execution. Ancestor passes are not combined-head acceptance.

The local optional-inclusive install exposed an optional native package without
its required notice and the rights gate correctly refused it. Repeating the
existing CI install policy (`--omit=optional`) keeps absent optional packages
explicitly uninspected; no license rule, dependency or allowlist is relaxed.

The corrected document parent #349's full API/recovery workflow
[41678135225](https://github.com/OpenxIntelligence/open-intelligence/actions/runs/41678135225)
completed successfully at `03ccca85026c5d437a288f62c5b48f4a74054bfa`: 427 API
tests, 304 reference tests and all five patient/source/review/follow-up/evidence
recovery steps. This remains parent-head evidence for the unchanged backend.

At that checkpoint, combined owner review, manual-document provenance in
questions/reports, document HTTP against a restored database copy, and
professional/clinical validation remained open. Sibling DOI, chronology,
imaging/archive and verification-draft work was not included. The current
section above records the later local composition of chronology, review drafts
and restored-document acceptance, whose combined hosted execution is still
pending. Synthetic inputs only; draft and undeployed.
