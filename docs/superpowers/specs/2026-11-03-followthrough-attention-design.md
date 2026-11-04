# Follow-through attention in the existing patient workflow

Status: bounded implementation proposal under OI-007/009/010/013; not a new architecture.

## Intent and scope
Help a person find recorded work affected by changed sources, passed revisit dates,
or missing ownership, without burying completed/deferred history. Extend the existing
H1 follow-through panel from PR #293, not the concurrent Overview owners #288/#294.
The accepted patient-centered direction and the user's instruction to start guide this
slice. Selecting this panel rather than another Overview integration is an engineering
choice to avoid duplicating active work.

## Approaches
- Add a second task dashboard/ledger: rejected; duplicates authority and active UI work.
- Add model-driven prioritization: deferred; not needed and would imply unvalidated urgency.
- Add deterministic filters over the existing authorized projection: selected; no new
  API, storage, dependency, permission or clinical rule.

## Behavior and boundaries
All work remains the default. Filters show All work, Source changed, Revisit date
passed, Unassigned, and Completed / deferred. Categories overlap; counts are not
additive or clinical priorities. Use server-evaluated flags; do not recompute dates
from the browser clock. Completed/deferred tasks stay historical even when sources
change. No tasks or counts are shown without a ready, same-patient/same-case read
and active patient/case binding. An empty authorized list is different from no read.
A new access receipt resets the filter synchronously to All work. Filtering makes
no HTTP request and does not change task identity, order, history, state, permission
or source anchors. Hidden cards remain mounted, preserving an unsaved status-change
reason/owner. After failed authorization the existing session clears content; this
projection independently withholds mismatched/stale state. Counts describe the last
successful read, not continuous permission or current clinical need.

## Acceptance
Tests cover scope/phase loss, row isolation, authoritative date flags, overlapping
counts, historical exclusion, immutable tasks and receipt-bound filter resets.
The existing real PostgreSQL/FastAPI/built React browser scenario must verify visible
rows, preserved drafts, zero extra reads/writes during filtering, explicit reset on
refresh, exact original source/history after amendment, denial clearing, keyboard
selection and 390px containment. Synthetic inputs only; no notifications or clinical
approval. Publish only a draft child, leaving main and source owners untouched.
