# H1 source-linked brief

## Product and ownership

This bounded increment extends #216 at `6ea7b3cdde680c971414f5b9ace8d513ec5dd7d8` in the existing FastAPI/PostgreSQL16/React workspace. The inspected baseline tree is `545ce116f06890327cf93cfe991849fc0b3c1955`; it matched the source archive from hosted run 41562817032. It supports a readable **source-only brief**, not an AI investigation, biomedical evidence report, clinical assessment or completed review. #203 retains the distinct governed biomedical report/content-rights scope; #210 and #215 remain reference workflow/provenance owners. Parallel #213/#218 contracts must be reconciled before merging overlapping work.

The same canonical PostgreSQL patient, case binding, source versions and assertions remain authoritative. No new table, migration, library, model, second patient store, evidence ledger or review receipt is created. The accepted H1 stack and package locks are unchanged; no Next.js.

## Workflow

Inspect the existing Investigations source view, choose **Prepare source brief**, inspect literal plain text, then **Recheck and download text**. Download calls the backend again; it never exports a previously cached preview. A successful request returns `oi.synthetic-source-brief/1`, an aware preparation timestamp, the inspected source snapshot digest, exact body and body digest. It includes current source-reported statements, original hashes/versions/lines, event/issued/received times, unresolved source labels, limited source-label disagreements and separately listed historical sources.

No information is reinterpreted. Missingness stays distinct from a negative finding. An empty projection is not declared complete. External publications/guidelines are absent. Exact source text is rendered as React text in `pre`, and downloaded as `text/plain;charset=utf-8` under a fixed non-patient filename. No HTML/Markdown renderer or print frame is used.

## API and authority

`POST /v1/patients/{patient_id}/cases/{case_id}/world-model/brief`

Request: `synthetic: true` plus the exact inspected `source_snapshot_sha256`; unknown fields and malformed values reject. Requires existing synthetic authentication, patient_read, source_read and the new independently supplied **source_brief_export** action, exact patient/organization/purpose, active canonical patient and case binding. No creation/read action implies export permission. No default credential gains the new action.

The API reads the original `PostgresWorldModelRead` inside its existing source-owner transaction and checks the expected digest. It validates the typed projection before deterministic rendering. It then re-authenticates the request credential, repeats permission checks and obtains another source-owner snapshot. Permission or fingerprint changes refuse disclosure. These sequential checks are not a distributed transaction and do not guarantee that a revocation arriving after the final check can stop an in-flight response. A digest is neither a credential nor a digital signature.

The body and complete compact UTF-8 JSON envelope are bounded to 64 KiB; an over-limit response is refused rather than truncated. Existing middleware bounds request bodies and adds no-store/nosniff headers. The client independently checks exact response fields, patient/case/fingerprint, time, authority/media labels and body SHA-256 before displaying or downloading it. Selection/session/generation guards discard late results, including A→B→A, navigation, refresh and disconnect. Denied or stale export clears prepared text and the inspected source view. Network/verification failure retains no partial brief; retry is explicit.

This is a read-only preparation path. It records no export, delivery, review or clinical-action receipt. A downloaded copy cannot be recalled, revoked or silently updated. The supported export grant does not prevent manual copying by a user already allowed to read the text.

## Tests and reproduction

```sh
PYTHONPATH=apps/api/src:src python -m unittest discover -s apps/api/tests -p test_source_brief.py -v
cd apps/web && npm test
```

Actual PostgreSQL16 tests require the original disposable database configuration, hash-locked backend dependencies and `OI_API_RUN_DATABASE_TESTS=1`:

```sh
PYTHONPATH=apps/api/src:src python -m unittest discover -s apps/api/tests -p test_source_brief_postgres.py -v
```

That module has four new feature methods plus inherited source fixture methods; total discovery counts are not distinct new test counts. It covers independent permission, no event writes, invalid/cross-case/grant/binding requests, amendment freshness, historical source retention/restart, and permission/source changes during rendering. The extended existing real Chromium journey covers preview, download bytes, no implicit export grant, stale download refusal, revoked export grant, original preservation and desktop/narrow layout alongside the original patient/source/revocation workflow. No browser/mock result substitutes for actual PostgreSQL verification.

## Local checkpoint before publication

Observed red tests: five renderer/HTTP tests failed before the endpoint/module existed; six added client tests failed before the client capability existed. After implementation: five renderer/HTTP tests and 37 total client tests passed (31 inherited + six new). One added negative client case accidentally supplied the same hash as its fixture; its test input was corrected, not the rejection policy. The complete inherited source-ledger suite passed 245 tests, with existing SQLite ResourceWarnings. Python compile, client TypeScript compile and diff checks passed.

A separate ten-test API contract run had nine passes and one environment error because pg8000 is not installed locally. Local PostgreSQL16 and a full locked React/Vite build were not executed; npm acquisition timed out. No substitute driver or unpinned dependency was installed and no checks were relaxed. Hosted exact-head H1 API/React/PostgreSQL/browser results are required, not inferred from this local checkpoint. Consult the PR verification receipt for subsequent observed results.

## Release boundaries

Independently authored fictional records only. Operator-issued synthetic grants are not proof of real identity, consent, professional status or clinical authority. No public patient data, Sid records, licensed scientific text, live model call, diagnosis, prescription, outreach, deployment or clinical validation. Source statements and conflicts remain unreviewed; the complete biomedical investigation/review migration remains separate. Source owner/security/product review and final combined-head regression are required before merging. This increment does not change accepted architecture or approve a commercial distribution.
