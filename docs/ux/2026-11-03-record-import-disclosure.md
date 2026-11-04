# Records reading before import setup

Bounded OI-009/010 frontend continuation, 3 November 2026. Parent #318 at
`40c4eb99f77d15fd645c97ba7522223d9bcf18df` already connects source reading to
questions, evidence, reports and verification. This slice keeps those owners.

## Problem and decision

A fully expanded file-import form precedes existing sources, pushing quotations
and their question actions farther down a narrow screen. Wrap the unchanged
SourceIntake in a native disclosure: initially closed when records exist and
open for an empty case. Keep the mounted form, selected File, exact preview and
confirmation when the user explicitly collapses it. Do not automatically close
an open form after a source-count change. The same patient/case key and original
session invalidation still govern its lifetime. Import receipts remain outside
the disclosure and retain their original visibility.

Alternatives considered: moving the form below all records makes importing hard
to discover in long lists; unmounting on collapse loses a local selection;
opening a modal adds focus trapping and another interaction pattern. A native
details/summary control provides the bounded progressive disclosure needed here.
This is a design hypothesis, not a measured reduction in patient effort.

## Acceptance and scope

Test empty-case default, existing-case default, native Enter open/close, visible
summary focus, exact File/preview/confirmation retention, and zero implicit
imports. Continue real upload/duplicate/amendment/quarantine and permission
checks. Capture narrow and desktop reading and expanded import. All existing
source/question/evidence/report/return/follow-through checks remain required.

Only frontend presentation, browser tests and this note change. SourceIntake,
RegistrySession, API/contracts, backend, schemas, rules, dependencies and CI stay
unchanged. No real patient data, clinical approval, merge or deployment.

## Inherited test race

Parent run 41662718464 reached its final reading-session reauthorization test,
then failed waiting for the restored response. That helper treated disappearance
of source-index as completed denial, although loadSources clears it immediately
when loading begins. It could restore the fixture grant and click disabled
reload controls before the denied response completed. Retain the disappearance
check and additionally await the existing terminal “Sources unavailable” message
before restoring the test grant. No application behavior or permission is
changed, and the denial assertion is strengthened. The child must pass its own
combined run; parent success is not assumed.

Final execution evidence and any failures are recorded in the draft PR and the
existing Google/Notion product records; this preparation note is not a pass claim.
