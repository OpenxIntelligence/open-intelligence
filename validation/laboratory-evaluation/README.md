# Laboratory extraction evaluation and correction registry

This implements a bounded part of **OI-011** (extraction/model evaluation), using
the existing H1 FHIR laboratory parser. It also supports OI-018's separation of
source corrections from model improvement. It does not replace the canonical
patient, source, observation, review or evaluation protocol owners.

## Experiment execution extension — 6 November 2026

The same registry now persists recipes, frozen experiment plans, unique start
claims, candidate outcomes, model artifacts/checkpoints and final selection
receipts. No new database schema or parallel source owner is introduced.

| Component | Executable now | Still absent |
| --- | --- | --- |
| AutoResearch foundation | Freeze a finite candidate list; fit/run allowed local adapters under budgets; evaluate validation outputs; select by a frozen objective; record failures and results | LLM post-training, adaptive recipe generation, synthetic-data generation, GPU/provider orchestration, general hyperparameter or mixture search |
| Fine-tuning ontology foundation | Existing datasets/reviews plus recipes, input/code hashes, experiment lineage, checkpoint artifacts, timing/resource measurements and selection receipts | Neural weight registry, deployment lifecycle, live operational feedback, production reviewer UI |

The two adapters are the **existing deterministic parser** and an **exact-source
memorization control**. The latter fits a lookup table from explicitly eligible,
reviewed train examples and abstains on every unseen source hash. It is an
intentional leakage/generalization control, not an LLM, gradient training,
learned medical interpretation, or an accuracy improvement. Its persisted
checkpoint contains the fitted table and the exact training-input fingerprint.
The parser checkpoint records its source identity, not invented model weights.

Run the real two-candidate exercise with a fresh file:

```bash
PYTHONPATH=apps/api/src:src python apps/api/tools/verify_laboratory_experiments.py \
  --registry /tmp/oi-laboratory-experiments.sqlite
```

This authors dataset version 2 with one explicitly eligible fictional training
example; version 1 remains unchanged. Only train/validation fixture reviews are
recorded. The worker receives eligible train examples and validation inputs, never
test cases or validation references. The parent coordinator reads the frozen
manifest/reference records; this is not a blinded study or a file-access sandbox.
The existing scorer now supports explicitly selected evaluation splits, preserving
historical all-split run/retry shapes. Excluded test cases are not scored as
abstentions or silently included in a denominator.

Observed practice outcome: the memorizer fits one example, abstains on the one
validation case (11 omitted field opportunities), and the parser has zero field
errors. The frozen validation objective selects the parser. That is useful evidence
that fitting this control does not improve this structured task, not evidence
against other trained models or an estimate of clinical accuracy.

Each built-in worker has a 5 CPU-second and 256 MiB address-space limit. Plans
allow at most eight candidates, 100 training examples, 10 wall seconds per worker
and 60 wall seconds for the experiment's worker-launch budget. Each worker's
timeout is capped by the remaining total budget. Parent bookkeeping may add
overhead after worker termination. The receipt reports actual elapsed time,
child CPU time and peak resident memory; external service charges are zero for
these local adapters, while total cost is **unknown**, not asserted free.

Duplicate/concurrent execution cannot launch a second copy of a claimed plan.
Completed retries return the original receipt without rerunning. A parent-process
crash remains `interrupted_or_running`; no automatic takeover or fabricated
completion occurs. Inspect it and use a new explicit experiment ID after resolving
the prior process. Checkpoint-based mid-training resume is not implemented.
Worker errors, timeouts and exhausted budgets remain visible; they cannot be
selected as successful candidates. An entirely unassessable validation set cannot
select a candidate. Selection never grants deployment/clinical approval.

The command interface is:

```text
python -m oi_api.laboratory_experiments --registry <path> recipe --input <recipe.json>
python -m oi_api.laboratory_experiments --registry <path> plan --input <plan.json>
python -m oi_api.laboratory_experiments --registry <path> execute --experiment <id>
python -m oi_api.laboratory_experiments --registry <path> inspect --experiment <id>
```

The executable verification script supplies complete recipe and plan examples.
Unsupported techniques, remote models, arbitrary commands and hyperparameters
are rejected rather than presented as implemented integrations. No third-party
model weights or new dependency are introduced. This extension is verified by
14 new execution/isolation/budget/recovery tests and the original 38 checks;
the updated hosted workflow executes both practice exercises on its exact head.

## Implemented behavior

- Freeze a versioned, hash-bound dataset containing the original fictional FHIR
  bytes, source identity/version, patient reference and explicit split.
- Keep a patient, source family and source hash in one split across every dataset
  version/name in a registry. Source versions cannot acquire different contents;
  duplicate sources cannot inflate one dataset's denominator.
- Record every case's original output, including explicit errors and abstentions.
  A supplied output file is never claimed to be verified model execution.
- Execute the existing deterministic parser as a baseline. Its source-file hash
  is captured. The supplied Git revision is a declaration, not repository proof;
  the hosted workflow separately verifies its checked-out revision.
- Store one immutable, output-hash-bound review per run/case. Corrections preserve
  original outputs and source identity. Review anchor checks read the frozen FHIR
  original directly, so an extractor omission cannot define the reference.
- Compare a candidate with an explicitly selected reviewed reference run. Persist
  scores with candidate, reference and dataset hashes. Report each split's case
  count, assessed/unassessable counts, field denominator/errors, omissions,
  unsupported observations, abstentions and execution errors.
- Export examples only from explicitly eligible, reviewed **train** cases. Every
  supplied fixture defaults to training-ineligible. This command prepares examples;
  it does not train or authorize training.

The local SQLite file is an **offline experiment artifact**, not a second patient
database or a change to the H1 PostgreSQL stack. The tool refuses unrelated
SQLite databases. Transactions serialize split assignment and roll back failed
freezes; immutable rows reject update/delete and changed same-ID retries. Exact
retries are idempotent. Reopening preserves original outputs, reviews and scores.
No API route, schema migration, product UI or application patient record changes.

## Run the complete practice exercise

From repository root, choose a new disposable file:

```bash
PYTHONPATH=apps/api/src:src python apps/api/tools/verify_laboratory_evaluation.py \
  --registry /tmp/oi-laboratory-practice.sqlite
```

The exercise freezes `dataset.json`, executes the actual parser, records
**scripted fixture reviews** from separately authored `reference.json`, scores
the baseline, plants a wrong unit and an omission, verifies their detection,
checks that no training examples are eligible, and reopens the registry to prove
recovery. No human review is claimed. Its JSON receipt identifies that distinction.

The four public cases cover decimal precision, explicit absence, zero and a
second source version. Two versions of the same fictional patient remain in the
test split. All four match the authored reference (44 field opportunities).
This is a small engineering counterexample suite, not an accuracy estimate.

## Individual commands

Set `PYTHONPATH=apps/api/src:src` and invoke:

```text
python -m oi_api.laboratory_evaluation --registry <path> freeze --input <manifest.json>
python -m oi_api.laboratory_evaluation --registry <path> baseline --dataset laboratory-practice:1 --run <id> --software-commit <40-character-sha>
python -m oi_api.laboratory_evaluation --registry <path> show-run --run <id>
python -m oi_api.laboratory_evaluation --registry <path> record --input <candidate.json>
python -m oi_api.laboratory_evaluation --registry <path> review --input <review.json>
python -m oi_api.laboratory_evaluation --registry <path> score --candidate <id> --reference <reviewed-run-id>
python -m oi_api.laboratory_evaluation --registry <path> training-examples --reference <reviewed-run-id>
```

`record` requires `run_id`, `dataset`, `system` and `outputs`. System metadata is
`system_id`, `system_version`, `software_commit`; outputs have exactly one entry
per dataset case, each with `status`, `observations`, `reason`. Status is
`extracted`, `abstained` or `error`. Missing cases must be explicit failures;
they cannot disappear from the denominator. Observation fields are defined in
the module's `FIELDS` tuple plus `reference`, and illustrated in `reference.json`.

`review` requires `run_id`, `case_id`, `reviewer_id`, `independence_declared`,
`decision`, `output_sha256`, `corrected_observations`, `reason`, and
`correction_seconds`. Decisions are `accept`, `correct`, `unassessable`. Only a
correction carries replacement rows; both accept/correct must cover every source
observation. The review hash must match the exact original output. Reference
correction seconds are self-reported reference preparation effort, not measured
candidate workflow burden. Later adjudication needs a new explicitly selected
reference run; this version does not implement a multi-reviewer adjudication UI.

## Boundaries and verification

This public practice set is not blinded, representative or independently
adjudicated. Repeated test scoring is permitted and does not establish an unseen
final evaluation. The existing [evaluation packet](../../docs/evaluation/PACKET_TEMPLATE.md)
and [IV-01 protocol](../iv01/README.md) retain their separate approval/reference
requirements. The scorer defines no clinical pass threshold or model promotion.

Synthetic provenance, reviewer identity/independence and training eligibility
are declarations, not verified permissions or a personal-data detector. Local
file administrators are trusted; hashes and SQLite triggers are not an access
control or tamper-proof audit service. Split isolation applies within one registry
to declared identities, not aliases across separate registries or institutions.
No real patient data, network call, neural model weights, deployment or clinical
validation is part of this increment. Text/PDF/OCR laboratory extraction and a
connected reviewer interface remain separate work.

Initial registry local focused checks: **38 tests passed**, zero skips, including 17 new registry
tests and 21 inherited parser/question-preflight checks. The executable practice
exercise passed, including restart and both planted defects. Initial verification
found read-only reopen changing SQLite header counters; initialization now avoids
rewriting an existing registry's PRAGMAs and the byte-preservation check passes.
Broader local laboratory discovery could not import four API test modules because
the local runtime lacks `fastapi`/`sqlalchemy`/`alembic`; it is not reported as a full API pass.
The new focused CI workflow checks its exact checkout, runs these tests and saves
a practice receipt. Full API/PostgreSQL/recovery acceptance remains separately
tracked by the existing H1 workflow. No parent green result qualifies this change.

The first focused hosted run at `21efe2f` passed the 25 registry/parser tests but
could not import the 13 inherited question-preflight tests without Pydantic.
The workflow now prepares and verifies the existing hash-locked H1 runtime,
including its reviewed code-only pydicom build, before running the same complete
38-check selection. No assertion, test or dependency-rights check was removed.
