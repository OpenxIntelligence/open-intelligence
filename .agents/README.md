# Engineering-agent operating system — proposed
Read root AGENTS.md, PRODUCT_CONSTITUTION.md, README.md, docs/FIRST_PRINCIPLES_PLAN.md, relevant Notion accepted decisions, the current task, and the files you will change. These complement existing instructions; none overrules founder decisions.

## Documentation map
- TASK_PROTOCOL.md — assignment, dependencies and handoffs.
- OWNERSHIP_MATRIX.md — ownership by actual repository paths, provisional until assigned.
- INTEGRATION_PROTOCOL.md — branch/PR/contract/migration/rollback coordination.
- SECURITY_AND_CLINICAL_GATES.md — patient, clinical, rights, provenance and release controls.
- HANDOFF_TEMPLATE.md — evidence-based completion and blocker format.
- docs/engineering/REPOSITORY_AUDIT_2026-11-02.md — inspected starting state, gaps and next validation.

## Engineering roles versus clinical agents
These are coding-team responsibilities; do not confuse with horizontal/vertical clinical intelligence components inside the eventual product. Roles are assigned to actual people or permitted coding agents through the existing Sprint Board, not instantiated by a file. Start with lead/coordinator + one implementation owner + independent QA/reviewer; expand after one safe parallel integration rehearsal.

## Agent read order
1. Human founder-accepted scope and specific decision request.
2. Current working copy of root AGENTS.md and this constitution.
3. Merged engineering contracts and accepted ADRs.
4. Current Notion Sprint Board assignment + linked GitHub Issue/PR.
5. Actual code/tests and latest target branch state.
6. Research and proposed architecture extensions, labeled as proposals.

When layers disagree, stop only the affected change, retain unrelated authorized work, record the discrepancy, and escalate.
