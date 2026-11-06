# Laboratory extraction evaluation and correction registry

This implements a bounded part of **OI-011** (extraction/model evaluation), using
the existing H1 FHIR laboratory parser. It also supports OI-018's separation of
source corrections from model improvement. It does not replace the canonical
patient, source, observation, review or evaluation protocol owners.

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
No real patient data, network call, trained model, deployment or clinical
validation is part of this increment. Text/PDF/OCR laboratory extraction and a
connected reviewer interface remain separate work.

Local focused checks: **38 tests passed**, zero skips, including 17 new registry
tests and 21 inherited parser/question-preflight checks. The executable practice
exercise passed, including restart and both planted defects. Initial verification
found read-only reopen changing SQLite header counters; initialization now avoids
rewriting an existing registry's PRAGMAs and the byte-preservation check passes.
Broader local laboratory discovery could not import four API test modules because
the local runtime lacks `fastapi`/`sqlalchemy`/`alembic`; it is not reported as a full API pass.
The new focused CI workflow checks its exact checkout, runs these tests and saves
a practice receipt. Full API/PostgreSQL/recovery acceptance remains separately
tracked by the existing H1 workflow. No parent green result qualifies this change.
