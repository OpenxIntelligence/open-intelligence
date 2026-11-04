# Open Intelligence — current record-reading audit

Date: 3 November 2026 (America/New_York).
Baseline: draft [#382](https://github.com/OpenxIntelligence/open-intelligence/pull/382),
`0e243e175dfdfe6e6d055531032c3dc284a1adc1`, tree
`d26ea69dd77d1e71c3f669a141cec72957ae5f29`.
This continues OI-010 within the existing H1 frontend and document owners.

## Reconciliation of the supplied UX-01 audit

The supplied 2 November audit examined #268 at `503e1b8`. It is historical
evidence, not a current implementation checklist. These observations come from
the pinned code, not a participant study or a comprehensive accessibility audit.

| Earlier recommendation | Current evidence | Decision |
| --- | --- | --- |
| Add persistent authorized patient context | `main.tsx` already renders `WorkspaceContext` from `state.patient` | Preserve; no additional identity state |
| Label Review unavailable | `ReviewPanel` now implements verification returns and history | Preserve working verification; clinical approval remains unavailable |
| Collapse technical source provenance | `source-reading.tsx` has native details for ID/hash/received/supersession | Preserve the disclosure; remove the duplicate opaque ID under every quotation |
| Keep source/question context coherent | The current App uses the same `RegistrySession`, question handoff and navigation invalidation | Preserve existing owners and handlers |
| Verify mobile and keyboard reading | #382's reading helper covers 320/390/768/1280 widths, original focus/return, enlarged text and disclosure keyboard access | Rerun the inherited browser journey on the new head; donor passes are not new acceptance |
| Distinguish available actions | Case rows repeat “Inspect source versions” without a case-specific accessible name | Add the existing exact case ID to the accessible name, retaining the visible label |

## Bounded design

People reading a report should see its quotation, reported state, exact line,
specimen/date context and unreviewed status together. Technical source identity
and hash remain available in that same source card's Verify disclosure. Removing
the duplicate identifier from the quotation footer changes presentation only.

A person navigating a list of actions should be able to distinguish two case
buttons. The accessible name will be `Inspect source versions for {case_id}`;
the visible label and the existing `session.loadSources(item.case_id)` callback
remain intact. Case IDs come from the existing authorized response.

Approaches considered: retain duplicate identifiers everywhere (more scanning
noise); hide the entire source context (would conceal dates/state); keep source
context visible and disclose only technical identifiers (selected). For case
controls, extending the accessible name is smaller than adding another menu or
changing routes. These are implementation choices within the requested bounded
continuation, not an architecture decision.

No new dependency, API call, permission, backend, migration or state store.
The case label must not outlive its existing case row. Provenance disclosure must
retain source ID/hash and historical version relationships. Clinical approval
must not be implied by a source read or verification return.

## Remaining work outside this slice

- Reconcile newer sibling integrations deliberately; #382 is a pinned baseline,
  not a claim that every latest draft is combined.
- Observe patient/clinician comprehension and task completion with participants.
- Conduct a broader visual-density and navigation study on the selected combined
  candidate before changing section names or introducing new navigation.
- Keep the separate manual-document-to-question/report contract with its owner.

## Verification record

Pre-change local checks: pinned `npm ci --omit=optional --ignore-scripts
--no-audit --no-fund` succeeded; dependency rights controls passed 13/13,
18 installed entries inspected and two omitted optional entries explicitly
uninspected; TypeScript/Vite production build passed.

Local browser execution is unavailable: Chromium exits because the runtime
denies its process-singleton socket. A Playwright browser download also failed
archive validation. Neither is counted as a browser pass. The existing hosted
PostgreSQL/FastAPI/built-React/Chromium workflow is the acceptance route.

Implementation and final acceptance are tracked in the accompanying plan and
the dependent draft PR. No clinical validation, deployment or merge is claimed.
