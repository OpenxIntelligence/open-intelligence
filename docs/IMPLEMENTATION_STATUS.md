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
