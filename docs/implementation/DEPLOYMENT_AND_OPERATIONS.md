# Deployment and operations

The supported environment described here is a persistent **local fictional demo** plus disposable CI, not a staging or production installation. The runnable configuration is [`apps/api/compose.yaml`](../../apps/api/compose.yaml); the [H1 demo guide](../H1_DEMO.md) owns setup and the end-to-end walkthrough. Operations/security lead OI-013 owns restoration evidence. The release owner records the source SHA, lock hashes, container identities, schema revision, workflow jobs and exceptions for each candidate.

## Start and stop the demo

Run from the repository root on macOS/Linux with Docker Compose v2, Python 3.12+ and Node 22.12+. The reviewed API environment is Linux amd64; Apple Silicon requires emulation. Ports 8000 and 4173 must be free. The first build requires the previously reviewed packages and images. Use an isolated machine/directory and only the supplied fictional fixtures.

```sh
npm --prefix apps/web ci --omit=optional --ignore-scripts --no-audit --no-fund
npm --prefix apps/web run rights
npm --prefix apps/web run build
python tools/h1_demo.py up --fictional-only
curl --fail http://127.0.0.1:8000/health/ready
python tools/h1_demo.py credentials
npm --prefix apps/web run preview
```

Open `http://127.0.0.1:4173`. Keep the locally printed token private. The launcher provisions one fictional patient, case and source, and renews the local grant for 12 hours. Save work explicitly; unsubmitted text is session state. Stop the web preview with Ctrl+C and run `python tools/h1_demo.py stop`. Resume with the same `up` command, `credentials` and `preview`; keep `.local/h1-demo` with its Docker volume. Do not delete an existing volume to repair a mismatch.

## Health, migration and recovery

| Symptom or event | Operator action | Evidence required |
|---|---|---|
| Process responds but workspace unavailable | Compare `curl --fail http://127.0.0.1:8000/health` with `/health/ready`. Readiness checks PostgreSQL major 16 and the single `SCHEMA_REVISION` in [`contracts.py`](../../apps/api/src/oi_api/contracts.py); the database check does not migrate on startup. A 200 from liveness alone is insufficient. | Confirm installed source SHA, actual DB revision and bounded readiness status. Check Compose migration job separately from API startup. Never relabel an unknown/multiple head as ready. |
| Upgrade the isolated fictional database | Use the existing Compose `migrate` service via the launcher, or, only in the configured disposable test environment with `PYTHONPATH=apps/api/src:src` and its synthetic `OI_API_DATABASE_URL`, run `python -m oi_api.migrate current`, `python -m oi_api.migrate upgrade head`, then `current`. | Before/after migration revision; populated branches and original rows, hashes, note/citation receipts checked; preserve both published parent histories. For rollback prefer a verified isolated restore; do not stamp revisions or issue unconditional destructive downgrade. |
| Returned work missing, failed save, source state changed | Reauthenticate; check active binding and independent grants. Compare immutable receipts/versions; for an uncertain committed operation only retry the original request with its exact identifier/payload. Restoring a browser draft does not grant access. | Distinguish forbidden from unavailable internally; expose only bounded errors. Preserve failures and correlation IDs without recording tokens or text. |
| Recovery drill | Run the seven pinned `verify_*_compose.py` stages in the [API workflow](../../.github/workflows/h1-api.yml) in a disposable project. They cover registry, sources, FHIR lab originals, images, review returns, follow-through and evidence/report history. The [web workflow](../../.github/workflows/h1-web.yml) separately runs `python apps/web/tools/demo_journey.py` for stop/resume. | Capture commit, run/attempt, backup identifiers, byte digests, effective schema and authorized and denied reads after restore. Count skipped stages explicitly. A fresh-volume happy path is not a restored production installation. |
| Suspected unauthorized disclosure or fixture contamination | Stop the affected local service and pause exports; quarantine the fixture/run artifacts without duplicating their contents. Notify the designated security/privacy owner through the project's incident process, revoke affected access, preserve minimal audit evidence and recheck before resuming. | Owner, timeline, affected scope, revocation timestamp, replay of the reproducer and independent decision to reopen. No production incident-response SLA has been demonstrated. |

## Requirements for deployment beyond local CI

| Target | Evidence still required before promotion |
|---|---|
| Shared synthetic staging | Reproducible target-specific manifests with image digests and OS SBOM, distinct secrets, isolated networking and ingress/TLS, migration dry run, offline artifact/terms review, current authorization tests, monitored failure drill and an explicit rollback/restore rehearsal. No shared environment is provisioned by this work. |
| Institutional staging/production | Named operations/security, clinical and privacy owners; independent identity/consent/rights reviews and function-level intended use. Set measurable service and recovery targets (RPO/RTO), audit/retention/deletion, supported key management, failover and offsite restore in a separate account. Enforce denied egress and current-user checks after restoration; require incident escalation and on-call coverage before real data. |
| Scaling | Measure request rate, DB latency/locks, failure rate, queue age (only if a worker is accepted), retry/cancellation, restore duration, disk/backup capacity and operating cost. Introduce Kubernetes, cache, broker, centralized telemetry or workflow engine only if measured constraints justify a scoped decision over the existing DB-backed design. |

The Compose `api`/`migrate` services are read-only containers with dropped capabilities and no-new-privileges. Database ports are not published by the local demo configuration; the API frontend bridge still allows outbound routes. Public synthetic credentials, versioned image tags, read-only mounts and successful fictional recovery are not evidence of production encryption, complete egress isolation, immutable image provenance or clinical readiness.
