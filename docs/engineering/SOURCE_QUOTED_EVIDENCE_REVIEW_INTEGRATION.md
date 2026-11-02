# Rights-gated, source-quoted evidence review packet (MRT-02 candidate)

**Status:** draft, synthetic-only functional integration candidate. Extends the existing clinical authority/Composer/knowledge adapters in PR #132 (stacked on #130/#95), using upstream rights-aware source owner #93. **Not** a new patient, evidence, clinical review, task or model store. **No production clinical claims.**

## Problem and implementation

The current authorized clinical knowledge adapter assembles patient assertions and external research information with current permissions, but it does not provide an explicit source-quoted handoff suitable for independent human verification. A proposed relationship marked `supports` or `contradicts` can be made without citing the particular original passage. Attaching a publication identifier alone is not proof that the passage exists or supports a clinical conclusion.

`EvidenceReviewPacket` adds a read-only, bounded **literal quotation validation** layer:
- Calls existing `AuthorizedClinicalKnowledge.snapshot` first (trusted patient↔case identity/actor/purpose, clinician source/EHR/LIS, versioned Composer and external rights preflight).
- Requires a selected `assertion_id`, `knowledge_id` and exact `quote`, corresponding to a current, proposed comparison. The literal quote must be a nonempty, bounded substring of rights-available source text. Forged, missing, duplicated and overlong text fails closed.
- Produces one structured row linking the original patient assertion's **exact source version, line, SHA-256, temporal data, reported state and original statement** to the rights-qualified **external source ID/version/date and selected literal passage**. Contains proposed direction/applicability, but explicitly `unreviewed_proposal` and no clinical sign-off.
- Rechecks the full owner-gated clinical/source/knowledge snapshot before release. Any change, including source amendment, publication-text update, revoked rights, binding or actor changes, fails closed.
- Never stores text, runs a language model, makes external requests, creates a medical decision, or executes clinical actions. It does not expose an unauthenticated API or UI.

The response contract is `oi.synthetic-source-quote-review/1`. Rights receipts supplied by the injected fictional provider are **not independently verified publisher licenses**. Literal quote match is **not semantic entailment, evidence-quality evaluation or applicability to an individual patient**. The packet is not permission to send patient or external text to an actual model. The separate clinical/LIS receiver is not a distributed atomic snapshot. The whole product remains a first-party, patient-centered EHR + Patient World Model + research platform, and Next.js remains excluded.

## Acceptance and verification

New `tests/test_evidence_quote_review_integration.py` works with the *existing actual first-party* PatientRegistry + EHR + LIS + clinical continuity + Composer + rights-aware knowledge fixture. Scenarios include exact source and quote receipt; no mutation of case journal; fabricated or duplicate quote denial; no-ML-use/revoked/metadata-only gate; patient report amendment; external evidence changing between two reads; wrong-case/actor/purpose; and no fabricated sources on missing input. These tests are **software and synthetic-data safety checks only**, not clinical evaluation.

### Dependencies and further work

- First review/merge upstream PRs #95, #130, #132, #93 and their identity/authority/source owners. Do not cherry-pick duplicate patient or rights stores.
- Human review handoff must use a real staff-role permission service and a durable review state from existing contracts, not a claimed clinician signature or this read-only packet.
- A future evidence assertion requires independent scientific appraisal of quotation context, study quality, population, benefit versus harm and relevance. A passage may be literally accurate and still irrelevant or misleading. No automated treatment decision.
- Before a deployed connector retrieves NCCN/ASCO/ESMO or other restricted text, establish and verify appropriate commercial storage, display, AI-use and redistribution rights. Current fixtures give no such clearance.
- Verify exact-head CI and UI before integration; no real patient data, external endpoints, new dependency, or unapproved model use.
