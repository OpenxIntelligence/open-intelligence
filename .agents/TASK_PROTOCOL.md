# Task ownership, coordination and handoff protocol

## Authoritative tracking
The existing Notion Sprint Board and Agent Playbook are currently the team's source of task ownership (see Team Dashboard). Do not move assignments to GitHub Projects or create a second backlog without a deliberate transition decision. GitHub Issues/PRs hold task ID links, code diffs, review and verification evidence. Because a Notion row read/update is not an atomic cross-agent lease, only the lead/coordinator may serialize claims when simultaneous agents work; a concurrent claim is BLOCKED until reconciled. Never assume GitHub issue assignment alone creates an atomic lock.

## Task record required before execution
Task ID and Notion link; objective, priority and acceptance; assigned agent/human reviewer; base commit; branch and worktree; exact expected paths; restricted paths; dependencies and linked PRs; contracts touched; data/safety/rights risk class; verified tests; user-facing change classification.

States: BACKLOG -> READY -> CLAIMED -> IN PROGRESS -> IN REVIEW -> TESTING -> MERGED -> DONE. Exceptions: BLOCKED, NEEDS COORDINATION, CANCELLED. DONE requires evidence of merge and acceptance; PR opened is not DONE. Task owner is one actor; related reviewers and helpers are explicitly named.

## Before code
1. Read live board entry and confirm assignment with coordinator.
2. Inspect git status, target branch HEAD, current open PRs and affected files.
3. Check branch/file overlap; record overlap even when on separate branches.
4. Freeze shared API/schema/types and migration sequence before parallel implementation.
5. Agree risk class, testing plan and owner for each shared interface.
6. Use a distinct worktree/clone, feature branch, temporary files, ports and test DB; never share a writable worktree.
7. For missing product decisions, record options and block only the dependent work. Do not invent approvals.

## Priority for current delivery
P0 = repeatable end-to-end synthetic demo + evidence; P1 = core dependency needed for demo; P2 = robustness and measured technical debt; P3 = optional research. Nov 4 hackathon freeze/submit dates are tracked in the existing Dashboard; they do not redefine the long-term full first-party product.

## Conflicts and communication
Record in the same task: scope, affected paths, owner conflict, alternatives, change request, decision owner and deadline. No informal agent message changes accepted contracts. Later duplicate claim stops; do not reset another branch. When blocked, retain evidence and create a linked dependency request.

## Completion
Use HANDOFF_TEMPLATE.md and the PR template. Never report tests as passing unless a check was actually executed; distinguish local test, CI status, synthetic scientific exercise and independent clinical validation.
