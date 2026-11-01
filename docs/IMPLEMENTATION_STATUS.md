# Implementation slice 01 — source and investigation ledger

**Stage:** local experimental synthetic-only code. **Not released for clinical use.**

**Backlog coverage:** Part of OI-003, OI-006, OI-007, OI-009 and OI-010. Does not complete the broader investigation/evidence stage (OI-008), identity/governance (OI-012–013), or clinical evaluation (OI-014 onward).

## Behaviors built

- Strict import of independently authored `OI-SYNTHETIC-REPORT/1` UTF-8 bytes; explicit report identifier, subject, event date, issued date, specimen, finding quotation, and status.
- SQLite persistence of original source bytes and SHA-256, per-document version history, source-line anchors, atomic amendment invalidation, and idempotent same-bytes import.
- Wrong-subject quarantine; no assertions created for the requested case or the declared other case.
- Persistent questions, source-version-bound human-authored investigation drafts, demo-only acknowledgment, stale-on-amendment, and Markdown export including full source versions.
- Local browser UI, served on `127.0.0.1` only, with no external assets or network-based research integrations.
- Plain Python `unittest` coverage for evidence and case boundaries, amendments, duplicate bytes, source recovery, and the local HTTP surface.

## Important unproven areas

- No authenticated identity, consent, delegation, role controls, auditing suitable for real patients, access revocation, or full security assessment.
- No PDF/OCR, automated clinical assertion extraction, FHIR/mCODE exchange, biological or imaging analysis, medical literature appraisal, trial searching, model inference, or provider integration.
- No independent professional review; demo acknowledgments are explicitly labeled and do not establish clinical correctness.
- The source format is deliberately artificial to make deterministic boundaries testable. It must not be described as a general clinical importer.
- The application has no user-selectable release license yet. Before licensing or distribution, select a license and audit dependencies/assets (none intentionally incorporated beyond the Python standard library in this slice).

## Next bounded work

1. Establish a reviewed real-world workflow contract (without real patient data) and a stronger adversarial synthetic challenge set.
2. Add source-to-assertion extraction as explicitly reviewable proposals from the specified document type, maintaining exact spans.
3. Implement an evidence item with true source content, permission metadata, applicability review, and immutable retrieval receipts. Keep publisher rights separate from discovery metadata.
4. Compare the local case-domain implementation with the candidate Medplum/FHIR boundary using the same amended-source and isolation tests.

No milestones should be marked complete solely because an interface displays the correct-looking data.

## Independent verification — 31 October 2026

This verification covers the local synthetic-only source-ledger slice, **not** clinical fitness, privacy compliance, external evidence, or a public deployment.

- Regression hardening: repeat wrong-case submissions are idempotent; Markdown source content remains contained in safe export fences; the HTTP server rejects non-loopback Host values to limit DNS-rebinding risk; the browser discards stale responses following case switches.
- Mobile layout: the navigation rail's intrinsic track size caused horizontal overflow at 390 px; constrained the outer grid and its rail/main children. This was a real defect caught by the new browser test.
- [GitHub Actions run #41221419037](https://github.com/OpenxIntelligence/open-intelligence/actions/runs/41221419037), commit `17f249ec085a08769a3386c454de18e3442b7883`: **pass**, Python compile, 18 unit/HTTP tests, and dependency-free headless Chromium journey.
- Browser journey verified: fictional Alpha source drilldown, switch to independent Beta and back, create a question, save source-linked draft, demo-only review acknowledgment, import amended pathology, stale previous snapshot and reopened question, preserve original source in export, and 390 px responsive containment.
- Tooling: Python 3.13 standard library, Chromium on GitHub's Ubuntu runner; no new runtime packages, medical data, services, scripts from vendors, or AI model weights incorporated.

**Remaining open evidence:** keyboard-only focus/operation and assistive technology testing, actual mobile-device testing, robust source-review and concurrency adversarial review, realistic ingestion, authentication and patient permissions, legal/build artifact clearance, clinical adjudication. Headless Chromium is not a substitute for clinical validation or a formal security audit. PR #1 should remain unmerged until the tracked review requirements have been resolved.

## Local UI redesign candidate — 31 October 2026

This is a local pull-request review candidate. The synthetic-only and non-clinical release status above is unchanged. Hallmark has no clinical-site template: its Console theme is for research and audit-trail interfaces; its Dose theme is a medication organizer, not a clinic. The app screen uses Console's light Paper colorway.

- Promoted the source-derived event timeline to the primary full-width view and grouped source review, investigation, evidence, bibliography, and import tools beneath it.
- Applied the user's 8 px spacing grid and 4 px type grid, visible surface boundaries, 44 px controls, explicit primary and secondary button states, selected section navigation, compact copy, and a collapsible narrow-screen menu.
- Kept all eight hash destinations, existing form IDs and handlers, source lineage, safety language, synthetic-only local case behavior, and the explicit opt-in for public DOI lookups. Named the two source/evidence checkbox groups with fieldset legends. Added exact-path local serving and HTTP coverage for the token/base stylesheets.
- Python suite: **38 tests pass**. Hallmark `sloplint`: **0 failures, 0 reflex issues, 0 warnings**; `--kept` confirms **8/8 links** retained (baseline 94 failures and 64 reflex issues).
- Reviewed the rendered page in the in-app browser at 390 px, the default 892 px, and 1440 px; at 390 px the document width remained 375 px with no horizontal overflow. Verified the mobile menu opens, closes after section selection, the current link is marked, and checkbox groups are exposed by name.
- Limits: the repository's headless browser journey could not run because Chrome/Chromium is unavailable here. Hallmark's render automation could not run because `puppeteer-core` is unavailable; the page was instead inspected directly in the in-app browser. No physical-device or screen-reader testing was done.

This interface work is supporting evidence for OI-010 only; it does not satisfy end-to-end workflow acceptance or complete any clinical, security, privacy, or release milestone. It has not been deployed and uses no real patient data.

## Patient-centered investigation workbench refinement — 31 October 2026

This second local iteration makes the question-driven case review the main workflow after the longitudinal timeline. It treats the larger patient intelligence environment as the direction while keeping the current app honest about its capabilities: the saved synthesis is human-authored and no model is called.

- Added a direct action from the case overview to the investigation workbench, a keyboard skip link, and clearer navigation names. The timeline remains the entry point for source history.
- Composed case questions and reviewable drafts side by side. The interface labels the synthesis as human-authored with no AI call. Draft content now stores separate headings for reported observations, a working hypothesis or mechanism, and assumptions, contradictions, and gaps, while preserving the existing server snapshot contract and source/evidence bindings.
- The hypothesis and uncertainty fields are optional; reported observations remain required. This allows an explicit lack of a supported hypothesis instead of forcing a speculative answer.
- Preserved all eight destinations and existing behavior. Updated the browser journey to cover the structured fields and their case-switch protection.
- Verification: all **38 Python tests pass**; JavaScript syntax and browser-journey Python syntax checks pass. Hallmark app-scope lint reports **0 FAIL, 0 REFLEX, 0 WARN**. The local preview accessibility tree confirms the skip link, all eight destinations, and named reasoning fields. Whitespace-only reported observations are rejected before submission.
- Limits: the browser journey itself could not run because Chrome/Chromium is unavailable. Hallmark's render tier is unavailable because `puppeteer-core` is absent. Responsive CSS stacks the workbench below 60rem, but this iteration has not had a new narrow-width visual review, physical-device test, or screen-reader test.

This remains a synthetic-only workflow refinement, not the AI research copilot or a clinically validated system. It does not call the model API or change provider configuration. No deployment or real-data use is part of this change.
