# Semantic evidence across current and historical patient context

Construction continuation for #604 and OI-004/005/006/009/013/018. The complete
shared foundation, clinical/scientific domains and human/veterinary scope remain
under construction. This document is the resumable checkpoint for this bounded
integration, not a second roadmap.

## Preserved implementation and ownership

| Input | Exact source | Treatment |
| --- | --- | --- |
| Connected source semantics (#616) | `5d13ee4c52c4bcf84b448b0d766e12d98924665d` | Preserve the corrected draft as a merge parent; existing semantic contract, current API and UI retained |
| Persisted access, Labs/Imaging and historical patient context (#618, including #611/#612/#608/#610) | `7f266e1c389c8a0a3d00111ba295ab0bc8186898` | Primary integration parent; preserve its migration and authority owner |
| Composer snapshot binding (#619) | `a14c6be0c8537ade54f57556229bced0de12c3b4` | Reuse exactly its three changed paths; no claim that all intervening main changes are incorporated |

Main and donor branches are unchanged. Local merge conflicts in routes, endpoint
inventory, imports, World Model sections and client tests were reconciled by
retaining both behaviors. No new state owner, database table, migration,
permission action, dependency or model is added by this integration. The inherited
0029 patient-access migration remains authoritative; persisted enforcement is
still controlled by the existing server setting and credential ceiling.

## Connected behavior

The current semantic endpoint remains `world-model/semantics` with
`oi.source-semantics/1`. The new read-only
`world-model/history/semantics?received_through=<timestamp>` uses the existing
source-history owner and returns `oi.source-semantics-history/1` containing the
selected receipt cutoff, inclusive receipt-time basis, historical-only marker,
current-authority requirement and the source semantic packet.

A report received later cannot enter an earlier snapshot merely because its
clinical event date is older. After a source amendment, historical classifications
retain the original source version, digest, anchor and missing/pending reason;
the current view retains the amended classification. Both require current patient,
organization, actor, purpose and source-read authority. Response preparation and
encoding occur before the source owner's final authorization and audit commit.
A failed final recheck rolls back the prepared history/read events.

Journey displays separate current and historical evidence inspection panels.
The browser binds every semantic reference to its corresponding decoded model,
including the source fingerprint and microsecond-precise cutoff. Closing history,
refreshing current context, disconnecting or losing source access prevents a late
response from restoring the old view. Historical selection never becomes current
Composer context. The reused Composer decoder also binds selected observations
to the decoded current source snapshot, addressing #619's reported contract gap.

## Verification and evidence boundaries

Local checks on the integrated source:

- 820 client tests passed without failures or skips, including the 35 imported
  Composer-binding cases and current/history semantic contract and race checks.
- Locked TypeScript/Vite production build passed.
- Ten API contract tests, three pure semantic projection tests, five shared
  semantic-contract tests and 31 architecture-gate tests passed.
- API module ownership, synthetic-data boundary and whitespace checks passed.
- Frontend dependency rights passed for 18 installed packages; two excluded
  optional packages remain uninspected. Runtime dependencies and locks unchanged.
- Six actual PostgreSQL semantic tests are implemented but skip locally because
  PostgreSQL 16 is unavailable. The new focused hosted gate requires all nine
  semantic tests (three pure plus six database) to pass with zero skips before
  broader regressions. It includes real pg_dump/pg_restore into a disposable
  database and actual HTTP reads of current/historical semantics after restore.
- The actual React/FastAPI/PostgreSQL browser journey now asserts both semantic
  views before/after amendment, exact source identifiers and fingerprints,
  original missingness, mobile width, denial clearing and a synthetic screenshot.
  Chromium is unavailable locally; execution is required on the hosted runner.

Prior evidence is identified separately: #616's exact source passed hosted web,
UI-glance and durable-execution workflows. Its initial full API run executed 1,033 tests with one failure: the final
authority test expected "Source unavailable" while the existing permission owner
correctly returned 404 "Patient unavailable". The exact denial assertion is
corrected here; the failed run remains recorded. Those donor results do not
establish that this new combined tree passes. The associated draft PR carries the current exact-head runs
and any failures or repairs.

## Resume from this state

1. Verify the integration draft's exact commit and all hosted checks, especially
   the focused semantic database gate and the newly added real-browser assertions.
   Repair failures on this branch; preserve failed-run evidence.
2. Record passing/failing/skipped results and exact source links in the existing
   #604 work item and engineering records. Do not close #604 from this increment.
3. Extend the existing investigation/Composer run owner with one versioned,
   deterministic, source-bound calculation. Explicitly record input references,
   method identity, units, assumptions and output identity. The current worker
   supports only source-question-brief/1, so a new calculation requires its actual
   contract, persistence and execution path rather than an unconnected helper.
4. Add exact input-dependency invalidation and a reviewable task on amendment;
   preserve historical outputs and leave unrelated questions/cases untouched.
   Qualify restart/restore, permission revocation and browser review at the same head.

Source-history membership in #617 overlaps the richer #618 reconstruction owner;
its separate Records interface has not been imported here. Reconcile that view
through the same source owner if needed, without duplicating canonical state.
Clinical beliefs, reviewed interpretations, model execution, ontology mapping
edits, species-specific reasoning, full scientific viewers, treatment workflows
and production qualification remain unfinished. This branch is synthetic-only,
draft, unmerged and undeployed.
