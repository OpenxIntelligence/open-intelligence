# Laboratory workflow convergence

## Purpose and authority

Execute the founder's 5 November unified directive through the existing OI-007,
OI-008 and OI-009 contracts. A patient must be able to keep a laboratory question
with its original result, find it in Overview, inspect its permitted citations,
and recognize that an amended report requires reassessment.

This is a bounded integration of existing owners, not a replacement architecture
or a new canonical mandate. The founder explicitly authorized reversible
engineering, reconciliation, testing and a reviewable pull request. No merge or
clinical release is part of this increment.

## Frozen inputs

| Input | Exact revision | Responsibility |
| --- | --- | --- |
| Main, including #520 | `086f31e78240f8c70118c467406e89fdd89a92a2` | Accepted H1 application and source-reported cancer episodes |
| #518 | `d9d288079400b55eafb76526b14bc51098645635` | Laboratory citations and original-result inspection |
| #519 | `a643b16936afb7fa54ed7d755f8fd12e5ef56ef3` | Independently authorized laboratory history in Overview |
| #521 | `b7cd25bc769514f0e896f1aa578e6fe2b93e26d8` | Observation-specific unsaved wording and preparation cancellation |

The inputs are proposals until accepted. Their individual verification does not
qualify their combination. Keep source branches and their ownership intact.

## Approach

Preserve each frozen contribution through merge ancestry in an isolated branch.
Resolve common source fingerprints, components and browser steps by inspecting
both versions. Keep one question registry, source owner and citation ledger.
An alternative of reimplementing these features would duplicate active work;
merging the drafts separately would leave their combined behavior unqualified.

## Invariants and acceptance

- React/TypeScript/Vite and Python/FastAPI/PostgreSQL; no Next.js or new runtime dependency.
- Independently authored fictional records only; reported observations do not become clinical decisions.
- Text-source questions and laboratory questions retain their distinct typed anchors and read grants.
- An unchecked, denied, stale or wrong-case laboratory read is unknown, never a verified empty count.
- Editing or switching an observation cannot save a question or retain another observation's preparation receipt.
- Citation reads, explicit linking, retry and result inspection use current source and rights checks.
- An amendment preserves the old question, original result and citation identity while indicating reassessment.
- Existing cancer-episode metadata, text evidence/report/follow-up and recovery behavior remain intact.
- Verify the actual combined React/API/PostgreSQL/browser/restart/recovery behavior on one recorded revision.

Preserved report versions, laboratory reviewer dispositions, real biomedical
retrieval, hosted models, production identity/consent and clinical release remain
separate work. The current laboratory inspection is not a signed clinical report.
