# Longitudinal biological explanation surface

**Scope:** bounded vertical slice from the product vision (Notion page 01):
a case-level biological explanation surface, not a mutation list. Optional
extension only. It does not replace the existing architecture, does not
reorder the OI-001–018 roadmap, and does not select a backend, model, or
license. No second ledger, no parallel canonical state: explanations and
assay observations live in the same SQLite case store, keyed by the same
`case_id`, anchored to the same `source_versions` rows, and invalidated by
the same amendment path that marks snapshots stale.

**Comparison with the existing implementations.** The source model versions
immutable bytes per document and marks dependent snapshots stale when a
version is superseded; the evidence model versions immutable items and marks
only snapshots citing the exact version stale; biological assets are
immutable rows with separately attributed inventory assertions that go stale
anchor-exactly. Explanations and assay observations follow all three:
immutable core rows, one exact source-version anchor each, and anchor-exact
staleness on amendment. Competing hypotheses follow the snapshot rule that
creation never rewrites a sibling: a second explanation for one question is
a second row, never a supersession.

## Model

- `bio_explanations`: one human-authored row per hypothesis, bound to one
  case question. Context: `episode_id`, specimen (`recorded`/`unknown`),
  lesion (`recorded`/`unknown`), and a clinical time-point label
  (`known`/`unknown`, a short fictional label such as a time-point name —
  never a disease status). Unknown is stored state, never defaulted, and a
  value is rejected unless its state allows it.
- `bio_assay_observations`: one row per assay record under one explanation.
  Each cites at most one tissue block (`recorded`/`unknown`); a recorded
  block must be a same-case `ffpe_block` or `fresh_frozen_aliquot` sharing
  the explanation's episode, so assays from different blocks or tumors are
  never silently pooled. Slides, WSI views, and genomics pointers are
  derivatives and cannot silently stand in for a tissue block.
- Matched control is first-class: `recorded` (with a specimen ID),
  `missing` (explicitly identified as missing), or `unknown`. A missing or
  unknown control must not carry a specimen ID.
- Reference kind is an explicit required choice with no default:
  `patient_normal` (the patient's own normal tissue),
  `external_population` (an external reference population, not the patient),
  or `unknown`.
- Specimen confusion is rejected, not merged: a recorded explanation
  specimen or tissue-block specimen that contradicts the anchored source's
  specimen fails with an explicit error. A new specimen is a distinct
  context — a distinct document and explanation — never an amendment.
- Text guard: labels, mechanism outlines, method names, result notes, and
  time-point labels reject staging, grading, variant-interpretation,
  response/progression, eligibility, and treatment language. This is a
  narrow guard, not a classifier; a human author rewords the text and
  nothing is repaired. Nothing in this slice states a clinical meaning for
  a variant, a stage, a grade, or a response.

## Amendment behavior

On source amendment, only explanations and observations anchored to the
exact superseded version become `stale`; competing hypotheses on other
versions survive untouched, and all historic rows are preserved. A stale
explanation cannot grow new observations — propose a new explanation
instead — and a stale anchor cannot start new work. The `source_imported`
event and import result carry `invalidated_bio_explanations` and
`invalidated_bio_assay_observations` alongside the existing invalidation
lists; both are additive and change no existing key.

## HTTP and UI

- `POST /api/cases/<id>/bio-explanations` and
  `POST /api/cases/<id>/bio-explanations/<explanation-id>/assay-observations`;
  both are case-scoped and reject cross-case question, explanation, block,
  or source references. Both lists are included in
  `GET /api/cases/<id>/state`.
- The case view links to a Biological explanation panel that renders one
  card per explanation (competing hypotheses side by side), groups each
  explanation's observations under per-block headings while keeping every
  observation on its own card, and states specimen, lesion, time point,
  tissue block, matched-control, reference, anchor, and freshness in plain
  words with fictional labels. Authoring forms propose explanations and
  record observations; unfinished narratives block case switches instead of
  crossing cases. Authored and source text is rendered as text only, never
  as HTML.

## What is NOT proved

Browser rendering is not verified in this slice's session (no shell or
Chromium here); the repository workflow runs headless Chromium, and the
slice ships static UI contract tests. No clinical claim, variant
interpretation, staging, grading, response/progression inference,
treatment recommendation, or deployment readiness is made or enabled by
this extension. Reference-kind and control-state values are human-entered
demonstration labels, not verified laboratory facts.
