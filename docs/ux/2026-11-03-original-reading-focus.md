# Reach an original and return to its source

OI-009/010 frontend continuation. Base #335: 9d173843f924b40becba3a7dffd71717c12afb5d.

The source card opens the existing separately authorized original panel above the source list. Before this change it leaves keyboard focus at the source card, so the newly loaded original can be outside the viewport. On a successful matching read, focus the original heading. Tab then reaches Close original. Closing returns to the exact initiating version button, or the source heading if filtering removed that button. Filters are not rewritten.

Only a pending explicit source-card read can focus the panel. Source response or patient changes discard the return target; navigation also discards it, including same-section navigation. The existing RegistrySession alone governs reads, hashes, authority, cancellation and original lifetime. Denied/failed reads create no panel and clear the presentation return target. No automatic read or write is added.

Alternatives: moving the entire original panel into each source row would duplicate layout and complicate long originals; a modal adds another navigation/focus-trapping pattern. Keep the current inline panel and make its existing action discoverable through focus and scrolling.

Acceptance: actual current and historical original reads at desktop/mobile widths, heading visibility under the measured header, native Tab/Enter close and exact return target, filtered-out fallback without changing filters, and no focus replay after navigation. Retain the complete source/evidence/report/follow-up journey, denial and case/session checks. Screenshot evidence is tied to the final passing head in the PR and existing product docs.

Only main.tsx, source-reading.tsx, styles.css, the existing reading browser helper, its caller and this note change. Backend, schemas, API/contracts, authentication, authorization, source/session/business logic, dependencies, CI and original import behavior are unchanged. Fictional-only software acceptance; no full screen-reader/browser certification or clinical validation. Draft, unmerged, undeployed.

First hosted run 41676780008 failed waiting for original focus because the new test lacked the separate source_original_read grant. Metadata access did not confer original access, as required. The test now grants it only around this subscenario and restores the previous fixture grants in finally. Runtime authorization and focus code are unchanged by this correction.
