# Open Intelligence — Authorized Clinical Composer to Rights-Aware Knowledge

**Status: draft synthetic-only first-party integration candidate, not a production clinical or regulatory release.** Additive to the canonical Open Intelligence architecture and [P0 issue #92](https://github.com/OpenxIntelligence/open-intelligence/issues/92). No additional patient master, source ledger, literature crawler or clinical decision-maker.

## Original ownership

- Base: [draft #130](https://github.com/OpenxIntelligence/open-intelligence/pull/130), itself stacked on #95: authorized clinical Composer over canonical patient registry, EHR encounter, original note-source provenance, LIS source/result and pending-only review receiver. The existing upstream clinical owner and source implementation remain unchanged.
- Imported *byte-identical* modules from [draft #93](https://github.com/OpenxIntelligence/open-intelligence/pull/93): knowledge_context.py and test_knowledge_context.py. Metadata/full-text/ML-use rights separation, source version assertion lineage and explicitly unreviewed comparisons remain owned by #93.
- New clinical_knowledge_context.py performs read-only composition. Its injected knowledge source provider is a synthetic stand-in for a future verified rights service. A claimed permission receipt is not legal or publisher clearance.

## Actual workflow

1. Existing AuthorizedClinicalComposer.snapshot enforces canonical patient/case binding, actor, purpose, EHR/LIS evidence provenance and source fingerprint.
2. An injected provider offers independently authored fictional knowledge sources and comparison proposals. With no provider, no external content is retrieved or fabricated.
3. The *original* compile_context withholds content without declared use-specific metadata and full-text/ML rights. All source comparisons remain unreviewed proposals.
4. Every original clinical assertion and source line is checked against the existing Composer anchors; an incomplete/truncated preview is rejected rather than silently accepted.
5. Clinical authorization and source fingerprint are rechecked after assembly; provider source/rights state is fetched again. Mutations, revocations and mismatched source versions fail closed.
6. The final result explicitly states that the review is pending, model execution is not authorized, clinical conclusions are not established, rights receipts are unverified fixtures, and there is no distributed atomic snapshot.

## Current functional acceptance and limitations

Tested workflows use actual first-party synthetic PatientRegistry, EHR, clinical source links, LIS and QC release, patient source ledger, Composer, rights gate and human-review candidate receiver. Negative cases include wrong patient/case/actor/purpose, source amendments, stale evidence comparisons, rights revocation while assembling, changed patient binding, empty provider, and multilingual content. They do not use real patient data, live licensed literature, real clinician signatures, external network, models or medical actions.

Remaining required: verified patient and clinician identity, consent, publisher rights for clinical guideline and AI use, authenticated domain APIs, PHI safety/tenant isolation, durable human reviewer receipts, actual knowledge retrieval and sourced investigation run, eventual cross-system consistency policy, clinical validation and regulatory assessment. A synthetic 'rights_state=approved' field is not a legally verified permission.

Dedicated CI workflow in .github/workflows/patient-composer-knowledge.yml includes new integration tests, original #93 rights tests, original #130 clinical/Composer tests, clinical continuity and full Python/HTTP repository regression. Record **exact-head hosted CI** outcome before claiming success.

**Next slice:** after review and reconciliation of #93/#95/#130, attach the original investigation engine and review inbox to this context for a versioned source-linked research packet, test post-amendment invalidation and professional re-review; do not silently merge upstream owners.
