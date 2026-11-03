# H1 Records → Investigations exact-source question handoff

**Status:** Synthetic-only draft, source-owner review required. Started 3 November 2026.

## Why this is a product slice

The current authenticated React/PG16 source reader (#305) displays literal authored-source quotations and exact source lineage alongside record versions. The canonical question owner (#287 → #299) already lets users author a question from Investigations after loading the World Model. A user viewing the relevant quotation in Records must currently relocate the same source statement by hand. This adds a single **Ask about this statement** control directly beside **current** quotations, with no competing storage or clinical inference.

## Behavior and failure boundaries

1. Capture the current original source ID, current document version/SHA, source-reported finding key/state, literal statement, line, patient and case from the already validated source-index response.
2. Before resetting a question intent, deny the handoff if a save is in progress/unknown or an unsaved question draft exists. The user can finish/discard the existing draft in Investigations. Nothing is silently discarded.
3. Invoke the existing, independently authorized **GET /world-model** source-owner endpoint, not a new server route. Only after that read succeeds, compare the exact current source ID/version/SHA and original source statement, key/state and line against the earlier index. A changed or missing source refuses the draft, clears derived World Model context and prompts an explicit Records refresh.
4. Only after the current literal source matches, use the existing in-memory `chooseQuestionDraft` operation. No Composer preflight, model execution, evidence-rights expansion, question save, review, export or follow-through is triggered.
5. The existing question panel handles explicit edit, source-pinned preflight, independent grants, stable save key and later reassessment. Patient/session/case/generation invalidation prevents late source reads from restoring the wrong question.

## Verification contract

Eight new Node/TypeScript client regressions verify fresh GET and no hidden write; hash/lineage/quote drift denial; permission refusal; wrong case/line/source without requests; an unfinished draft guard; no new intent during an uncertain save with same-key retry; and late patient switch.

Extend the unchanged-real-API Chromium journey over **actual synthetic PostgreSQL 16 → FastAPI → built React**: after source amendment, only a current quotation offers handoff; one fresh World Model HTTP read occurs; the user sees an unsubmitted editable draft pinned to the current v2 line; ordinary navigation preserves the draft and explicit discard clears it. Continue all inherited source reading, review, brief/download and follow-through journeys without relaxing an assertion.

## Ownership and limits

Stacked on #305 at `aea88341e260a4829d5b1647d5395b78ca17bfa6`; #305 itself stacks on #299, which reconciles canonical source/question/review/follow-through. The application still uses one PostgreSQL patient, case, original source, source question and append-only event owner.

No backend, schema, migration, package, license, runtime model, clinical content or account change. Independently authored fictional sources only. A source fingerprint is **not** a clinical authorization, and a quotation is **not** a verified medical fact. Real identity, consent, publisher rights, professional review, security qualification and deployment are blocked. Parent and main stay unchanged. No automatic merges.
