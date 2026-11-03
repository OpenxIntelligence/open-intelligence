# H1 Canonical Source Questions × DICOM Original Custody

**Status:** Isolated draft integration candidate. Fictional engineering records only;
not merged, not deployed, not a clinical imaging/diagnostic service.

## What is actually integrated

This branch builds on the verified canonical source read receipts, rights-gated
source-derived Patient World Model, Composer preflight and durable source-linked
question intake from [#234](https://github.com/OpenxIntelligence/open-intelligence/pull/234)
and [#244](https://github.com/OpenxIntelligence/open-intelligence/pull/244).
It composes the **source-owned** bounded original DICOM custody implementation
from [#242](https://github.com/OpenxIntelligence/open-intelligence/pull/242).

**One patient** remains `identity.identity_patients`; **one case binding**
remains `coordination.patient_case_bindings`; **one original report/line owner**
remains `clinical_source.source_versions` and `clinical_source.assertions`.
Question intake remains `investigation.source_questions` and the original
append-only patient event journal remains `identity.identity_domain_events`.
The image tables from #242, `clinical_source.dicom_objects` and
`clinical_source.source_image_links`, retain original DICOM bytes and link
them explicitly to one already accepted original *imaging report* version.
No duplicate patient/source/evidence/approval store or third-party PACS was
introduced. No image interpretation, genome model or clinical conclusion.

### Image/source boundary

Image import is explicitly limited to the independently authored, source-bound,
single-frame 16-bit uncompressed CT profile from #242, max 2 MiB per original.
Source reports must be current, explicitly linked to the exact active case
and verified against original UTF-8 bytes and source-version metadata. The
DICOM PatientID, IssuerOfPatientID and StudyDate must agree with the unique
case binding/source. An amended report does **not** silently inherit image
access; explicit re-link is needed. Images remain byte-identical and immutable.

`POST /v1/patients/{patient_id}/cases/{case_id}/sources/{source_id}/images`
requires an independently allowed `image_import` action.
`GET .../images` requires `image_read`;
`GET .../images/{image_id}` requires `image_original_read`.
Every route also requires canonical `patient_read` and the
active patient/case mapping, purpose and organization. Exact source, grant,
actor and original-byte checks precede exposure of raw bytes and are
repeated before the existing event journal's access receipt is committed.
An authorization receipt attests **prepared disclosure under checked
synthetic grants**, not confirmed network delivery or distributed revocation
atomicity. The existing source/World Model/Composer/question routes and
their independent permission semantics are preserved.

### Alembic history is deliberately not rewritten

Two existing published and separately tested revision branches descend from
`0005_source_versions`:

```
0005_source_versions
    ├── 0006_source_questions
    │       └── 0007_question_snapshot_contract
    └── 0006_image_custody

    0008_questions_images_merge  (both parents; no destructive DDL)
```

The merge revision `0008_questions_images_merge` requires both original
owners and the question fingerprint-column contract before marking the API
ready. It leaves the original `0006` and `0007` files and migration IDs
intact; no schema adoption based on a matching table name, source retargeting,
blanket `CASCADE` or magical version substitution. A real disposable
PostgreSQL upgrade from **either** previously applied branch must land at
one merged head, and a failed/unknown owner must remain refused rather than
silently adopted. Existing historical question hashes are not rewritten.

The merged app's `SCHEMA_REVISION`, version manifest, readiness, exact
OpenAPI paths, SQLite independence, migration cleanup fixtures, patient
backup/restore and image backup/restore should all agree on that one head.
The original #242 reviewed pydicom code-only runtime transformation and
its pinned input/output SHA-256, licenses, package inventory and build
instructions are copied as owned artifacts, not replaced with an unvetted
distribution or sample patient dataset. The H1 API and React workflows
must prepare the *same* code-only, hash-locked runtime wheel before tests.

### Verification and release boundaries

Real PostgreSQL 16 migrations and test suites must independently validate
source/question World Model and the original-image binary ingress, identity
and issuer, byte-for-byte upload/retrieval, 2 MiB limits, deduplication,
amendment/re-link, case-tenant denial, midflight credential revocation,
immutable database guards, database/API restart and `pg_dump`/restore.
The built React patient workspace must retain its current question/source
browser journey, rather than being replaced by an unconnected image demo.

Passing synthetic engineering tests do not qualify imaging diagnostic quality,
full DICOM/PACS interoperability, third-party rights/redistribution,
real clinician identity, real patient consent, PHI security or clinical
treatment. This slice does not add a diagnostic viewer or medical model.
The separate nonterminal verification-return inbox [#267](https://github.com/OpenxIntelligence/open-intelligence/pull/267)
is **not** silently overlaid on this divergent canonical World Model
branch. It remains an explicit next source-owner reconciliation requiring
fresh exact-head combined PostgreSQL/browser verification. A terminal
clinical reviewer or signed decision is not implemented here.

Do not merge main or deploy without owner, clinical/security, rights and
product signoff.
