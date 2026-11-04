# H1 original-image custody — implementation record

Date: 2026-11-03. Base: PR #222, commit
`911b0767c671ae6f40caf20f204aedf1e9df2ab0`.
Requirements: OI-006 original custody and provenance; OI-009 source amendments;
OI-013 exact patient access, integrity and recovery. This is an increment to
the existing H1 owner, not an alternate platform architecture.

## Decision

Store bounded original DICOM bytes as immutable children of `clinical_source`.
Reuse the existing canonical patient registry, qualified case mapping,
authentication port, source-original validation, transaction and event journal.
Two child tables separate each original object from its explicit source-version
links. An amendment can link the same object without duplicating raw bytes.

The current profile uses PostgreSQL bytea. It provides an executable HTTP and
persistence boundary before a private external object/PACS adapter is adopted.
The existing #217/#219/#220 PACS experiments remain evidence owners; their
service tokens, caller-supplied expected digests, or modality policies are not
substitutes for H1 patient/source authority. This does not protect independent
PACS copies. No PACS dependency or public image URL is introduced here.

## Contract

- An exact current imaging report is validated through the existing source
  parser and stored digest. Historical text remains available through its
  existing owner; current-image access requires a current parent.
- Original bytes supply DICOM identifiers and the server computes SHA-256.
  No hash, UID or upstream URL supplied as an API parameter establishes custody.
- In this bounded profile `PatientID` equals the locked binding's
  `source_subject_ref`; `IssuerOfPatientID` equals the exact concatenation
  `source_organization + "/" + source_system`. Both existing key fields forbid
  `/`, preserving an unambiguous qualified namespace. Bindings whose qualified
  issuer exceeds 64 bytes are outside this profile. No name,
  demographic, prefix or approximate identity matching occurs. The mapping
  itself is synthetic/operator-authored; `source_identity_verified` stays false.
- `StudyDate` must equal the original report's event date. This exact constraint
  is a development profile, not a general rule about clinical report dates.
- `image_import`, `image_read` and `image_original_read` are independent explicit
  actions on the existing Principal. Every operation also requires patient_read,
  exact patient membership, persisted organization and binding purpose.
- Identical imports to the same source are idempotent. Same case/SOP with
  different bytes conflicts. Linking an existing identical object to a new
  current source requires an explicit import and an immutable link event.
- Imports and all disclosures refresh the same actor, organization, purpose,
  patient and operation grant. Read receipts commit before buffered bytes are
  returned. Event or commit failure withholds the response. Receipts attest a
  grant for prepared disclosure; they do not attest client delivery.
- Patient/case locks serialize database custody with suspension, binding
  revocation and source amendment. This is not distributed revocation atomicity.
  A future network adapter needs a second transaction after fetching bytes so a
  revocation completed during a remote fetch is observed.
- Maximum original: 2 MiB; maximum case: 256 objects and 64 MiB. No archives,
  sequences, compressed transfer syntaxes or external bulk-data references.
  The five-second ingress deadline also applies to chunked bodies.

## Delivery and verification

1. Audit #222 source/identity/receipt owner and #219/#220 limitations — complete.
2. Author failing actual-HTTP route/body-bound tests before adding routes —
   observed three failing tests (four assertions) on the unchanged route owner.
3. Implement strict bounded parser, immutable migration, custody and routes.
4. Derive a deterministic code-only pydicom wheel from an exact hash-verified
   upstream wheel; exclude unapproved sample datasets before installation.
   Pin the result in the existing dependency inventory and verify notices,
   wheel RECORD, transform provenance and offline installation.
5. Verify parser and ingress locally, then actual PostgreSQL/API migration,
   permission, amendment, event failure and integrity tests in exact-head CI.
6. Verify API/database restart and pg_dump/pg_restore with two independently
   authored originals; preserve existing H1 and React integration gates.
7. Independent review, draft PR, actual-result publication and canonical roadmap
   reconciliation. Implementation and deployment statuses remain separate.

Local execution has no Docker CLI and only UID 0 in its user namespace; the
available PostgreSQL binary refuses that execution identity. Actual database
and container acceptance therefore belongs to the existing hosted H1 gates.
No substituted SQLite test is presented as PostgreSQL verification.

## Remaining boundaries

The parser profile is deliberately narrower than general DICOM. There is no
pixel interpretation, clinical validation, viewer, verified external-source
identity, production account/consent provider, production role/RLS qualification,
regulated-device approval, or authorization to process real-patient records.
Code/license review has the existing local synthetic-development scope; bundled
vendor sample files are excluded rather than cleared by the code license.
The next integration is the existing patient workspace's authorized image
attachment/retrieval experience, followed by private storage/PACS selection when
the corresponding access and content rights gates are satisfied.
