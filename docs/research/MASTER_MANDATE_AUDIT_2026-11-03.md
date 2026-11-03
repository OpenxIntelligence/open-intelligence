# Open Intelligence — bounded mandate audit and implementation receipt

**Inspection date:** 3 November 2026. **Classification:** current-truth audit,
supporting research and implemented correction; not a replacement architecture,
full-platform audit, release clearance or clinical validation.

## 1. Product and authority

The first useful product connects patient information, original sources,
longitudinal assertions, permitted evidence, investigation, sourced reports,
human review, authorized follow-through and reassessment. The patient remains
the organizing center across care settings. The complete first-party clinical
platform remains the long-term direction.

The supplied master mandate agrees with the current [architecture precedence](https://app.notion.com/p/40a3866f77ef8154bf15c7bb53138c9f)
and [accepted decisions](https://app.notion.com/p/40a3866f77ef81e08a12fd4921e19629):
preserve useful implementations and one patient/source/evidence identity;
Python/FastAPI/PostgreSQL plus React/Vite/TypeScript is the accepted H1 baseline;
no new Next.js; independently invented patients; permissive adoption policy;
human clinical authority; distinct implementation, integration, merge and
deployment states. The older main planning text still describes stack choices
as undecided. That historical wording does not override the accepted H1 decision.

No specific buyer, pilot jurisdiction, clinical authority or real-data permission
was inferred. No named person's medical records or biological profile were
downloaded, reconstructed or used as fixtures. No other product was connected.

## 2. Repository and project-record truth

GitHub metadata and remote HEAD identify default branch `main` at
`24519839aa8ac1ea3aff88a956349ba72798a72a`. The inspected main is the stdlib/SQLite
prototype. The accepted H1 implementation exists in unmerged drafts. A bounded
inventory returned **237 open PRs**; this is a dated observation, not a measure
of product completeness. This contribution uses a separate branch from main
and preserves other worktrees and PRs.

The canonical Notion precedence/decisions/engineering pages and the existing
[Drive engineering record](https://docs.google.com/document/d/1Zbn-8Z5fABdGrJa5W0kSh4ojSVFvd1ddXdvW6pHr9gA/edit)
were read. Branch claims were checked against GitHub. No parallel master roadmap
is created by this receipt.

### Historical references independently checked

All six requested PRs below are **open, draft, unmerged**. Source and tests were
inspected, and head-associated hosted workflow results were retrieved. Their
deployment and clinical-validation states are not established.

| PR / capability | Exact head | Source / test owner | Hosted result observed |
|---|---|---|---|
| [#56 LIS](https://github.com/OpenxIntelligence/open-intelligence/pull/56) | `08eafc5fc4d606c9c47913d0e8e45641338489aa` | `clinical_lab.py` / `test_clinical_lab_operations.py` | Three successful runs; [ledger](https://github.com/OpenxIntelligence/open-intelligence/actions/runs/41482472060) |
| [#70 events](https://github.com/OpenxIntelligence/open-intelligence/pull/70) | `b1b99b3095b33b8cd7352793c94990b852ea88f9` | `platform_events.py` / `test_platform_events.py` | Three successful runs; [ledger](https://github.com/OpenxIntelligence/open-intelligence/actions/runs/41493529854) |
| [#74 EHR](https://github.com/OpenxIntelligence/open-intelligence/pull/74) | `a1ce73e4bfa0eabee15e378968c424229a96cb02` | `clinical_encounters.py` / `test_clinical_encounters.py` | Three successful runs; [ledger](https://github.com/OpenxIntelligence/open-intelligence/actions/runs/41489395344) |
| [#85 registry](https://github.com/OpenxIntelligence/open-intelligence/pull/85) | `3326774b99e819d07ed555a6e505c24dfc699320` | `patient_registry.py` / `test_patient_registry.py` | Three successful runs; [ledger](https://github.com/OpenxIntelligence/open-intelligence/actions/runs/41494256338) |
| [#89 initial composition](https://github.com/OpenxIntelligence/open-intelligence/pull/89) | `7125aca84ebf38820482e8640e7a1479bcc0f429` | `clinical_event_host.py` / `test_patient_ehr_event_integration.py` | Integration/UI success; [integration](https://github.com/OpenxIntelligence/open-intelligence/actions/runs/41499730427) |
| [#93 rights context](https://github.com/OpenxIntelligence/open-intelligence/pull/93) | `aa6d3f21b8d36d9949b66ed13ed34f76dabbd875` | `knowledge_context.py` / `test_knowledge_context.py` | Three successful runs; [ledger](https://github.com/OpenxIntelligence/open-intelligence/actions/runs/41501875440) |

Paths are relative to `src/open_intelligence/` and `tests/`. Original issues
[#87](https://github.com/OpenxIntelligence/open-intelligence/issues/87) and
[#92](https://github.com/OpenxIntelligence/open-intelligence/issues/92) remain open
and unassigned. Separate successful PR checks do not prove a composed workflow.

### Current integration owners

| Path | Existing implementation and exact revision | Remaining seam |
|---|---|---|
| Registry → EHR → orders/specimens/QC/results → source/event | #95 `233ac3da6c191651708ebcd8b1ca92304a3839ca`; `platform_integration.py`, `clinical_lab_bridge.py`, `clinical_source_provenance.py`, `clinical_continuity.py` | Preserve `CanonicalEHRHost`; no additional patient ledger or clinical host. Production identity and cross-store consistency remain open. |
| Clinical sources → authorized Composer | #130 `c1d1aea5fe5ec2b1f80f6d10558ab1bc07acff3e`; current-main reconciliation #152 `d052700a0af8e9f031cc9988686220e20dd84058` | Source-bound read-only preflight exists; not live model execution or clinical authority. |
| Canonical registry and EHR on PostgreSQL | #148 `19b1c1319ba543fd0e93744ea3425bd861b0f233`; #301 `aa9f4c4b1fc4b76c1955aa6b6b31820a46ab5e32` | Reuse `PostgresClinicalEncounters(ClinicalEncounters)` and reconcile parallel #297. PG LIS/outbox/H1 composition remains unfinished. |
| H1 sources → questions → citations → authored evidence → reports/tasks | #307 `c35219dc5eb244874a7df6e9bf00cfbfda18251f`; `apps/api/src/oi_api/{question_evidence,authored_evidence,evidence_report,question_followthrough}.py` | Real permitted metadata/content and qualified appraisal are separate. The H1 catalog intentionally permits only fictional records. |
| Images/questions/tasks/citations | #313 `f6132e894a21a326f72660c3399499ccbf251831` | Archive/report/source-reading convergence already has owners #312/#307/#314/#318; preserve them. |

#307's exact delivery head completed API, React and UI checks, including
[API/recovery run 41661507705](https://github.com/OpenxIntelligence/open-intelligence/actions/runs/41661507705).
#301's [PG run](https://github.com/OpenxIntelligence/open-intelligence/actions/runs/41641322902)
logs show 44 tests passing on each of PG17.11 and PG18.6; its inherited
[single-cell workflow failed](https://github.com/OpenxIntelligence/open-intelligence/actions/runs/41641314183).
#313's API run was still in progress at inspection, although React succeeded.
These are retrieved CI observations; this audit did not repeat their databases,
artifact checks or clinical evaluation.

## 3. Patient workflow findings

General patient-support sources were checked, without acquiring personal cases.
[NCI's finding-care guidance](https://www.cancer.gov/about-cancer/managing-care/finding-cancer-care)
connects second opinions with arranging access to records and results.
[ACS navigation guidance](https://www.cancer.org/cancer/patient-navigation.html)
describes practical barriers, including transport, communication and financial
navigation. Neither source proves that this product reduces those burdens.

**Product interpretation:** preserve exact source/version handoff, named next-step
ownership, missing-record status and continuity through provider changes.
Scientific discovery alone does not complete patient support. Validate total
patient/caregiver/navigator effort, comprehension and unresolved handoffs in a
later authorized study. Broader pediatric, hematologic, low-resource, recurrent
and negative-outcome narrative coverage remains incomplete; this pass does not
claim a representative patient-journey atlas.

## 4. Technology and research coverage matrix

No package, model, asset or service was newly adopted. The changed connector uses
the Python standard library; local runtime is **Python 3.12.14**. Existing H1
locks inspected in #307 include FastAPI 0.162.0, Pydantic 2.14.1, SQLAlchemy
2.0.55, Alembic 1.20.1, uvicorn 0.54.0 and pg8000 1.31.6. This inventory is **not**
a fresh full transitive/license/security audit or product release approval.

| Area | This pass | Decision / next evidence |
|---|---|---|
| API/persistence/domain composition | Main and named H1/clinical branches inspected | EXTEND existing owners; reconcile PG clinical and H1 contracts |
| Frontend/UX | Existing React/source-reading owners identified; no UI redesign | EXTEND task/source/question continuity; independent usability work pending |
| Literature connector | Existing Crossref parser reproduced and repaired; #159 Europe PMC owner found | EXTEND Crossref; retain Europe PMC owner, no duplicate connector |
| Rights/provenance | Existing broker and fictional catalog boundaries inspected; primary source terms checked | Preserve operation-specific rights; do not infer content rights from a DOI |
| Clinical interoperability/terminology | Architecture/owner mapping only | RESEARCH exact standards, adapters, terminology artifacts and licenses |
| LIS/specimens | Original implementation/tests and clinical bridge inspected | Reconcile PG persistence, outbox and source authority |
| Imaging/pathology | Existing image/archive convergence owners identified | Remaining viewer/codec/server/assets rights and operational qualification not audited here |
| OCR/document extraction | Not benchmarked or adopted | HOLD candidates until exact artifacts/weights, source anchoring and failure tests |
| Genomics/multiomics/scientific workflows | No datasets acquired, no pipeline adopted | Historical data-origin and dependency audit remain open |
| AI models/inference/agents | No model/weights/tool framework adopted | Deterministic baseline first; model rights and task-specific evaluation outstanding |
| Search/knowledge graph | Accepted H1 lexical/structured direction retained | No vector/graph adoption in this package |
| Auth/consent/security/recovery | Existing branch evidence inspected; no production certification | Synthetic authorization receipts do not establish real identity/consent |
| Containers/OS/build/CI/assets | No new artifacts; not fully inventoried | Whole deployment/SBOM/NOTICE qualification remains open |
| Commercial competitors | Not re-researched in this pass | Complete exact capability/access comparison before selecting alternatives |

The four rights registers remain distinct: software, models, data, knowledge.
This report links findings to the existing [rights owner](https://app.notion.com/p/40a3866f77ef815a97d5e016ededf5b9)
and [technology registry](https://app.notion.com/p/40a3866f77ef811c969fc38e95027ec2).
The permissive adoption policy excludes reciprocal/restricted or unknown terms
without a scoped exception. It does not change Open Intelligence's own license.
The [SPDX v2.3.1 expression specification](https://spdx.github.io/spdx-spec/v2.3.1/SPDX-license-expressions/)
distinguishes OR choice, AND obligations and WITH exceptions; a permissive token
inside a compound expression cannot establish compliance by itself.

## 5. Biomedical access and rights findings

Primary pages checked 3 November 2026; no article bodies or patient records
acquired for this research. These findings guide a limited engineering choice,
not legal clearance for all uses or jurisdictions.

| Source | Verified boundary | Current decision |
|---|---|---|
| [Crossref](https://www.crossref.org/documentation/retrieve-metadata/) | Bibliographic facts reusable; Crossref-generated data CC0; abstracts retain publisher/author copyright. Public DOI API available without login; respect rate/concurrency limits. | EXTEND existing factual allowlist. No abstract, article, embedding/training or clinical-support inference. |
| [PubMed/NLM](https://www.nlm.nih.gov/databases/download.html) | Records contain both government-origin material and potentially copyrighted abstracts; acknowledgement/currency conditions apply. | HOLD abstract reuse until operation-specific review. Citation access is not PMC/full-text entitlement. |
| [PMC datasets](https://pmc.ncbi.nlm.nih.gov/tools/textmining/) | Use current permitted retrieval services and each article's license. The 2026 dataset transition supersedes older FTP assumptions. | RESEARCH item-specific rights; no unrestricted full-text scraping or legacy-FTP connector. |
| [CIViC](https://docs.civicdb.org/en/latest/about/faq.html) | Documentation identifies content as CC0 and application code as MIT. Cited papers retain their own rights. | Promising evidence-content candidate; exact API/schema, provenance and integration qualification still required. |
| [OncoKB](https://faq.oncokb.org/licensing) | Commercial/clinical and academic programmatic access require appropriate licenses; AI/ML training is expressly prohibited. | HOLD unless a specific authorized agreement supports the intended operation. |
| NCCN | Exact current Guidelines EULA could not be retrieved. Related [JNCCN terms](https://jnccn360.org/terms-of-use/) do not substitute for that EULA. | Preserve accepted metadata/version/link boundary; content integration remains disabled/unresolved. |

No ASCO/ESMO, clinical-trial, drug, terminology or model access grant was newly
verified. Publisher restrictions and missing evidence cannot be resolved by an
API wrapper, a public URL or a container.

## 6. Implemented correction and verification

The existing Crossref projection accepted arbitrary retrieval dates, invalid
calendar dates, naive times, invalid offset minutes and control characters. An
explicit empty value silently became current time. The decoder also silently
resolved duplicate JSON members; the live MIME check accepted lookalikes.

Changed `tools/crossref_metadata.py`: strict calendar/timezone validation,
preservation of valid supplied timestamps, None-only defaulting, shared strict
live/CLI JSON parsing and exact media-type matching. The original factual-field,
DOI-only, redirect, timeout and byte boundaries remain. No migration, API route,
dependency, model, patient registry, H1 data policy or clinical authority changed.

| Check actually performed | Result |
|---|---|
| Main baseline `PYTHONPATH=src python -m unittest discover -s tests -v` | 236 passed in 33.346 s |
| Tests-first Crossref regressions | 13 tests ran; 25 failing subcases reproduced accepted bad inputs |
| Corrected Crossref suite | 13 passed |
| Full corrected unit/HTTP suite | 244 passed in 47.679 s; no skips |
| Real loopback HTTP, controlled fictional upstream | Duplicate DOI returns fixed 422; valid subsequent request succeeds; patient request fields do not leave the adapter; excluded fields are absent |
| Separate live CLI lookup | NumPy paper DOI `10.1038/s41586-020-2649-2` succeeded at `2026-11-03T15:29:15+00:00`; allowed bibliography only, raw provider response not retained |
| Local browser journey | Attempted; blocked by missing Chrome/Chromium. No local browser pass claimed |
| `git diff --check` | Passed |

The local live lookup proves one provider request, not reliable availability,
scientific appraisal, H1 persistence or the full section-14 MVP. The HTTP fixture
test and live request are separate evidence. Hosted checks/reviewer findings are
recorded in the draft PR and completion checkpoint.

## 7. Decisions, milestones and continuation

**Established:** preserve accepted architecture, synthetic-patient boundary,
FICT-only H1 catalog, existing PR owners and strict content rights. **Implemented:**
the bounded Crossref correction. **Recommended:** qualify a real metadata import
through the existing H1 catalog owner rather than introducing another ledger.
**Unresolved:** full deployment rights inventory, production identity/consent,
independent clinical/user validation, full patient-workflow coverage and intended
use. **Named approval:** founder/maintainer for merge; appropriate clinical,
privacy/legal and institutional owners for real-data or clinical operation.

| Next milestone | Concrete acceptance | Owner / dependency |
|---|---|---|
| Review this correction | Exact-head unit/HTTP and hosted browser gates; no weakened rights or egress | Maintainer; no merge authorized by this receipt |
| Design permitted H1 metadata import | Typed record provenance and retrieval time, real-vs-fictional status, exact DOI/source validation, immutable version/hash, operation-specific rights, no source/patient egress | Existing #224/#298/#307 evidence owner, OI-004/008 and #92 |
| Implement the admitted metadata path | One canonical patient question finds and links one permitted real metadata record; wrong identity, changed rights, duplicate retry, amendment and restart/restore negatives pass through actual API/UI | Same catalog/authority owners; preserve source-only vs evidence-report distinction |
| Complete content-backed investigation | Permitted passage, exact claim support/applicability, reviewed report and reassessment across one composed branch | Existing report/Composer owners; scoped content rights and human review |
| Clinical operation convergence | Registry/EHR/LIS/outbox/source behavior shares canonical identity and survives PG recovery | #95/#301 and H1 owners; no third competing implementation |

**Next executable task:** inspect current #307/#314/#318 heads and existing
`EvidenceRecord`, `materialize_locked`, `public_metadata`, citation verifier and
rights contracts together. Specify real bibliography provenance without relaxing
synthetic-patient isolation or claiming article evidence. Add failing contract
and PostgreSQL tests for the explicit source admission before implementing it.
This correction is compatible with that work but does not complete it.

Continuation branch: `fix/crossref-provenance-boundary-20261103`, based on the
main SHA above. Preserve this receipt and the existing Crossref boundary document;
resume from the PR's final head rather than repeating broad discovery. No PR was
merged/closed and no deployment, external outreach or clinical action occurred.
