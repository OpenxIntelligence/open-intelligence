# Composer + permitted evidence: bounded implementation plan

**Status:** implementation in progress. This extends the existing plan and OI-008/009/010 evidence, investigation and review contracts; it is not a replacement architecture or a claim of MVP completion.

**Product purpose:** connect the patient's existing source-bound investigation to the persistent knowledge-rights broker, so one question can compare patient facts with permitted external evidence and retain an auditable, reviewable result. Keep the full first-party cancer-care platform visible while delivering one useful connected increment.

## Audited starting point

- Upstream: PR126, `integration/composer-evidence-run-freshness-20261102`, exact head `3e20873cf129f0e7827aaa6619f74e847d62292a`.
- All 180 tracked upstream blobs were reconstructed and Git-hash verified locally. Local snapshot commit `6dff2ef` is a workspace receipt, not an upstream release.
- Baseline: 301 Python tests passed, including real loopback HTTP tests. The restricted shell initially denied socket creation; the same suite passed after allowing local sockets. No external model or patient-data request ran.
- PR93's separate in-memory knowledge-context compiler is research precedent, not another registry to import. Reuse the persisted `rights_sources`, `rights_permissions` and `broker_links` already in this application.
- Reuse PR123's five exact CI safety files before publication. Existing research workflow commands in the old base are unsuitable for synthetic-only development. Their static scanner is a limited regression guard, not a network firewall.
- This application lacks production identity, organization authorization, secure document operations and clinical validation. The integration does not establish those capabilities or legal rights.

## Acceptance criteria

1. The existing Composer preview displays question-scoped external evidence, source version, direction, applicability and whether model processing is allowed. Metadata-only content is never treated as substantive support.
2. Store, display and model-processing permission cells are evaluated separately and fail closed. Recorded permissions are operator declarations, not legal verification. Restricted titles/excerpts do not leak through other fields.
3. The actual bounded prompt uses eligible broker passages; validated broker citations must refer to the exact input set. Existing source and fictional assessment citation behavior remains compatible.
4. The server captures the same input fingerprint even when a legacy client omits its preview token. A relevant source, rights or applicability change before save prevents stale persistence.
5. Saved investigations keep immutable input receipts. Revocation, correction or review changes withhold affected derived text, including claims, abstentions and rejected text, while preserving non-content audit identity. Other questions/cases remain isolated.
6. A real Chromium journey exercises the visible evidence preview, distinction between display and model eligibility, persisted result and revocation response. Backend tests exercise prompt inputs, stale denial and persistence across restart using independently authored fictional material and a stub provider.
7. No new dependency, live model execution, patient dataset, merge or deployment is required. Publication is a draft stacked PR against the audited integration branch, with exact-head hosted checks.

## Work sequence

1. Extend existing persistence, context fingerprint, prompt/citation validation and read-time withholding; add behavior and HTTP tests.
2. Extend the existing Composer and result UI, preserving source-reader, numeric-tool and saved-run flows; add the broker browser journey.
3. Apply the upstream CI safety files; add the missing stacked-target check with pinned existing actions and no package installation.
4. Review the combined diff independently, resolve material findings, run Python/JS/browser acceptance and inspect exact-head hosted results.
5. Update the canonical vision, evidence/rights research, technology atlas and implementation register with actual results and remaining gates. Preserve existing issue92 and the repository's execution backlog rather than creating a competing roadmap.

## Next product gates

After this slice, prioritize converging the existing patient/EHR/LIS branch with the investigation workspace, secure identity/consent/authorization and document ingestion with original bytes, provenance and correction review. Use a selected source adapter only after its exact content rights, retrieval rules and intended AI uses are documented. Production stack, first cohort, commercial model and clinical intended use remain separately reviewed decisions. Advanced predictive or image models follow measured need and validation, not the initial launch dependency chain.
