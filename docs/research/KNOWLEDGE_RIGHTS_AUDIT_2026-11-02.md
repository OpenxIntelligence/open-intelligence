# Open Intelligence: evidence integrations and rights gates

Research date: 2026-11-02. This is an implementation-oriented assessment for the existing platform, not a replacement architecture or a legal opinion. Official documentation verifies the access surfaces below; no authenticated integration, account entitlement, service-level guarantee, or production request was tested. No patient records, Sid data, or patient-derived evaluation material were accessed or used.

## Recommended decision

Start with **PubMed and Crossref citation metadata, CIViC curated content, NCI Thesaurus, HGNC, and the non-proprietary RxNorm API**. Add a small corpus of **PMC articles with verified CC0 or CC BY licenses** through a current authorized retrieval route. Use **selected openFDA labeling records** only with provenance and source-document verification, observing its clinical-use disclaimer. Keep **ClinicalTrials.gov adapter implementation** moving, but complete capture and review of its current primary terms before commercial activation. Europe PMC is a useful alternate retrieval/discovery route, not an independent license to the same publications.

Treat **NCCN, ASCO, ESMO, and OncoKB** as separate commercial licensing workstreams. The initial guideline feature can be a curated catalog of bibliographic citations and outbound links, acquired from permitted metadata sources. A catalog entry must never imply that the guideline's recommendations, algorithms, figures, or prose are available to the model.

These are conservative product choices. Unknown rights are not synonymous with prohibited rights. Explicit prohibitions, unresolved permissions, and broad licenses should remain distinguishable in the data model.

## Reading the matrix

- **Explicit broad grant:** the provider or applicable artifact license expressly permits relevant copying/reuse, sometimes commercially. Its language may not name embeddings, retrieval-augmented generation (RAG), or AI.
- **Inferred implementation use:** storage, indexing, embedding, or grounded summarization is proposed under that broad grant, subject to artifact scope, attribution, source terms, and any other applicable rights. This is not an assertion that the provider has specifically approved the product's AI use.
- **Unresolved:** the necessary grant was not verified, the rights vary by record, or the current primary terms could not be retrieved in this review.
- **Restricted:** primary terms expressly limit the activity or require a separate agreement.

Commercial operation, customer-facing display, model prompting, embedding generation, model training, evaluation, and redistribution are separate uses. An API key or successful HTTP response proves none of these permissions. CC BY 4.0 grants sharing and adaptation, including commercial uses, with attribution, a license link, and change notices; CC0 supplies a broad copyright waiver but does not eliminate privacy, trademark, or other rights. [S29–S30]

## 1. Verified access surfaces

“Not verified” below means this review did not establish an official provider-supported implementation; it does not mean none exists. **No official provider MCP server was verified for any source in this table.** Community MCP wrappers are adapters, not content licenses, and should not be represented as official. Use ordinary documented APIs for the MVP; an internal MCP wrapper can later expose the same rights-filtered methods.

| Source | Official API or machine access verified | SDK / official client status | Content boundary and implementation choice |
|---|---|---|---|
| PubMed / NCBI | E-utilities; annual XML baseline and daily updates. | Official E-utilities documentation verified; no SDK dependency needed. | Bibliographic records and abstracts, not journal full text. Use metadata-only responses/projection. NCBI documents 3 requests/second without a key and 10/second with a key; batch and back off. [S01–S03] |
| PMC | Cloud Service, OAI-PMH, E-utilities, BioC are the current authorized automated routes. | No dedicated official SDK verified; standard HTTP/cloud client suffices. | Full text is a separate resource with article-level rights. The current dataset page reports removal of legacy FTP/cloud dataset files in August 2026. Do not implement old OA FTP assumptions. [S04–S06] |
| Europe PMC | REST article service, OAI-PMH, documented bulk services. Canonical REST base: `https://www.ebi.ac.uk/europepmc/webservices/rest/`. | No official SDK verified. | Metadata/abstract discovery; OA full-text XML is a distinct operation. Official production pages returned 403 to this research tool; official dev/staging copies and the production reference PDF corroborated interfaces. Recheck production documentation at integration time. [S07–S09] |
| Crossref | REST, `https://api.crossref.org/`. | No official SDK verified. | DOI metadata, licenses, links, relations and updates; abstracts can be present and should be excluded by the MVP projection. A full-text link is not a full-text grant. [S10] |
| ClinicalTrials.gov | API v2; NLM's own technical bulletin documents `https://clinicaltrials.gov/api/v2/studies/{NCT_ID}` and JSON retrieval. | No official SDK verified. | Registry records, structured status/locations/eligibility/results where submitted; attached study documents are separate artifacts. Current primary terms were not text-retrievable in this review. [S11–S13] |
| CIViC | V2 GraphQL at `https://civicdb.org/api/graphql`; V1 REST is deprecated and unavailable. | CIViCpy is an SDK recommended by official CIViC API documentation; verified documentation. | Structured assertions, evidence items, molecular profiles and curated text. Anonymous reads are documented at 3 requests/second over a five-minute window. Use read queries only. [S14–S16] |
| openFDA | Official JSON APIs including drug labeling and Drugs@FDA. | No official SDK required or verified. | Label sections and regulatory datasets. Dataset-specific exceptions matter. [S17–S19] |
| DailyMed | REST v2 at `https://dailymed.nlm.nih.gov/dailymed/services/v2/`; SPL ZIP/PDF and version history. | No official SDK verified. | SPL documents, label metadata and version history. Use for authoritative document linkage/version checking; do not silently inherit openFDA's license for a separate DailyMed artifact. [S20–S21] |
| OncoKB | Token-authenticated REST API and Swagger documentation. | Official OncoKB Annotator is linked by the provider. | Commercial/clinical use requires an appropriate license; a code license for an annotator does not license the knowledgebase. [S22–S23] |
| NCCN / ASCO / ESMO | Public guideline discovery pages exist. No official generally available content API, SDK, or MCP was verified. | Unverified; obtain any contracted delivery specification. | Website access, membership, PDF availability and journal publication are not blanket application-integration rights. [S24–S28] |
| NCI Thesaurus / EVS | EVS REST API and versioned terminology downloads. | Provider API verified; no SDK dependency needed. | Pin NCIt release and license; do not treat every terminology exposed by EVS as covered by NCIt's license. [S31–S33] |
| RxNorm / HGNC / LOINC | Official RxNorm REST, HGNC REST, and LOINC terminology/search/download APIs verified. | No official SDK verified. | Each terminology and artifact has its own terms; see section 4. [S34–S40] |

## 2. Eight MVP evidence sources: permissions and activation

| Source | Metadata / full-text boundary | Storage, indexing, AI, display and commercial position | Recommended MVP state |
|---|---|---|---|
| **PubMed** | Citation fields can be used without taking article text. Abstracts are third-party prose, even when returned in the same record. | NLM permits data downloading without a signed license, with attribution, non-endorsement and currency/disclosure conditions. It specifically warns that abstracts may be copyrighted and that commercial redistribution remains the user's responsibility. Metadata indexing/display is supportable subject to those terms; blanket abstract storage, embeddings, prompts, summaries and redistribution are **unresolved**, not automatically licensed. [S02–S03] | **Enable metadata.** Field allowlist: identifiers, bibliographic citation, dates, publication type, source URLs and status signals. Exclude abstract/body/figures before persistence or model use unless separately cleared. |
| **PMC OA** | PMC membership, “free full text,” OA labeling, and a PMCID do not establish a particular reuse license. | The OA collection includes commercial-capable, noncommercial, and other licenses. Each article's copyright/license statement governs. Storage and display under verified CC0/CC BY have an explicit broad basis; indexing/embedding/RAG are proposed uses under that grant, not separately named AI permissions. Third-party images or supplements may have different rights. [S04–S06, S29–S30] | **Enable per artifact, text only initially.** Allow CC0 and reviewed versions of CC BY. Hold NC, ND, SA, custom, missing or inconsistent licenses for review. This hold is a product simplification: SA/ND are not blanket commercial prohibitions. Author-manuscript text-mining availability is not treated as a general customer-display license. |
| **Europe PMC** | REST/OAI exposes both metadata and an OA full-text subset; abstracts and full text remain rights-bearing content. | Official copyright guidance reserves rights to authors/publishers, requires per-article terms, and limits automated retrieval to designated services. No repository-wide full-text/abstract commercial or AI grant was established. An independently verified article license can support reuse through an authorized route. [S07–S09] | **Optional metadata/fallback adapter.** Apply the same article rights gate as PMC. Deduplicate by DOI/PMCID and retain the actual route and license evidence; switching mirrors does not change rights. |
| **Crossref** | Primarily bibliographic metadata; some records include abstracts and full-text URLs. | Official REST documentation says almost all metadata may be used for any purpose, while abstracts may be copyrighted. Storage, indexing and display of selected bibliographic fields have a strong basis; metadata embedding/RAG is an implementation inference. Abstract/full-text AI use and display need separate clearance. License metadata describes a work; it is not a grant from Crossref to that work. [S10] | **Enable metadata.** Project out abstracts; use DOI resolution, deduplication, publication updates and license discovery. Reconcile license assertions against the actual acquired artifact. |
| **ClinicalTrials.gov** | Registry facts versus sponsor-written prose, posted protocols, consent forms and publications. | Official NLM sources verify API access and warn that some ClinicalTrials.gov data may carry third-party copyright and international copyright. The current primary terms page rendered only a shell, so this review cannot certify storage/indexing/display/commercial or AI rights under its full current terms. This is **unresolved**, not a finding that reuse is forbidden. [S11–S13] | **Build adapter; activation gate.** Capture current provider terms and approve a field/use policy first. Prefer factual identifiers/status/dates/locations and source links. Do not import attachments or claim that registry listing validates a trial's science. |
| **CIViC** | CIViC's curated knowledgebase versus the papers it cites. | Provider FAQ releases CIViC content under CC0 1.0; application code is separately MIT. Storage, indexing, display and commercial reuse of CIViC-owned content have an explicit broad basis. RAG/embedding is a proposed use under CC0, not a provider-specific clinical or AI endorsement. Cited article text does not acquire CC0 through the citation. [S14–S16, S30] | **Enable curated evidence.** Preserve record IDs, revision/snapshot, evidence level/type/direction, review status and citations. Use accepted records by policy; keep contradictions visible. Do not translate CIViC levels into NCCN categories. |
| **openFDA labeling** | Selected drug-label data versus unrelated openFDA datasets and source attachments. | openFDA generally applies public-domain/CC0 terms, with exceptions for third-party works. Its SPL dataset page specifically lists public domain/CC0. This supports commercial reuse, storage and display of that licensed dataset; indexing/RAG is an inference. The API explicitly warns that its data are unvalidated for medical-care decisions. License clearance is not clinical validation. [S17–S19] | **Conditional enable.** Start with a curated drug list, preserve source IDs and label dates, identify archived/replaced data, and link to the original label. Do not make openFDA the sole medication decision authority. Exclude unrelated licensed fields such as GMDN. |
| **DailyMed** | Label metadata and version history versus SPL body/media/PDF. | REST access and downloads are explicit. DailyMed describes labels as company submissions; general NLM policy distinguishes government and third-party works. No DailyMed-specific blanket commercial/AI grant was verified. Therefore blanket full-text storage, embedding, redistribution and commercial display remain **unresolved** in this review. [S20–S21] | **Enable links/version checks only after a narrow metadata policy.** For label content, use a specifically cleared feed/artifact and preserve its terms. Do not assign CC0 solely because the same drug appears in openFDA. |

### Why model training is separate

The MVP should set `model_training=false` and `provider_training=false` across the evidence pipeline as an implementation default. This does not claim all source licenses prohibit training. It keeps fine-tuning and provider retention outside the initial evidence-retrieval scope. Evaluation also needs an explicit permission path: OncoKB, for example, requires specific permission for benchmarking even though an ordinary data-access license may exist. [S22]

## 3. Guidelines and precision-oncology licensing gates

| Source | Primary-source finding | MVP treatment | Agreement must resolve |
|---|---|---|---|
| **NCCN** | NCCN's JNCCN360 disclaimer reserves copying, transfer, reproduction, modification and reuse without express written authorization. The linked current NCCN EULA could not be fetched. This review does **not** treat third-party quotations of its AI clause as verified primary evidence. [S24] | Curated citation/link discovery only; no guideline prose, algorithm, screenshot, PDF ingestion, embeddings or generated recommendation from NCCN content absent rights. | Exact covered products/versions; machine delivery; cache/index/embedding; model prompts and vendors; output/display/snippets; clinical/commercial uses; attribution; update obligations; termination/deletion. Capture current EULA. |
| **ASCO** | Current official terms explicitly restrict AI ingestion, processing, analysis and outputs, uploads to AI tools, automated copying/TDM, and commercial content reuse absent authorization. [S25] | Provider website/app content disabled for model ingestion and content mirroring. Obtain discovery citations through permitted metadata routes. | Written rights for the intended AI workflow and commercial display. An independently licensed journal article acquired through an authorized route requires artifact-specific review; site terms are not a reason to mislabel every ASCO-related publication identically. |
| **ESMO** | Official ESMO materials reserve reproduction rights absent written permission unless otherwise indicated; its guideline author agreement assigns guideline copyright to ESMO. Some journal artifacts can carry separate user licenses. No blanket commercial AI license or official guideline API was verified. [S26–S28] | Discovery only. Do not infer reuse rights from a free PDF, slide set, living-guideline page, or ESMO Open branding. | License per article/product and version, authorized delivery, commercial RAG/embedding, display/derivatives, living-guideline refresh and attribution. Independently eligible CC BY artifacts may enter the ordinary article gate after verification. |
| **OncoKB** | Commercial and clinical use need licenses; academic API access also requires licensing. Local database copies need separate case-by-case approval and fees. FAQ explicitly disallows AI/ML training; benchmarking requires express permission. [S22–S23] | Adapter stub disabled until contract/token and use policy are approved. Do not use downloaded public lists as an assumed exception to commercial terms. | RAG versus prohibited training; caching/embeddings; excerpts and customer reports; jurisdiction; API entitlements; local-copy needs; evaluation/benchmarking. A commercial license alone should not be assumed to settle every use. |

## 4. Terminology foundation

Use terminology to normalize what the evidence says, while preserving original text and coding versions. It does not independently establish diagnosis, equivalence of disease subtypes, variant pathogenicity, or treatment applicability.

| Terminology | Verified rights/access | MVP recommendation |
|---|---|---|
| **NCI Thesaurus** | Current NCIt terms specify **CC BY 4.0** and reserve its name/trademark. Official EVS REST and versioned downloads exist; the download page identifies release-specific README information. [S31–S33] | Use for cancer concepts. Store code + display + release + attribution. Pin a released build; do not silently rewrite historical mappings. Other vocabularies or mappings served by EVS require their own rights assessment. |
| **HGNC** | All HGNC data are published under CC0. Official REST supports search/fetch and requests at no more than 10/second. [S38–S39] | Use stable HGNC IDs and preserve approved/previous symbols. Useful for gene normalization; not a variant interpretation database. |
| **RxNorm** | NLM-created normalized names/codes are public domain; full monthly/weekly downloads require a free UMLS license and include proprietary sources. RxNorm API normally returns non-proprietary content; RxClass/SNOMED is a separate exception. [S34–S37] | Start with non-proprietary RxNorm API. Pin retrieval/version, preserve ingredient/product distinctions. Do not bulk import UMLS or enable RxClass merely because RxNorm is allowed. |
| **LOINC** | Official license permits commercial/noncommercial use, copying and distribution subject to conditions, including notices, protection of standard identifiers and restrictions on competing standards. Official APIs exist and account access is required. [S40–S41] | Add only when laboratory normalization is needed. Review exact artifact group, mapping modifications and notices. Broad clinical terminology reuse does not by itself establish a separate AI-training permission. |
| **SNOMED CT / UMLS** | SNOMED deployment requires the relevant license; territory, affiliate and web/mobile terms can matter. UMLS is a collection with source-specific restrictions, not a universal commercial sublicense. [S34–S37, S42] | Defer bulk content until the deployment territory, affiliate/UMLS agreements and redistributed sources are recorded. Store externally supplied codes without assuming permission to redistribute the full terminology. |

## 5. Compact activation policy to add to the current platform

Implement one source policy registry and one artifact-level rights check in the existing ingestion/retrieval path. A new vector database, agent framework, or replacement application is unnecessary for this foundation.

### Required provenance and rights fields

For every source record or document, store: `source`, `source_record_id`, `canonical_url`, `retrieved_at`, `source_updated_at`, `source_version`, `content_sha256`, `content_class`, `license_id`, `license_version`, `license_url`, `license_evidence`, `terms_url`, `terms_checked_at`, `rights_basis`, `rights_status`, `allowed_uses`, `attribution`, `jurisdiction_scope`, and `reviewed_by`. Version the policy that produced the decision. A record can have field-specific permissions: citation fields allowed, abstract denied, full text separately evaluated.

Suggested values for `rights_status`: `explicit_license`, `approved_interpretation`, `contract_required`, `unresolved`, `restricted`. Suggested independent `allowed_uses`: `store`, `lexical_index`, `embed`, `send_to_model`, `display_excerpt`, `display_full`, `commercial`, `evaluate`, `train`. Do not reduce this to one `open_access` boolean.

### Runtime behavior

1. **Before retrieval:** select an approved API and content projection; suppress unnecessary abstracts and attachments. Rate-limit per provider, retry with backoff, and keep credentials server-side.
2. **Before persistence:** require a source policy and resolve artifact/field rights. Preserve raw licensed source separately from derived text, and keep the license evidence with both. Unresolved documents can retain bibliographic pointers without body ingestion.
3. **Before indexing or model use:** check the specific operation, commercial scope, current policy and source exclusions. A metadata-only article must not gain full-text privileges through DOI/PMCID deduplication.
4. **Before display:** return a source citation, source date/version, access URL, attribution/license where required, and a clear distinction between quoted source text and generated synthesis. Do not claim provider endorsement.
5. **After updates or restriction changes:** suspend affected retrieval/display, invalidate cached derived material and embeddings as required, reprocess corrected records, and retain permitted audit evidence. Retractions and expressions of concern are evidence-status events, not merely bibliographic updates.

### Initial source configuration

| State | Sources / scope |
|---|---|
| `metadata_enabled` | PubMed citation allowlist; Crossref bibliographic allowlist. |
| `content_enabled_with_license` | CIViC-owned CC0 content; NCIt CC BY 4.0; HGNC CC0; NLM-owned RxNorm fields. |
| `artifact_gate_required` | PMC/Europe PMC text with verified CC0/CC BY, complete attribution and no excluded third-party content. |
| `dataset_and_clinical_gate_required` | Selected openFDA labeling, source version verified; label retrieval is separate from permission to deploy clinical recommendations. |
| `terms_capture_required` | ClinicalTrials.gov current primary terms; DailyMed content grant; both can have adapter contracts prepared meanwhile. |
| `discovery_only` | NCCN/ASCO/ESMO curated citation/URL catalog without licensed content. |
| `contract_required` | OncoKB; provider guideline content integrations; SNOMED/UMLS sources as applicable. |

### Reviewable MVP acceptance evidence

Use independently authored synthetic vignettes and rights-cleared public evidence only. **Sid's records must not enter examples, prompts, fixtures, embeddings, training, evaluation, screenshots, or incident reproductions.** This restriction applies even to purportedly deidentified or paraphrased versions.

Demonstrate: a metadata-only paper cannot supply an abstract to a model; a valid CC BY article retains attribution through an excerpt; a missing/NC/custom license stays out of the commercial corpus; a corrected or retracted record changes retrieval behavior; a guideline link cannot be mistaken for licensed guideline knowledge; and a disabled commercial source cannot be activated by adding an API token alone. These checks exercise concrete rights and provenance behavior rather than duplicating implementation.

## 6. Evidence and verification limitations

The findings are based on official pages and official project documentation accessed on 2026-11-02. ClinicalTrials.gov's current terms were not retrievable as substantive text; NLM's PubChem source registry corroborates copyright caveats but does not substitute for the full current contract. NCCN's current EULA was inaccessible; the primary NCCN disclaimer supports a reuse gate without relying on a third-party AI quote. Europe PMC production pages failed to load in the research tool, so official alternate-host documentation was used with a recheck flag. ASCO's official terms were indexed in search but direct opening returned 403. No content experiment or API response was treated as permission evidence.

This review does not determine all jurisdiction-specific exceptions, resolve all third-party content rights, establish regulatory status, or promise zero IP or clinical risk. It identifies defensible activation boundaries and the exact unresolved decisions that remain.

## Primary-source references

Each reference is a provider, government, publisher/rightsholder, or license-authority source. URLs are retained for implementation review; source content should be rechecked when the adapter or contractual scope changes.

- **S01:** PubMed data access: https://pubmed.ncbi.nlm.nih.gov/download/
- **S02:** NLM data copyright and conditions: https://www.nlm.nih.gov/databases/download.html
- **S03:** NCBI policies and E-utilities limits: https://www.ncbi.nlm.nih.gov/home/about/policies/ and https://eutilities.github.io/site/API_Key/usageandkey/
- **S04:** PMC current article datasets and authorized retrieval routes: https://pmc.ncbi.nlm.nih.gov/tools/textmining/
- **S05:** PMC copyright: https://pmc.ncbi.nlm.nih.gov/about/copyright/
- **S06:** PMC cloud service and current distribution: https://pmc.ncbi.nlm.nih.gov/tools/cloud/
- **S07:** Europe PMC REST documentation (production target; alternate official host accessed): https://europepmc.org/RestfulWebService and https://staging.europepmc.org/RestfulWebService
- **S08:** Europe PMC copyright (production target; alternate official host accessed): https://europepmc.org/Copyright and https://staging.europepmc.org/Copyright
- **S09:** Europe PMC developer access matrix / reference PDF: https://dev.europepmc.org/developers and https://europepmc.org/docs/EBI_Europe_PMC_Web_Service_Reference.pdf
- **S10:** Crossref REST and metadata rights: https://www.crossref.org/documentation/retrieve-metadata/rest-api/
- **S11:** NLM ClinicalTrials.gov API guidance: https://www.nlm.nih.gov/pubs/techbull/ja25/ja25_clinical_trials_screen-scraping.html
- **S12:** ClinicalTrials.gov primary terms, unresolved text retrieval: https://clinicaltrials.gov/about-site/terms-conditions
- **S13:** NLM PubChem source registry, ClinicalTrials.gov rights entry: https://pubchem.ncbi.nlm.nih.gov/rest/source/
- **S14:** CIViC licensing FAQ: https://docs.civicdb.org/en/latest/about/faq.html
- **S15:** CIViC official API: https://docs.civicdb.org/en/latest/api.html
- **S16:** CIViCpy: https://docs.civicpy.org/en/latest/index.html
- **S17:** openFDA terms and exceptions: https://open.fda.gov/terms/ and https://open.fda.gov/license/
- **S18:** openFDA SPL dataset license: https://open.fda.gov/data/spl/
- **S19:** openFDA API and clinical-use disclaimer: https://open.fda.gov/apis/ and https://open.fda.gov/apis/drug/label/understanding-the-api-results/
- **S20:** DailyMed official APIs: https://dailymed.nlm.nih.gov/dailymed/app-support-web-services.cfm
- **S21:** DailyMed source description and NLM copyright: https://dailymed.nlm.nih.gov/ and https://www.nlm.nih.gov/privacy.html
- **S22:** OncoKB licensing FAQ: https://faq.oncokb.org/licensing
- **S23:** OncoKB API: https://api.oncokb.org/oncokb-website/api
- **S24:** NCCN primary disclaimer, linking the EULA and permissions: https://jnccn360.org/disclaimer/ ; linked EULA unresolved: https://www.nccn.org/Store/EULA/Default.aspx
- **S25:** ASCO terms of use: https://www.asco.org/about-asco/legal/terms-use
- **S26:** ESMO rights statement: https://www.esmo.org/about-esmo/esmo-logo
- **S27:** ESMO guideline author agreement: https://www.esmo.org/content/download/405602/7849859/1/ESMO-Clinical-Practice-Guidelines-Author-Agreement-Form.pdf
- **S28:** ESMO publication copyright/user-license distinction: https://dam.esmo.org/image/upload/v1718613399/Abstract_Book__ESMO_Gynaecological_Cancers_Congress_2024_vxqk1m.pdf
- **S29:** CC BY 4.0: https://creativecommons.org/licenses/by/4.0/ ; legal code: https://creativecommons.org/licenses/by/4.0/legalcode
- **S30:** CC0: https://creativecommons.org/publicdomain/zero/1.0/ ; legal code: https://creativecommons.org/publicdomain/zero/1.0/legalcode
- **S31:** NCIt terms: https://evs.nci.nih.gov/ftp1/NCI_Thesaurus/ThesaurusTermsofUse.htm
- **S32:** NCI official vocabulary/API description: https://www.cancer.gov/about-nci/organization/cbiit/data-standards/vocabulary
- **S33:** NCIt versioned downloads: https://evs.nci.nih.gov/thesaurus-downloads
- **S34:** RxNorm terms: https://www.nlm.nih.gov/research/umls/rxnorm/docs/termsofservice.html
- **S35:** RxNorm API: https://lhncbc-portal.lhcaws-prod-pub.nlm.nih.gov/RxNav/APIs/RxNormAPIs.html
- **S36:** RxNav APIs' conditions and SNOMED exception: https://lhncbc.nlm.nih.gov/RxNav/TermsofService.html
- **S37:** RxNorm licensing FAQ: https://www.nlm.nih.gov/research/umls/rxnorm/faq.html
- **S38:** HGNC license: https://www.genenames.org/about/license/
- **S39:** HGNC REST: https://www.genenames.org/help/rest/
- **S40:** LOINC license: https://loinc.org/license ; official CDN copy accessed: https://cdn.loinc.org/kb/license
- **S41:** LOINC access/APIs: https://loinc.org/get
- **S42:** SNOMED licensing: https://www.snomed.org/get-snomed

