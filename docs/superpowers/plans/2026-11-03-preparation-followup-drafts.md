# Preparation and follow-up draft composition

## Scope and design

Continue OI-007 and OI-010 by composing the saved-question task agenda from
draft #395 (`48d543609d96915c907bfab9d6a0eda2648977de`) with memory-only
follow-up draft preservation from #379 (`61339216147154c2c3555933e6e1c7281f3c0460`).
Both descend from #375. Preserve both upstream parents and canonical owners.

The existing RegistrySession retains literal creation fields and proposed
status-change fields. The preparation view continues to project only independently
authorized, saved tasks. Navigating to preparation or refreshing matching task
history must preserve unsent input without writing it or displaying it as recorded
work. Task access denial removes task content and drafts while separately authorized
questions remain readable. Changed source/task context, case/patient changes and
disconnect retain the donor's invalidation rules and exact uncertain-write recovery.

No new endpoint, dependency, database migration, persistence owner, permission,
clinical assertion, merge or deployment is included. Inputs are independently
authored synthetic examples. This is a bounded integration, not full platform
acceptance or clinical validation.

## Implementation and verification plan

1. Reconstruct the exact #395 tree from its verified hosted source artifact; check
   every tracked blob and mode. Inspect the common base and six-file donor delta.
2. Add the twelve donor regressions and two composed-session tests first. Confirm
   they fail against #395 because the draft-retention interface is absent.
3. Reuse the three exact donor runtime files. Merge the browser helper against
   their common ancestor, preserving both agenda and draft scenarios. Add real
   Overview navigation/refresh checks that unsent fields never become saved work.
4. Run the complete client/typecheck/build/installed-rights checks and synthetic
   boundary audit. Obtain independent review of the bounded diff.
5. Open a separate draft PR onto #395 with both source commits as parents. Inspect
   the hosted actual PostgreSQL/API/built-browser run on that exact head, verify
   artifact digest and source tree, and inspect desktop/mobile captures.

## Evidence status

The #395 artifact digest and all 433 source blobs/modes matched its remote tree.
The tests-first checkpoint compiled successfully: the 426 inherited tests passed
and the 14 added tests failed on the absent draft-edit methods. With the three
exact #379 runtime files, all 440 client tests passed with no skips. Local
`npm run rights` passed 13 filesystem controls and inspected 18 installed packages
(two optional packages remain uninstalled/uninspected). TypeScript/Vite build,
Python helper compilation, whitespace and synthetic boundary checks passed.

Independent review and combined hosted browser acceptance remain pending at this
source checkpoint. The final draft PR receipt must identify the actual head,
run attempt, artifact digest and remaining limits; an upstream passing run does
not prove this combined candidate.
