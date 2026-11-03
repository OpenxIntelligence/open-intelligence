# Crossref bibliographic metadata boundary

## Connected reading and follow-up continuation — 3 November 2026

This candidate ([draft #357](https://github.com/OpenxIntelligence/open-intelligence/pull/357))
joins the existing #321 DOI owner to the verified #335 workspace
(`9d173843f924b40becba3a7dffd71717c12afb5d`, tree
`57165fc8b1c6305336752eb948710a437eda9cf9`), which retains #328 follow-up attention,
#322 strict citation history/status-bearing downloads and source reading/intake.
The DOI donor is pinned at `bc93149671f518081dd95d75333ce8c87693f707`, tree
`b2f28f1da4c4b13bf3bc64135c191fa141172f93`. Its local recovered source has the
same complete Git tree; historical source receipts below remain donor evidence.

### Bounded design and acceptance

Reuse the existing canonical patient/source/question/catalog/citation and rights
owners. Keep DOI lookup default off, require the explicit public-DOI acknowledgment
and separate lookup grant, and retain a separate explicit citation save. Reading,
filters, drafts, source inspection and report downloads must not initiate lookup.
Bibliography cannot confer article rights, scientific support or clinical approval.
No new dependency, external activation or live provider request is part of this work.

Preserve #321's migration `0012_crossref_metadata` and all earlier published
migrations byte for byte. Reviewed-document intake is separately in #349; do not
silently copy or rename its migration into this candidate. Their eventual joining
requires an explicit forward migration and combined populated-upgrade/recovery
acceptance. #348 comparison-draft and #339 rights-gate changes remain separate.

Five runtime/test files require composition with the newer parent: retain strict
`EvidenceLink.created_at` validation while allowing native DOI citations; add the
DOI session methods alongside source-to-question entry; retain reading/intake CSS;
update the metadata control label in the existing composed test; and insert the
DOI provider-fixture journey into the complete browser path. Existing report
download/current-status helpers and task attention files remain unchanged.

Plan: reproduce missing DOI behavior with donor tests; compose those owners;
run full compiled client/build and reference/backend checks; independently review;
then execute unchanged hosted API/PostgreSQL/restart/restore and React/Chromium
gates on the exact published combined head. No donor-only pass is combined proof.

### Observed local checkpoint

The initial tests-first run executed 310 client checks: eight new DOI behavior
checks failed, two new negative controls already passed, and 299 inherited checks
passed. One inherited in-flight navigation check also failed after 22.2 seconds;
it passed unchanged when run alone (39 ms) and in the corrected full suite. No
timeout, assertion or implementation on that path was changed to obtain a pass.

After composition all **310 client checks passed with zero skips**, production
TypeScript/Vite build and the existing dependency gate passed. All **19 focused
API contract checks passed**, including strict citation timestamps and DOI input,
configuration and authorization boundaries. All **298 reference checks passed**.
The first full local API run reported two test-server timing errors (startup for
the schema-mismatch readiness subcase and a five-second OpenAPI read timeout).
An unchanged sequential rerun completed **436 checks: 105 passed, 331 skipped**
because actual PostgreSQL was unavailable. No assertion or time limit was relaxed.
Those skips are not database acceptance. Independent review and hosted acceptance
remain pending at this committed checkpoint; the continuation PR records their
later exact outcomes against the published combined head.

### Review follow-up

Independent read-only review of local `75add1f1` found no Critical or Important
defect and two Minor issues: a known stale question still offered DOI lookup,
and README described the donor's source-reading scope as current. Three focused
checks reproduced the stale-input, request and HTTP 409 guidance failures before
repair. The final client now blocks known stale lookup, explains a server-side
context conflict without exposing diagnostics, and leaves permitted catalog and
citation-history reads available. README distinguishes the donor from this
connected candidate. All **312 client tests and the production build passed**
after repair. Backend, migrations, dependencies and browser assertions are unchanged.

The initial combined head `0767e03a19bc8d62bc940865a02254f7cae8b3bb` already passed
[the complete built-browser gate](https://github.com/OpenxIntelligence/open-intelligence/actions/runs/41678462495)
with 310 client tests. Artifact `13250957911` matched SHA-256
`dabb396b02cac6acb9b97b36cceaa1aea427752e7b40d7479fd69d9ca3133b35`;
its recorded commit and all 413 archived source files/modes matched the tested
tree. Desktop/mobile DOI views were inspected. Final-head hosted verification
and the small review-follow-up assessment are recorded on #357 after completion.

This is a synthetic, unmerged integration candidate. The provider fixture is
explicitly labeled and has no live fallback. Existing clinical/commercial/source
activation holds and incomplete professional review/identity/consent stay in force.

This boundary owns the existing DOI-only bibliographic adapter and its bounded
H1 continuation. Public bibliography, independently authored patient fixtures,
permitted article content, and scientific appraisal have separate provenance
and permissions.

## Rights and sources (checked 31 October 2026)

- Crossref's [Metadata Retrieval](https://www.crossref.org/documentation/retrieve-metadata/) states bibliographic metadata is generally factual and reusable; Crossref-generated material is CC0. **Publisher-supplied abstracts are separately copyrighted.**
- Crossref's [REST API access policy](https://www.crossref.org/documentation/retrieve-metadata/rest-api/access-and-authentication/) allows public access without login, encourages a contact email/identified User-Agent, caching and respecting published rate/concurrency limits.
- This prototype only projects the DOI, title, journal, year, type, public author names and a **constructed** canonical DOI URL with retrieval time and the rights-policy reference. Provider abstracts, article text, clinical claims, unreviewed links, license claims and unknown fields are dropped. No biomedical knowledge is assumed merely from a citation.

## Run (Python 3.11+, standard library only)

Offline fixture (no network):
```bash
python -m tools.crossref_metadata 10.5555/oi-synthetic-001 --fixture examples/synthetic/crossref-metadata-fixture.json
```

Explicit operator-invoked single DOI lookup:
```bash
python -m tools.crossref_metadata 10.1038/s41586-020-2649-2 --live
```

The live mode sends **only the supplied public DOI** to the fixed Crossref HTTPS host. It has no free-text search or attachment input and does not read or automatically append patient identifiers or genomic profiles. Only deliberately supplied public DOIs are permitted; DOI syntax validation cannot detect all identifying information in user input. It rejects redirects, bounds response size and timeout, and does not automatically retry. The optional `--contact` parameter identifies an operator to Crossref's polite pool. It is not enabled by default.

Run tests:
```bash
python -m unittest discover -s tests -p 'test_crossref_metadata.py' -v
```

## Explicit limits

- Synthetic fixture DOI is fictional and is not a real article citation.
- No automatic content-rights clearance, article or abstract ingestion, clinical trial matching, evidence-grade estimation, treatment ranking, patient-record reading, model training, or automatic patient-context egress. The supplied DOI must itself be public and appropriate to disclose.
- Bibliographic metadata is useful for discovery and attribution but **cannot support a clinical claim without independently retrieving and evaluating the source under appropriate rights**.
- The repository distribution license is undecided; a successful technical check is not product release approval.

## H1 continuation — 3 November 2026

**Decision: recommended reversible engineering increment; clinical and commercial
release clearance remains HOLD.** The canonical [Rights register](https://app.notion.com/p/40a3866f77ef815a97d5e016ededf5b9)
continues to classify Crossref as a provisional technical candidate. Its hold on
clinical evidence and patient-context retrieval is not overridden by this code,
an environment switch, a test result, or a metadata rights declaration.

The selected implementation adds one deliberate action: enter a public
publication DOI, inspect its selected bibliographic facts, then explicitly save
its exact version as a citation on an existing synthetic question. The external
request receives only the supplied DOI and fixed adapter headers. Patient,
case, question, source text, molecular findings, and application credentials do
not enter the provider request. DOI syntax validation is not a detector for
personal information; the input must be a deliberately supplied public DOI.

### Existing owners and source reuse

The base is the combined H1 application in [PR #307](https://github.com/OpenxIntelligence/open-intelligence/pull/307),
head `477f24826a8a102c7437c993d69877c1f250b951`, tree
`cd8d909ad2844e7fbd37ae30a9a10b9123374666`. Its exact-head API run
[41658525044](https://github.com/OpenxIntelligence/open-intelligence/actions/runs/41658525044)
passed 414 API tests without skips, 287 reference tests, and the inherited
PostgreSQL/restart/restore probes. The React/browser run
[41658525265](https://github.com/OpenxIntelligence/open-intelligence/actions/runs/41658525265)
also passed. These are baseline results, not acceptance of this extension.
The later documentation-only head `c35219dc5eb244874a7df6e9bf00cfbfda18251f`
and its four updated records are preserved as this continuation's parent.

- Reuse `tools/crossref_metadata.py` from merged PR #6, blob
  `7546143c9a20d72791c7e4a984805514e03d6cb7`. Relocate its shared implementation
  into the existing domain package with a compatibility CLI entry point.
- Extend #298's canonical metadata catalog, current rights decisions, and
  immutable question citation links. Preserve its synthetic seeding boundary.
- Preserve #300/#307's independently authored passages, comparisons, immutable
  reports and their separate permissions. A DOI link does not create or approve
  any of these objects.
- Leave #314's source-to-question handoff, #313's imaging integration and #159's
  Europe PMC title-discovery owner in their existing lanes. This increment adds
  neither a second patient chart nor another literature search implementation.

### Operation-specific source assessment

Official sources were rechecked on **3 November 2026**:
[metadata licensing](https://www.crossref.org/documentation/retrieve-metadata/),
[REST API and single-record route](https://www.crossref.org/documentation/retrieve-metadata/rest-api/),
and [access/rate policy](https://www.crossref.org/documentation/retrieve-metadata/rest-api/access-and-authentication/).
No official MCP service, SDK, institution agreement, or production SLA is
asserted by this integration.

| Operation | Technical boundary | Decision/status |
|---|---|---|
| Retrieve one publication identity | Existing fixed HTTPS `/works/{doi}` adapter; explicit public DOI; bounded response, timeout and concurrency; no redirects or automatic retries | Existing technical capability; H1 default off pending operation review |
| Store and search selected bibliography | DOI, title, journal, year, publication type and public author names; exact immutable projection; current metadata store/display decision | Official policy provides a factual-metadata reuse basis; bounded synthetic engineering declaration only |
| Display/link bibliography | Source-specific label, constructed DOI destination, retrieval/version/policy provenance; independent local question authorization | Implement and test; no article-access or support assertion |
| Retrieve/store an abstract, paper, figure or supplementary file | No such ingress in this adapter; unknown response fields are discarded | HOLD; source-specific content rights and a separate implementation required |
| Quote/export article content | Existing authored-evidence owner requires its own original and content-specific permissions | DOI metadata cannot grant this operation |
| Model input, embeddings, evaluation or training | No model call or such permission inferred | HOLD; separate intended-use and source assessment |
| Patient-context query or automatic research | No automatic query generation, patient forwarding, broad topic query or scheduled refresh | HOLD; outside this increment |
| Clinical or commercial deployment | No production activation, contract, verified identity/consent or clinical validation | Requires the appropriate review and approval; remains blocked |

Bibliographic policy permits reuse of facts; Crossref-generated data is CC0.
Publisher or author abstracts retain their own copyright. Article license
metadata, free access, a DOI, and a successful API response each fail to establish
permission to ingest or analyze an article. Provider policy should be rechecked
before activation and periodically thereafter; no expiry is invented.

### Contract and acceptance plan

1. Preserve native normalized DOI identity. Use the allowlisted bibliographic
   projection's SHA-256 as the immutable catalog version, excluding retrieval
   time. A metadata snapshot version is not a publisher article edition.
2. Add a forward migration after `0011_evidence_convergence`; leave published
   migration bytes unchanged. Preserve the same catalog, rights and citation
   owners. Store projection provenance and append-only retrieval receipts in
   this evidence domain. Protocol fixtures are recorded as fixtures.
3. Require a separate lookup action in addition to the current patient, source,
   question and evidence-read authority. Validate context before egress, release
   database locks during the provider call, then recheck current authority and
   the exact original context before persistence/disclosure.
4. Encode the actual response within the existing source transaction and final
   authority boundary. Audit failure or changed access rolls back new metadata
   and receipts. Provider failure returns a bounded error without raw payloads.
5. Never restore withdrawn metadata rights through a repeated lookup or a new
   projection of the same DOI. Maintain the earlier exact citation and its
   historical rights outcome. Existing citation retries retain their original
   identity without redisclosing withdrawn metadata.
6. Preserve independent question drafts, uncertain citation intents and
   cross-patient/case response invalidation. A lookup does not save a citation;
   a citation does not create a supporting finding, comparison or report.
7. Exercise protocol, malformed metadata, permission denial before and during
   lookup, source changes, immutable-version retries, and literal UI rendering.
   Verify real PostgreSQL HTTP, built React/Chromium, API/database restart and
   restored HTTP on the final candidate. Do not count skipped local database
   tests or deterministic provider fixtures as live-service evidence.

The inherited provider's documented vendor JSON type and invalid timestamp
handling were reproduced before repair. The completed verification record below
belongs to this extension's own runtime, not to its predecessor.

### Implemented candidate and practical limits

The H1 POST route ends in `/questions/{question_id}/evidence-doi`. It requires
exact `synthetic: true`, exact `public_doi_acknowledged: true`, a bounded public
DOI, and a separate `evidence_lookup` grant. `OI_API_CROSSREF_ENABLED` defaults
to `false`; only the exact strings `true` and `false` are accepted. An operator
switch does not approve a real-patient, clinical or commercial release.

The provider implementation remains standard-library-only. It uses an
**eight-second socket timeout**, a 256 KiB response ceiling, no redirect
following and no automatic retry. This is not an eight-second total deadline:
a trickling response can take longer, and a browser abort does not terminate the
server's provider thread. The single-flight/cooldown gate is process-local; it
does not provide a distributed production quota. Production egress, overall
deadline/cancellation and coordinated rate control remain review requirements.

An immutable metadata snapshot retains its first retrieval time and acquisition
mode; subsequent identical lookups append receipts without rewriting it. A new
projection creates a separate version, and returning to earlier bytes recovers
the earlier version. Each already stored version retains its independent rights
decision. Any restricted version blocks further DOI-family lookup/import, so a
refetch cannot create a fresh grant around a withdrawal. This is not a new
blanket family-withdrawal operation.

Browser and recovery acceptance inject the original independently authored
Crossref protocol fixture through `apps/api/tools/crossref_fixture_api.py`.
That factory is excluded from the product image and mounted only into the
disposable verification container. It has no live-provider fallback. Its mode
is persisted and displayed as `protocol_fixture`; these checks establish the
application integration, not live Crossref availability or article validity.

### Verified implementation — draft #321

[PR #321](https://github.com/OpenxIntelligence/open-intelligence/pull/321) contains
runtime `a49530893f210609c1d203bd74a55fc683335149`, tree
`6a3fcb4baff79ff5e45ae6bf0111e3791234c4ea`, on preserved upstream documentation
head `c35219dc5eb244874a7df6e9bf00cfbfda18251f`. The verification recorded here
applies to that exact runtime; this receipt and research-register follow-up
change documentation only. The contribution remains draft, unmerged and
undeployed, with the production feature switch off by default.

| Verification | Observed result |
|---|---|
| [API/PostgreSQL run 41664556129](https://github.com/OpenxIntelligence/open-intelligence/actions/runs/41664556129), job 126016287746 | **434 tests passed, zero skips**, including actual PostgreSQL, populated migration, authority races, metadata immutability and retry behavior. **298 reference tests passed, zero skips.** |
| [React/browser run 41664556136](https://github.com/OpenxIntelligence/open-intelligence/actions/runs/41664556136), job 126016288044 | **276 client tests passed, zero skips**; TypeScript/Vite build, inherited browser workflow and the new DOI browser journey passed. |
| [Reference UI run 41664556375](https://github.com/OpenxIntelligence/open-intelligence/actions/runs/41664556375) | Completed successfully. |
| Actual container recovery in the API run | All five patient, source, review, follow-through and combined evidence/report recovery probes passed, including actual API/DB restarts, PostgreSQL dump/restore and restored HTTP. |
| Dependency and source boundaries | No dependency added. Existing web rights inventory: 18 installed packages inspected, two optional packages uninstalled/uninspected, zero errors. Patient-data boundary gate passed. |

The new built-browser journey entered and acknowledged the public DOI, rendered
the protocol-fixture label and native bibliography, then explicitly saved it on
the same canonical question. Dropping an actual successful citation response
led to an exact retry of the same link, not a duplicate. An actual API restart
retained the citation; removing the separate lookup grant denied lookup with
404 while the independently permitted saved citation remained readable. The
existing authored report stayed unchanged. Desktop and 390-pixel mobile
screenshots were visually inspected.

The complete evidence recovery receipt records revision `0012_crossref_metadata`,
equal restored table/sequence state, one immutable Crossref projection, one
retrieval receipt and two question citations beside the existing authored
reports and task. Restored HTTP preserved exact retry identities, denied a
revoked patient binding and withheld the withdrawn DOI title/URL. Refetch did
not create a fresh metadata grant. The original database remained unchanged.
The receipt explicitly records `protocol_fixture`, `live_crossref_verified:
false`, `clinical_approval: false` and `model_executed: false`.

The [web verification artifact](https://github.com/OpenxIntelligence/open-intelligence/actions/runs/41664556136/artifacts/13244367098)
has SHA-256 `e8c0471400b468cde6a2ae2fdb30135634baf714f0bcbd5eb9ff41d199ec43b4`.
Its recorded commit and all 406 source blobs were checked against the published
runtime tree. The [complete recovery receipt artifact](https://github.com/OpenxIntelligence/open-intelligence/actions/runs/41664556129/artifacts/13245348190)
has SHA-256 `eb1075c3d0390b380cb02506678d6eecd25190945e4700ed3a81e7e934ede654`;
its downloaded receipt was inspected. Both artifacts expire on 10 November
2026; their identities and outcomes remain recorded here. Local tests that
skipped PostgreSQL were not used as database acceptance.

Implementation owners are `src/open_intelligence/crossref_metadata.py`,
`apps/api/src/oi_api/crossref_contract.py`, `crossref_evidence.py`, migration
`0012_crossref_metadata.py`, and the existing `question-evidence-view.ts`,
`question-evidence-panel.tsx` and `registry-client.ts`. Focused tests live in
`tests/test_crossref_metadata.py`,
`apps/api/tests/test_crossref_question_evidence.py`, the existing web test
files, `apps/web/tools/crossref_citation_journey.py` and
`apps/api/tools/verify_evidence_compose.py`. Independent review corrected
acquisition-mode coercion, timestamp/UTC overflow and encoded DOI URL limits
before these final runs. No source activation, article ingestion, scientific
appraisal, model execution or professional signoff follows from these results.

### Research register additions from this increment

These are scoped additions to OI-004/008/012/013 and issue #117, not another
roadmap or a change to the primary patient/clinical workflow.

| Open question | Why it matters and current evidence | Options / research required | Review, dependencies and recommendation |
|---|---|---|---|
| What precise H1 DOI operation may be activated? | Official policy supports factual bibliography, while the canonical register still holds patient-context, clinical and commercial activation. No live-provider acceptance was performed here. | Keep disabled; or review the DOI-only external request plus separately authorized local citation attachment for a defined synthetic pilot. Verify applicable terms, intended use, retention and operational access. | Legal/privacy and clinical/intended-use reviewers; depends on the source-operation record and host egress policy. **Recommended:** remain disabled until that review is recorded. Founder approval applies to product/release scope or a commercial commitment, not this reversible engineering increment. |
| How should a citation be associated with an independently permitted original? | #307 already owns authored passages/reports; a DOI identity alone proves neither quotation provenance nor article rights. | Explicit source-version/identifier association after verification, or a separately qualified open-content adapter. Inspect exact edition, quotation anchors, attribution and store/display/process/export permissions. Preserve #159's discovery ownership. | Evidence workflow owner, scientific reviewer and rights reviewer; depends on the canonical original/evidence/rights contracts. **Recommended:** explicit provenance association first; no inferred matching or automatic clinical support. Commercial licenses require the appropriate approval. |
| What bounds will production provider execution enforce? | The inherited socket timeout and new process-local gate do not create an overall deadline, server cancellation or a shared quota. | Evaluate a supervised provider worker or an appropriately reviewed transport, explicit total deadlines, cancellation, cache policy and aggregate request limits. Test slow delivery and multiple workers before selecting an approach. | Platform/security owner; depends on the unresolved production hosting model and dependency review. **Unresolved:** no new infrastructure or dependency selected. Founder approval only if commercial/hosting commitments change. |
| How will correction/retraction status affect an investigation? | The current factual projection records identity and citation fields, not a complete post-publication status history. Rights withdrawal and a scientific retraction are different events. | Inspect the existing provider's structured update metadata and independent retraction sources; define exact versions, monitoring, contradictory notices and reassessment rules before ingestion. | Evidence/scientific reviewer with rights owner; depends on operation clearance and investigation dependency events. **Unresolved:** a metadata citation remains unappraised and cannot represent a complete evidence assessment. |
