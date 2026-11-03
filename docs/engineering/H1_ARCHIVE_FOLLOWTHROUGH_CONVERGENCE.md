# H1 archive reads within image, question, task and citation continuity

## Scope and ownership — 3 November 2026

This candidate continues the adopted H1 FastAPI/PostgreSQL and React/Vite stack.
It selectively integrates archive owner [#312](https://github.com/OpenxIntelligence/open-intelligence/pull/312)
at `9cd218210099c69d04b023ef77f9051a32206fc4` into combined image/question owner
[#313](https://github.com/OpenxIntelligence/open-intelligence/pull/313) at
`f6132e894a21a326f72660c3399499ccbf251831`, including its citation timestamp correction.

The existing canonical registry, qualified binding, source versions, image
objects/links, questions, verification returns, follow-through tasks/events,
evidence catalog/rights/citations and identity journal keep their ownership.
All 14 published migrations and the `0011_image_evidence_merge` head remain
unchanged. No dependency, permission, public API field or frontend is added.

## Implemented behavior

The application may receive an archive reader through trusted composition.
Clients cannot select one; default reads continue using local custody. Original
reads first validate canonical patient, case, source and image state and current
authority. The archive receives only server-stored Study/Series/SOP identifiers.
I/O occurs after preflight locks are released. A fresh transaction verifies the
same binding/source and exact original bytes, prepares the complete response,
rechecks authority and commits its access receipt before returning it.

A configured archive failure withholds the response. Missing, altered,
wrong-subject or non-byte content never falls back to a valid local original.
Source amendment and explicit relinking retain original image identity and
historical questions, returns, tasks and citations. Image grants and citation
metadata rights remain independent; rights withdrawal redacts fresh metadata
without rewriting earlier citation identity.

## Reuse and new integration evidence

The three donor HTTP suites and bounded archive fixture are copied exactly from
#312. The runtime constructor and original-read methods are reused exactly;
trusted composition is added while preserving #313's richer route registrations.
The older recovery script is not substituted for #313's current script.

New coverage adds three actual PostgreSQL/HTTP cases for the combined
archive/task/citation history and two bounded response-ordering checks. The
recovery gate retains its local-custody checkpoints, then explicitly enables the
archive in the restored API. It checks exact invocation and bytes, restored-only
receipts, missing/altered-object failures, denied reads without archive calls,
historical/current questions and returns, task events, citation redaction, exact
retries, API/database restarts and a second restore containing revoked access.

## Verification ledger

Before the runtime port, the five existing ordering tests passed and the two new
archive checks failed: local retrieval ignored the configured archive and did not
withhold a changed archive original. After the port, all seven passed. An earlier
test-authoring attempt used an incorrect exception import; that import error was
corrected before recording the actual two behavioral failures.

Local verification on the implementation tree:

| Check | Observed result |
|---|---|
| API discovery | 485 collected; 135 passed, 350 PostgreSQL-gated tests skipped |
| Original synthetic reference suite | 282 passed |
| React/client tests | 219 passed, no skips |
| TypeScript and Vite production build | Passed |
| Known patient-case acquisition entrypoint scan | Passed within the scanner's bounded coverage |
| Recovery helper syntax and whitespace checks | Passed; not Docker acceptance |

PostgreSQL and Docker are unavailable in the local runtime. Hosted verification
must run the exact proposed commit with zero skipped API tests, actual browser
acceptance and all five existing recovery probes. Local skips are not acceptance.
The draft PR and canonical Roadmap hold the resulting commit/run receipts; no
hosted result is claimed in this pre-publication ledger.

## Boundaries and next owners

All test content is independently authored fiction. The mounted file archive is
an explicit test fixture, not a network PACS or an external-archive backup system.
Live DICOMweb transport, production identity/consent, backend bypass protection,
external-archive durability, broader DICOM profiles and clinical validation remain
separate gates. PACSNode remains on its existing HOLD decision.

[#320](https://github.com/OpenxIntelligence/open-intelligence/pull/320) owns a
separate private-socket transport. [#307](https://github.com/OpenxIntelligence/open-intelligence/pull/307)
and its report/reading continuations, including #316/#322/#326, remain the next
schema and product-workflow convergence owners. Metadata citations do not establish
scientific claim support; operational task/return history does not grant clinical
approval. This slice advances OI-007/008/009/010/013 without closing those broader
work packages. It remains a draft, unmerged and undeployed candidate.
