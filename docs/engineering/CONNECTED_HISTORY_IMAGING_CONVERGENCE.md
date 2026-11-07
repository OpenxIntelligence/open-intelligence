# Open Intelligence — Connected permissions, history and Imaging convergence

**Status:** construction candidate — not merged, deployed or clinically qualified.

## Goal

Retain #618's authorized historical World Model and durable patient-permission foundation while incorporating the verified #615 Imaging report chronology, the connected #610 study/series navigation and #608 Labs display on one immutable candidate. This is one shared React/FastAPI/PostgreSQL fictional-patient application, not competing data owners.

## Exact donor inputs and merge rule

- Authority/history owner: PR #618, `7f266e1c389c8a0a3d00111ba295ab0bc8186898`, tree `ad2a72201f10e8e65166baa7aa09c04580cd6a2c`. Its ancestry preserves #611/#612, #610/#608 and #602.
- Imaging chronology: PR #615, `588f58cb4d290e6da1efe3df819342af37197dbd`, tree `7bfaa004140da4a94511151b4170af5dd1973de0`.
- Imaging increment is exactly ten file paths relative to its verified parent #610 `a5ac62a25b924f0edb6f8b2a77886d7b8467d466`. Each of those paths is unchanged in #618 relative to that same parent. Therefore copy the ten exact Git blobs without rewriting or losing concurrent owner changes. Merge commit retains both donor parents.

## Preserved functional contracts

1. Persisted grant/revoke authority and patient-suspension/recovery maintain their original API and worker gates. Selection of a report does not grant patient, case, source or image permissions.
2. Historical as-received World Model remains separate from current context; Imaging chronology reads the currently authorized source-index projection only. A chronology item is *not* an authorization receipt, retrospective grant or clinical interpretation.
3. Original files and images remain source- and case-bound; historical reports do not automatically expose historical pixels, start network requests or infer disease progression.
4. Existing Labs filtering, study/series grouping, review, source receipts, task follow-through, background jobs and persistent fictional demo are retained without new stores.
5. Nothing is a real-patient clinical deployment or a replacement for qualified professional review.

## Acceptance gates

- Inspect the merged tree against both exact parents; prove the ten imported blobs match #615 and all other existing #618 blobs remain identical.
- Run locked dependency gates, complete React/TypeScript/Vite tests, production build, real PostgreSQL/FastAPI/Chromium walkthrough, historical replay, permission revocation and patient-switch tests, and persistent fictional demo on the **merge commit**.
- Run focused historical/source PostgreSQL and dump/restore/migration gates on the same head as needed. Donor passes alone do not qualify a newly combined candidate.
- Record exact commit and workflow run IDs, failures, skips and unresolved issues in the PR. No automatic merge or deployment.

## Remaining convergence and full-product construction

#617 independently develops a receipt-time source-membership API, and #616 develops semantic classifications; both modify shared source/registry routes and need a separate owner-conflict reconciliation rather than an arbitrary tree overlay. #619 strengthens Composer snapshot binding. Main has moved independently. Integrate each only with verified contracts, avoid duplicate canonical ledgers, and reconcile the complete accepted main before any merge decision.

The destination remains the complete human and veterinary oncology ecosystem: clinical records/encounters, diagnostic services, genomics, treatment management, research/biological modeling, trials, operations, evidence and provenance, interoperability, consent and audit, with scientific evaluation and safety gates.
