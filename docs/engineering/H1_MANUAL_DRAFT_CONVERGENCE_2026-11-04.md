# Manual passage drafts in the combined H1 workspace

This bounded OI-007/008/009/013 increment composes existing #445 draft retention
with #449 preparation and its inherited document/image/manual-report workspace.
It extends the existing RegistrySession and QuestionPassageClient owners.

## Pinned inputs and scope

- Combined base #449: `4f17b4aef58ca5614a4d48b9b904b6bc5c759442`,
  tree `af43c73123676e9f0b43af464911f008367b5a0d`.
- Draft donor #445: `474631eac8d67af8e537e6b307fedc74793d30ad`,
  donor base `d1ac30b0604d06df8fb47ef69046d893ffdc6cbd`.
- Preserve both parents when updating the existing #445 candidate. Retarget it
  onto #449 for a bounded review; do not create another overlapping candidate.
- Keep backend, published migrations, dependencies, grants and workflows
  byte-identical to #449. Preserve its preparation, image, A/B/A case-switch and
  uncertain-command browser assertions.

Unsent additions and removals retain only exact references and the inspected
context hash in session memory. Navigation and refresh must recheck current
context and each selection before displaying quotations. Changed context or
annotation withholds the draft until explicit resolution. Common authority
denial and patient/case reset clear it; temporary failures preserve references.
Explicit save transfers to existing immutable uncertain-command recovery.
Unsent selections are neither report inputs nor durable autosave.

## Composition decisions

Apply the six-file #445 delta, preserving newer #449 content. The tests-file
three-way merge conflicted at the append boundary because the donor base had
unrelated evidence-comparison tests. Preserve the entire current test file and
append only #445's 103 newly added lines. Do not import unrelated donor-base
tests or replace current evidence behavior.

Use #445's refresh-and-reauthorize behavior. Sibling #444's refresh-blocking
approach is an alternative, not an additional requirement for this composition.
Other sibling work is not implicitly incorporated or qualified.

## Verification checkpoint

- Tests first: all 505 current tests passed; 15 new cases failed for the missing
  draft interface/behavior. Conflict-marker syntax failures during composition
  are not counted as behavioral proof.
- After composition: 520 client tests passed; after the review repair below,
  533 client tests pass, zero failures/skips; TypeScript/Vite
  production build passes. The existing bundle-size advisory remains.
- Synthetic-data boundary audit and changed browser-helper syntax pass.
- Dependency-rights inspection passes: 13 controls, 18 installed packages,
  two absent optional packages explicitly uninspected.
- Initial composed head `5b2dfecae8c33eb8da822110fd7e3bb8bc65a9dc` passed
  hosted run 41829904361, including the actual PostgreSQL/FastAPI/Chromium journey.
  This result predates the additional refresh repair and is not final acceptance.

Independent review found one Important defect: the donor's unconditional manual
draft reset erased unsent references during same-case case-map, source and World
Model refresh. Thirteen new behavioral cases cover success, temporary failure,
403/404 denial, inactive mapping and old callback isolation; six retention cases
failed before repair. A same-case reset now invalidates old store callbacks while
retaining references for fresh checks. Authoritative denial or inactive mapping
clears them. Patient/session/case changes retain their clearing behavior. The
browser additionally reloads cases, sources, World Model and question history
before verifying both unsent passages and zero writes.

Review of the repair, hosted acceptance on the corrected head and retained
artifact inspection remain pending. Parent or superseded results do not qualify
this composition.

The final PR receipt must record the exact commit/tree, run and artifact identity,
review findings and remaining limitations. This checkpoint does not close the
full H1 milestone or establish clinical validation, deployment or a main merge.
