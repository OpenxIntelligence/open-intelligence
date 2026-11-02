# Submission safety packet — Open Intelligence demo

For the current tree on branch `oi/safety-packet` (current `main`
merged in; refreshed 2026-11-02). Read in this order:

1. `SBOM.md` — everything the demo ships (and what it deliberately does not).
2. `NOTICE.md` — fictional-data statement, no clinical claims, license undecided.
3. `DATA_RIGHTS.md` — data-rights note: fictional content, Crossref metadata-only, bounded model path.
4. `ASSET_CATALOG.md` — every demo asset and its origin.

Covered surfaces: the timeline projection and route, the clinician
glance, the Patient Mission panel and route, the incoming board and
patient view, the investigation panel (including the bounded
model-assisted investigation with offline replay), the What Changed
panel and route, the discovery-rights linkage, and the reviewed
option/dependency view. `SBOM.md` maps each surface to its module,
routes, store tables, and UI panel.

Rules this packet follows:

- Every claim is verifiable from the repository itself, or it is marked
  UNVERIFIED. No license or clearance is invented.
- The packet covers the current tree on this branch only. Later merges
  must be folded in before the packet is used for a submission.
- The packet does not choose a project license, does not claim clinical
  approval, and does not clear arbitrary user-supplied text.
- The packet certifies the current tree only; it does not approve a
  vendor, dependency, product pivot, or clinical function.
- The guard test `tests/test_safety_packet.py` re-checks the packet's
  load-bearing invariants (no package-manager files, only the three
  pinned CI actions, no externally fetched web resources, synthetic
  markers on all example files in both example directories) on every
  test run.
- This refresh was produced by reading files only; no test suite or
  `git` command was run to verify it (see `SBOM.md`). Re-run the
  suite before submission.
