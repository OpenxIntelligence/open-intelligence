# H1 Imaging study and series navigation — presentation-only continuation

## Purpose

Extend the existing connected patient Imaging workspace from PR #608 by grouping the already-authorized synthetic DICOM originals under their recorded study UID and series UID. Avoid replacing the source ledger, changing image custody, or claiming a diagnostic viewer.

## Contract

- Uses `SourceImageIndex.images` only after the existing scoped source-image read has succeeded. Each list is already bounded and permission-checked by the canonical API and client decoder.
- Study grouping is keyed by `study_uid`; series grouping is scoped within its study, not globally. Original object references, order within each series, and image IDs are preserved.
- Existing per-image preview and exact DICOM download callbacks remain attached to the same `source_id`/`image_id` pair. No sorting of images, new requests, independent permissions, persistence, zoom/windowing, diagnostic interpretation or inferred clinical status.
- The metadata receipt remains visible once per source response. Empty response remains explicit; identity/case/source revocation clearing stays in the existing session owner.
- Responsive nested lists keep the original keyboard focus and buttons. The grouped view is structural navigation, not a diagnostic image interpretation or verified imaging study report.

## Verification

Pure projection regressions use zero, repeated series UID across studies, multiple series, immutability, order and object identity. The server-rendering regression exercises source image buttons, metadata receipts and empty states. Browser/runtime and backend recovery must pass on the exact new published revision before acceptance; prior PR receipts are not inherited.

No runtime dependency, schema, backend, source metadata, security, model or clinical release change is authorized. Draft branch only; merge and deployment remain separate review gates.
