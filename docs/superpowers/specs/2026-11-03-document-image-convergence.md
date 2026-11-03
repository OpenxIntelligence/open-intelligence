# H1 reviewed documents and image/archive continuity

## Intent and authority

Continue the authorized Open Intelligence H1 engineering work by joining the existing reviewed-document candidate and the verified image/archive/report candidate. Preserve the canonical Python/FastAPI/PostgreSQL 16 owners and React/Vite/TypeScript workspace. This is reversible draft integration under the existing continuation mandate; it does not merge or deploy any owner branch.

## Fixed inputs

- Document/evidence/review/main composition #377: b13dd4810342d6a7ef08bbad53745502e0950801.
- Socket/report qualification #370: cc624fe3b258e39a3b833a0053ed9e9f2ced57be.
- Image audit-tail authority #376: 319e68b1445cb4547db56bb82d173ce47f88274b.
- Test-fixture lifespan correction #373: e22dd159f3543452798dd124433c066e729eab42.

These branches retain their respective ownership. Their historical test results are not acceptance of this new composition.

## Approach and decisions

Use #377 as the first parent and preserve #376/#373 as additional source parents. Merge both histories deliberately. Add the DDL-free revision `0013_document_image_convergence`, descending from `0012_reviewed_documents` and `0012_image_report_convergence`. Never edit a published migration.

Preserve document filtering, image original validation, the final image authority check after audit persistence, independent grants, exact bytes, immutable correction/report history, cancellation, strict timestamp validation, recoverable drafts and all existing recovery drivers. Resolve shared request limits to retain both the document limit and exact image-upload limit.

Keep all package evidence and full notices from both owners: the existing pinned pypdf wheel and deterministic code-only pydicom derivative. No new package, sample data, external service, model or permission is selected.

Retain Review draft checks before journeys that add further fictional cases. Run the reviewed-document and image/evidence journeys in the same built application. Manual document selections remain attributed user selections; this integration must not fabricate structured question/report provenance.

## Acceptance

1. One authenticated API exposes both original owners and all existing question/report routes.
2. A single new migration head preserves every existing revision. Populated upgrades from either 0012 head preserve old rows, original bytes, annotation revisions, citations, tasks, reports and sequence states.
3. Joining both already-populated heads changes version bookkeeping only, in both upgrade and downgrade. Current HTTP rejects unconverged states.
4. After upgrade, actual HTTP reads exact document and image bytes, recovers identical retries and preserves manual attribution. Reviewed documents never leak through structured-original routes or appear as source-authored assertions.
5. All inherited API/PostgreSQL tests run without skips; all six restart/dump/restore helpers, final inventory, reference tests, React tests/build and actual browser journeys pass on the exact combined source.
6. Independent review and canonical engineering records distinguish executed evidence from pending and external gates.

## Limits

Independently authored synthetic cases only. Next.js, real patient data, live PACS, new production services, clinical inference, clinical sign-off and distribution-license changes remain outside this engineering integration. Same-process/same-UID socket fixtures do not qualify external archive isolation or external archive recovery. Production identity/consent, manual-passage provenance integration, qualified biomedical/model access and independent clinical evaluation keep their separate owners and acceptance requirements.
