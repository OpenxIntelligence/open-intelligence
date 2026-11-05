# H1 durable second-opinion packet draft

## Goal
Persist an exact preparation packet over the canonical H1 patient/case, original-source and saved-question owners without creating a second record system or implying a referral was transmitted.

## Boundaries
- Packet membership stores canonical source IDs/version/hash tuples and canonical question IDs, plus the exact source-snapshot contract and digest that defined their preparation context.
- Create requires a current source snapshot, current selected sources, and current source-grounded questions.
- Exact retries recover one receipt even after later source amendment; changed intent conflicts.
- Read-time freshness derives from the current source owner and question projection. Historical packet bytes are never retargeted.
- Recipient verification, external dispatch, appointment confirmation, clinical approval and record-completeness proof are unsupported and explicitly false.
- No model execution, new dependency, third-party service or restricted clinical content.

## Acceptance
1. One packet survives API restart with exact selected source and question identities.
2. Source amendment changes packet preparation state to source reassessment required without mutating its historical selection.
3. Wrong patient/case, missing independent source/question/packet grants and research purpose fail closed.
4. Serialization-time revocation rolls back a tentative create and withholds a prepared read.
5. Event-journal failure leaves no packet or membership rows.
6. Exact retry remains idempotent; changed intent with the same request key conflicts.
7. Database guards reject direct mutation and cross-scope inserts.
8. Existing full PostgreSQL/API/client/browser/recovery gates remain green on the combined head.
