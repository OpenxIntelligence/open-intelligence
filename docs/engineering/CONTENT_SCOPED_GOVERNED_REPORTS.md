# Content-scoped evidence in the existing governed report workflow

## Scope and ownership

Continue OI-008/009/010 and PR #186's shared rights gate on the connected
PR #196 candidate (`874df829eaa53d59bdee302879a825ee9364c3ad`, tree
`6829aa309d4c965dda30962293737bd39aee58c1`). Preserve the source owners from
#175/#179/#191/#196. This is not a new architecture, identity, evidence ledger,
review service or privileged HTTP endpoint.

The previous downloadable report build is a reference only. Its older store,
HTTP and UI modules are not copied over the newer authorized report owners.
Only the exact #186 `rights.py` gate and its five tests are reused. Existing
`AuthorizedClinicalKnowledge` -> `EvidenceReviewPacket` ->
`EvidenceReviewReport` -> `ReportReviewHandoff` remain the execution path.

## Behavior to establish

An optional source-provider `content_item` explicitly selects `full_text`,
`abstract`, or `api_output`. Omission means the existing full-text contract,
not inferred rights. Explicit null/unsupported types or classes fail closed.
The exact class must independently allow storage, display and model processing
before text enters this existing knowledge preflight; report export additionally
requires that class's redistribution permission and separate metadata rights.

The class and its declared/legacy basis travel with the authorized knowledge
projection and selected quotation into the report and its packet/body hashes.
Changing the class during assembly invalidates the report even when the text
and all permissions are identical. Existing patient/actor/purpose, exact source,
review-write, export and final freshness gates remain unchanged.

The provider's declaration is not classification, legal clearance or provenance
proof. No linked paper inherits rights from its curated API output. Fixtures are
independently fictional. A report receipt is preparation for review, not delivery,
clinical sign-off or a verified external license. Existing source-owner receipt
hashes persist, not a copy of restricted text or a second clinical record.

## Implementation plan

- [x] Add failing actual-domain tests for the class/operation matrix, legacy
  defaults, metadata, wrong-case/actor, class-change races, export denial and
  the existing persistent nonterminal report-review receipt.
- [x] Reuse #186's exact shared gate and tests; extend the three existing
  knowledge/quote/report modules without relaxing any permission or adding a
  schema migration, provider, dependency or route.
- [x] Run focused and complete local suites, negative paths, existing browser
  journeys when the environment permits, and inspect changed code.
- [ ] Add exact-head hosted CI preserving the existing workspace/browser tests;
  publish an isolated draft, verify source hashes and actual results; do not merge.

## Review focus

1. API-output grants must never authorize abstracts/full text, including when
   text is identical or the family happens to be a curated database.
2. Permission denial before a write must create no receipt. Post-write revocation
   must withhold the report but keep the existing nonterminal preparation history.
3. Legacy omission may retain full-text semantics; explicit invalid labels must
   not default to a more permissive class.
4. Reclassification must alter the hash-bound context, not silently reuse a
   prior report/reference. Hashes are not digital signatures or identity proof.
5. The underlying real patient/EHR/LIS/PWM composition must remain intact and
   no privileged report/export/review API may become unauthenticated.

## Verification

Observed local red/green: the 14 new integration tests failed on the unchanged
#196 baseline (8 failures and 13 subtest errors); after the extension, all 14
passed. The five unchanged #186 pure-gate tests also passed. All 59 application
Python test modules passed in four isolated subprocess workers: **624 tests**,
no failing module. Counts include inherited repeated fixture tests and are not
624 new or independent scenarios. An initial single-process discovery exceeded
the local 120-second execution limit; it is not counted as a completed pass.
The existing intake/source-reader/line-diff/text-change JavaScript run passed
**52 checks**. Python compilation, JS syntax and diff checks were run separately.

The original clinical-workspace browser journey was attempted locally but Chrome
exited before DevTools started: this container runs as root and Chrome refused
without disabling its sandbox. No sandbox/policy bypass was attempted and no
local browser pass is claimed. The existing hosted workflow is extended to
exercise this exact feature head, all tests and the three original browser
journeys on a separate runner. **Hosted results are pending at publication.**
Those browser journeys verify unchanged workspace behavior; the new privileged
content-specific report/export path is exercised by actual-domain tests, not a
new public browser export endpoint.

The base was reconstructed from authenticated CI artifact 13194485866 (SHA-256
`f9a38152dc6f9dd6829f35aeb68a924e0a1ce4a9a2f8b631190c131c2763d527`), and its entire
Git tree matched the #196 head before edits. The #186 shared `rights.py` and five
tests match the earlier source-owner bytes. Inline code review was performed;
independent review remains required before merging. No new vendor, runtime
package, weight, schema, real source license or clinical approval is introduced.

## Compatibility and next boundary

Legacy inputs without a class remain full-text inputs and are labeled as such;
explicit reclassification is never inferred from a database family or URL.
Adding class/basis to rendered packets changes hashes for newly rendered reports.
Previously recorded hashes and original report references are not rewritten or
claimed to reproduce with this new renderer. Persisted prepared-report receipts
remain nonterminal history. Sequential rights checks cannot recall an already
exported copy or provide a distributed atomic snapshot.

Follow source-owner review and final combined-head testing before merge. H1
PostgreSQL/FastAPI/React integration and a production-authenticated report route
remain separate work. This change intentionally does not transplant the older
local report UI/store or relax the current governed library's authority gates.
