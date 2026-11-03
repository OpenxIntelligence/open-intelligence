# Native PACSNode OIDC security bake-off — authenticated DICOMweb is not patient authorization

**Status: isolated test-only candidate / ADOPTION HOLD.** Pinned upstream `knopkem/pacsnode@e9b4334477a66967d290add9e0b9afa068f59dc0`; depends on [draft #217](https://github.com/OpenxIntelligence/open-intelligence/pull/217) -> [#207](https://github.com/OpenxIntelligence/open-intelligence/pull/207) -> [#180](https://github.com/OpenxIntelligence/open-intelligence/pull/180), all unmerged. No patient data, clinical device, licensed model, real identity, or production service.

## Source audit and reason for this experiment

The prior pinned standalone PACS ran with `[plugins].enabled` not including `basic-auth`. Its live anonymous WADO probe retrieved **both** fictional original SOP objects with status 200, despite the OI adapter refusing an amended source. This is proven research evidence, not a claim about all PACSNode configurations.

The inspected pinned Rust upstream contains **optional built-in `basic-auth`** supporting externally issued OIDC bearer JWTs, validated using a static RSA public key; a `PolicyEngine` assigns `viewer` read permission, `uploader` upload-only permission, and optional `modality_access` restrictions. The same source **does not implement case/patient, tenant, or purpose scoping in its native `PolicyEngine`** (it checks role and modality). The HTTP server binds `0.0.0.0`; the DIMSE server and other routes remain separate security concerns. The upstream README warns **NOT FOR CLINICAL USE**.

The aim is to test what enabling the real native middleware changes, not to invent a parallel PACS, claim that OI grants have reached the PACS, or suppress the earlier failed isolation result.

## Executable synthetic experiment

1. Run the existing pinned standalone Rust/SQLite/filesystem source-and-pixel protocol test with two newly authored fictional 2x2 CT DICOM Part 10 objects. Confirm exact original SHA-256, OI wrong-case and amendment denial, and direct anonymous 200 as baseline.
2. Stop the **same** PACS process while preserving its temporary SQLite database and stored fictional SOPs.
3. Generate an RSA-2048 keypair inside GitHub Actions runner temp using OpenSSL. Rewrite **only the generated temporary** PACS configuration to enable the upstream `basic-auth` plugin in `oidc` mode with a static public verification key. Disable embedded viewers/admin for this isolated auth test. No real IdP, network calls to a remote issuer, cookies, long-lived secrets, static checked-in keys or new code dependencies.
4. Restart the original pinned binary on the original port/database. The new test issues ephemeral fixture-signed RS256 JWTs for `oi_viewer`/CT and `oi_uploader` and deliberately provides conflicting fictional `patient_id` attributes.
5. Exercise actual native PACS routes: anonymous WADO (instance/study/metadata/WADO-URI), QIDO, REST and STOW; invalid or expired bearer; authenticated CT viewer; disallowed modality; disallowed uploader read; and **a token whose patient claim belongs to the other fictional patient**. Compare complete original Part 10 bytes, never just the HTTP status.
6. Emit only categorical status fields and hashes. Neither JWT, RSA private key, public-key configuration, DICOM bytes, images nor response bodies are included in CI artifact uploads. Preserve both anonymous and secured receipts to prevent a falsely reassuring pre/post comparison.

## Success criteria and interpretation

- Expected: all tested anonymous routes reject unauthorized requests; invalid/expired tokens rejected; authorized viewer retrieves the expected original; uploading role cannot read; restricted wrong modality cannot read.
- **Do not define success as secure patient isolation.** If the wrong fictional patient's fully valid CT viewer token retrieves the SOP, record `different_patient_original_bytes_exposed=true` and keep the release on HOLD.
- Even if a 403 is observed for a cross-patient token, do not infer OI patient/consent scope or server-side revocation without verifying policy and binding enforcement against the canonical source ledger.
- The OI adapter's post-retrieval amendment check remains valuable but cannot revoke direct PACS objects. Retained storage does not automatically equal unauthorized access; access is independently controlled.
- Full DICOMweb conformance, compressed decoded pixels, QIDO media type, clinical intended-use validation, secure listener, DIMSE, native patient-level ACL, tenant segregation, revocation, persistent authorizations, audit, upstream licenses and embedded assets **remain separate approval gates**.

## Next first-party implementation dependency

Build a patient/case/purpose authorization integration over the **existing canonical FastAPI/PostgreSQL clinical-source owner**, not a second patient ledger or an invented clinical grant. It must authenticate the actor, revalidate `patient_read` + `source_read` and exact source version under a consistent transaction, emit access receipts, and restrict PACS network reachability to a trusted service or gateway. Test direct raw-PACS URL bypass from a separate network identity; deny cross-patient, revoked and stale-source readers at **every actual retrieval surface**. Implement DIMSE ingress controls separately.

**Decision:** PRESERVE the optional PACS native-auth capability as a candidate technology; do not adopt PACSNode or approve use with identifiable patient data. Require owner, clinical safety, licensing, and security review before any live deployment.
