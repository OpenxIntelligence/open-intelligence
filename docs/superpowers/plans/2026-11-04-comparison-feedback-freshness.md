# Comparison feedback within report freshness and preparation

Continue OI-008/009/010 by integrating #388
(`f1e7482df7d1bdfed7fb5a191470f74dd82d817f`) into #404
(`7c08e7a53559423a93ef1430357d4034b39c29e3`), preserving both parents and
existing domain owners. No new dependencies, backend, schema, grants or workflow.

Rejected oversized comparison edits must not silently submit earlier accepted
text. Controller-owned rejection markers block saving until a valid correction
or explicit acknowledgement. Field-linked feedback explains exact passage,
rationale and relation/applicability constraints. A matching refresh retains
the warning. A freshly historical report retains the marker with its hidden
draft; acknowledgement is unavailable until current matching context returns.
Denial/discard/session reset clears dependent draft and markers. Independent
follow-up drafts and saved preparation work retain their existing boundaries.

Plan: reproduce the missing rejection marker with two composed session tests;
apply the inspected donor delta without overwriting report freshness; run its six
rendered/controller tests and the full suite; preserve both browser scenarios
and capture actual rejected-edit feedback at desktop/mobile widths; obtain an
independent review; verify exact-head hosted PostgreSQL/API/Chromium acceptance
and retained artifact before reporting completion.

The two new composed tests failed before implementation because the controller
had no rejection marker. At the local implementation checkpoint all 457 client
tests, 13 rights controls, installed package gate, TypeScript/Vite build, Python
helper compilation, whitespace and synthetic-data audit passed. Independent review
and exact-head hosted acceptance remain pending. Upstream #388's successful run
is not proof of this combination.
Synthetic-only draft engineering; no merge, deployment or clinical approval.

Independent review identified a multi-field controller edge case: a bulk edit
with both oversized passage and rationale marked only the first rejected field.
A regression reproduced this before repair. The controller now collects every
rejected text field while leaving accepted draft input unchanged. Correcting one
field cannot authorize the other; both field orders are covered. The final local
suite has 458 passing tests and the production build passes. This supplements the
initial 457-test checkpoint; final hosted acceptance and repair review remain
separately attributable in the PR receipt.
