# Europe PMC metadata discovery boundary

**Status:** bounded local prototype; live access disabled by default. No clinical validation, commercial rights clearance, or real-patient authorization is implied.

This slice extends the existing bibliography panel and maps to **OI-004** (source rights boundary) and **OI-008** (discovery distinguished from appraised evidence). It adds no dependencies, database tables, canonical source ledger, case attachment, evidence assessment or model call. Search results remain transient and unsaved pending source and permitted-use review. The existing source/rights/evidence contracts remain authoritative for any future import.

## Implemented interface

| Entry point | Behavior |
|---|---|
| `GET /api/bibliography/europe-pmc/status` | Reports operator-controlled live access and the 25-result cap. |
| `GET /api/bibliography/europe-pmc/example` | Returns independently authored fictional citation examples, without provider calls, real publication identifiers or external publication links. |
| `POST /api/bibliography/europe-pmc/search` | Requires `--enable-europe-pmc-live`. Validates the complete request and makes at most one provider request. |
| `python -m tools.europe_pmc_metadata` | Prints the offline demonstration. A positional topic without `--live` is rejected. |

The HTTP routes retain the local server's loopback Host and same-origin write checks. There is no production identity or authorization system. The Europe PMC option is independent of the existing Crossref option.

### Request contract

```json
{
  "topic": "melanoma",
  "start_date": "2024-01-01",
  "end_date": "2026-11-02",
  "page_size": 10
}
```

Only these four keys are accepted. `topic` is required: at most 120 ASCII letters, digits, spaces or hyphens, with at least one letter or digit. Whitespace is normalized. Quotes, control characters, raw query operators, URLs and caller-selected sources are not accepted. `page_size` is a true integer from 1 to 25; booleans and strings are rejected. Both dates must be supplied or both omitted/null; they must be actual ISO calendar dates within 1500–2200, with start no later than end. The default page size is 10.

The provider query is constructed as a literal title phrase:

```text
SRC:MED AND TITLE:"melanoma" AND FIRST_PDATE:[2024-01-01 TO 2026-11-02]
```

This is a deliberately narrow discovery query. It is not a systematic literature review or a comprehensive medical search. A later title/abstract, synonym or multi-term query capability requires an explicitly documented extension.

**Syntax validation is not PHI detection.** A name or identifying narrative can satisfy a character allowlist. Operators must use public research topics. No case object, patient identifier, question, selected assertion or model context is automatically added. This implementation does not qualify patient-specific search egress.

### Network controls

- Fixed HTTPS endpoint: `https://www.ebi.ac.uk/europepmc/webservices/rest/search`.
- Fixed `format=json`, `resultType=lite`, `cursorMark=*`, and `SRC:MED`; at most one page is fetched. Provider cursors and links are discarded.
- No generic URL fetch, automatic retries or redirects.
- Eight-second transport timeout and a 256 KiB response limit, read with one overflow byte. The timeout follows Python's network-operation timeout behavior; it is not an independently enforced wall-clock watchdog.
- One active request and at most one start per second per Python process. Multiple processes share no limiter; deployment would need an IP-wide budget. The provider's documented limits are 10 requests/second and 500/minute per IP, so this single-process prototype is conservative [3,4].
- Require HTTP 200 and JSON content type. Transport, decoding, truncation, malformed-envelope, identity and size failures are explicit failures. A response such as `{"version":"6.9"}` is never treated as zero results.
- HTTP status mapping: disabled access 403; invalid request 422; concurrency/local/provider throttle 429; unacceptable upstream response 502. Upstream exception bodies and URLs are not echoed.

## Metadata and provenance

The adapter projects only provider source, source ID, optional PMID/PMCID/DOI, title, author string, journal, year and first-publication date. It validates source `MED`, identifier formats, PMID/record agreement, actual dates and bounded text. Duplicate identities or results exceeding the requested page size fail the whole response. Missing optional fields remain null.

Abstracts, book/report summaries, full-text links, article license assertions, open-access flags, annotations, arbitrary URLs, provider request echoes, cursors and unknown fields are not returned or persisted. This is stronger than merely asking for `lite`: the provider reference includes book/report fields in that response class [1,2]. Titles and other provider text are rendered through `textContent`, never HTML. Publication links are constructed from a validated `MED` identifier.

Each live result page records provider, adapter version `europe-pmc-lite/1`, fixed endpoint, UTC retrieval time, a SHA-256 fingerprint of the normalized search request, and `rights_status=unassessed`. Each citation has a SHA-256 of the selected normalized metadata, excluding retrieval time, unselected provider fields and article text. This hash identifies that projection; it does not authenticate a publication or represent a hash of the full provider response.

The upstream service is unversioned at this endpoint. A bounded live contract check on 2 November 2026 succeeded for the public title topic `melanoma` with `page_size=1`: the actual adapter accepted one citation through the same projection used by the API. The verification receipt retains counts and hashes, not article text or the raw response. This single request does not certify every record shape, query, or future provider version. The reference guide used for field semantics is dated May 2022; provider drift still requires operational checks.

Provider `firstPublicationDate` may include algorithmically supplied month/day values when the original date is partial [2]. The UI displays the year in the citation and labels the detailed provider date as having unverified day precision. It does not invent an exact publication date.

Live results retain `mode=live` and the Europe PMC provider identity. Offline demonstrations retain `mode=offline_demo`, `source=DEMO`, and no DOI, PMID, PMCID, provider retrieval timestamp or publication link. The adapter never relabels fetched publications as fictional. Both paths state that results are unsaved and have not been clinically appraised.

## Rights evidence and unresolved scope

Official Europe PMC staff state that the APIs may be used in commercial web services and are free, while emphasizing that publishers/authors retain rights [3]. EMBL-EBI's terms impose no additional restrictions beyond the data owner's restrictions, subject to more specific service terms [5]. These statements do not provide a blanket CC0 license, clear article content, or authorize every AI use.

The official copyright policy requires attention to each work's rights. The production copyright page could not be retrieved during this research pass; the official staging copy was accessible [6]. No metadata-wide commercial/AI grant was established. Live opt-in controls network access; it is not legal approval. Retain this scope for review before commercial deployment. Abstracts, full text, embeddings, model grounding/training, publication-quality appraisal, and any future persistent import remain outside this slice.

No guideline content or OncoKB data is included. This extension does not change existing rights decisions or grant itself source-review status.

## Running and verification

Offline CLI demonstration:

```bash
python -m tools.europe_pmc_metadata
```

Local app with both bibliography providers offline by default:

```bash
PYTHONPATH=src python -m open_intelligence serve
```

Optional live examples below are operating instructions. Only the single one-result request recorded above was executed for this change:

```bash
PYTHONPATH=src python -m open_intelligence serve --enable-europe-pmc-live
python -m tools.europe_pmc_metadata melanoma --live --start-date 2024-01-01 --end-date 2026-11-02 --page-size 10
```

Tests use independently authored protocol fixtures and offline provider transport doubles. HTTP tests exercise an actual local server. The UI-function test executes the actual panel functions with a minimal DOM harness, checks disabled-by-default behavior, topic-only payloads, text rendering, safe record links and live/demo distinctions. The existing Chromium journey additionally exercises the real offline panel, disabled submission, literal hostile text and narrow-screen overflow. Its execution status is recorded separately in the integration verification; the DOM harness alone is not a browser layout or accessibility audit.

```bash
PYTHONPATH=src python -m unittest discover -s tests -p 'test_europe_pmc_*.py' -v
node --check web/app.js
```

Red/green observations: the initial 13 adapter/CLI tests failed while the operation was absent, then passed. The HTTP/UI tests failed on absent routes/panel, then passed. Added regression cases exposed unhandled truncated HTTP reads and oversized JSON integer errors; their fixes were verified. Independent review then reproduced a malformed client JSON request that closed the HTTP connection. The shared decoder now converts JSON `ValueError` and `RecursionError` to the existing 422 invalid-input response; an actual local HTTP regression verifies the response and absence of provider access. The final focused test count is 23. Whole-application integration results and the tested source inventory are recorded in [the integration verification](engineering/EUROPE_PMC_INTEGRATION_2026-11-02.md), separately from these focused results.

## Primary sources checked 2026-11-02

1. [Europe PMC REST documentation](https://dev.europepmc.org/RestfulWebService), official development host; production documentation was inaccessible in this research environment.
2. [Europe PMC service reference](https://dev.europepmc.org/doc/EBI_Europe_PMC_Web_Service_Reference.pdf), May 2022, field/query/date semantics. This is documentation, not a current live contract test.
3. [Europe PMC official team response on commercial access and per-IP limits](https://groups.google.com/a/ebi.ac.uk/g/epmc-webservices/c/cZLnV1JhCj8), December 11, 2024.
4. [Europe PMC official team response on lite metadata and rate/page limits](https://groups.google.com/a/ebi.ac.uk/g/epmc-webservices/c/f0TIuqrmvHw), November 25, 2025.
5. [EMBL-EBI terms of use](https://www.ebi.ac.uk/about/terms-of-use/), revised October 14, 2026.
6. [Europe PMC copyright statement, official staging copy](https://staging.europepmc.org/Copyright). Recheck the [production policy](https://europepmc.org/copyright) for any operational/commercial decision.
