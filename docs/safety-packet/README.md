# Submission safety packet — Open Intelligence demo

For the demo on `main` (`46bb1db`). Read in this order:

1. `SBOM.md` — everything the demo ships (and what it deliberately does not).
2. `NOTICE.md` — fictional-data statement, no clinical claims, license undecided.
3. `DATA_RIGHTS.md` — data-rights note: fictional content, Crossref metadata-only.
4. `ASSET_CATALOG.md` — every demo asset and its origin.

Rules this packet follows:

- Every claim is verifiable from the repository itself, or it is marked
  UNVERIFIED. No license or clearance is invented.
- The packet covers `main` only. Unmerged pull requests are out of scope
  and must be folded in when they merge.
- The packet does not choose a project license, does not claim clinical
  approval, and does not clear arbitrary user-supplied text.
- The guard test `tests/test_safety_packet.py` re-checks the packet's
  load-bearing invariants (no package-manager files, only the two pinned
  CI actions, no external web resources, synthetic markers on all example
  files) on every test run.
