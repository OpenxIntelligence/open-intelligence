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
