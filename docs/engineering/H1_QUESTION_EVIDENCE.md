# H1 canonical question → governed evidence metadata

## Bounded implementation plan — 3 November 2026

**Goal:** let an authorized person discover independently authored fictional
research-source metadata, inspect its exact version and rights state, and retain
a citation beside an existing H1 question. Citation identity verification does
not establish that a source supports a claim.

**Spec:** the founder's unified execution directive; existing OI-004/007/008/009/013,
[WS-06 #117](https://github.com/OpenxIntelligence/open-intelligence/issues/117),
and [#224's catalog/citation contract](https://github.com/OpenxIntelligence/open-intelligence/pull/224).
This is an integration increment, not another master architecture.

**Base:** published #293 `635f357048eb27e52e6ec5c3d7b6714215070127`, exact tree
`74c4a2ab65bf54a0908246199bb67c300ae2662b`. It preserves #287's canonical
source/question/review-return/brief workflow and durable follow-through.

**Architecture:** reuse #224's typed metadata and citation validation contracts,
with explicit stored scope and version checks; adapt persistence to the existing
H1 PostgreSQL transaction. Canonical sources, questions, identity, events,
review returns and tasks remain their current owners. The SQLite catalog is an
isolated reference fixture, never a second patient chart. No new dependency,
network fetch, provider, model, clinical authority, or content license is adopted.

## Tasks and acceptance

- [ ] Reproduce and fix the inherited catalog's scope, version-search and malformed
  rights-flag defects before reusing its pure contracts.
- [ ] Add immutable versioned metadata, append-only rights decisions and immutable
  question/citation links in the existing `investigation` schema. Preserve all
  prior migrations; reject incompatible pre-existing objects. The new migration
  follows `0009_question_followthrough`, without rewriting earlier revisions.
- [ ] Expose independently authorized metadata search, citation linking and history
  on the existing patient/question router. Prepare actual JSON under source and
  evidence locks; check grants and evidence rights before committing access events.
- [ ] Connect the saved-question UI. Show current/restricted/superseded and source
  reassessment states, clear obsolete results after context changes, and recover
  uncertain link writes with the same request key.
- [ ] Verify actual API persistence, wrong-patient/tenant denial, unknown/revoked
  rights, exact versions and metadata hashes, malformed input, concurrent retry,
  failed serialization/audit rollback, amendments, restart and backup/restore.
- [ ] Run inherited API/reference/client/build gates and a real built-browser
  journey, inspect the result, publish a draft for independent review, and update
  the existing GitHub/Notion/Drive receipts with exact evidence.

## Review focus

Metadata rights must permit both storage and display before searchable fields
leave the server. Search must not use an unauthorized title to reveal a matching
record. A valid identifier cannot grant authority or prove claim support. A
case-bound record must match its stored organization and case, even when a caller
supplies a different scope map. A version-specific result cannot borrow another
version's terms. Revocation hides previously visible metadata on the next read;
the immutable link identity/history remains inspectable under patient access.
An amendment preserves old links and flags their original question context stale.

## Current evidence and limits

The 334 tracked files of the base were compared to their published Git blobs;
the complete tree and published commit were reconstructed exactly. Baseline
client tests: 195 passed, zero skipped. The local executor contains PostgreSQL
16.15 binaries but cannot change to an unprivileged database account (`setresuid`
returns `Invalid argument`), so PostgreSQL acceptance must run on the existing
hosted disposable-database workflow. Local skipped cases are never counted as
database passes. No real-patient input or third-party clinical content is used.

This increment intentionally remains metadata discovery and citation linkage.
Clinical evidence appraisal, scientific/model execution, evidence-rich reports,
professional review, ordinary medical uploads and real identity/consent remain
separate integration and validation work. Existing #249/#250/#272 report and
clinical evidence owners are preserved for that next adapter.
