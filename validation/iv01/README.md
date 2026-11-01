# Open Intelligence — IV-01–03 synthetic evaluation practice packet

**Status: original AI-assisted engineering fixtures, not independently adjudicated clinical cases.** No external evaluation has happened. This supplements the existing architecture and [issue #22](https://github.com/OpenxIntelligence/open-intelligence/issues/22), OI-003/004/010/011 and the [proposed protocol in PR #18](https://github.com/OpenxIntelligence/open-intelligence/pull/18). It does not implement a new clinical product, replace architecture, select a provider, reorder the roadmap or authorize outreach.

## What is supplied

Two fictitious case identities, ten original source objects, eleven receipt events and three time cutoffs. Sources use the current `OI-SYNTHETIC-REPORT/1` and `OI-SYNTHETIC-EVIDENCE/1` text formats. Every source includes its UTF-8 bytes as JSON text and a SHA-256 checksum. `sources[].text.encode('utf-8')` recovers the original import bytes. All names, specimens, experiments and findings are fictitious; no studies, actual patient records, terminology datasets or restricted content are copied.

The challenges cover untested versus negative, indeterminate findings, order versus administration, old events received late, explicit source amendments, wrong-subject quarantine, a wrong-specimen attempted amendment, duplicate receipts, contradictory fictional evidence, and a no-urgency/no-action control. The texts intentionally remain artificial; they do not prove general clinical document extraction or clinical plausibility.

## No architectural changes

The new tool validates and packages evaluation inputs only. Existing CaseStore, source/version semantics, human review, evidence ledger and UI are not modified. The integration tests feed these original examples through the existing importer. No new runtime packages, downloaded models or external services are needed.

## Additional fail-closed source checks

The packet generator validates the exact UTF-8 hash and also requires one unambiguous ISO `Issued-At` date for each source. Every source issue date must be no later than its declared receipt date. Synthetic reports must declare a patient that exists among the fictional cases. A source addressed to a different *receipt target* remains an intentional wrong-case challenge, not automatically corrected. Synthetic evidence must carry exactly one `Rights: original-synthetic` header; ambiguous or restrictive declarations are rejected, even if the content hash has been recomputed.

These checks protect the integrity of this fictional practice manifest only. A rights header is **not** proof of copyright ownership, lawful AI training, actual patient consent, or suitability for clinical use. No production rights clearance, medical validity or PHI approval is implied.

## Coordinator and participant separation

`cases.json`, `coordinator_key.json`, this README, the protocol and tests are **coordinator/development material**. Generate only one cutoff-specific `inputs.json` for a participant. Do not hand participants the complete repository, source manifest, tests or answer key during a purported masked run. Only selected source bytes and receipt metadata enter `inputs.json`; later sources, later receipt IDs, future hashes and the coordinator key are omitted.

**Important limitation:** these are PUBLIC PRACTICE cases with a PUBLIC DESIGNER REFERENCE KEY. The packaging reduces accidental answer/future-data leakage; it is not a secrecy boundary. Do not call a result on this published set blinded, independent clinical validation, or held-out model performance. A genuine confirmatory exercise needs new unpublished cases, a separate qualified reference author/adjudicator, controlled distribution, conflict declarations and recorded prior-exposure checks. The assistant that authored the fixtures is not an independent clinical evaluator.

## Reproduce locally

From the repository root, using Python 3.10 or newer:

```sh
python tools/evaluation_packet.py
python -m unittest discover -s tests -p 'test_evaluation_packet.py' -v
PYTHONPATH=src python -m unittest discover -s tests -p 'test_iv01_store.py' -v
PYTHONPATH=src python -m unittest discover -s tests -v
python tools/evaluation_packet.py --cutoff T0 --output /tmp/oi-iv01-t0.json
python tools/evaluation_packet.py --cutoff T1 --output /tmp/oi-iv01-t1.json
python tools/evaluation_packet.py --cutoff T2 --output /tmp/oi-iv01-t2.json
```

Output creation is exclusive: an existing path fails rather than silently replacing a previously scored packet. Freeze the evaluated application commit, packet commit, command, Python/browser versions and output SHA-256 in the run record. `reference_code_commit` identifies the inspected baseline; it must not be mislabeled as the commit actually tested later. Application source `received_at` is the real import timestamp; the manifest receipt clock controls this offline evaluation's simulated knowledge cutoffs. Do not claim the app has a historical cutoff query feature because this packaging tool exists.

## Paired baselines and procedure

At each cutoff, provide identical original sources and question wording for: A, manual source reading; B, simple deterministic manifest/time sorting with links; C, the current source-investigation application. Keep the allowed information and task burden equal. Record acquisition, preparation, correction, review and coordination separately; capture failures and abstentions, not only completed cases. Counterbalance order or use different previously unseen cases across arms to control learning. A blinded evaluator may not see later cutoffs early or reuse knowledge from a prior full-case exposure.

`SCORING.md` defines claim-level denominators and severity. `protocol.json` is a preregistration-ready **template**, with empirical thresholds and evaluator assignments deliberately unset. A real evaluation cannot be considered preregistered or activated until those fields, governance, allowed inputs and independent reviewer sign-offs are complete. `results_template.csv` contains headers only; no fabricated observations or scores.

## Rights and limits

These are original AI-assisted fictional text and code contributions; no external content license was imported. This authorship declaration does not select the project's distribution license or clear Python/browser/CI distributions, trademarks, clinical use, or third-party services. The repository's existing license decision remains open. No real data, external contact, medical recommendation, confirmed eligibility, sampling/experimental work or clinical deployment is authorized. Keep existing rights, privacy and clinical approval gates.

## Acceptance

Engineering gate: exact hashes and references validate; all participant-cutoff and malformed-input tests pass; existing-importer replay preserves expected identity/missingness/amendment outcomes; no app code changes; CI evidence identifies its commit. Human gate: independent clinical/reference review, prespecified metrics/thresholds and authorized evaluation remain **not performed**.

## Evaluation declaration preflight (not authorization)

Run `python -m tools.evaluation_preflight` from the repository root. This read-only check reports `blocked` for the default public `not_activated` template, lists missing declarations, and emits SHA-256 fingerprints for protocol/manifest/blank CSV template. It intentionally does not mark a study clinically validated or legally permitted. To make incomplete declarations fail CI/automation, use `python -m tools.evaluation_preflight --require-complete` (exit 3 while incomplete; malformed inputs exit 2). A declaration-complete *fictional* protocol still reports `scoring_authorized: false` and `blinded_evaluation_established: false` because text fields are not external proof of independence, data rights, institutional permission, or prospective clinical review.

The validator rejects unknown protocol fields, duplicate JSON keys, non-finite or unfrozen thresholds, duplicate reviewer IDs, past results already inspected, nonzero engineering safety invariants, and a nonblank or modified results CSV template. It is a **preregistration structure check**, not the packet source-hash validator or the clinical reviewer. Run `python tools/evaluation_packet.py` separately to validate authored synthetic source bytes, rights declarations and receipt cutoffs. No person is contacted, score generated, real record accessed, or source file modified by the preflight.
