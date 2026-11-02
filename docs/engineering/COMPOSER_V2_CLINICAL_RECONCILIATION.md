# Open Intelligence — Composer v2 / Canonical Clinical Source Reconciliation

**Draft implementation, 2 November 2026. Synthetic-only, not merged, not clinically validated.**

## Purpose

Converge the first-party rights-qualified Composer investigations [PR #140](https://github.com/OpenxIntelligence/open-intelligence/pull/140) and the canonical patient → EHR/LIS → rights-aware evidence → durable numeric review chain [PR #144](https://github.com/OpenxIntelligence/open-intelligence/pull/144), without deleting source-owner identity/adapter bindings or replacing the patient/world-model architecture. The full platform vision and no-Next.js decision remain unchanged.

## Exact code ownership / composition

- **Base is #144**, with unchanged underlying first-party patient registry, clinical encounters, LIS, source-note, outbox, Composer numeric journal, rights-aware patient knowledge, and review adapters.
- **From #140 without modification:** `src/open_intelligence/composer.py` at Git blob `0cb972819abc836c5affe651e8696daf8c21a6ba` and `src/open_intelligence/investigation.py` at `f6e986d51ff13ee684cc1ad80fe95112e30ac35c`.
- **The shared `store.py` required reconciliation, not whole-file replacement.** Preserve #144's issuer-qualified `adapter_identity_bindings`, receipt revocations, first-party source import transaction and clinical invariants. Adapt #140's upstream `_broker_context_inputs`, text-free rights receipts, input-context version/prompt digest tables, permission/review invalidation, and source-owned `save_investigation`/read-withholding behavior. Retain historical source-line/hash and case/question isolation.
- **Original dependent-only model staleness** brought from [#91/#126](https://github.com/OpenxIntelligence/open-intelligence/pull/126): a new accepted current clinical source or amendment invalidates current model hypotheses for that case, while an evidence assessment/withdrawal targets only affected case/questions; record history retained. Duplicates and wrong-case quarantine do not promote results.
- **Question lifecycle** from [#136](https://github.com/OpenxIntelligence/open-intelligence/pull/136): saving an unreviewed/abstained hypothesis must not mark the question addressed. An explicit (fictional) human review remains a separate state transition.
- **Numeric Composer adapter** `composer_lab.py` now binds the original source + broker receipts using v2 fingerprint semantics, preserving all source-owner arithmetic and source-anchored numerical behavior.
- **New authorized read-only investigation review** `PatientResearchReview.investigation_snapshot`: preflight canonical patient, current EHR/LIS/source/proposed knowledge; retrieve source-owned stored investigation; require versioned context fingerprint; recheck patient/source/right context and result before releasing. Any stale/revoked/right-changed historical model text is redacted from the integrated review response, including potentially sensitive abstention/drop fields. This is not a model execution service.

## Invariants / acceptance

1. Current clinical identity/adapter mappings, original source history, EHR notes and LIS release/QC provenance remain intact; no duplicate patient or evidence store.
2. Every Composer preview and original durable numerical computation receives the **same v2 fingerprint** over current case/question/source/assessments and broker-rights receipts. Numeric output is source-linked and interpreted as mathematics only.
3. Only independently authored fictional broker text with recorded `full_text` store/display/model permissions may enter bounded hypothetical model inputs. This enforces declarations but does **not** legally verify rights.
4. Persist text-free source/rights input receipts with versioned context hash. Broker revocation, correction, review, accepted source amendment and changed assessment must invalidate the proper dependent investigation; prior assertions and numeric artifacts remain inspectable when authorized. Protected model output becomes withheld.
5. Cross-patient, wrong purpose, revoked patient-case binding, forged source/reference/arithmetical receipts and mid-read mutation fail closed.
6. Unreviewed or abstained model output never closes the patient's question. Hypothesis claims must remain unreviewed and may not direct actual treatment.
7. **No real PHI, actual informed consent, provider credentials, real publications, medical AI invocation, production endpoint, commercial/publisher rights approval or independent human signature.** Separate lab receiver and source store are not an atomic distributed snapshot; recheck logic narrows but does not eliminate cross-store races.
8. These exact-commit tested modules are a **reconciliation candidate**. Original branches #140, #144, #136, #95 and others remain authoritative for their respective functionality until reviewed and integrated. CI does not mean clinical validation or safe patient deployment.

## Remaining integration work

The installed workflow tests original PR #140 broker-v2 input and withholding regressions, #144 clinical/numeric/rights tests, new cross-domain paired investigation/numeric tests, then full Python/HTTP regressions. Hosted run/commit must be recorded before changing status to verified.

**Not included:** #140's UI and HTTP changes (these overlap #144's existing source-owner paths) or #141 provider-neutral model execution. The next step after exact-head software acceptance is a separate constrained HTTP/API+UI integration incorporating the original authorized owner API, with a real authenticated actor/consent policy and independent clinical and security review before any clinical use. Do not silently merge incompatible parent versions or duplicate authoritative clinical stores.
