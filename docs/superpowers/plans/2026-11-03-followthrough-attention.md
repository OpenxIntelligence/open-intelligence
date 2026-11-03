# Follow-through Attention Implementation Plan

> Execute inline using the existing repository workflow and test-first verification.

**Goal:** Make recorded next steps easier to find while retaining source lineage,
scoped authority, task drafts and immutable operational history.
**Architecture:** Pure read projection and receipt-bound filters inside the existing
FollowthroughPanel. No second store or new model/runtime.
**Tech Stack:** Existing React/Vite/TypeScript; no dependency changes.
**Spec:** ../specs/2026-11-03-followthrough-attention-design.md

## Global constraints
Independently authored synthetic fixtures only. No Next.js. No clinical priority,
automatic task execution, external notification, authorization changes or main merge.

## Review focus
Cross-patient/case stale state must withhold counts and task content. Hidden cards
must not lose unsaved status-change inputs. New receipts reset filters without a
stale render. Historical states never become open-work alerts. Browser dates must
not reinterpret the backend's evaluated-on flags.

## Tasks
- [x] Inspect exact parent, instructions, backlog, task owner and active PRs.
- [x] Acquire parent source from hosted artifact; verify digest and complete Git tree.
- [x] Run unchanged client baseline (195 passing; local TypeScript 5.8.3).
- [x] Write failing attention/filter unit tests in apps/web/tests/followthrough-attention.test.mjs.
- [x] Add scoped projection/filter helpers to apps/web/src/followthrough-view.ts; run all client tests.
- [x] Extend apps/web/src/followthrough-panel.tsx with accessible filters and mounted hidden cards.
- [x] Write browser assertions before UI implementation; complete actual hosted execution.
- [x] Verify local client/compile/diff; publish isolated draft child and run exact-head hosted checks.
- [x] Inspect actual artifacts/screenshots and record evidence/limits; no independent-review claim without a reviewer.

## Evidence and rulings
Parent: PR #293 at 635f357048eb27e52e6ec5c3d7b6714215070127, tree
74c4a2ab65bf54a0908246199bb67c300ae2662b. Local complete source tree matches.
Source artifact 13228693741 digest:
7cd60c8a39520b883553cea7f84b67c4f861f149118e785fd9db9b471aafb869.
Parent API/web/UI workflows were observed successful; these are parent evidence,
not evidence for this change. Local runtime cannot clone over the network; the
connector's authenticated artifact supplied the exact source. No inherited files
were rewritten to work around the network boundary.

Observed local RED: 21 new attention tests failed; 195 inherited tests passed.
GREEN after the helpers: 216 tests passed, zero failures/skips. Browser additions
were written before UI wiring but not executed locally (no PostgreSQL/browser stack).
No browser RED is claimed. The final hosted run must verify the real integration.

Parent reconciliation before publication: #293 advanced to e44f225e3ce4953d754ad0e6e1409e22b696a29f
(tree 7c8d022a6158c3edcb0210dba85a18367e4145bb). The five changed upstream
documentation files were verified against its downloaded exact-head source and retained
unchanged; runtime/tests/dependencies are identical to the tested parent. Artifact
13229797793 SHA-256 c905f0526df720ffd7da6b8a54b6da1ede7fdb38807131dfd251423e7c922745
and complete parent tree were independently recomputed locally. This child is based
on that final parent, not an overwrite of the active branch.

Local final checks before publication: 216/216 client tests, zero failures/skips;
Python browser-helper compilation and git diff --check passed. Full pinned React/TSX
build and actual database/browser acceptance require the new head's hosted run.
Self-review covered scope guards, immutable flags, hidden-card draft retention,
new-receipt filter reset and unavailable-versus-empty semantics. No independent
reviewer or clinical validation is claimed.

## Hosted failure and bounded harness repair
At implementation head 67a1f3732be3d810682855e38e6a04223f2cd54d, run 41636773262
passed 216 client tests, production build and the existing dependency gates. The real
browser progressed through inherited workflow checks and new filter counts, visible
rows, retained drafts, zero filter HTTP calls and refresh reset, then failed Enter
activation. The failure screenshot showed the correct focused native button.
A local real-Chromium isolated native-button reproduction produced zero clicks for
keyDown/keyUp (no keypress), and one click for rawKeyDown/char(\r)/keyUp. This matches
the existing tests/ui_glance_journey.py input sequence. Repair changes the test's
input sequence only, retains all assertions, and adds no application workaround.
The new exact-head complete hosted journey is still required.
Failure artifact 13231725547 SHA-256:
5766192b32fd2cbb539237b1f6fa66071a0499dffd8f9d4a359f797020b97234.

## Verified runtime receipt — 3 November 2026

[Draft PR #299](https://github.com/OpenxIntelligence/open-intelligence/pull/299)
is a six-file child of #293; it remains unmerged and undeployed.

**Runtime head:** `6a2def885002f521107a672d6c000ea234450a51`
**Tree:** `84884e77491c863371416e069277022bd318b51b`
**Successful hosted run:** [41637669069](https://github.com/OpenxIntelligence/open-intelligence/actions/runs/41637669069), job `125922858637`.

Observed complete successful job and inspected retained evidence:
- `client-tests.txt`: 216 passed, zero failures, cancellations or skipped tests.
  The 21 new tests were observed failing before implementation; inherited baseline is 195.
- `build.txt`: pinned TypeScript check and Vite 7.3.7 production React build succeeded.
- `browser.txt`: actual PostgreSQL 16/FastAPI/built-React Chromium journey passed,
  including overlapping filter counts, exact visible historical/source-amended rows,
  zero extra filter HTTP requests, retained owner/reason drafts, fresh-receipt reset,
  native Enter activation, independent task-read denial clearing and case switching.
  Existing intake, question, literal quotation, brief/download, review-return,
  lost-response recovery and source-amendment assertions also passed.
- Desktop 1440px and mobile 390px attention/task captures inspected; labels and controls
  wrap without horizontal overflow. This is not comprehensive accessibility certification.
- Existing dependency/notice gates passed; the retained npm audit reported zero known
  vulnerabilities for this run. No dependency or backend change was introduced.

Artifact `13230734072`, expiry 10 November 2026, was downloaded and its SHA-256
recomputed: `4219267c339244bb25cd877d3ac7f984a27198f40cb38493e4624654414a8d35`.
Its `commit.txt` identifies the exact runtime head. All 337 archived source files were
compared byte-for-byte with the inspected local tree. The local Git tree equals the
published tree above; do not infer Git file modes from zero ZIP external attributes.

The first failed hosted run and its harness-only repair remain recorded above.
This receipt is a documentation-only follow-up to the verified runtime. A later
head's checks must be attributed to that head; parent or runtime evidence must not
be relabeled as an independent full API/unit rerun.

**Remaining gates:** independent code/security/product review and integration with
the parent stack. No clinical validation, real-patient identity/consent, continuously
pushed revocation, notification delivery, appointment booking or autonomous clinical
execution is established. Date/source flags describe the last authorized read, not
clinical urgency or all of a patient's care needs.
