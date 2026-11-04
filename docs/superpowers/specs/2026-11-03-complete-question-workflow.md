# Connected patient question, source inspection and verification workflow

## Intent and authority

Implement the founder's 3 November 2026 patient-centered execution mandate by extending existing owners. The initial [project-state assessment](../../project-state/PROJECT_STATE.md) precedes product changes. The user authorized independent ordinary development and preservation of existing architecture; no additional architecture approval, new dependency, external notification, merge or deployment is inferred.

The useful outcome is one patient-scoped workflow: author a question about a current source; retain its original anchor; inspect that quotation; record a nonterminal verification return with a reason; recover an uncertain receipt; and prepare/download an independently authorized source brief. An amendment preserves history and makes the old source context require reassessment.

## Existing owners and alternatives

1. Start on #280 alone. It has question authoring and source inspection, but omits #265 intake authority and #262 canonical review history. This would discard important work.
2. Merge every image/PDF/domain branch. This includes unrelated migrations and clinical/evidence ownership seams that cannot be certified by this bounded workflow's acceptance.
3. **Selected engineering approach:** base on #276 `c154bfbc5f99f76801d37903959943659c0b6a71`; integrate #280 `e8d851e5c7769c31f429a3d1649c26402aa9de12`; selectively retain #278 `b72560ac0f5e5005040b0fc660ce1650343611cf`'s review JSON and exact-retry client repairs. This is an implementation choice within the accepted H1 design, not a new founder decision.

## Invariants

- One canonical patient, source, question, review and event history; no new database schema or identity format.
- Preserve `0008_review_convergence`, all existing migrations and all dependency locks/notices.
- Actual packet/queue/return JSON encoding occurs inside the existing source transaction, before final same-bearer authority recheck, audit insertion and commit. Failure withholds the body and any new successful receipt.
- Independent packet, queue, return and brief grants; same bearer cannot silently change actor, organization, purpose or exact-patient scope during preparation.
- Source anchors and question text remain literal and hash-bound. A verification return never promotes a question into clinical approval.
- Switching questions invalidates another question's pending/prepared packet or brief. Same-question views may coexist.
- Source amendment preserves exact return retry intent through same-case imports and temporary metadata failures, but denied/missing/revoked bindings, patient change and credential change clear it. Retry is explicit and uses the original request key.
- Use independently authored fictional fixtures only. No external biomedical evidence/model use, provider notification, real identity/consent, PHI or clinical action.

## Scope and practical limits

The existing React layout and source-only product vocabulary remain. Patient Overview #286 and reading presentation #274 are separate owners. Images, PDF/reviewed annotations, governed biomedical reports and their schemas are follow-on work, not silently imported. This slice does not certify every other route's final-JSON boundary or the platform's production readiness. No cache, broker, ORM replacement, component library or new framework is needed.

## Acceptance

Retain donor/client/API behavior and both existing browser journeys; add a real connected custom-question → packet → operational return/history → brief lifecycle, including amendment/retry and authorization failures. New authority tests must intercept both FastAPI's actual typed encoder and `JSONResponse.render`, so a missed encoder cannot produce a false pass. Verify transaction locks/commit failure with PostgreSQL in the existing hosted gate. Local DB skips remain explicit. Final evidence must name the exact source commit and tree, not just a parent PR.
