# Permission-scoped evidence review report

**Goal:** Produce an actual human-readable source-linked report from the existing authorized patient/EHR/LIS/Composer/knowledge quotation packet.
**Architecture:** Extend existing knowledge/source projections with explicit report-export capability, evidence-content hash and receipt time. Reuse EvidenceReviewPacket and its owner-gated snapshots; add one deterministic text/plain rendering service with a separate deny-by-default export policy. No patient, evidence, permission or review database.
**Spec:** Founder Master Directive §§6–8, 14, 28, 32; existing docs/engineering/SOURCE_QUOTED_EVIDENCE_REVIEW_INTEGRATION.md and issues #92/#87.
**Baseline:** PR143 head 83a52eee04136bdc8a0a973e760593079768a3d9, exact tree 24d79cbac5eafe4d212a6f353985c8bda27d46fd. Import the three exact final-read repair files from upstream PR132 head 864e1f703c6ada019ddd23dd15e4fb2933515285 before feature work; neither remote source branch is changed.

## Design decision
A read-only report is the next reversible connection. A new persistent clinical approval system would duplicate unresolved review ownership; copying a preview directly would confuse read/AI rights with export rights. Use existing full_text/metadata `redistribute` permissions independently of read and ML use, plus a separate patient/actor/action/purpose export authorizer. These injected test policies are not verified identity, consent or publisher permission.

## Scope and acceptance
- [x] Verify isolated byte-exact source and upstream repair; 23 focused baseline executions passed (includes imported tests).
- [x] Add failing tests for report output, provenance, support/counterevidence, no-write/determinism, default deny, explicit source redistribution, changed permissions/source, wrong patient/purpose, malformed quotations, empty and unselected evidence, and text injection.
- [x] Implement only the projection fields and renderer required by those tests.
- [x] Retain pending human review, proposed applicability, explicit limited coverage, and non-atomic consistency limits; never infer study quality, clinical truth or actual review.
- [ ] Run focused and full synthetic suites; inspect actual output; preserve exact source/log hashes.
- [ ] Publish a draft stacked candidate only; no merge/deployment, new dependency, Next.js, medical data, live model, external evidence retrieval or distribution to third parties.

## Report contract
UTF-8 text/plain body; packet and body SHA-256; patient/case/question references; question text; reported source line/version/hash and event/issue/receipt axes; literal evidence passage and full permitted text hash; separate proposed support, contradiction, context and unknown groups; count of omitted candidate comparisons; withheld-evidence counts without withheld source identity or content. Copied text is JSON-quoted to prevent line/heading injection; bidirectional control characters are escaped. The report method returns bytes/text to its authorized caller and writes no file or audit event. It cannot revoke copies already exported; integration must add governed storage/audit and trusted actors before release.

## Observed local results
13 initial report tests failed because the renderer did not exist. Initial implementation passed 12; one assertion incorrectly selected the first returned source rather than the assertion's source_version_id. That fixture assertion was corrected without weakening source linkage. Final 15 report-specific tests pass; 44 related executions passed before the last two checks were added. A whole-suite discovery and a separate parallel-module attempt each exceeded the local execution window and are not claimed as completed. Hosted results must be read at the exact published head. Existing SQLite ResourceWarnings remain.

## Integration status
A library service only: no unauthenticated export route or new UI. It returns a report but neither stores it nor claims an audit receipt. A future authorized API must add recipient-specific disclosure scope, retention, audit, trusted principals and governed artifact custody; a clinical reviewer must independently assess study quality and applicability. Current default-deny callbacks and rights declarations are synthetic policy contracts, not production approval. Source #93 and packet #143 owners must review the additive projection fields, including evidence-text hash/export flag and source receipt time. Upstream #132's final-read repair is copied byte-for-byte, not independently rewritten. Keep this work draft/unmerged.
