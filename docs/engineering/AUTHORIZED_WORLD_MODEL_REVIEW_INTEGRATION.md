# Authorized Patient World Model + Unified Clinical Research Review

**Status:** Draft integration on top of #149. Independently authored fictional data only. Not merged, no PHI, no clinical use.

## Purpose

Connect the source-derived PWM from [PR #147](https://github.com/OpenxIntelligence/open-intelligence/pull/147) to the *existing* patient/EHR/LIS/Composer/rights/quoted-evidence/durable-numeric review composition in [PR #149](https://github.com/OpenxIntelligence/open-intelligence/pull/149). There is **no second patient model, source ledger, knowledge database or task runtime**. The original `world_model.py` source is an exact unchanged copy of the #147 blob. #147 owns future PWM interpretation and source/identity semantics.

## New boundary

`AuthorizedWorldModelReview.preview(patient_id, case_id, question_id, run_id, actor, purpose, selected_quotes)`:

1. Starts with the same authorized `AuthorizedClinicalKnowledge.snapshot` used for rights and clinical provenance. An unknown/wrong patient or actor must fail before any patient data is returned.
2. Calls the existing, independently verified `UnifiedClinicalReview.preview` which owns exact quote and durable numeric receipt checking.
3. Reads only the current original `CaseStore.state(case_id)` and invokes the original read-only `synthetic_world_model(state, expected_case_id)`.
4. Independently compares **all current observations** with the authoritative knowledge source packet on exact source version/line, finding key, reported state, original quote, SHA, event date and issued date. A missing or forged source entry fails; the model does not infer absent specimen data or claim clinical interpretation.
5. Rechecks source identifiers, patient/case actor authority, knowledge-source licensing *declarations* and complete clinical snapshot after assembly. Any data-source or permission drift aborts the whole preview.
6. Returns one synthetic read-only payload with separately identified `patient_world_model` and `unified_review`, pending human review, false clinical approval and no new model execution.

**Security limitations:** sequential read preflights are **not** a distributed atomic transaction; the rights provider is an injected fictional test stub rather than verified publisher permissions; the policy callback does not prove clinician identity or consent. This adapter is internal only. It must not be exposed through the unauthenticated loopback demo as if it were a real patient API.

## Tests

`PYTHONPATH=src python -m unittest discover -s tests -p 'test_authorized_world_model_review.py' -v`

The test suite imports original real domain fixtures already in #149, then tests (a) successful current source/evidence/numeric join with no ledger writes, (b) historical source amendments and stale arithmetic, (c) wrong patient/purpose/actor denial, (d) revoked scientific use rights, (e) fabricated original source SHA, and (f) source revision after evidence/numeric assembly. Tests are actual SQLite/source operations and no external medical input is accessed.

Full project unit/HTTP and browser CI must pass at exact head. Do not merge until #149, #147 and their upstream first-party data owners agree on one contract and review the combined diff. No Next.js, new dependency, public endpoint, clinical claim, research license or consent authorization is introduced.
