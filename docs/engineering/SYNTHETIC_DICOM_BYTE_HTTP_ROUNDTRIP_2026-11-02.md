# Open Intelligence — Synthetic DICOM Part 10 / HTTP Roundtrip Experiment

**Status:** isolated engineering experiment stacked on [imaging metadata contract PR #146](https://github.com/OpenxIntelligence/open-intelligence/pull/146). **Not a DICOMweb-compliant PACS, production endpoint or clinical imaging system.**

## What is implemented
- One independently authored 2×2, 16-bit fictional CT object serialized into genuine **DICOM Part 10 byte structure** with 128-byte preamble, `DICM` prefix, file meta and explicit-VR little endian typed elements. No patient records were used to construct it.
- An intentionally minimal loopback-only (`127.0.0.1`) HTTP test transport. POST `/studies` accepts `application/dicom` (simplified, single part, **not standards-compliant STOW-RS multipart**). GET `/studies` returns JSON resembling QIDO-RS result. GET `/studies/{study}/series/{series}/instances/{instance}` returns original bytes (simplified single-part, **not full WADO-RS negotiation**).
- The transport uses the pre-existing [PR #146](https://github.com/OpenxIntelligence/open-intelligence/pull/146) `check_dicomweb_metadata` against current versioned fictional imaging report in `CaseStore`; a wrong case, superseded source or mismatched source date is refused. Per-request connections avoid cross-thread SQLite use.
- Byte-for-byte SHA-256 verification of the stored/retrieved synthetic object, independent of the metadata report SHA. No persistent PACS storage: the object is in-memory only. An original source amendment returns HTTP 409 on subsequent reads.
- Five new regression tests in `tests/test_synthetic_dicom_roundtrip.py` for actual binary HTTP roundtrip, wrong patient, malformed object, amendment invalidation, and ledger immutability.

## Exactly what is not implemented
No actual DICOMweb STOW multipart request or study-bulk retrieval, standard QIDO filtering, robust DICOM parser, authenticated/access-authorized storage, encrypted object storage, durable SOP ingestion, real medical image, real clinician, pixel analysis, radiology inference, RLE/JPEG/JPEG2000 codec or regulated deployment. This minimal test server is **not safe for external exposure**; it is a future-backend interface experiment.

## Why no new backend dependency was installed
Existing [OI-17 license governance](https://app.notion.com/p/40a3866f77ef815a97d5e016ededf5b9) and [backend rights audit #134](https://github.com/OpenxIntelligence/open-intelligence/pull/134) require pin/verification of every direct and transitive package, optional codec and media/model asset. Upstream pydicom MIT core and dicomweb-client MIT are promising, but package/component rights and service interoperability need qualification. In particular, pydicom's optional `pylibjpeg[libjpeg]` integration includes GPLv3 code; do not install unrestricted extras.

## Next test against a real permissive backend
1. Select exactly one fixed-release **verified permissive** DICOMweb server candidate with code, container, dependencies, plugins, codecs, fonts and license/NOTICE cleared.
2. Use independent synthetic DICOM with Study/Series/SOP identifiers, pixel hashes and explicit case/report binding.
3. Exercise actual DICOMweb multipart STOW-RS, QIDO-RS, WADO-RS and compare original bytes and separate deidentification/permission policies.
4. Test unauthorized patient and tenant boundary, unrecognized UIDs, duplicate SOPs, amended imaging report, audit trail, failure and restart, retention and storage encryption.
5. Add actual viewer/annotation and image-processing evaluations only after validating the separate components and clinical intended use.

**No adoption or merge authorization** is implied by passing this test. Preserve source-case truth and first-party domain ownership, no Next.js and no named-person case data.