# Pathology and Molecular report inspection

Continues OI-007 / OI-010 / GH-112 on the connected React/FastAPI/PostgreSQL product. The parent is #624 at `631c3e0cea30d4b859a2e428d200d352c97c6567`, which retains #620 patient permissions, historical World Model, Imaging chronology and Labs. Its tree was recovered and checked against all source blobs before changes.

## Behavior

Pathology and Molecular now expose specimen-label and literal reported-state filters, search across current quoted statements and finding keys, loaded-scope counts and twelve-version pagination. Filtering a report's quotations explicitly indicates omitted statements. Unknown specimen metadata, absence of quotations and source-reported negative results remain distinct. Historical versions remain inspectable through the original reader, without assigning them quotations from a current version.

Source identity, original hashes, source lines and received/issued/event dates remain with the existing source contract. The browser is a projection of one already-authorized source-index response. It creates no clinical inference, specimen identity, new persistent ledger or automatic retrieval. The original and question buttons retain their existing fresh authorization and source-owner handoff. Patient/case/receipt changes reset the view. Imaging, Labs, Visits, permissions and other existing workflows remain intact.

## Verification

At the local pre-publication checkpoint, all 837 client/server-render tests passed with no skips. The added 15 tests cover statement/state intersections, precise specimen labels, history, domain isolation, pagination, empty results, raw-text escaping and unchanged source identities. The production build and existing rights gate are required. The browser acceptance extends the actual FastAPI/PostgreSQL journey with earlier pathology bytes, fourteen persisted molecular originals, page transitions, specimen and state filters, exact-statement question navigation and 320/390/1440-pixel screenshots.

Exact-head hosted browser/build/rights results belong to this candidate's PR. Donor passes are not its acceptance. Local PostgreSQL/Chromium are unavailable in the resumed environment. The full backend migration/recovery suite is not rerun for this presentation-only increment; the hosted journey exercises the unchanged API and persistence.

## Remaining construction

This closes a report-inspection usability gap only. Orders, specimen accession/tracking, assay-native structured workflows, longitudinal molecular interpretation and qualified scientific computations remain core construction targets. Persisted permissions do not establish verified identity or legal consent. The full PF-01–PF-10 and PD-01–PD-16 delivery mandate remains open. Synthetic records only; draft, unmerged and undeployed.
