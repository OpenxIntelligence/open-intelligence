# Provisional file/module ownership map — repository main as of 2026-11-02
This is an ownership proposal, not proof of assignments. The current Sprint Board/lead assigns actual humans/agents. Do not fabricate a seven-agent team.

| Paths or contract | Primary accountable role | Change sensitivity | Coordination |
| --- | --- | --- | --- |
| PRODUCT_CONSTITUTION.md, AGENTS.md, CLAUDE.md, .agents/, docs/engineering/ | Lead + founder for policy | RED for authority changes | All agents read; explicit human review |
| .github/workflows/, CI, deploy, permissions, secrets policy | Infra/security lead | RED | Founder approves privilege or release changes |
| src/open_intelligence/store.py, persistent source/case/receipt/event contracts | Domain/persistence lead | AMBER; RED for destructive/identity | All consumers + migrations sequence |
| src/open_intelligence/patient_access.py and subject-binding logic | Identity/security lead | RED for any access/authorization semantics | Clinical/privacy review; cross-case tests |
| src/open_intelligence/rights.py, source-rights integration | Rights/data lead | RED for release/clearance changes | Exact use/version receipts |
| src/open_intelligence/investigation.py, discovery.py, mission.py, timeline.py, changes.py | Investigation/domain lead | AMBER | Preserve candidate vs reviewed vs executed distinctions |
| web/index.html, web/*.js, web/*.css | UX frontend lead | GREEN when isolated, AMBER if shared journeys | Review source-linked states, cross-case leakage, accessibility |
| tests/, validation/, examples/synthetic/, examples/patient-access/ | QA/evaluation lead for acceptance, module author for test implementation | AMBER for gold-baseline alterations | Independent evidence, never rewrite tests merely to pass |
| tools/research/, .github/workflows/public-research.yml, rna-analysis.yml, single-cell-analysis.yml | Research/evaluation lead | AMBER; RED for external data/egress/weights | Keep research output separate from patient facts |
| docs/safety-packet/, docs/BIOLOGICAL_ASSET_PROVENANCE.md | Rights/clinical safety reviewers | RED for changed safety claims or permissions | Cross-check existing rights/asset records |
| README.md, README_IMPLEMENTATION.md, docs/EXECUTION_BACKLOG.csv | Lead coordinator with relevant owner | AMBER | Update claims only after verified implementation |

One file may support multiple teams but has one integration reviewer. Planned future first-party domains (EHR, LIS, imaging, pathology, genomics, therapy, enterprise) require domain contract and accountable owner before assigning paths; do not create empty services to match a speculative folder tree.
