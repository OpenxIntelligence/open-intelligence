# Review chronology in the connected document workspace

Continue OI-007/009/010/013 on the existing patient/source/question/Review owners.
Independently authored fictional inputs only; no merge or deployment.

## Source pins and bounded change

- Current document/main reconciliation #377:
  `b13dd4810342d6a7ef08bbad53745502e0950801`, tree
  `ced2dd53450a576295b610c91b8240206e4c25a3`.
- Existing Review chronology owner #375:
  `1bdc44ac8507ec3a05398c3965bed5fcae0d59eb`.
- Base web artifact `13267037305`, run `41709821292`, SHA-256
  `622b5394eb535b7072f4c7cbdb2adf649256665e536eb7dabe0d8548d6c90e39`.
  Downloaded digest and recorded head match; all 461 source files reconstruct
  the exact base tree, including executable classifications.

The base already contains #375's follow-through decoder, regressions and browser
helper, byte-for-byte. Its shared-path CI gate is also present; a trailing blank
line is the only workflow difference and the current workflow is preserved.
Only the Review decoder, Review client regressions and Review browser helper
are selected from #375. Each retains exact donor bytes. Keep the document/main
reconciliation, complete document-denial/late-inbox probe, owner ancestry,
browser-helper order and existing migration graph intact.

## Acceptance

1. Reject impossible or out-of-contract question and return-history timestamps
   before disclosing the Review inbox. Preserve valid strings and microseconds.
2. An invalid refresh clears previously disclosed inbox/history and unsent
   reasons, blocks new returns, and leaves uncertain submissions recoverable
   with their exact captured reason, request key and body.
3. Receipt recovery cannot restore invalid current disclosure. Only a fresh
   valid authorized read restores the unchanged questions and immutable history;
   it neither recreates cleared unsent text nor silently submits a return.
4. Run the existing real-response chronology faults with separate original,
   one-field-fault and restored records, then the current text/PDF intake,
   correction, download, document-denial and delayed-inbox scenarios in the same
   actual PostgreSQL/FastAPI/React/Chromium journey.
5. Preserve backend/API, grants, RegistrySession, dependency locks, shared
   reference inputs, workflows and earlier migration bytes. No new data owner,
   clinical authority, package or external-service activation.

## Execution record

- [x] Inspect live owners and reproduce the current base from its source archive.
- [x] Pristine base client suite: 415 passed, zero failures/skips.
- [x] Adopt the existing regressions first: four intended failures and 416
  passing controls, zero skips. Reproduced invalid question/history acceptance,
  retained disclosure after invalid refresh, and uncertain-return recovery
  against the unchanged base runtime before adopting the fix.
- [ ] Reuse the existing strict validator and browser helper; verify donor bytes.
- [ ] Run all client tests, production build, rights controls, syntax, boundary
  and protected-path checks; obtain separate read-only review.
- [ ] Publish a draft child of #377 and require its own exact-head hosted web
  acceptance, retained source/chronology/document/report receipts and inspection.

Final publication and hosted receipts belong in the draft PR without rewriting
tested source only to mark these publication-time checkboxes. Parent/donor
successes do not establish acceptance of this combination. A new full standalone
API suite or backup/restore run is not claimed for this frontend-only delta;
#377 remains the owner of its separate whole-stack acceptance. The new browser
faults alter a copy of actual successful responses and do not imply the genuine
server emitted malformed dates. This does not implement manual document passage
provenance in canonical questions/reports, clinical validation or real identity.
