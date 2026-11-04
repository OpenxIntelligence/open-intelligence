# Extraction baseline implementation plan

**Goal:** Make the extraction comparison proposed in #452 executable before adopting another parser.

**Architecture:** An offline engineering tool invokes the existing `preview_document` owner on independently authored built-in fixtures. It checks literal text, original-byte identity, PDF page/line anchors and explicit rejection. It never writes patient/domain state. A separate allowlisted operational projection contains no document text, source hashes, filenames or exception messages.

**Tech stack:** Python standard library and the existing pinned pypdf 6.21.4 worker; no new dependencies.

**Scope/acceptance:** OI-006/011/013. This is a synthetic extraction baseline, not clinical interpretation, an independent blinded evaluation, an OpenTelemetry integration or a Docling benchmark. No external inputs/downloads are accepted by the CLI. Failed extraction, unsupported input and environment failures must be distinguishable. Timing is diagnostic per attempt, not a performance claim. Unknown/malformed output must fail verification, not become a pass. Full source and dependency qualification remains required for future candidates.

**Approach:** Start with the current parser and reusable PDF fixture authoring helper. Installing Docling now would mix unqualified model/dependency selection with baseline measurement; adding production instrumentation would broaden the change to runtime privacy and operational controls. Both remain subsequent, separate steps.

**Base:** #461, 701afe959ecf8b3a5e58d1059b231d595fbba764 (local equivalent 50fe6e9). Main lacks this PDF owner; this child is deliberately stacked on the verified document workspace and does not interfere with #463 convergence.

## Task 1 — Executable baseline and honest receipts

- [ ] Add `tests/test_extraction_baseline.py`: demonstrate missing runner; then actual text/PDF corpus and rejection checks, changed unit/page/hash, malformed output, wrong worker version, exception-message leakage, nonfinite timing and no-overwrite CLI output.
- [ ] Add `tools/extraction_baseline.py`: built-in fixtures; `run_suite()` returns per-case results, raw denominators and metadata-only metrics; `main()` returns nonzero for any failed check and writes only with exclusive creation.
- [ ] Run focused tests, existing PDF tests and repository data-boundary check. Run the existing complete hosted synthetic suite on the exact published head; do not describe local wrong-version failures as parser defects or skips as execution.
- [ ] Record results and remaining limits in `docs/engineering/EXTRACTION_BASELINE.md`; update existing OI-011 backlog acceptance evidence without marking the milestone complete.
- [ ] Independent code review, draft PR, and concise updates to the existing Notion/Drive owners.

## Review focus

Missing pinned worker must fail even for deliberately invalid PDF cases. Accepted text must preserve negation, units and dates literally. Blank PDF pages must retain physical numbering. Error details must never enter the metadata-only projection. A second CLI invocation must not replace an earlier receipt.
