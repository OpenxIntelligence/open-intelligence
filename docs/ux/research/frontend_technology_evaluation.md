# Open Intelligence — Frontend technology evaluation

Research date: **2 November 2026 (America/New_York)**  
Status: researched alternatives; no dependency adoption authorized by this document.

## Decision

Preserve the accepted **React + Vite + TypeScript** H1 architecture. Implement the bounded redesign through React components, authored CSS tokens and native HTML controls. **Add no production or development dependencies for this slice unless the implementation identifies a concrete requirement that the existing toolchain cannot meet. Next.js is explicitly excluded by AGENTS.md.**

The source comparison below establishes upstream license declarations and documented capabilities. It is not an exact-version dependency clearance, bundled-asset audit, security audit or clinical qualification. Any later integration must pass the repository's existing exact-version, origin, integrity and LICENSE/NOTICE gate; a root MIT or Apache declaration does not clear every transitive dependency, font, asset, paid extension or service.

## Inspected local baseline

The selected H1 baseline is d8de9aaca352cc58b64e9e32440f4ea248b02cb8. The researcher read AGENTS.md, README.md, the relevant plan/backlog sections, apps/web/package.json, apps/web/README.md and apps/web/src/main.tsx after the snapshot became available.

| Layer | Observed implementation | Decision for this redesign |
|---|---|---|
| UI runtime | react 19.3.1 and react-dom 19.3.1 | Retain versions and existing state/session boundaries. |
| Language/build | TypeScript 5.9.3; Vite 7.3.7; Node >=22.12.0 | Retain existing build. No framework migration. |
| Types | @types/react 19.3.0; @types/react-dom 19.2.2 | Retain. |
| Build overrides | esbuild-wasm 0.28.2; @rollup/wasm-node 4.67.4 | Preserve reviewed overrides; do not simplify them by silently reintroducing native/uncleared packages. |
| Styling | Authored styles.css | Introduce/refine CSS custom-property tokens and reusable classes here. |
| Client state | RegistrySession with useSyncExternalStore; explicit current patient/source state | Presentation refactor only; keep permission, request, retry and stale-response semantics intact. |
| Unit checks | TypeScript compile plus Node test runner | Reuse existing tests; add meaningful presentation tests only when needed. |
| Browser checks | Existing Python standard-library CDP harness and Chromium | Reuse for screenshots, keyboard, responsive and actual API journeys. |
| Rights | Existing lock/supplier-notice gate | Run unchanged; no new license policy. |

The README records that a Vite 8 candidate was held because of Lightning CSS MPL-2.0 and missing native notice files. The current application therefore has a deliberate dependency boundary. This research does not reopen that decision or relabel a held component as permissive.

## Framework, language and styling alternatives

| Candidate | Verified upstream declaration | Documented capability and fit | Decision |
|---|---|---|---|
| React | [MIT](https://raw.githubusercontent.com/react/react/main/LICENSE) | [Official integration guidance](https://react.dev/learn/add-react-to-an-existing-project) supports incremental UI work. Already the accepted runtime. | Keep; extract bounded presentational components as useful. |
| Next.js | [MIT](https://raw.githubusercontent.com/vercel/next.js/canary/license.md) | React framework alternative; choosing it would be an architectural change. | Excluded by accepted H1 decision, regardless of license. |
| TypeScript | [Apache-2.0](https://raw.githubusercontent.com/microsoft/TypeScript/main/LICENSE.txt) | Already provides typed contracts and a compilation gate. | Keep exact version; do not weaken API types to make the new UI compile. |
| Tailwind CSS | [MIT](https://raw.githubusercontent.com/tailwindlabs/tailwindcss/main/LICENSE) | [Vite installation guidance](https://tailwindcss.com/docs/installation/using-vite) shows the build integration; utility CSS can standardize spacing and variants. | No need for this bounded redesign; authored tokens are sufficient. |
| CSS Modules | A technique supported by [Vite](https://vite.dev/guide/features.html#css-modules), not a single separately licensed runtime library. | Scoped class names can help when components and global CSS begin to collide. | Compatible future option within Vite; not necessary to reorganize all styles now. |
| CSS design tokens | Original project CSS; no new third-party runtime. | Share colors, spacing, focus styles, borders and responsive rules across patient/care-team presentations. | Adopt/refine tokens in existing CSS. |
| Other frameworks | Not shortlisted for migration. | The accepted React stack is already present; this request identifies no unmet capability requiring a rewrite. | Preserve architecture and measure before proposing a framework change. |

## Component ecosystems

No library makes the completed application automatically accessible. Evaluate the exact interaction, labels, focus, content and composition. Avoid installing multiple competing component ecosystems.

| Candidate | Upstream license/source | Potential benefit | Fit and decision |
|---|---|---|---|
| shadcn/ui | [MIT](https://raw.githubusercontent.com/shadcn-ui/ui/main/LICENSE.md); [official model](https://ui.shadcn.com/docs) | Distributes editable component source rather than an opaque design system. | Good ownership model if a specific component is later needed, but copied code and every imported dependency still require qualification. Do not import a dashboard template wholesale. |
| Radix Primitives | [MIT](https://github.com/radix-ui/primitives/blob/main/LICENSE); [official introduction](https://www.radix-ui.com/primitives/docs/overview/introduction) | Unstyled primitives with interaction/focus behavior and incremental adoption. | Candidate for a genuinely complex dialog/popover/menu; prefer native elements for the current simple disclosures and navigation. |
| Material UI | [MIT for core](https://raw.githubusercontent.com/mui/material-ui/master/LICENSE); [official overview](https://mui.com/material-ui/getting-started/) | Comprehensive React components and theming. | Larger design-system adoption than this slice needs. [MUI X Pro/Premium use commercial licensing](https://mui.com/x/introduction/licensing/); do not treat the entire ecosystem as MIT. |
| Ant Design | [MIT](https://raw.githubusercontent.com/ant-design/ant-design/master/LICENSE) | [Broad React component set](https://ant.design/docs/react/introduce/). | Could support dense operational tools; adopting its full visual/component system is unnecessary for the current record-inspection workspace. |
| React Aria | [Apache-2.0](https://raw.githubusercontent.com/adobe/react-spectrum/main/LICENSE); [official components](https://react-aria.adobe.com/) | Accessible behavior, custom styling and internationalization support. | Strong candidate if complex collections or interaction patterns become necessary; no immediate dependency need for this slice. |

The recommendation is compatible with later adoption of one carefully scoped primitive library. It is not a policy to rebuild complex accessible interactions from scratch. The current implementation can use native buttons, labeled inputs, lists, definition lists and disclosures with modest authored CSS.

## Data, visualization and forms

| Candidate | Upstream license/source | Benefit | Fit and decision |
|---|---|---|---|
| TanStack Table | [MIT](https://raw.githubusercontent.com/TanStack/table/main/LICENSE); [official headless-engine description](https://tanstack.com/table/latest) | Sorting, filtering, pagination and column logic separate from markup. | Consider when a real multi-column workflow needs it. It does not supply complete accessible presentation by itself; current small case/source lists need no grid engine. |
| Recharts | [MIT](https://raw.githubusercontent.com/recharts/recharts/main/LICENSE); [upstream accessibility documentation](https://github.com/recharts/recharts/blob/main/storybook/stories/API/Accessibility.mdx) | React chart composition; 3.x documentation describes default keyboard/screen-reader support. | No chart required for source inspection. A later chart needs unit/date correctness, accessible summary/data alternative and exact version qualification. |
| Apache ECharts | [Apache-2.0](https://raw.githubusercontent.com/apache/echarts/master/LICENSE); [official accessibility guidance](https://echarts.apache.org/handbook/en/best-practices/aria/) | Broad charting capabilities. The documented accessibility module/configuration is opt-in. | Defer; no clinical trend or visual inference should be added from unqualified source data. Accessibility configuration is not optional merely because a chart library exists. |
| React Hook Form | [MIT](https://github.com/react-hook-form/react-hook-form/blob/master/LICENSE); [official getting started](https://react-hook-form.com/get-started) | Reusable form values, errors and submission behavior. | Current access/identity forms are small and already implemented. Introducing a form framework could alter validation/submission behavior; not needed. |
| Zod | [MIT](https://github.com/colinhacks/zod/blob/main/LICENSE); [official schema documentation](https://zod.dev/) | Runtime schema validation with TypeScript inference. | Existing contract validation must remain authoritative and unchanged. Do not replace it during a presentation task. |

Charts, form libraries and table engines solve different problems. None is a prerequisite for a modern-looking healthcare product. The first test is whether an actual supported task becomes more reliable or maintainable.

## Documentation and testing tools

| Candidate | Upstream license/source | Role | Fit and decision |
|---|---|---|---|
| Storybook | [MIT](https://raw.githubusercontent.com/storybookjs/storybook/next/LICENSE) | [Isolated component development/documentation](https://storybook.js.org/docs). | Consider when the reusable component inventory warrants it; a concise component convention document and existing render states suffice now. No hosted visual service added. |
| Playwright | [Apache-2.0](https://raw.githubusercontent.com/microsoft/playwright/main/LICENSE); [accessibility testing limitations](https://playwright.dev/docs/accessibility-testing) | Browser journeys, screenshots, responsive and input tests. | Strong general option, but the existing CDP harness already exercises real API behavior. Reuse it for this slice rather than introduce parallel infrastructure. |
| Vitest | [MIT root](https://github.com/vitest-dev/vitest/blob/main/LICENSE); [bundled-license inventory](https://github.com/vitest-dev/vitest/blob/main/packages/vitest/LICENSE.md) | [Test runner powered by Vite](https://vitest.dev/guide/). | Conditional future option. Existing Node tests already cover session contracts; changing the runner provides no immediate UX benefit. |
| React Testing Library | [MIT](https://github.com/testing-library/react-testing-library/blob/main/LICENSE); [user-centered testing principles](https://testing-library.com/docs/guiding-principles/) | DOM-focused component tests around user interactions. | Useful if component behavior expands. For this slice, use existing browser coverage for navigation/focus and retain existing client tests. |
| axe-core / axe tooling | [axe-core is MPL-2.0](https://raw.githubusercontent.com/dequelabs/axe-core/develop/LICENSE) | Automated accessibility checks. | **Not a permissive license.** Do not add it to this repository under the existing gate merely because it is a development tool. If a separately provided scanner is used, document tool/version and limits without claiming runtime adoption or full conformance. |

Automated checks and screenshots are useful evidence, but neither proves complete accessibility. Use keyboard inspection, accessible-name/status checks and manual assistive-technology testing for remaining risks. This follows [official browser-testing guidance](https://playwright.dev/docs/accessibility-testing), not a claim that switching test frameworks establishes compliance.

## Adoption record

**Recommended immediate production additions:** none.  
**Recommended immediate development additions:** none.  
**Recommended refinements:** authored CSS tokens; reusable presentational React components; native semantic controls; task-oriented headings and context; tests in the existing harness.  
**Rejected for this scope:** Next.js, wholesale frontend rewrite, multiple UI kits, new chart engine, new runtime validation rules, new hosted service, changing the rights gate.  
**Deferred with a trigger:** a primitive library for an interaction that cannot be implemented robustly with native controls; a table library for demonstrated complex collection requirements; component-testing infrastructure when material independent component behavior exceeds current coverage.

Actual adoption, exact dependency diff, build results and rights results must be recorded by the implementing agent. This research does not claim those checks were executed.
