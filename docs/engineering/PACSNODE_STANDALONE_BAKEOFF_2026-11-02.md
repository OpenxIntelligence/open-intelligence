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
