# Connected evidence safety and draft recovery

Continue OI-008/009/010/013 by composing #355 at `6f836b451c2e8426e5c3b2be194408424f95c69f` with #359 at `e2c888cf5b9065c8b6a60284666e6f35fe2c1e63` (including #348). Preserve #355's chronology validators, dependency gates, native intake, source/report/follow-through owners and #359's exact draft/session/browser behavior.

The patient outcome is a comparison that survives ordinary authorized navigation, remains recoverable after contradictory save confirmation, and is withheld when refreshed evidence fails chronology validation. Existing immutable reports and exact retry identities remain authoritative. A malformed refresh must never reauthorize a draft; receipt recovery must remain possible after that failure without creating another assessment.

Alternatives considered: #360 lacks #355's intake-disclosure continuation; #356 lacks chronology and the later receipt repair. Rewriting their behavior introduces unnecessary duplication. Reuse exact donor production/tests/browser files and retain both parent histories in the published integration commit. Reconcile documentation additively.

Use independently authored synthetic inputs only. No dependency, lockfile, backend, migration, permission, public API, workflow, clinical authority, content-rights or external-service change. No merge or deployment. This is one bounded composition, not completion of all twenty program scenarios.

Acceptance: baseline client suite; donor regressions fail before integration; full composed client suite, rights tests, installed-tree gate and production build pass; actual PostgreSQL/FastAPI/built React browser journey passes on the exact published head. Add two composition checks for malformed chronology with an editable draft and during uncertain receipt recovery. Full standalone API/backup-restore acceptance remains separately identified if not executed.
