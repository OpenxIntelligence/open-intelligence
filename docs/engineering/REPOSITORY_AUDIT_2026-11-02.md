# Open Intelligence multi-agent engineering audit — 2 November 2026
Scope: non-destructive remote GitHub/Notion/Drive inspection, not a full local security or runtime audit. Status: report for review; no clinical validation.

## Evidence inspected
- GitHub OpenxIntelligence/open-intelligence main commit 7626ec8bd91ea7451b042389cb6559339e9f332c at inspection; tree, README, README_IMPLEMENTATION, AGENTS, execution backlog and synthetic-tests workflow.
- Existing source: Python 3.11+/SQLite local synthetic case ledger in src/open_intelligence/; static web assets in web/; suites in tests/; synthetic sources in examples/; public research probes in tools/research/. No Next.js used in the inspected main tree.
- Six .github/workflows: crossref-metadata, public-research, rna-analysis, single-cell-analysis, synthetic-tests, ui-glance. Synthetic workflow compiles Python, validates JavaScript syntax, runs unit/HTTP and headless Chromium journeys. CI exists; required status check enforcement not demonstrated.
- 181 paths (files plus directories) at inspection. No root CODEOWNERS or pull-request template found on main. Existing root AGENTS.md already contains evidence-first, rights, historical architecture and synthetic-data instructions.
- Open PRs at inspection: #10, #48, #49, #51, #52, #53, all draft; #53 depends on #51. Earlier PR numbers may be merged/closed; inspect the current live list before release.
- Branch listing reported main protected=false. Direct branch-protection endpoint returned 403 to the GitHub app, so actual administrator ruleset configuration could not be inspected here; do not state that policy is enforced.
- Notion Team Dashboard states current owner/team process: Sprint Board as task truth, one task/owner/branch, independent PR verification, Nov 4 internal freeze, team of four. Agent Playbook is existing instruction record.
- Notion founder decisions on Nov 2 expand to first-party healthcare domains and prohibit Next.js for new work; strict commercially independent core licensing policy is accepted. Related architecture PR #49 remains unmerged; no stack migration should be inferred from these notes.

## Actual demonstrated boundaries
README states current code is synthetic-only local research/demonstration with no real identity, patient authorization, clinical inference or validated deployment. It cites last verified main 9bef888 (Oct 31); do not extrapolate that receipt to current main. No end-to-end test was executed in this remote audit. Code commits, local uncommitted state and shell isolation of external contributors cannot be evaluated through GitHub alone.

## Collision and delivery risks
1. Main currently reported unprotected; PR habit is not enforced permission control.
2. Several draft PRs and stacked patient-identity work could conflict with a new contract or policy change.
3. AGENTS.md is also touched by draft #49: integration must reconcile, not blindly overwrite.
4. Shared store, patient_access, source/provenance, web navigation, test fixtures and workflow YAML require explicit ownership.
5. Notion Sprint Board and GitHub Issues can diverge if both claim to own assignments; current board is authoritative until formally migrated.
6. Test workflow existence does not demonstrate mandatory checks, branch protection, secrets checks, CODEOWNERS verification, migration rehearsals or independent review.
7. The long-term full first-party mandate and Nov 4 hackathon demonstration are distinct schedules; the demo must not be mistaken for product completeness.
8. No production PHI authorization, clinical/regulatory gate, validated safety escalation or project distribution license has been established.

## Prioritized action / verification gate
- P0: review and merge policy instructions in correct order against #49; preserve all existing branches.
- P0: founder/admin verifies ruleset: block direct pushes/force pushes to main, require PR and successful named checks, require independent human review, prevent privileged agent bypass. Record screenshots or API proof; no claim until configured.
- P0: coordinator inventories all active PR files and dependencies; reserve shared areas and serialize identity/schema work. Resolve PR #51 -> #53 ordering and other overlaps before merge.
- P0: keep existing Notion Sprint Board as task owner source; attach GitHub PR links and enforce claim serialization by coordinator; no competing project board.
- P0: run current main unit/HTTP/Chromium test commands and record the exact commit, actions links, pass/fail results, including synthetic case isolation.
- P1: add PR/Issue templates and CODEOWNERS only after a real independent eligible human reviewer is identified. CODEOWNERS cannot restrict edits or guarantee an independent reviewer alone.
- P1: trial two isolated parallel worktrees on separate low-risk tasks and deliberately test the overlap escalation path.
- P1: preserve known-good tag and test migration recovery (on synthetic throwaway data); never assume git revert restores a migrated DB.
- P2: consider automated path-ownership/contract drift checks and license/secret scanning after baseline verification; avoid brittle new CI gates just before freeze.

## Exit criteria for declaring operating system operational
Evidence of actual branch/ruleset enforcement, reviewer identity, verified current CI checks, task claim/handoff rehearsal, testable path-collision detection, documented API/schema owner, and rollback rehearsal. These are not satisfied by this documentation PR alone.
