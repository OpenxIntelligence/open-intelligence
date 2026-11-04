# H1 manual-passages and document/image convergence — 2026-11-04

Status: **unverified integration candidate**. This is a source-composition record, not clinical validation, release authorization, or a claim that a hosted test passed on the resulting tree.

## Frozen source inputs

- First parent / existing document-image owner: #381 at `924008266d741b2494df41112e2da446b526f920`, including #394's restored-selection JSON type/digest verifier.
- Second parent / existing manual question-context owner: #398 at `a85d30f5563d763507c64d91ec3c70100b446fc3`, including #396 and #392's functional ancestry.
- The manual donor is compared with its #392 parent `3eeeaac29ba60f490a6f0e1af1cb28a2baee29c7`. The goal is to apply only the donor's additional bounded behavior while retaining the newer image/archive/source authorization runtime and tests.
- Current `main` reconciliation remains separately proposed in #401 and is **not** implied by this composition.

## Existing owners and retained invariants

- Keep one canonical patient/case, source/original, annotation, source question, evidence/report, return and follow-through owner; no second database of clinical facts.
- A human-selected passage remains a manually attributed, unreviewed selection and does not become a source-authored World Model assertion or image-owned source.
- Preserve exact original bytes and source revision, annotation revision/selection key, quote/page/line, anchor digest, access receipts and historic report bodies.
- Keep independent source-original, question, evidence metadata, report export and image permissions. Check authority before and after audit persistence; reject revoked bindings and wrong-patient/case/source access.
- Preserve #381's image/archive/report original custody, the DDL-free join of published 0012 histories, exact current-v2 documents, full restore/revocation checks, and #394's strict JSON-typed restored-selection verifier.
- Preserve donor #398's bounded (20-reference) question attachment, immutable passage revision, exact retry/uncertain-response recovery, stale selection reassessment and frozen manual-context report renderer.
- All input fixtures are independently fictional. No real PHI, clinical approval, model execution, live PACS or licensed clinical-content claim.

## Migration reconciliation

```
0012_reviewed_documents -----+
                             +-- 0013_document_image_convergence
0012_image_report_convergence+      |
                                   v
                         0014_question_passages
                                   |
                                   v
                         0015_manual_report_context (new H1 head)
```

The #381 `0013_document_image_convergence` migration remains unchanged. Donor `0013_question_passages` and `0014_manual_report_context` were imported as `0014_question_passages` and `0015_manual_report_context`; their down-revisions follow the linear joined history. API readiness, disposable database and recovery head assertions were adjusted to the new head. Fixture-oriented legacy metadata handling includes the prior 0013 join. Never rewrite a published migration or silently skip it.

## Source reuse and conflict disposition

- Reuse donor blobs for 19 newly added or unchanged-target files including the canonical question-passage code, React passage panel, evidence/report extensions, negative tests and recovery driver.
- Apply donor's additive changes to the existing patient routes, reviewed-document selection resolver, RegistrySession client and authored-evidence state without replacing target image and authorization code.
- Preserve current #381 tests that already reference the schema constant instead of reinstating donor's older hard-coded head literals.
- Extend the existing OpenAPI assertion with the manual-passages route; preserve current image routes.
- Preserve the target browser's `add_synthetic` argument while adding optional manual passage context and the exact record fixture.
- Preserve #381's migration cleanup for image custody, adding only the question-passage table and trigger cleanup.
- The reference implementation and current-main changes are not newly integrated here. The prior `docs/EXECUTION_BACKLOG.csv` remains as-is pending exact-head verification and reviewed state updates.

## Required exact-head acceptance before any adoption

1. Confirm unique Alembic head `0015_manual_report_context`, both historical 0012 owners, 0013 join and complete populated migration history; fail on unexpected schema or duplicate heads.
2. Full FastAPI/PostgreSQL tests, including manual-context reference revision/actor/quote/source/hash, wrong-patient/case/source, denial/audit rollback, and immutable historical report semantics; zero failure/skip in the intended database suite.
3. Full inherited reference suite and both original browser journeys; no clinical/real-data path.
4. All six HTTP/restart/backup/restore probes: patient, document/source, image/archive, review, follow-through and authored evidence. Verify current/historical manual passage and original bytes/selection types/digests after restore and revoked-binding denial.
5. Full React tests, rights controls, TypeScript/Vite production build and actual PostgreSQL/FastAPI/built-React/Chromium journey with manual text and PDF selection, uncertain retry, source correction/amendment and historical report download.
6. Retain evidence for previously observed failures; inspect exact commit identity, tests, skip counts, rights notices and artifacts. Fix the actual combined tree and rerun instead of borrowing green parent results.
7. Review preserved source/image fail-closed checks and case authority after audit writes; assess any new or inherited security issues independently.

## Intentional limits

This candidate does **not** create a question from a manual-only document; it adds manual passages to an **existing canonical question** anchored to a structured source. It does not establish human clinical sign-off or external care handoffs. The production readiness, real identity/delegation/consent, content-rights and clinical qualification gates remain open.

Until the exact combined head passes, report status as **integration under test**. Merge remains subject to explicit founder/maintainer review and approval.
