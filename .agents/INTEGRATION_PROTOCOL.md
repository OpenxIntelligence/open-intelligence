# Integration, contracts, migration, rollback and release protocol

## Branch model
Keep main stable and reviewable. Agents use short-lived worktree branches oi/<task-id>-<scope> or existing established branch naming; one task/PR owner. The live Notion Sprint Board decides assignment; GitHub PR is the code handoff. PR must include exact base, dependencies/stacking, risk class, overlapping paths and test evidence.

Currently multiple draft PRs are open, including #10, #48, #49, #51, #52, and #53 on Nov 2; #53 explicitly depends on #51. Inspect live status before any integration. Do not merge one stacked PR or combine schema versions simply because its individual checks pass. Rebase with consent and reverify the integrated diff. Do not force-reset or force-push somebody else's branch.

## Shared contracts
No UI/backend parallel implementation until source-of-truth request/response, errors, subject/case scoping, provenance/versions, authorization and persistence semantics are agreed in an issue/ADR. Current demo uses Python HTTP endpoints, not an adopted full-platform API framework. OpenAPI may be introduced only for a qualified HTTP contract. Interfaces must preserve unknown, failed, unauthorized, pending, superseded, and stale states.

One named schema/migration owner per bounded integration window. Record old/new schema and rollback/restore plan, data preservation, backfill checks, and cross-version compatibility. No synthetic demo need justifies destructive migration, data repair or change to real clinical data.

## PR/merge gate
- All acceptance tests of affected modules run and exact commands/commit IDs recorded.
- Existing synthetic unit/HTTP + browser journeys remain green. Workflow names are listed in audit; check exact current CI run status, not only a documented earlier success.
- Contract checks, cross-case isolation, wrong-subject, amendment/staleness, source provenance, rights/terms, and security checks run as relevant.
- No new unapproved external dependency, asset, egress destination or cloud spend.
- Documentation and backlog/status reflect observed current behavior.
- Independent human reviewer and product owner approval for RED changes; never self-merge.
- Use GitHub rulesets and least-privilege tokens to enforce this, not AGENTS.md alone.

## Release / rollback
Tag verified known-working candidate after checks, preserving commit + test artifacts. For a bad merge, identify exact introduced commits and effects, revert through a reviewed PR, re-run tests, and restore only from tested backups if data changed. Do not use blind conflict resolution or assume a failed irreversible migration can be fixed with git revert. Production release authority is external to this protocol and is not granted here.

## Validation rehearsal
On isolated test branches: claim one low-risk documentation/example task, create a PR, verify CI evidence and reviewer handoff, deliberately simulate overlapping planned paths and confirm NEEDS COORDINATION is recorded. Do not merge a demo conflict into main. Track ruleset/branch protection verification separately.
