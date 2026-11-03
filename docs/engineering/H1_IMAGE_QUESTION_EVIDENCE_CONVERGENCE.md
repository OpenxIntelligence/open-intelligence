# Original images in the canonical question, task and citation workflow

## Preserved owners

This integration joins two existing first-party H1 owners and adopts their existing
bounded citation-history correction:

| Owner | Exact remote head | Preserved responsibility |
| --- | --- | --- |
| [#298](https://github.com/OpenxIntelligence/open-intelligence/pull/298) | `89f98824610e23a26d2904a845ed1d930207bd76` | Canonical patient/source/question, source packet/brief, verification return, follow-through and governed metadata/citation history |
| [#278](https://github.com/OpenxIntelligence/open-intelligence/pull/278) | `b72560ac0f5e5005040b0fc660ce1650343611cf` | Exact image custody, original source/image links, complete image/review response preparation and restored image/question/return HTTP |
| [#311](https://github.com/OpenxIntelligence/open-intelligence/pull/311) | `8f7ad6a80dcb5312bc63480339d9142376883a4a` | Exact two-file correction for visible, actual-calendar citation timestamps with explicit valid offsets |

The patient remains the organizing center. This joins information and work that
already belong to the same qualified case. It does not introduce another chart,
question owner, task store, citation catalog or event journal.

## Connected behavior

An original imaging report and its exact DICOM bytes coexist with a question
pinned to its original source/version/line. Existing independent operations can
inspect the source quotation, prepare the source-only brief, record a verification
return, create and update follow-through work, and retain a permitted metadata
citation. Image access receipts do not change content fingerprints.

Amendment preserves the original bytes, old question anchors and committed return,
task and citation history. The old question requires reassessment; an explicit
same-byte image relink reuses the immutable object without making that question
current. Existing exact retries recover their original IDs under the current
owners' authority and rights rules. A fresh question supports distinct current
intent. Task history keeps its operational meaning throughout.

Image import, image metadata, original bytes, verification returns, task actions
and metadata/citation actions retain independent grants. Citation rights cannot
grant image access. Withdrawing metadata rights redacts restricted title/URL data
while preserving citation identity; it does not rewrite image or task history.
Withdrawing a qualified case binding denies the relevant operations and new
receipts. Failed attempted image effects leave committed sibling history intact.

## Migration contract

The 14 distinct published migrations remain byte-identical. The only new revision
is the no-DDL `0011_image_evidence_merge`, joining `0009_image_review_merge` and
`0010_question_evidence`. Readiness requires exactly that one complete head.

Populated acceptance covers either parent and both separately applied heads,
preserved owner rows/schema/original bytes, unknown image/task/evidence ownership
rollback, and the inherited immutable-history and downgrade protections. The new
graph test first observed the two unjoined heads and then passed with the merge.

## Response and recovery contract

The #278 image routes retain their complete JSON/binary preparation before final
authority, audit and commit. #298's review, task and evidence owners retain their
existing response preparation, locking and rights checks. Integration does not
broaden that claim to every source/World Model/Composer endpoint; separate
original-source disclosure work remains with its existing owner.

All four #298 Compose gates remain, and the #278 combined image gate is retained
as a fifth. That gate now records image/question/return/task/citation history,
restores an actual PostgreSQL backup and reconnects the real API to the restored
copy. It reopens exact originals and old/current history, explicitly retries the
original intents, and checks that new HTTP receipts exist only in the restored
database. The original database must remain unchanged. Restored metadata-rights
and case-binding revocation retain redaction/denial without new effects.

## Archive and original-source continuation

This continuation starts from corrected #313 at
`f6132e894a21a326f72660c3399499ccbf251831`, preserving #311's timestamp
validation and all published migration bytes. It reuses #312 at
`9cd218210099c69d04b023ef77f9051a32206fc4` for optional archive reads, the
three existing archive regression modules and the explicit test-only file
archive. The older verification and continuation receipts below remain history;
their statement that #312 is separate describes those earlier checkpoints.

An injected archive receives only canonical stored Study/Series/SOP identifiers
after the existing patient/source/image preflight. Source-owner locks are released
during I/O. A fresh transaction validates the source, binding and exact original
bytes, prepares the complete response, refreshes authority and commits the access
receipt before returning. Missing, altered or non-byte results withhold content;
valid local originals do not authorize a fallback. Default local custody remains
the ordinary application path. No new patient, source, image, task or evidence
owner, route, permission, setting, dependency or migration is introduced.

The audit also identified #304's existing original-source disclosure correction
at `6532e394411f66272c88bce63002dcd40ffbcd37`. Its response-preparation pattern
is selectively applied to `PostgresSourceVersions.original` and the one original
route, preserving this branch's shared `_validated_original` implementation.
The owner allocates one receipt ID, prepares the complete OriginalSource JSON,
then performs its existing final-authority/receipt/commit protocol. Its four
exact donor HTTP/PostgreSQL regression methods are retained. This does not import
the separate authored-evidence/report owner's other routes or schema.

New connected HTTP/PostgreSQL tests combine archive reads with #313's questions,
verification returns, task transitions and metadata citations. They verify old
anchors and retry identities after amendment, explicit image relinking, fresh v2
work, restricted metadata, independent grants and unchanged sibling history when
archive retrieval fails. The existing archive regressions retain late-authority,
unlocked-I/O, response-preparation and deferred-commit checks. The original local
ordering double explicitly selects `archive=None`; its assertions are unchanged.

The five existing Compose gates remain. The combined image gate first exercises
populated default-custody restarts, then restores PostgreSQL and recreates the API
with the bounded file archive. Canonical identifier traces prove invocation;
fresh original-image receipts must exist only in the restored database. Task,
question, return and citation IDs and exact retry receipts remain stable. Revoked
metadata stays redacted. Missing and changed archive objects must leave the full
database snapshot unchanged, with no new read receipt, despite valid local bytes.
Archive-enabled API/database restarts preserve the same history. Restored revoked
bindings deny access before archive invocation, and neither restored-copy work
nor its retries may mutate the original database.

The fixture module and two independently authored originals are read-only
acceptance mounts; only a synthetic identifier trace is writable. It is absent
from the default runtime image and has no environment-based activation. This
qualifies a controlled application seam only. #320 remains the separate concrete
transport owner; live-PACS isolation, external-archive recovery and the #248
adoption HOLD are unchanged. #307 and its report/reading/intake continuations,
professional review and clinical release remain separately governed.

Final combined hosted results belong to this continuation's draft PR and the
existing canonical engineering records. Parent passes, local syntax checks and
database skips are not evidence that the new combined workflow executed.

### Concurrent archive overlap

The later #332 at `ae550ed9272dcd0414b9c44042deb26ff659f669` independently
implements the same #312-to-#313 archive connection. A code-level comparison
identified three useful acceptance assertions to retain in this existing
continuation: a successful image-index read never invokes the archive; the whole
archive failure/recovery/restart cycle preserves all non-event snapshot owners
and the prior event prefix, appending only allowed read events; and a caller
without the `source_read` grant can still use an independently granted
`image_original_read` action. These refine the existing tests and helper without adding duplicate
test methods, another runtime or another owner. #332's other archive behavior
is already covered by the retained PostgreSQL and recovery tests. This candidate
also retains the #304 source-original correction absent from that overlap.
Neither existing PR is merged or closed by this reconciliation.

The separate #327 owns the planned image-inspection UI and authored-report join.
At the inspected `96ea369df0a560c8a325d33d66ef5b6b4a4865ef` checkpoint it
contains tests only and has expected missing-feature failures; it is not an
accepted combined runtime. Its future implementation must preserve the current
source/citation protections and both image and authored-evidence recovery probes.
Adoption of this archive continuation into that owner requires its own combined
acceptance; citing either candidate does not complete the join.

## Source preservation and verification

The #298 source archive's 356 files reproduced tree
`30e40fd60b4f42d65732bfcebe6233ad602ad955`; its current API, React and
inherited UI workflows passed before adoption. All 51 frontend files remain
identical to that owner. Six of its seven task/evidence modules remain unchanged;
`evidence_contracts.py` and its contract tests now match #311 exactly. Thirteen selected
image, parser, dependency/container and rights-gate files match #278 exactly.
The locked code-only pydicom 3.0.2 preparation remains inherited; no new dependency
is adopted. The two parents' individual results are not combined acceptance.

The new combined tests exercise real HTTP/PostgreSQL behavior and the restore
helper. The existing built React journey remains responsible for the question,
task and citation UI. This change adds no image viewer. Exact submitted-head
workflow results, artifact identity and review findings are recorded in the draft
PR and canonical Notion/Drive engineering records after execution. Local database
skips are never counted as acceptance.

## Executed verification and current receipt

[Draft PR #313](https://github.com/OpenxIntelligence/open-intelligence/pull/313)
preserves the actual remote #298 and #278 parents. GitHub comparisons confirm both
are ancestors of the initial combined runtime
`895561f6ca7e1271e8401604c77c95635c28274f`, tree
`1df1532f23891a8e9f2af42de579fd3375512552`.

| Initial combined-runtime gate | Observed result |
| --- | --- |
| [API/PostgreSQL 41659051682](https://github.com/OpenxIntelligence/open-intelligence/actions/runs/41659051682) | 464 API/contract/database tests passed, zero skips; 282 reference tests and both original browser journeys passed. |
| Five Compose gates in that API run | Patient, source, combined image/question/return/task/citation, review and follow-through recovery passed. The API served actual restored databases; new read receipts existed only there, original rows remained unchanged, and revoked rights/bindings remained enforced. |
| [React/browser 41659051340](https://github.com/OpenxIntelligence/open-intelligence/actions/runs/41659051340) | 219 client tests passed, zero failures/skips; production build and actual PostgreSQL/FastAPI/built-React/Chromium acceptance passed. |
| [Artifact 13241720289](https://github.com/OpenxIntelligence/open-intelligence/actions/runs/41659051340/artifacts/13241720289) | Downloaded digest, recorded commit, all 391 source blobs and exact lockfile matched. Populated citation desktop and task mobile captures were inspected. |

Artifact SHA-256:
`363e84b5a0b63c6aaa54426c23dffdc6563d594eaca4ec1a1264c4b60219f1bc`.
Retention ends 10 November 2026. Existing dependency gates passed; frontend license
inventory errors and reported audit vulnerabilities were both zero.

Fresh independent whole-change review found no material issue. The eight new
populated migration cases and three new connected HTTP/PostgreSQL cases each ran
successfully. Local discovery had explicitly skipped 333 database tests; those
skips were not used as acceptance. The standalone legacy UI workflow did not
trigger because its `web`, `src`, `tests` and workflow inputs are byte-identical
to #298. Its inherited reference regression and the two original browser journeys
ran in the exact-head API gate.

### Current-source correction from #311

The final source reconciliation found the directly applicable citation timestamp
correction in the existing owner. The two donor files are preserved exactly:
`evidence_contracts.py` blob `30f215155508914f7b1c0de83e7632c03baf4c98` and
`test_question_evidence_contracts.py` blob
`8a0506bb4da62ac1bab390a92cdfc7ec77d194fe`. Its actual remote history is retained
in the follow-up publication.

Before adopting the implementation, the donor tests reproduced **20 failures**
against the initial combined runtime: 19 invalid timestamp values plus refusal
at complete response preparation. After exact adoption, **22 focused contract
and API tests passed with zero skips**. Visible syntax, real calendar dates,
explicit timezone bounds, bounded precision and strict string type are enforced;
valid stored timestamp strings remain unchanged. OpenAPI now exposes the added
length bounds. This is an outgoing-contract regression and preparation-helper
check, not evidence of malformed dates entering normal PostgreSQL `timestamptz`
rows through a public request.

The initial 464-test result above predates this two-file adoption. The current
combined-head results, focused delta review, final artifact identity and canonical
Notion/Drive receipt are recorded in PR #313 after fresh execution. Parent results
alone do not establish the combined candidate.

## Remaining scope

All fixtures are independently authored fiction. Citation identity establishes
metadata integrity, not claim support, applicability or quotation/export rights.
Verification returns and task completion do not establish clinical approval or
external delivery. Receipts establish authorized preparation, not network
delivery or atomic distributed credential revocation.

The refreshed continuation owners are [#307](https://github.com/OpenxIntelligence/open-intelligence/pull/307)
at `c35219dc5eb244874a7df6e9bf00cfbfda18251f` (verified runtime
`477f24826a8a102c7437c993d69877c1f250b951`) for metadata, authored evidence,
reports and follow-through, and [#312](https://github.com/OpenxIntelligence/open-intelligence/pull/312)
at `9cd218210099c69d04b023ef77f9051a32206fc4` for #277's archive behavior joined
to #278. #307 preserves the contributions of #300/#302/#303/#304; #312 preserves
its image/archive predecessors. Those joins have their own verified receipts.
Their reconciliation with this candidate remains future work, as do the separate
first-party clinical EHR/LIS ports. Neither is included by implication here.
The complete patient-centered healthcare and biomedical platform remains the
destination. This candidate is draft, unmerged and undeployed.

## Preserved concurrent closeout of the initial runtime

The following receipt from remote commit `a68628ccf8689340c786e7d2702b2d97994f7f7e`
is retained verbatim. Its execution-session limits and continuation table describe
the initial `895561f6` runtime. The current-source section above now adopts #311;
#307 and #312 remain separate. This preserves the concurrent documentation work
without treating its historical next-step statement as the current adoption state.

## Hosted acceptance completed — 3 November 2026

The interrupted acceptance was reconciled against GitHub's completed jobs and
decoded logs. These results apply to runtime commit
`895561f6ca7e1271e8401604c77c95635c28274f` (tree
`1df1532f23891a8e9f2af42de579fd3375512552`). Both workflows checked out that
exact proposed source head.

| Gate | Observed result |
| --- | --- |
| [API/PostgreSQL job 125997113982](https://github.com/OpenxIntelligence/open-intelligence/actions/runs/41659051682/job/125997113982) | 464 API/contract/PostgreSQL tests passed in 476.692 seconds; zero skips. |
| Reference suite in the same job | 282 tests passed in 12.379 seconds; zero skips. Original loopback browser journeys passed. |
| Five Compose recovery probes in the same job | Patient, source, combined image/question/return/task/citation, review, and follow-through/evidence all passed. |
| [React/browser job 125997112174](https://github.com/OpenxIntelligence/open-intelligence/actions/runs/41659051340/job/125997112174) | 219 client tests passed; zero failures, cancellations or skips. TypeScript/Vite production build and actual React/FastAPI/PostgreSQL Chromium journey passed. |

The combined recovery gate completed at 10:10:31 America/New_York on
3 November 2026 (15:10:31 UTC in the log). The actual API reopened both generations
of canonical questions, immutable verification returns, tasks, citations and exact
DICOM originals from a restored database. Exact retries preserved their IDs;
revoked metadata title/URL fields remained redacted. New receipts existed only in
the restored copy, the original database remained unchanged, and the separately
restored revoked binding continued to deny access. The remaining review and
follow-through/evidence probes also completed successfully. These are software
execution counts and fictional recovery scenarios, not clinical validation.

The browser workflow exercises the inherited question, source quotation/brief,
return, task and citation workspace, including uncertain-response recovery,
amendment reassessment, independent permissions and case-switch isolation. Image
custody is verified by HTTP/PostgreSQL and recovery acceptance; there is no image
viewer in this increment.

GitHub's [browser artifact 13241720289](https://github.com/OpenxIntelligence/open-intelligence/actions/runs/41659051340/artifacts/13241720289)
reports SHA-256
`363e84b5a0b63c6aaa54426c23dffdc6563d594eaca4ec1a1264c4b60219f1bc`,
matching the upload log, and expires on 10 November 2026. The earlier execution
handoff reports comparison of all 391 archived source files and inspection of
desktop/narrow screenshots, plus independent review with no material defect.
Those prior checks are retained as handoff evidence: the resumed session checked
hosted logs and metadata, and did not repeat the archive comparison, visual
inspection or independent review. Its local execution environment was
unavailable. No test suite is claimed to have been rerun during this closeout.

This receipt is a documentation-only continuation of the tested runtime.
Previously recorded local PostgreSQL skips remain skips; hosted results above
supply the actual database acceptance.

### Subsequent integration ownership

Current open draft heads were rechecked during closeout:

| Owner | Current head | Separate responsibility |
| --- | --- | --- |
| [#312](https://github.com/OpenxIntelligence/open-intelligence/pull/312) | `9cd218210099c69d04b023ef77f9051a32206fc4` | Archive-backed image disclosure and restored-API acceptance |
| [#307](https://github.com/OpenxIntelligence/open-intelligence/pull/307) | `c35219dc5eb244874a7df6e9bf00cfbfda18251f` | Authored evidence/report/follow-through convergence; runtime receipt pins `477f24826a8a102c7437c993d69877c1f250b951` |
| [#311](https://github.com/OpenxIntelligence/open-intelligence/pull/311) | `8f7ad6a80dcb5312bc63480339d9142376883a4a` | Citation-history timestamp correction |

The existing engineering records recommend reconciling #312 into #313, then
converging with #307 while preserving #311's correction and the separately owned
source-reading work. This is the next integration boundary, not completed
capability in #313. It needs fresh combined migration, authority, retry and
restored-HTTP acceptance. Existing OI-006/007/008/009/010/013 remain partially
covered rather than closed. Draft, unmerged and undeployed; fictional inputs only.
