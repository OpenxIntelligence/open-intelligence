# Bounded concurrent private-archive reads

## Intent and ownership
Continue the transport client in draft #320 at
`583f77255b6fb00386fbed3005a01cc3c8874c6b` (tree
`2ee591beb1282f66a71f5d07925c51aa526212d5`). A slow archive must not cause
one injected transport to open an unbounded number of connections or accumulate
an unbounded number of in-flight response buffers. Advance OI-006/OI-013 without
replacing the canonical patient/source/image owners or activating an archive.

Live inspection on 3 November 2026 found no review comments on #320. Separate
#331/#332 own richer archive/history integration; #327 owns image inspection and
report convergence. This change stays within #320's transport owner.

## Approaches and engineering decision
A waiting queue would retain callers and require independent queue, fairness,
authority-refresh and cancellation policy. A distributed admission service would
add deployment/state ownership prematurely. Choose a small, non-waiting,
process-local capacity shared explicitly by operator-created adapters. This is
an engineering choice under the standing continuation mandate, not a new
production architecture or an independently approved deployment policy.

## Contract
`ArchiveReadCapacity(max_in_flight=4)` is an immutable configuration with a
thread-safe bounded semaphore. Accept only integers 1 through 16 (not booleans).
It stores no patient identifiers, request data or credentials. Each
`UnixSocketImageArchive` receives a keyword-only `capacity`, defaulting to a new
four-read capacity. Reuse the same capacity object when several adapters in one
process must share a single limit; no module-global pool or implicit path registry.
The original three constructor arguments remain compatible.

Validate identifiers, then try admission without waiting. When full, return the
existing generic `ArchiveTransportError` before allocating a socket, sending
identifiers or reading upstream bytes. No automatic retry, local fallback, new
queue or background task. The HTTP owner retains its existing sanitized 503 and
must not create a successful-read receipt on capacity refusal.

Hold the slot through connect, peer-UID verification, send, bounded receive,
EOF check, parsing, deadline check and socket closure. Release exactly once on
success, malformed input, peer mismatch, disconnect, timeout, and exceptional
unwinding, including cancellation-like BaseException. Never swallow that
BaseException. Failed admission must not release someone else's slot.
Existing per-read size limits, total deadlines and authorization remain unchanged.

## Verification and non-goals
First reproduce excess admission with the existing default reader. Add real
Unix-socket tests for default/custom/shared/separate capacity, simultaneous
contenders, no-socket refusal, parsing lifetime, failure/timeout cleanup and
exceptional unwinding. Retain all 34 original transport tests unchanged. Add
actual PostgreSQL/HTTP tests for saturated-read denial without receipt/fallback,
recovery after capacity is released, and permission withdrawal during the active
read while excess work is refused. Use only independently authored fixtures.

A slot bounds transport activity, not all application memory: canonical custody
preflight and returned bytes are outside it. Separate capacities/processes do
not share limits. Create capacities in each worker after any process fork;
production worker counts need separate aggregate sizing. The values 4 and 16 are
conservative engineering bounds, not measured service-capacity claims. This does
not solve gateway isolation, raw-PACS bypass, whole-service ingress limits,
external archive recovery, clinical qualification or independent review.

No migration, dependency, frontend, workflow, public API schema, permission,
production setting, merge or deployment is included.

Primary API reference checked 2026-11-03:
https://docs.python.org/3.12/library/threading.html#semaphore-objects
The standard library provides non-waiting semaphore acquisition and bounded
release checks; implementation is original project code.
