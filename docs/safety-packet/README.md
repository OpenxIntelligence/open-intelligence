# Submission safety packet — Open Intelligence demo

For the current tree on `main` (HEAD `4b13bc2`; refreshed 2026-11-05).
This refold supersedes the 2026-11-02 revision, which described the
pre-submission tree on the `oi/safety-packet` branch. The packet now
lives on `main` itself; there is no separate packet branch. Read in
this order:

1. `SBOM.md` — everything the demo ships (and what it deliberately does not).
2. `NOTICE.md` — fictional-data statement, no clinical claims, license undecided.
3. `DATA_RIGHTS.md` — data-rights note: fictional content, Crossref metadata-only, bounded model path.
4. `ASSET_CATALOG.md` — every demo asset and its origin.

## Product scope

Open Intelligence is a general, patient-centered intelligence
platform. Cancer bioinformatics is its starting domain, not its
definition: nothing in this packet limits the platform to oncology,
and no claim here depends on an oncology-specific function. Every
patient case, source, finding, and investigation in the demo is
independently authored fictional content (see `NOTICE.md`).

## Covered surfaces

The timeline projection and route, the clinician glance, the Patient
Mission panel and route, the incoming board and patient view, the
investigation panel (including the bounded model-assisted
investigation with offline replay), the What Changed panel and route,
the discovery-rights linkage, and the reviewed option/dependency
view — plus everything added since the 2026-11-02 revision: visits
and amendments, consents, the clinician overview, patient goals,
notes and attention, follow-through tasks, second-opinion requests,
survivorship plans, workspace questions, biological explanations,
evidence quality, document intake and preview (including the optional
bounded PDF text-extraction runtime), the packet export, the
bibliography panel, synthetic metrics, the review queue and receipts,
scoped review, and re-review tasks. `SBOM.md` maps each surface to
its module, routes, store tables, and UI panel.

Auth state on `main`: the demo still runs behind the B-01
fictional-actor gate (`X-Fictional-Actor` header, deny-by-default,
seeded demo actor, `actor_grants` + `access_log` tables). There are
no real accounts, roles, or sessions on `main` yet. Real accounts,
roles, and sessions are pending in PR #515 (readied for merge on
green; the demo-credential, registration, roles/patient-binding,
header-retirement, session, access-log-UI, and vanilla-only decisions
were confirmed by the user on 2026-11-05). The `access_log` table
exists on `main` but has no HTTP route or UI there — that arrives
with #515.

## Rules this packet follows

- Every claim is verifiable from the repository itself, or it is marked
  UNVERIFIED. No license or clearance is invented.
- The packet covers the current tree on `main` only. Later merges
  must be folded in before the packet is used for a submission.
- The packet does not choose a project license, does not claim clinical
  approval, and does not clear arbitrary user-supplied text.
- The packet certifies the current tree only; it does not approve a
  vendor, dependency, product pivot, or clinical function.
- The guard test `tests/test_safety_packet.py` re-checks the packet's
  load-bearing invariants (no package-manager files at the repository
  root, only the five pinned CI actions, no externally fetched web
  resources, synthetic markers on all example files in both example
  directories) on every test run. The case-switch guard test
  `tests/test_case_switch_guards.py` re-checks that case-scoped
  narrative inputs are guarded and cleared on case switch.
- This refresh was produced by reading files, running the full vanilla
  test suite on the refold base (`main` `4b13bc2`: 772 tests, 17
  failures, all pre-existing `test_pdf_intake` failures from the
  missing local `pypdf`, zero other failures), and running `git`
  commands to measure what changed since 2026-11-02. The suite run
  is recorded in `SBOM.md`.
