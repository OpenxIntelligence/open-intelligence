# H1 application convergence and acceptance

## Laboratory workflow candidate — 5 November 2026

Current accepted baseline was checked directly at main
`086f31e78240f8c70118c467406e89fdd89a92a2`, including #512's durable laboratory
questions and #520's source-reported cancer episodes. The complete first-party
ecosystem remains the destination; this increment connects the existing patient
intelligence experience without selecting a new architecture or dependency.

The isolated candidate preserves the ancestry and ownership of:

| Contribution | Frozen head | Combined responsibility |
| --- | --- | --- |
| [#518](https://github.com/OpenxIntelligence/open-intelligence/pull/518) | `d9d288079400b55eafb76526b14bc51098645635` | Exact laboratory question citations, rights checks, original-result inspection and 0019 migration |
| [#519](https://github.com/OpenxIntelligence/open-intelligence/pull/519) | `a643b16936afb7fa54ed7d755f8fd12e5ef56ef3` | Separate authorized laboratory counts in Overview and preparation |
| [#521](https://github.com/OpenxIntelligence/open-intelligence/pull/521) | `b7cd25bc769514f0e896f1aa578e6fe2b93e26d8` | Unfinished wording tied to its selected result and fresh preparation on return |

Three new decoder-to-Overview regressions first failed on the accepted baseline:
saved laboratory history was omitted, amendment scope was not represented in
Overview, and an independently unavailable laboratory read had no count state.
The composed client passes all 657 tests, including these regressions and the
existing episode tests. All 13 installed dependency checks pass, with 18 packages
inspected and two absent optional packages still explicitly uninspected. The
production build succeeds. No runtime dependency or new ledger is introduced.

The shared test-file conflict retained both citation-lifecycle and scoped-history
tests. The backlog conflict involved different adjacent rows; both owner changes
were retained. The merged real browser journey preserves draft switching,
explicit save, exact retry, original citations, amendments and rights withdrawal,
and adds Overview navigation during uncertain citation recovery and after source
change. Its `laboratory-workflow-convergence.json` receipt must be inspected in
hosted acceptance; authoring or compiling that scenario is not a browser pass.

The local API baseline ran 785 tests with 477 PostgreSQL-dependent skips and 75
socket `PermissionError` records. This is preserved negative evidence, not API
acceptance. The candidate requires fresh exact-revision API/PostgreSQL,
migration, browser, restart and backup/restore checks plus independent review.
The candidate's PR is the live verification record; donor results alone do not
qualify it. This section does not claim merge, deployment or clinical validation.

The full scope, source choices and verification tasks are in the
[bounded integration plan](../superpowers/plans/2026-11-05-laboratory-workflow-convergence.md).
Advanced EHR/LIS operations, production identity/consent, qualified external
biomedical retrieval, models and professional clinical review remain separate
qualification work. The laboratory inspection view is not a preserved signed
clinical report and does not establish therapeutic benefit.

## Accepted application checkpoint — 4 November 2026

Implementation scope and source resolutions are recorded here. The exact tested
revision, verification receipts and landing status are maintained in
[consolidation #481](https://github.com/OpenxIntelligence/open-intelligence/pull/481).
Software acceptance does not establish deployment or clinical acceptance.

The candidate targets accepted main `a5a5482f815ceb3c322cdfb32ab8b18c1c0e8709`.
The existing patient, source, question, evidence, report, review and task owners remain authoritative.

| Input | Frozen revision | Contribution |
|---|---|---|
| #471 | `95bf73d23172c15bcf326183494030e6597ed449` | #463 current-main reconciliation, document/image/manual-report backend, laboratory custody, optional manual-task origin, published migrations joined at 0017 |
| #445 | `346e32b9a3b3acbbf5d8ee730993fd6d87b920fa` | #408 preparation and follow-up drafts, passage draft continuity, request ingress limits |
| #470 | `647d414d0331024302886a2beaba25b727460c45` | #461 draft discovery and exact saved-question records/report navigation |
| #473 | `9ea4560fc03be567e8383f9b145fc8eaef0cd140` | #472 laboratory UI and #450/#443 keyboard navigation/reading |
| #475 | `254876cb933548d796cbb755eb6029674cb8efed` | Journey action for exact laboratory report versions |
| #468 | `d52847201fd4abfe1e468f5502284605a34d8ca4` | Reference UI accessibility and CI coverage reconciled with main |
| #465 | `b4da5f7aed4e75e2e6d95c084334b0435524c366` | Four-task timestamp rejection and recovery coverage |

## Work and acceptance

1. Preserve donor ancestry once and resolve overlapping session state explicitly.
2. Retain the published migration files and the 0017 join without rewriting history.
3. Add a local fictional demo setup and an exact records → question → evidence → report → follow-up walkthrough.
4. Split the existing frontend runtime bundle without increasing the advisory limit or changing dependencies.
5. Run client, installed rights, build, reference, API/PostgreSQL, populated migration, browser and all seven restart/backup/restore lanes on the final revision. Parent green is not final acceptance.
6. Review integration conflicts, demo restart behavior, source boundaries and rights; record the exact final head and CI receipts in the PR.

## Resolution ledger

- Session publication first enforces laboratory intent scope/retry invalidation, then derives quote-free manual-draft question IDs from the same resulting state. Both lifecycle owners survive.
- Navigation clears both pending source-entry focus and pending passage-resume focus. Existing focus guards remain.
- Manual browser helper retains the union of grants required by its explicit scenarios and both receipt sets; no negative assertion is deliberately removed.
- The retained historical project-state documents use the current-main reconciliation's versions; their old checkpoints are not rewritten into new acceptance claims. Imported increment-specific documents and Git histories remain available. This document is the current consolidation record.
- Root/API/web entry points and contributor guidance now point to one connected demo and acceptance record. Older checkpoint prose remains explicitly historical, including its original pending/failure evidence and schema references.
- #444's refresh-blocking alternative is not mixed with #445's retained-and-reverified draft implementation. Unrelated research, option-engine and second-opinion packet extensions are outside this landing candidate.
- #445's failed reference browser job was inspected: Chrome startup exceeded its 12-second readiness deadline. No passing result is inferred from that failure; the final reference workflow must execute again.

## Initial local evidence

The composed client passed 566 tests, zero failures/skips. All 13 installed dependency-rights controls passed: 18 packages inspected and two absent optional packages explicitly uninspected. TypeScript/Vite built successfully, initially reporting a 554.98 kB JavaScript chunk. These are pre-final checkpoints, not final acceptance.

## Limits

The laboratory import shared the older 72,000-byte text-source ingress envelope.
A regression first reproduced rejection of an otherwise bounded UTF-8 original
when JSON escaping expanded its transport. The route now shares the laboratory
preview's bounded 800,000-byte envelope and unchanged five-second read timeout;
the parser's 65,536-byte original limit remains unchanged. All ten ingress tests pass.

The pre-review local reference run uses the verified locked wheels: 770 tests passed.
An earlier run with the host's different pypdf installation failed 17 PDF checks;
that environment mismatch is not hidden or counted as a pass. The 26 reference
source-dialog/accessibility tests pass. After splitting runtime packaging, the
production JavaScript chunks are 332.41 kB (application) and 221.70 kB (React),
with the original 500 kB advisory limit unchanged. This is packaging evidence,
not a measured interaction-latency improvement.

Independent final source review passed 82 focused client tests, ten ingress
tests and five initial setup tests. It found one concrete startup race: ownership
state was initialized before the operator lock. The new two-caller regression
failed on that ordering. Initialization now runs under an exclusive sibling
lock acquired before any state-directory creation or ownership read. All six
setup tests pass. The final complete suite/CI must include this repair.
The reviewer found no further important scoped source issue. The demo-specific
browser checks report bytes through the API; report-download and Overview-return
controls also retain coverage in the broader combined browser journey.

The post-lock local reference suite passed 771 tests. The first combined hosted
browser run exposed a short-screen laboratory focus regression: at 320×256 the
focused reader lay below the viewport after the patient header resized. Its
focus alignment now waits for that layout and checks that focus still belongs
to the reader. The existing whole-reader visibility assertion is unchanged;
the repaired head must pass it and the complete browser journey before acceptance.
The next hosted run passed the unchanged short-screen assertion and the complete
combined browser journey. Its separate demo walkthrough then exposed a missing
explicit report-open action in the new test and guide. Both now recheck and open
the saved report before inspecting its body; no application permission gate changed.

Independently fictional fixtures only. No live models or external clinical connector, real identity/consent, professional approval, recipient authorization or acknowledged external handoff is introduced. Session drafts remain memory-only. Manual-only documents and laboratory results do not acquire a new question-creation path here. Package checks do not resolve the project's distribution license or qualify clinical use.
