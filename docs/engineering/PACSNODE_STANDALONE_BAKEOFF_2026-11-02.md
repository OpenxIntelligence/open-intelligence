# PACSNode DICOMweb backend — isolated synthetic evaluation (B-06)

**Status:** Research-only evaluation, never an adopted runtime or medical device. Date: 2026-11-02. Parent: [draft PR #169](https://github.com/OpenxIntelligence/open-intelligence/pull/169) → [#155](https://github.com/OpenxIntelligence/open-intelligence/pull/155) → [#146](https://github.com/OpenxIntelligence/open-intelligence/pull/146). This study does not change canonical patient, case, source, consent or clinician-review contracts, nor introduce Next.js.

## Evidence that justified a bounded experiment

- [pacsnode](https://github.com/knopkem/pacsnode) official repository: commit `e9b4334477a66967d290add9e0b9afa068f59dc0` (2026-04-06); standalone Rust PACS advertised with STOW-RS/QIDO-RS/WADO-RS, SQLite + filesystem mode, optional PostgreSQL + S3 for multi-node. Version `0.2.1` in root Cargo workspace. Upstream expressly warns that it is not validated for clinical use.
- Its `NOTICE` states MIT; `Cargo.toml` workspace declares MIT. **No conventional root LICENSE file was found** in the inspected commit, so release-specific attribution/source terms require independent confirmation. A root declaration is not a full transitive licensing or security verdict.
- Its `Cargo.lock` supplies dependency pins; the isolated workflow records the SHA-256 and Rust version and emits a crate-level declared-license snapshot. **No software bill of materials or license clearance is claimed** merely because that report exists.
- The separately maintained `dicom-toolkit-rs` source (used through 0.5.0 crates) declares `MIT OR Apache-2.0` at workspace level and provides a NOTICE acknowledging DCMTK and CharLS as research references. Code/data/binary notices and exact crate versions still need verification.
- The upstream **default Docker Compose uses MinIO**, which has known AGPL/archival issues in OI-17. **This experiment does not run Docker Compose or MinIO.** It compiles `pacs-server` using only `--no-default-features --features standalone` and uses a temporary SQLite database and filesystem.
- [pydicom 3.0.2](https://pypi.org/project/pydicom/3.0.2/) core is MIT and has no mandatory Python packages. This experiment installs the sole pure-Python wheel via `--no-deps --only-binary --require-hashes` using **SHA-256 `abf971a5440f84dbaf42c4b6758e30e62480902584f8b270b9a5d146e278a07b`**. No optional `[gpl-license]` or compressed-image extra is allowed.
- Other upstream choices [dcmjs-org/dicomweb-server](https://github.com/dcmjs-org/dicomweb-server), [DICOMcloud](https://github.com/DICOMcloud/DICOMcloud) and [dicomweb-pacs](https://github.com/knopkem/dicomweb-pacs) were reviewed as alternatives. dcmjs declares Apache-2.0 but its documented Dockerfile uses Node 13 and its example compose uses CouchDB 2.3.1; DICOMcloud Apache-2.0 code is older; dicomweb-pacs MIT root uses a native DCMTK-derived addon and its README lists QIDO/WADO and DIMSE rather than STOW-RS. None is accepted as a production dependency.

## Actual test implementation (only the tests specified here)

- `tools/imaging/pacsnode_live_probe.py` is a **loopback-only, redirects-disabled, read-write synthetic evaluation client**.
- Creates two independently authored 2×2 uncompressed CT Part 10 SOP instances using only the hash-pinned pydicom wheel. No third-party reference images, copyrighted textbooks, patient data or bulk genomics.
- Sends a two-part **genuine multipart STOW-RS** request to `POST /wado/studies`, looks up the specific study and instances via **QIDO-RS**, retrieves each instance via **multipart WADO-RS**, then compares SOP/Study/Series IDs, fictional PatientID, original complete object bytes and original pixel bytes. A response transformation is reported as such; no false source-preservation claim.
- Validates the returned instance set against the existing canonical `CaseStore` report-version projection, **using explicit OI case/source binding**, not DICOM PatientID as a permission token.
- Repeats the same binding check for another fictional patient (must be refused), and adds an amended imaging report (old OI binding must be refused). **This does not mean the standalone upstream PACS itself enforces tenant/caregiver/clinician permissions or that stored SOP objects are revoked upon an OI report amendment.**
- Records source commits, SHA-256 and bounded run receipts, not synthetic DICOM payloads. `tests/test_pacsnode_probe_contract.py` tests loopback blocking, multipart parser and metadata assumptions offline.
- `.github/workflows/pacsnode-standalone-evaluation.yml` runs only against the isolated research branch or explicit manual dispatch, with read-only repository permissions. It pins the upstream source commit; compiles from its lockfile; never publishes a PACS, opens a public port intentionally, or connects PHI.

## Strict statuses and stop conditions

- **Researched:** upstream capabilities and source-level licenses, exact commit, standalone mode.
- **Implemented:** standalone evaluator scripts, rights/receipt harness, pinned fixture dependency and isolated CI.
- **Tested:** only mark STOW/QIDO/WADO successful if the hosted workflow runs and the emitted receipt/actual HTTP results verify it. CI errors are evidence, not hidden.
- **Not implemented or approved:** DICOM/PS3.18 conformance certification, full server security, production identity/consent, regulated image processing, exact legal clearance, packaged binaries, deployment, MinIO or models.
- **Adoption:** HOLD. Real enterprise PACS selection requires full source+binary SBOM, copyright/NOTICE review, codec/asset/plugin rights, FHIR/DICOM mapping, exact patient and tenant scopes enforced at the service, authenticated QIDO/WADO/STOW, audit/access revocation, object retention/amendment semantics, disaster recovery, performance/availability, clinical intended-use risk classification, professional signoff and owner authorization.

This evaluation is a **candidate bake-off** tied to the existing [OI-17 policy](https://app.notion.com/p/40a3866f77ef815a97d5e016ededf5b9), the original 556-entry technology register and [backend wave #135](https://github.com/OpenxIntelligence/open-intelligence/pull/135). It is not a second technology registry or a new product architecture.

## Verified checkpoint and stricter original-preservation gate

The uncompressed experiment at first-party commit
`81569bf6d909d9f7d153955642056c0ae57df280` completed in
[run 41554474814](https://github.com/OpenxIntelligence/open-intelligence/actions/runs/41554474814).
The downloaded artifact ZIP SHA-256 was
`950e7afb9f3451fc30a682c52d2187b836a36330490cc7584a8efd71c7b8a965`.
Its receipt verifies both complete Part 10 files and both eight-byte pixel values
survived STOW/QIDO/WADO unchanged in the explicitly uncompressed storage mode.
The existing first-party wrong-case and amended-source checks also passed.
QIDO study and instance replies were `application/json`, so media conformance
remained HOLD. STOW also returned `application/json`; this evaluator records its
status/body digest but does not validate the complete STOW response contract.
The checkpoint is evidence for that commit, not proof of later revisions.

The previous encoded-pixel mismatch is consistent with the pinned backend's
default archival transcoding, not evidence sufficient to establish image
corruption. [Upstream storage settings](https://github.com/knopkem/pacsnode/blob/e9b4334477a66967d290add9e0b9afa068f59dc0/crates/pacs-core/src/domain/server_settings.rs)
default to HTJ2K lossless `1.2.840.10008.1.2.4.201`, and
[STOW ingestion](https://github.com/knopkem/pacsnode/blob/e9b4334477a66967d290add9e0b9afa068f59dc0/crates/pacs-api/src/routes/stow.rs)
transcodes when the incoming syntax differs. Neither the earlier failure nor
the uncompressed success establishes decoded fidelity of that compressed path.

The evaluator now requires **both complete-original equality and matching raw
pixel bytes in the expected uncompressed transfer syntax** for a successful
technical result and exit code. Complete-file changes are a source-custody
failure in this experiment even if DICOM permits an equivalent representation.
This is an Open Intelligence preservation requirement, not a claim that DICOM
generally requires identical file serialization.

- WADO explicitly requests `transfer-syntax=1.2.840.10008.1.2.1`, and records that
  actual Accept value. Default negotiation remains a separate unverified path.
- Ten dependency-free harness/CLI checks include nonzero exit for changed
  originals, retained pixel-failure receipts and safe receipts on early errors.
- Eight isolated pydicom regression cases exercise real generation/parsing and
  the first-party ledger, replacing only external HTTP: exact roundtrip, changed
  preamble, changed nonpixel metadata, changed pixels, unexpected valid syntax,
  explicit negotiation, valid fixture VRs and separate QIDO media HOLD.
- The new tests were observed failing against the earlier evaluator in
  [run 41555614502](https://github.com/OpenxIntelligence/open-intelligence/actions/runs/41555614502):
  original-file changes were incorrectly accepted, the advertised transfer
  syntax was not sent, and the fictional accession number exceeded SH's limit.
  The accession is now `OI-SYNTH-ACC-001`; no source patient data was involved.
- CI uses a fresh temporary database because persisted server settings override
  bootstrap configuration. It preserves the exact evaluator commit alongside
  the upstream pin, configuration, regression output and numerical receipts.
- Local dependency-free checks pass. The local full suite cannot open loopback
  sockets in this execution environment (`PermissionError: Operation not permitted`),
  and the isolated pydicom package is unavailable locally. Hosted CI must verify
  the full Python/HTTP suite, real-pydicom tests and live backend at the new head.

[PS3.18 section 8.7.3.4](https://dicom.nema.org/medical/dicom/current/output/chtml/part18/sect_8.7.3.4.html)
defines Explicit VR Little Endian as the default object-payload transfer syntax,
with specified exceptions. The pinned
[WADO handler](https://github.com/knopkem/pacsnode/blob/e9b4334477a66967d290add9e0b9afa068f59dc0/crates/pacs-api/src/routes/wado.rs)
returns stored bytes when no syntax is supplied; review and live tests of that
compressed-storage/default-negotiation path remain necessary.

The loopback-only restriction belongs to the evaluation **client**. Upstream's
HTTP listener binds `0.0.0.0`; the receipt does not claim server confinement,
authentication or tenant isolation. Existing license, embedded asset, codec,
authorization, recovery and clinical gates remain HOLD. This advances B-06 and
the existing OI-006 source-preservation/OI-013 isolation requirements without
adopting the backend or modifying application persistence or business logic.
