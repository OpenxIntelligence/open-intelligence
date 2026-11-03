# Healthcare Navigation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [x]`) syntax for tracking.

**Goal:** Replace the long mixed-audience document with the proposed patient and clinician navigation while preserving every existing connected feature.

**Architecture:** A client-side fragment shell groups permanent existing DOM nodes and keeps `app.js` as the sole case-state owner. It uses current served assets and existing event handlers; navigation does not reload canonical data. Patient/clinician selection is a development presentation preview, not authorization.

**Tech Stack:** Existing dependency-free HTML, CSS, classic JavaScript, Python/SQLite behavior oracle, Node checks, and the current browser/CDP harness. No new runtime dependency.

**Spec:** `docs/superpowers/specs/2026-11-02-healthcare-navigation-design.md`

## Global Constraints

- Baseline: PR #166 commit `334d863b2206b290c02cd2606dcb93c93afe3a68`, tree `d7059e5c178e761e0987a67ff8c220f47e6da2f8`; do not mix PR #167.
- No backend, API, authentication, schema, or business-logic changes.
- Use the same permanent DOM nodes and existing handlers; no second case, source, question, evidence, or review store.
- Do not call `refresh()` for page-only navigation.
- Preserve all 16 forms, seven exact host-composition anchors, old section hashes, and generated snapshot links.
- Public bibliography/literature metadata remains ephemeral and not case-linked.
- The patient/clinician switch is a development preview of presentation only; it grants no authority or access.
- Do not fabricate appointments, messaging, medication management, profiles, professional authentication, clinical recommendations, or other absent capabilities.
- No actual patient data, patient-derived fixtures, or external commitments are introduced.
- Implementation is already authorized. The root implements the shell, then an independent reviewer checks the complete change; this plan adds no approval gate.

## Review Focus

- Direct/deep fragments and back/forward navigation must reveal a page before focus/scroll, including a snapshot rendered after startup (Task 1).
- Unsaved text, selected source/evidence IDs, and local file preview must survive page/preview changes without a data refresh or write (Task 1).
- Empty startup and first creation must remain visible under the existing composed-host empty-state CSS (Task 2).
- Narrow layouts and keyboard users must reach each destination, with inactive forms outside the tab order and dialogs still usable (Task 2).
- A vetoed case switch or delayed source/context response must retain the original case guard, cancellation behavior, and Composer gate (Task 3).

---

## File responsibilities

| File | Change |
|---|---|
| `web/app.js` | Add isolated navigation/presentation orchestration using existing owner symbols and nodes; keep domain handlers intact. |
| `web/index.html` | Add accessible shell controls/landmarks while preserving all original IDs and the seven literal composition anchors. |
| `web/style.css` | Desktop/narrow page layouts, global/local navigation, current/focus states, readable content spacing. |
| `web/intake.css` | Reconcile empty/loading workspace selectors with page wrappers. |
| `web/workspace-entry.html` / `web/workspace-entry.js` | Change only if a frontend integration adjustment is necessary; preserve creation/upload handlers and observer targets. |
| `tests/test_navigation_shell.js` | Focused navigation contract checks if a lightweight DOM harness is needed; no new runtime dependency. |
| Existing browser journey harness, plus a bounded navigation journey if needed | Exercise actual composed UI, input preservation, anchors, keyboard and viewport behavior. |
| This plan and its spec | Record actual verification status and remaining browser limitations. |

## Task 1: Permanent navigation shell and legacy anchors

**Files:** Modify `web/app.js`, `web/index.html`; add focused `tests/test_navigation_shell.js` only for the material navigation contract.

**Interfaces:** Consume existing `caseId`, `active`, `readyCase()`, `case-picker`, original IDs, and hash links. Produce a private shell initializer and a single `navigateToAnchor(fragment, {focus})` operation (or coherent equivalent) that selects presentation/page, reveals the owning existing node, and manages navigation focus without data mutation. No public API or second case state.

- [x] Read the spec's complete section map and 16-form table; inventory original node identity before moving anything.
- [x] Add focused checks for `legacy_anchor_reveals_owner`, `late_snapshot_anchor_resolves`, and `navigation_preserves_form_and_file_state`; assert no `refresh()`/fetch/write is caused by page-only navigation.
- [x] Run the new checks against the baseline and confirm they fail because the page shell does not exist, not because the harness is broken.
- [x] Implement fragment resolution, active-page state, global/local navigation, and the development preview switch in existing `app.js`; move existing nodes, never clone or replace them.
- [x] Preserve original script scope/order, observer targets, all handlers, seven composition anchors, and body-level dialogs. Keep global notices visible.
- [x] Run focused checks and verify original IDs are unique, all 16 forms still exist, same-case inputs survive navigation, and direct/legacy/dynamic anchors select the proper page.

## Task 2: Agreed IA, readable layouts, and empty startup

**Files:** Modify `web/index.html`, `web/style.css`, `web/intake.css`, and only necessary frontend intake integration. Use the existing browser harness.

**Interfaces:** Consume Task 1's anchor navigation and permanent section registry. Produce the spec's exact patient/clinician labels and local Patient chart navigation, using the same selected case and recorded data.

- [x] Compose patient **Home / My health records / Questions & reports / Documents / Updates / Workspace setup** and clinician **Workspace / Patients / Patient chart / Research library / Workspace setup**.
- [x] Compose Patient chart **Overview / Timeline / Documents / Investigations / Evidence / Discussion options / Updates**; retain every inventory surface and action.
- [x] Add Patients search that filters existing case labels/references locally and uses the original picker change path for selection.
- [x] Make global/local navigation, selected-case context, page headings, focus indicators, skip link, and disclosure labels readable at desktop and narrow widths; inactive pages must not remain keyboard reachable.
- [x] Reconcile empty/loading selectors with wrappers; add/extend checks `empty_workspace_setup_visible`, `first_creation_reaches_documents`, `mobile_navigation_keyboard_reachable`, and `dialog_works_across_pages`.
- [x] Verify the composed page still loads without changing `workspace_host.py`, any backend route, any payload, or authentication behavior.

## Task 3: Behavior verification, captures, and independent review

**Files:** Existing tests/browser harness; bounded navigation journey and evidence documentation as needed. Do not change domain behavior to make presentation checks pass.

**Interfaces:** Consume the completed shell and composed host. Produce an accurate verification receipt, available desktop/mobile captures, and an independent review of the complete frontend diff.

- [x] Run `PYTHONPATH=src python -m unittest discover -s tests` and record the actual result. The pre-implementation receipt is 345 passing tests; explain any count difference.
- [x] Run every `tests/test_*.js` script with Node, including focused navigation checks. Recount the suite's named checks from actual output; do not publish the provisional 71 count or confuse file counts with named checks.
- [x] Use `tests/workspace_start_browser_journey.py` and the current harness to exercise empty creation, exact source import, question, replay run, review-draft handoff, demo acknowledgment, amendment, and stale export.
- [x] Run the relevant existing source-dialog, World Model, Composer/review-handoff, and literature checks; specifically verify a vetoed case switch and delayed response cannot expose another case or reactivate stale context.
- [x] Exercise page-only and preview navigation with unsaved values and a selected file; test direct old hashes, late snapshot links, back/forward, patient filtering, and all local chart destinations.
- [x] Capture desktop and narrow views with the local Chromium/CDP path if available; inspect clipping, scrolling, focus, headings, controls, and source dialogs. If unavailable, state the exact blocker and separate source/automated evidence from visual evidence.
- [x] Request independent final review of the whole diff against the spec: all features retained, no duplicate DOM IDs or stores, no route-triggered refresh, no fake capabilities, and no backend/API/auth/schema/business-logic changes.
- [x] Resolve concrete review findings, rerun only affected checks, and report what changed, what was verified, and what remains unproven. Do not claim clinical validation or deployment.

## Completion receipt

Implementation and independent review completed on 2026-11-03. The [verification receipt](../../ux/healthcare-navigation-verification.md) contains the final feature mapping, actual named test counts, all four reproduced review fixes, scope confirmation, and genuine desktop/mobile captures. The new route checks were observed failing against the original shell; the retained-state and keyboard defects were reproduced before correction.
