# H1 original-source response authority

The next PDF/source migration must retain original bytes through the same source
owner. Inspection of #300 at 818c67f found its existing original route constructs
OriginalSource after the owner commits, and lets FastAPI encode JSON after the
registry context exits. Unlike index/brief/evidence reads, this leaves response
construction and actual encoding outside final authority and receipt rollback.

Bounded repair: extend PostgresSourceVersions.original with the existing optional
trusted prepare_response callback. Reserve the receipt ID, prepare the complete
response under existing patient/binding locks, recheck the same bearer, append
the existing receipt, commit, return. The HTTP adapter validates OriginalSource
and constructs JSONResponse inside that callback. Keep direct domain callers'
existing dict result and the unchanged public response schema.

Do not create a source store, PDF representation, migration, permission, dependency
or new event. Do not adopt another branch's evidence or recovery changes. Tests
must distinguish current/historical originals and prove response failures or
late grant/identity changes cannot disclose bytes or leave an access receipt.
Existing successful source hashes/bytes, same grant semantics and event ownership
must remain intact. This is a source-download prerequisite, not completed PDF
intake, clinical review, production identity or clinical validation.
