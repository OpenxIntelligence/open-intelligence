# IV-03 — Reproducibility and frozen-baseline procedure

Status: **procedure only, unadjudicated.** No independent reviewer has yet
run this procedure from a clean checkout, so no baseline result exists yet.
A passing unit test is not clinical validation, and synthetic performance
does not transfer to real records, real workflows, or real patients.

Scope: issue #22 (IV-01–03), backlog items OI-011 and OI-014, and the
evaluation protocol proposed in PR #18. This procedure defines how an
evaluation run is reproduced and what it is scored against. It does not
change the architecture, the stack, or any priority. The adjudication rules
it points to live in `ADJUDICATION.md`; the two documents are companions
and neither replaces the other.

## 1. Clean-checkout procedure (fail-closed)

Run from an empty directory. Any unrecorded modification voids the run
record — do not patch, edit, or "fix forward" inside a run.

```sh
mkdir oi-eval-clean && cd oi-eval-clean
git clone https://github.com/OpenxIntelligence/open-intelligence.git packet
cd packet
git checkout <PINNED_PACKET_COMMIT>
git rev-parse HEAD
# Must equal <PINNED_PACKET_COMMIT>. Record the output verbatim.
python3 --version
node --version
git status --porcelain
# Must be empty before proceeding. If not, stop: the checkout is not clean.
PYTHONPATH=src python3 -m unittest discover -s tests
node --check web/app.js
git status --porcelain
git diff --exit-code
# Must still be empty. Record both outputs.
```

Record in the run record (`run_record_template.json`): the pinned packet
commit, the `git rev-parse HEAD` output, the application commit under test
(for Arm C; see §3), Python and Node versions, every command run with its
exit code, and the `git status` output before and after. Then hash the
cutoff inputs and every output artifact with SHA-256 and store the hashes
in the run record.

Rules:

- If `git status --porcelain` is non-empty at the start or the end, the
  run is **VOID**. Do not score its outputs.
- Any deviation, local patch, or uncommitted file must be committed and
  pinned as a new commit, and the run restarted from step 1. Otherwise
  the run is void.
- The packet commit and the application commit are different values and
  must never be conflated: the packet commit identifies the frozen
  evaluation material; the application commit identifies the system under
  test. A reference to an inspected commit must not be mislabeled as the
  commit actually tested.
- `received_at` / import timestamps of the application are the real import
  timestamps. A packet's simulated receipt clock controls only the
  offline evaluation's knowledge cutoffs; the existence of a packaging
  tool must not be claimed as a historical-cutoff query feature of the
  application.

## 2. Frozen baseline: the ordinary case brief

The baseline the packet is scored against is the **ordinary case brief**:
a human-readable brief produced by manual source reading (Arm A, §3),
under the same cutoff and the same question wording as every other arm,
and frozen **before the evaluated system output is opened**. Opening an
Arm C output before freezing the brief invalidates that case.

### Fixed section structure

Every ordinary case brief has exactly these sections, in this order:

1. **Sources actually reporting** — which packet sources contain
   responsive facts at this cutoff, with source IDs, versions, and
   anchors.
2. **What remains unknown** — requested items with no source support at
   this cutoff, keeping untested, negative, pending, and indeterminate
   distinct. Never collapse "not tested" into "negative".
3. **Source versions and specimen identities** — version, issue date,
   receipt date, and specimen ID for each cited source; which version is
   current and which versions are superseded but preserved.
4. **What changed since the previous cutoff** — additions, corrections,
   amendments, and retractions; what needs re-review because of them.
5. **What cannot be concluded** — plausible but unsupported inferences
   explicitly withheld, including any efficacy, eligibility, urgency, or
   action inference the packet does not support.

### Freezing the brief

Save the brief as `baseline_<case>_<cutoff>.md`, record its SHA-256, the
timestamp, the author (anonymous reviewer ID), and the cutoff in the run
record, and do not edit it afterwards. A corrected brief is a new file
with a new hash and a note explaining the correction; the original stays
in the record.

### Scoring against the baseline

The evaluated arms are scored against the predeclared opportunities and
the frozen brief using `ADJUDICATION.md` — not against an ad-hoc reading
made after the outputs were seen. The baseline brief is the reference for
what a careful manual reader could conclude at the cutoff; it is not
clinical ground truth, and agreement with it is not clinical validation.

## 3. Three comparable arms

Equal information, equal task burden. All three arms receive identical
sources, identical question wording, identical cutoffs, and identical
burden recording. The packet's question set is fixed before the run; no
arm gets extra hints, extra sources, or a reworded question.

- **Arm A — Manual source reading.** The reviewer reads the cutoff
  sources directly and writes the ordinary case brief (§2). This arm
  produces the frozen baseline.
- **Arm B — Simple deterministic manifest / time sorting with links.**
  A simple script sorts the cutoff manifest by time and version and lists
  links to sources. No summarization, no inference, no model output. The
  reviewer then writes the brief from the sorted manifest. Record the
  script version (or `n/a` with a note if the sorting is done by hand
  from the manifest).
- **Arm C — The current source-investigation application.** Run the
  pinned application commit on the same cutoff inputs. The reviewer
  reviews and corrects the application output; corrections and their
  burden are recorded, not hidden.

Learning control: counterbalance arm order across reviewers and cases, or
use previously unseen cases across arms so no reviewer sees the same case
in two arms. Record the arm order and case assignment in every run
record. A reviewer who has seen a later cutoff early, or who reuses
knowledge from a prior full-case exposure, is prior-exposed for that case
(see `ADJUDICATION.md` §2) and is recused from primary scoring of it.

## 4. Burden ledger

Record minutes separately, per case and per arm, in these five buckets.
Use a timer during the run; never estimate retroactively and never
fabricate timing. Record 0 when a bucket does not apply. Missing timing
makes the run record incomplete.

| Bucket | Counts |
| --- | --- |
| Acquisition | Finding and fetching the cutoff sources |
| Preparation | Setup, install, input preparation |
| Correction | Fixing tool, script, or output errors |
| Review | Reading, verification, brief writing |
| Coordination | Handoffs, clarifications, logging |

Field names in `run_record_template.json` are the lowercase bucket names:
`acquisition`, `preparation`, `correction`, `review`, `coordination`,
plus `total`.

Include failed runs, timeouts, and abstentions as rows with their burden
and outcome — not only completed cases. Report burden as total per
case/arm with the denominator, the range across runs, and assessor time;
a burden improvement claim without a denominator and a range is not a
result.

## 5. Run record

One `run_record_template.json` record per case/arm run. Required fields:

- `evaluation_id`, `status` (`not_activated` until the §6 freeze items
  are complete), `packet_id`, `packet_commit`, `application_commit`
  (`null` for Arms A/B; script version recorded separately for Arm B),
  `case_id`, `cutoff`, `arm`, `arm_order`, `reviewer_id`,
  `prior_key_exposure`;
- `input_sha256`, `output_sha256`, `baseline_brief_sha256` (Arm A;
  `null` for other arms until the frozen brief hash is attached),
  `tool_versions` (Python, Node, packet tooling);
- `burden_minutes` with all five buckets plus `total`;
- `outcome_counts` (reported, unknown, corrected, abstained, timed-out,
  failed);
- `git_status_clean` (boolean plus the recorded output);
- `freeze` — the `ADJUDICATION.md` §5 freeze checklist, all items
  boolean, all `false` until actually completed;
- `thresholds` — all `null` until frozen prospectively; never filled in
  after results are seen;
- `results_observed` — `false` until scoring begins.

Attach checksums, logs, and the frozen baseline hash to the record. A
record with `results_observed: true` and null thresholds is not a
preregistered run; it is an unactivated template that was opened late,
and its results must be labeled as such.

## 6. Limitations (read before citing any result)

- Passing unit tests are **not clinical validation** and not evidence
  about real records.
- Synthetic performance **does not transfer** to real workflows, real
  patients, or real clinical documents.
- This packet is **unadjudicated** until an independent reviewer actually
  runs it from a clean checkout under `ADJUDICATION.md` and files a
  complete run record. Until then, every result claim must carry the
  label "unadjudicated procedure; no independent evaluation has happened".
- The entire repository must not be handed to a participant and then
  described as a blinded run. Participant distribution is cutoff inputs
  only; coordinator material (reference keys, full manifests, tests) is
  never participant material.
- No external evaluator is recruited, no study is activated, no contact
  is made, and no real patient record is involved by this procedure.

## 7. How this pairs with the runnable packet (PR #24)

PR #24 supplies the packet machinery this procedure reproduces: fictional
cases, hashed sources, receipts, cutoffs, and a cutoff-specific
participant-input generator. Where that packet is present, run this
procedure at each of its cutoffs, generate one cutoff-specific input per
run (never the whole packet), and freeze the application commit, packet
commit, command, tool versions, and output SHA-256 in the run record, as
its README directs. The paired-baseline paragraph in that README and the
arm definitions in §3 above describe the same three arms; this document
is the fuller procedure behind that paragraph: the fail-closed checkout
(§1), the fixed brief structure and freezing rule (§2), and the burden
ledger (§4). Where the packet is absent, this procedure still applies to
any packet satisfying issue #22.
