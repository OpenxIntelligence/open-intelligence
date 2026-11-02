# Bounded literature metadata discovery

**Status:** implemented adapter, explicitly enabled local HTTP route, and a public-terms form in the existing Bibliography panel. Documentation retrieved **2026-11-02**. This is a bounded discovery slice for [issue #117](https://github.com/OpenxIntelligence/open-intelligence/issues/117). It adds no patient model, source ledger, evidence appraisal, persistence, vectors or model call. Root separately verified one operator-invoked generic public metadata request; that observation and its limits are recorded below.

## Verified provider contract

The provider's [REST documentation](https://dev.europepmc.org/RestfulWebService) links the production search route and distinguishes `lite` citation metadata from `core`, which adds abstracts and content links. Its [official API example](https://blog.europepmc.org/2019/08/fair-biomed-a-browser-extension-using-europe-pmc-api.html) corroborates the JSON/lite query parameters and bibliographic fields. The [web-service reference](https://dev.europepmc.org/docs/EBI_Europe_PMC_Web_Service_Reference.pdf), service 6.9.0/document 1.51 dated 2023-08-31, describes source codes, response fields, cursor pagination and page-size limits. This is a documented contract, not a claim that 6.9.0 is the currently deployed version.

| Property | Provider contract and adapter choice |
|---|---|
| Route | `GET https://www.ebi.ac.uk/europepmc/webservices/rest/search` only |
| Parameters | `query`, `format=json`, `resultType=lite`, `pageSize`, `cursorMark=*`, `synonym=false` |
| Provider page size | Published range 0–1000; adapter accepts 1–10, default 5 |
| Page policy | One first-page request; no cursor continuation or returned URL is followed |
| Response | JSON object with `hitCount`, `resultList.result`; provider `version` retained if supplied |
| Accepted records | `MED` (PubMed/MEDLINE) and `PMC` (PubMed Central); other source codes excluded and counted |
| Publication dates | `pubYear` and `firstPublicationDate` when present; provider may complete missing month/day algorithmically |
| Integrity metadata | Publication-type labels; explicit comment/correction relationships if supplied. The reference places relationship details in `core`, so `lite` cannot establish a complete integrity history |

The production documentation page returned HTTP 403 in the research environment. The accessible `dev.europepmc.org` reference is provider-controlled and links the production route; its documentation may lag deployment. The API example was available through the official blog's search-indexed result, while a subsequent direct fetch returned 520. These limitations are recorded rather than treated as live validation. The adapter records the actual response's API version instead of hard-coding a deployed version.

## Input and transport boundary

`search_europe_pmc` requires both `human_authored=True` and `public_terms_only=True`. The caller must supply independently authored public biomedical terms. It must not compose queries from patient context, medical records, conversations, uploaded files, or patient identifiers. There is no case identifier or patient parameter in this API. These booleans are **caller attestations, not a privacy detector or authorization service**. A person's name could satisfy a lexical grammar; the module must not be exposed as an unrestricted text egress endpoint.

The restricted query accepts 3–240 ASCII characters: letters, numbers, spaces and `()+/'",-`. At least one letter is required. Control characters, URL/email punctuation, dots, field selectors, and protocol-relative URLs are rejected before transport. Terms are encoded with `urlencode`; they cannot replace the fixed scheme, host, path or request parameters. This deliberately excludes some useful advanced query syntax and non-ASCII terminology. Such extensions require their own review.

The standard-library transport makes one request, uses an eight-second socket timeout, requests identity encoding, and reads at most 256 KiB plus one sentinel byte. It rejects non-200 statuses, redirects, a changed final URL, non-JSON content types, compressed responses, malformed length headers, oversized responses, invalid UTF-8, duplicate JSON keys, non-finite JSON values, and malformed response envelopes. No retries or automatic pagination occur. Raw response bodies and the query are not returned or logged by this module. Error messages and error codes contain neither input terms nor provider response text.

The timeout is a socket-operation timeout, **not a guaranteed total wall-clock deadline** against a slowly streaming peer. A deployed caller still needs an end-to-end request budget, cancellation, and aggregate rate/concurrency limits. The injected `opener` and `clock` are trusted test seams, not remotely configurable options. TLS validation uses Python's standard HTTPS transport. Environment-level network/proxy configuration remains outside this module.

## Result contract

The public result is a JSON-serializable `LiteratureSearchResult` `TypedDict`, containing provider provenance, observation time, response hash, provider counts, exclusion counts, and a list of provider-neutral `Citation` dictionaries. It is returned in memory only.

| Retained field | Meaning and limit |
|---|---|
| Citation identity | Validated source/ID pair; MED requires a positive decimal PMID, PMC a `PMC`-prefixed positive decimal ID; maximum ten digits |
| PMID / PMCID / DOI | Optional, strictly validated identifiers; a supplied primary ID must agree with the source record ID; DOI normalized to lowercase using a deliberately conservative ASCII grammar |
| Title / authors / journal | Plain untrusted bibliographic strings, capped at 1000 / 4000 / 300 characters; authors remain the provider's citation string |
| Year / first publication date | Valid four-digit year 1000–2999 or exact valid ISO calendar date; missing stays `null`; publication date carries a provider-imputation caveat |
| Publication types | At most 20 bounded labels; unexpected `pubTypeList` labels are also preserved without requesting `core` |
| Integrity markers | Explicit retraction/correction/concern type labels and bounded comment/correction relationship types/IDs; free-text notes and references are discarded |
| Record URL | Constructed from validated IDs on `https://europepmc.org/article/`; never taken from a returned link |
| Metadata hash | SHA-256 of canonical projected citation JSON, excluding the hash itself; changes with retained metadata, not retrieval time or discarded text |
| Observation provenance | Fixed endpoint, adapter version, provider API version if supplied, UTC retrieval timestamp, SHA-256 of response bytes |

Both the result and each citation declare `metadata_only=true`, `clinical_evidence_appraised=false`, `clinical_use="not evidence for a clinical conclusion"`, and `rights_status="not_assessed"`. Abstracts, article body, figures, supplements, full-text links, open-access flags, licenses, citation metrics, and the provider's echoed query are not projected. An unexpected field may exist transiently in the bounded response/parser; it is not returned, persisted, or logged by the module.

Invalid or unsupported records are excluded with coded counts. Duplicate source/ID pairs cannot produce two citations. An invalid envelope aborts the request. Counts distinguish provider hits, records on this page, and accepted citations; an empty accepted list after exclusions is not evidence that the literature contains no relevant work. The provider's relevance ordering is not an assessment of evidence quality or completeness.

`integrity.status` is either `unknown` or `provider_markers_present`. A returned relationship can be a general comment, so marker presence is not itself a judgment that an article is invalid. The parser never declares a work clean, infers retraction from its title, or treats missing markers as a completed retraction check. A syntactically valid identifier or date is not independent verification of the publication's contents or status.

## Rights and context integration

Europe PMC's [copyright guidance](https://staging.europepmc.org/Copyright) distinguishes access from reuse permissions and requires attention to individual content licenses. The [API documentation's privacy notice](https://dev.europepmc.org/RestfulWebService#privacy-notice) also forms part of the service-access boundary. Neither an accessible API nor a PMCID establishes permission to reproduce full text or use it in a model. Commercial bulk reuse, downstream display and model use have not been approved by this module. The rights state stays unassessed, including for metadata, pending the application's use-specific broker decision.

For later integration with PR93 `compile_context`, a trusted rights broker may map the validated citation identifier, title, source family, dates and metadata hash to the existing source capability contract. It must independently supply the reviewed rights state, operation permissions, approval receipt, source-version policy and content state. The citation hash represents this projected metadata observation; it is not a publisher's article version, license receipt, or authenticity proof. Do not fabricate a day from a year, conflate retrieval time with publication time, or infer `content_state=current` from a successful fetch.

This adapter intentionally supplies no `permission_receipt`, permissions object, `evidence_text`, support/contradiction relation, applicability rating or trial-eligibility assertion. Metadata candidates can guide a human's next source-selection step. They cannot establish supporting or contradicting clinical evidence, applicability to a case, or eligibility for a trial. Patient-to-evidence comparison remains a separate authorized workflow using permitted source content and human review. H1 remains a no-vector implementation.

## Local HTTP and interface boundary

Live literature search is **disabled by default**. An operator can enable it for this loopback-only synthetic application with:

```sh
PYTHONPATH=src python -m open_intelligence serve --enable-literature-live
```

| Interface | Behavior |
|---|---|
| `GET /api/literature/status` | Reports exact operator enablement, provider and the metadata-only/unappraised/unassessed boundary; no database or provider request |
| `POST /api/literature/search` | JSON body with only `terms`, `human_authored`, `public_terms_only`, and optional `page_size` (default 5) |
| Input gate | Both attestations must be literal `true`; 3–240-character terms; strict integer page size 1–10; unexpected case/context/provider fields rejected |
| Local query placement | Search terms are accepted only in the POST body. A query string on the local search route is rejected. The reviewed adapter uses the fixed upstream provider GET contract described above |
| Egress control | Existing Host/Origin/fetch-site checks precede the route. One in-flight search per bound handler and at least one second between admitted request starts; no arbitrary endpoint or transport override |
| Failure behavior | 403 disabled; 422 invalid input; 429 busy/rate-limited; 502 provider failure. Fixed messages and codes; no provider exception, query or raw response reflection |
| Persistence | These routes return before CaseStore creation. No case links, source/evidence rows, rights grants, search history, stored queries or stored provider responses |
| Logging | Request logs contain only an allowed method name, status and size; diagnostics are generic. Request lines, URLs, query strings, bodies and unknown method text are not interpolated |

`web/literature.js` is isolated from `app.js` and reads only its own Bibliography controls. It clears browser-restored terms/checkbox state, never prefills from a patient, and keeps the search button disabled until the operator status is exactly enabled and the user explicitly attests to independently authored public terms. Changing terms resets that attestation. The interface does not detect private information; public-only input remains the user's responsibility and this local gate is not production identity or authorization.

The form sends only those four fields in a local POST. It clears old results before another search, and a generation counter plus input checks discard late results/errors after terms or checkbox changes, including values changed away and back. Clear removes the terms, attestation and visible results. It does not cancel a provider request already admitted by the server; the server's concurrency gate continues to apply.

Results use literal text, exact canonical `https://europepmc.org/article/{MED|PMC}/{identifier}` links, `target="_blank"` and `rel="noopener noreferrer"`. Noncanonical links remain inert. The panel shows provider-hit, returned-page, displayed and excluded counts, unassessed rights, unknown or explicitly supplied integrity markers, and “not evidence for a clinical conclusion.” It rejects unexpected appraisal/rights-grant flags and does not read or display raw HTTP error bodies. Nothing is automatically promoted into an investigation or clinical evidence assessment.

## Focused verification and live observation

`tests/test_literature.py` uses invented bibliographic metadata only, injected responses and a frozen clock. It does not make network calls. Tests cover exact request encoding and host, explicit input attestations, input/size/date/identity failures, malformed provider envelopes, duplicate identifiers, content exclusion, stable metadata hashes, preserved integrity markers, safe error messages, and a real urllib redirect-handling path with an offline HTTPS handler.

The HTTP tests start real loopback servers with the provider mocked and CaseStore replaced by a denial guard. They cover disabled/status behavior, strict payloads and exact booleans, wrong method/route, query strings, Host/Origin, rate/concurrency, error whitelisting, CLI flags, static serving and log exclusion. `tests/test_literature_ui.js` executes the complete actual script in a DOM/fetch harness with patient-context and storage access traps; it covers deliberate submission, inert markup, canonical URL validation, result invalidation, attestation reset, failure handling and the unappraised metadata boundary.

Run the focused checks with:

```sh
PYTHONPATH=src python -m unittest discover -s tests -p 'test_literature*.py' -v
node --test tests/test_literature_ui.js
node --check web/literature.js
```

On 2026-11-02, **29 focused Python tests passed** (16 adapter tests plus 13 HTTP/CLI tests; 6.194 seconds), and **11 JavaScript behavior tests passed**. JavaScript syntax and `git diff --check` also passed. The HTTP and UI tests were first observed failing before their implementation. No external provider call or patient data was used by these tests. Synthetic CI now includes this script's syntax and the repository's JavaScript behavior tests.

The adapter's earlier module-only run recorded 266 repository tests with 16 socket-setup errors in the restricted sandbox; that is historical environment evidence. This integration used the authorized socket-enabled environment for its focused HTTP tests. **Root's final combined repository suite and hosted browser checks are separate gates; no full-suite or browser pass is claimed by this focused verification.**

Root separately ran the generic public query `oncology systematic review` with page size 3 at **2026-11-02T20:27:39Z**. The fixed production endpoint returned API version **6.9**, three accepted MED metadata records and no exclusions. The [exact observation receipt](LITERATURE_LIVE_METADATA_RECEIPT_2026-11-02.json) records the response hash, accepted identifiers and limits; it states that no patient context was used and no abstract or full text was retained. This single successful adapter observation verifies transport/schema compatibility at that time. It does not verify the browser workflow, completeness, content permissions, evidence appraisal or clinical reasoning. The application's rights state remains `not_assessed`.
