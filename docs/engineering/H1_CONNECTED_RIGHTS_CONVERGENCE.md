# Connected reviewed intake: existing dependency-rights safeguards

## Scope and ownership

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
#324/#345 verification-draft continuity remains separate. No merge or deployment.

## Continuation: reviewed documents and recoverable comparisons

PR #354 now composes the existing document/rights workspace at
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

This continuation is self-reviewed engineering composition. Combined owner
review, manual-document provenance in questions/reports, document HTTP against a
restored database copy, and professional/clinical validation remain open. The
other sibling DOI, chronology, imaging/archive and verification-draft work is not
included by this continuation. Synthetic inputs only; draft and undeployed.
