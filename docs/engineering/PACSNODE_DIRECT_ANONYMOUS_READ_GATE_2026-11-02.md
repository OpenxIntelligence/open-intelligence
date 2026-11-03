# PACSNode direct anonymous read observation — synthetic security acceptance

**Status: RESEARCH / HOLD.** Stacked on draft [#207](https://github.com/OpenxIntelligence/open-intelligence/pull/207) and its real standalone PACS evaluation [#180](https://github.com/OpenxIntelligence/open-intelligence/pull/180). No clinical access, production integration, legal approval or backend adoption.

## Why this exists

The first-party adapter can reject wrong-case access and source versions superseded by a report amendment. **Those OI checks do not prove that the underlying PACS prevents direct requests for the DICOM object.** A backend can preserve original bytes, pass QIDO/WADO integrity checks and still allow an anonymous caller to fetch the same SOP through the PACS URL.

This slice adds `tools/imaging/pacsnode_direct_access_gate.py`, an independent, read-only negative-security observation **after** the existing synthetic test has stored two fictional CT SOPs and proved first-party report-amendment denial.

## What is actually observed

- Requires the exact successful prior evaluator receipt, pinned upstream commit, independently authored fictional SOP set, byte-identical SHA-256 digests, and documented OI wrong-case and amendment denials. Malformed or failed prior receipts are rejected **before HTTP**.
- Makes one **unauthenticated, no-cookie, no-proxy, no-redirect** direct WADO GET per SOP on the explicit `127.0.0.1` origin. No new data are uploaded.
- Reports `anonymous_original_access_observed` only when a 200 multipart DICOM response contains the **exact original** synthetic SOP bytes. Records only HTTP status, outcome and hashes, never DICOM bytes or pixel content.
- A 401/403 is an observed denial, **not** a claim that patient grants, tenant isolation, purpose limits or source revocation work. A 404, altered bytes or malformed response is *inconclusive*, not a false access-denied pass.
- Writes a bounded receipt separately from the upstream byte-integrity result. Successful evidence collection still sets `upstream_patient_authorization_verified=false`, `upstream_revocation_verified=false`, and `backend_adoption_approved=false`.

The existing PACS evaluation starts a synthetic-only local service in GitHub Actions; it remains **not proven listener-confined** because the pinned server's default bind is `0.0.0.0`. A loopback client URL does not establish server network confinement. No real patient records or identifying images may be sent.

## Execution and proof

1. Existing isolated workflow `.github/workflows/pacsnode-standalone-evaluation.yml` builds pinned PACSNode with standalone SQLite/filesystem features, runs two-SOP multipart STOW/QIDO/WADO and validates OI source-amendment denial.
2. A new offline `tests/test_pacsnode_direct_access_gate.py` suite checks exact original exposure, 401/403, inconclusive 404/altered MIME, invalid receipts, loopback restrictions and no-leak receipts.
3. With the SAME PACS still running and objects still stored, the workflow runs the direct anonymous retrieval observer using `verification-artifacts/pacsnode-real-dicomweb.json` as its prerequisite. A separate JSON receipt is uploaded with the existing hash-only artifacts.
4. Treat this as negative control evidence. A passing test run means the observer executed; it does **not** clear PACS authentication, ownership of the upstream object, or DICOM PS3.18 conformance.

## Required backend decisions before adoption

- Authenticated QIDO/WADO/STOW at the service or policy-enforcing gateway, with **direct URL bypass tests**, cross-tenant/person/purpose denial and revocation after source amendment.
- Proven process/network listener confinement; protected service credentials and audit receipts; independently checked original DICOM retention and deletion/reconciliation rules.
- Exact pinned dependency and redistributed asset/license SBOM, NOTICE, codec and viewer rights, clinical intended-use/security validation, and independent review of the candidate's QIDO `application/json` media-type deviation.

**Release decision:** HOLD. Do not expose this candidate as a patient-facing imaging service or merge stacked research PRs as a substitute for the backend approval gates.
