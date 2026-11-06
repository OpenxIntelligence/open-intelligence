# Asset catalog — every demo asset and its origin

Scope: assets in the current tree on `main` (HEAD `4b13bc2`;
refreshed 2026-11-05). This supersedes the 2026-11-02 revision,
which described the pre-submission tree on the `oi/safety-packet`
branch; nothing listed there has been removed, and the files merged
since are added below.

There are no fonts, images, icons, audio, video, or vendored files in the
demo. The complete asset list is: twelve web files; twenty-four fictional
report, evidence, and discovery text files plus one replay fixture, one
bibliographic fixture, one FHIR lab-bundle fixture, and one readme in
`examples/synthetic/`; and seven fictional report text files plus one
expectations file in `examples/patient-access/`.

## Web assets (authored for this repository)

| Asset | Origin | Purpose |
|---|---|---|
| `web/index.html` | Independently authored for this repository | Demo page structure. Loads only local `/style.css`, `/app.js`, and `/mission.js`. |
| `web/app.js` | Independently authored for this repository | Demo UI logic. No third-party library. All requests go to relative `/api/…` paths. |
| `web/case_search.js` | Independently authored for this repository | Case search and triage list logic. All requests go to relative `/api/…` paths. |
| `web/clinician-overview.js` | Independently authored for this repository | Clinician overview panel logic. All requests go to relative `/api/…` paths. |
| `web/consent.js` | Independently authored for this repository | Consent panel logic. All requests go to relative `/api/…` paths. |
| `web/intake.js` | Independently authored for this repository | Document intake and preview logic. All requests go to relative `/api/…` paths. |
| `web/provenance.js` | Independently authored for this repository | Source provenance panel logic. All requests go to relative `/api/…` paths. |
| `web/report.js` | Independently authored for this repository | Patient report panel logic. All requests go to relative `/api/…` paths. |
| `web/mission.js` | Independently authored for this repository | Patient Mission panel logic. Fetches only the relative `/api/cases/{id}/mission` projection. |
| `web/style.css` | Independently authored for this repository | Demo styling. Imports only the local `./tokens.css` and `./base.css`. No external fonts or imported stylesheets. |
| `web/tokens.css` | Independently authored for this repository | Design tokens (spacing, type, color, system font stacks). No external resources. |
| `web/base.css` | Independently authored for this repository | Base element styles. No external resources. |

## Fictional case and evidence text (independently authored)

| Asset | Origin | Purpose / note |
|---|---|---|
| `examples/synthetic/alpha-pathology-original.txt` | Independently authored fictional report, format `OI-SYNTHETIC-REPORT/1`, document `PATH-ALPHA`, case `CASE-ALPHA` | Original pathology source for the Alpha demo case. |
| `examples/synthetic/alpha-pathology-amended.txt` | Independently authored fictional report, format `OI-SYNTHETIC-REPORT/1`, document `PATH-ALPHA`, case `CASE-ALPHA` | Amended version of the same document; exercises amendment-stale behavior. |
| `examples/synthetic/alpha-imaging.txt` | Independently authored fictional report, format `OI-SYNTHETIC-REPORT/1`, document `IMG-ALPHA`, case `CASE-ALPHA` | Imaging source for the Alpha demo case. |
| `examples/synthetic/beta-pathology.txt` | Independently authored fictional report, format `OI-SYNTHETIC-REPORT/1`, document `PATH-BETA`, case `CASE-BETA` | Pathology source for the Beta demo case. |
| `examples/synthetic/wrong-patient.txt` | Independently authored fictional report, format `OI-SYNTHETIC-REPORT/1`, document `PATH-OTHER`, case `CASE-BETA` | Negative test asset: exercises wrong-case linkage rejection. Not a real record. |
| `examples/synthetic/demo-evidence.txt` | Independently authored fictional evidence, format `OI-SYNTHETIC-EVIDENCE/1`, declaration `Rights: original-synthetic` | The original bundled evidence-format example. That declaration is not clearance for arbitrary user-supplied text. |
| `examples/synthetic/discovery-literature-001.txt` | Independently authored fictional discovery record, format `OI-SYNTHETIC-DISCOVERY/1`, key `FICT-LIT-001`, kind `literature`, DOI `10.5555/oi-synthetic-002` | Fictional bibliographic record for demonstration only. The DOI is an identifier only; no lookup is performed. |
| `examples/synthetic/discovery-trial-001.txt` | Independently authored fictional discovery record, format `OI-SYNTHETIC-DISCOVERY/1`, key `FICT-TRIAL-001`, kind `trial`, registry `FICT-NCT-000001`, status `not-verified` | Fictional study listing for demonstration only. Recruitment availability is not verified. |
| `examples/synthetic/oi019-a-t0-pathology.txt` | Independently authored fictional report, format `OI-SYNTHETIC-REPORT/1`, document `PATH-OI019-A`, case `CASE-OI019-A` | Case A baseline pathology (T0). |
| `examples/synthetic/oi019-a-t0-imaging.txt` | Independently authored fictional report, format `OI-SYNTHETIC-REPORT/1`, document `IMG-OI019-A`, case `CASE-OI019-A` | Case A baseline imaging (T0). |
| `examples/synthetic/oi019-a-t1-clinical.txt` | Independently authored fictional report, format `OI-SYNTHETIC-REPORT/1`, document `CLIN-OI019-A`, case `CASE-OI019-A` | Case A new-information clinical note (T1). |
| `examples/synthetic/oi019-a-t2-clinical-amended.txt` | Independently authored fictional report, format `OI-SYNTHETIC-REPORT/1`, document `CLIN-OI019-A`, case `CASE-OI019-A`, amends `CLIN-OI019-A@1` | Case A amendment (T2) of the T1 clinical document only. |
| `examples/synthetic/oi019-b-t0-pathology.txt` | Independently authored fictional report, format `OI-SYNTHETIC-REPORT/1`, document `PATH-OI019-B`, case `CASE-OI019-B` | Case B baseline pathology (T0). |
| `examples/synthetic/oi019-b-t0-imaging.txt` | Independently authored fictional report, format `OI-SYNTHETIC-REPORT/1`, document `IMG-OI019-B`, case `CASE-OI019-B` | Case B baseline imaging (T0). |
| `examples/synthetic/oi019-b-t1-clinical.txt` | Independently authored fictional report, format `OI-SYNTHETIC-REPORT/1`, document `CLIN-OI019-B`, case `CASE-OI019-B` | Case B new-information clinical note (T1). |
| `examples/synthetic/oi019-b-t2-clinical-amended.txt` | Independently authored fictional report, format `OI-SYNTHETIC-REPORT/1`, document `CLIN-OI019-B`, case `CASE-OI019-B`, amends `CLIN-OI019-B@1` | Case B amendment (T2) of the T1 clinical document only. |
| `examples/synthetic/oi019-evidence-control.txt` | Independently authored fictional evidence, format `OI-SYNTHETIC-EVIDENCE/1`, id `EVID-OI019-CONTROL`, declaration `Rights: original-synthetic` | No-threat control example. That declaration is not clearance for arbitrary user-supplied text. |
| `examples/synthetic/oi019-evidence-discussion.txt` | Independently authored fictional evidence, format `OI-SYNTHETIC-EVIDENCE/1`, id `EVID-OI019-DISCUSSION`, declaration `Rights: original-synthetic` | Preservation-discussion example. That declaration is not clearance for arbitrary user-supplied text. |
| `examples/synthetic/oi019-evidence-hypothetical.txt` | Independently authored fictional evidence, format `OI-SYNTHETIC-EVIDENCE/1`, id `EVID-OI019-HYPOTHETICAL`, declaration `Rights: original-synthetic` | Hypothetical-criterion example. That declaration is not clearance for arbitrary user-supplied text. |
| `examples/synthetic/oi019-evidence-invalid.txt` | Independently authored fictional evidence, format `OI-SYNTHETIC-EVIDENCE/1`, id `EVID-OI019-INVALID`, declaration `Rights: original-synthetic` | Invalid-candidate example. That declaration is not clearance for arbitrary user-supplied text. |
| `examples/synthetic/oi019-wrong-patient.txt` | Independently authored fictional report, format `OI-SYNTHETIC-REPORT/1`, document `PATH-OI019-WRONG`, declares `CASE-OI019-B` | Negative test asset: intentionally declares the other synthetic subject. Not a real record. |
| `examples/synthetic/h1-demo-report.txt` | Independently authored fictional report, format `OI-SYNTHETIC-REPORT/1`, document `DOC-DEMO-PATHOLOGY`, case `CASE-DEMO` | H1 demo pathology source. First line carries the `OI-SYNTHETIC-REPORT/1` marker. |
| `examples/synthetic/plaintext-record.txt` | Independently authored fictional source record, format `OI-SYNTHETIC-PLAIN-TEXT` | Synthetic teaching material for the plaintext intake path; states no real patient or published patient narrative was used. First line carries the `OI-SYNTHETIC-PLAIN-TEXT` marker. |
| `examples/patient-access/oi017-pathology-specimen-a.txt` | Independently authored fictional report, format `OI-SYNTHETIC-REPORT/1`, document `PATH-OI017-A`, case `CASE-OI017` | Institution A pathology on specimen A. |
| `examples/patient-access/oi017-pathology-specimen-a-amended.txt` | Independently authored fictional report, format `OI-SYNTHETIC-REPORT/1`, document `PATH-OI017-A`, case `CASE-OI017`, amends `PATH-OI017-A@1` | Amended version of the specimen A document. |
| `examples/patient-access/oi017-pathology-specimen-b.txt` | Independently authored fictional report, format `OI-SYNTHETIC-REPORT/1`, document `PATH-OI017-B`, case `CASE-OI017` | Institution B pathology on a different specimen B. |
| `examples/patient-access/oi017-encounter-inst-a.txt` | Independently authored fictional report, format `OI-SYNTHETIC-REPORT/1`, document `ENC-OI017-A`, case `CASE-OI017` | Institution A encounter note. |
| `examples/patient-access/oi017-medications-inst-a.txt` | Independently authored fictional report, format `OI-SYNTHETIC-REPORT/1`, document `MEDS-OI017-A`, case `CASE-OI017` | Institution A medications note. |
| `examples/patient-access/oi017-imaging-report-only.txt` | Independently authored fictional report, format `OI-SYNTHETIC-REPORT/1`, document `IMG-OI017-A`, case `CASE-OI017` | Imaging report-only note. |
| `examples/patient-access/oi017-collision-wrong-binding.txt` | Independently authored fictional report, format `OI-SYNTHETIC-REPORT/1`, document `PATH-OI017-COLLISION`, case `CASE-OI017` | Negative test asset: envelope binding conflicts with the recorded binding; must be rejected, not merged. Not a real record. |

## Fictional bibliographic and replay fixtures (independently authored)

| Asset | Origin | Purpose / note |
|---|---|---|
| `examples/synthetic/fictional-fhir-r4-lab-bundle.json` | Independently authored fictional FHIR R4 Bundle (Patient `FICTIONAL-PATIENT-A`, Specimen `FICTIONAL-SPECIMEN-A`, Observation `FICTIONAL-OBS-A`, DiagnosticReport `FICTIONAL-REPORT-A`) | Fictional laboratory bundle fixture for the H1 FHIR lab-custody path. All identifiers are `FICTIONAL-*`; no real patient data. |
| `examples/synthetic/crossref-metadata-fixture.json` | Independently authored fictional entry in Crossref JSON shape; DOI `10.5555/oi-synthetic-001`; journal "Fictional Examples Journal" | Offline bibliography demonstration. Not a real article citation. No live lookup is performed for this entry. |
| `examples/synthetic/demo-investigation.json` | Independently authored recorded demonstration output with `FIRST_SOURCE` / `FIRST_ASSESSMENT` citation placeholders | Offline replay for model investigation. Placeholders are replaced server-side with real current case ids and validated like live output; labeled `mode=replay`, never a live run. |
| `examples/synthetic/oi019-readme.md` | Independently authored demonstration note | Describes the OI-019 two-case staging (T0/T1/T2 by file import) and the four evaluation elements. Not advice or a recommendation. |
| `examples/patient-access/EXPECTED_RESULTS.json` | Independently authored expectations record for `CASE-OI017` | Per-fixture hashes and sizes plus a synthetic-provenance statement. Synthetic contract evidence only. |

## Merged-main top-up (2026-11-05): growth since the 2026-11-02 revision

682 files were added to `main` since 2026-11-02 (counted with
`git log --since=2026-11-02 --diff-filter=A --name-only main`):
397 under `apps/`, 181 under `docs/`, 57 under `tests/`, 25 under
`src/`, 6 under `web/`, 6 under `tools/`, 3 under `examples/`, 3
under `.github/`, plus the repository-root `requirements-pdf.lock`.
The demo-asset tables above remain file-by-file; the non-demo
growth below is summarized by category, with safety-relevant new
files named individually. A per-file listing of all 682 is not
attempted — at this scale it would be unreadable and would go stale
faster than it could be checked — and this packet says so rather
than pretending otherwise. Every count here is re-derivable from
the repository with the `git log` command above.

### Safety-relevant new files (named individually)

| Asset | Origin | Purpose / note |
|---|---|---|
| `requirements-pdf.lock` (repository root) | Authored for this repository | Hash-pinned `pypdf==6.21.4` lock for the optional bounded PDF intake runtime. The guard test's no-package-manager check covers `requirements.txt`, `pyproject.toml`, `package.json`, `package-lock.json`, `Pipfile`, `Pipfile.lock` at the root — this lock filename is not in that list, and the guard passes with it present. |
| `THIRD_PARTY_NOTICES/pypdf.txt` | `pypdf` project notice | BSD license notice for the optional PDF runtime. |
| `docs/engineering/DOCUMENT_INTAKE.md` | Authored for this repository | Source and license record for the bounded PDF intake runtime. |
| `tools/research/data_policy.py` | Authored for this repository | Research data-policy helpers (fictional/offline only). |
| `tools/research/test_restricted_research_entrypoints.py` | Authored for this repository | Regression tests enforcing the named-person / public-case acquisition refusal (PR #137, merged). |
| `tools/research/test_sid_case_data_disabled.py` | Authored for this repository | Regression tests: named-person case data disabled in research paths. |
| `apps/api/migrations/versions/0015_manual_report_context.py` through `0018_laboratory_questions.py` | Authored for this repository | H1 PostgreSQL migrations; chain ends at `0018_laboratory_questions`, with the 0016 fork converged by `0017_lab_manual_convergence`. |
| `apps/web/package.json`, `apps/web/package-lock.json` | Authored for this repository | H1 React tree manifest (`open-intelligence-h1-web` 0.1.0). Outside the legacy demo's standard-library claim and outside the root package-manifest guard. |

### Growth by category (counts only)

| Category | Files added | Note |
|---|---|---|
| `apps/` (H1 API + H1 web) | 397 | FastAPI/PostgreSQL tree, React tree, migrations 0015–0018, laboratory/FHIR modules, question/passage/review contracts, dependency-gate tooling. Covered at inventory level in `SBOM.md` (26 pinned packages, `SCHEMA_REVISION` 0018); not demo assets. |
| `docs/` | 181 | Engineering notes, H1 contracts, research and evaluation docs. Complementary inputs, not shipped code; no new license decision. |
| `tests/` | 57 | Vanilla + H1 tests, including the case-switch guard test and the restricted-entrypoint tests. Test-only, not shipped. |
| `src/` | 25 | New `src/open_intelligence` modules (see `SBOM.md` first-party table). Demo code; no new model path, no new dependency. |
| `web/` | 6 | The six new panel scripts listed in the web-assets table above. Demo code; all requests to relative `/api/…` paths. |
| `tools/` | 6 | Research-policy helpers and regression tests (named above). |
| `examples/` | 3 | The three new synthetic fixtures listed above. |
| `.github/` | 3 | `offline-scientific-safety.yml`, `h1-api.yml`, `h1-web.yml` (see `SBOM.md` CI table). |

## Merged-main top-up (2026-11-02): covered non-demo files

The 44 files below are CI-only, test-only, research-only, docs-only,
or coordinator/blank-template material. They are listed here for
coverage only; the demo-asset counts above are unchanged, and none of
these files is a demo asset. Each file's first lines were read on
2026-11-02.

### CI workflows (authored for this repository; CI-only, not shipped)

| Asset | Origin | Purpose / note |
|---|---|---|
| `.github/workflows/public-research.yml` | Authored for this repository | Runs the research unit tests, builds a research-only venv from `tools/research/requirements.lock`, and runs probes that hit live public endpoints read-only. Uploads aggregate receipts and research source only (30-day retention). SHA-pinned checkout/setup-python; same SHA-pinned upload-artifact as the existing workflows. |
| `.github/workflows/rna-analysis.yml` | Authored for this repository | Runs the research regression suite and the fixed-scope RNA probe; retains bounded derived findings and code, not full patient matrices (30-day retention). SHA-pinned checkout/setup-python; same SHA-pinned upload-artifact. |
| `.github/workflows/single-cell-analysis.yml` | Authored for this repository | Installs research-only `numpy==2.3.5` + `h5py==3.15.1` into the CI environment (not application dependencies), runs the research suite and the fixed-scope single-cell probe; retains aggregate findings and code only (30-day retention). SHA-pinned checkout/setup-python; same SHA-pinned upload-artifact. |

### Offline evaluation tools (authored for this repository; stdlib-only, no network)

| Asset | Origin | Purpose / note |
|---|---|---|
| `tools/evaluation_packet.py` | Authored for this repository | Cutoff-isolated packaging of fictional IV-01 practice inputs. Strict JSON validation, SHA-256 checks, no-overwrite output. Never opens the coordinator key. |
| `tools/evaluation_preflight.py` | Authored for this repository | Fail-closed declaration preflight over recorded IV-01 fields and fingerprints. Writes, activates, contacts, and scores nothing. |

### Research probes (authored for this repository; research-only, not shipped)

Each probe hits live public endpoints read-only (except `runtime_probe.py`, which uses no network). Raw rows stay in memory; only aggregate counts, schema, hashes, and receipts leave the probe.

| Asset | Origin | Purpose / note |
|---|---|---|
| `tools/research/clinical_semantics_probe.py` | Authored for this repository | Semantic audit over GDC open case metadata (in memory) against a pinned NCI-GDC dictionary commit plus FHIR R4 MedicationStatement/Administration meaning. No reidentification, controlled files, or LLM calls. |
| `tools/research/gdc_projection_probe.py` | Authored for this repository | Hierarchy/temporal projection probe over GDC public TCGA-LUAD/BRCA/LAML metadata in RAM/in-memory SQLite. Aggregate receipts only. No controlled files or inference. |
| `tools/research/public_case_intake.py` | Authored for this repository | Intake over one fixed public catalog (`osteosarc.com/data/catalog/datasets.json`, S3 bucket listing). Raw rows in memory; aggregate engineering receipts, not medical findings. |
| `tools/research/public_evidence_probe.py` | Authored for this repository | Structure audit over fixed public TCIA CSV/ZIP attachments and GDC public TCGA-LUAD case data. Aggregate counts/schema/hashes only; never subject identifiers or rows. |
| `tools/research/requirements.lock` | Observed-environment record for research run 41294219202 | Exact third-party pins for the isolated research venv (`/tmp/oi-research-env` in CI). Research only: explicitly not an application dependency decision or security clearance. |
| `tools/research/rna_expression_probe.py` | Authored for this repository | Fixed-scope descriptive check over five fixed public processed-RNA assets (one subject, four specimens). No raw reads, full matrices, genotypes, p-values, causal claims, or recommendations. |
| `tools/research/runtime_probe.py` | Authored for this repository | LangGraph/SQLite process-boundary experiment on original fictional state only. No network, no model API, no medical data; includes negative controls. Requires the research env. |
| `tools/research/single_cell_probe.py` | Authored for this repository | Bounded descriptive localization over one fixed public processed single-cell (h5ad) object. Only aggregates leave RAM; source labels are never equated with malignancy. |
| `tools/research/trial_screening_probe.py` | Authored for this repository | Registry/screening-contract research over public ClinicalTrials.gov/NLM records. Aggregate time-stamped observations only; no eligibility advice, referrals, or enrollment actions. Executes only a hash-verified pure `parse_criteria` function characterized from ncbi-nlp/TrialGPT (commit `1b3242c`, US Government Work notice); no upstream module imports. |

### Tests (authored for this repository; test-only, not shipped)

| Asset | Origin | Purpose / note |
|---|---|---|
| `tests/test_evaluation_packet.py` | Authored for this repository | Packaging-mechanics tests over the fictional IV-01 packet, not clinical performance. |
| `tests/test_evaluation_packet_json_boundary.py` | Authored for this repository | JSON-boundary CLI regressions with minimal fictional parser fixtures (`CASE-JSON`, `OI-SYNTHETIC-REPORT/1`). Not reference cases or clinical evidence. |
| `tests/test_evaluation_preflight.py` | Authored for this repository | Fail-closed preflight readiness checks with fictional protocol fixtures. Not clinical assessment. |
| `tests/test_iv01_evidence_replay.py` | Authored for this repository | IV-01 evidence replay through the existing `CaseStore`. Synthetic software tests only; labels are not clinical truth. |
| `tests/test_iv01_store.py` | Authored for this repository | IV-01 store replay of practice fixtures through the existing application, without changing it. |
| `tools/research/test_clinical_semantics_probe.py` | Hand-derived fictional cases (`FICTIONAL-A`) | Semantics-probe unit tests. No upstream patient records or model calls. |
| `tools/research/test_gdc_projection_probe.py` | Original fictional fixtures (`FICTIONAL-A/B`) | Projection-probe unit tests. No patient records or clinical reference answers. |
| `tools/research/test_public_case_intake.py` | Original fictional catalog fixtures (`SYN-T0`, `SYN-BLOCK-A`) | Intake unit tests. No copied clinical/genomic records. |
| `tools/research/test_public_evidence_probe.py` | Original fictional audit fixtures | Public-evidence calculation tests. No patient data. |
| `tools/research/test_rna_expression_probe.py` | Original fictional RNA fixtures | Expression-parser unit tests. Expectations independent of real-case values. |
| `tools/research/test_semantic_evidence.py` | Original fictional fixtures (`FICTIONAL-TRACE-A`) | Source-meaning and evidence-attachment checks. |
| `tools/research/test_single_cell_probe.py` | Original fictional aggregate fixtures | Single-cell summary tests. No patient cell records embedded. |
| `tools/research/test_trial_screening_probe.py` | Original fictional registry fixtures (`FICTIONAL-A`) | Trial-screening unit tests. No true patient or trial records. |

### Docs and plans (authored for this repository; complementary, not shipped, no code)

| Asset | Origin | Purpose / note |
|---|---|---|
| `docs/INDEPENDENT_EVALUATION_COLLABORATION.md` | Authored for this repository | Proposed complementary evaluation/collaboration protocol for the existing architecture. Not a new architecture, validation claim, partnership, or data authorization. |
| `docs/evaluation/PACKET_TEMPLATE.md` | Authored for this repository | Blank unexecuted evaluation-packet template. No data, no identifiers. |
| `docs/evaluation/RESULTS_REGISTER_TEMPLATE.csv` | Authored for this repository | Blank results-register header row. No rows, no outcomes. |
| `docs/research/EXPERIMENTAL_LOOP_EXTENSION_2026-10-31.md` | Authored for this repository | Experimental-loop extension proposal, explicitly not adopted. No new platform, dependency, or clinical function. |
| `docs/research/HL7_NANO_MODEL_FABRIC_ADDENDUM.md` | Authored for this repository | Additive HL7/Nano/specialist-model evaluation, explicitly research/evaluate. Not an architecture decision, implementation, validation, or vendor approval. |
| `docs/superpowers/plans/2026-10-31-iv01-packet.md` | Authored for this repository | IV-01 packet implementation plan and constraint record. |

### IV-01 practice packet (independently authored fictional fixtures; coordinator material)

| Asset | Origin | Purpose / note |
|---|---|---|
| `validation/iv01/README.md` | Independently authored fictional-engineering notes | Packet readme. Original AI-assisted fictional fixtures; explicitly not independently adjudicated clinical cases. Coordinator/development material, not for participants. |
| `validation/iv01/SCORING.md` | Authored for this repository | Reviewer rubric and preregistration contract. Supporting methodology, not a validated clinical instrument. |
| `validation/iv01/cases.json` | Independently authored fictional fixtures, cases `CASE-EVAL-A`/`CASE-EVAL-B` | Practice packet: 2 fictional cases, 10 `OI-SYNTHETIC-REPORT/1` / `OI-SYNTHETIC-EVIDENCE/1` sources with SHA-256, 11 receipts, 3 cutoffs. `synthetic: true`, `status: engineering-practice-only`. Coordinator material. |
| `validation/iv01/coordinator_key.json` | Designer reference authored with the fixtures | Twelve designer-expected checks with source anchors. `status: designer-reference-not-independent-ground-truth`, `participant_distribution: DO NOT INCLUDE`. Never a participant asset. |
| `validation/iv01/protocol.json` | Authored for this repository | Protocol record: `status: not_activated`, null evaluation id/commits/thresholds, no reviewers. Nothing activated or approved. |
| `validation/iv01/results_template.csv` | Authored for this repository | Blank results header row. No rows, no outcomes. |

### IV-04 preparation templates (authored for this repository; blank, no data, no authorization)

| Asset | Origin | Purpose / note |
|---|---|---|
| `validation/iv04/ACTIVATION_CHECKLIST.md` | Authored for this repository | Activity/disclosure checklist. Preparation only; all decisions unmade. Not law, permission, approval, or authorization to send anything. |
| `validation/iv04/INDEPENDENCE_AND_ROLES.md` | Authored for this repository | Blank role/conflict/independence assessment instructions. Not a completed assessment. |
| `validation/iv04/INVITATION_BRIEF.md` | Authored for this repository | Draft one-page review invitation. DRAFT — NOT SENT; recipient, approval, scope, and participation unestablished. |
| `validation/iv04/README.md` | Authored for this repository | Handoff readme. Draft preparation material; no outreach, study activation, or partnership. No application, schema, provider, priority, or license change. |
| `validation/iv04/decision_template.json` | Authored for this repository | Blank activity/authorization record: `status: template_not_an_authorization`, `disposition: not_reviewed`, all decision fields null. An agent cannot supply the approval. |

## Explicitly absent

- No real patient records, clinical images, pathology slides, or genomic
  files.
- No copyrighted article, guideline, or trial text.
- No model weights, embeddings, or datasets.
- No stock or licensed media of any kind.

## Verification method

Each demo file above was listed from the repository and its first
lines inspected: every `.txt` file in both example directories opens
with an `OI-SYNTHETIC-*` marker, the JSON fixtures carry the
fictional identifiers shown above, and the two readme/expectations
files carry their own fictional-provenance statements. The guard test
`tests/test_safety_packet.py` re-checks these markers in both example
directories on every test run, and the full vanilla suite was run on
the refold base (`main` `4b13bc2`, 2026-11-05): 772 tests, 17
failures, all pre-existing `test_pdf_intake` failures from the
missing local `pypdf`, zero other failures. The 682-file growth
count was measured with `git log --since=2026-11-02
--diff-filter=A --name-only main`.
