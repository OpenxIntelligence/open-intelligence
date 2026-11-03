# PACSNode source-bound read acceptance — original bytes, never clinical authorization
**Status: staged draft, independently fictional evaluation only.** This is a follow-up to the [real PACSNode bake-off PR #180](https://github.com/OpenxIntelligence/open-intelligence/pull/180), stacked on #169 → #155 → #146. The external server is not an Open Intelligence patient authority.

## Actual functionality
- `tools/imaging/source_bound_wado.py` adds a reusable *test-only*, read-only WADO acceptance gate.
- An explicit `SyntheticWadoBinding` records one OI case ID, current imaging report version ID, original report SHA-256, exact Study/Series/SOP UIDs and the original DICOM object SHA-256. These are two **different** original-content hashes.
- Before sending a request, the test checks current original report/source and same-case identity using the existing `CaseStore.state()` and `check_dicomweb_metadata()`, rather than the DICOM PatientID as an access token.
- Requests only an explicit SOP over a non-credentialed, **127.0.0.1** HTTP origin using the existing no-proxy/no-redirect backend client. Verifies the exact original object bytes and rechecks that the original report remains current after the network operation.
- The result is a **digest-only, source-anchored receipt**. Neither raw DICOM data nor pixels are emitted, and no source/patient ledger is modified.
- Live PACSNode evaluation on the stacked branch exercises this exact gate for the two stored fictional SOPs, tests another fictional case and rejects a report amendment before any new OI read. The upstream PACS retains responsibility for its own storage and access controls.

## Negative contract
- Old/superseded source version or changed original SHA -> deny before HTTP.
- Unrelated fictional case or malformed Study/Series/SOP identity -> deny before HTTP.
- Changed original object digest, unexpected WADO status, malformed multipart MIME and extra bytes after closing MIME boundary -> deny.
- A source amended **during** WADO fetch -> no result is published; a completed old receipt is not silently treated as current.
- Missing/invalid data never produces a normal radiology conclusion, and no public REST endpoint is created.

## Critical limitations
- **No user authentication or authorization:** the caller supplies case/source binding. This is a synthetic engineering acceptance contract, *not* an identity or consent capability. No real patient data, clinical production release or externally accessible endpoint is allowed.
- **No upstream object revocation:** an OI report amendment does not remove or restrict direct PACS access; that must be enforced with actual service-level tenant/actor/purpose control before clinical integration. The receipt explicitly labels upstream revocation **not verified**.
- **No DICOM conformance certificate:** PACSNode QIDO results currently use generic `application/json`, not `application/dicom+json`; full PS3.18 conformance remains on HOLD. The shared multipart MIME parser now rejects malformed framing/epilogue; this is stricter than a tolerant mail parser, not a general-purpose clinical DICOM decoder.
- **No source of medical facts other than OI's existing original record ledger:** the original imaging report is source-linked but does not itself prove the image belongs to a clinically authorized individual or that a laboratory/radiology review happened.
- **No vendor adoption:** PACSNode is still MIT-declared only at the upstream source level with missing conventional root LICENSE, unreviewed dependency/codec/viewer rights, default Docker MinIO licensing concerns, unaudited listener/access controls and explicit NOT FOR CLINICAL USE wording.

## Required next integration gates
1. Owner-reviewed actor identity, tenant/case/role/purpose grants and revocation enforced at the proxy/backend boundary; test **direct** PACS URL bypass, not merely an OI Python helper.
2. Exact source-to-DICOM binding entered via an authorized ingestion transaction with immutable stored DICOM hash and case/episode relationship, not caller-supplied arbitrary hashes.
3. Independent executable DICOMweb PS3.18 conformance tests for QIDO media negotiation, STOW response contract, WADO multipart and compressed codec equivalence.
4. Persistent source-linked object lifecycle, crash/restart/retry and immutable audit; signed scoped receipts and permissions for the clinician/patient viewer.
5. Pinned license/NOTICE, binary and transitive SBOM, codecs/embeddings/viewer assets, legal/clinical/privacy review. Keep OI-17 controls, no Next.js and synthetic-only engineering until separately authorized.

**Verification:** `tests/test_source_bound_wado.py` exercises original digest, case isolation, preflight/late amendment, framing and wrong URL; `tests/test_pacsnode_probe_contract.py` adds explicit MIME epilogue refusal. Hosted exact-head CI evidence should be linked in the PR after it completes, with failed attempts preserved.
