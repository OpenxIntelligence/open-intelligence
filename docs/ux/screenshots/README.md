# H1 frontend audit screenshots

Date: 2 November 2026 (America/New_York).

All screenshots use independently authored fictional identities and sources. Only opened/inspected captures should be included. Baseline and redesigned captures are kept separately; they are interface evidence, not clinical or user-study outcomes.

## Baseline capture names

The accepted before-images are saved under `before/`, with byte hashes/dimensions in `before/manifest.json`: `01-entry-desktop.png`, `02-patient-open-desktop.png`, `03-records-desktop.png`, `04-amendment-desktop.png`, `05-source-history-desktop.png`, `06-records-mobile.png`, and `h1-mobile.png`.

The baseline is exact PR #200 commit `d8de9aaca352cc58b64e9e32440f4ea248b02cb8`, with actual Chromium over FastAPI/PostgreSQL 16. Observations and limits are in the main report and baseline audit.

## Redesigned capture names

The final inspected after-images are saved under `after/`, with byte hashes/dimensions in `after/manifest.json`: `ux-clinical-records.png`, `ux-patient-records.png`, `ux-patient-records-mobile.png`, `ux-source-reading-desktop.png`, `ux-source-reading-mobile.png`, `ux-long-source-mobile.png`, `h1-desktop.png`, and `h1-mobile.png`.

All eight after-images were opened and inspected from the final passing actual-API browser run. Their product/test source is local checkpoint `0b741bf8ef7987ab4396474e3fbf0fa4b0f7e053`, on reconciled parent `68935c9fc60ef229aa9ff6cc4238153dc01a9b91`. A hosted publication commit may differ in documentation only; exact product/test hashes are in the boundary report. Earlier intermediate captures are not included as final evidence.

The 320px `ux-long-source-mobile.png` is a scrolled stress capture, so part of the long case eyebrow is above the visible content edge. The document identifier wraps; patient identity, source heading and filters remain visible. This is not a full-document screenshot. The normal 390px source-reading capture places the heading and focused filter below the sticky patient header.

Screenshots show independently fictional identities; repeated runs use different generated patient IDs. They are not matched patient records or a participant study. The separate browser log establishes the executed scope, focus, reflow, error and permission checks.
